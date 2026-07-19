"""Server-verified session cookie -- replaces the old pattern where every
route trusted a client-supplied `user_id` query/form param with no proof it
belonged to the caller (see GAPS.md "Auth is dev-grade outside LTI").

One signed, httponly cookie (`evoke_session`) carries {user_id, role}. It's
minted server-side in exactly two places: the Brightspace OAuth callback
(evoke/main.py's auth_brightspace_callback, after a verified whoami) and the
Evoke Admin login below. Every other route that needs "who is calling"
depends on get_current_user / get_current_admin instead of accepting an
identity from the request itself -- so a route's signature is now the same
thing as its access control.

SESSION_SECRET must be set to a real random value outside local dev --
sessions signed with the fallback dev secret are useless as an attack
target (anyone with the repo has it), but that's fine for a fresh clone
with no real students in it yet.
"""
import os
import secrets
from typing import Optional
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException, Response, Depends

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-only-insecure-secret-change-me")
SESSION_COOKIE = "evoke_session"
SESSION_MAX_AGE_S = 12 * 3600  # 12h -- a school-day session, not a persistent login

_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="evoke-session-v1")

# The one non-Brightspace identity: a human ops/instructor account for the
# app itself. Everything about *students* -- roster, teams, roles -- comes
# from Brightspace now (OAuth login + Groups sync); this login exists only
# so someone can reach #/admin (release gating, the Ops Deck) without an
# LMS account. ADMIN_PASSWORD_HASH is a bcrypt hash (see
# scripts/hash_admin_password.py); unset means the Evoke Admin login is
# disabled, not silently open.
ADMIN_USERNAME = os.getenv("EVOKE_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("EVOKE_ADMIN_PASSWORD_HASH")


def issue_session(response: Response, user_id: str, role: str = "learner") -> None:
    """Mint and set the session cookie. Call this from a verified identity
    source only (OAuth callback, admin login) -- never from a route that
    itself takes an unauthenticated user_id."""
    token = _serializer.dumps({"user_id": user_id, "role": role})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=SESSION_MAX_AGE_S,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def _read_session(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE_S)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session")
    return data


def get_current_user(request: Request) -> str:
    """FastAPI dependency: returns the verified caller's user_id. Use this
    in place of a route accepting `user_id` from the client -- e.g.
    `async def get_awards(user_id: str = Depends(get_current_user))`. Any
    route using this can keep its existing body unchanged, since the
    variable name and type are the same; only where the identity comes
    from changes."""
    return _read_session(request)["user_id"]


def get_current_admin(request: Request) -> str:
    """Same as get_current_user but requires role == 'admin'. Use for every
    #/admin-surfaced route (mission release gating, the Ops Deck) --
    Brightspace-authenticated learners can never hit these regardless of
    what they pass, because their session's role is always 'learner'."""
    data = _read_session(request)
    if data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin login required")
    return data["user_id"]


def require_self(user_id: str, caller: str = Depends(get_current_user)) -> str:
    """Drop-in replacement for a route's own `user_id: str` parameter --
    FastAPI still fills `user_id` from the same path/query slot the route
    already declares (dependencies resolve path/query params by name just
    like route functions do), so no URL or frontend call site changes.
    What changes: the value now has to match the caller's own verified
    session, or the request 403s before the route body ever runs. Use for
    any route where "user_id" means *the calling user's own data* --
    NOT for routes where user_id names some other target (e.g. removing a
    teammate), which need get_current_admin instead."""
    if user_id != caller:
        raise HTTPException(status_code=403, detail="Cannot access another user's data")
    return user_id


def get_current_user_optional(request: Request) -> Optional[str]:
    """Like get_current_user, but returns None instead of 401ing when
    there's no session -- for routes that personalize otherwise-public data
    (e.g. highlighting your own score on a public leaderboard) without
    requiring login just to view it. Never trusts a client-supplied
    user_id the way the old optional params did."""
    try:
        return _read_session(request)["user_id"]
    except HTTPException:
        return None


def verify_admin_password(username: str, password: str) -> bool:
    if not ADMIN_PASSWORD_HASH:
        return False
    if not secrets.compare_digest(username, ADMIN_USERNAME):
        return False
    return bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode())

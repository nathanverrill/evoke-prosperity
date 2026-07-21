"""Swappable OAuth 2.0 login providers -- AUTH_PROVIDER (.env) picks the
implementation. This is a real user clicking "Login with Central Registry"
and authorizing as themselves; distinct from the LTI 1.3 platform-launch
flow (evoke/lti/brightspace_lti_provider.py, a platform-initiated JWT launch)
and from the server-to-server Brightspace API creds evoke/lms/brightspace_lms.py
uses for roster/classlist/dropbox calls -- those can share the same
Brightspace app registration, but authenticate different things (the app
itself vs. a specific person).

Adding another provider (Keycloak, EvokeHub, ...) means adding another
AuthProvider subclass and an _PROVIDERS entry -- evoke/main.py's routes and
evoke/identity.py's get_or_create_evoke_player don't change.
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class OAuthLoginError(Exception):
    """Raised when a provider fails to authenticate a user (bad code, token
    exchange failure, provider unreachable, malformed profile response)."""


class AuthProvider(ABC):
    """One implementation per swappable login backend. All evoke/main.py's
    routes need from a provider is an authorize URL and a way to turn a
    returned code into a stable (subject, email, display_name, role) --
    everything after that reuses the same get_or_create_evoke_player path
    LTI launches and admin roster-import already share."""

    name: str

    @abstractmethod
    def authorize_url(self, state: str) -> str:
        ...

    @abstractmethod
    async def exchange_code(self, code: str) -> dict:
        """Returns {"subject": int, "email": str, "display_name": str, "role": str}."""
        ...


class BrightspaceOAuthProvider(AuthProvider):
    """Standard OAuth 2.0 authorization-code flow against D2L's Auth Service.
    Endpoints are fixed/global, not tenant-specific -- see
    https://docs.valence.desire2learn.com/basic/oauth2.html. Whoami (which
    *is* tenant-specific) falls back to BRIGHTSPACE_SIM_URL when
    BRIGHTSPACE_TENANT_URL isn't set, matching how the rest of this codebase
    already treats sim-vs-real Brightspace (see main.py's _fetch_classlist)."""

    name = "brightspace"

    def __init__(self):
        self.client_id = os.getenv("BRIGHTSPACE_CLIENT_ID")
        self.client_secret = os.getenv("BRIGHTSPACE_CLIENT_SECRET")
        self.authorize_endpoint = os.getenv(
            "BRIGHTSPACE_OAUTH_AUTHORIZE_URL", "https://auth.brightspace.com/oauth2/auth"
        )
        self.token_endpoint = os.getenv(
            "BRIGHTSPACE_OAUTH_TOKEN_URL", "https://auth.brightspace.com/core/connect/token"
        )
        self.redirect_uri = os.getenv("BRIGHTSPACE_OAUTH_REDIRECT_URI")
        self.scopes = os.getenv("BRIGHTSPACE_OAUTH_SCOPES", "core:*:*")
        # Always your real tenant -- no brightspace-sim fallback. Real
        # tenants version-lock their supported API range (checked live: max
        # lp version 1.61 on charge.yacenter.org) -- override via
        # BRIGHTSPACE_WHOAMI_VERSION if a specific tenant needs something
        # else. 1.43 is old enough to be broadly supported and whoami's
        # shape hasn't changed since.
        self.whoami_base = os.getenv("BRIGHTSPACE_TENANT_URL")
        self.whoami_version = os.getenv("BRIGHTSPACE_WHOAMI_VERSION", "1.43")
        # Dropbox (assignments/submissions) lives under the `le` product,
        # not `lp` -- same real-tenant version-lock caveat as whoami.
        self.le_version = os.getenv("BRIGHTSPACE_LE_VERSION", "1.43")
        # Team sync (Brightspace Groups -> Evoke teams) is optional -- a
        # login still succeeds without it, just with no team assigned, same
        # as a group-lookup failure below. Set to the course's org unit ID
        # (visible in its Brightspace URL) to turn it on.
        self.org_unit_id = os.getenv("BRIGHTSPACE_ORG_UNIT_ID")

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri and self.whoami_base)

    def authorize_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
        }
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if token_resp.status_code != 200:
                raise OAuthLoginError(
                    f"Brightspace token exchange failed: {token_resp.status_code} {token_resp.text}"
                )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise OAuthLoginError("Brightspace token response had no access_token")
            # Refresh tokens are enabled on the registered app -- capturing
            # these is what lets a connection (student or the admin service
            # connection) keep working indefinitely without anyone
            # re-authenticating. expires_in is seconds-from-now, per RFC 6749.
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            whoami_resp = await client.get(
                f"{self.whoami_base}/d2l/api/lp/{self.whoami_version}/users/whoami",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if whoami_resp.status_code != 200:
                raise OAuthLoginError(
                    f"Brightspace whoami failed: {whoami_resp.status_code} {whoami_resp.text}"
                )
            who = whoami_resp.json()

            # whoami's Identifier is the same underlying numeric Brightspace
            # user ID as LTI's `sub` claim, just returned as a string --
            # consistent with evoke_identities.brightspace_user_id (INTEGER).
            subject = who.get("Identifier")
            if not subject:
                raise OAuthLoginError("Brightspace whoami response had no Identifier")

            team_name = await self._resolve_team_name(client, access_token, int(subject))

        display_name = " ".join(filter(None, [who.get("FirstName"), who.get("LastName")]))
        display_name = display_name or who.get("UniqueName") or f"User {subject}"
        # whoami doesn't return a real email field -- best-effort same as
        # BrightspaceLTIProvider's own fallback for a launch with no email claim.
        email = who.get("UniqueName") or f"{subject}@brightspace.local"

        return {
            "subject": int(subject),
            "email": email,
            "display_name": display_name,
            # whoami carries no LTI-style roles claim -- same default fallback
            # BrightspaceLTIProvider._map_lti_roles uses when a launch has none.
            "role": "learner",
            "team_name": team_name,
            # Persisted by the caller (evoke_identities for a real student
            # login, brightspace_service_connection for the admin-connect
            # flow) so submissions/roster/grade calls keep working via
            # refresh_token without a human ever logging in again.
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
        }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Exchanges a refresh token for a new access+refresh token pair --
        RFC 6749's Refresh Token grant. Same token endpoint as the initial
        exchange. Returns {"access_token", "refresh_token", "expires_in"};
        raises OAuthLoginError if the refresh token itself is no longer
        valid (revoked, or the app's refresh-token support was turned off
        after this token was issued) -- callers should treat that as "the
        connection needs to be re-established by a human," not retry."""
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if token_resp.status_code != 200:
                raise OAuthLoginError(
                    f"Brightspace token refresh failed: {token_resp.status_code} {token_resp.text}"
                )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise OAuthLoginError("Brightspace refresh response had no access_token")
            return {
                "access_token": access_token,
                # D2L's refresh workflow issues a new refresh token alongside
                # the new access token (single-use, per the docs) -- fall
                # back to the old one only if the response omits it.
                "refresh_token": token_data.get("refresh_token", refresh_token),
                "expires_in": token_data.get("expires_in", 3600),
            }

    async def _resolve_team_name(self, client: httpx.AsyncClient, access_token: str, brightspace_user_id: int):
        """Brightspace's own Groups feature is the source of truth for team
        assignment -- no separate Evoke-side admin step. Looks across every
        Group Category in the configured course for a group this user is
        enrolled in; returns that group's Name, or None (login still
        succeeds, just with no team) if unconfigured, the user isn't in any
        group, or the lookup fails for any reason -- team sync is a
        best-effort enrichment, never a login blocker."""
        if not self.org_unit_id:
            return None
        headers = {"Authorization": f"Bearer {access_token}"}
        base = f"{self.whoami_base}/d2l/api/lp/{self.whoami_version}/{self.org_unit_id}/groupcategories/"
        try:
            cat_resp = await client.get(base, headers=headers)
            if cat_resp.status_code != 200:
                logger.warning(f"Brightspace group categories lookup failed: {cat_resp.status_code} {cat_resp.text}")
                return None
            for category in cat_resp.json():
                groups_resp = await client.get(f"{base}{category['GroupCategoryId']}/groups/", headers=headers)
                if groups_resp.status_code != 200:
                    logger.warning(f"Brightspace groups lookup for category {category.get('Name')} failed: {groups_resp.status_code} {groups_resp.text}")
                    continue
                for group in groups_resp.json():
                    if brightspace_user_id in (group.get("Enrollments") or []):
                        return group.get("Name")
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Brightspace group lookup failed for user {brightspace_user_id}: {e}")
        return None

    async def list_dropbox_folders(self, access_token: str) -> list:
        """Real Brightspace Dropbox Folders (assignments) for the configured
        course. Test-harness use only (see /api/test/brightspace/* in
        main.py) -- NOT wired into the production mission catalog
        (sync_missions_from_lms), because a real DropboxFolder has no field
        for Evoke's curriculum metadata (arc, superpower, skills, PFL
        domain, etc. -- see CONCEPTS.md's Mission glossary entry). That
        metadata stays Evoke's own data either way; this only confirms the
        real assignment list itself is reachable."""
        if not self.org_unit_id:
            raise OAuthLoginError("BRIGHTSPACE_ORG_UNIT_ID not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.whoami_base}/d2l/api/le/{self.le_version}/{self.org_unit_id}/dropbox/folders/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                raise OAuthLoginError(f"Brightspace dropbox folders lookup failed: {resp.status_code} {resp.text}")
            return resp.json()

    async def submit_test_file(self, access_token: str, folder_id: int, text: str) -> dict:
        """Submits a small generated .txt file to a real dropbox folder.
        Test-harness use only, same scope note as list_dropbox_folders.
        Brightspace's submission endpoint requires multipart/mixed (a JSON
        RichText part, then the file part) -- httpx has no high-level
        support for that content type, so the body is assembled by hand per
        https://docs.valence.desire2learn.com/basic/fileupload.html."""
        if not self.org_unit_id:
            raise OAuthLoginError("BRIGHTSPACE_ORG_UNIT_ID not configured")
        boundary = "EvokeTestBoundary123456"
        json_part = '{"Text": "Submitted from the EVOKE Brightspace test page", "Html": null}'
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json\r\n\r\n"
            f"{json_part}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name=""; filename="evoke-test-submission.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode("utf-8") + text.encode("utf-8") + f"\r\n--{boundary}--\r\n".encode("utf-8")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.whoami_base}/d2l/api/le/{self.le_version}/{self.org_unit_id}"
                f"/dropbox/folders/{folder_id}/submissions/mysubmissions/",
                content=body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/mixed; boundary={boundary}",
                },
            )
            if resp.status_code not in (200, 201):
                raise OAuthLoginError(f"Brightspace submission failed: {resp.status_code} {resp.text}")
            return resp.json() if resp.content else {"status": resp.status_code}

    async def submit_dropbox_file(
        self, access_token: str, folder_id: str, file_name: str, file_bytes: bytes
    ) -> dict:
        """Real evidence submission -- generalizes submit_test_file's
        already-correct multipart/mixed encoding to a real filename/content
        instead of fixed demo text. Called with the *submitting student's
        own* access token (see evoke/workers.py's Brightspace Submission
        Worker), not a shared service connection -- .../mysubmissions/
        submits as whichever identity's token is used, so this is what
        makes evidence attribute to the real student in Brightspace's
        gradebook."""
        if not self.org_unit_id:
            raise OAuthLoginError("BRIGHTSPACE_ORG_UNIT_ID not configured")
        boundary = "EvokeSubmissionBoundary123456"
        json_part = '{"Text": "Submitted via EVOKE", "Html": null}'
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json\r\n\r\n"
            f"{json_part}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name=""; filename="{file_name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.whoami_base}/d2l/api/le/{self.le_version}/{self.org_unit_id}"
                f"/dropbox/folders/{folder_id}/submissions/mysubmissions/",
                content=body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/mixed; boundary={boundary}",
                },
            )
            if resp.status_code not in (200, 201):
                raise OAuthLoginError(f"Brightspace submission failed: {resp.status_code} {resp.text}")
            return resp.json() if resp.content else {"status": resp.status_code}

    async def list_classlist(self, access_token: str) -> list:
        """The real course roster. Requires enrollment:orgunit:read, which
        (per docs.valence.desire2learn.com/res/enroll.html) needs an
        instructor/TA-level Brightspace account -- a student's token will
        403 here even though it's fine for dropbox reads. Called with the
        one shared brightspace_service_connection token, not a per-student
        one."""
        if not self.org_unit_id:
            raise OAuthLoginError("BRIGHTSPACE_ORG_UNIT_ID not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.whoami_base}/d2l/api/le/{self.le_version}/{self.org_unit_id}/classlist/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                raise OAuthLoginError(f"Brightspace classlist lookup failed: {resp.status_code} {resp.text}")
            return resp.json()

    async def list_grade_values(self, access_token: str, grade_item_id: str) -> list:
        """Every student's grade value for one Grade Item -- a separate
        resource from the dropbox folder/assignment itself (a DropboxFolder
        carries its linked GradeItemId, captured at link time -- see
        mission_brightspace_mapping.brightspace_grade_item_id). Requires
        grades:gradevalues:read; same service-connection-token expectation
        as list_classlist.

        Confirmed live against a real graded submission (2026-07-20): this is
        a paged Bookmark envelope, `{"Objects": [...], "Next": "<url-or-null>"}`,
        not a bare list -- the caller previously iterated the raw dict itself,
        which walked its string keys ("Objects", "Next") instead of the grade
        rows, throwing AttributeError the first time this ran against real
        data (see admin_sync_grades in main.py, which unwraps User/GradeValue
        per item). Follows `Next` here so a roster large enough to paginate
        doesn't silently lose students past the first page."""
        if not self.org_unit_id:
            raise OAuthLoginError("BRIGHTSPACE_ORG_UNIT_ID not configured")
        objects: list = []
        url = (
            f"{self.whoami_base}/d2l/api/le/{self.le_version}/{self.org_unit_id}"
            f"/grades/{grade_item_id}/values/"
        )
        async with httpx.AsyncClient() as client:
            while url:
                resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
                if resp.status_code != 200:
                    raise OAuthLoginError(f"Brightspace grade values lookup failed: {resp.status_code} {resp.text}")
                page = resp.json()
                objects.extend(page.get("Objects") or [])
                url = page.get("Next") or None
        return objects


_PROVIDERS = {"brightspace": BrightspaceOAuthProvider}


def get_auth_provider() -> Optional[AuthProvider]:
    """AUTH_PROVIDER (.env) picks the implementation. Returns None if unset,
    unrecognized, or missing required config -- callers fall back to
    dev-login in that case, the same fallback shape get_brightspace_lti_provider
    already uses for LTI when it isn't configured."""
    provider_name = os.getenv("AUTH_PROVIDER", "").strip().lower()
    cls = _PROVIDERS.get(provider_name)
    if not cls:
        return None
    provider = cls()
    if not provider.is_configured():
        logger.warning(f"AUTH_PROVIDER={provider_name} set but missing required config; falling back to dev-login")
        return None
    return provider

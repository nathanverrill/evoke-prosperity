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
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise OAuthLoginError("Brightspace token response had no access_token")

            whoami_resp = await client.get(
                f"{self.whoami_base}/d2l/api/lp/{self.whoami_version}/users/whoami",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if whoami_resp.status_code != 200:
                raise OAuthLoginError(
                    f"Brightspace whoami failed: {whoami_resp.status_code} {whoami_resp.text}"
                )
            who = whoami_resp.json()

        # whoami's Identifier is the same underlying numeric Brightspace user
        # ID as LTI's `sub` claim, just returned as a string -- consistent
        # with evoke_identities.brightspace_user_id (INTEGER).
        subject = who.get("Identifier")
        if not subject:
            raise OAuthLoginError("Brightspace whoami response had no Identifier")

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
        }


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

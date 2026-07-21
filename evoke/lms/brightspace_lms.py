"""
BrightspaceLMS - Production adapter for D2L Brightspace API

Handles all communication with real Brightspace instances:
- OAuth 2.0 service account authentication
- Assignment submission (dropbox) sync
- Badge issuance (Award Service)
- Grade updates
- Error handling and logging

Based on Brightspace API v1.96 (LP) and v1.62 (BAS)
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
import asyncpg
import jwt as pyjwt
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

# kid for the one RSA key EVOKE signs client_credentials JWT assertions with.
# Fixed rather than derived, since the JWKS route and the signer must agree on
# it and there's only ever one active key.
SERVICE_JWT_KID = "evoke-service-1"


def _load_service_private_key():
    """Loads the RSA private key used to sign Brightspace client_credentials
    JWT assertions, from BRIGHTSPACE_SERVICE_PRIVATE_KEY_B64 (base64 PEM, an
    env var rather than a file so it's never baked into the Docker image --
    see the Dockerfile's COPY . ./evoke/ and the .dockerignore fix alongside
    this). Returns None if unconfigured, same "not configured" convention
    get_brightspace_lms() already uses for its other required env vars.
    """
    b64 = os.getenv("BRIGHTSPACE_SERVICE_PRIVATE_KEY_B64")
    if not b64:
        return None
    pem_bytes = base64.b64decode(b64)
    return serialization.load_pem_private_key(pem_bytes, password=None)


def get_service_jwks() -> Dict[str, Any]:
    """Public JWKS for the key above -- served at /.well-known/jwks.json so
    Brightspace's Trusted-application client_credentials flow can verify the
    JWT assertion get_service_account_token() signs. Empty keyset if the
    private key isn't configured, rather than erroring: the route should
    still respond (just with nothing to verify against) before setup.
    """
    private_key = _load_service_private_key()
    if private_key is None:
        return {"keys": []}
    public_key = private_key.public_key()
    jwk = json.loads(pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(public_key))
    jwk["kid"] = SERVICE_JWT_KID
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


class BrightspaceLMS:
    """Production adapter for D2L Brightspace LMS integration"""

    def __init__(
        self,
        tenant_url: str,
        app_key: str,
        app_secret: str,
        org_unit_id: str,
        db_pool: asyncpg.Pool = None,
    ):
        """
        Initialize Brightspace adapter with tenant credentials.

        Args:
            tenant_url: Brightspace tenant URL (e.g., https://school.brightspace.com)
            app_key: OAuth 2.0 application key (from Brightspace admin)
            app_secret: OAuth 2.0 application secret
            org_unit_id: Organization unit ID for the course
            db_pool: PostgreSQL connection pool for querying evoke_identities
        """
        self.tenant_url = tenant_url.rstrip("/")
        self.app_key = app_key
        self.app_secret = app_secret
        self.org_unit_id = org_unit_id
        self.db_pool = db_pool

        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client connection"""
        await self.client.aclose()

    async def get_service_account_token(self) -> str:
        """
        OAuth 2.0 client credentials flow for server-to-server auth, using a
        signed JWT client assertion (RFC 7523) rather than a plain client
        secret. Confirmed live against the real tenant: posting
        client_id/client_secret to this endpoint returns
        {"error":"invalid_request","error_description":"Missing
        \"client_assertion\" parameter"} -- the Trusted application Brightspace
        registers for server-to-server auth requires this, it isn't optional.
        (docs.valence.desire2learn.com/basic/oauth2.html; the app_secret this
        class was constructed with is unused for this grant -- trust is
        established by Brightspace fetching our public key from
        /.well-known/jwks.json, not a shared secret.)

        This retrieves a service account token to make API calls on behalf
        of the EVOKE application (not a specific user).

        Returns:
            Access token for API calls

        Raises:
            HTTPException: If OAuth request fails
        """
        if self.access_token and datetime.now() < self.token_expires_at:
            return self.access_token

        private_key = _load_service_private_key()
        if private_key is None:
            raise RuntimeError(
                "BRIGHTSPACE_SERVICE_PRIVATE_KEY_B64 not configured -- "
                "required to sign the client_credentials JWT assertion"
            )

        # Central Brightspace Auth Service token endpoint, NOT tenant-scoped
        # -- the previous f"{self.tenant_url}/oauth2/token" doesn't exist on
        # any tenant and 302-redirected to a 404 error page. Same endpoint
        # already correctly used by the OAuth login flow's
        # BRIGHTSPACE_OAUTH_TOKEN_URL.
        token_url = "https://auth.brightspace.com/core/connect/token"

        logger.debug(f"Requesting service account token from {token_url}")

        now = int(datetime.now().timestamp())
        assertion = pyjwt.encode(
            {
                "iss": self.app_key,
                "sub": self.app_key,
                "aud": token_url,
                "iat": now,
                "exp": now + 300,
                "jti": str(uuid.uuid4()),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": SERVICE_JWT_KID},
        )

        payload = {
            "client_id": self.app_key,
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": "awards:_:_ courses:_:_",
        }

        try:
            response = await self.client.post(token_url, data=payload)
            response.raise_for_status()

            data = response.json()
            self.access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            logger.info("Service account token obtained successfully")
            return self.access_token

        except httpx.HTTPError as e:
            logger.error(f"Failed to get service account token: {e}")
            raise

    async def get_brightspace_user_id(self, evoke_user_id: str) -> Optional[int]:
        """
        Look up Brightspace user ID from evoke_identities table.

        Args:
            evoke_user_id: EVOKE user UUID

        Returns:
            Brightspace user ID (integer) or None if not linked
        """
        if not self.db_pool:
            logger.warning("Database pool not configured")
            return None

        try:
            row = await self.db_pool.fetchrow(
                "SELECT brightspace_user_id FROM evoke_identities WHERE user_id = $1::uuid",
                evoke_user_id,
            )
            if row:
                return row["brightspace_user_id"]
            logger.warning(f"No Brightspace ID linked for EVOKE user {evoke_user_id}")
            return None
        except asyncpg.PostgresError as e:
            logger.error(f"Database error looking up Brightspace user: {e}")
            return None

    async def submit_assignment(
        self,
        evoke_user_id: str,
        mission_id: str,
        file_name: str,
        file_content: bytes,
        submission_id: str = None,
        brightspace_user_id: Optional[int] = None,
        brightspace_assignment_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Submit evidence/file to Brightspace dropbox (assignment).

        POST /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions

        Args:
            evoke_user_id: EVOKE user making submission
            mission_id: Mission UUID (maps to assignment_id)
            file_name: Name of uploaded file
            file_content: File bytes
            submission_id: EVOKE submission ID for tracking
            brightspace_user_id: Pre-resolved Brightspace user ID -- skips
                get_brightspace_user_id's own (asyncpg) lookup when the
                caller already has it. The BRIGHTSPACE SUBMISSION WORKER
                (evoke/workers.py) runs off a sync psycopg2 pool, not
                asyncpg, so it resolves this itself and passes it in rather
                than this class needing two different DB clients.
            brightspace_assignment_id: Same idea for _get_assignment_id's
                lookup.

        Returns:
            Brightspace submission ID or None if failed
        """
        bs_user_id = brightspace_user_id or await self.get_brightspace_user_id(evoke_user_id)
        if not bs_user_id:
            logger.warning(f"Cannot submit: no Brightspace ID for user {evoke_user_id}")
            return None

        assignment_id = brightspace_assignment_id or await self._get_assignment_id(mission_id)
        if not assignment_id:
            logger.warning(f"Cannot submit: no assignment ID for mission {mission_id}")
            return None

        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/lp/1.96/dropbox/{assignment_id}/submissions"
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": (file_name, file_content)}
        data = {"user_id": str(bs_user_id)}

        try:
            logger.debug(f"Submitting to Brightspace: {assignment_id}")
            response = await self.client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()

            result = response.json()
            bs_submission_id = result.get("SubmissionId")

            # Update submissions table with Brightspace ID
            if self.db_pool and submission_id:
                await self.db_pool.execute(
                    "UPDATE submissions SET brightspace_submission_id = $1 WHERE id = $2::uuid",
                    bs_submission_id,
                    submission_id,
                )

            logger.info(
                f"Submission successful: EVOKE {submission_id} → Brightspace {bs_submission_id}"
            )
            return bs_submission_id

        except httpx.HTTPError as e:
            logger.error(f"Failed to submit to Brightspace: {e}")
            return None

    async def push_badge_award(
        self,
        evoke_user_id: str,
        badge_id: str,
        campaign_id: str,
        criteria: str = "",
        evidence: str = "",
    ) -> bool:
        """
        Issue a badge/award in Brightspace Award Service (BAS).

        POST /d2l/api/bas/1.62/orgunits/{orgUnitId}/issued/

        Args:
            evoke_user_id: EVOKE user earning badge
            badge_id: Badge UUID
            campaign_id: Campaign UUID
            criteria: Achievement criteria text
            evidence: Evidence/submission ID

        Returns:
            True if successful, False otherwise
        """
        bs_user_id = await self.get_brightspace_user_id(evoke_user_id)
        if not bs_user_id:
            logger.warning(f"Cannot award: no Brightspace ID for user {evoke_user_id}")
            return False

        award_id = await self._get_brightspace_award_id(badge_id, campaign_id)
        if not award_id:
            logger.warning(f"Cannot award: no Brightspace award ID for badge {badge_id}")
            return False

        # Check if already awarded (idempotency)
        already_awarded = await self._check_award_exists(bs_user_id, award_id)
        if already_awarded:
            logger.info(f"Award {award_id} already issued to user {bs_user_id}")
            return True

        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/bas/1.62/orgunits/{self.org_unit_id}/issued"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "AwardId": award_id,
            "IssuedToUserId": bs_user_id,
            "Criteria": criteria,
            "Evidence": evidence,
        }

        try:
            logger.debug(f"Issuing award {award_id} to user {bs_user_id}")
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            logger.info(f"Award issued: badge {badge_id} → user {evoke_user_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to issue award: {e}")
            return False

    async def push_mission_status(
        self,
        evoke_user_id: str,
        submission_id: str,
        grade: int,
        feedback: str = "",
    ) -> bool:
        """
        Update submission grade in Brightspace.

        PUT /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions/{submissionId}/grade

        Args:
            evoke_user_id: User who submitted
            submission_id: EVOKE submission UUID
            grade: Grade 0-100
            feedback: Teacher feedback

        Returns:
            True if successful, False otherwise
        """
        if not self.db_pool:
            logger.warning("Cannot grade: database pool not configured")
            return False

        # Get submission details
        sub_row = await self.db_pool.fetchrow(
            """
            SELECT brightspace_submission_id, mission_id
            FROM submissions WHERE id = $1::uuid
            """,
            submission_id,
        )

        if not sub_row or not sub_row["brightspace_submission_id"]:
            logger.warning(f"No Brightspace submission ID for {submission_id}")
            return False

        bs_sub_id = sub_row["brightspace_submission_id"]
        mission_id = sub_row["mission_id"]

        assignment_id = await self._get_assignment_id(mission_id)
        if not assignment_id:
            logger.warning(f"Cannot grade: no assignment ID for mission {mission_id}")
            return False

        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/lp/1.96/dropbox/{assignment_id}/submissions/{bs_sub_id}/grade"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"Grade": grade, "Feedback": feedback}

        try:
            logger.debug(f"Grading submission {bs_sub_id} with grade {grade}")
            response = await self.client.put(url, headers=headers, json=payload)
            response.raise_for_status()

            # Update submissions table
            await self.db_pool.execute(
                "UPDATE submissions SET grade = $1, graded_at = NOW() WHERE id = $2::uuid",
                grade,
                submission_id,
            )

            logger.info(f"Grade updated: submission {submission_id} → {grade}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to grade submission: {e}")
            return False

    # ========== Private Helper Methods ==========

    async def _get_assignment_id(self, mission_id: str) -> Optional[str]:
        """Look up Brightspace assignment ID from mission_brightspace_mapping table"""
        if not self.db_pool:
            return None

        try:
            row = await self.db_pool.fetchrow(
                "SELECT brightspace_assignment_id FROM mission_brightspace_mapping WHERE mission_id = $1::uuid LIMIT 1",
                mission_id,
            )
            return row["brightspace_assignment_id"] if row else None
        except asyncpg.PostgresError as e:
            logger.error(f"Error looking up assignment ID: {e}")
            return None

    async def _get_brightspace_award_id(
        self, badge_id: str, campaign_id: str
    ) -> Optional[int]:
        """Look up Brightspace award ID from badge_brightspace_mapping table"""
        if not self.db_pool:
            return None

        try:
            row = await self.db_pool.fetchrow(
                """
                SELECT brightspace_award_id
                FROM badge_brightspace_mapping
                WHERE badge_id = $1::uuid AND campaign_id = $2::uuid
                """,
                badge_id,
                campaign_id,
            )
            return row["brightspace_award_id"] if row else None
        except asyncpg.PostgresError as e:
            logger.error(f"Error looking up award ID: {e}")
            return None

    async def _check_award_exists(self, bs_user_id: int, award_id: int) -> bool:
        """Check if award was already issued to user (idempotency check)"""
        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/bas/1.62/issued/users/{bs_user_id}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            awards = data.get("Awards", [])

            # Check if this award is in the list
            for award in awards:
                if award.get("AwardId") == award_id:
                    return True
            return False

        except httpx.HTTPError as e:
            logger.warning(f"Error checking existing awards: {e}")
            return False

    async def get_user_info(self, bs_user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information from Brightspace.

        GET /d2l/api/lp/1.96/users/{userId}

        Useful for validation and debugging.
        """
        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/lp/1.96/users/{bs_user_id}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting user info: {e}")
            return None

    async def get_submissions_for_assignment(
        self, assignment_id: str
    ) -> Optional[list]:
        """
        Get all submissions for an assignment.

        GET /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions

        Useful for polling/syncing grades from Brightspace.
        """
        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/lp/1.96/dropbox/{assignment_id}/submissions"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("Submissions", [])
        except httpx.HTTPError as e:
            logger.error(f"Error getting submissions: {e}")
            return None

    async def get_classlist(self) -> Optional[list]:
        """
        Get the course roster.

        GET /d2l/api/le/1.x/{orgUnitId}/classlist/

        Backs the admin roster-import flow -- pulling the real class list
        so an admin can bring students into EVOKE and assign them to teams
        without waiting for each one's first LTI launch.
        """
        token = await self.get_service_account_token()

        url = f"{self.tenant_url}/d2l/api/le/1.x/{self.org_unit_id}/classlist/"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting classlist: {e}")
            return None


# ========== Configuration from Environment ==========

def get_brightspace_lms(db_pool: asyncpg.Pool = None) -> Optional[BrightspaceLMS]:
    """
    Factory function to create BrightspaceLMS from environment variables.

    Environment variables:
    - BRIGHTSPACE_TENANT_URL: https://school.brightspace.com
    - BRIGHTSPACE_APP_KEY: OAuth app key
    - BRIGHTSPACE_APP_SECRET: OAuth app secret
    - BRIGHTSPACE_ORG_UNIT_ID: Course/org unit ID
    - BRIGHTSPACE_SIMULATOR_MODE: true for simulator, false for real (default: false)

    Returns:
        BrightspaceLMS instance or None if not configured
    """
    simulator_mode = os.getenv("BRIGHTSPACE_SIMULATOR_MODE", "false").lower() == "true"

    if simulator_mode:
        logger.info("Brightspace simulator mode enabled")
        return None  # Caller will use simulator instead

    tenant_url = os.getenv("BRIGHTSPACE_TENANT_URL")
    app_key = os.getenv("BRIGHTSPACE_APP_KEY")
    app_secret = os.getenv("BRIGHTSPACE_APP_SECRET")
    org_unit_id = os.getenv("BRIGHTSPACE_ORG_UNIT_ID")

    if not all([tenant_url, app_key, app_secret, org_unit_id]):
        logger.warning("Brightspace credentials incomplete, simulator mode assumed")
        return None

    logger.info(f"Initializing Brightspace adapter for {tenant_url}")
    return BrightspaceLMS(
        tenant_url=tenant_url,
        app_key=app_key,
        app_secret=app_secret,
        org_unit_id=org_unit_id,
        db_pool=db_pool,
    )

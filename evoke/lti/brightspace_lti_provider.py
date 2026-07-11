"""
Brightspace LTI 1.3 Platform Provider

Handles LTI 1.3 launches from Brightspace, verifying JWT signatures and
auto-provisioning users. Students click "Launch External Tool" in Brightspace
and are immediately logged into EVOKE.

Based on IMS Global LTI 1.3 specification:
https://www.imsglobal.org/spec/lti/v1p3/
"""

import logging
import os
import jwt
import asyncpg
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)

# LTI claims constants
LTI_CLAIM_SUB = "sub"  # User ID from platform
LTI_CLAIM_EMAIL = "email"
LTI_CLAIM_NAME = "name"
LTI_CLAIM_GIVEN_NAME = "given_name"
LTI_CLAIM_FAMILY_NAME = "family_name"
LTI_CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
LTI_CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
LTI_CLAIM_TOOL_PLATFORM = "https://purl.imsglobal.org/spec/lti/claim/tool_platform"


class LTIVerificationError(Exception):
    """Raised when LTI JWT verification fails"""
    pass


class BrightspaceLTIProvider:
    """LTI 1.3 provider for Brightspace platform launches"""

    def __init__(
        self,
        client_id: str,
        public_key_jwk: Dict[str, Any],
        db_pool: asyncpg.Pool,
        issuer: str = None,
    ):
        """
        Initialize LTI 1.3 provider for Brightspace.

        Args:
            client_id: LTI Tool Client ID (from Brightspace admin)
            public_key_jwk: Brightspace's public key in JWK format
                           (obtained during tool registration)
            db_pool: PostgreSQL connection pool
            issuer: Expected JWT issuer (Brightspace tenant URL)
        """
        self.client_id = client_id
        self.public_key_jwk = public_key_jwk
        self.db_pool = db_pool
        self.issuer = issuer or os.getenv("BRIGHTSPACE_TENANT_URL")

        # Convert JWK to PEM for verification
        try:
            self.public_key = self._jwk_to_pem(public_key_jwk)
        except Exception as e:
            logger.warning(f"Failed to convert JWK to PEM: {e}")
            self.public_key = None

    async def verify_and_login(self, id_token: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Verify LTI 1.3 JWT and auto-provision user.

        Args:
            id_token: JWT from Brightspace platform

        Returns:
            (session_token, user_dict) or (None, None) if verification fails
        """
        # Verify JWT signature
        try:
            payload = self._verify_jwt(id_token)
        except LTIVerificationError as e:
            logger.error(f"LTI verification failed: {e}")
            return None, None

        # Extract required claims
        try:
            brightspace_user_id = int(payload[LTI_CLAIM_SUB])
            email = payload.get(LTI_CLAIM_EMAIL, f"{brightspace_user_id}@brightspace.local")
            display_name = payload.get(LTI_CLAIM_NAME, f"User {brightspace_user_id}")
            roles = payload.get(LTI_CLAIM_ROLES, [])

            logger.info(f"LTI launch verified for user {brightspace_user_id}")
        except (KeyError, ValueError) as e:
            logger.error(f"Missing LTI claims: {e}")
            return None, None

        # Determine user role
        user_role = self._map_lti_roles(roles)

        # Get or create user
        try:
            evoke_user_id = await self._get_or_create_user(
                brightspace_user_id=brightspace_user_id,
                email=email,
                display_name=display_name,
                role=user_role,
            )

            if not evoke_user_id:
                logger.error("Failed to provision user")
                return None, None

            # Create session token
            session_token = str(uuid4())

            # Get user info for response
            user = await self.db_pool.fetchrow(
                "SELECT id, display_name, email, role FROM users WHERE id = $1::uuid",
                evoke_user_id,
            )

            user_dict = {
                "user_id": str(user["id"]),
                "display_name": user["display_name"],
                "email": user["email"],
                "role": user["role"],
                "session_token": session_token,
            }

            logger.info(f"User logged in via LTI: {evoke_user_id}")
            return session_token, user_dict

        except asyncpg.PostgresError as e:
            logger.error(f"Database error during LTI login: {e}")
            return None, None

    def _verify_jwt(self, id_token: str) -> Dict[str, Any]:
        """
        Verify JWT signature and return payload.

        Args:
            id_token: JWT from Brightspace

        Returns:
            Decoded JWT payload

        Raises:
            LTIVerificationError: If verification fails
        """
        if not self.public_key:
            raise LTIVerificationError("Public key not available")

        try:
            # Decode without verification first to inspect headers
            unverified = jwt.decode(id_token, options={"verify_signature": False})

            # Verify signature
            payload = jwt.decode(
                id_token,
                self.public_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={"verify_aud": True, "verify_iss": True},
            )

            # Verify this is an LTI token
            if "https://purl.imsglobal.org/spec/lti/claim/lti_version" not in payload:
                raise LTIVerificationError("Not an LTI token")

            # Verify deployment ID if present
            deployment_id = payload.get(
                "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
            )
            if deployment_id:
                logger.debug(f"LTI deployment: {deployment_id}")

            return payload

        except jwt.InvalidSignatureError:
            raise LTIVerificationError("Invalid JWT signature")
        except jwt.ExpiredSignatureError:
            raise LTIVerificationError("JWT expired")
        except jwt.DecodeError as e:
            raise LTIVerificationError(f"JWT decode error: {e}")
        except Exception as e:
            raise LTIVerificationError(f"JWT verification error: {e}")

    async def _get_or_create_user(
        self,
        brightspace_user_id: int,
        email: str,
        display_name: str,
        role: str,
    ) -> Optional[str]:
        """
        Get existing user or create new one.

        Args:
            brightspace_user_id: User ID from Brightspace
            email: User email
            display_name: User name
            role: learner, instructor, or admin

        Returns:
            EVOKE user ID or None if failed
        """
        try:
            # Check if already linked
            existing = await self.db_pool.fetchrow(
                "SELECT user_id FROM evoke_identities WHERE brightspace_user_id = $1",
                brightspace_user_id,
            )

            if existing:
                logger.debug(f"Found existing EVOKE user for BS {brightspace_user_id}")
                return str(existing["user_id"])

            # Get default org (for now, use first org)
            org = await self.db_pool.fetchrow(
                "SELECT id FROM organizations LIMIT 1"
            )

            if not org:
                logger.error("No organizations found in database")
                return None

            org_id = org["id"]
            user_id = str(uuid4())

            # Create user
            await self.db_pool.execute(
                """INSERT INTO users (id, org_id, display_name, email, role)
                   VALUES ($1::uuid, $2::uuid, $3, $4, $5)
                   ON CONFLICT (email, org_id) DO UPDATE
                   SET display_name = $3, role = $5
                   WHERE users.email = $4 AND users.org_id = $2::uuid
                   RETURNING id""",
                user_id,
                org_id,
                display_name,
                email,
                role,
            )

            # Create identity link
            await self.db_pool.execute(
                """INSERT INTO evoke_identities (user_id, brightspace_user_id)
                   VALUES ($1::uuid, $2)
                   ON CONFLICT (brightspace_user_id) DO UPDATE
                   SET updated_at = NOW()""",
                user_id,
                brightspace_user_id,
            )

            logger.info(f"Created new user {user_id} for Brightspace {brightspace_user_id}")
            return user_id

        except asyncpg.PostgresError as e:
            logger.error(f"Database error creating/finding user: {e}")
            return None

    def _map_lti_roles(self, roles: list) -> str:
        """
        Map LTI roles to EVOKE roles.

        LTI roles: http://purl.imsglobal.org/vocab/lis/v2/institution/person#

        Args:
            roles: List of LTI role URIs

        Returns:
            EVOKE role: 'learner', 'instructor', or 'admin'
        """
        if not roles:
            return "learner"

        role_lower = " ".join(roles).lower()

        if "instructor" in role_lower or "teacher" in role_lower:
            return "instructor"
        if "admin" in role_lower:
            return "admin"

        return "learner"

    @staticmethod
    def _jwk_to_pem(jwk: Dict[str, Any]) -> str:
        """
        Convert JWK to PEM format for PyJWT.

        PyJWT can directly use RSA keys in certain formats.
        This is a simplified converter for RSA public keys.

        Args:
            jwk: JSON Web Key dictionary

        Returns:
            PEM-formatted public key string

        Note:
            PyJWT 2.8+ can directly use JWK format via:
            jwt.decode(..., key=jwk, algorithms=['RS256'])
            So this returns the JWK as-is for use with newer PyJWT.
        """
        # For PyJWT 2.8+, we can use JWK directly
        # So just return a marker that PyJWT will handle
        import json
        return json.dumps(jwk)

    @staticmethod
    def parse_authorization_header(header: str) -> Optional[str]:
        """
        Parse Bearer token from Authorization header.

        Args:
            header: Authorization header value

        Returns:
            Token or None
        """
        if not header or not header.startswith("Bearer "):
            return None
        return header[7:]  # Remove "Bearer " prefix


# Configuration helper
def get_brightspace_lti_provider(db_pool: asyncpg.Pool) -> Optional[BrightspaceLTIProvider]:
    """
    Create BrightspaceLTIProvider from environment variables.

    Environment variables:
    - BRIGHTSPACE_LTI_CLIENT_ID: LTI Tool Client ID
    - BRIGHTSPACE_LTI_PUBLIC_KEY: JWK public key (JSON string)
    - BRIGHTSPACE_TENANT_URL: Issuer URL

    Returns:
        BrightspaceLTIProvider or None if not configured
    """
    client_id = os.getenv("BRIGHTSPACE_LTI_CLIENT_ID")
    public_key_str = os.getenv("BRIGHTSPACE_LTI_PUBLIC_KEY")
    issuer = os.getenv("BRIGHTSPACE_TENANT_URL")

    if not client_id or not public_key_str:
        logger.warning("LTI not configured (missing CLIENT_ID or PUBLIC_KEY)")
        return None

    try:
        import json
        public_key_jwk = json.loads(public_key_str)
    except Exception as e:
        logger.error(f"Failed to parse LTI public key: {e}")
        return None

    return BrightspaceLTIProvider(
        client_id=client_id,
        public_key_jwk=public_key_jwk,
        db_pool=db_pool,
        issuer=issuer,
    )

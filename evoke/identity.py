"""Shared EVOKE Player provisioning -- an EVOKE Player is 1:1 with an LMS
student (evoke_identities.brightspace_user_id is unique, same as user_id).
Two things trigger provisioning: a student's first real LTI launch
(evoke/lti/brightspace_lti_provider.py), or an admin importing them from the
roster ahead of time (evoke/main.py's /api/admin/roster/{id}/import) --
same underlying row, same logic, so it lives here once instead of twice.
"""
import logging
from typing import Optional
from uuid import uuid4

import asyncpg

logger = logging.getLogger(__name__)


async def get_or_create_evoke_player(
    db_pool: asyncpg.Pool,
    brightspace_user_id: int,
    email: str,
    display_name: str,
    role: str,
) -> Optional[str]:
    """Returns the EVOKE user_id for this LMS student, creating the
    users + evoke_identities rows on first call. Idempotent -- a second
    call for the same brightspace_user_id just returns the existing link."""
    try:
        existing = await db_pool.fetchrow(
            "SELECT user_id FROM evoke_identities WHERE brightspace_user_id = $1",
            brightspace_user_id,
        )
        if existing:
            return str(existing["user_id"])

        org = await db_pool.fetchrow("SELECT id FROM organizations LIMIT 1")
        if not org:
            logger.error("No organizations found in database")
            return None
        org_id = org["id"]
        user_id = str(uuid4())

        await db_pool.execute(
            """INSERT INTO users (id, org_id, display_name, email, role)
               VALUES ($1::uuid, $2::uuid, $3, $4, $5)
               ON CONFLICT (email, org_id) DO UPDATE
               SET display_name = $3, role = $5
               WHERE users.email = $4 AND users.org_id = $2::uuid
               RETURNING id""",
            user_id, org_id, display_name, email, role,
        )
        await db_pool.execute(
            """INSERT INTO evoke_identities (user_id, brightspace_user_id)
               VALUES ($1::uuid, $2)
               ON CONFLICT (brightspace_user_id) DO UPDATE
               SET updated_at = NOW()""",
            user_id, brightspace_user_id,
        )

        logger.info(f"Created new EVOKE Player {user_id} for Brightspace student {brightspace_user_id}")
        return user_id

    except asyncpg.PostgresError as e:
        logger.error(f"Database error creating/finding EVOKE Player: {e}")
        return None

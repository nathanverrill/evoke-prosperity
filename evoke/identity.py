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


async def sync_team_membership(
    db_pool: asyncpg.Pool,
    org_id: str,
    user_id: str,
    team_name: Optional[str],
) -> Optional[str]:
    """Resolves (creating on first sight) the Evoke team matching a
    Brightspace Group's name, and moves this user onto it -- Brightspace
    Groups are the source of truth for team assignment (see
    evoke/oauth_providers.py's _resolve_team_name), not a separate
    Evoke-side admin step. Same delete-then-insert 'always moves, never a
    second membership' pattern as /api/admin/teams/{id}/members. A no-op
    (returns None) if team_name is falsy -- e.g. team sync isn't configured,
    or this Brightspace user isn't in any group yet."""
    if not team_name:
        return None
    try:
        team_row = await db_pool.fetchrow(
            """INSERT INTO teams (org_id, name) VALUES ($1::uuid, $2)
               ON CONFLICT (org_id, name) DO UPDATE SET name = teams.name
               RETURNING id""",
            org_id, team_name,
        )
        team_id = str(team_row["id"])

        current = await db_pool.fetchrow(
            "SELECT team_id FROM team_members WHERE user_id = $1::uuid", user_id,
        )
        if current and str(current["team_id"]) == team_id:
            return team_id

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM team_members WHERE user_id = $1::uuid", user_id)
                await conn.execute(
                    "INSERT INTO team_members (team_id, user_id) VALUES ($1::uuid, $2::uuid)",
                    team_id, user_id,
                )
        return team_id

    except asyncpg.PostgresError as e:
        logger.error(f"Team sync failed for user {user_id} -> '{team_name}': {e}")
        return None

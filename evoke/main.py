import os
import json
import datetime
import asyncio
import random
import re
import uuid
import hashlib
import textwrap
from typing import Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends, Response, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import httpx
import asyncpg
import logging
from io import BytesIO
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from PIL import Image, ImageOps

from evoke.clients import s3_client, os_client, get_producer, topic_for_event
from evoke.workers import evoke_workers_loop
from evoke.lti import BrightspaceLTIProvider
from evoke import skills_framework, progression, world_state, gear as gear_catalog
from evoke.live import live_hub
from evoke.identity import get_or_create_evoke_player, sync_team_membership
from evoke.oauth_providers import get_auth_provider, OAuthLoginError
from evoke.auth_session import (
    issue_session, clear_session, get_current_user, get_current_user_optional,
    get_current_admin, require_self, verify_admin_password,
)

logger = logging.getLogger(__name__)

# ========== Configuration ==========
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://evoke:devsecret123@localhost:5432/evoke")
# billbot_chat() below no longer talks to OpenWebUI directly -- it points
# at the LiteLLM gateway (GUARDRAILS_PLAN.md Phase 0/1), which forwards to
# OpenWebUI as its one real backend and applies the content-filter/Presidio
# guardrails in evoke-infra/litellm/config.yaml on the way through.
# LITELLM_MASTER_KEY is the gateway's own auth, not a user session JWT
# (which expires) -- it's a static secret shared with the gateway container.
AI_GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "http://litellm:4000")
AI_GATEWAY_KEY = os.getenv("AI_GATEWAY_KEY", "sk-devsecret123")
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
# The internal container hostname (MINECRAFT_HOST) is for the app/bridge's
# own RCON traffic -- not reachable from a learner's actual Minecraft
# client. This is the address a real player types into their client,
# separately configurable since it has to be a real public host once this
# runs on a cohort instance (see HOSTING_COST_MODEL.md's domain scheme:
# {cohort-slug}.mc.<root-domain>). Defaults assume same-machine local dev.
MINECRAFT_PUBLIC_HOST = os.getenv("MINECRAFT_PUBLIC_HOST", "prosperity.apexmc.co")
MINECRAFT_PUBLIC_PORT_JAVA = os.getenv("MINECRAFT_PUBLIC_PORT_JAVA", "25565")
MINECRAFT_PUBLIC_PORT_BEDROCK = os.getenv("MINECRAFT_PUBLIC_PORT_BEDROCK", "19132")
# Java requires an exact version match to even connect (a mismatched client
# gets "Outdated client/server" and can't join at all) -- Bedrock via Geyser
# is far more forgiving about client version, so this is a Java-specific
# instruction. Kept server-side, not hardcoded in companion.html, so a
# future server upgrade is a one-line env change, not a frontend redeploy.
MINECRAFT_JAVA_VERSION = os.getenv("MINECRAFT_JAVA_VERSION", "1.21.10")

# ========== Database Pool ==========
db_pool = SimpleConnectionPool(1, 20, DATABASE_URL)
async_db_pool: Optional[asyncpg.Pool] = None
brightspace_lti: Optional[BrightspaceLTIProvider] = None

def get_db_connection():
    return db_pool.getconn()

def return_db_connection(conn):
    db_pool.putconn(conn)

# ========== FastAPI Setup ==========
app = FastAPI(title="EVOKE Prosperity API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mission Catalog Sync -- sync_missions_from_lms() used to live here,
# auto-upserting from brightspace-sim on every startup. Removed: real
# missions now come from the admin Mission Sync flow (POST /api/admin/missions
# + link-brightspace, see BRIGHTSPACE.md), not an LMS the app treats as
# nonexistent. The 12 missions that flow already populated keep their real
# curriculum content -- nothing lost by no longer re-pulling from the sim.

# ========== Startup/Shutdown ==========
@app.on_event("startup")
async def startup():
    """Initialize async database pool and LTI provider"""
    global async_db_pool, brightspace_lti

    try:
        # Create async database pool for LTI and everything else
        async_db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
        logger.info("Async database pool created")

        # Initialize LTI 1.3 provider if configured
        try:
            from evoke.lti import get_brightspace_lti_provider
            brightspace_lti = get_brightspace_lti_provider(async_db_pool)
            if brightspace_lti:
                logger.info("Brightspace LTI 1.3 provider initialized")
            else:
                logger.info("LTI not configured (optional feature)")
        except ImportError:
            logger.warning("LTI provider not available")

        # Idempotent DDL for tables newer than a deployment's Postgres
        # volume -- init-db.sql only runs on a *fresh* volume, so anything
        # added later needs a create-if-missing here to work on existing
        # installs. Matches the bridge's own world_meta bootstrap.
        db_execute("""CREATE TABLE IF NOT EXISTS minigame_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            game_key VARCHAR(64) NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        db_execute("CREATE INDEX IF NOT EXISTS idx_minigame_scores_user_game ON minigame_scores(user_id, game_key)")
        db_execute("CREATE INDEX IF NOT EXISTS idx_minigame_scores_game_score ON minigame_scores(game_key, score DESC)")
        # Halyard Mob Arena progress -- bridge-owned table (matches world_meta's
        # split: the bridge is the only thing that ever writes it, from RCON
        # reads of the arenaBestWave scoreboard), created here too so the web
        # side can read it even before the bridge's first heartbeat tick.
        db_execute("CREATE TABLE IF NOT EXISTS mc_arena_best (user_id UUID PRIMARY KEY, best_wave INT NOT NULL DEFAULT 0)")
        # Same split for the Mob Gauntlet (evoke-infra/minecraft/datapacks/mob_gauntlet) --
        # bridge-owned table, mirrors mc_arena_best.
        db_execute("CREATE TABLE IF NOT EXISTS mc_gauntlet_best (user_id UUID PRIMARY KEY, best_wave INT NOT NULL DEFAULT 0)")
        # mission_brightspace_mapping's own UNIQUE(mission_id, campaign_id)
        # (init-db.sql) only stops one mission from having two mapping rows
        # -- nothing stopped two *different* missions from both claiming the
        # same brightspace_assignment_id. The Brightspace Mission Sync flow
        # (admin_link_brightspace_assignment) requires a true 1:1: one Evoke
        # mission is the container for exactly one Brightspace assignment.
        # init-db.sql only runs on a fresh volume, so this needs the same
        # idempotent create-if-missing treatment as the tables above.
        db_execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mission_brightspace_mapping_assignment
            ON mission_brightspace_mapping (campaign_id, brightspace_assignment_id)
        """)
        # Real Brightspace integration (no simulator): a student's own
        # OAuth tokens, captured at login, used to push their own
        # submissions -- see BRIGHTSPACE.md. init-db.sql has this inline for
        # fresh volumes; same idempotent treatment for an existing one.
        db_execute("ALTER TABLE evoke_identities ADD COLUMN IF NOT EXISTS brightspace_access_token TEXT")
        db_execute("ALTER TABLE evoke_identities ADD COLUMN IF NOT EXISTS brightspace_refresh_token TEXT")
        db_execute("ALTER TABLE evoke_identities ADD COLUMN IF NOT EXISTS brightspace_token_expires_at TIMESTAMP")
        db_execute("ALTER TABLE mission_brightspace_mapping ADD COLUMN IF NOT EXISTS brightspace_grade_item_id VARCHAR(50)")
        db_execute("""
            CREATE TABLE IF NOT EXISTS brightspace_service_connection (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                brightspace_user_id INTEGER,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at TIMESTAMP NOT NULL,
                connected_by_admin_id UUID REFERENCES users(id),
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # evoke/identity.py's get_or_create_evoke_player needs this for its
        # ON CONFLICT (email, org_id) clause -- found live (2026-07-16) that
        # it never actually existed, so LTI auto-provisioning of a genuinely
        # new user always 500'd. init-db.sql has it inline for fresh volumes;
        # this is the same fix for a volume that predates that.
        db_execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_org_unique ON users(email, org_id)")
        # organizations had the exact same missing-uniqueness problem as
        # users(email, org_id) above -- seed.py's org INSERT used
        # ON CONFLICT DO NOTHING with nothing to conflict against, so every
        # re-run of seed.py against an existing volume created a brand-new
        # "Demo School" org (found live, 2026-07-21, alongside the mc_quests
        # duplication below -- same root cause, different table, worse blast
        # radius since users/teams/badges all cascade from org_id). Verified
        # live before writing this: none of the junk orgs ever accumulated
        # real submissions/awards/chat/etc. -- purely orphaned seed-script
        # output -- so a clean delete loses nothing. Keeps whichever "Demo
        # School" row has a real Brightspace-linked user under it (the org
        # an actual deployment is using), or the oldest one if none do (a
        # fresh dev clone where every org is equally a seed.py artifact).
        junk_org_ids = [str(r[0]) for r in db_fetch_all("""
            SELECT id FROM (
                SELECT o.id, ROW_NUMBER() OVER (
                    ORDER BY (EXISTS (
                        SELECT 1 FROM evoke_identities ei JOIN users u ON u.id = ei.user_id
                        WHERE u.org_id = o.id AND ei.brightspace_user_id IS NOT NULL
                    )) DESC, o.created_at, o.id
                ) AS rn
                FROM organizations o
            ) ranked WHERE rn > 1
        """)]
        if junk_org_ids:
            db_execute("DELETE FROM team_members WHERE user_id IN (SELECT id FROM users WHERE org_id = ANY(%s::uuid[]))", (junk_org_ids,))
            db_execute("DELETE FROM auth_identities WHERE user_id IN (SELECT id FROM users WHERE org_id = ANY(%s::uuid[]))", (junk_org_ids,))
            db_execute("DELETE FROM evoke_identities WHERE user_id IN (SELECT id FROM users WHERE org_id = ANY(%s::uuid[]))", (junk_org_ids,))
            db_execute("DELETE FROM teams WHERE org_id = ANY(%s::uuid[])", (junk_org_ids,))
            db_execute("DELETE FROM users WHERE org_id = ANY(%s::uuid[])", (junk_org_ids,))
            db_execute("DELETE FROM organizations WHERE id = ANY(%s::uuid[])", (junk_org_ids,))
        db_execute("CREATE UNIQUE INDEX IF NOT EXISTS organizations_name_unique ON organizations(name)")
        # Team-evidence + individual-reflection model: submissions become the
        # team's shared artifact (team_id is the real completion key now,
        # user_id kept only for submitted-by attribution); mission_reflections
        # is each member's own required reflection, gating their own award/XP
        # -- see main.py's _complete_mission_for_user. Not the same thing as
        # daily_reflections (Field Report/Wisdom Journal), which is unrelated.
        db_execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS team_id UUID REFERENCES teams(id)")
        db_execute("""CREATE TABLE IF NOT EXISTS mission_reflections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            mission_id UUID NOT NULL REFERENCES missions(id),
            team_id UUID NOT NULL REFERENCES teams(id),
            reflection TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, mission_id)
        )""")
        # Submission redesign (Mission Submission Redesign doc): each mission
        # can carry a per-learner Individual Task and a Team Product that every
        # member turns in (Option A -- each uploads their own copy, hash-checked
        # so a divergent file is flagged, never blocked). `kind` distinguishes
        # the two; existing rows are team products. `content_hash` is the sha256
        # of the uploaded file, used to detect who turned in the same file.
        db_execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS kind VARCHAR(32) NOT NULL DEFAULT 'team_product'")
        db_execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS content_hash TEXT")
        # In-app Team Discussion thread (one per team per mission): the
        # collaboration step, captured as evidence a facilitator can review.
        db_execute("""CREATE TABLE IF NOT EXISTS team_discussion (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id UUID NOT NULL REFERENCES teams(id),
            mission_id UUID NOT NULL REFERENCES missions(id),
            user_id UUID NOT NULL REFERENCES users(id),
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Team page (nav): a team-wide message board (not mission-scoped) plus an
        # editable team motto for the team identity from Mission 2.
        db_execute("ALTER TABLE teams ADD COLUMN IF NOT EXISTS motto TEXT")
        db_execute("""CREATE TABLE IF NOT EXISTS team_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id UUID NOT NULL REFERENCES teams(id),
            user_id UUID NOT NULL REFERENCES users(id),
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Identity customization: uploaded avatar (MinIO object key), the
        # procedural Agent Sigil config (small JSON: glyph + hue), and the
        # equipped Field Gear (JSON list of gear keys, validated on write).
        db_execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_object_key TEXT")
        db_execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sigil TEXT")
        db_execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS equipped_gear TEXT")
        db_execute("""CREATE TABLE IF NOT EXISTS mc_quest_triggers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            quest_id UUID NOT NULL REFERENCES mc_quests(id),
            objective VARCHAR(64) NOT NULL,
            threshold INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(quest_id, objective)
        )""")

        # Scoreboard-driven quest triggers (GAME_DESIGN §6.2's implementation
        # note): map real in-world mechanics' scoreboards to quests, keyed by
        # quest title so this works on any volume where seed.py already ran.
        # - rentPaid >= 1: set by halyard_rent_functions/start_rent_timer --
        #   the learner engaged Halyard's rent/budgeting mechanic (mission 5's
        #   quest). Verified against the committed datapack, not guessed.
        # - evoke_walked >= 1: a reserved hook objective for 'Walk the
        #   Mountain' -- the world (a command block / future datapack) sets it
        #   when the learner completes the tour; documented convention, so
        #   world-builders can wire triggers without touching this code.
        for quest_title, objective, threshold in [
            ("Factory Crafting I", "rentPaid", 1),
            ("Walk the Mountain", "evoke_walked", 1),
        ]:
            db_execute(
                """INSERT INTO mc_quest_triggers (quest_id, objective, threshold)
                   SELECT id, %s, %s FROM mc_quests WHERE title = %s
                   ON CONFLICT (quest_id, objective) DO NOTHING""",
                (objective, threshold, quest_title)
            )

        # Basin Archive (playtest 2026-07-21): Billbot's fragmented memory of
        # the Basin, recovered by exploring — the value-add framing for the
        # optional Minecraft layer. Each entry is an mc_quest completed
        # automatically by the bridge (scoreboard/position detection, see
        # bridge.py's world_progress_loop) and rendered on the Field Tablet
        # as a locked/unlocked memory (GET /api/basin-archive/{user_id}).
        # Same optionality rule as every mc_quest: never gates, never grades.
        db_execute("ALTER TABLE mc_quests DROP CONSTRAINT IF EXISTS mc_quests_kind_check")
        db_execute("""ALTER TABLE mc_quests ADD CONSTRAINT mc_quests_kind_check
                      CHECK (kind::text = ANY (ARRAY['mission_quest', 'side_quest', 'basin_archive']::text[]))""")

        # seed.py's quest INSERT already reads "ON CONFLICT DO NOTHING", but
        # mc_quests had no unique constraint for that clause to actually
        # target -- a no-op guard that never fired, so every re-run of
        # seed.py (a normal dev workflow, not a misuse) silently tripled the
        # 16 curriculum quests on this volume (found live, 2026-07-21, while
        # building the Field Tablet's quest log). Basin Archive rows above
        # were already NOT EXISTS-guarded and never duplicated. Self-healing,
        # not a one-off fix: dedupes on every startup (a no-op once actually
        # clean), so any other volume with the same history heals the same
        # way without a manual migration. Keeps the oldest row per
        # (campaign_id, title) -- the one most likely still correctly linked
        # via mission_id from its original seed.py run. Triggers pointing at
        # a row about to be deleted are dropped first, not repointed: the
        # startup loop above/below re-seeds exactly one correct trigger per
        # real quest once the duplicate rows are gone, which is simpler and
        # less error-prone than guessing which duplicate's trigger to keep.
        db_execute("""
            DELETE FROM mc_quest_triggers WHERE quest_id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY campaign_id, title ORDER BY created_at, id
                    ) AS rn
                    FROM mc_quests
                ) ranked WHERE rn > 1
            )
        """)
        db_execute("""
            DELETE FROM mc_quests WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY campaign_id, title ORDER BY created_at, id
                    ) AS rn
                    FROM mc_quests
                ) ranked WHERE rn > 1
            )
        """)
        db_execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mc_quests_campaign_title
            ON mc_quests(campaign_id, title)
        """)

        # Same bug, same fix, one table over: mc_reward_catalog's insert
        # also relied on a toothless ON CONFLICT DO NOTHING, so re-running
        # seed.py multiplied the whole reward catalog too (found live
        # alongside the mc_quests case above). mc_reward_grants -- the only
        # table that references a catalog row -- is empty on every volume
        # this has been checked against, so this is a clean delete, no
        # repointing needed.
        db_execute("""
            DELETE FROM mc_reward_catalog WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY campaign_id, tier, reward ORDER BY created_at, id
                    ) AS rn
                    FROM mc_reward_catalog
                ) ranked WHERE rn > 1
            )
        """)
        db_execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mc_reward_catalog_campaign_tier_reward
            ON mc_reward_catalog(campaign_id, tier, reward)
        """)
        for quest_title, objective in [
            ("Archive: The Overlook", "basinSeen"),
            ("Archive: Down into Keel", "keelVisited"),
            ("Archive: The Mines", "minesVisited"),
            ("Archive: First Coal", "gotCoal"),
            ("Archive: The Ticket Up", "halyardVisited"),
        ]:
            db_execute(
                """INSERT INTO mc_quests (campaign_id, title, kind)
                   SELECT id, %s, 'basin_archive' FROM campaigns WHERE key = 'evoke-prosperity'
                   AND NOT EXISTS (SELECT 1 FROM mc_quests WHERE title = %s)""",
                (quest_title, quest_title)
            )
            db_execute(
                """INSERT INTO mc_quest_triggers (quest_id, objective, threshold)
                   SELECT id, %s, 1 FROM mc_quests WHERE title = %s
                   ON CONFLICT (quest_id, objective) DO NOTHING""",
                (objective, quest_title)
            )

        # Replace the 4 placeholder side quests (Find Hidden Treasure,
        # Master Farmer, Mining Expert, Explorer's Log -- never had a
        # mc_quest_triggers row, so nothing could ever check one off) with
        # the real Keel Mine expedition line (2026-07-22): explore + descend
        # already exist as Basin Archive entries above, this is the
        # mine-it-sell-it-earn-it chain that follows. Catalog only for
        # now -- no mc_quest_triggers yet, same disabled-until-real
        # Field Quest Log state as before; the "sell ores" step in
        # particular has no in-world sell mechanic to trigger off yet
        # (only the Halyard arena's spider-eye sell plate exists today).
        # Guarded by zero completions/submissions so this never deletes a
        # quest some real learner actually finished.
        db_execute("""
            DELETE FROM mc_quests WHERE title IN
                ('Find Hidden Treasure', 'Master Farmer', 'Mining Expert', 'Explorer''s Log')
            AND NOT EXISTS (SELECT 1 FROM mc_quest_completions c WHERE c.quest_id = mc_quests.id)
            AND NOT EXISTS (SELECT 1 FROM mc_quest_submissions s WHERE s.quest_id = mc_quests.id)
        """)
        for quest_title, description in [
            ("Speak with B1llBot", "Find B1llBot in Keel and say hello."),
            ("Enter the Keel Mine", "Step through the Keel Mine entrance."),
            ("Mine 32 Coal", "Mine 32 coal ore in the Keel Mine."),
            ("Mine 16 Iron Ore", "Mine 16 iron ore in the Keel Mine."),
            ("Return to town", "Carry your haul back to Keel."),
            ("Sell your ores at the Marketplace", "Trade your coal and iron for coins at the Marketplace."),
            ("Earn your first coins", "Walk away from the Marketplace with money in your pocket."),
        ]:
            db_execute(
                """INSERT INTO mc_quests (campaign_id, title, description, kind)
                   SELECT id, %s, %s, 'side_quest' FROM campaigns WHERE key = 'evoke-prosperity'
                   AND NOT EXISTS (SELECT 1 FROM mc_quests WHERE title = %s)""",
                (quest_title, description, quest_title)
            )

        # Wave 3 (BUILD_PLAN_2.md): admin-configurable stages, daily
        # reflections (Words of Wisdom), phone pairing tokens, and the
        # two-channel Minecraft link codes.
        # Stage is instructor pedagogy config, not LMS data -- lives on
        # EVOKE's side of the sync and defaults to the mission's week so a
        # fresh install has a sensible grouping without any admin work.
        db_execute("ALTER TABLE missions ADD COLUMN IF NOT EXISTS stage INTEGER")
        db_execute("UPDATE missions SET stage = week WHERE stage IS NULL")
        # objective_md was added to init-db.sql (2026-07-21) but never to
        # this idempotent block -- init-db.sql only runs on a brand-new
        # Postgres volume, so any pre-existing dev DB threw
        # `column "objective_md" does not exist` on every /api/missions
        # call (surfacing as a blank page) after pulling that change.
        db_execute("ALTER TABLE missions ADD COLUMN IF NOT EXISTS objective_md TEXT")
        db_execute("""CREATE TABLE IF NOT EXISTS daily_reflections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            reflection_date DATE NOT NULL DEFAULT CURRENT_DATE,
            text TEXT NOT NULL,
            wisdom TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, reflection_date)
        )""")
        db_execute("""CREATE TABLE IF NOT EXISTS pairing_tokens (
            token UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_at TIMESTAMP
        )""")
        db_execute("""CREATE TABLE IF NOT EXISTS mc_link_codes (
            code INTEGER PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            minecraft_username VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            status VARCHAR(16) NOT NULL DEFAULT 'waiting'
        )""")

        # Staged in-world dialogue for the Minecraft NPCs (Jim/Beth/Benjamin/
        # Craig/Billbot) -- externally editable content, not baked into the
        # ProsperityDialog.java mod itself. The mod fetches GET /api/npc-lines
        # at startup and on a periodic refresh, so editing a row here changes
        # what an NPC says without a mod rebuild/redeploy. Replaced the old
        # BillBot.java's live OpenWebUI call per-NPC (removed along with
        # in-game player-to-player chat, see GAPS.md) -- these are canned
        # lines now, not AI-generated.
        db_execute("""CREATE TABLE IF NOT EXISTS npc_lines (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            npc_name VARCHAR(64) NOT NULL,
            line_text TEXT NOT NULL,
            is_greeting BOOLEAN NOT NULL DEFAULT false,
            sort_order INT NOT NULL DEFAULT 0
        )""")
        if not db_fetch_one("SELECT 1 FROM npc_lines"):
            _npc_seed = [
                ("jim", True, 0, "Here — take this. [taps a small relay chip into your hand] Frequency's yours now. Signal's not what it used to be, but it'll reach me."),
                ("jim", False, 1, "Yield's down again today. Coal's not what it used to be around here."),
                ("jim", False, 2, "Keep your credits close. Don't gamble 'em — I've seen it eat men whole."),
                ("jim", False, 3, "Never miss a shift. That's the only rule that matters down here."),
                ("jim", False, 4, "New here? Mines are the west end of town, past the coin-flip stand. Grab the free pickaxe at the worker station by the pen first."),
                ("beth", True, 0, "You want to actually talk sometime? Here. [hands over a scratched relay chip] Towers went dark years back — this is the only way anyone talks anymore."),
                ("beth", False, 1, "Apartment's still got no walls. Water still comes in warm, if it comes at all."),
                ("beth", False, 2, "Tough conditions, low pay, fewer resources every season. That's Keel for you."),
                ("beth", False, 3, "You didn't hear it from me, but the Oasis isn't hoarding water out of spite. It's something else."),
                ("benjamin", True, 0, "You'll want a relay if you're going to keep asking me questions. Here — courtesy of Alpha Dynamics. Don't say we never gave you anything."),
                ("benjamin", False, 1, "Need tools? Right-click the signs. Alpha's not made of credits, you know."),
                ("benjamin", False, 2, "Halyard's better than this dust pit, I'll tell you that much."),
                ("benjamin", False, 3, "Alpha does more for this town than the government ever did. Remember that."),
                ("benjamin", False, 4, "Saved $100? Type /trigger buyTicket and Alpha will print your train ticket to Halyard. Nothing up there is free either."),
                ("craig", True, 0, "Eh — take the chip, keep the noise down. [mutters] Not like the old towers are coming back. Frequency's yours."),
                ("craig", False, 1, "Coal's honest work. Don't let the Oasis crowd tell you otherwise."),
                ("craig", False, 2, "Keel residents do the hardest work on this mountain. Don't forget it."),
                ("craig", False, 3, "...You're not still short on credits, are you? [glances toward the town hall stairs, says nothing more]"),
                ("billbot", True, 0, "I've patched a relay into your Field Kit. The old comm towers went dark when Alpha pulled out — this signal's the only line left, but it reaches me anytime you need it."),
                ("billbot", False, 1, "Every credit you don't spend today is a choice you're making about tomorrow."),
                ("billbot", False, 2, "Ask yourself: who benefits when you don't ask questions about where your pay goes?"),
                ("billbot", False, 3, "I've got more to say than a few words can hold out here. Open your Field Kit — let's really talk."),
                ("billbot", False, 4, "Pockets full of coal? Alpha buys it — the shop sign in the mines, or /trigger sellCoal from anywhere. Save $100 and the train up is yours: /trigger buyTicket."),
                # The starter villager pen (keel_villager_pen datapack) -- decorative
                # "unemployed" NPCs, no relay-chip mechanic (Billbot/Jim/Beth/Benjamin/
                # Craig already cover that), just ambient Keel-hardship flavor.
                ("chuzz", True, 0, "Oh — you're new. Don't mind me, I'm just... between jobs. Aren't we all."),
                ("chuzz", False, 1, "Alpha stopped hiring out of the pen years back. Now we just... exist."),
                ("chuzz", False, 2, "Used to work the mines. The coal took my knees before it took my job."),
                ("chuzz", False, 3, "Ethan says the Oasis is hiring. Ethan says a lot of things."),
                ("ethan", True, 0, "Welcome to Keel. Don't expect much — most of us don't."),
                ("ethan", False, 1, "I hear things. Traders talk more than they think they do."),
                ("ethan", False, 2, "Fredster's convinced there's easy credits up the mountain. There aren't."),
                ("ethan", False, 3, "Nobody's coming to fix this place. We just get by."),
                ("fredster", True, 0, "Hey! New face! Wouldn't get your hopes up about this town, though."),
                ("fredster", False, 1, "Had a plan once. Involved coal, a cart, and not thinking it through."),
                ("fredster", False, 2, "Want advice? Keep your credits. Don't trust anyone selling a \"sure thing.\""),
                ("fredster", False, 3, "Chuzz and Ethan don't talk much. Suits me — more room for me to."),
            ]
            for _name, _greeting, _order, _text in _npc_seed:
                db_execute(
                    "INSERT INTO npc_lines (npc_name, line_text, is_greeting, sort_order) VALUES (%s, %s, %s, %s)",
                    (_name, _text, _greeting, _order)
                )

        # Completing the Aqueduct Kit delivers a real in-world trophy for
        # linked players (a conduit — the most water-alive block in the
        # game) through the same tier-keyed reward pipeline as everything.
        if not db_fetch_one("SELECT 1 FROM mc_reward_catalog WHERE tier = 'kit'"):
            db_execute(
                """INSERT INTO mc_reward_catalog (campaign_id, tier, reward_type, reward, reward_amount, persistent)
                   SELECT id, 'kit', 'item', 'minecraft:conduit', 1, false FROM campaigns WHERE key = 'evoke-prosperity'"""
            )

    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown():
    """Close database pool"""
    global async_db_pool

    if async_db_pool:
        await async_db_pool.close()
        logger.info("Async database pool closed")

# ========== Pydantic Models ==========
class Mission(BaseModel):
    id: str
    title: str
    week: int
    arc: str
    superpower: str
    brief: str

class Award(BaseModel):
    id: str
    mission_id: str
    tier: str
    source: str
    awarded_at: str
    collected_at: Optional[str]

class Notification(BaseModel):
    id: str
    award_id: str
    created_at: str
    read: bool

class MinecraftLink(BaseModel):
    username: str
    uuid: Optional[str]

class Quest(BaseModel):
    id: str
    title: str
    description: str
    kind: str

# ========== Helper Functions ==========
def db_execute(query: str, params=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()
        result = cur.fetchall() if query.strip().upper().startswith("SELECT") else None
        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        return_db_connection(conn)

def db_fetch_one(query: str, params=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        result = cur.fetchone()
        cur.close()
        return result
    finally:
        return_db_connection(conn)

def db_fetch_all(query: str, params=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        result = cur.fetchall()
        cur.close()
        return result
    finally:
        return_db_connection(conn)

async def publish_event(event_type: str, data: dict):
    producer = get_producer()
    event = {
        "event_type": event_type,
        "version": "1.0.0",
        "timestamp": datetime.datetime.now().isoformat(),
        "data": data
    }
    producer.send(topic_for_event(event_type), value=event)
    producer.flush()
    return event

# ========== Health Checks ==========
@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/health/database")
async def health_database():
    try:
        result = db_fetch_one("SELECT 1")
        return {"status": "connected"}
    except:
        return JSONResponse({"status": "disconnected"}, status_code=500)

@app.get("/api/health/minio")
async def health_minio():
    try:
        s3_client.head_bucket(Bucket="default-bucket")
        return {"status": "ok"}
    except:
        return JSONResponse({"status": "error"}, status_code=500)

@app.get("/api/health/opensearch")
async def health_opensearch():
    try:
        await os_client.info()
        return {"status": "ok"}
    except:
        return JSONResponse({"status": "error"}, status_code=500)

# ========== Session Management ==========
# The old /api/login and /api/dev-login let an unauthenticated caller become
# ANY user by passing their email or id -- not a dev convenience, an open
# impersonation endpoint, reachable even with real Brightspace auth
# configured. Both routes below are now hard-disabled the moment
# AUTH_PROVIDER is set; with no AUTH_PROVIDER (fresh local clone), dev-login
# still exists for convenience, but now mints the same signed, httponly
# session cookie every other route relies on -- no longer a JSON payload
# the frontend chooses to trust, and no longer accepts an arbitrary user_id.
@app.post("/api/dev-login")
async def dev_login(response: Response, email: Optional[str] = None):
    """Local-dev-only auto-login. Disabled entirely once AUTH_PROVIDER is
    configured -- see the Brightspace OAuth callback below for how real
    logins work instead."""
    if get_auth_provider():
        raise HTTPException(status_code=404, detail="Not available -- real login is configured")
    if email:
        result = db_fetch_one("SELECT id, display_name FROM users WHERE email = %s", (email,))
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        user_id, display_name = result
    else:
        result = db_fetch_one("SELECT id, display_name, email FROM users WHERE role = 'learner' ORDER BY created_at LIMIT 1")
        if not result:
            result = db_fetch_one("SELECT id, display_name, email FROM users ORDER BY created_at LIMIT 1")
        if not result:
            raise HTTPException(status_code=404, detail="No users found")
        user_id, display_name, email = result

    issue_session(response, str(user_id), role="learner")
    return {"user_id": str(user_id), "display_name": display_name, "email": email}


@app.post("/api/admin/login")
async def admin_login(response: Response, username: str = Form(...), password: str = Form(...)):
    """The one non-Brightspace login: a human ops/instructor reaching
    #/admin. Everything about *students* -- roster, teams, roles -- is
    Brightspace's job now (OAuth login + Groups sync); this exists only so
    someone can reach mission release gating and the Ops Deck without an
    LMS account. Disabled unless EVOKE_ADMIN_PASSWORD_HASH is set."""
    if not verify_admin_password(username, password):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    org_row = db_fetch_one("SELECT id FROM organizations LIMIT 1")
    org_id = org_row[0] if org_row else None
    admin_email = f"{username}@evoke.local"
    admin_row = db_fetch_one("SELECT id FROM users WHERE email = %s", (admin_email,))
    if admin_row:
        admin_user_id = str(admin_row[0])
    else:
        admin_user_id = str(uuid.uuid4())
        db_execute(
            """INSERT INTO users (id, org_id, display_name, email, role)
               VALUES (%s::uuid, %s::uuid, %s, %s, 'admin')
               ON CONFLICT (email, org_id) DO NOTHING""",
            (admin_user_id, org_id, f"Evoke Admin ({username})", admin_email),
        )
    issue_session(response, admin_user_id, role="admin")
    return {"user_id": admin_user_id, "role": "admin"}


# ========== Identity Management ==========
# /api/identity/link-brightspace used to live here -- removed. It verified
# against brightspace-sim directly and took evoke_user_id/brightspace_user_id
# straight from an unauthenticated request body (no session check at all),
# exactly the client-supplied-identity pattern the real OAuth login work
# replaced everywhere else. Superseded entirely by auth_brightspace_callback
# + get_or_create_evoke_player -- nothing in the frontend called this route.
class LinkMinecraftRequest(BaseModel):
    evoke_user_id: str
    minecraft_uuid: str
    minecraft_username: str

@app.post("/api/identity/link-minecraft")
async def link_minecraft_identity(request: LinkMinecraftRequest):
    """Link EVOKE user to Minecraft UUID and username"""
    try:
        db_execute(
            """INSERT INTO evoke_identities (user_id, minecraft_uuid, minecraft_username)
               VALUES (%s::uuid, %s, %s)
               ON CONFLICT (minecraft_uuid) DO UPDATE
               SET minecraft_username = %s, updated_at = CURRENT_TIMESTAMP""",
            (request.evoke_user_id, request.minecraft_uuid, request.minecraft_username,
             request.minecraft_username)
        )

        return {
            "evoke_user_id": request.evoke_user_id,
            "minecraft_uuid": request.minecraft_uuid,
            "minecraft_username": request.minecraft_username,
            "status": "linked"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Minecraft linking failed: {str(e)}")

@app.get("/api/identity/{evoke_user_id}")
async def get_identity(evoke_user_id: str = Depends(require_self)):
    """Get cross-system identity mapping for a user"""
    try:
        result = db_fetch_one(
            """SELECT user_id, brightspace_user_id, minecraft_uuid, minecraft_username
               FROM evoke_identities WHERE user_id = %s::uuid""",
            (evoke_user_id,)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Identity mapping not found")

        user_id, bs_user_id, mc_uuid, mc_username = result
        return {
            "evoke_user_id": str(user_id),
            "brightspace_user_id": bs_user_id,
            "minecraft_uuid": mc_uuid,
            "minecraft_username": mc_username
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/identity/by-brightspace/{brightspace_user_id}")
async def get_identity_by_brightspace(brightspace_user_id: int):
    """Look up EVOKE user ID by Brightspace user ID"""
    try:
        result = db_fetch_one(
            """SELECT user_id FROM evoke_identities WHERE brightspace_user_id = %s""",
            (brightspace_user_id,)
        )
        if not result:
            raise HTTPException(status_code=404, detail="No EVOKE user linked to this Brightspace account")

        evoke_user_id = result[0]
        return {
            "evoke_user_id": str(evoke_user_id),
            "brightspace_user_id": brightspace_user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== LTI 1.3 Launch ==========
@app.post("/api/lti/launch")
async def lti_launch(
    id_token: str = Form(...),
    response: Response = None,
):
    """
    LTI 1.3 platform launch endpoint.

    Brightspace sends an LTI 1.3 launch request with a signed JWT.
    This endpoint verifies the JWT, auto-logs in the user, and redirects.

    Flow:
    1. Receive LTI launch request
    2. Verify JWT signature using Brightspace public key
    3. Extract user claims (sub, email, name, roles)
    4. Get or create user in EVOKE
    5. Link to Brightspace via evoke_identities
    6. Create session
    7. Set session cookie
    8. Redirect to missions (auto-logged in)
    """
    if not brightspace_lti:
        logger.warning("LTI not configured")
        raise HTTPException(
            status_code=503,
            detail="LTI launch not available (not configured)"
        )

    try:
        session_token, user_dict = await brightspace_lti.verify_and_login(id_token)

        if not session_token:
            logger.warning("LTI login verification failed")
            raise HTTPException(status_code=401, detail="LTI verification failed")

        logger.info(
            f"LTI login successful for user {user_dict['user_id']} ({user_dict['role']})"
        )

        # Create redirect response to missions page
        redirect_response = RedirectResponse(
            url="/api/missions",
            status_code=302
        )

        # Same signed, httponly session cookie as the Brightspace OAuth
        # login and Evoke Admin login use -- no more separate
        # readable-by-JS user_id/user_display_name cookies a script (or a
        # forged request) could set to any value. brightspace_lti's own
        # session_token isn't used as the app session; it's discarded here
        # once the identity it verified has been folded into our cookie.
        issue_session(redirect_response, user_dict["user_id"], role=user_dict.get("role", "learner"))

        return redirect_response

    except Exception as e:
        logger.error(f"LTI launch error: {e}")
        raise HTTPException(status_code=400, detail=f"LTI launch failed: {str(e)}")

# ========== OAuth 2.0 Login (swappable provider) ==========
# A real user clicking "Login with Central Registry" and authorizing as
# themselves -- distinct from the LTI 1.3 platform-launch flow above (a
# platform-initiated launch) and from the server-to-server Brightspace API
# creds evoke/lms/brightspace_lms.py uses for roster/classlist/dropbox calls.
# AUTH_PROVIDER (.env) picks the implementation (evoke/oauth_providers.py);
# adding Keycloak/EvokeHub/etc. later means adding another AuthProvider, not
# touching these routes.

@app.get("/api/auth/config")
async def auth_config():
    """Tells the frontend whether real login is required -- a fresh clone
    with no AUTH_PROVIDER configured keeps today's dev auto-login behavior
    (see controller.js's seedFromBackend)."""
    provider = get_auth_provider()
    return {"login_required": provider is not None, "provider": provider.name if provider else None}

@app.get("/api/auth/login")
async def auth_login():
    """Redirects to the configured provider's authorize URL. A random state
    value is set as a short-lived httponly cookie and echoed back by the
    provider on callback -- a double-submit CSRF check, no server-side
    state store needed."""
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No OAuth login provider configured")
    state = uuid.uuid4().hex
    response = RedirectResponse(url=provider.authorize_url(state), status_code=302)
    response.set_cookie(
        key="oauth_state", value=state, httponly=True, secure=True, samesite="Lax", max_age=600,
    )
    return response

@app.get("/api/auth/brightspace/callback")
async def auth_brightspace_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Brightspace redirects the browser here after the user authorizes.
    Exchanges the code, resolves the real user via whoami, provisions/finds
    their EVOKE Player (the same shared path LTI launches and admin
    roster-import already use -- evoke/identity.py), syncs their team from
    whichever Brightspace Group they're enrolled in (Brightspace is the
    source of truth for team assignment, not a separate Evoke-side admin
    step -- see oauth_providers.py's _resolve_team_name), then hands off to
    the SPA's existing playtest magic-link convention (?login=<email>, see
    controller.js's seedFromBackend) rather than inventing a second
    identity hand-off mechanism."""
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No OAuth login provider configured")
    if error:
        raise HTTPException(status_code=400, detail=f"Brightspace login failed: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code/state")

    # Admin token-only connect (see admin_brightspace_connect above) --
    # same redirect URI as a real learner login, distinguished by its own
    # state cookie. Caches the token against the already-logged-in Evoke
    # Admin session and stops there -- never provisions/logs in as a
    # Brightspace user, so the admin account stays exactly as
    # Brightspace-independent as it was before this button was ever clicked.
    admin_state = request.cookies.get("admin_oauth_state")
    if admin_state and state == admin_state:
        admin_id = get_current_admin(request)
        try:
            profile = await provider.exchange_code(code)
        except OAuthLoginError as e:
            logger.error(f"Brightspace admin-connect failed: {e}")
            raise HTTPException(status_code=401, detail=str(e))
        # Always exactly one row -- this connection is shared across every
        # admin/course-wide operation (roster, assignment pull, grades),
        # not tied to whichever admin happened to click Connect. Whoever
        # authenticates here needs to be an instructor/TA-level Brightspace
        # account for roster pulls specifically to work -- see BRIGHTSPACE.md.
        expires_at = datetime.datetime.now() + datetime.timedelta(seconds=profile.get("expires_in", 3600))
        db_execute("DELETE FROM brightspace_service_connection")
        db_execute(
            """INSERT INTO brightspace_service_connection
               (brightspace_user_id, access_token, refresh_token, expires_at, connected_by_admin_id)
               VALUES (%s, %s, %s, %s, %s::uuid)""",
            (profile["subject"], profile["access_token"], profile.get("refresh_token"), expires_at, admin_id)
        )
        redirect_response = RedirectResponse(url="/admin/", status_code=302)
        redirect_response.delete_cookie("admin_oauth_state")
        return redirect_response

    expected_state = request.cookies.get("oauth_state")
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    try:
        profile = await provider.exchange_code(code)
    except OAuthLoginError as e:
        logger.error(f"Brightspace OAuth login failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))

    evoke_user_id = await get_or_create_evoke_player(
        async_db_pool,
        brightspace_user_id=profile["subject"],
        email=profile["email"],
        display_name=profile["display_name"],
        role=profile["role"],
    )
    if not evoke_user_id:
        raise HTTPException(status_code=500, detail="Failed to provision EVOKE Player")

    org_row = await async_db_pool.fetchrow("SELECT id FROM organizations LIMIT 1")
    if org_row and profile.get("team_name"):
        await sync_team_membership(async_db_pool, str(org_row["id"]), evoke_user_id, profile["team_name"])

    # This student's own token, persisted (not just cached in memory) so
    # the Brightspace Submission Worker can push their evidence as them --
    # see evoke/workers.py and BRIGHTSPACE.md. Refreshed on demand via
    # brightspace_refresh_token rather than needing them to log in again
    # every time it's used.
    expires_at = datetime.datetime.now() + datetime.timedelta(seconds=profile.get("expires_in", 3600))
    db_execute(
        """UPDATE evoke_identities SET
               brightspace_access_token = %s,
               brightspace_refresh_token = %s,
               brightspace_token_expires_at = %s
           WHERE user_id = %s::uuid""",
        (profile.get("access_token"), profile.get("refresh_token"), expires_at, evoke_user_id)
    )

    # No more ?login=<email> round-trip: the callback itself is the only
    # place that ever saw a verified identity, so it's the only place that
    # should ever mint a session for it. Nothing (query string, browser
    # history, referrer headers, server logs) carries the email anymore.
    redirect_response = RedirectResponse(url="/", status_code=302)
    issue_session(redirect_response, evoke_user_id, role=profile["role"])
    redirect_response.delete_cookie("oauth_state")
    return redirect_response

# The Brightspace real-API test harness (/api/test/brightspace/*,
# static/test-brightspace.html) that used to live here is superseded:
# static/admin's Mission Sync panel does the real assignments pull for
# real now (/api/admin/brightspace/assignments), and real submission goes
# through the Brightspace Submission Worker using each student's own
# persisted token (evoke/workers.py), not a request-scoped in-memory cache.
# The static HTML page still exists but its backend routes are gone.

@app.get("/api/session/validate")
async def validate_session(user_id: str = Depends(get_current_user)):
    """Validates the real session cookie (see auth_session.py) -- replaces
    the old version, which accepted any non-empty string as a valid
    session. 401s via get_current_user if there's no valid session.

    A correctly-signed cookie whose user row is GONE (e.g. the DB was
    reset while a browser kept its cookie) used to return status=valid
    with null fields -- the SPA then booted as a ghost user and every
    downstream call 404'd, rendering a blank page that Log Out couldn't
    fix. Treat it as no session: 401 and clear the cookie so the client
    falls through to its normal logged-out/re-login path."""
    row = db_fetch_one("SELECT display_name, email FROM users WHERE id = %s::uuid", (user_id,))
    if not row:
        resp = JSONResponse(status_code=401, content={"detail": "Session user no longer exists -- log in again"})
        clear_session(resp)
        return resp
    return {
        "status": "valid",
        "user_id": user_id,
        "display_name": row[0],
        "email": row[1],
    }

@app.post("/api/session/logout")
async def logout_session(response: Response):
    """Logout and clear the session cookie, plus the old cookie names in
    case a browser still has them from before this change.

    Clearing Evoke's own session cookie is all this endpoint can actually
    do -- it has no way to touch Brightspace's separate session in the same
    browser. On a shared/lab computer, that gap is a real problem: if
    Brightspace's own session is still alive, the next person to click
    "Login with Central Registry" gets silently signed in as whoever just
    "logged out," no credentials prompt at all (found live -- confirmed
    charge.yacenter.org/d2l/lp/auth/logout/LogoutConfirmation.d2l is a real,
    working per-tenant logout page). Returning that URL here lets the
    frontend send the browser through it right after -- one extra
    confirmation click on Brightspace's own page, but it's what actually
    closes the SSO session, not just Evoke's half of it."""
    clear_session(response)
    response.delete_cookie("session_token")
    response.delete_cookie("user_id")
    response.delete_cookie("user_display_name")
    logger.info("User logged out")
    tenant_url = os.getenv("BRIGHTSPACE_TENANT_URL")
    brightspace_logout_url = f"{tenant_url}/d2l/lp/auth/logout/LogoutConfirmation.d2l" if tenant_url else None
    return {"status": "success", "message": "Logged out successfully", "brightspace_logout_url": brightspace_logout_url}

# ========== Brightspace Grade Webhook ==========
@app.post("/api/webhooks/brightspace/grade")
async def brightspace_grade_webhook(
    submission_id: str = Form(...),
    brightspace_user_id: int = Form(...),
    grade: int = Form(...),
    feedback: str = Form(None),
):
    """
    Webhook called when teacher grades submission in Brightspace.

    Brightspace can be configured to POST grade updates here.
    This syncs grade back to EVOKE and awards epic/legendary badges.

    Flow:
    1. Receive grade update from Brightspace webhook
    2. Look up EVOKE user via brightspace_user_id
    3. Find submission record
    4. Update submission with grade + feedback
    5. Award badges based on grade:
       - 95+: legendary tier
       - 85-94: epic tier
       - <85: common tier (already awarded)
    6. Sync award to Brightspace (push_badge_award)
    7. Publish TeacherReviewed event
    """
    try:
        logger.info(f"Grade webhook: user {brightspace_user_id}, grade {grade}")

        # Look up EVOKE user
        evoke_user = db_fetch_one(
            "SELECT user_id FROM evoke_identities WHERE brightspace_user_id = %s",
            (brightspace_user_id,)
        )

        if not evoke_user:
            logger.warning(f"No EVOKE user linked to Brightspace user {brightspace_user_id}")
            return {"status": "error", "message": "User not linked"}

        evoke_user_id = evoke_user[0]

        # Update submission with grade. status='graded' is this pipeline's
        # terminal state (see workers.py's BRIGHTSPACE SUBMISSION WORKER
        # comment) -- can only ever land on a row that already reached
        # 'brightspace', since Brightspace has nothing to grade otherwise.
        db_execute(
            """UPDATE submissions SET grade = %s, feedback = %s, graded_at = CURRENT_TIMESTAMP, status = 'graded'
               WHERE brightspace_submission_id = %s""",
            (grade, feedback, submission_id)
        )

        logger.info(f"Submission {submission_id} updated with grade {grade}")

        # Get submission details for award logic
        submission = db_fetch_one(
            """SELECT mission_id FROM submissions
               WHERE brightspace_submission_id = %s""",
            (submission_id,)
        )

        if not submission:
            logger.warning(f"Submission {submission_id} not found")
            return {"status": "error", "message": "Submission not found"}

        mission_id = submission[0]

        # Get campaign for badge lookup
        campaign_id = db_fetch_one(
            "SELECT active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
            (evoke_user_id,)
        )

        if not campaign_id:
            logger.warning(f"No campaign found for user {evoke_user_id}")
            return {"status": "error", "message": "Campaign not found"}

        campaign_id = campaign_id[0]

        # Determine badge tier based on grade
        if grade >= 95:
            tier = "legendary"
            badge_key = "legendary-tier"
        elif grade >= 85:
            tier = "epic"
            badge_key = "epic-tier"
        else:
            tier = "common"
            badge_key = "common-tier"

        # Get badge ID
        badge = db_fetch_one(
            "SELECT id FROM badges WHERE campaign_id = %s::uuid AND key = %s",
            (campaign_id, badge_key)
        )

        if not badge:
            logger.warning(f"Badge {badge_key} not found for campaign {campaign_id}")
            return {"status": "error", "message": "Badge not found"}

        badge_id = badge[0]

        # Check if badge already awarded (avoid duplicates)
        existing_award = db_fetch_one(
            """SELECT id FROM awards
               WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = %s""",
            (evoke_user_id, mission_id, tier)
        )

        if existing_award:
            logger.info(f"Badge {tier} already awarded for mission {mission_id}")
        else:
            # Award badge
            award_id = str(uuid.uuid4())
            db_execute(
                """INSERT INTO awards (id, user_id, mission_id, tier, source, awarded_at)
                   VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'teacher_review', CURRENT_TIMESTAMP)""",
                (award_id, evoke_user_id, mission_id, tier)
            )

            # Pushing this award into Brightspace's own Award Service (BAS)
            # used to happen here via the now-removed service-account
            # adapter -- out of scope for this pass (roster/assignments/
            # submissions/grades, not badge push-back). The award is still
            # real and local (INSERT INTO awards above); only the optional
            # "also show it in Brightspace's own gamification feature" step
            # is gone, and it was already best-effort/non-blocking.

            # Publish event
            await publish_event("TeacherReviewed", {
                "user_id": evoke_user_id,
                "mission_id": mission_id,
                "grade": grade,
                "tier": tier,
                "feedback": feedback or ""
            })

        # Create notification
        notification_id = str(uuid.uuid4())
        award = db_fetch_one(
            """SELECT id FROM awards
               WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = %s LIMIT 1""",
            (evoke_user_id, mission_id, tier)
        )

        if award:
            db_execute(
                "INSERT INTO notifications (id, user_id, award_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
                (notification_id, evoke_user_id, award[0])
            )

        return {
            "status": "success",
            "message": f"Grade {grade} processed, {tier} tier award granted",
            "award_tier": tier
        }

    except Exception as e:
        logger.error(f"Grade webhook error: {e}")
        return {"status": "error", "message": str(e)}

# The backup grade-polling route (/api/webhooks/brightspace/poll) that used
# to live here depended on the now-removed service-account adapter.
# Superseded by POST /api/admin/missions/{id}/sync-grades, which does the
# same job (pull grade values, write them onto the matching submission)
# via the shared service connection instead.

# ========== Mission API ==========
@app.get("/api/missions")
async def list_missions(user_id: str = Depends(require_self)):
    """List all missions for a campaign"""
    try:
        # Get organization and campaign for the user
        org_result = db_fetch_one(
            "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
            (user_id,)
        )
        if not org_result:
            raise HTTPException(status_code=404, detail="Organization not found")

        campaign_id = org_result[0]

        # Fetch all missions for this campaign
        missions_data = db_fetch_all(
            """SELECT id, title, week, arc, superpower, mission_brief_md, released_at,
                      pbl_description, evidence_requirements_md, objective_md
               FROM missions WHERE campaign_id = %s::uuid ORDER BY week, sequence""",
            (campaign_id,)
        )

        missions = []
        for mission in missions_data:
            mission_id, title, week, arc, superpower, brief, released_at, pbl_description, evidence_requirements, objective = mission

            # Get any linked quest
            quest = db_fetch_one(
                "SELECT id, title, description FROM mc_quests WHERE mission_id = %s::uuid AND kind = 'mission_quest' LIMIT 1",
                (mission_id,)
            )

            missions.append({
                "id": str(mission_id),
                "title": title,
                "week": week,
                "arc": arc,
                "superpower": superpower,
                "brief": brief,
                "objective": objective,
                "pbl_description": pbl_description,
                "evidence_requirements": evidence_requirements,
                "released": released_at is not None,
                "quest": {
                    "id": str(quest[0]),
                    "title": quest[1],
                    "description": quest[2]
                } if quest else None
            })

        return {"missions": missions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== Admin: mission release gating ==========
# No role/permission check yet -- these routes are unprotected by construction,
# same as the rest of this dev-grade build (see GAPS.md's "Auth is dev-grade
# outside LTI" gap). Not a new gap introduced here, just inheriting the
# existing one; real deployment needs an instructor-role check before this
# ships to a real classroom.
@app.get("/api/admin/missions")
async def admin_list_missions(user_id: str = Depends(get_current_admin)):
    """All missions for the caller's campaign, including release state --
    the admin-facing counterpart to GET /api/missions, which only shows
    the learner-relevant fields."""
    try:
        org_result = db_fetch_one(
            "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
            (user_id,)
        )
        if not org_result:
            raise HTTPException(status_code=404, detail="Organization not found")

        missions_data = db_fetch_all(
            """SELECT id, title, week, sequence, arc, released_at, stage, lms_assignment_ref
               FROM missions WHERE campaign_id = %s::uuid ORDER BY week, sequence""",
            (org_result[0],)
        )
        return {"missions": [{
            "id": str(m[0]), "title": m[1], "week": m[2], "sequence": m[3], "arc": m[4],
            "released": m[5] is not None,
            "released_at": m[5].isoformat() if m[5] else None,
            "stage": m[6],
            "lms_assignment_ref": m[7],
        } for m in missions_data]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/missions/{mission_id}/release")
async def admin_release_mission(mission_id: str, admin_id: str = Depends(get_current_admin)):
    """Console-player feedback (BUILD_PLAN_2's "season drops" gap): a
    stage/mission release is already this campaign's real content-drop
    mechanic, but nothing ever announced it -- CoD frames a season launch
    with a NEW banner naming what's inside; this just gives our existing
    mechanic the same framing. Checks released_at *before* the UPDATE
    (db_execute doesn't surface RETURNING, and db_fetch_one doesn't commit
    -- see their definitions above -- so this can't be done in one
    UPDATE...RETURNING call) to know whether this call actually flipped it,
    so a repeat call on an already-released mission never fires a duplicate
    announcement."""
    try:
        mission = db_fetch_one("SELECT title, week, arc, released_at FROM missions WHERE id = %s::uuid", (mission_id,))
        was_locked = bool(mission) and mission[3] is None
        db_execute(
            "UPDATE missions SET released_at = CURRENT_TIMESTAMP WHERE id = %s::uuid AND released_at IS NULL",
            (mission_id,)
        )
        if was_locked:
            await publish_event("MissionReleased", {
                "mission_id": mission_id,
                "title": mission[0],
                "week": mission[1],
                "arc": mission[2],
            })
        return {"status": "released"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/missions/{mission_id}/unrelease")
async def admin_unrelease_mission(mission_id: str, admin_id: str = Depends(get_current_admin)):
    """Puts a mission back behind the gate. Deliberately doesn't touch
    submissions/awards already granted while it was open -- unreleasing is
    about stopping new submissions, not undoing a learner's completed work."""
    try:
        db_execute(
            "UPDATE missions SET released_at = NULL WHERE id = %s::uuid",
            (mission_id,)
        )
        return {"status": "unreleased"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Brightspace Mission Sync (Evoke Admin) ==========
# Pull real assignments from the live tenant, validate them, and let an
# admin decide what becomes a mission -- distinct from sync_missions_from_lms
# above, which blind-upserts from brightspace-sim on every startup. Real
# DropboxFolders carry no Evoke curriculum metadata (arc, superpower,
# skills, PFL domain, narrative, evidence checklist -- see CONCEPTS.md's
# Mission glossary entry and the test-harness note further up this file),
# so this only ever writes lms_assignment_ref + title; curriculum fields are
# authored afterward via PUT /api/admin/missions/{id}, a pure Postgres
# write with no Brightspace call -- mission content stays editable with
# zero live LMS connectivity once a mission has been pulled once.
#
# The Evoke Admin account (POST /api/admin/login) is deliberately
# Brightspace-independent -- but pulling real assignment data unavoidably
# needs a live Brightspace credential from *somewhere*. admin_brightspace_connect
# below gets one without giving the admin account a Brightspace identity: it
# reuses the same OAuth authorize/callback round-trip real logins use, but a
# separate admin_oauth_state cookie tells auth_brightspace_callback to just
# cache the resulting token against this already-logged-in admin session
# (see the branch near the top of that function) instead of provisioning a
# Brightspace-linked EVOKE Player. No second Brightspace redirect-URI
# registration needed -- same callback URL, distinguished by that cookie.

async def _get_service_token() -> Optional[str]:
    """A valid access token for the one shared brightspace_service_connection
    row (roster, assignment pull, grade reads -- course-wide operations),
    refreshing it first if it's expired or about to be. Returns None if
    nothing's ever connected, or if the refresh itself fails (refresh token
    revoked/expired) -- callers should treat that as 'reconnect via Connect
    Brightspace', not retry."""
    row = db_fetch_one(
        "SELECT access_token, refresh_token, expires_at FROM brightspace_service_connection LIMIT 1"
    )
    if not row:
        return None
    access_token, refresh_token, expires_at = row
    if expires_at and expires_at > datetime.datetime.now() + datetime.timedelta(seconds=60):
        return access_token
    if not refresh_token:
        return None
    provider = get_auth_provider()
    if not provider:
        return None
    try:
        refreshed = await provider.refresh_access_token(refresh_token)
    except OAuthLoginError as e:
        logger.warning(f"Brightspace service connection refresh failed: {e}")
        return None
    new_expires_at = datetime.datetime.now() + datetime.timedelta(seconds=refreshed.get("expires_in", 3600))
    db_execute(
        "UPDATE brightspace_service_connection SET access_token = %s, refresh_token = %s, expires_at = %s",
        (refreshed["access_token"], refreshed.get("refresh_token", refresh_token), new_expires_at)
    )
    return refreshed["access_token"]


@app.get("/api/admin/brightspace/connect")
async def admin_brightspace_connect(admin_id: str = Depends(get_current_admin)):
    """Kicks off the token-only OAuth round-trip described above. The admin
    session itself is untouched by this -- it only ever ends with a cached
    access token for API calls, never a new login/session."""
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No OAuth login provider configured")
    state = uuid.uuid4().hex
    response = RedirectResponse(url=provider.authorize_url(state), status_code=302)
    response.set_cookie(
        key="admin_oauth_state", value=state, httponly=True, secure=True, samesite="Lax", max_age=600,
    )
    return response


@app.get("/api/admin/brightspace/assignments")
async def admin_brightspace_assignments(admin_id: str = Depends(get_current_admin)):
    """Live pull + validate, no writes. Uses the one shared service
    connection (see _get_service_token, admin_brightspace_connect) and
    list_dropbox_folders. Safe to call repeatedly while an admin reviews."""
    token = await _get_service_token()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="No Brightspace connection yet -- click \"Connect Brightspace\" first, then try the pull again",
        )
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No OAuth login provider configured")
    try:
        folders = await provider.list_dropbox_folders(token)
    except OAuthLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))

    mapped = {
        str(row[0]): str(row[1])
        for row in db_fetch_all("SELECT brightspace_assignment_id, mission_id FROM mission_brightspace_mapping")
    }

    seen_ids = set()
    assignments = []
    for folder in (folders or []):
        raw_id = folder.get("Id")
        name = folder.get("Name")
        assignment_id = str(raw_id) if raw_id not in (None, "") else None
        # DropboxFolder carries its own linked Grade Item ID directly (per
        # docs.valence.desire2learn.com/res/dropbox.html) -- captured here
        # so the Link step can store it for later grade reads, which need
        # this ID, not the assignment ID.
        grade_item_id = folder.get("GradeItemId")

        errors = []
        if assignment_id is None:
            errors.append("Missing assignment ID")
        if not name or not str(name).strip():
            errors.append("Missing name")
        if assignment_id and assignment_id in seen_ids:
            errors.append("Duplicate assignment ID in this pull")
        if assignment_id:
            seen_ids.add(assignment_id)

        assignments.append({
            "id": assignment_id,
            "name": name,
            "grade_item_id": str(grade_item_id) if grade_item_id not in (None, "") else None,
            "already_mapped": mapped.get(assignment_id) if assignment_id else None,
            "errors": errors,
        })
    return {"assignments": assignments}


@app.get("/api/admin/brightspace/roster")
async def admin_brightspace_roster(admin_id: str = Depends(get_current_admin)):
    """Real course roster via the shared service connection. Needs
    enrollment:orgunit:read, which (per
    docs.valence.desire2learn.com/res/enroll.html) requires an
    instructor/TA-level Brightspace account -- connecting as a student
    will 403 here even though it's fine for the assignments pull above.
    Cross-referenced against evoke_identities so an admin can see who's
    enrolled in Brightspace vs. who's actually logged into EVOKE yet --
    visibility only, not a reintroduction of the old manual roster-import
    flow (deliberately removed in favor of automatic OAuth-login
    provisioning)."""
    token = await _get_service_token()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="No Brightspace connection yet -- click \"Connect Brightspace\" first, then try the roster pull again",
        )
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No OAuth login provider configured")
    try:
        classlist = await provider.list_classlist(token)
    except OAuthLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))

    linked = {
        row[0]: str(row[1])
        for row in db_fetch_all("SELECT brightspace_user_id, user_id FROM evoke_identities WHERE brightspace_user_id IS NOT NULL")
    }

    roster = []
    for entry in (classlist or []):
        bs_user_id = entry.get("Identifier")
        try:
            bs_user_id_int = int(bs_user_id) if bs_user_id is not None else None
        except (TypeError, ValueError):
            bs_user_id_int = None
        roster.append({
            "brightspace_user_id": bs_user_id,
            "display_name": entry.get("DisplayName") or " ".join(filter(None, [entry.get("FirstName"), entry.get("LastName")])),
            "logged_into_evoke": bs_user_id_int in linked if bs_user_id_int is not None else False,
            "evoke_user_id": linked.get(bs_user_id_int),
        })
    return {"roster": roster}


class MissionCreateRequest(BaseModel):
    title: str
    arc: Optional[str] = None
    superpower: Optional[str] = None
    primary_skill: Optional[str] = None
    secondary_skill: Optional[str] = None
    pfl_domain: Optional[str] = None
    week: Optional[int] = None
    sequence: Optional[int] = None
    mission_brief_md: Optional[str] = None
    pbl_description: Optional[str] = None
    evidence_requirements_md: Optional[str] = None


@app.post("/api/admin/missions")
async def admin_create_mission(body: MissionCreateRequest, admin_id: str = Depends(get_current_admin)):
    """The Evoke mission is the container: created here with its
    Evoke-authored curriculum fields, independent of Brightspace. A
    Brightspace assignment is attached afterward, one at a time, via
    admin_link_brightspace_assignment below -- never the other way
    around. lms_assignment_ref starts NULL."""
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    org_result = db_fetch_one(
        "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
        (admin_id,)
    )
    if not org_result:
        raise HTTPException(status_code=404, detail="Organization not found")
    campaign_id = org_result[0]

    mission_id = str(uuid.uuid4())
    try:
        db_execute(
            """INSERT INTO missions
               (id, campaign_id, title, arc, superpower, primary_skill, secondary_skill,
                pfl_domain, week, sequence, mission_brief_md, pbl_description, evidence_requirements_md)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                mission_id, campaign_id, title, body.arc, body.superpower,
                body.primary_skill, body.secondary_skill, body.pfl_domain, body.week,
                body.sequence, body.mission_brief_md, body.pbl_description, body.evidence_requirements_md,
            )
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "created", "mission_id": mission_id}


class LinkBrightspaceAssignmentRequest(BaseModel):
    brightspace_assignment_id: str
    # From the assignments pull's own "grade_item_id" field (DropboxFolder's
    # linked GradeItemId) -- optional since a folder isn't required to have
    # a grade item attached. Needed later for grade reads, a separate
    # resource from the assignment ID itself.
    grade_item_id: Optional[str] = None


@app.post("/api/admin/missions/{mission_id}/link-brightspace")
async def admin_link_brightspace_assignment(
    mission_id: str, body: LinkBrightspaceAssignmentRequest, admin_id: str = Depends(get_current_admin)
):
    """Attaches one real Brightspace assignment to an already-created Evoke
    mission -- the container-first flow: create the mission (with its Evoke
    curriculum fields) via POST /api/admin/missions, then link it to the
    one Brightspace assignment it represents. True 1:1, enforced at the
    database level in both directions: missions' own
    UNIQUE(campaign_id, lms_assignment_ref) stops two missions sharing an
    assignment via that column, and idx_mission_brightspace_mapping_assignment
    (added at startup, see below) does the same for
    mission_brightspace_mapping. An assignment already linked to a
    *different* mission 409s naming that mission rather than silently
    stealing the link."""
    org_result = db_fetch_one(
        "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
        (admin_id,)
    )
    if not org_result:
        raise HTTPException(status_code=404, detail="Organization not found")
    campaign_id = org_result[0]

    mission_row = db_fetch_one(
        "SELECT id FROM missions WHERE id = %s::uuid AND campaign_id = %s::uuid", (mission_id, campaign_id)
    )
    if not mission_row:
        raise HTTPException(status_code=404, detail="Mission not found")

    conflict = db_fetch_one(
        """SELECT m.id, m.title FROM mission_brightspace_mapping mbm
           JOIN missions m ON m.id = mbm.mission_id
           WHERE mbm.campaign_id = %s::uuid AND mbm.brightspace_assignment_id = %s AND mbm.mission_id != %s::uuid""",
        (campaign_id, body.brightspace_assignment_id, mission_id)
    )
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"That assignment is already linked to mission \"{conflict[1]}\"",
        )

    try:
        db_execute(
            "UPDATE missions SET lms_assignment_ref = %s WHERE id = %s::uuid",
            (body.brightspace_assignment_id, mission_id)
        )
        db_execute(
            """INSERT INTO mission_brightspace_mapping
               (mission_id, brightspace_assignment_id, campaign_id, brightspace_grade_item_id)
               VALUES (%s::uuid, %s, %s::uuid, %s)
               ON CONFLICT (mission_id, campaign_id) DO UPDATE SET
                   brightspace_assignment_id = EXCLUDED.brightspace_assignment_id,
                   brightspace_grade_item_id = EXCLUDED.brightspace_grade_item_id""",
            (mission_id, body.brightspace_assignment_id, campaign_id, body.grade_item_id)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "linked"}


@app.post("/api/admin/missions/{mission_id}/sync-grades")
async def admin_sync_grades(mission_id: str, admin_id: str = Depends(get_current_admin)):
    """Pulls every student's grade for this mission's linked assignment via
    the shared service connection, maps each back to an EVOKE user via
    evoke_identities, and writes it onto that user's most recent
    team_product submission for this mission -- same terminal
    status='graded' state the webhook path already sets (see BRIGHTSPACE.md).
    NOTE: the GradeValue field names below (PointsNumerator/DisplayedGrade/
    Comments) are a best-effort reading of the Valence grade resource, not
    yet confirmed against a real response -- verify field names the first
    time this actually runs against a linked assignment with real grades."""
    org_result = db_fetch_one(
        "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
        (admin_id,)
    )
    if not org_result:
        raise HTTPException(status_code=404, detail="Organization not found")
    campaign_id = org_result[0]

    mapping = db_fetch_one(
        "SELECT brightspace_grade_item_id FROM mission_brightspace_mapping WHERE mission_id = %s::uuid AND campaign_id = %s::uuid",
        (mission_id, campaign_id)
    )
    if not mapping or not mapping[0]:
        raise HTTPException(status_code=400, detail="This mission has no linked Brightspace grade item yet")
    grade_item_id = mapping[0]

    token = await _get_service_token()
    if not token:
        raise HTTPException(status_code=400, detail="No Brightspace connection yet -- click \"Connect Brightspace\" first")
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No OAuth login provider configured")
    try:
        grade_values = await provider.list_grade_values(token, grade_item_id)
    except OAuthLoginError as e:
        raise HTTPException(status_code=502, detail=str(e))

    synced = []
    skipped = []
    for gv in (grade_values or []):
        # Real shape confirmed live 2026-07-20 (see list_grade_values's own
        # comment): each row is {"User": {"Identifier": "<id>", ...},
        # "GradeValue": {...} | null} -- there's no top-level "UserId"/
        # "PointsNumerator" at all, which is what the previous version of
        # this loop assumed and crashed on the first real run.
        user = gv.get("User") or {}
        bs_user_id_raw = user.get("Identifier")
        if bs_user_id_raw is None:
            continue
        bs_user_id = int(bs_user_id_raw)
        grade_value = gv.get("GradeValue")
        if grade_value is None:
            # Enrolled but not yet graded (real, unremarkable case -- two of
            # three rows in the first live test were exactly this).
            continue
        evoke_row = db_fetch_one(
            "SELECT user_id FROM evoke_identities WHERE brightspace_user_id = %s", (bs_user_id,)
        )
        if not evoke_row:
            skipped.append(bs_user_id)
            continue
        evoke_user_id = evoke_row[0]
        grade = grade_value.get("PointsNumerator")
        comments = grade_value.get("Comments") or {}
        # Confirmed live: an instructor grading through Brightspace's rich-text
        # feedback field leaves Comments.Text empty and puts the real content
        # in Comments.Html -- preferring Text alone silently drops it.
        feedback = (comments.get("Text") or "").strip()
        if not feedback and comments.get("Html"):
            feedback = re.sub(r"<[^>]+>", "", comments["Html"]).strip()
        submission_row = db_fetch_one(
            """SELECT id FROM submissions WHERE user_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product'
               ORDER BY submitted_at DESC LIMIT 1""",
            (evoke_user_id, mission_id)
        )
        if not submission_row:
            skipped.append(bs_user_id)
            continue
        db_execute(
            """UPDATE submissions SET grade = %s, feedback = %s, graded_at = CURRENT_TIMESTAMP, status = 'graded'
               WHERE id = %s::uuid""",
            (grade, feedback, submission_row[0])
        )
        synced.append(str(evoke_user_id))

    return {"status": "ok", "synced": synced, "skipped_no_match": skipped}


class MissionUpdateRequest(BaseModel):
    arc: Optional[str] = None
    superpower: Optional[str] = None
    primary_skill: Optional[str] = None
    secondary_skill: Optional[str] = None
    pfl_domain: Optional[str] = None
    week: Optional[int] = None
    sequence: Optional[int] = None
    mission_brief_md: Optional[str] = None
    pbl_description: Optional[str] = None
    evidence_requirements_md: Optional[str] = None


@app.put("/api/admin/missions/{mission_id}")
async def admin_update_mission(mission_id: str, body: MissionUpdateRequest, admin_id: str = Depends(get_current_admin)):
    """Hand-edit a mission's Evoke-only curriculum fields. Pure Postgres
    write, no Brightspace call. COALESCE makes this a partial update --
    any field the admin's form didn't send is left unchanged."""
    try:
        db_execute(
            """UPDATE missions SET
                   arc = COALESCE(%s, arc),
                   superpower = COALESCE(%s, superpower),
                   primary_skill = COALESCE(%s, primary_skill),
                   secondary_skill = COALESCE(%s, secondary_skill),
                   pfl_domain = COALESCE(%s, pfl_domain),
                   week = COALESCE(%s, week),
                   sequence = COALESCE(%s, sequence),
                   mission_brief_md = COALESCE(%s, mission_brief_md),
                   pbl_description = COALESCE(%s, pbl_description),
                   evidence_requirements_md = COALESCE(%s, evidence_requirements_md)
               WHERE id = %s::uuid""",
            (
                body.arc, body.superpower, body.primary_skill, body.secondary_skill,
                body.pfl_domain, body.week, body.sequence, body.mission_brief_md,
                body.pbl_description, body.evidence_requirements_md, mission_id,
            )
        )
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Admin: Dev User Reset ==========
# Two seeded local-dev learner accounts (evoke-infra/seed.py) exist so a
# real Brightspace-connected cohort's shape -- a team of players plus an
# admin -- is testable without a live tenant: the team-evidence AND-gate
# (shared submission + each member's own reflection, _complete_mission_for_user
# below) genuinely needs two distinct people, not one account playing both
# parts. Hard-safelisted by email so this can never reach a real
# Brightspace-identified learner's data, even if called with their email by
# mistake -- these two rows only ever exist because seed.py created them.
DEV_USER_EMAILS = {"player1@evoke.local", "player2@evoke.local"}


def _recompute_team_profile(team_id: str):
    """team-profile (workers.py's PROFILE WORKER) accumulates XP/badges
    per-event with no per-member subtraction possible -- there's no "undo
    this member's contribution" operation on a running total. Rebuilt here
    from scratch by summing every current member's own player-profile doc
    instead, which is exactly what the accumulation was supposed to add up
    to in the first place."""
    member_rows = db_fetch_all("SELECT user_id FROM team_members WHERE team_id = %s::uuid", (team_id,))
    xp_total = 0
    missions_completed = set()
    quests_completed_count = 0
    member_badges = {}
    for (uid,) in member_rows:
        uid = str(uid)
        try:
            profile = os_client.get(index="player-profile", id=uid)["_source"]
        except Exception:
            continue
        xp_total += profile.get("xp", 0)
        missions_completed.update(profile.get("missions_completed", []))
        quests_completed_count += len(profile.get("quests_completed", []))
        earned = {k: True for k, v in profile.get("badges", {}).items() if v.get("earned")}
        if earned:
            member_badges[uid] = earned
    os_client.index(index="team-profile", id=team_id, body={
        "team_id": team_id, "xp_total": xp_total,
        "missions_completed": sorted(missions_completed),
        "quests_completed_count": quests_completed_count,
        "member_badges": member_badges,
        "updated_at": datetime.datetime.now().isoformat(),
    }, refresh=True)


@app.get("/api/admin/dev-users")
async def admin_list_dev_users(admin_id: str = Depends(get_current_admin)):
    """The two seeded dev accounts, with just enough current state (XP,
    missions completed, open submissions) for the admin dashboard's Reset
    button to show what a reset would actually clear."""
    out = []
    for email in sorted(DEV_USER_EMAILS):
        row = db_fetch_one("SELECT id, display_name FROM users WHERE email = %s", (email,))
        if not row:
            out.append({"email": email, "exists": False})
            continue
        user_id, display_name = str(row[0]), row[1]
        try:
            profile = os_client.get(index="player-profile", id=user_id)["_source"]
        except Exception:
            profile = {}
        submission_count = db_fetch_one(
            "SELECT COUNT(*) FROM submissions WHERE user_id = %s::uuid", (user_id,)
        )[0]
        team_row = db_fetch_one(
            "SELECT t.name FROM team_members tm JOIN teams t ON t.id = tm.team_id WHERE tm.user_id = %s::uuid",
            (user_id,)
        )
        out.append({
            "email": email, "exists": True, "user_id": user_id, "display_name": display_name,
            "team_name": team_row[0] if team_row else None,
            "xp": profile.get("xp", 0), "level": profile.get("level", 1),
            "missions_completed": len(profile.get("missions_completed", [])),
            "submissions": submission_count,
        })
    return {"dev_users": out}


async def _reset_dev_user(email: str) -> dict:
    if email not in DEV_USER_EMAILS:
        raise HTTPException(status_code=400, detail=f"Not a resettable dev user: {email}")
    row = db_fetch_one("SELECT id FROM users WHERE email = %s", (email,))
    if not row:
        raise HTTPException(status_code=404, detail=f"Dev user {email} not found -- run seed.py first")
    user_id = str(row[0])

    # Every table a player's own activity could have written a row to.
    # Team membership/identity itself is deliberately untouched -- a reset
    # clears progress, not who this account is or which team it's on.
    db_execute("DELETE FROM peer_insights_given WHERE from_user_id = %s::uuid OR target_user_id = %s::uuid", (user_id, user_id))
    db_execute("DELETE FROM notifications WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM awards WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM mission_reflections WHERE user_id = %s::uuid", (user_id,))
    # Shared team evidence, not just this user's own reflection -- if this
    # account submitted the team's evidence for a mission, resetting it
    # removes that mission's evidence for the whole team, same as it would
    # in reality if the work simply hadn't happened yet.
    db_execute("DELETE FROM submissions WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM mc_quest_submissions WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM mc_quest_completions WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM mc_reward_grants WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM billbot_chat_log WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM minigame_scores WHERE user_id = %s::uuid", (user_id,))
    db_execute("DELETE FROM checkins WHERE user_id = %s::uuid", (user_id,))

    # OpenSearch: player-profile/learner-timeline accumulate from events and
    # never get recomputed from Postgres -- clearing the rows above alone
    # leaves XP/level/badges/timeline stale.
    try:
        os_client.delete(index="player-profile", id=user_id)
    except Exception:
        pass
    try:
        os_client.delete_by_query(index="learner-timeline", body={"query": {"term": {"learner_id": user_id}}})
    except Exception:
        pass

    for (team_id,) in db_fetch_all("SELECT team_id FROM team_members WHERE user_id = %s::uuid", (user_id,)):
        _recompute_team_profile(str(team_id))

    return {"status": "reset", "email": email, "user_id": user_id}


@app.post("/api/admin/dev-users/{email}/reset")
async def admin_reset_dev_user(email: str, admin_id: str = Depends(get_current_admin)):
    """Wipes one seeded dev-login learner's progress -- evidence, reflections,
    XP, badges, chat, checkins, quest completions -- back to a fresh account,
    so the same two accounts can be reused for repeated local testing without
    a database rebuild. Team assignment and identity are left alone; only
    activity is cleared."""
    return await _reset_dev_user(email)


@app.post("/api/admin/dev-users/reset-all")
async def admin_reset_all_dev_users(admin_id: str = Depends(get_current_admin)):
    """Both seeded dev accounts at once -- the common case when a
    team-evidence test run (both members' submission + reflection) needs a
    clean slate."""
    results = []
    for email in sorted(DEV_USER_EMAILS):
        if db_fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
            results.append(await _reset_dev_user(email))
    return {"results": results}


# ========== Evidence Submission ==========
def _get_user_team(user_id: str) -> Optional[str]:
    """A learner belongs to exactly one team (see the admin roster/team
    endpoints) -- this is the single lookup everything in the
    team-evidence-submission flow resolves "current team" through."""
    row = db_fetch_one("SELECT team_id FROM team_members WHERE user_id = %s::uuid LIMIT 1", (user_id,))
    return str(row[0]) if row else None


def _team_member_ids(team_id: str) -> List[str]:
    rows = db_fetch_all("SELECT user_id FROM team_members WHERE team_id = %s::uuid", (team_id,))
    return [str(r[0]) for r in rows]


async def _complete_mission_for_user(user_id: str, mission_id: str, team_id: str):
    """The AND-gate: fires the one-time completion effects (award, XP,
    MissionCompleted, stage completion, Power/Quality unlocks, notification)
    only once BOTH the team's shared evidence exists for this mission AND
    this specific member has submitted their own reflection. Safe to call
    speculatively from either submit-evidence (evidence just landed) or
    submit-reflection (a reflection just landed) -- checks its own
    already-completed guard first, so calling it when the gate isn't
    closed, or when it's already closed, are both safe no-ops."""
    already = db_fetch_one(
        "SELECT 1 FROM awards WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = 'common' AND source = 'submission'",
        (user_id, mission_id)
    )
    if already:
        return

    # team_product: any teammate's shared submission satisfies this half of
    # the gate for everyone (unchanged, existing behavior). individual_evidence
    # (Field Tablet, no team artifact concept): only THIS user's own
    # submission counts -- reusing team_product's team-wide check here would
    # let one teammate's Field Tablet submission silently complete another's
    # gate despite them never submitting anything themselves.
    evidence = db_fetch_one(
        """SELECT 1 FROM submissions
           WHERE mission_id = %s::uuid
             AND ((kind = 'team_product' AND team_id = %s::uuid)
               OR (kind = 'individual_evidence' AND user_id = %s::uuid))
           LIMIT 1""",
        (mission_id, team_id, user_id)
    )
    reflected = db_fetch_one(
        "SELECT 1 FROM mission_reflections WHERE user_id = %s::uuid AND mission_id = %s::uuid LIMIT 1",
        (user_id, mission_id)
    )
    if not evidence or not reflected:
        return  # gate not closed yet

    # Grant common tier award locally
    award_id = str(uuid.uuid4())
    db_execute(
        """INSERT INTO awards (id, user_id, mission_id, tier, source, awarded_at)
           VALUES (%s::uuid, %s::uuid, %s::uuid, 'common', 'submission', CURRENT_TIMESTAMP)
           ON CONFLICT (user_id, mission_id, tier, source) DO NOTHING""",
        (award_id, user_id, mission_id)
    )

    # Publish AwardGranted event
    await publish_event("AwardGranted", {
        "award_id": award_id,
        "user_id": user_id,
        "mission_id": mission_id,
        "tier": "common",
        "source": "submission"
    })

    # Team evidence + your own reflection is what "completes" a mission for
    # badge/count purposes -- later AI/teacher award tiers (the AI COACH
    # WORKER's epic-tier upgrade in workers.py, brightspace_review) are
    # quality upgrades on an already-completed mission, not separate
    # completions, so MissionCompleted/BadgeAwarded only fire here.
    await publish_event("MissionCompleted", {
        "user_id": user_id,
        "mission_id": mission_id
    })

    # XP value is a placeholder (matches overview.md's example table) —
    # GAPS.md flags the real XP economy as still undecided.
    await publish_event("XPGranted", {
        "user_id": user_id,
        "amount": 100,
        "reason": "mission_completed",
        "mission_id": mission_id
    })

    # Achievements are Power-level (GAME_DESIGN.md §4.1), not just the 4
    # Quality badges: each of the mission's Primary/Secondary tags
    # resolves (via skills_framework.resolve_power, which also handles
    # the 3 non-canonical mission-tag terms) to one of the 16 real
    # Powers, and a Quality badge only "earns" once all 4 of its
    # constituent Powers are unlocked. Route by the Power's own Table 1
    # Quality, never the mission's labeled `superpower` field — those
    # disagree in real cases (e.g. mission-09's primary tag, Courage, is
    # a Creative Visionary Power despite that mission being headlined
    # "Empathetic Changemaker").
    # Stage completion (BUILD_PLAN_2 §3): if this closed out the user's
    # stage ring, say so everywhere — the chapter-level celebration
    # GAPS.md flags as missing. Keyed on real completion (an award exists)
    # now, not just evidence existing somewhere.
    stage_row = db_fetch_one("SELECT stage, week FROM missions WHERE id = %s::uuid", (mission_id,))
    if stage_row:
        the_stage = stage_row[0] or stage_row[1] or 1
        remaining = db_fetch_one(
            """SELECT COUNT(*) FROM missions m
               WHERE COALESCE(m.stage, m.week, 1) = %s
                 AND m.campaign_id = (SELECT campaign_id FROM missions WHERE id = %s::uuid)
                 AND NOT EXISTS (SELECT 1 FROM awards a
                                 WHERE a.user_id = %s::uuid AND a.mission_id = m.id AND a.source = 'submission')""",
            (the_stage, mission_id, user_id)
        )
        if remaining and remaining[0] == 0:
            await publish_event("StageCompleted", {
                "user_id": user_id, "stage": the_stage,
            })

    mission_tags = db_fetch_one(
        "SELECT primary_skill, secondary_skill FROM missions WHERE id = %s::uuid", (mission_id,)
    )
    if mission_tags:
        for raw_tag, tag_type in [(mission_tags[0], "primary"), (mission_tags[1], "secondary")]:
            power_key = skills_framework.resolve_power(raw_tag)
            if not power_key:
                continue
            await publish_event("BadgeAwarded", {
                "user_id": user_id,
                "badge_key": skills_framework.POWER_TO_QUALITY[power_key],
                "power_key": power_key,
                "tag_type": tag_type,
                "mission_id": mission_id
            })

    # Create notification
    notification_id = str(uuid.uuid4())
    award_id_from_db = db_fetch_one(
        "SELECT id FROM awards WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = 'common' AND source = 'submission' LIMIT 1",
        (user_id, mission_id)
    )[0]

    db_execute(
        "INSERT INTO notifications (id, user_id, award_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
        (notification_id, user_id, award_id_from_db)
    )


async def _submit_evidence_core(user_id: str, mission_id: str, kind: str, filename: str, file_bytes: bytes, content_type: Optional[str]) -> dict:
    """The one real evidence-submission path -- same DB writes, same S3
    put, same Kafka event, same completion gate, regardless of caller.
    /api/submit-evidence (desktop) and the Field Tablet's Mission Evidence
    flow (evoke-web PDF built from a photo+observation) both call this
    directly, so there is no separate mobile pipeline to drift out of sync.

    `kind='team_product'` is the TEAM's shared artifact -- any member can
    call it, and it closes the completion AND-gate (see
    _complete_mission_for_user) for any teammate who already reflected.
    `kind='individual_task'` is a learner's own piece (Submission Redesign
    doc, missions 1-4): stored + hash-recorded for the roster/assessment,
    but it does not fire team-completion effects.
    `kind='individual_evidence'` (Field Tablet, 2026-07-21) is one
    learner's own submission for an individually-graded assignment -- no
    team artifact concept at all. Resubmission-guarded and gate-checked
    per (user_id, mission_id), not per team, so one teammate's Field
    Tablet submission can never silently satisfy another's gate the way
    reusing team_product would have."""
    if kind not in ("team_product", "individual_task", "individual_evidence"):
        raise HTTPException(status_code=400, detail="kind must be 'team_product', 'individual_task', or 'individual_evidence'")

    mission_release = db_fetch_one(
        "SELECT released_at FROM missions WHERE id = %s::uuid", (mission_id,)
    )
    if not mission_release or mission_release[0] is None:
        # Real gating, not just a UI hint -- a locked mission's evidence
        # form is hidden client-side too (screens.js), but this is the
        # enforcement that actually matters. See GAPS.md's resolved
        # "mission ordering" item: admin-release, not order-of-completion.
        raise HTTPException(status_code=403, detail="This mission hasn't been released yet")

    team_id = _get_user_team(user_id)
    if not team_id:
        raise HTTPException(status_code=400, detail="You're not on a team yet -- ask your teacher to add you to a group in Brightspace")

    submission_id = str(uuid.uuid4())

    # Revise-and-resubmit is a first-class path (GAPS.md #3): a later
    # submission re-runs the AI review (which can upgrade the award tier)
    # but must NOT re-fire the one-time completion effects for anyone
    # already completed -- previously every resubmission re-published
    # MissionCompleted/XPGranted/BadgeAwarded and duplicate AwardGranted
    # feed events, which both spammed the feed and made resubmission an
    # infinite +100 XP faucet.
    # team_product's guard is scoped to the TEAM (any member's earlier
    # submission counts); individual_evidence's is scoped to THIS user --
    # each learner has their own first-submission guard, since there's no
    # shared artifact. individual_task never resubmission-guards (it
    # doesn't gate anything to begin with).
    if kind == "team_product":
        prior = db_fetch_one(
            "SELECT 1 FROM submissions WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product' LIMIT 1",
            (team_id, mission_id)
        )
    elif kind == "individual_evidence":
        prior = db_fetch_one(
            "SELECT 1 FROM submissions WHERE user_id = %s::uuid AND mission_id = %s::uuid AND kind = 'individual_evidence' LIMIT 1",
            (user_id, mission_id)
        )
    else:
        prior = None
    is_resubmission = bool(prior)

    # The AI Coach worker actually reads this file (evoke/workers.py's
    # PdfReader(...) on EvidenceSubmitted/TeamEvidenceSubmitted) -- a
    # non-PDF used to sail through here, then fail silently downstream with
    # a broken "Error parsing document" string sent to learners as if it
    # were real AI feedback (confirmed live). Reject it here instead, where
    # the uploader gets an actual error message. individual_task files are
    # never AI-parsed, so they aren't restricted.
    if kind in ("team_product", "individual_evidence"):
        try:
            PdfReader(BytesIO(file_bytes))
        except PdfReadError:
            raise HTTPException(status_code=400, detail="Evidence must be a PDF")

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    object_key = f"evoke-evidence/{mission_id}/{kind}/{user_id}_{filename}"
    s3_client.put_object(
        Bucket="default-bucket",
        Key=object_key,
        Body=file_bytes,
        ContentType=content_type or "application/octet-stream"
    )

    # Create submission record. content_hash lets the roster flag whether
    # each member turned in the SAME team file (Option A hash-check) --
    # only meaningful for team_product; individual_evidence rows are never
    # compared against each other this way.
    db_execute(
        """INSERT INTO submissions (id, user_id, mission_id, team_id, file_path, status, kind, content_hash)
           VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'submitted', %s, %s)""",
        (submission_id, user_id, mission_id, team_id, object_key, kind, content_hash)
    )

    # An individual task is a learner's own piece -- store it and stop.
    # No Brightspace team sync, no AI team review, no completion effects.
    if kind == "individual_task":
        return {"status": "success", "submission_id": submission_id, "kind": kind}

    # Brightspace sync (real adapter or simulator fallback) is no longer
    # inline here -- it used to be a live network round-trip blocking
    # this request's response. It's now event-based: the
    # TeamEvidenceSubmitted publish just below is consumed by
    # workers.py's BRIGHTSPACE SUBMISSION WORKER, which does the exact
    # same real/simulator push this block used to do, off the request
    # path. See BRIGHTSPACE.md.
    # individual_evidence fans out to just the submitter -- same event
    # type and shape as team_product (workers.py doesn't branch on kind,
    # only on the team_members list it's handed), just a roster of one.
    team_members = [user_id] if kind == "individual_evidence" else _team_member_ids(team_id)

    # Publish TeamEvidenceSubmitted (fans out AI-coach feedback to every
    # member independently -- see workers.py's AI COACH WORKER, which
    # already expected this event and just needed a real publisher).
    await publish_event("TeamEvidenceSubmitted", {
        "submission_id": submission_id,
        "user_id": user_id,
        "team_id": team_id,
        "team_members": team_members,
        "mission_id": mission_id,
        "object_key": object_key,
        "filename": filename
    })

    # AI review is event-based now, not an inline blocking call here --
    # the TeamEvidenceSubmitted event published just above is already
    # consumed by workers.py's AI COACH WORKER, which grants the epic-
    # tier award itself once its own AI pass completes (same worker
    # that already fetches the real file and extracts real text, so
    # this also removes what used to be a second, redundant OpenWebUI
    # call that only ever got a filename, not the actual content).
    # This request no longer blocks on an AI call that measured up to
    # ~90s cold -- resubmission and first-time paths both just return
    # once the event's published; the upgrade lands async, same as
    # every other award in this app.
    if is_resubmission:
        return {"status": "success", "submission_id": submission_id, "resubmission": True}

    # Evidence alone doesn't complete anyone's mission -- only close the
    # gate for teammates who already reflected before this landed.
    # Teammates who haven't reflected yet complete later, from
    # submit-reflection, when they do. (For individual_evidence,
    # team_members is just [user_id], so this only ever checks the
    # submitter's own gate.)
    for member_id in team_members:
        await _complete_mission_for_user(member_id, mission_id, team_id)

    return {
        "status": "success",
        "submission_id": submission_id,
        "resubmission": False
    }


@app.post("/api/submit-evidence")
async def submit_evidence(
    mission_id: str = Form(...),
    file: UploadFile = File(...),
    kind: str = Form("team_product"),
    user_id: str = Depends(get_current_user),
):
    """Submit evidence for a mission -- see _submit_evidence_core for the
    real logic; this route just adapts the HTTP layer to it."""
    try:
        file_bytes = await file.read()
        return await _submit_evidence_core(user_id, mission_id, kind, file.filename, file_bytes, file.content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit evidence error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def _initials(name: Optional[str]) -> str:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@app.get("/api/submission-state/{user_id}/{mission_id}")
async def submission_state(mission_id: str, user_id: str = Depends(require_self)):
    """Per-member submission state for the requesting learner's team on one
    mission -- drives the submission screen's roster strip, the motivational
    banner, and completion status. Team-product files are hash-checked
    (Option A): the most-common hash is 'canonical'; members matching it are
    'matching', a different file is 'divergent', none is 'missing'."""
    try:
        team_id = _get_user_team(user_id)
        if not team_id:
            return {"team_id": None, "members": [], "you": None,
                    "banner": {"show": False, "submitted": 0, "total": 0}, "canonical_hash": None}

        members = db_fetch_all(
            """SELECT u.id, u.display_name FROM team_members tm
               JOIN users u ON u.id = tm.user_id
               WHERE tm.team_id = %s::uuid ORDER BY u.display_name""",
            (team_id,)
        )
        # team-product submissions (latest hash per member) for this mission
        prod = db_fetch_all(
            """SELECT DISTINCT ON (user_id) user_id, content_hash
               FROM submissions
               WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product'
               ORDER BY user_id, submitted_at DESC""",
            (team_id, mission_id)
        )
        product_hash = {str(r[0]): r[1] for r in prod}
        indiv = {str(r[0]) for r in db_fetch_all(
            "SELECT DISTINCT user_id FROM submissions WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'individual_task'",
            (team_id, mission_id))}
        reflected = {str(r[0]) for r in db_fetch_all(
            "SELECT user_id FROM mission_reflections WHERE mission_id = %s::uuid", (mission_id,))}
        discussed = {str(r[0]) for r in db_fetch_all(
            "SELECT DISTINCT user_id FROM team_discussion WHERE team_id = %s::uuid AND mission_id = %s::uuid",
            (team_id, mission_id))}

        # canonical = most common team-product hash
        counts: dict = {}
        for h in product_hash.values():
            if h:
                counts[h] = counts.get(h, 0) + 1
        canonical = max(counts, key=counts.get) if counts else None

        def product_status(uid: str) -> str:
            if uid not in product_hash:
                return "missing"
            return "matching" if product_hash[uid] == canonical else "divergent"

        out_members = []
        for mid, name in members:
            mid = str(mid)
            out_members.append({
                "user_id": mid,
                "display_name": name,
                "initials": _initials(name),
                "is_you": mid == user_id,
                "individual_task": mid in indiv,
                "team_product": product_status(mid),
                "reflected": mid in reflected,
                "discussed": mid in discussed,
            })

        you = next((m for m in out_members if m["is_you"]), None)
        submitted = sum(1 for m in out_members if m["team_product"] != "missing")
        total = len(out_members)
        banner_show = bool(you and you["team_product"] == "missing" and submitted >= 1)

        return {
            "team_id": team_id,
            "mission_id": mission_id,
            "canonical_hash": canonical,
            "you": you,
            "members": out_members,
            "banner": {"show": banner_show, "submitted": submitted, "total": total},
        }
    except Exception as e:
        logger.error(f"submission-state error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class TeamDiscussionPost(BaseModel):
    user_id: str
    mission_id: str
    message: str


@app.post("/api/team-discussion")
async def post_team_discussion(body: TeamDiscussionPost, caller: str = Depends(get_current_user)):
    """Add a message to the team's in-app discussion thread for a mission."""
    if body.user_id != caller:
        raise HTTPException(status_code=403, detail="Cannot post as another user")
    try:
        msg = (body.message or "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Message can't be empty")
        team_id = _get_user_team(body.user_id)
        if not team_id:
            raise HTTPException(status_code=400, detail="You're not on a team yet")
        mid = str(uuid.uuid4())
        db_execute(
            """INSERT INTO team_discussion (id, team_id, mission_id, user_id, message)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s)""",
            (mid, team_id, body.mission_id, body.user_id, msg[:4000])
        )
        return {"status": "success", "id": mid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"team-discussion post error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/team-discussion/{user_id}/{mission_id}")
async def get_team_discussion(mission_id: str, user_id: str = Depends(require_self)):
    """The team's discussion thread for a mission (resolved via the caller's team)."""
    try:
        team_id = _get_user_team(user_id)
        if not team_id:
            return {"team_id": None, "messages": []}
        rows = db_fetch_all(
            """SELECT d.user_id, u.display_name, d.message, d.created_at
               FROM team_discussion d JOIN users u ON u.id = d.user_id
               WHERE d.team_id = %s::uuid AND d.mission_id = %s::uuid
               ORDER BY d.created_at ASC""",
            (team_id, mission_id)
        )
        return {"team_id": team_id, "messages": [{
            "user_id": str(r[0]), "display_name": r[1], "initials": _initials(r[1]),
            "message": r[2], "created_at": r[3].isoformat() if r[3] else None,
            "is_you": str(r[0]) == user_id,
        } for r in rows]}
    except Exception as e:
        logger.error(f"team-discussion get error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/team/{user_id}")
async def get_team(user_id: str = Depends(require_self)):
    """The Team page: team name/motto + each member with their mission progress."""
    try:
        team_id = _get_user_team(user_id)
        if not team_id:
            return {"team_id": None, "name": None, "motto": None, "members": []}
        row = db_fetch_one("SELECT name, motto FROM teams WHERE id = %s::uuid", (team_id,))
        name = row[0] if row else "Your Team"
        motto = row[1] if row else None
        member_rows = db_fetch_all(
            """SELECT u.id, u.display_name FROM team_members tm
               JOIN users u ON u.id = tm.user_id
               WHERE tm.team_id = %s::uuid ORDER BY u.display_name""",
            (team_id,)
        )
        members = []
        for mid, dname in member_rows:
            mid = str(mid)
            done, lvl = 0, 1
            try:
                prof = os_client.get(index="player-profile", id=mid)["_source"]
                done = len(prof.get("missions_completed", []))
                lvl = prof.get("level", 1)
            except Exception:
                pass
            members.append({
                "user_id": mid, "display_name": dname, "initials": _initials(dname),
                "missions_completed": done, "level": lvl, "is_you": mid == user_id,
            })
        return {"team_id": team_id, "name": name, "motto": motto, "members": members}
    except Exception as e:
        logger.error(f"get-team error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class TeamMessagePost(BaseModel):
    user_id: str
    message: str


@app.post("/api/team-message")
async def post_team_message(body: TeamMessagePost, caller: str = Depends(get_current_user)):
    """Post to the team-wide message board (not tied to a mission)."""
    if body.user_id != caller:
        raise HTTPException(status_code=403, detail="Cannot post as another user")
    try:
        msg = (body.message or "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Message can't be empty")
        team_id = _get_user_team(body.user_id)
        if not team_id:
            raise HTTPException(status_code=400, detail="You're not on a team yet")
        mid = str(uuid.uuid4())
        db_execute(
            "INSERT INTO team_messages (id, team_id, user_id, message) VALUES (%s::uuid, %s::uuid, %s::uuid, %s)",
            (mid, team_id, body.user_id, msg[:4000])
        )
        return {"status": "success", "id": mid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"team-message post error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/team-messages/{user_id}")
async def get_team_messages(user_id: str = Depends(require_self)):
    """The team-wide message board thread."""
    try:
        team_id = _get_user_team(user_id)
        if not team_id:
            return {"team_id": None, "messages": []}
        rows = db_fetch_all(
            """SELECT m.user_id, u.display_name, m.message, m.created_at
               FROM team_messages m JOIN users u ON u.id = m.user_id
               WHERE m.team_id = %s::uuid ORDER BY m.created_at ASC LIMIT 200""",
            (team_id,)
        )
        return {"team_id": team_id, "messages": [{
            "user_id": str(r[0]), "display_name": r[1], "initials": _initials(r[1]),
            "message": r[2], "created_at": r[3].isoformat() if r[3] else None,
            "is_you": str(r[0]) == user_id,
        } for r in rows]}
    except Exception as e:
        logger.error(f"team-messages get error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


async def _submit_reflection_core(user_id: str, mission_id: str, reflection: str) -> dict:
    """An individual team member's own reflection on a mission -- always
    personal, always available regardless of who submitted the team's
    evidence. Closes the completion AND-gate for this one user once their
    half of the evidence check (team or individual, see
    _complete_mission_for_user) already exists. Shared by
    /api/submit-reflection and the Field Tablet's Mission Evidence flow, so
    there's no separate mobile reflection path."""
    mission_release = db_fetch_one(
        "SELECT released_at FROM missions WHERE id = %s::uuid", (mission_id,)
    )
    if not mission_release or mission_release[0] is None:
        raise HTTPException(status_code=403, detail="This mission hasn't been released yet")

    team_id = _get_user_team(user_id)
    if not team_id:
        raise HTTPException(status_code=400, detail="You're not on a team yet -- ask your teacher to add you to a group in Brightspace")

    db_execute(
        """INSERT INTO mission_reflections (user_id, mission_id, team_id, reflection)
           VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
           ON CONFLICT (user_id, mission_id) DO UPDATE SET reflection = EXCLUDED.reflection""",
        (user_id, mission_id, team_id, reflection)
    )

    await _complete_mission_for_user(user_id, mission_id, team_id)

    return {"status": "success"}


@app.post("/api/submit-reflection")
async def submit_reflection(
    mission_id: str = Form(...),
    reflection: str = Form(...),
    user_id: str = Depends(get_current_user),
):
    """Submit a reflection -- see _submit_reflection_core for the real
    logic; this route just adapts the HTTP layer to it."""
    try:
        return await _submit_reflection_core(user_id, mission_id, reflection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit reflection error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# AI review moved to workers.py's AI COACH WORKER (event-driven, consumes
# the TeamEvidenceSubmitted event already published above) -- see that
# file for the epic-tier award-granting logic that used to live here.

# ========== Teacher Review Webhook ==========
@app.post("/api/webhooks/brightspace/review")
async def brightspace_review(
    submission_id: str,
    brightspace_user_id: int,
    assignment_id: str,
    rating: str = "epic"
):
    """Webhook from Brightspace (sim or real) when a teacher grades a
    submission. Takes Brightspace-native identifiers only -- a real
    Brightspace webhook would never know EVOKE's internal UUIDs, so they're
    resolved here rather than expected from the caller. (Previously this
    endpoint took EVOKE's own user_id/mission_id directly, which nothing
    could actually have supplied -- brightspace-sim's grading endpoint never
    called this webhook at all until now.)"""
    try:
        identity = db_fetch_one(
            "SELECT user_id FROM evoke_identities WHERE brightspace_user_id = %s", (brightspace_user_id,)
        )
        if not identity:
            raise HTTPException(status_code=404, detail=f"No EVOKE identity linked to Brightspace user {brightspace_user_id}")
        user_id = str(identity[0])

        mission_row = db_fetch_one(
            "SELECT id FROM missions WHERE lms_assignment_ref = %s", (assignment_id,)
        )
        if not mission_row:
            raise HTTPException(status_code=404, detail=f"No mission synced for assignment {assignment_id}")
        mission_id = str(mission_row[0])

        # Determine tier based on rating
        tier = "legendary" if rating == "legendary" else "epic"

        award_id = str(uuid.uuid4())
        db_execute(
            """INSERT INTO awards (id, user_id, mission_id, tier, source, awarded_at)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'teacher_review', CURRENT_TIMESTAMP)
               ON CONFLICT (user_id, mission_id, tier, source) DO NOTHING""",
            (award_id, user_id, mission_id, tier)
        )

        # Publish event
        await publish_event("TeacherReviewed", {
            "submission_id": submission_id,
            "user_id": user_id,
            "mission_id": mission_id,
            "rating": rating
        })

        await publish_event("AwardGranted", {
            "award_id": award_id,
            "user_id": user_id,
            "mission_id": mission_id,
            "tier": tier,
            "source": "teacher_review"
        })

        # Create notification
        notification_id = str(uuid.uuid4())
        award_id_from_db = db_fetch_one(
            f"SELECT id FROM awards WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = %s AND source = 'teacher_review' LIMIT 1",
            (user_id, mission_id, tier)
        )[0]

        db_execute(
            "INSERT INTO notifications (id, user_id, award_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
            (notification_id, user_id, award_id_from_db)
        )

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== Notifications & Awards ==========
@app.get("/api/notifications/{user_id}")
async def get_notifications(user_id: str = Depends(require_self)):
    """Get notifications for a user"""
    try:
        notifications = db_fetch_all(
            """SELECT n.id, n.award_id, n.created_at, n.read_at
               FROM notifications n WHERE n.user_id = %s::uuid ORDER BY n.created_at DESC""",
            (user_id,)
        )

        result = []
        for notif in notifications:
            notif_id, award_id, created_at, read_at = notif
            result.append({
                "id": str(notif_id),
                "award_id": str(award_id) if award_id else None,
                "created_at": created_at.isoformat() if created_at else None,
                "read": read_at is not None
            })

        return {"notifications": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/guide-overlay/{user_id}")
async def get_guide_overlay(user_id: str = Depends(require_self)):
    """Console-player feedback (BUILD_PLAN_2's "Guide overlay" gap): the
    Xbox-button overlay pattern -- notifications, awards, presence, all from
    wherever you are, without leaving what you're doing. Aggregates three
    things that already had their own endpoints (pending awards, the link-
    confirm flow, the daily wisdom line) into one call so the bell can open
    an in-place panel instead of navigating to the Dossier."""
    try:
        pending = db_fetch_all(
            """SELECT a.id, a.tier, a.source, m.title
               FROM awards a JOIN missions m ON m.id = a.mission_id
               WHERE a.user_id = %s::uuid AND a.collected_at IS NULL
               ORDER BY a.awarded_at DESC""",
            (user_id,)
        )
        pending_awards = [{"id": str(a[0]), "tier": a[1], "source": a[2], "mission_title": a[3]} for a in pending]

        wisdom_row = db_fetch_one(
            "SELECT wisdom FROM daily_reflections WHERE user_id = %s::uuid ORDER BY reflection_date DESC LIMIT 1",
            (user_id,)
        )

        link_row = db_fetch_one(
            """SELECT code, minecraft_username FROM mc_link_codes
               WHERE user_id = %s::uuid AND status = 'matched' ORDER BY created_at DESC LIMIT 1""",
            (user_id,)
        )

        return {
            "pending_awards": pending_awards,
            "recent_wisdom": wisdom_row[0] if wisdom_row else None,
            "link_request": {"pending": True, "minecraft_username": link_row[1]} if link_row else {"pending": False},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/awards/{user_id}")
async def get_awards(user_id: str = Depends(require_self)):
    """Get all awards for a user"""
    try:
        awards = db_fetch_all(
            """SELECT a.id, a.mission_id, a.tier, a.source, a.awarded_at, a.collected_at
               FROM awards a WHERE a.user_id = %s::uuid ORDER BY a.awarded_at DESC""",
            (user_id,)
        )

        result = []
        for award in awards:
            award_id, mission_id, tier, source, awarded_at, collected_at = award
            result.append({
                "id": str(award_id),
                "mission_id": str(mission_id),
                "tier": tier,
                "source": source,
                "awarded_at": awarded_at.isoformat() if awarded_at else None,
                "collected_at": collected_at.isoformat() if collected_at else None
            })

        return {"awards": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/awards/{award_id}/collect")
async def collect_award(award_id: str, user_id: str = Depends(require_self)):
    """Collect an award - triggers Minecraft delivery"""
    try:
        # Update award with collected_at timestamp
        db_execute(
            "UPDATE awards SET collected_at = CURRENT_TIMESTAMP WHERE id = %s::uuid",
            (award_id,)
        )

        # Get award details
        award = db_fetch_one(
            "SELECT user_id, mission_id, tier FROM awards WHERE id = %s::uuid",
            (award_id,)
        )

        if award:
            award_user_id, mission_id, tier = award

            # Publish RewardCollected event
            await publish_event("RewardCollected", {
                "award_id": award_id,
                "user_id": str(award_user_id),
                "mission_id": str(mission_id),
                "tier": tier
            })

        return {"status": "collected"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== Profiles ==========
@app.get("/api/profile/player/{user_id}")
async def get_player_profile(user_id: str = Depends(require_self)):
    """Player profile. XP/level/badges/missions/quests come from the
    player-profile projection (built by the worker's PROFILE WORKER branch
    from MissionCompleted/BadgeAwarded/XPGranted/QuestCompleted). Awards are
    read directly from Postgres instead of duplicated into the projection —
    `awards` is already a properly indexed source-of-truth table and this is
    the same query GET /api/awards/{user_id} already uses; projecting it a
    second time would just be two places that can disagree about the same
    facts."""
    try:
        try:
            profile = os_client.get(index="player-profile", id=user_id)["_source"]
        except Exception:
            # No events yet for this learner — a valid empty state, not an error.
            profile = {"xp": 0, "level": 1, "missions_completed": [], "badges": {}, "quests_completed": []}

        user_row = db_fetch_one("SELECT display_name FROM users WHERE id = %s::uuid", (user_id,))
        minecraft_link = db_fetch_one(
            "SELECT minecraft_username FROM minecraft_links WHERE user_id = %s::uuid LIMIT 1", (user_id,)
        )

        awards = db_fetch_all(
            """SELECT a.id, a.mission_id, a.tier, a.source, a.awarded_at, a.collected_at
               FROM awards a WHERE a.user_id = %s::uuid ORDER BY a.awarded_at DESC""",
            (user_id,)
        )
        awards_list = [{
            "id": str(a[0]), "mission_id": str(a[1]), "tier": a[2], "source": a[3],
            "awarded_at": a[4].isoformat() if a[4] else None,
            "collected_at": a[5].isoformat() if a[5] else None,
        } for a in awards]

        missions_completed = profile.get("missions_completed", [])
        quests_completed = profile.get("quests_completed", [])

        return {
            "user_id": user_id,
            "display_name": user_row[0] if user_row else None,
            "minecraft_username": minecraft_link[0] if minecraft_link else None,
            "xp": profile.get("xp", 0),
            "level": profile.get("level", 1),
            "rank_title": progression.level_title(profile.get("level", 1)),
            "next_level_xp": progression.next_threshold(profile.get("xp", 0)),
            "next_rank_title": progression.level_title(profile.get("level", 1) + 1),
            "badges": profile.get("badges", {}),
            "missions_completed": missions_completed,
            "missions_completed_count": len(missions_completed),
            "quests_completed": quests_completed,
            "quests_completed_count": len(quests_completed),
            "awards": awards_list,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/achievements/{user_id}")
async def get_achievements(user_id: str = Depends(require_self)):
    """The 16 Powers as individually-unlockable achievements (GAME_DESIGN.md
    §4.1) -- canon's Profile-screen "Achievements" section, distinct from
    the 4 Quality badges. Merges the always-16 static framework (so unearned
    Powers still render, grouped correctly under their real Quality) with
    whatever's actually been earned in the player-profile projection's
    `badges.*.powers` sub-structure."""
    try:
        try:
            profile = os_client.get(index="player-profile", id=user_id)["_source"]
        except Exception:
            profile = {"badges": {}}

        badges = profile.get("badges", {})
        powers = {}
        for power_key, (quality, definition) in skills_framework.POWERS.items():
            earned_state = badges.get(quality, {}).get("powers", {}).get(power_key)
            powers[power_key] = {
                "quality": quality,
                "definition": definition,
                "earned": bool(earned_state and earned_state.get("earned")),
                "earned_at": earned_state.get("earned_at") if earned_state else None,
                "tag_type": earned_state.get("tag_type") if earned_state else None,
                "behavioral": power_key in skills_framework.BEHAVIORAL_POWERS,
            }

        qualities = {}
        for quality in skills_framework.QUALITIES:
            badge = badges.get(quality, {})
            qualities[quality] = {
                "earned": bool(badge.get("earned")),
                "powers_earned": badge.get("progress", 0),
                "powers_total": 4,
            }

        return {"user_id": user_id, "qualities": qualities, "powers": powers}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Test/debug: anonymous student report ==========
# Deliberately unauthenticated -- a shareable read-only report for one
# provided user_id, not gated behind require_self/get_current_user like
# every other route in this file. Same tradeoff as the pre-existing
# static/test-brightspace.html harness (its own backend routes are gone,
# see the comment above admin_link_brightspace_assignment's block), just a
# new instance of it: real grade/feedback/XP/Powers data for a real,
# specific student, visible to anyone who has this exact URL. Requested as
# a "vanilla test page," not part of the authenticated product surface --
# do not link this from anywhere a real student would find it.
@app.get("/api/test/students")
async def test_list_students():
    """Backs the report page's user picker -- every learner, not just the
    one currently in a browser session, since this page is meant to be
    usable for any student without needing their session cookie. Same
    no-auth tradeoff as the report endpoint below; deliberately excludes
    role='admin' rows (e.g. admin@evoke.local) since those aren't real
    students and have no missions/grades to show."""
    rows = db_fetch_all(
        "SELECT id, display_name, email FROM users WHERE role = 'learner' ORDER BY display_name"
    )
    return {"students": [{"id": str(r[0]), "display_name": r[1], "email": r[2]} for r in rows]}


@app.get("/api/test/student-report/{user_id}")
async def test_student_report(user_id: str):
    user_row = db_fetch_one("SELECT display_name, email FROM users WHERE id = %s::uuid", (user_id,))
    if not user_row:
        raise HTTPException(status_code=404, detail="No such user")
    display_name, email = user_row

    org_result = db_fetch_one(
        "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
        (user_id,)
    )
    campaign_id = org_result[0] if org_result else None

    try:
        profile = os_client.get(index="player-profile", id=user_id)["_source"]
    except Exception:
        profile = {"xp": 0, "level": 1, "badges": {}}

    team_id = _get_user_team(user_id)

    missions = []
    if campaign_id:
        rows = db_fetch_all(
            """SELECT id, title, week, arc, superpower FROM missions
               WHERE campaign_id = %s::uuid ORDER BY week, sequence""",
            (campaign_id,)
        )
        for mission_id, title, week, arc, superpower in rows:
            grade_row = db_fetch_one(
                """SELECT status, grade, feedback, graded_at, submitted_at FROM submissions
                   WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product'
                   ORDER BY submitted_at DESC LIMIT 1""",
                (team_id, mission_id)
            ) if team_id else None
            reflection_row = db_fetch_one(
                "SELECT reflection, submitted_at FROM mission_reflections WHERE user_id = %s::uuid AND mission_id = %s::uuid",
                (user_id, mission_id)
            )
            missions.append({
                "id": str(mission_id),
                "title": title,
                "week": week,
                "arc": arc,
                "superpower": superpower,
                "submission_status": grade_row[0] if grade_row else "not_started",
                "grade": grade_row[1] if grade_row else None,
                "feedback": grade_row[2] if grade_row else None,
                "graded_at": grade_row[3].isoformat() if grade_row and grade_row[3] else None,
                "submitted_at": grade_row[4].isoformat() if grade_row and grade_row[4] else None,
                "reflection": reflection_row[0] if reflection_row else None,
                "reflected_at": reflection_row[1].isoformat() if reflection_row and reflection_row[1] else None,
            })

    badges = profile.get("badges", {})
    powers = {}
    for power_key, (quality, definition) in skills_framework.POWERS.items():
        earned_state = badges.get(quality, {}).get("powers", {}).get(power_key)
        powers[power_key] = {
            "quality": quality,
            "definition": definition,
            "earned": bool(earned_state and earned_state.get("earned")),
        }
    qualities = {
        quality: {"earned": bool(badges.get(quality, {}).get("earned")),
                  "powers_earned": badges.get(quality, {}).get("progress", 0), "powers_total": 4}
        for quality in skills_framework.QUALITIES
    }

    return {
        "user_id": user_id,
        "display_name": display_name,
        "email": email,
        "xp": profile.get("xp", 0),
        "level": profile.get("level", 1),
        "rank_title": progression.level_title(profile.get("level", 1)),
        "qualities": qualities,
        "powers": powers,
        "missions": missions,
    }


@app.get("/api/profile/team/{team_id}")
async def get_team_profile(team_id: str):
    """Team profile. Aggregated from members' individual events (missions
    completed, XP, badges, quests) — there's no TeamEvidenceSubmitted event
    yet, since team-scoped submission isn't wired into /api/submit-evidence
    (see GAPS.md's "no team-level play" gap). The PROFILE WORKER rolls each
    completing member's contribution into their team's projection as a
    side effect of processing that member's own event."""
    try:
        try:
            team_profile = os_client.get(index="team-profile", id=team_id)["_source"]
        except Exception:
            team_profile = {"xp_total": 0, "missions_completed": [], "quests_completed_count": 0, "member_badges": {}}

        team_row = db_fetch_one("SELECT name FROM teams WHERE id = %s::uuid", (team_id,))
        members = db_fetch_all(
            """SELECT tm.user_id, u.display_name, tm.role_label, u.sigil, ml.minecraft_username
               FROM team_members tm JOIN users u ON u.id = tm.user_id
               LEFT JOIN minecraft_links ml ON ml.user_id = tm.user_id
               WHERE tm.team_id = %s::uuid""",
            (team_id,)
        )
        members_list = [{
            "user_id": str(m[0]), "display_name": m[1], "role_label": m[2],
            "sigil": json.loads(m[3]) if m[3] else None,
            "minecraft_username": m[4],
        } for m in members]
        missions_completed = team_profile.get("missions_completed", [])

        return {
            "team_id": team_id,
            "team_name": team_row[0] if team_row else None,
            "members": members_list,
            "missions_completed": missions_completed,
            "missions_completed_count": len(missions_completed),
            "quests_completed_count": team_profile.get("quests_completed_count", 0),
            "xp_total": team_profile.get("xp_total", 0),
            "member_badges": team_profile.get("member_badges", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Check-In & Activity Feed ==========
@app.post("/api/checkin")
async def checkin(user_id: str = Depends(require_self)):
    """Visiting the Operations Hub is itself a small, repeatable reward loop,
    not just a portal for submitting missions -- missions are paced weekly,
    so personal activity is otherwise sparse most days. One grant per
    calendar day per user (checkins.UNIQUE(user_id, checkin_date)) --
    non-punitive by construction: there's no streak counter here to break,
    just whether today's check-in has already happened. Publishes a real
    RewardCollected event, reusing the exact same tier-keyed RCON delivery
    pipeline mission awards use (a 'checkin' entry in mc_reward_catalog) --
    so opening the website is a genuine way to earn something in Minecraft,
    not just a cosmetic gesture."""
    try:
        already = db_fetch_one(
            "SELECT 1 FROM checkins WHERE user_id = %s::uuid AND checkin_date = CURRENT_DATE", (user_id,)
        )
        if already:
            return {"status": "already_checked_in"}

        db_execute(
            "INSERT INTO checkins (user_id, checkin_date) VALUES (%s::uuid, CURRENT_DATE) ON CONFLICT DO NOTHING",
            (user_id,)
        )

        await publish_event("XPGranted", {"user_id": user_id, "amount": 10, "reason": "checkin"})

        has_minecraft_link = db_fetch_one(
            "SELECT 1 FROM minecraft_links WHERE user_id = %s::uuid", (user_id,)
        )
        minecraft_reward = bool(has_minecraft_link)
        if minecraft_reward:
            await publish_event("RewardCollected", {
                "award_id": str(uuid.uuid4()),  # synthetic -- the bridge never looks up a real awards row for this
                "user_id": user_id,
                "mission_id": None,
                "tier": "checkin",
            })

        return {"status": "checked_in", "xp_granted": 10, "minecraft_reward": minecraft_reward}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/activity")
async def get_activity(limit: int = 30):
    """Class-wide activity stream -- the social layer GAPS.md flags as
    missing ("the game is single-player homework with better wallpaper").
    Reads the activity-feed OpenSearch index the ACTIVITY WORKER maintains
    from AwardGranted/QuestCompleted events across every learner, not just
    the caller."""
    try:
        result = os_client.search(
            index="activity-feed",
            body={"query": {"match_all": {}}, "sort": [{"timestamp": {"order": "desc"}}], "size": limit},
        )
        return {"activity": [hit["_source"] for hit in result["hits"]["hits"]]}
    except Exception:
        return {"activity": []}


# ========== Submissions ==========
@app.get("/api/submissions/{user_id}/{mission_id}")
async def get_submission(mission_id: str, user_id: str = Depends(require_self)):
    """The learner's own reflection for one mission -- text, when it was
    submitted. Feeds the Vault retrospective screen, which needed a way to
    show what the learner actually wrote, not just the timeline's
    system-generated insights. Reflections are personal (mission_reflections)
    even though the evidence file itself is team-owned (submissions).

    Also carries the team's grade/feedback, once it exists: confirmed live
    (2026-07-20) that admin_sync_grades correctly writes grade/feedback/
    status='graded' onto the team_product submission row, but until now
    nothing anywhere read those columns back out -- a real student had a
    real 100% sitting in Postgres with no way to ever see it. This is the
    minimal fix: surface the team's latest team_product row alongside the
    existing reflection payload."""
    row = db_fetch_one(
        """SELECT reflection, submitted_at FROM mission_reflections
           WHERE user_id = %s::uuid AND mission_id = %s::uuid""",
        (user_id, mission_id)
    )
    team_id = _get_user_team(user_id)
    grade_row = db_fetch_one(
        """SELECT status, grade, feedback, graded_at FROM submissions
           WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product'
           ORDER BY submitted_at DESC LIMIT 1""",
        (team_id, mission_id)
    ) if team_id else None
    grading = {
        "status": grade_row[0] if grade_row else None,
        "grade": grade_row[1] if grade_row else None,
        "feedback": grade_row[2] if grade_row else None,
        "graded_at": grade_row[3].isoformat() if grade_row and grade_row[3] else None,
    } if grade_row else None

    if not row:
        return {"submitted": False, "grading": grading}
    return {
        "submitted": True,
        "reflection": row[0],
        "submitted_at": row[1].isoformat() if row[1] else None,
        "status": "submitted",
        "grading": grading,
    }


# ========== Timeline ==========
@app.get("/api/timeline/{user_id}/{mission_id}")
async def get_timeline(mission_id: str, user_id: str = Depends(require_self)):
    """The learner-timeline projection (submitted/processing/ai_analysis/
    teacher_review steps + insights) that workers.py's SEARCH & TIMELINE
    WORKER maintains -- UI_SPEC.md's mission brief/debrief screens poll this
    for the live timeline strip, but no read API existed for it at all until
    now."""
    projection_id = f"{user_id}_{mission_id}"
    try:
        doc = os_client.get(index="learner-timeline", id=projection_id)["_source"]
    except Exception:
        # No feedback event has landed yet -- valid pre-processing state, not
        # an error. "Submitted" reflects the TEAM's shared evidence (the
        # closest analog to the old per-user submission row) -- this is
        # "has our team turned this in," not "have I personally reflected."
        team_id = _get_user_team(user_id)
        has_submission = team_id and db_fetch_one(
            "SELECT 1 FROM submissions WHERE team_id = %s::uuid AND mission_id = %s::uuid LIMIT 1",
            (team_id, mission_id)
        )
        submitted_status = "completed" if has_submission else "pending"
        doc = {
            "learner_id": user_id, "mission_id": mission_id, "insights": [],
            "timeline": [
                {"id": "submitted", "label": "Submitted", "status": submitted_status, "timestamp": None, "content": "Evidence received." if has_submission else ""},
                {"id": "processing", "label": "Processing", "status": "pending", "timestamp": None, "content": ""},
                {"id": "ai_analysis", "label": "AI Analysis", "status": "pending", "timestamp": None, "content": ""},
                {"id": "teacher_review", "label": "Instructor Review", "status": "pending", "timestamp": None, "content": ""},
            ]
        }
    return doc


@app.post("/api/timeline/{target_user_id}/{mission_id}/peer-insight")
async def add_peer_insight(
    target_user_id: str,
    mission_id: str,
    text: str = Form(...),
    from_user_id: str = Depends(get_current_user),
):
    """A classmate leaves feedback on someone else's mission work -- the
    peer half of CONCEPTS.md's Insight concept ("feedback from AI Coach,
    instructor, or peer"), which had never been built: nothing emitted or
    displayed peer insights before this (GAPS.md's #2 flagged gap). Reuses
    the existing InsightPublished event and learner-timeline projection --
    the worker was fixed alongside this to NOT treat a peer comment as
    completing "Instructor Review" the way a real teacher insight does."""
    try:
        if target_user_id == from_user_id:
            raise HTTPException(status_code=400, detail="Can't leave peer feedback on your own work")

        commenter = db_fetch_one("SELECT display_name FROM users WHERE id = %s::uuid", (from_user_id,))
        commenter_name = commenter[0] if commenter else "A classmate"

        await publish_event("InsightPublished", {
            "learner_id": target_user_id,
            "mission_id": mission_id,
            "kind": "peer",
            "insight": {
                "category": "Peer Feedback",
                "source": commenter_name,
                "text": text,
            },
        })

        # Behavioral achievement trigger (GAME_DESIGN.md §4.1): Generosity of
        # Spirit ("collaborates, gives, and shares one's time... with
        # others") has zero coverage in the fixed 12 missions' tags, so it's
        # unlocked by the act of giving peer feedback instead. Fire exactly
        # once, at the threshold -- the worker is idempotent on repeats, but
        # there's no reason to keep publishing after the Power is earned.
        db_execute(
            "INSERT INTO peer_insights_given (id, from_user_id, target_user_id, mission_id) VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid)",
            (str(uuid.uuid4()), from_user_id, target_user_id, mission_id)
        )
        given_count = db_fetch_one(
            "SELECT COUNT(*) FROM peer_insights_given WHERE from_user_id = %s::uuid", (from_user_id,)
        )[0]
        threshold = skills_framework.BEHAVIORAL_POWERS["Generosity of Spirit"]["threshold"]
        if given_count == threshold:
            await publish_event("BadgeAwarded", {
                "user_id": from_user_id,
                "badge_key": skills_framework.POWER_TO_QUALITY["Generosity of Spirit"],
                "power_key": "Generosity of Spirit",
                "tag_type": "behavioral",
                "mission_id": None
            })

        return {"status": "posted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Gallery ==========
@app.get("/api/gallery")
async def get_gallery(mission_id: Optional[str] = None, limit: int = 30):
    """Class-wide gallery of completed mission work -- the other half of
    GAPS.md's #2 flagged social-layer gap. Urgent Evoke's engine was peers
    seeing each other's work; before this, no learner could see anyone
    else's submission at all. A live join over submissions/users/missions,
    not a projection -- this is a straightforward indexed catalog read (the
    same category as GET /api/mc-quests), not the kind of cross-event
    aggregation the "no request-time aggregation" rule in UI_SPEC.md is
    about.

    Under the team-evidence model, each row is still the team's one shared
    file, attributed to whoever on the team actually submitted it (s.user_id)
    -- a valid, unchanged interpretation, not every reflecting member."""
    try:
        query = """SELECT s.user_id, u.display_name, s.mission_id, m.title, m.superpower, s.submitted_at
                    FROM submissions s
                    JOIN users u ON u.id = s.user_id
                    JOIN missions m ON m.id = s.mission_id"""
        params = []
        if mission_id:
            query += " WHERE s.mission_id = %s::uuid"
            params.append(mission_id)
        query += " ORDER BY s.submitted_at DESC LIMIT %s"
        params.append(limit)

        rows = db_fetch_all(query, tuple(params))
        return {"gallery": [{
            "user_id": str(r[0]), "display_name": r[1], "mission_id": str(r[2]),
            "mission_title": r[3], "superpower": r[4],
            "submitted_at": r[5].isoformat() if r[5] else None,
        } for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Minecraft ==========
@app.get("/api/minecraft/connect-info")
async def minecraft_connect_info():
    """Server address for a learner's actual Minecraft client -- previously
    nowhere in the app (GAPS.md: "No Minecraft connect flow in the web
    app", found by comparing against ui/Final Prosperity Showcase.html,
    which designed this and the real app never built it)."""
    return {
        "host": MINECRAFT_PUBLIC_HOST,
        "java_port": MINECRAFT_PUBLIC_PORT_JAVA,
        "bedrock_port": MINECRAFT_PUBLIC_PORT_BEDROCK,
        "java_address": f"{MINECRAFT_PUBLIC_HOST}:{MINECRAFT_PUBLIC_PORT_JAVA}",
        "bedrock_address": f"{MINECRAFT_PUBLIC_HOST}:{MINECRAFT_PUBLIC_PORT_BEDROCK}",
        "java_version": MINECRAFT_JAVA_VERSION,
    }


@app.get("/api/npc-lines")
async def get_npc_lines():
    """Staged dialogue for the in-Minecraft NPCs, externally editable here
    instead of baked into ProsperityDialog.java's jar. The mod polls this on
    a timer, so editing a row changes what an NPC says with no rebuild or
    redeploy. One greeting (shown once per player, per NPC, the first time
    they're approached -- the "here's my frequency" beat) plus a rotating
    pool of ordinary lines."""
    rows = db_fetch_all(
        "SELECT npc_name, line_text, is_greeting FROM npc_lines ORDER BY npc_name, sort_order"
    )
    result: dict = {}
    for npc_name, line_text, is_greeting in rows:
        entry = result.setdefault(npc_name, {"greeting": None, "lines": []})
        if is_greeting:
            entry["greeting"] = line_text
        else:
            entry["lines"].append(line_text)
    return result


@app.get("/api/minecraft/link/{user_id}")
async def get_minecraft_link(user_id: str = Depends(require_self)):
    """Get Minecraft link for a user"""
    try:
        link = db_fetch_one(
            "SELECT minecraft_username FROM minecraft_links WHERE user_id = %s::uuid AND server_id = 'default'",
            (user_id,)
        )
        if link:
            return {"linked": True, "username": link[0]}
        return {"linked": False}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Basin Archive: the tablet-facing content for the basin_archive quest chain
# seeded at startup. Hard-coded here on purpose (playtest 2026-07-21) — the
# teaser is what a locked entry shows, the memory is Billbot's recovered
# text once the bridge detects the matching in-world act. Every directive in
# the memory text references a real, verified world mechanic: the free
# pickaxe station at (-138,63,211), the mines entrance sign at (-140,66,168),
# the claimReward wage trigger at the mines exit lobby, the bridge's
# /trigger buyTicket office (bridge.py), and the paper-consuming train at
# (-137,65,108).
BASIN_ARCHIVE = [
    {"key": "tablet", "title": "The Tablet", "quest": None,
     "teaser": "Billbot's memory of the Basin is fragmented. Sync your tablet from inside the simulation to start recovering it.",
     "memory": "Signal locked — you're in my world now. You'll wake on the ridge above Keel. Stop. Look around before you move: Keel below you, Halyard's lights upslope, the Oasis glowing at the summit. That's the whole mountain. Then walk downhill into town."},
    {"key": "overlook", "title": "The Overlook", "quest": "Archive: The Overlook",
     "teaser": "▓▓▓ corrupted — enter the Basin to recover ▓▓▓",
     "memory": "You made it in. From up there everything looks small — that's how Alpha liked it. Head down into Keel and find my kiosk near the villager pen. New workers get a free pickaxe at the worker station beside it. Take it. You'll need it."},
    {"key": "keel", "title": "Down into Keel", "quest": "Archive: Down into Keel",
     "teaser": "▓▓▓ corrupted — find the town below the ridge ▓▓▓",
     "memory": "Keel. Home. Not much, but people here get by on each other. Talk to anyone you meet — Jim, Beth, the folks in the pen. The mines are at the west end of town, past the coin-flip stand. Look for the 'Enter the mines' sign."},
    {"key": "mines", "title": "The Mines", "quest": "Archive: The Mines",
     "teaser": "▓▓▓ corrupted — find where Keel earns its keep ▓▓▓",
     "memory": "The lift still runs. Good. Mine coal down there — it's hard, honest work, and it's how everyone in Keel starts. Every piece sells back to Alpha for a dollar: right-click the shop sign in the mines, or type /trigger sellCoal from anywhere."},
    {"key": "coal", "title": "First Coal", "quest": "Archive: First Coal",
     "teaser": "▓▓▓ corrupted — bring something back from underground ▓▓▓",
     "memory": "Coal in hand. That seam kept this town alive for a generation. Now save: a train ticket up to Halyard costs $100. Mine, sell, repeat — and when you've got $100, buy your ticket at the station booth sign (or type /trigger buyTicket)."},
    {"key": "ticket", "title": "The Ticket Up", "quest": "Archive: The Ticket Up",
     "teaser": "▓▓▓ corrupted — earn your way off the mountain floor ▓▓▓",
     "memory": "Halyard. Rent, fees, time-clocks — everything up here costs, and the water still isn't free. You earned your way up; nobody gave it to you. Remember what that took. The archive continues…"},
]


@app.get("/api/basin-archive/{user_id}")
async def get_basin_archive(user_id: str = Depends(require_self)):
    """The Field Tablet's Basin Archive: BASIN_ARCHIVE entries resolved
    against this user's link state (entry 1) and mc_quest_completions
    (the rest, completed by the bridge's world detection)."""
    try:
        linked = bool(db_fetch_one(
            "SELECT 1 FROM minecraft_links WHERE user_id = %s::uuid", (user_id,)
        ))
        completed = {r[0] for r in db_fetch_all(
            """SELECT q.title FROM mc_quest_completions c
               JOIN mc_quests q ON q.id = c.quest_id
               WHERE c.user_id = %s::uuid AND q.kind = 'basin_archive'""",
            (user_id,)
        )}
        entries = []
        for e in BASIN_ARCHIVE:
            unlocked = linked if e["quest"] is None else e["quest"] in completed
            entries.append({
                "key": e["key"], "title": e["title"], "unlocked": unlocked,
                "text": e["memory"] if unlocked else e["teaser"],
            })
        return {
            "linked": linked,
            "recovered": sum(1 for e in entries if e["unlocked"]),
            "total": len(entries),
            "entries": entries,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/mc-quests")
async def list_mc_quests(campaign_id: Optional[str] = None):
    """List Minecraft quests"""
    try:
        if not campaign_id:
            campaign_id_row = db_fetch_one("SELECT id FROM campaigns WHERE key = 'evoke-prosperity'")
            campaign_id = campaign_id_row[0] if campaign_id_row else None

        quests = db_fetch_all(
            """SELECT id, mission_id, title, description, kind FROM mc_quests
               WHERE campaign_id = %s::uuid ORDER BY kind, title""",
            (campaign_id,)
        )

        result = []
        for quest in quests:
            quest_id, mission_id, title, description, kind = quest
            result.append({
                "id": str(quest_id),
                "mission_id": str(mission_id) if mission_id else None,
                "title": title,
                "description": description,
                "kind": kind
            })

        return {"quests": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/mc-quests/{quest_id}/submit")
async def submit_quest_evidence(
    quest_id: str,
    observation_text: str = Form(None),
    screenshot: UploadFile = File(None),
    user_id: str = Depends(get_current_user),
):
    """Submit evidence for a Minecraft quest"""
    try:
        screenshot_key = None
        if screenshot:
            screenshot_bytes = await screenshot.read()
            screenshot_key = f"mc-quests/{quest_id}/{user_id}_{screenshot.filename}"
            s3_client.put_object(
                Bucket="default-bucket",
                Key=screenshot_key,
                Body=screenshot_bytes
            )

        # Record submission
        db_execute(
            """INSERT INTO mc_quest_submissions (quest_id, user_id, observation_text, screenshot_object_key)
               VALUES (%s::uuid, %s::uuid, %s, %s)""",
            (quest_id, user_id, observation_text, screenshot_key)
        )

        # Check-then-insert (not atomic — mirrors this file's existing style,
        # e.g. the awards ON CONFLICT DO NOTHING pattern above) so
        # QuestCompleted/XPGranted only fire on a genuinely new completion,
        # not every resubmission of the same quest.
        already_completed = db_fetch_one(
            "SELECT 1 FROM mc_quest_completions WHERE user_id = %s::uuid AND quest_id = %s::uuid",
            (user_id, quest_id)
        )

        db_execute(
            """INSERT INTO mc_quest_completions (user_id, quest_id)
               VALUES (%s::uuid, %s::uuid)
               ON CONFLICT DO NOTHING""",
            (user_id, quest_id)
        )

        if not already_completed:
            quest_row = db_fetch_one(
                "SELECT mission_id, kind FROM mc_quests WHERE id = %s::uuid", (quest_id,)
            )
            await publish_event("QuestCompleted", {
                "user_id": user_id,
                "quest_id": quest_id,
                "mission_id": str(quest_row[0]) if quest_row and quest_row[0] else None,
                "kind": quest_row[1] if quest_row else None
            })
            # XP value is a placeholder (matches overview.md's example table)
            # — GAPS.md flags the real XP economy as still undecided. Per
            # canon, quest XP is real but never gates or grades a mission.
            await publish_event("XPGranted", {
                "user_id": user_id,
                "amount": 40,
                "reason": "quest_completed",
                "quest_id": quest_id
            })

        return {"status": "submitted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== B1llbot Chat ==========
@app.post("/api/billbot/chat")
async def billbot_chat(message: str, user_id: str = Depends(require_self)):
    """Chat with B1llbot"""
    try:
        # Behavioral achievement trigger (GAME_DESIGN.md §4.1): Curiosity
        # ("asks good questions") has zero coverage in the fixed 12
        # missions' tags, so it's unlocked by chat volume instead. Logged
        # before the OpenWebUI call so the count reflects messages sent
        # regardless of whether B1llbot's reply succeeds.
        db_execute(
            "INSERT INTO billbot_chat_log (id, user_id, message) VALUES (%s::uuid, %s::uuid, %s)",
            (str(uuid.uuid4()), user_id, message)
        )
        sent_count = db_fetch_one(
            "SELECT COUNT(*) FROM billbot_chat_log WHERE user_id = %s::uuid", (user_id,)
        )[0]
        threshold = skills_framework.BEHAVIORAL_POWERS["Curiosity"]["threshold"]
        if sent_count == threshold:
            await publish_event("BadgeAwarded", {
                "user_id": user_id,
                "badge_key": skills_framework.POWER_TO_QUALITY["Curiosity"],
                "power_key": "Curiosity",
                "tag_type": "behavioral",
                "mission_id": None
            })

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AI_GATEWAY_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_GATEWAY_KEY}"},
                json={
                    "model": "billbot",
                    "messages": [
                        {"role": "user", "content": message}
                    ]
                },
                # A cold model load on the local Ollama backend (host.docker.internal)
                # measured up to ~60s end-to-end in testing; a warm one is ~10-20s.
                # Generous margin above the observed worst case rather than cutting
                # it close.
                timeout=90
            )

            if response.status_code == 200:
                data = response.json()
                # `.get("content", default)` only falls back when the KEY is
                # missing, not when it's present but "" -- and an empty
                # string genuinely happens: the base model's hidden
                # reasoning trace (see openwebui-bootstrap.py's MAX_TOKENS
                # comment) can consume the entire token budget before any
                # visible answer is generated, returning content: "". `or`
                # catches both cases instead of just the missing-key one.
                reply = data.get("choices", [{}])[0].get("message", {}).get("content") or "Hmm, lost my train of thought there. Ask me again?"
                return {"reply": reply}
            logger.warning(f"B1llbot chat failed: HTTP {response.status_code} {response.text[:300]}")

        return {"reply": "I'm having trouble responding right now."}
    except Exception as e:
        logger.warning(f"B1llbot chat error: {e}")
        return {"reply": f"Error: {str(e)}"}

# ========== Live layer (WebSocket) ==========
@app.websocket("/ws")
async def websocket_live(ws: WebSocket):
    """One-way live push of processed stream events to the browser (Hub,
    Companion) — see evoke/live.py. Inbound messages are ignored (clients
    may send pings to keep intermediaries from idling the socket)."""
    await ws.accept()
    live_hub.register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        live_hub.unregister(ws)
    except Exception:
        live_hub.unregister(ws)


# ========== World State ==========
@app.get("/api/world-state")
async def get_world_state():
    """Keel's collective restoration state (GAPS.md #5) — the WORLD WORKER's
    projection over every learner's MissionCompleted events, plus the full
    stage table so the UI can render the whole arc, not just the current
    reading."""
    try:
        world = os_client.get(index="world-state", id="keel")["_source"]
    except Exception:
        world = {"completions": 0, "stage": 0, "history": []}

    stage = world.get("stage", 0)
    completions = world.get("completions", 0)
    next_at = (stage + 1) * world_state.STAGE_STEP if stage < world_state.MAX_STAGE else None
    return {
        "stage": stage,
        "total_stages": world_state.MAX_STAGE,
        "completions": completions,
        "step": world_state.STAGE_STEP,
        "next_stage_at": next_at,
        "current": world_state.stage_meta(stage),
        "stages": [world_state.stage_meta(i) for i in range(world_state.MAX_STAGE + 1)],
        "history": world.get("history", []),
    }


# ========== Minecraft live status ==========
@app.get("/api/minecraft/status")
async def minecraft_status():
    """Who's in the Basin right now — the PRESENCE WORKER's projection of
    the bridge's MinecraftPresence snapshots. Staleness matters: if the
    bridge hasn't reported in a while, say "unknown" rather than repeating
    a dead snapshot as if it were live."""
    try:
        doc = os_client.get(index="minecraft-status", id="default")["_source"]
    except Exception:
        return {"server_online": False, "online_players": [], "linked_players": {}, "stale": True}

    stale = True
    try:
        updated = datetime.datetime.fromisoformat(doc.get("updated_at"))
        stale = (datetime.datetime.now() - updated).total_seconds() > 90
    except Exception:
        pass
    return {
        "server_online": doc.get("server_online", False) and not stale,
        "online_players": doc.get("online_players", []) if not stale else [],
        "linked_players": doc.get("linked_players", {}),
        "stale": stale,
    }


@app.get("/api/mc-arena/{user_id}")
async def get_arena_progress(user_id: str = Depends(require_self)):
    """Claude's Halyard Mob Arena best-wave reached -- bridge-owned table
    (see check_arena_progress in bridge.py), read-only here."""
    row = db_fetch_one("SELECT best_wave FROM mc_arena_best WHERE user_id = %s::uuid", (user_id,))
    return {"best_wave": row[0] if row else 0}


@app.get("/api/mc-gauntlet/{user_id}")
async def get_gauntlet_progress(user_id: str = Depends(require_self)):
    """The Mob Gauntlet best-wave reached -- bridge-owned table (see
    check_gauntlet_progress in bridge.py), read-only here."""
    row = db_fetch_one("SELECT best_wave FROM mc_gauntlet_best WHERE user_id = %s::uuid", (user_id,))
    return {"best_wave": row[0] if row else 0}


# ========== Companion (phone) ==========
_PRIVATE_IPV4_RE = re.compile(
    r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})$"
)


def _companion_url(request: Request, hint_host: Optional[str] = None) -> str:
    """Best-effort URL a *phone* can reach. Priority: explicit override
    (PUBLIC_WEB_URL) > the host the browser itself used (works when the
    user opened the app via LAN IP) > a client-supplied hint_host (the
    browser's own WebRTC-discovered local IP, app.js's detectLocalIP() --
    the server can't determine the host machine's real LAN IP itself from
    behind Docker's bridge network, but a browser that navigated here via
    localhost still knows its own local network address) > localhost (QR
    still renders; the UI explains it won't scan usefully as-is)."""
    override = os.getenv("PUBLIC_WEB_URL", "")
    if override:
        return override.rstrip("/") + "/companion.html"
    host = request.headers.get("host", "localhost:8000")
    if hint_host and _PRIVATE_IPV4_RE.match(hint_host) and (host.startswith("localhost") or host.startswith("127.")):
        port = host.split(":", 1)[1] if ":" in host else "80"
        host = f"{hint_host}:{port}"
    return f"http://{host}/companion.html"


def _mint_pairing_token(user_id: str) -> Optional[str]:
    """Single-use, 10-min-expiry token that lets a *different device/tab*
    open companion.html already logged in as user_id, no re-auth (BUILD_PLAN_2
    §7). Shared by the QR code (phone) and the desktop "Open Field Kit"
    entry points -- same mechanism either way, since Field Kit is the same
    PWA regardless of which device opens it."""
    token = str(uuid.uuid4())
    try:
        db_execute(
            "INSERT INTO pairing_tokens (token, user_id) VALUES (%s::uuid, %s::uuid)",
            (token, user_id)
        )
        return token
    except Exception as e:
        logger.warning(f"Pairing token mint failed: {e}")
        return None


@app.get("/api/companion/info")
async def companion_info(request: Request, hint_host: Optional[str] = None, user_id: str = Depends(get_current_user)):
    """user_id now always comes from the caller's own verified session, not
    a query param -- previously any unauthenticated caller could pass
    ?user_id=<anyone> and get back a pairing token for that person's
    account (see companion_qr's docstring)."""
    url = _companion_url(request, hint_host)
    token = _mint_pairing_token(user_id)
    if token:
        url += f"?pair={token}"
    return {"url": url, "scannable": not url.startswith("http://localhost") and not url.startswith("http://127.")}


@app.get("/api/companion/qr.svg")
async def companion_qr(request: Request, hint_host: Optional[str] = None, user_id: str = Depends(get_current_user)):
    """This QR is a pairing token minted for whoever calls it -- previously
    that was any client-supplied user_id, so anyone who knew or guessed a
    UUID could render a QR that logged a phone in as that person with no
    credential check at all. Now it's always the logged-in caller's own
    session."""
    import io
    import qrcode
    import qrcode.image.svg
    url = _companion_url(request, hint_host)
    token = _mint_pairing_token(user_id)
    if token:
        url += f"?pair={token}"
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=12)
    buf = io.BytesIO()
    img.save(buf)
    return Response(content=buf.getvalue(), media_type="image/svg+xml")


# ========== Minigames (Training Sims) ==========
# Browser minigames -- the same optionality rule as Minecraft quests applies
# (self-directed, never gates or grades a mission), and the same XP-through-
# the-real-pipeline rule as everything else: completions publish XPGranted
# events, never write projections directly. XP per game is capped at one
# grant per calendar day (plus a small personal-best bonus) so grinding a
# minigame can't out-earn actual missions -- the quest-XP-cap principle
# GAPS.md asks for, applied here from day one.

MINIGAME_KEYS = {"flow-control", "signal-decrypt"}
MINIGAME_DAILY_XP = 25
MINIGAME_BEST_BONUS = 10

# Scores are computed client-side and posted as a plain int with no signing
# -- fine for a self-reported honor-system XP grant (already capped above),
# but an unclamped score would also land straight on the public per-game
# leaderboard, where a spoofed request is far more visible than a spoofed
# quest. Clamp to each game's real theoretical max (with headroom) so a
# forged score can't out-rank real play. See games.js for the math each
# ceiling is derived from: Flow Control's gauges cap at 100/100/12/12 plus
# a +20 survive bonus; Signal Decrypt's streak multiplier over an 8-card
# deck tops out at 100*(1+2+...+8).
MINIGAME_MAX_SCORE = {"flow-control": 300, "signal-decrypt": 3700}

# The Alchemy Signal hunt: 5 fragments hidden across the app. NOTE:
# GAME_DESIGN.md §13.5 explicitly leaves Alchemy's encrypted-signal beats
# as an open narrative question -- the unlock copy stays deliberately
# minimal (no invented backstory) until the narrative team answers it.
SIGNAL_FRAGMENT_KEYS = {"glyph", "konami", "novel", "vault", "billbot"}
SIGNAL_UNLOCK_XP = 150


@app.post("/api/minigames/{game_key}/score")
async def submit_minigame_score(game_key: str, user_id: str = Depends(require_self), score: int = Form(...)):
    if game_key not in MINIGAME_KEYS:
        raise HTTPException(status_code=404, detail="Unknown training sim")
    try:
        score = max(0, min(score, MINIGAME_MAX_SCORE[game_key]))

        prev_best = db_fetch_one(
            "SELECT MAX(score) FROM minigame_scores WHERE user_id = %s::uuid AND game_key = %s",
            (user_id, game_key)
        )
        prev_best = prev_best[0] if prev_best and prev_best[0] is not None else None

        already_today = db_fetch_one(
            """SELECT 1 FROM minigame_scores
               WHERE user_id = %s::uuid AND game_key = %s AND created_at::date = CURRENT_DATE LIMIT 1""",
            (user_id, game_key)
        )

        db_execute(
            "INSERT INTO minigame_scores (user_id, game_key, score) VALUES (%s::uuid, %s, %s)",
            (user_id, game_key, score)
        )

        xp = 0
        if not already_today:
            xp += MINIGAME_DAILY_XP
        is_best = prev_best is None or score > prev_best
        if is_best and prev_best is not None:
            xp += MINIGAME_BEST_BONUS
        if xp:
            await publish_event("XPGranted", {
                "user_id": user_id, "amount": xp,
                "reason": "minigame", "game_key": game_key,
            })
        return {"status": "recorded", "xp_granted": xp, "personal_best": is_best}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/minigames/{game_key}/leaderboard")
async def minigame_leaderboard(game_key: str, limit: int = 10, user_id: Optional[str] = Depends(get_current_user_optional)):
    if game_key not in MINIGAME_KEYS:
        raise HTTPException(status_code=404, detail="Unknown training sim")
    rows = db_fetch_all(
        """SELECT u.display_name, MAX(s.score) AS best
           FROM minigame_scores s JOIN users u ON u.id = s.user_id
           WHERE s.game_key = %s GROUP BY u.id, u.display_name
           ORDER BY best DESC LIMIT %s""",
        (game_key, limit)
    )
    personal = None
    if user_id:
        best = db_fetch_one(
            "SELECT MAX(score) FROM minigame_scores WHERE user_id = %s::uuid AND game_key = %s",
            (user_id, game_key)
        )
        personal = best[0] if best and best[0] is not None else None
    return {
        "leaderboard": [{"display_name": r[0], "best": r[1]} for r in rows],
        "personal_best": personal,
    }


@app.post("/api/minigames/signal/fragment")
async def collect_signal_fragment(user_id: str = Depends(require_self), fragment: str = Form(...)):
    """One fragment of the Alchemy Signal found. Server-tracked (not just
    localStorage) so the unlock XP can't be re-farmed by clearing the
    browser, and so finding all 5 lands in the class feed."""
    if fragment not in SIGNAL_FRAGMENT_KEYS:
        raise HTTPException(status_code=404, detail="No such signal source")
    try:
        game_key = f"signal:{fragment}"
        already = db_fetch_one(
            "SELECT 1 FROM minigame_scores WHERE user_id = %s::uuid AND game_key = %s LIMIT 1",
            (user_id, game_key)
        )
        if not already:
            db_execute(
                "INSERT INTO minigame_scores (user_id, game_key, score) VALUES (%s::uuid, %s, 1)",
                (user_id, game_key)
            )

        found_rows = db_fetch_all(
            "SELECT DISTINCT game_key FROM minigame_scores WHERE user_id = %s::uuid AND game_key LIKE 'signal:%%'",
            (user_id,)
        )
        found = sorted(r[0].split(":", 1)[1] for r in found_rows)

        unlocked = False
        if len(found) == len(SIGNAL_FRAGMENT_KEYS):
            already_unlocked = db_fetch_one(
                "SELECT 1 FROM minigame_scores WHERE user_id = %s::uuid AND game_key = 'signal:unlocked' LIMIT 1",
                (user_id,)
            )
            if not already_unlocked:
                db_execute(
                    "INSERT INTO minigame_scores (user_id, game_key, score) VALUES (%s::uuid, 'signal:unlocked', 1)",
                    (user_id,)
                )
                await publish_event("XPGranted", {
                    "user_id": user_id, "amount": SIGNAL_UNLOCK_XP, "reason": "alchemy_signal",
                })
                unlocked = True

        return {"found": found, "total": len(SIGNAL_FRAGMENT_KEYS), "unlocked": unlocked}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/minigames/signal/{user_id}")
async def signal_progress(user_id: str = Depends(require_self)):
    rows = db_fetch_all(
        "SELECT DISTINCT game_key FROM minigame_scores WHERE user_id = %s::uuid AND game_key LIKE 'signal:%%'",
        (user_id,)
    )
    keys = {r[0].split(":", 1)[1] for r in rows}
    return {
        "found": sorted(k for k in keys if k != "unlocked"),
        "total": len(SIGNAL_FRAGMENT_KEYS),
        "unlocked": "unlocked" in keys,
    }


# ========== Team Wheel ==========
@app.get("/api/team/{team_id}/wheel")
async def team_wheel(team_id: str):
    """GAME_DESIGN §7.1's Team Wheel, rolling-roster variant: one wheel per
    released mission, a wedge per *current* member, filled when that member
    has reflected on the mission (the team's shared evidence is one file
    for everyone -- the personal, per-member act is the reflection, so
    that's what a wedge represents under the team-evidence model). Computed
    live from mission_reflections, so roster changes are reflected
    immediately (variant #1) and wheels never expire (variant #3)."""
    try:
        members = db_fetch_all(
            """SELECT tm.user_id, u.display_name FROM team_members tm
               JOIN users u ON u.id = tm.user_id WHERE tm.team_id = %s::uuid""",
            (team_id,)
        )
        roster = [{"user_id": str(m[0]), "display_name": m[1]} for m in members]
        roster_ids = [m[0] for m in members]

        campaign_row = db_fetch_one("SELECT id FROM campaigns WHERE key = 'evoke-prosperity'")
        missions = db_fetch_all(
            """SELECT id, title, week FROM missions
               WHERE campaign_id = %s::uuid AND released_at IS NOT NULL ORDER BY week, sequence""",
            (campaign_row[0],)
        ) if campaign_row else []

        wheels = []
        for mission_id, title, week in missions:
            done_rows = db_fetch_all(
                "SELECT DISTINCT user_id FROM mission_reflections WHERE mission_id = %s::uuid AND user_id = ANY(%s::uuid[])",
                (mission_id, roster_ids)
            ) if roster_ids else []
            done = {str(r[0]) for r in done_rows}
            wheels.append({
                "mission_id": str(mission_id), "title": title, "week": week,
                "wedges": [{**m, "filled": m["user_id"] in done} for m in roster],
                "complete": bool(roster) and len(done) == len(roster),
            })
        return {"team_id": team_id, "roster_size": len(roster), "wheels": wheels}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Instructor Ops Deck ==========
@app.get("/api/admin/cohort")
async def admin_cohort(user_id: str = Depends(get_current_admin)):
    """Per-learner overview for the instructor: level/XP, missions done,
    last activity, and what's waiting on the teacher. Same unprotected-dev
    status as the rest of /api/admin (see the release routes' note)."""
    try:
        org_row = db_fetch_one("SELECT org_id FROM users WHERE id = %s::uuid", (user_id,))
        if not org_row:
            raise HTTPException(status_code=404, detail="User/org not found")
        learners = db_fetch_all(
            "SELECT id, display_name, email FROM users WHERE org_id = %s::uuid AND role = 'learner' ORDER BY display_name",
            (org_row[0],)
        )
        out = []
        for lid, name, email in learners:
            lid = str(lid)
            try:
                profile = os_client.get(index="player-profile", id=lid)["_source"]
            except Exception:
                profile = {}
            # Last activity: the more recent of this learner's own last
            # reflection, or their team's last evidence submission -- either
            # is genuine per-learner engagement under the team-evidence
            # model (a teammate submitting the shared file doesn't count as
            # *this* learner's activity on its own, but their team doing so
            # is still worth surfacing here).
            last_sub = db_fetch_one(
                """SELECT GREATEST(
                     (SELECT MAX(mr.submitted_at) FROM mission_reflections mr WHERE mr.user_id = %s::uuid),
                     (SELECT MAX(s.submitted_at) FROM submissions s
                        JOIN team_members tm ON tm.team_id = s.team_id
                        WHERE tm.user_id = %s::uuid)
                   )""",
                (lid, lid)
            )
            last_checkin = db_fetch_one(
                "SELECT MAX(checkin_date) FROM checkins WHERE user_id = %s::uuid", (lid,)
            )
            # Waiting on the teacher: completed missions (evidence +
            # reflection both landed -- a real 'submission' award exists)
            # with no teacher_review award yet.
            pending = db_fetch_one(
                """SELECT COUNT(DISTINCT a.mission_id) FROM awards a
                   WHERE a.user_id = %s::uuid AND a.source = 'submission' AND NOT EXISTS (
                     SELECT 1 FROM awards a2 WHERE a2.user_id = a.user_id
                       AND a2.mission_id = a.mission_id AND a2.source = 'teacher_review')""",
                (lid,)
            )
            out.append({
                "user_id": lid, "display_name": name, "email": email,
                "level": profile.get("level", 1),
                "xp": profile.get("xp", 0),
                "rank_title": progression.level_title(profile.get("level", 1)),
                "missions_completed": len(profile.get("missions_completed", [])),
                "last_submission": last_sub[0].isoformat() if last_sub and last_sub[0] else None,
                "last_checkin": last_checkin[0].isoformat() if last_checkin and last_checkin[0] else None,
                "pending_teacher_reviews": pending[0] if pending else 0,
            })
        return {"cohort": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Admin: roster import + team management ==========
# EVOKE Players are 1:1 with LMS students (evoke_identities, see
# evoke/identity.py); this is the admin-driven half of that link -- the
# other half is a student's first real LTI launch
# (evoke/lti/brightspace_lti_provider.py). Same unprotected-dev status as
# the rest of /api/admin (see admin_cohort's note) -- not introducing a new,
# inconsistent auth model just for these.

# _fetch_classlist() used to live here -- dead code with no callers even
# before this pass, and superseded anyway by GET /api/admin/brightspace/roster
# (the real classlist pull via the shared service connection).

# Manual roster-import (/api/admin/roster*), team CRUD (/api/admin/teams*),
# and playtest-user provisioning used to live here. Removed: Brightspace is
# now the sole source of truth for who exists (OAuth login provisioning,
# evoke/identity.py) and which team they're on (Groups sync at login,
# oauth_providers.py's _resolve_team_name -> identity.sync_team_membership)
# -- Evoke Admin no longer manages users or teams directly, and
# playtest-user's whole purpose (provisioning a non-Brightspace identity via
# the ?login= magic link) went away with that link. If a non-Brightspace
# smoke-test identity is ever needed again, that's a seed script run
# against the database directly, not a live unauthenticated-by-design API
# route.


# ========== Stages & the Campaign Map (BUILD_PLAN_2 §2-3) ==========
TIER_RANK = {"common": 1, "epic": 2, "legendary": 3}
STAGE_STARS = {1: "★", 2: "★★", 3: "★★★"}


@app.post("/api/admin/missions/{mission_id}/stage")
async def admin_set_stage(mission_id: str, stage: int = Form(...), admin_id: str = Depends(get_current_admin)):
    """Stages are instructor pedagogy config (Nathan's decision: cadence
    must flex with classes/workshops), decoupled from the LMS week the
    stage column defaults to. Same unprotected-dev status as /api/admin."""
    if stage < 1 or stage > 24:
        raise HTTPException(status_code=400, detail="Stage must be 1-24")
    db_execute("UPDATE missions SET stage = %s WHERE id = %s::uuid", (stage, mission_id))
    return {"status": "ok", "stage": stage}


@app.get("/api/progress-map/{user_id}")
async def progress_map(user_id: str = Depends(require_self)):
    """The 'what done means' infographic's data: missions grouped by
    admin-configured stage; per stage a completion ring (submitted/total)
    and a quality grade (MIN best-tier across submitted missions -- a
    stage is as strong as its weakest evidence, which is what makes
    resubmission legible). Quests attach per-mission only when the learner
    is Minecraft-linked (BUILD_PLAN_2 §4)."""
    try:
        org_row = db_fetch_one(
            "SELECT o.active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
            (user_id,)
        )
        if not org_row:
            raise HTTPException(status_code=404, detail="Organization not found")

        linked = bool(db_fetch_one(
            "SELECT 1 FROM minecraft_links WHERE user_id = %s::uuid", (user_id,)
        ))

        rows = db_fetch_all(
            """SELECT m.id, m.title, m.week, m.stage, m.released_at IS NOT NULL AS released,
                      (SELECT MAX(CASE a.tier WHEN 'legendary' THEN 3 WHEN 'epic' THEN 2 ELSE 1 END)
                         FROM awards a WHERE a.user_id = %s::uuid AND a.mission_id = m.id) AS best_rank,
                      EXISTS(SELECT 1 FROM awards a2 WHERE a2.user_id = %s::uuid AND a2.mission_id = m.id AND a2.source = 'submission') AS submitted
               FROM missions m WHERE m.campaign_id = %s::uuid
               ORDER BY m.stage NULLS LAST, m.week, m.sequence""",
            (user_id, user_id, org_row[0])
        )

        quest_rows = {}
        if linked:
            for qid, mission_id_q, title, done in db_fetch_all(
                """SELECT q.id, q.mission_id, q.title,
                          EXISTS(SELECT 1 FROM mc_quest_completions c WHERE c.quest_id = q.id AND c.user_id = %s::uuid)
                   FROM mc_quests q WHERE q.mission_id IS NOT NULL""",
                (user_id,)
            ):
                quest_rows[str(mission_id_q)] = {"quest_id": str(qid), "title": title, "done": done}

        stages = {}
        for mid, title, week, stage, released, best_rank, submitted in rows:
            stage = stage or week or 1
            s = stages.setdefault(stage, {"stage": stage, "missions": []})
            s["missions"].append({
                "id": str(mid), "title": title, "week": week,
                "released": released, "submitted": bool(submitted),
                "best_tier_rank": best_rank,
                "quest": quest_rows.get(str(mid)),
            })

        out = []
        for stage in sorted(stages):
            s = stages[stage]
            total = len(s["missions"])
            done = sum(1 for m in s["missions"] if m["submitted"])
            submitted_ranks = [m["best_tier_rank"] for m in s["missions"] if m["submitted"] and m["best_tier_rank"]]
            grade_rank = min(submitted_ranks) if submitted_ranks else 0
            out.append({
                **s,
                "total": total,
                "completed": done,
                "pct": round(done * 100 / total) if total else 0,
                "complete": total > 0 and done == total,
                "grade": STAGE_STARS.get(grade_rank),
                "grade_rank": grade_rank,
            })
        return {
            "user_id": user_id,
            "minecraft_linked": linked,
            "stages": out,
            "stages_complete": sum(1 for s in out if s["complete"]),
            "stages_total": len(out),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Field Report / Words of Wisdom (BUILD_PLAN_2 §6) ==========
# Wisdom generation moved to workers.py's FIELD REPORT WORKER (event-based,
# same reasoning/pattern as the AI Coach Worker's epic-tier award move):
# this endpoint used to block the learner's HTTP response on a synchronous
# OpenWebUI call with the same timeout=90 cold-start risk trigger_ai_review
# had. Everything else here (the row itself, the checkin XP, the
# Transformation badge check) is fast and local, so it still happens
# inline -- only the AI call moved off the request path.
@app.post("/api/reflection")
async def post_reflection(user_id: str = Depends(require_self), text: str = Form(...)):
    """The daily Field Report: one reflection a day, answered with a Word
    of Wisdom in B1llbot's voice, generated async and pushed live once
    ready (see workers.py's FIELD REPORT WORKER + evoke/live.py). Doubles
    as the daily check-in (grants that XP if today's hasn't happened) and,
    at 10 lifetime reflections, unlocks the Transformation Power
    (skills_framework.BEHAVIORAL_POWERS, approved trigger)."""
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Say something — even one line")
    already = db_fetch_one(
        "SELECT wisdom FROM daily_reflections WHERE user_id = %s::uuid AND reflection_date = CURRENT_DATE",
        (user_id,)
    )
    if already:
        return {"status": "already_filed", "wisdom": already[0]}

    db_execute(
        "INSERT INTO daily_reflections (user_id, text, wisdom) VALUES (%s::uuid, %s, NULL) ON CONFLICT DO NOTHING",
        (user_id, text)
    )
    await publish_event("ReflectionFiled", {"user_id": user_id, "text": text})

    # Doubles as the daily check-in (same XP, never double-granted).
    checked = db_fetch_one(
        "SELECT 1 FROM checkins WHERE user_id = %s::uuid AND checkin_date = CURRENT_DATE", (user_id,)
    )
    if not checked:
        db_execute(
            "INSERT INTO checkins (user_id, checkin_date) VALUES (%s::uuid, CURRENT_DATE) ON CONFLICT DO NOTHING",
            (user_id,)
        )
        await publish_event("XPGranted", {"user_id": user_id, "amount": 10, "reason": "field_report"})

    count = db_fetch_one(
        "SELECT COUNT(*) FROM daily_reflections WHERE user_id = %s::uuid", (user_id,)
    )[0]
    threshold = skills_framework.BEHAVIORAL_POWERS["Transformation"]["threshold"]
    if count == threshold:
        await publish_event("BadgeAwarded", {
            "user_id": user_id,
            "badge_key": skills_framework.POWER_TO_QUALITY["Transformation"],
            "power_key": "Transformation",
            "tag_type": "behavioral",
            "mission_id": None,
        })

    return {"status": "filed", "wisdom": None, "wisdom_pending": True, "reflections_total": count}


@app.get("/api/reflections/{user_id}")
async def get_reflections(user_id: str = Depends(require_self), limit: int = 60):
    rows = db_fetch_all(
        """SELECT reflection_date, text, wisdom FROM daily_reflections
           WHERE user_id = %s::uuid ORDER BY reflection_date DESC LIMIT %s""",
        (user_id, limit)
    )
    today = db_fetch_one(
        "SELECT 1 FROM daily_reflections WHERE user_id = %s::uuid AND reflection_date = CURRENT_DATE",
        (user_id,)
    )
    return {
        "filed_today": bool(today),
        "total": len(rows),
        "journal": [{"date": r[0].isoformat(), "text": r[1], "wisdom": r[2]} for r in rows],
    }


@app.get("/api/daily-objectives/{user_id}")
async def get_daily_objectives(user_id: str = Depends(require_self)):
    """Today's rotating checklist (console-player feedback: live games always
    greet you with a short list of "what do I do in the next 10 minutes" --
    we already have every mechanic behind these three, just never presented
    them as a checklist). Not a new subsystem: each row is a plain
    CURRENT_DATE check against a table that already exists for its own
    reason (daily_reflections for the Field Report, minigame_scores for
    Training Sims, peer_insights_given for peer feedback)."""
    try:
        field_report = db_fetch_one(
            "SELECT 1 FROM daily_reflections WHERE user_id = %s::uuid AND reflection_date = CURRENT_DATE",
            (user_id,)
        )
        training_sim = db_fetch_one(
            "SELECT 1 FROM minigame_scores WHERE user_id = %s::uuid AND created_at::date = CURRENT_DATE LIMIT 1",
            (user_id,)
        )
        peer_feedback = db_fetch_one(
            "SELECT 1 FROM peer_insights_given WHERE from_user_id = %s::uuid AND created_at::date = CURRENT_DATE LIMIT 1",
            (user_id,)
        )
        return {
            "objectives": [
                {"key": "field_report", "label": "File a Field Report", "xp_label": "10 XP", "done": bool(field_report), "href": "#/"},
                {"key": "training_sim", "label": "Run a Training Sim", "xp_label": "25 XP", "done": bool(training_sim), "href": "#/arcade"},
                {"key": "peer_feedback", "label": "Leave peer feedback", "xp_label": "Generosity of Spirit", "done": bool(peer_feedback), "href": "#/gallery"},
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Phone pairing (BUILD_PLAN_2 §7) ==========
@app.post("/api/companion/pair")
async def companion_pair(response: Response, token: str = Form(...)):
    """Exchange a one-time QR pairing token (minted by the QR endpoint for
    the logged-in web user) for that user's identity — the phone is
    registered without a login. Single-use, 10-minute expiry.

    The token itself is the verified identity source here (server-minted,
    single-use, short-lived, tied to one user_id at mint time) — same trust
    tier as an OAuth callback code — so this is one of the few places
    outside auth_session.py allowed to call issue_session directly."""
    row = db_fetch_one(
        """SELECT p.user_id, u.display_name, u.email, u.role, p.used_at, p.created_at
           FROM pairing_tokens p JOIN users u ON u.id = p.user_id WHERE p.token = %s::uuid""",
        (token,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Unknown pairing code — rescan from the Hub")
    user_id, display_name, email, role, used_at, created_at = row
    if used_at is not None:
        raise HTTPException(status_code=410, detail="That QR was already used — rescan a fresh one from the Hub")
    if (datetime.datetime.now() - created_at).total_seconds() > 600:
        raise HTTPException(status_code=410, detail="That QR expired — rescan a fresh one from the Hub")
    db_execute("UPDATE pairing_tokens SET used_at = CURRENT_TIMESTAMP WHERE token = %s::uuid", (token,))
    issue_session(response, str(user_id), role=role or "learner")
    return {"user_id": str(user_id), "display_name": display_name, "email": email}


# ========== Two-channel Minecraft linking (BUILD_PLAN_2 §8) ==========
@app.post("/api/minecraft/link-code")
async def create_link_code(user_id: str = Depends(require_self)):
    """Mint a short numeric code the learner types in-game as
    `/trigger evoke_link set <code>`. The bridge watches the trigger
    scoreboard, matches the code, and the phone confirms — two-channel
    possession proof (web session + in-game presence)."""
    db_execute(
        "DELETE FROM mc_link_codes WHERE user_id = %s::uuid AND status = 'waiting'", (user_id,)
    )
    for _ in range(20):
        code = random.randint(1000, 9999)
        try:
            db_execute(
                "INSERT INTO mc_link_codes (code, user_id) VALUES (%s, %s::uuid)",
                (code, user_id)
            )
            return {"code": code, "command": f"/trigger evoke_link set {code}", "expires_in_s": 600}
        except Exception:
            continue  # code collision — try another
    raise HTTPException(status_code=500, detail="Couldn't mint a code, try again")


@app.get("/api/minecraft/link-request/{user_id}")
async def get_link_request(user_id: str = Depends(require_self)):
    """The pending in-game match (bridge saw the code typed) awaiting the
    phone's confirm — polled by the Field Kit alongside the live push."""
    row = db_fetch_one(
        """SELECT code, minecraft_username FROM mc_link_codes
           WHERE user_id = %s::uuid AND status = 'matched' ORDER BY created_at DESC LIMIT 1""",
        (user_id,)
    )
    if not row:
        return {"pending": False}
    return {"pending": True, "code": row[0], "minecraft_username": row[1]}


@app.post("/api/minecraft/link-confirm")
async def confirm_link(user_id: str = Depends(require_self), accept: bool = Form(...)):
    row = db_fetch_one(
        """SELECT code, minecraft_username FROM mc_link_codes
           WHERE user_id = %s::uuid AND status = 'matched' ORDER BY created_at DESC LIMIT 1""",
        (user_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="No pending link request")
    code, mc_username = row
    if not accept:
        db_execute("UPDATE mc_link_codes SET status = 'denied', resolved_at = CURRENT_TIMESTAMP WHERE code = %s", (code,))
        return {"status": "denied"}
    db_execute(
        """INSERT INTO minecraft_links (user_id, server_id, minecraft_username)
           VALUES (%s::uuid, 'default', %s)
           ON CONFLICT (user_id, server_id) DO UPDATE SET minecraft_username = EXCLUDED.minecraft_username""",
        (user_id, mc_username)
    )
    db_execute("UPDATE mc_link_codes SET status = 'confirmed', resolved_at = CURRENT_TIMESTAMP WHERE code = %s", (code,))
    await publish_event("MinecraftLinked", {"user_id": user_id, "minecraft_username": mc_username})
    return {"status": "linked", "minecraft_username": mc_username}


# ========== Aqueduct Kit (BUILD_PLAN_2 §5) ==========
# 10 components, one per major surface, auto-collected by visiting. The
# collection mechanic doubles as navigation training: it rewards seeing
# every screen once.
KIT_PIECES = {
    "intake": "Intake Screen", "basin": "Settling Basin", "sand": "Sand Bed",
    "charcoal": "Charcoal Layer", "membrane": "Membrane", "valve": "Valve",
    "gauge": "Pressure Gauge", "pipes": "Pipe Run", "spout": "Spout", "cap": "Reservoir Cap",
}
KIT_COMPLETE_XP = 100


@app.post("/api/minigames/kit/piece")
async def collect_kit_piece(user_id: str = Depends(require_self), piece: str = Form(...)):
    if piece not in KIT_PIECES:
        raise HTTPException(status_code=404, detail="No such component")
    game_key = f"kit:{piece}"
    already = db_fetch_one(
        "SELECT 1 FROM minigame_scores WHERE user_id = %s::uuid AND game_key = %s LIMIT 1",
        (user_id, game_key)
    )
    newly = not already
    if newly:
        db_execute(
            "INSERT INTO minigame_scores (user_id, game_key, score) VALUES (%s::uuid, %s, 1)",
            (user_id, game_key)
        )
    rows = db_fetch_all(
        "SELECT DISTINCT game_key FROM minigame_scores WHERE user_id = %s::uuid AND game_key LIKE 'kit:%%'",
        (user_id,)
    )
    found = sorted(r[0].split(":", 1)[1] for r in rows if r[0] != "kit:complete")
    completed_now = False
    if len(found) == len(KIT_PIECES):
        done_row = db_fetch_one(
            "SELECT 1 FROM minigame_scores WHERE user_id = %s::uuid AND game_key = 'kit:complete' LIMIT 1",
            (user_id,)
        )
        if not done_row:
            db_execute(
                "INSERT INTO minigame_scores (user_id, game_key, score) VALUES (%s::uuid, 'kit:complete', 1)",
                (user_id,)
            )
            await publish_event("XPGranted", {"user_id": user_id, "amount": KIT_COMPLETE_XP, "reason": "aqueduct_kit"})
            if db_fetch_one("SELECT 1 FROM minecraft_links WHERE user_id = %s::uuid", (user_id,)):
                await publish_event("RewardCollected", {
                    "award_id": str(uuid.uuid4()), "user_id": user_id,
                    "mission_id": None, "tier": "kit",
                })
            completed_now = True
    return {
        "new": newly, "piece": piece, "piece_name": KIT_PIECES[piece],
        "found": found, "total": len(KIT_PIECES), "completed_now": completed_now,
        "complete": len(found) == len(KIT_PIECES),
    }


@app.get("/api/minigames/kit/{user_id}")
async def kit_progress(user_id: str = Depends(require_self)):
    rows = db_fetch_all(
        "SELECT DISTINCT game_key FROM minigame_scores WHERE user_id = %s::uuid AND game_key LIKE 'kit:%%'",
        (user_id,)
    )
    keys = {r[0].split(":", 1)[1] for r in rows}
    found = sorted(k for k in keys if k != "complete")
    return {
        "found": found, "total": len(KIT_PIECES),
        "pieces": KIT_PIECES, "complete": len(found) == len(KIT_PIECES),
    }


# ========== Identity: avatars & Agent Sigils ==========
# Two paths, safest first: a procedural Agent Sigil (curated glyph + hue,
# no user-generated imagery at all — always appropriate for a minors
# cohort) and an optional real photo upload. Uploads share the exact
# moderation posture GAPS.md already flags for screenshot evidence
# (teacher visibility/removal tooling needed before a real pilot) — same
# open gap, one more surface, called out there rather than hidden here.

AVATAR_MAX_BYTES = 2 * 1024 * 1024
SIGIL_GLYPHS = ["⬡", "◈", "✦", "☄", "⚙", "♜", "⟁", "◭", "⬢", "❖"]


@app.post("/api/avatar/{user_id}")
async def upload_avatar(user_id: str = Depends(require_self), file: UploadFile = File(...)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Avatars must be an image")
    data = await file.read()
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Avatar too large (2MB max)")
    object_key = f"avatars/{user_id}"
    s3_client.put_object(Bucket="default-bucket", Key=object_key, Body=data,
                         ContentType=file.content_type)
    db_execute("UPDATE users SET avatar_object_key = %s WHERE id = %s::uuid", (object_key, user_id))
    return {"status": "ok"}


@app.get("/api/avatar/{user_id}")
async def get_avatar(user_id: str):
    row = db_fetch_one("SELECT avatar_object_key FROM users WHERE id = %s::uuid", (user_id,))
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="No avatar")
    try:
        obj = s3_client.get_object(Bucket="default-bucket", Key=row[0])
        return Response(content=obj["Body"].read(),
                        media_type=obj.get("ContentType", "image/png"),
                        headers={"Cache-Control": "no-cache"})
    except Exception:
        raise HTTPException(status_code=404, detail="No avatar")


@app.delete("/api/avatar/{user_id}")
async def delete_avatar(user_id: str = Depends(require_self)):
    db_execute("UPDATE users SET avatar_object_key = NULL WHERE id = %s::uuid", (user_id,))
    return {"status": "removed"}


# ========== Field Tablet: Mission Evidence (companion.html) ==========
# One photo + one observation, filed once per (learner, mission) from the
# phone while a student is out investigating. This IS real evidence --
# goes through the exact same pipeline the desktop Operations Hub uses
# (_submit_evidence_core/_submit_reflection_core below), via
# kind='individual_evidence' -- same Kafka event, same Brightspace worker,
# same completion/XP/badge gate. No separate mobile submission system, no
# divergence between surfaces.
#
# The uploaded photo is NEVER written to storage, by design -- 2026-07-21
# revision, after finding the original design (a separate "display cache"
# S3 object holding the raw photo) carried whatever EXIF the phone attached,
# GPS location included, with no functional reason to. The photo exists
# only in memory, for exactly as long as it takes to render it into the PDF
# (_build_field_report_pdf) -- confirmed live that rendering an image onto
# a reportlab canvas re-encodes raw pixels into the PDF's image stream and
# does not carry the source JPEG's EXIF block along with it, so the one
# artifact that does get stored is already metadata-clean by construction,
# not by an extra stripping step. The PDF *is* the evidence; there's no
# separate photo to view or cache, so mission_field_reports (the old
# display-cache table) is gone -- "filed" state now reads straight from
# submissions/mission_reflections, the same tables the real pipeline
# already writes.

@app.get("/api/mission-field-report/{mission_id}")
async def get_mission_field_report(mission_id: str, user_id: str = Depends(get_current_user)):
    row = db_fetch_one(
        """SELECT s.submitted_at, r.reflection
           FROM submissions s
           JOIN mission_reflections r ON r.user_id = s.user_id AND r.mission_id = s.mission_id
           WHERE s.user_id = %s::uuid AND s.mission_id = %s::uuid AND s.kind = 'individual_evidence'
           ORDER BY s.submitted_at DESC LIMIT 1""",
        (user_id, mission_id)
    )
    if not row:
        return {"filed": False}
    return {
        "filed": True,
        "observation": row[1],
        "filed_at": row[0].isoformat() if row[0] else None,
        "pdf_url": f"/api/mission-field-report/{mission_id}/pdf",
    }


def _build_field_report_pdf(photo_bytes: bytes, observation: str, mission_title: str) -> bytes:
    """One page, styled as a real evidence document since this PDF is now
    the only stored artifact -- EVOKE Field Evidence letterhead, the
    mission and filing date, the photo (EXIF-rotated upright first --
    phone camera JPEGs carry orientation as metadata, not pixels, so
    skipping this renders sideways/upside-down photos taken in portrait),
    then the observation text, wrapped and paginated below it."""
    img = Image.open(BytesIO(photo_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    margin = 50
    accent = colors.HexColor("#0d7d74")

    def draw_letterhead(y):
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, y, "EVOKE FIELD EVIDENCE")
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 16)
        y -= 20
        c.drawString(margin, y, mission_title)
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#666666"))
        y -= 14
        c.drawString(margin, y, f"Filed {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        c.setFillColor(colors.black)
        y -= 10
        c.setStrokeColor(accent)
        c.setLineWidth(1)
        c.line(margin, y, width - margin, y)
        return y - 20

    y = draw_letterhead(height - margin)

    iw, ih = img.size
    max_w = width - 2 * margin
    max_h = height * 0.42
    scale = min(max_w / iw, max_h / ih, 1.0)
    draw_w, draw_h = iw * scale, ih * scale
    x = margin + (max_w - draw_w) / 2
    y -= draw_h
    c.drawImage(ImageReader(img), x, y, draw_w, draw_h)
    y -= 22

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(accent)
    c.drawString(margin, y, "OBSERVATION")
    c.setFillColor(colors.black)
    y -= 18

    c.setFont("Helvetica", 11)
    line_height = 15
    max_chars = 92
    for para in observation.split("\n"):
        wrapped = textwrap.wrap(para, max_chars) or [""]
        for line in wrapped:
            if y < margin:
                c.showPage()
                y = draw_letterhead(height - margin)
                c.setFont("Helvetica", 11)
            c.drawString(margin, y, line)
            y -= line_height

    c.save()
    return buf.getvalue()


@app.post("/api/mission-field-report")
async def submit_mission_field_report(
    mission_id: str = Form(...),
    photo: UploadFile = File(...),
    observation: str = Form(...),
    user_id: str = Depends(get_current_user),
):
    if not (photo.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Evidence must be a photo")
    observation = observation.strip()
    if not observation:
        raise HTTPException(status_code=400, detail="Describe your evidence before filing")

    mission_row = db_fetch_one("SELECT title FROM missions WHERE id = %s::uuid", (mission_id,))
    mission_title = mission_row[0] if mission_row else "Field Mission"

    # In memory only -- never written to storage. See this section's header
    # comment for why, and how the PDF built from it ends up clean anyway.
    photo_bytes = await photo.read()
    try:
        pdf_bytes = _build_field_report_pdf(photo_bytes, observation, mission_title)
    except Exception as e:
        logger.error(f"Field report PDF build failed: {e}")
        raise HTTPException(status_code=400, detail="Couldn't process that photo -- try a different one")

    # The real submission -- same pipeline, same Kafka event, same
    # Brightspace sync, same completion gate as the desktop Operations
    # Hub's evidence + reflection forms. This PDF is the one and only
    # copy of the evidence that gets stored anywhere.
    result = await _submit_evidence_core(
        user_id, mission_id, "individual_evidence",
        f"field-report-{mission_id}.pdf", pdf_bytes, "application/pdf"
    )
    await _submit_reflection_core(user_id, mission_id, observation)

    row = db_fetch_one(
        "SELECT submitted_at FROM submissions WHERE id = %s::uuid", (result["submission_id"],)
    )
    return {
        "filed": True,
        "observation": observation,
        "filed_at": row[0].isoformat() if row and row[0] else None,
        "pdf_url": f"/api/mission-field-report/{mission_id}/pdf",
    }


@app.get("/api/mission-field-report/{mission_id}/pdf")
async def get_mission_field_report_pdf(mission_id: str, user_id: str = Depends(get_current_user)):
    row = db_fetch_one(
        """SELECT file_path FROM submissions
           WHERE user_id = %s::uuid AND mission_id = %s::uuid AND kind = 'individual_evidence'
           ORDER BY submitted_at DESC LIMIT 1""",
        (user_id, mission_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="No field report filed for this mission")
    try:
        obj = s3_client.get_object(Bucket="default-bucket", Key=row[0])
        return Response(content=obj["Body"].read(),
                        media_type="application/pdf",
                        headers={"Cache-Control": "no-cache"})
    except Exception:
        raise HTTPException(status_code=404, detail="Report not found")


@app.post("/api/profile/{user_id}/sigil")
async def set_sigil(user_id: str = Depends(require_self), glyph: str = Form(...), hue: int = Form(...)):
    if glyph not in SIGIL_GLYPHS:
        raise HTTPException(status_code=400, detail="Pick a sigil from the curated set")
    hue = max(0, min(360, hue))
    db_execute("UPDATE users SET sigil = %s WHERE id = %s::uuid",
               (json.dumps({"glyph": glyph, "hue": hue}), user_id))
    return {"status": "ok", "sigil": {"glyph": glyph, "hue": hue}}


# ========== Field Gear ==========
def _gear_facts(user_id: str) -> dict:
    """Assemble the facts evaluate_gear() reads, all from existing sources."""
    try:
        profile = os_client.get(index="player-profile", id=user_id)["_source"]
    except Exception:
        profile = {}
    badges = profile.get("badges", {})
    powers_earned = set()
    quality_counts = {}
    qualities_earned = 0
    for quality, b in badges.items():
        count = 0
        for pkey, pstate in (b.get("powers") or {}).items():
            if pstate.get("earned"):
                powers_earned.add(pkey)
                count += 1
        quality_counts[quality] = count
        if b.get("earned"):
            qualities_earned += 1

    score_rows = db_fetch_all(
        "SELECT game_key, MAX(score) FROM minigame_scores WHERE user_id = %s::uuid GROUP BY game_key",
        (user_id,)
    )
    game_best, games_played, fragments, signal_unlocked = {}, set(), 0, False
    for game_key, best in score_rows:
        if game_key.startswith("signal:"):
            if game_key == "signal:unlocked":
                signal_unlocked = True
            else:
                fragments += 1
        else:
            game_best[game_key] = best
            games_played.add(game_key)

    linked = db_fetch_one("SELECT 1 FROM minecraft_links WHERE user_id = %s::uuid", (user_id,))
    peer_count = db_fetch_one(
        "SELECT COUNT(*) FROM peer_insights_given WHERE from_user_id = %s::uuid", (user_id,)
    )

    return {
        "level": profile.get("level", 1),
        "missions": len(profile.get("missions_completed", [])),
        "quests": len(profile.get("quests_completed", [])),
        "powers_earned": powers_earned,
        "quality_counts": quality_counts,
        "qualities_earned": qualities_earned,
        "game_best": game_best,
        "games_played": games_played,
        "fragments": fragments,
        "signal_unlocked": signal_unlocked,
        "minecraft_linked": bool(linked),
        "peer_insights": peer_count[0] if peer_count else 0,
    }


@app.get("/api/gear/{user_id}")
async def get_gear(user_id: str):
    """Full catalog with unlocked flags + the user's equipped selection.
    Unlocks are computed at read time from existing facts, so they can
    never drift from the truth (see evoke/gear.py)."""
    facts = _gear_facts(user_id)
    items = gear_catalog.evaluate_gear(facts)
    row = db_fetch_one("SELECT equipped_gear, sigil, avatar_object_key FROM users WHERE id = %s::uuid", (user_id,))
    equipped = json.loads(row[0]) if row and row[0] else []
    unlocked_keys = {i["key"] for i in items if i["unlocked"]}
    equipped = [k for k in equipped if k in unlocked_keys]  # never display gear that's no longer earned
    best_sim_score = max(facts["game_best"].values()) if facts["game_best"] else None
    return {
        "gear": items,
        "equipped": equipped,
        "unlocked_count": len(unlocked_keys),
        "total": len(items),
        "sigil": json.loads(row[1]) if row and row[1] else None,
        "has_avatar": bool(row and row[2]),
        "next_unlock": gear_catalog.pick_next_unlock(items),
        "best_sim_score": best_sim_score,
    }


@app.post("/api/gear/{user_id}/equip")
async def equip_gear(user_id: str = Depends(require_self), keys: str = Form(...)):
    """Equip up to 3 unlocked gear items for display on the Dossier."""
    try:
        wanted = [k for k in json.loads(keys) if isinstance(k, str)][:3]
    except Exception:
        raise HTTPException(status_code=400, detail="keys must be a JSON list")
    unlocked = {i["key"] for i in gear_catalog.evaluate_gear(_gear_facts(user_id)) if i["unlocked"]}
    invalid = [k for k in wanted if k not in unlocked]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Not unlocked: {', '.join(invalid)}")
    db_execute("UPDATE users SET equipped_gear = %s WHERE id = %s::uuid", (json.dumps(wanted), user_id))
    return {"status": "equipped", "equipped": wanted}


# ========== Static Files ==========
# Resolved relative to this file, not the process's working directory --
# CWD is /app (so main.py can import itself as the evoke.* package, per the
# Dockerfile), but the actual static/ directory lives at /app/evoke/static.
# A CWD-relative check here silently mounted nothing and every request to
# "/" 404'd, which broke serving the SPA built for this build step (steps 1
# and 2's Dockerfile fix for the package-import issue introduced this
# regression without anyone noticing until the SPA was actually loaded).
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Evoke Admin's own small static bundle (login form + mission sync/edit
# dashboard, see static/admin/admin.js) -- a separate page from the
# learner-facing SPA, not a route inside it, so it never touches
# controller.js's Brightspace-gated boot path. Signs in via
# POST /api/admin/login, independent of AUTH_PROVIDER entirely. Must be
# mounted before the root "/" mount below -- Starlette matches mounts in
# registration order, and a "/" mount matches every path, so it would
# swallow "/admin/*" requests if it were registered first.
_admin_static_dir = os.path.join(_static_dir, "admin")
if os.path.exists(_admin_static_dir):
    app.mount("/admin", StaticFiles(directory=_admin_static_dir, html=True), name="admin-static")

if os.path.exists(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

# ========== Background Workers ==========
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(evoke_workers_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

import os
import json
import datetime
import asyncio
import random
import re
import uuid
import hashlib
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

from evoke.clients import s3_client, os_client, get_producer
from evoke.workers import evoke_workers_loop
from evoke.lms import get_brightspace_lms
from evoke.lti import BrightspaceLTIProvider
from evoke import skills_framework, progression, world_state, gear as gear_catalog
from evoke.live import live_hub
from evoke.identity import get_or_create_evoke_player

logger = logging.getLogger(__name__)

# ========== Configuration ==========
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://evoke:devsecret123@localhost:5432/evoke")
BRIGHTSPACE_SIM_URL = os.getenv("BRIGHTSPACE_SIM_URL", "http://brightspace-sim:8001")
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://open-webui:8080")
# OpenWebUI requires auth on every API call (this wasn't true when
# billbot_chat() below was first written, which is why it originally sent
# none -- it silently 401'd until evoke-infra/openwebui-bootstrap.py's
# smoke test surfaced it). A per-instance service API key, not a user
# session JWT (which expires) -- generate one via that bootstrap script.
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
# The internal container hostname (MINECRAFT_HOST) is for the app/bridge's
# own RCON traffic -- not reachable from a learner's actual Minecraft
# client. This is the address a real player types into their client,
# separately configurable since it has to be a real public host once this
# runs on a cohort instance (see HOSTING_COST_MODEL.md's domain scheme:
# {cohort-slug}.mc.<root-domain>). Defaults assume same-machine local dev.
MINECRAFT_PUBLIC_HOST = os.getenv("MINECRAFT_PUBLIC_HOST", "localhost")
MINECRAFT_PUBLIC_PORT_JAVA = os.getenv("MINECRAFT_PUBLIC_PORT_JAVA", "25565")
MINECRAFT_PUBLIC_PORT_BEDROCK = os.getenv("MINECRAFT_PUBLIC_PORT_BEDROCK", "19132")

# Brightspace integration (adapter or simulator)
BRIGHTSPACE_SIMULATOR_MODE = os.getenv("BRIGHTSPACE_SIMULATOR_MODE", "true").lower() == "true"
BRIGHTSPACE_TENANT_URL = os.getenv("BRIGHTSPACE_TENANT_URL")
BRIGHTSPACE_APP_KEY = os.getenv("BRIGHTSPACE_APP_KEY")
BRIGHTSPACE_APP_SECRET = os.getenv("BRIGHTSPACE_APP_SECRET")
BRIGHTSPACE_ORG_UNIT_ID = os.getenv("BRIGHTSPACE_ORG_UNIT_ID")

# ========== Database Pool ==========
db_pool = SimpleConnectionPool(1, 20, DATABASE_URL)
async_db_pool: Optional[asyncpg.Pool] = None
brightspace_lms = None
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

# ========== Mission Catalog Sync ==========
async def sync_missions_from_lms():
    """The LMS (brightspace-sim now; real Brightspace later) is the system
    of record for the mission catalog -- this pulls its assignment list and
    upserts EVOKE's missions table, keyed by (campaign_id, lms_assignment_ref)
    (see the UNIQUE constraint added in init-db.sql). Postgres becomes a
    synced cache, not an independent catalog: missions are no longer seeded
    directly (see evoke-infra/seed.py). Sim-only for this build pass, per
    BUILD_PLAN.md's non-goals -- a real-Brightspace path would call the
    equivalent authenticated BrightspaceLMS method instead of hitting
    BRIGHTSPACE_SIM_URL directly."""
    campaign_row = db_fetch_one("SELECT id FROM campaigns WHERE key = 'evoke-prosperity'")
    if not campaign_row:
        logger.warning("Mission sync skipped: no 'evoke-prosperity' campaign found")
        return
    campaign_id = campaign_row[0]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BRIGHTSPACE_SIM_URL}/d2l/api/lp/1.96/dropbox/assignments", timeout=10
            )
            response.raise_for_status()
            assignments = response.json().get("Assignments", [])
    except Exception as e:
        logger.error(f"Mission sync failed (LMS unreachable, keeping existing missions): {e}")
        return

    synced = 0
    for assignment in assignments:
        fields = assignment.get("CustomFields", {})
        db_execute(
            """INSERT INTO missions
               (id, campaign_id, lms_assignment_ref, week, sequence, title, arc,
                superpower, primary_skill, secondary_skill, pfl_domain, mission_brief_md,
                pbl_description, evidence_requirements_md)
               VALUES (gen_random_uuid(), %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (campaign_id, lms_assignment_ref) DO UPDATE SET
                   week = EXCLUDED.week, sequence = EXCLUDED.sequence, title = EXCLUDED.title,
                   arc = EXCLUDED.arc, superpower = EXCLUDED.superpower,
                   primary_skill = EXCLUDED.primary_skill, secondary_skill = EXCLUDED.secondary_skill,
                   pfl_domain = EXCLUDED.pfl_domain, mission_brief_md = EXCLUDED.mission_brief_md,
                   pbl_description = EXCLUDED.pbl_description,
                   evidence_requirements_md = EXCLUDED.evidence_requirements_md""",
            (
                campaign_id, assignment["AssignmentId"], fields.get("Week"), fields.get("Sequence"),
                assignment["Name"], fields.get("Arc"), fields.get("Superpower"),
                fields.get("PrimarySkill"), fields.get("SecondarySkill"), fields.get("PflDomain"),
                fields.get("Description"),
                # pbl_description holds the full "Evoke Mission (direct to
                # students)" narrative (the "Your Mission" framing + Step
                # 1/2/3) -- not literally the docx's separate, instructor-
                # facing "Activity (PBL Description)" paragraph, which is
                # what the column name suggests. Reusing this existing,
                # previously-unpopulated column rather than adding a new one
                # for content that's genuinely the richer version of the
                # same "what is this mission" idea `mission_brief_md` (the
                # short summary) already carries.
                fields.get("MissionNarrative"),
                fields.get("EvidenceRequirements"),
            )
        )
        synced += 1

    # Per GAME_DESIGN.md §6.1 ("Mission 1: the entire Basin is open") and
    # the now-resolved mission-ordering gap in GAPS.md, week 1/sequence 1 is
    # the only mission released by default -- every other mission needs an
    # admin to manually release it (POST /api/admin/missions/{id}/release).
    # Only touches missions that have never been released, so re-running
    # this sync never re-locks something an admin already opened.
    db_execute(
        """UPDATE missions SET released_at = CURRENT_TIMESTAMP
           WHERE campaign_id = %s::uuid AND week = 1 AND sequence = 1 AND released_at IS NULL""",
        (campaign_id,)
    )

    logger.info(f"Mission sync complete: {synced} assignments synced from LMS")


# ========== Startup/Shutdown ==========
@app.on_event("startup")
async def startup():
    """Initialize async database pool, Brightspace adapter, and LTI provider"""
    global async_db_pool, brightspace_lms, brightspace_lti

    try:
        # Create async database pool for BrightspaceLMS and LTI
        async_db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
        logger.info("Async database pool created")

        # Initialize Brightspace adapter (real or simulator mode)
        if not BRIGHTSPACE_SIMULATOR_MODE and BRIGHTSPACE_TENANT_URL:
            brightspace_lms = get_brightspace_lms(async_db_pool)
            if brightspace_lms:
                logger.info(f"BrightspaceLMS adapter initialized for {BRIGHTSPACE_TENANT_URL}")
            else:
                logger.warning("Brightspace adapter not configured, falling back to simulator")
        else:
            logger.info("Using Brightspace simulator mode")

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

        await sync_missions_from_lms()

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
        # evoke/identity.py's get_or_create_evoke_player needs this for its
        # ON CONFLICT (email, org_id) clause -- found live (2026-07-16) that
        # it never actually existed, so LTI auto-provisioning of a genuinely
        # new user always 500'd. init-db.sql has it inline for fresh volumes;
        # this is the same fix for a volume that predates that.
        db_execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_org_unique ON users(email, org_id)")
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

        # Wave 3 (BUILD_PLAN_2.md): admin-configurable stages, daily
        # reflections (Words of Wisdom), phone pairing tokens, and the
        # two-channel Minecraft link codes.
        # Stage is instructor pedagogy config, not LMS data -- lives on
        # EVOKE's side of the sync and defaults to the mission's week so a
        # fresh install has a sensible grouping without any admin work.
        db_execute("ALTER TABLE missions ADD COLUMN IF NOT EXISTS stage INTEGER")
        db_execute("UPDATE missions SET stage = week WHERE stage IS NULL")
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
    """Close database pool and Brightspace adapter"""
    global async_db_pool, brightspace_lms

    if async_db_pool:
        await async_db_pool.close()
        logger.info("Async database pool closed")

    if brightspace_lms:
        await brightspace_lms.close()
        logger.info("BrightspaceLMS adapter closed")

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
    producer.send('evoke-events', value=event)
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
@app.post("/api/login")
async def login(email: str, password: str):
    """Dev login - returns a session token"""
    # Simple dev auth
    try:
        result = db_fetch_one(
            "SELECT u.id, u.display_name FROM users u JOIN auth_identities ai ON u.id = ai.user_id WHERE u.email = %s AND ai.provider = 'local'",
            (email,)
        )
        if result:
            user_id, display_name = result
            return {
                "user_id": str(user_id),
                "display_name": display_name,
                "email": email,
                "session_token": str(uuid.uuid4())
            }
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/dev-login")
async def dev_login(user_id: Optional[str] = None, email: Optional[str] = None):
    """Dev mode auto-login. No params: deterministically Player One, the
    default learner-facing identity -- previously `LIMIT 1` with no
    ORDER BY, which picked "whichever row sorts first" rather than a
    specific, intentional user. `email` param: an explicit way to log in
    as a specific seeded user (e.g. ?email=admin@evoke.local for Admin,
    which has no in-app UI switcher and no role check on #/admin yet)."""
    if user_id:
        result = db_fetch_one("SELECT display_name, email FROM users WHERE id = %s::uuid", (user_id,))
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        display_name, email = result
    elif email:
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

    return {
        "user_id": user_id,
        "display_name": display_name,
        "email": email,
        "session_token": str(uuid.uuid4())
    }

# ========== Identity Management ==========
class LinkBrightspaceRequest(BaseModel):
    evoke_user_id: str
    brightspace_user_id: int
    brightspace_access_token: str

class LinkMinecraftRequest(BaseModel):
    evoke_user_id: str
    minecraft_uuid: str
    minecraft_username: str

@app.post("/api/identity/link-brightspace")
async def link_brightspace_identity(request: LinkBrightspaceRequest):
    """Link EVOKE user to Brightspace user ID and verify token"""
    try:
        # Verify token with Brightspace simulator
        async with httpx.AsyncClient() as client:
            verify_response = await client.get(
                f"{BRIGHTSPACE_SIM_URL}/d2l/api/lp/1.96/users/whoami",
                headers={"Authorization": f"Bearer {request.brightspace_access_token}"}
            )
            if verify_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Brightspace token")

        # Create or update identity mapping
        db_execute(
            """INSERT INTO evoke_identities (user_id, brightspace_user_id)
               VALUES (%s::uuid, %s)
               ON CONFLICT (brightspace_user_id) DO UPDATE
               SET updated_at = CURRENT_TIMESTAMP""",
            (request.evoke_user_id, request.brightspace_user_id)
        )

        return {
            "evoke_user_id": request.evoke_user_id,
            "brightspace_user_id": request.brightspace_user_id,
            "status": "linked"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Identity linking failed: {str(e)}")

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
async def get_identity(evoke_user_id: str):
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

        # Set session token in HTTP-only cookie
        # Browser will include this in all subsequent requests
        redirect_response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,  # Prevent JavaScript access (XSS protection)
            secure=True,    # HTTPS only (enforce in production)
            samesite="Lax", # CSRF protection
            max_age=86400,  # 24 hours
        )

        # Also set user info cookie (readable by frontend)
        redirect_response.set_cookie(
            key="user_id",
            value=user_dict["user_id"],
            httponly=False,  # Allow frontend to read
            secure=True,
            samesite="Lax",
            max_age=86400,
        )

        redirect_response.set_cookie(
            key="user_display_name",
            value=user_dict["display_name"],
            httponly=False,
            secure=True,
            samesite="Lax",
            max_age=86400,
        )

        return redirect_response

    except Exception as e:
        logger.error(f"LTI launch error: {e}")
        raise HTTPException(status_code=400, detail=f"LTI launch failed: {str(e)}")

@app.get("/api/lti/launch/callback")
async def lti_launch_callback(session_token: str = None):
    """
    Optional callback endpoint after LTI launch.

    If the client needs JSON instead of redirect, call this endpoint
    with the session_token received from the launch form submission.

    Returns:
    {
        "status": "success",
        "session_token": "...",
        "redirect_to": "/api/missions"
    }
    """
    if not session_token:
        raise HTTPException(status_code=400, detail="Missing session_token")

    # Could validate the token here if needed
    return {
        "status": "success",
        "session_token": session_token,
        "redirect_to": "/api/missions"
    }

@app.get("/api/session/validate")
async def validate_session(session_token: str = None):
    """
    Validate and get session info.

    Called by frontend to check if session is valid and get user info.

    Returns user info if valid, 401 if invalid.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="No session token")

    # In production, would validate token against database/cache
    # For now, accept any non-empty token as valid
    # Could enhance with session store (Redis, DB, etc.)

    logger.debug(f"Session validated for token {session_token[:8]}...")

    return {
        "status": "valid",
        "session_token": session_token,
        "message": "Session is active"
    }

@app.post("/api/session/logout")
async def logout_session(response: Response):
    """
    Logout and clear session cookies.

    Returns:
    {
        "status": "success",
        "message": "Logged out"
    }
    """
    # Clear session cookies
    response.delete_cookie("session_token")
    response.delete_cookie("user_id")
    response.delete_cookie("user_display_name")

    logger.info("User logged out")

    return {
        "status": "success",
        "message": "Logged out successfully"
    }

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
    if not brightspace_lms:
        logger.warning("Grade webhook received but Brightspace LMS not configured")
        return {"status": "warning", "message": "Brightspace LMS not configured"}

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

        # Update submission with grade
        db_execute(
            """UPDATE submissions SET grade = %s, feedback = %s, graded_at = CURRENT_TIMESTAMP
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

            # Sync badge to Brightspace
            try:
                await brightspace_lms.push_badge_award(
                    evoke_user_id=evoke_user_id,
                    badge_id=badge_id,
                    campaign_id=campaign_id,
                    criteria=f"Teacher graded submission: {grade}/100",
                    evidence=f"Submission ID: {submission_id}"
                )
                logger.info(f"Award {tier} synced to Brightspace for user {evoke_user_id}")
            except Exception as e:
                logger.error(f"Failed to sync award to Brightspace: {e}")
                # Continue anyway - award created locally

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

@app.get("/api/webhooks/brightspace/poll")
async def poll_brightspace_grades():
    """
    Polling fallback for Brightspace grades.

    If Brightspace doesn't support webhooks, call this endpoint periodically
    (e.g., every 5 minutes) to fetch new grades and sync them.

    This is a backup mechanism; webhooks are preferred.

    Returns count of grades synced.
    """
    if not brightspace_lms:
        return {"status": "error", "message": "Brightspace LMS not configured"}

    try:
        # Find ungraded submissions
        ungraded = db_fetch_all(
            """SELECT s.id, s.user_id, s.mission_id, s.brightspace_submission_id
               FROM submissions s
               WHERE s.status = 'submitted' AND s.grade IS NULL
               AND s.brightspace_submission_id IS NOT NULL
               LIMIT 100"""
        )

        if not ungraded:
            return {"status": "success", "count": 0, "message": "No ungraded submissions"}

        synced_count = 0

        for submission_id, user_id, mission_id, bs_sub_id in ungraded:
            try:
                # Get mission's assignment ID
                mission = db_fetch_one(
                    "SELECT brightspace_assignment_id FROM mission_brightspace_mapping WHERE mission_id = %s::uuid LIMIT 1",
                    (mission_id,)
                )

                if not mission:
                    logger.warning(f"No assignment mapping for mission {mission_id}")
                    continue

                assignment_id = mission[0]

                # Poll Brightspace for submissions
                submissions = await brightspace_lms.get_submissions_for_assignment(assignment_id)

                if not submissions:
                    continue

                # Find matching submission
                for bs_sub in submissions:
                    if bs_sub.get("SubmissionId") == bs_sub_id:
                        grade = bs_sub.get("Grade")
                        feedback = bs_sub.get("Feedback", "")

                        if grade is not None:
                            # Update EVOKE submission
                            db_execute(
                                """UPDATE submissions SET grade = %s, feedback = %s, graded_at = CURRENT_TIMESTAMP
                                   WHERE id = %s::uuid""",
                                (grade, feedback, submission_id)
                            )
                            synced_count += 1
                            logger.info(f"Polled grade: submission {submission_id}, grade {grade}")
                        break

            except Exception as e:
                logger.error(f"Error polling submission {submission_id}: {e}")
                continue

        return {
            "status": "success",
            "count": synced_count,
            "message": f"Synced {synced_count} grades from Brightspace"
        }

    except Exception as e:
        logger.error(f"Grade polling error: {e}")
        return {"status": "error", "message": str(e)}

# ========== Mission API ==========
@app.get("/api/missions")
async def list_missions(user_id: str):
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
                      pbl_description, evidence_requirements_md
               FROM missions WHERE campaign_id = %s::uuid ORDER BY week, sequence""",
            (campaign_id,)
        )

        missions = []
        for mission in missions_data:
            mission_id, title, week, arc, superpower, brief, released_at, pbl_description, evidence_requirements = mission

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
async def admin_list_missions(user_id: str):
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
            """SELECT id, title, week, sequence, arc, released_at, stage
               FROM missions WHERE campaign_id = %s::uuid ORDER BY week, sequence""",
            (org_result[0],)
        )
        return {"missions": [{
            "id": str(m[0]), "title": m[1], "week": m[2], "sequence": m[3], "arc": m[4],
            "released": m[5] is not None,
            "released_at": m[5].isoformat() if m[5] else None,
            "stage": m[6],
        } for m in missions_data]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/missions/{mission_id}/release")
async def admin_release_mission(mission_id: str):
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
async def admin_unrelease_mission(mission_id: str):
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

    evidence = db_fetch_one(
        "SELECT 1 FROM submissions WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product' LIMIT 1",
        (team_id, mission_id)
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

    # Get campaign for badge mapping
    campaign_id = db_fetch_one(
        "SELECT active_campaign_id FROM organizations o JOIN users u ON u.org_id = o.id WHERE u.id = %s::uuid",
        (user_id,)
    )
    if campaign_id:
        campaign_id = campaign_id[0]

        # Get common tier badge for this campaign
        badge_id = db_fetch_one(
            "SELECT id FROM badges WHERE campaign_id = %s::uuid AND key = 'common-tier' LIMIT 1",
            (campaign_id,)
        )

        # Sync badge to Brightspace if adapter available
        if brightspace_lms and badge_id:
            try:
                await brightspace_lms.push_badge_award(
                    evoke_user_id=user_id,
                    badge_id=badge_id[0],
                    campaign_id=campaign_id,
                    criteria="Completed mission (team evidence + reflection)",
                    evidence=f"Mission ID: {mission_id}"
                )
                logger.info(f"Badge synced to Brightspace for user {user_id}")
            except Exception as e:
                logger.error(f"Badge sync failed: {e}")

    # Publish AwardGranted event
    await publish_event("AwardGranted", {
        "award_id": award_id,
        "user_id": user_id,
        "mission_id": mission_id,
        "tier": "common",
        "source": "submission"
    })

    # Team evidence + your own reflection is what "completes" a mission for
    # badge/count purposes -- later AI/teacher award tiers (trigger_ai_review/
    # brightspace_review) are quality upgrades on an already-completed
    # mission, not separate completions, so MissionCompleted/BadgeAwarded
    # only fire here.
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


@app.post("/api/submit-evidence")
async def submit_evidence(
    user_id: str = Form(...),
    mission_id: str = Form(...),
    file: UploadFile = File(...),
    kind: str = Form("team_product"),
):
    """Submit evidence for a mission. `kind='team_product'` (default) is the
    TEAM's shared artifact -- any member can call it, and it closes the
    completion AND-gate (see _complete_mission_for_user) for any teammate who
    already reflected. `kind='individual_task'` is a learner's own piece
    (Submission Redesign doc, missions 1-4): stored + hash-recorded for the
    roster/assessment, but it does not fire team-completion effects."""
    if kind not in ("team_product", "individual_task"):
        raise HTTPException(status_code=400, detail="kind must be 'team_product' or 'individual_task'")
    try:
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
            raise HTTPException(status_code=400, detail="You're not on a team yet -- ask an admin to assign you one")

        submission_id = str(uuid.uuid4())

        # Revise-and-resubmit is a first-class path (GAPS.md #3): a later
        # submission of the same TEAM's evidence re-runs the AI review
        # (which can upgrade the award tier) but must NOT re-fire the
        # one-time completion effects for anyone already completed --
        # previously every resubmission re-published MissionCompleted/
        # XPGranted/BadgeAwarded and duplicate AwardGranted feed events,
        # which both spammed the feed and made resubmission an infinite
        # +100 XP faucet.
        # Resubmission is scoped to the team's PRODUCT (the shared artifact that
        # drives AI review + completion); individual-task and per-member product
        # uploads don't count against the team-product first-submission guard.
        prior = db_fetch_one(
            "SELECT 1 FROM submissions WHERE team_id = %s::uuid AND mission_id = %s::uuid AND kind = 'team_product' LIMIT 1",
            (team_id, mission_id)
        )
        is_resubmission = bool(prior)

        # Store file in MinIO
        file_bytes = await file.read()
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        object_key = f"evoke-evidence/{mission_id}/{kind}/{user_id}_{file.filename}"
        s3_client.put_object(
            Bucket="default-bucket",
            Key=object_key,
            Body=file_bytes,
            ContentType=file.content_type or "application/octet-stream"
        )

        # Create submission record. content_hash lets the roster flag whether
        # each member turned in the SAME team file (Option A hash-check).
        db_execute(
            """INSERT INTO submissions (id, user_id, mission_id, team_id, file_path, status, kind, content_hash)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, 'submitted', %s, %s)""",
            (submission_id, user_id, mission_id, team_id, object_key, kind, content_hash)
        )

        # An individual task is a learner's own piece -- store it and stop.
        # No Brightspace team sync, no AI team review, no completion effects.
        if kind == "individual_task":
            return {"status": "success", "submission_id": submission_id, "kind": kind}

        # Sync to Brightspace if adapter available
        if brightspace_lms:
            try:
                bs_id = await brightspace_lms.submit_assignment(
                    evoke_user_id=user_id,
                    mission_id=mission_id,
                    file_name=file.filename,
                    file_content=file_bytes,
                    submission_id=submission_id
                )
                if bs_id:
                    logger.info(f"Submission synced to Brightspace: {bs_id}")
            except Exception as e:
                logger.error(f"Brightspace sync failed: {e}")
                # Continue anyway - submission stored locally
        else:
            # Fallback: use simulator for demo. This used to always post to
            # the sim's "m1" dropbox regardless of which mission was actually
            # submitted, and sent a JSON body to an endpoint that only
            # accepts form fields (submit_to_dropbox's Form(...) params) --
            # meaning this call has always 422'd and been silently swallowed
            # by the except below. Fixed: resolve the mission's real
            # lms_assignment_ref and post as form data with the field names
            # the sim endpoint actually expects.
            mission_ref = db_fetch_one(
                "SELECT lms_assignment_ref FROM missions WHERE id = %s::uuid", (mission_id,)
            )
            assignment_ref = mission_ref[0] if mission_ref and mission_ref[0] else mission_id

            # The sim's dropbox just stores whatever 'user_id' string it's
            # given, without validating it -- so passing EVOKE's own UUID
            # (as this used to) "worked" for storing the submission, but
            # broke the round trip: grading later echoes that same value
            # back as UserId, and the grading webhook needs a real
            # Brightspace-native numeric ID to resolve back to an EVOKE
            # user via evoke_identities. Resolve it here instead.
            bs_identity = db_fetch_one(
                "SELECT brightspace_user_id FROM evoke_identities WHERE user_id = %s::uuid", (user_id,)
            )
            brightspace_user_id = bs_identity[0] if bs_identity and bs_identity[0] else None

            if brightspace_user_id is not None:
                async with httpx.AsyncClient() as client:
                    try:
                        # The sim's dropbox endpoint requires a real bearer
                        # token (previously this call sent none at all and
                        # would have 401'd even after fixing the encoding
                        # above). This pass doesn't model true per-learner
                        # OAuth for the demo/sim path -- acquiring a token via
                        # the sim's own login as a fixed service identity,
                        # since the sim accepts any password for its seeded
                        # users (matching how a real integration would use a
                        # service account, not a per-learner login, for
                        # server-to-server calls).
                        token_response = await client.post(
                            f"{BRIGHTSPACE_SIM_URL}/oauth2/token",
                            data={"grant_type": "password", "username": "teacher@evoke.local", "password": "sim-demo"}
                        )
                        sim_token = token_response.json().get("access_token") if token_response.status_code == 200 else None

                        if sim_token:
                            await client.post(
                                f"{BRIGHTSPACE_SIM_URL}/d2l/api/lp/1.96/dropbox/{assignment_ref}/submissions",
                                data={
                                    "user_id": str(brightspace_user_id),
                                    "file_name": file.filename,
                                    "file_content": object_key
                                },
                                headers={"Authorization": f"Bearer {sim_token}"}
                            )
                    except Exception as e:
                        logger.warning(f"Simulator sync failed (non-blocking): {e}")
            else:
                logger.info(f"No Brightspace identity linked for {user_id}; skipping sim dropbox sync")

        team_members = _team_member_ids(team_id)

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
            "filename": file.filename
        })

        if is_resubmission:
            # Re-run the AI review (the upgrade path), skip every one-time
            # completion effect, and tell the client which case this was.
            if AI_ENABLED:
                await trigger_ai_review(team_id, mission_id, object_key)
            return {"status": "success", "submission_id": submission_id, "resubmission": True}

        # Evidence alone doesn't complete anyone's mission -- only close the
        # gate for teammates who already reflected before this landed.
        # Teammates who haven't reflected yet complete later, from
        # submit-reflection, when they do.
        if AI_ENABLED:
            await trigger_ai_review(team_id, mission_id, object_key)

        for member_id in team_members:
            await _complete_mission_for_user(member_id, mission_id, team_id)

        return {
            "status": "success",
            "submission_id": submission_id,
            "resubmission": False
        }
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
async def submission_state(user_id: str, mission_id: str):
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
async def post_team_discussion(body: TeamDiscussionPost):
    """Add a message to the team's in-app discussion thread for a mission."""
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
async def get_team_discussion(user_id: str, mission_id: str):
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


@app.post("/api/submit-reflection")
async def submit_reflection(
    user_id: str = Form(...),
    mission_id: str = Form(...),
    reflection: str = Form(...),
):
    """An individual team member's own reflection on a mission -- always
    personal, always available regardless of who submitted the team's
    evidence. Closes the completion AND-gate for this one user if the
    team's evidence already exists (see _complete_mission_for_user)."""
    try:
        mission_release = db_fetch_one(
            "SELECT released_at FROM missions WHERE id = %s::uuid", (mission_id,)
        )
        if not mission_release or mission_release[0] is None:
            raise HTTPException(status_code=403, detail="This mission hasn't been released yet")

        team_id = _get_user_team(user_id)
        if not team_id:
            raise HTTPException(status_code=400, detail="You're not on a team yet -- ask an admin to assign you one")

        db_execute(
            """INSERT INTO mission_reflections (user_id, mission_id, team_id, reflection)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
               ON CONFLICT (user_id, mission_id) DO UPDATE SET reflection = EXCLUDED.reflection""",
            (user_id, mission_id, team_id, reflection)
        )

        await _complete_mission_for_user(user_id, mission_id, team_id)

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit reflection error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


async def trigger_ai_review(team_id: str, mission_id: str, object_key: str):
    """Trigger AI review of the team's shared evidence. One judgment for
    the team; the resulting epic-tier award fans out to every member who's
    actually completed the mission (has a common/submission award) --
    members who haven't reflected yet aren't awarded anything here either,
    same AND-gate as the common tier."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENWEBUI_URL}/api/chat/completions",
                headers={"Authorization": f"Bearer {OPENWEBUI_API_KEY}"} if OPENWEBUI_API_KEY else {},
                json={
                    "model": "billbot",
                    "messages": [
                        {"role": "user", "content": f"Review this mission submission for consistency: {object_key}"}
                    ]
                },
                # See billbot_chat()'s identical timeout note -- a cold model
                # load on this same backend measured up to ~60s.
                timeout=90
            )
            if response.status_code != 200:
                # This exact bug (no auth header sent -> silent 401, this
                # whole branch skipped, no exception, nothing logged, no
                # epic award ever granted) went unnoticed here even after
                # fixing the identical issue in billbot_chat() -- this
                # sibling function makes the same OpenWebUI call and was
                # never touched. Logging now so a repeat doesn't stay silent.
                logger.warning(f"AI review failed: HTTP {response.status_code} {response.text[:300]}")

            if response.status_code == 200:
                # Assume consistent for now - in real implementation, parse response
                completed_members = db_fetch_all(
                    "SELECT DISTINCT user_id FROM awards WHERE mission_id = %s::uuid AND source = 'submission' AND user_id = ANY(SELECT user_id FROM team_members WHERE team_id = %s::uuid)",
                    (mission_id, team_id)
                )
                for (member_id,) in completed_members:
                    member_id = str(member_id)
                    award_id = str(uuid.uuid4())
                    db_execute(
                        """INSERT INTO awards (id, user_id, mission_id, tier, source, awarded_at)
                           VALUES (%s::uuid, %s::uuid, %s::uuid, 'epic', 'ai_review', CURRENT_TIMESTAMP)
                           ON CONFLICT (user_id, mission_id, tier, source) DO NOTHING""",
                        (award_id, member_id, mission_id)
                    )

                    await publish_event("AwardGranted", {
                        "award_id": award_id,
                        "user_id": member_id,
                        "mission_id": mission_id,
                        "tier": "epic",
                        "source": "ai_review"
                    })

                    notification_id = str(uuid.uuid4())
                    award_id_from_db = db_fetch_one(
                        "SELECT id FROM awards WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = 'epic' AND source = 'ai_review' LIMIT 1",
                        (member_id, mission_id)
                    )
                    if award_id_from_db:
                        db_execute(
                            "INSERT INTO notifications (id, user_id, award_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
                            (notification_id, member_id, award_id_from_db[0])
                        )
    except Exception as e:
        print(f"AI review error: {e}")

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
async def get_notifications(user_id: str):
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
async def get_guide_overlay(user_id: str):
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
async def get_awards(user_id: str):
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
async def collect_award(award_id: str, user_id: str):
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
async def get_player_profile(user_id: str):
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
async def get_achievements(user_id: str):
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
async def checkin(user_id: str):
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
async def get_submission(user_id: str, mission_id: str):
    """The learner's own reflection for one mission -- text, when it was
    submitted. Feeds the Vault retrospective screen, which needed a way to
    show what the learner actually wrote, not just the timeline's
    system-generated insights. Reflections are personal (mission_reflections)
    even though the evidence file itself is team-owned (submissions)."""
    row = db_fetch_one(
        """SELECT reflection, submitted_at FROM mission_reflections
           WHERE user_id = %s::uuid AND mission_id = %s::uuid""",
        (user_id, mission_id)
    )
    if not row:
        return {"submitted": False}
    return {
        "submitted": True,
        "reflection": row[0],
        "submitted_at": row[1].isoformat() if row[1] else None,
        "status": "submitted",
    }


# ========== Timeline ==========
@app.get("/api/timeline/{user_id}/{mission_id}")
async def get_timeline(user_id: str, mission_id: str):
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
    from_user_id: str,
    text: str = Form(...),
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
    }


@app.post("/api/minecraft/link")
async def link_minecraft(user_id: str, minecraft_username: str):
    """Link a user to a Minecraft account"""
    try:
        db_execute(
            """INSERT INTO minecraft_links (user_id, server_id, minecraft_username)
               VALUES (%s::uuid, 'default', %s)
               ON CONFLICT (user_id, server_id) DO UPDATE SET minecraft_username = EXCLUDED.minecraft_username""",
            (user_id, minecraft_username)
        )
        return {"status": "linked", "username": minecraft_username}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/minecraft/link/{user_id}")
async def get_minecraft_link(user_id: str):
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
    user_id: str,
    observation_text: str = Form(None),
    screenshot: UploadFile = File(None)
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
async def billbot_chat(user_id: str, message: str):
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
                f"{OPENWEBUI_URL}/api/chat/completions",
                headers={"Authorization": f"Bearer {OPENWEBUI_API_KEY}"} if OPENWEBUI_API_KEY else {},
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
async def get_arena_progress(user_id: str):
    """Claude's Halyard Mob Arena best-wave reached -- bridge-owned table
    (see check_arena_progress in bridge.py), read-only here."""
    row = db_fetch_one("SELECT best_wave FROM mc_arena_best WHERE user_id = %s::uuid", (user_id,))
    return {"best_wave": row[0] if row else 0}


@app.get("/api/mc-gauntlet/{user_id}")
async def get_gauntlet_progress(user_id: str):
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


@app.get("/api/companion/info")
async def companion_info(request: Request, hint_host: Optional[str] = None):
    url = _companion_url(request, hint_host)
    return {"url": url, "scannable": not url.startswith("http://localhost") and not url.startswith("http://127.")}


@app.get("/api/companion/qr.svg")
async def companion_qr(request: Request, user_id: Optional[str] = None, hint_host: Optional[str] = None):
    import io
    import qrcode
    import qrcode.image.svg
    url = _companion_url(request, hint_host)
    if user_id:
        # Pairing token (BUILD_PLAN_2 §7): the QR registers the phone as
        # the logged-in web user, no login. Single-use, 10-min expiry,
        # a fresh token per render.
        token = str(uuid.uuid4())
        try:
            db_execute(
                "INSERT INTO pairing_tokens (token, user_id) VALUES (%s::uuid, %s::uuid)",
                (token, user_id)
            )
            url += f"?pair={token}"
        except Exception as e:
            logger.warning(f"Pairing token mint failed (QR stays unpaired): {e}")
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
async def submit_minigame_score(game_key: str, user_id: str, score: int = Form(...)):
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
async def minigame_leaderboard(game_key: str, user_id: Optional[str] = None, limit: int = 10):
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
async def collect_signal_fragment(user_id: str, fragment: str = Form(...)):
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
async def signal_progress(user_id: str):
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
async def admin_cohort(user_id: str):
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

async def _fetch_classlist():
    """Real adapter in production mode; the simulator's own classlist call
    (same service-account-token pattern submit_evidence's fallback already
    uses) when brightspace_lms is None."""
    if brightspace_lms:
        return await brightspace_lms.get_classlist()
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            f"{BRIGHTSPACE_SIM_URL}/oauth2/token",
            data={"grant_type": "password", "username": "teacher@evoke.local", "password": "sim-demo"}
        )
        sim_token = token_response.json().get("access_token") if token_response.status_code == 200 else None
        if not sim_token:
            return None
        resp = await client.get(
            f"{BRIGHTSPACE_SIM_URL}/d2l/api/le/1.x/1/classlist/",
            headers={"Authorization": f"Bearer {sim_token}"}
        )
        return resp.json() if resp.status_code == 200 else None


@app.get("/api/admin/roster")
async def admin_roster():
    """LMS classlist cross-referenced against evoke_identities and
    team_members -- who's already an EVOKE Player, and which team (if any)
    they're on."""
    try:
        classlist = await _fetch_classlist()
        if classlist is None:
            raise HTTPException(status_code=502, detail="Could not reach the LMS roster")

        out = []
        for student in classlist:
            bs_id = int(student["Identifier"])
            link = db_fetch_one(
                "SELECT user_id FROM evoke_identities WHERE brightspace_user_id = %s", (bs_id,)
            )
            user_id = str(link[0]) if link else None
            team = None
            if user_id:
                team_row = db_fetch_one(
                    """SELECT t.id, t.name FROM teams t
                       JOIN team_members tm ON tm.team_id = t.id
                       WHERE tm.user_id = %s::uuid LIMIT 1""",
                    (user_id,)
                )
                if team_row:
                    team = {"team_id": str(team_row[0]), "name": team_row[1]}
            out.append({
                "brightspace_user_id": bs_id,
                "display_name": student["DisplayName"],
                "email": student["Email"],
                "imported": user_id is not None,
                "user_id": user_id,
                "team": team,
            })
        return {"roster": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/roster/{brightspace_user_id}/import")
async def admin_import_student(brightspace_user_id: int):
    """Provisions an EVOKE Player for this LMS student ahead of their first
    LTI launch, so an admin can assign them to a team right away.
    Idempotent -- importing an already-linked student returns their
    existing user_id, no duplicate row."""
    try:
        classlist = await _fetch_classlist()
        student = next((s for s in (classlist or []) if int(s["Identifier"]) == brightspace_user_id), None)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found on LMS roster")

        user_id = await get_or_create_evoke_player(
            async_db_pool, brightspace_user_id, student["Email"], student["DisplayName"], "learner"
        )
        if not user_id:
            raise HTTPException(status_code=500, detail="Failed to provision EVOKE Player")
        return {"status": "ok", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/teams")
async def admin_list_teams():
    try:
        teams = db_fetch_all("SELECT id, name FROM teams ORDER BY name")
        out = []
        for tid, name in teams:
            members = db_fetch_all(
                """SELECT u.id, u.display_name, u.email FROM team_members tm
                   JOIN users u ON u.id = tm.user_id WHERE tm.team_id = %s::uuid
                   ORDER BY u.display_name""",
                (tid,)
            )
            out.append({
                "team_id": str(tid), "name": name,
                "members": [{"user_id": str(m[0]), "display_name": m[1], "email": m[2]} for m in members],
            })
        return {"teams": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/teams")
async def admin_create_team(name: str = Form(...)):
    try:
        org_row = db_fetch_one("SELECT id FROM organizations LIMIT 1")
        if not org_row:
            raise HTTPException(status_code=500, detail="No organization configured")
        team_id = str(uuid.uuid4())
        db_execute(
            "INSERT INTO teams (id, org_id, name) VALUES (%s::uuid, %s::uuid, %s)",
            (team_id, org_row[0], name)
        )
        return {"status": "ok", "team_id": team_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/teams/{team_id}/members")
async def admin_add_team_member(team_id: str, user_id: str = Form(...)):
    """A learner belongs to exactly one team (matching how the curriculum
    is actually run, and what the team-evidence-submission model assumes)
    -- assigning here always means *moving* them, not adding a second
    membership, so any prior team_members row is cleared first."""
    try:
        db_execute("DELETE FROM team_members WHERE user_id = %s::uuid", (user_id,))
        db_execute(
            "INSERT INTO team_members (team_id, user_id) VALUES (%s::uuid, %s::uuid)",
            (team_id, user_id)
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/teams/{team_id}/members/{user_id}")
async def admin_remove_team_member(team_id: str, user_id: str):
    try:
        db_execute(
            "DELETE FROM team_members WHERE team_id = %s::uuid AND user_id = %s::uuid",
            (team_id, user_id)
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Stages & the Campaign Map (BUILD_PLAN_2 §2-3) ==========
TIER_RANK = {"common": 1, "epic": 2, "legendary": 3}
STAGE_STARS = {1: "★", 2: "★★", 3: "★★★"}


@app.post("/api/admin/missions/{mission_id}/stage")
async def admin_set_stage(mission_id: str, stage: int = Form(...)):
    """Stages are instructor pedagogy config (Nathan's decision: cadence
    must flex with classes/workshops), decoupled from the LMS week the
    stage column defaults to. Same unprotected-dev status as /api/admin."""
    if stage < 1 or stage > 24:
        raise HTTPException(status_code=400, detail="Stage must be 1-24")
    db_execute("UPDATE missions SET stage = %s WHERE id = %s::uuid", (stage, mission_id))
    return {"status": "ok", "stage": stage}


@app.get("/api/progress-map/{user_id}")
async def progress_map(user_id: str):
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
WISDOM_FALLBACKS = [
    "Every drop counts. Even the small ones.",
    "The mountain doesn't move for anyone. Water finds a way around it anyway.",
    "Budget today's water so tomorrow still exists.",
    "Assets create value long after they're built. So does showing up.",
]


@app.post("/api/reflection")
async def post_reflection(user_id: str, text: str = Form(...)):
    """The daily Field Report: one reflection a day, answered with a Word
    of Wisdom in B1llbot's voice. Doubles as the daily check-in (grants
    that XP if today's hasn't happened) and, at 10 lifetime reflections,
    unlocks the Transformation Power (skills_framework.BEHAVIORAL_POWERS,
    approved trigger)."""
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Say something — even one line")
    already = db_fetch_one(
        "SELECT wisdom FROM daily_reflections WHERE user_id = %s::uuid AND reflection_date = CURRENT_DATE",
        (user_id,)
    )
    if already:
        return {"status": "already_filed", "wisdom": already[0]}

    wisdom = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENWEBUI_URL}/api/chat/completions",
                headers={"Authorization": f"Bearer {OPENWEBUI_API_KEY}"} if OPENWEBUI_API_KEY else {},
                json={"model": "billbot", "messages": [{
                    "role": "user",
                    "content": ("An Agent files their daily field report with you. It says: "
                                f"\"{text[:600]}\" — Reply with ONE short word of wisdom in your own voice, "
                                "1-2 sentences, no preamble, that honors what they said."),
                }]},
                timeout=90,
            )
            if response.status_code == 200:
                wisdom = response.json().get("choices", [{}])[0].get("message", {}).get("content") or None
    except Exception as e:
        logger.warning(f"Wisdom generation failed: {e}")
    if not wisdom:
        wisdom = random.choice(WISDOM_FALLBACKS)

    db_execute(
        "INSERT INTO daily_reflections (user_id, text, wisdom) VALUES (%s::uuid, %s, %s) ON CONFLICT DO NOTHING",
        (user_id, text, wisdom)
    )

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

    return {"status": "filed", "wisdom": wisdom, "reflections_total": count}


@app.get("/api/reflections/{user_id}")
async def get_reflections(user_id: str, limit: int = 60):
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
async def get_daily_objectives(user_id: str):
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
async def companion_pair(token: str = Form(...)):
    """Exchange a one-time QR pairing token (minted by the QR endpoint for
    the logged-in web user) for that user's identity — the phone is
    registered without a login. Single-use, 10-minute expiry."""
    row = db_fetch_one(
        """SELECT p.user_id, u.display_name, u.email, p.used_at, p.created_at
           FROM pairing_tokens p JOIN users u ON u.id = p.user_id WHERE p.token = %s::uuid""",
        (token,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Unknown pairing code — rescan from the Hub")
    user_id, display_name, email, used_at, created_at = row
    if used_at is not None:
        raise HTTPException(status_code=410, detail="That QR was already used — rescan a fresh one from the Hub")
    if (datetime.datetime.now() - created_at).total_seconds() > 600:
        raise HTTPException(status_code=410, detail="That QR expired — rescan a fresh one from the Hub")
    db_execute("UPDATE pairing_tokens SET used_at = CURRENT_TIMESTAMP WHERE token = %s::uuid", (token,))
    return {"user_id": str(user_id), "display_name": display_name, "email": email}


# ========== Two-channel Minecraft linking (BUILD_PLAN_2 §8) ==========
@app.post("/api/minecraft/link-code")
async def create_link_code(user_id: str):
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
async def get_link_request(user_id: str):
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
async def confirm_link(user_id: str, accept: bool = Form(...)):
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
async def collect_kit_piece(user_id: str, piece: str = Form(...)):
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
async def kit_progress(user_id: str):
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
async def upload_avatar(user_id: str, file: UploadFile = File(...)):
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
async def delete_avatar(user_id: str):
    db_execute("UPDATE users SET avatar_object_key = NULL WHERE id = %s::uuid", (user_id,))
    return {"status": "removed"}


@app.post("/api/profile/{user_id}/sigil")
async def set_sigil(user_id: str, glyph: str = Form(...), hue: int = Form(...)):
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
async def equip_gear(user_id: str, keys: str = Form(...)):
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
if os.path.exists(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

# ========== Background Workers ==========
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(evoke_workers_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

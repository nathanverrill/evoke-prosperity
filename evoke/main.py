import os
import json
import datetime
import asyncio
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends, Response
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

logger = logging.getLogger(__name__)

# ========== Configuration ==========
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://evoke:devsecret123@localhost:5432/evoke")
BRIGHTSPACE_SIM_URL = os.getenv("BRIGHTSPACE_SIM_URL", "http://brightspace-sim:8001")
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://open-webui:8080")
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"

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
                superpower, primary_skill, secondary_skill, pfl_domain, mission_brief_md)
               VALUES (gen_random_uuid(), %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (campaign_id, lms_assignment_ref) DO UPDATE SET
                   week = EXCLUDED.week, sequence = EXCLUDED.sequence, title = EXCLUDED.title,
                   arc = EXCLUDED.arc, superpower = EXCLUDED.superpower,
                   primary_skill = EXCLUDED.primary_skill, secondary_skill = EXCLUDED.secondary_skill,
                   pfl_domain = EXCLUDED.pfl_domain, mission_brief_md = EXCLUDED.mission_brief_md""",
            (
                campaign_id, assignment["AssignmentId"], fields.get("Week"), fields.get("Sequence"),
                assignment["Name"], fields.get("Arc"), fields.get("Superpower"),
                fields.get("PrimarySkill"), fields.get("SecondarySkill"), fields.get("PflDomain"),
                fields.get("Description"),
            )
        )
        synced += 1

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
async def dev_login(user_id: Optional[str] = None):
    """Dev mode auto-login"""
    if not user_id:
        # Return first dev user
        result = db_fetch_one("SELECT id, display_name, email FROM users LIMIT 1")
        if not result:
            raise HTTPException(status_code=404, detail="No users found")
        user_id, display_name, email = result
    else:
        result = db_fetch_one("SELECT display_name, email FROM users WHERE id = %s::uuid", (user_id,))
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        display_name, email = result

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
            """SELECT id, title, week, arc, superpower, mission_brief_md
               FROM missions WHERE campaign_id = %s::uuid ORDER BY week, sequence""",
            (campaign_id,)
        )

        missions = []
        for mission in missions_data:
            mission_id, title, week, arc, superpower, brief = mission

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
                "quest": {
                    "id": str(quest[0]),
                    "title": quest[1],
                    "description": quest[2]
                } if quest else None
            })

        return {"missions": missions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== Evidence Submission ==========
@app.post("/api/submit-evidence")
async def submit_evidence(
    user_id: str = Form(...),
    mission_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Submit evidence for a mission"""
    try:
        submission_id = str(uuid.uuid4())

        # Store file in MinIO
        file_bytes = await file.read()
        object_key = f"evoke-evidence/{mission_id}/{user_id}_{file.filename}"
        s3_client.put_object(
            Bucket="default-bucket",
            Key=object_key,
            Body=file_bytes,
            ContentType=file.content_type or "application/octet-stream"
        )

        # Create submission record
        db_execute(
            """INSERT INTO submissions (id, user_id, mission_id, file_path, status)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'submitted')""",
            (submission_id, user_id, mission_id, object_key)
        )

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

        # Publish EvidenceSubmitted event
        await publish_event("EvidenceSubmitted", {
            "submission_id": submission_id,
            "user_id": user_id,
            "mission_id": mission_id,
            "object_key": object_key,
            "filename": file.filename
        })

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
                        criteria="Submitted evidence for mission",
                        evidence=f"Submission ID: {submission_id}"
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

        # Submitting evidence is what "completes" a mission for badge/count
        # purposes — later AI/teacher award tiers (below, and in
        # trigger_ai_review/brightspace_review) are quality upgrades on an
        # already-completed mission, not separate completions, so
        # MissionCompleted/BadgeAwarded only fire here.
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

        mission_superpower = db_fetch_one(
            "SELECT superpower FROM missions WHERE id = %s::uuid", (mission_id,)
        )
        if mission_superpower and mission_superpower[0]:
            # badge_key = the Superpower this mission builds toward. Criteria
            # for what "earns" a badge (every tagged mission vs. a threshold)
            # is explicitly flagged undecided in GAPS.md — this just makes
            # every mission-completion count as one step of progress, so
            # profiles have something to render.
            await publish_event("BadgeAwarded", {
                "user_id": user_id,
                "badge_key": mission_superpower[0],
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

        # Trigger AI review if enabled
        if AI_ENABLED:
            await trigger_ai_review(user_id, mission_id, object_key)

        return {
            "status": "success",
            "submission_id": submission_id,
            "award_id": str(award_id_from_db)
        }
    except Exception as e:
        logger.error(f"Submit evidence error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def trigger_ai_review(user_id: str, mission_id: str, object_key: str):
    """Trigger AI review of submission"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENWEBUI_URL}/api/chat/completions",
                json={
                    "model": "billbot",
                    "messages": [
                        {"role": "user", "content": f"Review this mission submission for consistency: {object_key}"}
                    ]
                },
                timeout=30
            )

            if response.status_code == 200:
                # Assume consistent for now - in real implementation, parse response
                award_id = str(uuid.uuid4())
                db_execute(
                    """INSERT INTO awards (id, user_id, mission_id, tier, source, awarded_at)
                       VALUES (%s::uuid, %s::uuid, %s::uuid, 'epic', 'ai_review', CURRENT_TIMESTAMP)
                       ON CONFLICT (user_id, mission_id, tier, source) DO NOTHING""",
                    (award_id, user_id, mission_id)
                )

                await publish_event("AwardGranted", {
                    "award_id": award_id,
                    "user_id": user_id,
                    "mission_id": mission_id,
                    "tier": "epic",
                    "source": "ai_review"
                })

                notification_id = str(uuid.uuid4())
                award_id_from_db = db_fetch_one(
                    "SELECT id FROM awards WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = 'epic' AND source = 'ai_review' LIMIT 1",
                    (user_id, mission_id)
                )
                if award_id_from_db:
                    db_execute(
                        "INSERT INTO notifications (id, user_id, award_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
                        (notification_id, user_id, award_id_from_db[0])
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
            "badges": profile.get("badges", {}),
            "missions_completed": missions_completed,
            "missions_completed_count": len(missions_completed),
            "quests_completed": quests_completed,
            "quests_completed_count": len(quests_completed),
            "awards": awards_list,
        }
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
            """SELECT tm.user_id, u.display_name, tm.role_label
               FROM team_members tm JOIN users u ON u.id = tm.user_id
               WHERE tm.team_id = %s::uuid""",
            (team_id,)
        )
        members_list = [{"user_id": str(m[0]), "display_name": m[1], "role_label": m[2]} for m in members]
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
        # an error. "Submitted" only reflects reality if a submission row
        # actually exists; otherwise this is a mission the learner hasn't
        # touched yet and the timeline shouldn't claim otherwise.
        has_submission = db_fetch_one(
            "SELECT 1 FROM submissions WHERE user_id = %s::uuid AND mission_id = %s::uuid LIMIT 1",
            (user_id, mission_id)
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
    about."""
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENWEBUI_URL}/api/chat/completions",
                json={
                    "model": "billbot",
                    "messages": [
                        {"role": "user", "content": message}
                    ]
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "I'm not sure how to help with that.")
                return {"reply": reply}

        return {"reply": "I'm having trouble responding right now."}
    except Exception as e:
        return {"reply": f"Error: {str(e)}"}

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

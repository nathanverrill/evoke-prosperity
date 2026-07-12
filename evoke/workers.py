import json
import os
import datetime
import asyncio
from io import BytesIO
from pypdf import PdfReader
from kafka import KafkaConsumer
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from evoke.clients import s3_client, os_client, ai_client, get_producer, REDPANDA_BROKER, AI_ENABLED, AI_MODEL

# Small, self-contained Postgres pool for the PROFILE WORKER's team-membership
# lookups. Deliberately not shared with main.py's db_pool (a separate pool
# construction, same DATABASE_URL) to avoid a circular import — main.py
# imports evoke_workers_loop from this module, so this module importing
# main.py's pool back would be circular.
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://evoke:devsecret123@localhost:5432/evoke")
_db_pool = SimpleConnectionPool(1, 5, _DATABASE_URL)


def _db_fetch_one(query: str, params=None):
    conn = _db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.fetchone()
    finally:
        _db_pool.putconn(conn)


def _db_fetch_all(query: str, params=None):
    conn = _db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.fetchall()
    finally:
        _db_pool.putconn(conn)


def xp_to_level(xp: int) -> int:
    """Placeholder level curve (overview.md's example table: 0/100/250/450...)
    — GAPS.md flags the real XP economy as still undecided; this just gives
    profiles something coherent to render in the meantime."""
    thresholds = [0, 100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700]
    level = 1
    for i, t in enumerate(thresholds):
        if xp >= t:
            level = i + 1
    return level


def generate_ai_insight(preview_text: str) -> str:

    if not AI_ENABLED or ai_client is None:
        return (
            "AI is disabled for this installation. "
            "Great job submitting your evidence. An instructor can review it later."
        )

    try:
        response = ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an empathetic learning coach..."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Student submission:\n{preview_text}",
                },
            ],
            max_tokens=150,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"AI unavailable: {e}")

        return (
            "AI feedback is temporarily unavailable. "
            "Your submission has been received successfully."
        )


def _process_event(event: dict, producer):
    """Handles one event from the evoke-events stream. Split out from the poll
    loop so a bad event can be caught and skipped per-message (see the caller)
    instead of taking down the whole worker for the rest of the process's life
    — which is exactly what a pre-existing field-name mismatch was doing here
    (this loop's single outer try/except meant one uncaught KeyError silently
    ended the coroutine permanently)."""
    event_type = event.get("event_type")

    # -------------------------------------------------------------
    # 1. AI COACH WORKER
    # -------------------------------------------------------------
    if event_type in ["EvidenceSubmitted", "TeamEvidenceSubmitted"]:

        object_key = event['data']['object_key']
        mission_id = event['data']['mission_id']

        # Handle individual vs team payload structure. NOTE: this used to read
        # 'learner_id', but /api/submit-evidence in main.py has always
        # published the field as 'user_id' — a pre-existing mismatch that
        # silently crashed this entire worker loop on the very first
        # EvidenceSubmitted event, every time.
        if event_type == "EvidenceSubmitted":
            learners_to_update = [event['data']['user_id']]
        else:
            learners_to_update = event['data']['team_members']

        print(f"[AI WORKER] Fetching payload {object_key} for {len(learners_to_update)} learners...")

        try:
            response = s3_client.get_object(Bucket="default-bucket", Key=object_key)
            reader = PdfReader(BytesIO(response['Body'].read()))
            extracted_text = "".join([page.extract_text() + "\n" for page in reader.pages])[:3000]
            ai_response = generate_ai_insight(extracted_text)
        except Exception as e:
            print(f"[AI WORKER ERROR] Failed to parse file payload: {e}")
            ai_response = "Error parsing document. Please confirm it is a readable PDF layout."

        # Publish feedback for EVERY learner on the team independently
        for learner_id in learners_to_update:
            feedback_event = {
                "event_type": "FeedbackGenerated",
                "version": "1.0.0",
                "timestamp": datetime.datetime.now().isoformat(),
                "data": {
                    "learner_id": learner_id,
                    "mission_id": mission_id,
                    "insight": {
                        "category": "Suggestion",
                        "source": "AI Coach",
                        "text": ai_response
                    }
                }
            }
            producer.send('evoke-events', value=feedback_event)

        producer.flush()
        print(f"[AI WORKER] Dispatched AI Insights for {len(learners_to_update)} learners.")

    # -------------------------------------------------------------
    # 2. SEARCH & TIMELINE WORKER
    # -------------------------------------------------------------
    elif event_type in ["FeedbackGenerated", "InsightPublished"]:
        learner_id = event['data']['learner_id']
        mission_id = event['data']['mission_id']
        new_insight = event['data']['insight']

        projection_id = f"{learner_id}_{mission_id}"
        now_str = datetime.datetime.now().isoformat()

        try:
            current = os_client.get(index="learner-timeline", id=projection_id)['_source']
        except Exception:
            # Nothing previously initialized the actual timeline step
            # scaffold (submitted/processing/ai_analysis/teacher_review) that
            # UI_SPEC.md's timeline strip and the step-matching logic below
            # both assume exists -- "timeline": [] meant the for loop below
            # had nothing to iterate and no step ever advanced past nothing.
            # By the time any event reaches this branch, evidence has always
            # already been submitted, so "submitted" starts complete.
            current = {
                "learner_id": learner_id, "mission_id": mission_id, "insights": [],
                "timeline": [
                    {"id": "submitted", "label": "Submitted", "status": "completed", "timestamp": now_str, "content": "Evidence received."},
                    {"id": "processing", "label": "Processing", "status": "active", "timestamp": None, "content": "Awaiting processing."},
                    {"id": "ai_analysis", "label": "AI Analysis", "status": "pending", "timestamp": None, "content": "Awaiting AI analysis."},
                    {"id": "teacher_review", "label": "Instructor Review", "status": "pending", "timestamp": None, "content": "Awaiting human insights."},
                ]
            }

        if "insights" not in current:
            current["insights"] = []
        current["insights"].append(new_insight)

        # Logic to advance the specific timeline steps based on who provided feedback
        for step in current.get("timeline", []):
            if event_type == "FeedbackGenerated":
                if step["id"] == "processing":
                    step["status"] = "completed"
                    step["content"] = "Text extracted and routed successfully."
                elif step["id"] == "ai_analysis":
                    step["status"] = "completed"
                    step["timestamp"] = now_str
                    step["content"] = f"<strong>[{new_insight['category']} from {new_insight['source']}]</strong><br/>{new_insight['text']}"
                elif step["id"] == "teacher_review":
                    step["status"] = "active"

            elif event_type == "InsightPublished":
                current["status"] = "Human Review Received"
                if step["id"] == "teacher_review":
                    step["status"] = "completed"
                    step["timestamp"] = now_str
                    # Append human feedback to the timeline step directly
                    existing = step["content"] if step["content"] != "Awaiting human insights." else ""
                    step["content"] = existing + f"<br/><br/><strong>[{new_insight['category']} from {new_insight['source']}]</strong><br/>{new_insight['text']}"

        os_client.index(index="learner-timeline", id=projection_id, body=current, refresh=True)
        print(f"[SEARCH WORKER] Projected {event_type} into read-model for {learner_id}.")

    # -------------------------------------------------------------
    # 3. PROFILE WORKER
    # -------------------------------------------------------------
    elif event_type in ["MissionCompleted", "BadgeAwarded", "XPGranted", "QuestCompleted"]:
        user_id = event['data']['user_id']
        now_str = datetime.datetime.now().isoformat()

        try:
            profile = os_client.get(index="player-profile", id=user_id)['_source']
        except Exception:
            profile = {
                "user_id": user_id, "xp": 0, "level": 1,
                "missions_completed": [], "badges": {}, "quests_completed": []
            }

        if event_type == "MissionCompleted":
            mission_id = event['data']['mission_id']
            if mission_id not in profile["missions_completed"]:
                profile["missions_completed"].append(mission_id)

        elif event_type == "BadgeAwarded":
            badge_key = event['data']['badge_key']
            badge = profile["badges"].setdefault(
                badge_key, {"earned": False, "progress": 0, "earned_at": None}
            )
            badge["progress"] += 1
            if not badge["earned"]:
                badge["earned"] = True
                badge["earned_at"] = now_str

        elif event_type == "XPGranted":
            profile["xp"] = profile.get("xp", 0) + event['data']['amount']
            profile["level"] = xp_to_level(profile["xp"])

        elif event_type == "QuestCompleted":
            quest_id = event['data']['quest_id']
            if not any(q["quest_id"] == quest_id for q in profile["quests_completed"]):
                profile["quests_completed"].append({"quest_id": quest_id, "completed_at": now_str})

        profile["updated_at"] = now_str
        os_client.index(index="player-profile", id=user_id, body=profile, refresh=True)
        print(f"[PROFILE WORKER] Updated player-profile for {user_id} ({event_type}).")

        # Team aggregation: roll this member's contribution into each team
        # they belong to. No TeamEvidenceSubmitted event exists (team-scoped
        # submission isn't wired into /api/submit-evidence yet), so
        # team-profile is computed by aggregating individual members' events
        # per-team rather than consuming a team-scoped event stream.
        try:
            team_rows = _db_fetch_all(
                "SELECT team_id FROM team_members WHERE user_id = %s", (user_id,)
            )
        except Exception as e:
            print(f"[PROFILE WORKER] Team lookup failed for {user_id}: {e}")
            team_rows = []

        for (team_id,) in team_rows:
            team_id = str(team_id)
            try:
                team_profile = os_client.get(index="team-profile", id=team_id)['_source']
            except Exception:
                team_profile = {
                    "team_id": team_id, "xp_total": 0,
                    "missions_completed": [], "quests_completed_count": 0,
                    "member_badges": {}
                }

            if event_type == "MissionCompleted":
                mission_id = event['data']['mission_id']
                if mission_id not in team_profile["missions_completed"]:
                    team_profile["missions_completed"].append(mission_id)
            elif event_type == "BadgeAwarded":
                badge_key = event['data']['badge_key']
                member_badges = team_profile["member_badges"].setdefault(user_id, {})
                member_badges[badge_key] = True
            elif event_type == "XPGranted":
                team_profile["xp_total"] = team_profile.get("xp_total", 0) + event['data']['amount']
            elif event_type == "QuestCompleted":
                team_profile["quests_completed_count"] = team_profile.get("quests_completed_count", 0) + 1

            team_profile["updated_at"] = now_str
            os_client.index(index="team-profile", id=team_id, body=team_profile, refresh=True)


async def evoke_workers_loop():
    await asyncio.sleep(5)

    try:
        consumer = KafkaConsumer(
            'evoke-events',
            bootstrap_servers=[REDPANDA_BROKER],
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        producer = get_producer()
        print(">>> Independent EVOKE background workers started listening to stream.")

        while True:
            msg_pack = consumer.poll(timeout_ms=500)
            for tp, messages in msg_pack.items():
                for message in messages:
                    try:
                        _process_event(message.value, producer)
                    except Exception as e:
                        # One bad/malformed event must not take down every
                        # consumer downstream of it for the rest of the
                        # process's life — log and keep polling.
                        print(f"[WORKER ERROR] Failed to process {message.value.get('event_type')}: {e}")

            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"Fatal worker pipeline event loop crash: {e}")

import json
import os
import uuid
import datetime
import asyncio
from io import BytesIO
from pypdf import PdfReader
from kafka import KafkaConsumer
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from evoke.clients import s3_client, os_client, ai_client, get_producer, REDPANDA_BROKER, AI_ENABLED, AI_MODEL, topic_for_event
from evoke import skills_framework, progression, world_state
from evoke.live import live_hub

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


def _db_execute(query: str, params=None):
    conn = _db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()
    finally:
        _db_pool.putconn(conn)


# Level curve + rank titles moved to evoke/progression.py (levels now have
# names and a level-up moment, not just a number); re-exported so anything
# importing xp_to_level from here keeps working.
xp_to_level = progression.xp_to_level


# Moved from main.py alongside the FIELD REPORT WORKER (below) -- this is
# the only place that generates wisdom now.
WISDOM_FALLBACKS = [
    "Every drop counts. Even the small ones.",
    "The mountain doesn't move for anyone. Water finds a way around it anyway.",
    "Budget today's water so tomorrow still exists.",
    "Assets create value long after they're built. So does showing up.",
]


def generate_ai_insight(preview_text: str) -> str:

    if not AI_ENABLED or ai_client is None:
        return (
            "AI is disabled for this installation. "
            "Great job submitting your evidence. An instructor can review it later."
        )

    try:
        # No system message here on purpose -- same as main.py's other
        # "billbot" calls (billbot_chat, post_reflection): the model itself
        # already carries B1llBot's real configured voice/RAG in OpenWebUI.
        # A generic "empathetic learning coach" system message here would
        # fight that instead of using it.
        response = ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
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
            producer.send(topic_for_event(feedback_event["event_type"]), value=feedback_event)

        producer.flush()
        print(f"[AI WORKER] Dispatched AI Insights for {len(learners_to_update)} learners.")

        # Epic-tier award upgrade -- moved here from main.py's old
        # trigger_ai_review(), which fired synchronously inline in the
        # submit-evidence request (blocking the learner's HTTP response on
        # an AI call measured up to ~90s cold) and, worse, only ever sent
        # OpenWebUI the file's storage path, never its content -- this
        # worker already has the real extracted text and a real ai_response
        # in hand, from the exact same pass, so this reuses that instead of
        # making a second, redundant call. Team-scoped only (individual
        # EvidenceSubmitted events carry no team_id); only upgrades members
        # who've already closed the common/submission AND-gate, same as
        # the original -- someone who hasn't reflected yet isn't awarded
        # here either.
        if event_type == "TeamEvidenceSubmitted" and AI_ENABLED and ai_response != "Error parsing document. Please confirm it is a readable PDF layout.":
            team_id = event['data']['team_id']
            completed_members = _db_fetch_all(
                "SELECT DISTINCT user_id FROM awards WHERE mission_id = %s::uuid AND source = 'submission' AND user_id = ANY(SELECT user_id FROM team_members WHERE team_id = %s::uuid)",
                (mission_id, team_id)
            )
            for (member_id,) in completed_members:
                member_id = str(member_id)
                award_id = str(uuid.uuid4())
                _db_execute(
                    """INSERT INTO awards (id, user_id, mission_id, tier, source, awarded_at)
                       VALUES (%s::uuid, %s::uuid, %s::uuid, 'epic', 'ai_review', CURRENT_TIMESTAMP)
                       ON CONFLICT (user_id, mission_id, tier, source) DO NOTHING""",
                    (award_id, member_id, mission_id)
                )
                award_row = _db_fetch_one(
                    "SELECT id FROM awards WHERE user_id = %s::uuid AND mission_id = %s::uuid AND tier = 'epic' AND source = 'ai_review' LIMIT 1",
                    (member_id, mission_id)
                )
                if award_row:
                    _db_execute(
                        "INSERT INTO notifications (id, user_id, award_id) VALUES (%s::uuid, %s::uuid, %s::uuid)",
                        (str(uuid.uuid4()), member_id, award_row[0])
                    )
                # One event per member, matching the original -- the
                # ACTIVITY WORKER (this same file, further down) requires
                # AwardGranted.data.user_id; a single bundled team-level
                # event would silently drop this from the class feed.
                producer.send(topic_for_event("AwardGranted"), value={
                    "event_type": "AwardGranted",
                    "version": "1.0.0",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "data": {"award_id": award_id, "user_id": member_id, "mission_id": mission_id, "tier": "epic", "source": "ai_review"}
                })
            producer.flush()
            print(f"[AI WORKER] Epic-tier upgrade granted to {len(completed_members)} completed team member(s).")

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
                # Peer comments are also InsightPublished (per CONCEPTS.md:
                # "Insight -- feedback from AI Coach, instructor, or peer"),
                # but must NOT be treated as the teacher review -- a
                # classmate leaving a comment on your work is not the same
                # as an instructor completing "Instructor Review". Only
                # advance that step for non-peer insights.
                if event['data'].get('kind') != 'peer':
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
            # Power-level achievements (GAME_DESIGN.md §4.1): a Quality
            # badge is a derived rollup over its 4 constituent Powers, not
            # its own independent counter. `power_key` names which of the
            # 16 real Powers this event demonstrates (already resolved by
            # the publisher via skills_framework.resolve_power, including
            # the 3 non-canonical mission-tag aliases); `badge_key` is that
            # Power's own Table 1 Quality, not the mission's labeled
            # Superpower field.
            badge_key = event['data']['badge_key']
            power_key = event['data'].get('power_key')
            tag_type = event['data'].get('tag_type')
            badge = profile["badges"].setdefault(
                badge_key, {"earned": False, "progress": 0, "earned_at": None, "powers": {}}
            )
            badge.setdefault("powers", {})
            if power_key:
                power_state = badge["powers"].setdefault(
                    power_key, {"earned": False, "earned_at": None, "tag_type": None}
                )
                if not power_state["earned"]:
                    power_state["earned"] = True
                    power_state["earned_at"] = now_str
                    power_state["tag_type"] = tag_type
                badge["progress"] = len(badge["powers"])
                if not badge["earned"] and badge["progress"] >= 4:
                    badge["earned"] = True
                    badge["earned_at"] = now_str

        elif event_type == "XPGranted":
            old_level = profile.get("level", 1)
            profile["xp"] = profile.get("xp", 0) + event['data']['amount']
            profile["level"] = xp_to_level(profile["xp"])
            if profile["level"] > old_level:
                # A rank-up is its own event (LevelUpped), not just a bigger
                # number in the projection — the bridge turns it into an
                # in-game title/fireworks for a linked player, the web gets
                # a celebration via the live hub, and the feed announces it.
                title = progression.level_title(profile["level"])
                name_row = _db_fetch_one("SELECT display_name FROM users WHERE id = %s", (user_id,))
                display_name = name_row[0] if name_row else "An agent"
                producer.send(topic_for_event("LevelUpped"), value={
                    "event_type": "LevelUpped",
                    "version": "1.0.0",
                    "timestamp": now_str,
                    "data": {
                        "user_id": user_id,
                        "level": profile["level"],
                        "title": title,
                        "xp": profile["xp"],
                        "display_name": display_name,
                    },
                })
                producer.flush()
                os_client.index(index="activity-feed", body={
                    "timestamp": now_str, "user_id": user_id, "display_name": display_name,
                    "kind": "level_up", "tier": None,
                    "message": f"{display_name} reached Level {profile['level']} — {title}",
                })

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

    # -------------------------------------------------------------
    # 4. ACTIVITY WORKER
    # -------------------------------------------------------------
    # Class-wide social layer: GAPS.md's #2 flagged gap ("no social layer...
    # the game is single-player homework with better wallpaper") and the
    # reason a real feed matters more here than in a typical app -- missions
    # are paced weekly, so any one learner's personal activity is sparse most
    # days, but a whole cohort's combined activity (everyone's submissions,
    # awards, quests) is not. AwardGranted + QuestCompleted only (not
    # MissionCompleted/BadgeAwarded/XPGranted, which fire at the same moment
    # as AwardGranted for the same underlying action and would just be
    # redundant noise in a public feed).
    #
    # Deliberately a standalone `if`, not chained onto the elif above:
    # QuestCompleted is also handled by the PROFILE WORKER's elif branch, and
    # elif chains are mutually exclusive -- as elif this never ran for
    # QuestCompleted at all (caught and fixed by actually testing the feed,
    # not just reading the code back).
    if event_type in ["AwardGranted", "QuestCompleted"]:
        user_id = event['data']['user_id']
        now_str = datetime.datetime.now().isoformat()
        name_row = _db_fetch_one("SELECT display_name FROM users WHERE id = %s", (user_id,))
        display_name = name_row[0] if name_row else "An agent"

        if event_type == "AwardGranted":
            tier = event['data']['tier']
            mission_row = _db_fetch_one("SELECT title FROM missions WHERE id = %s", (event['data']['mission_id'],))
            mission_title = mission_row[0] if mission_row else "a mission"
            message = f"{display_name} earned a {tier} award for {mission_title}"
            kind, tier_out = "award_granted", tier
        else:  # QuestCompleted
            quest_row = _db_fetch_one("SELECT title FROM mc_quests WHERE id = %s", (event['data']['quest_id'],))
            quest_title = quest_row[0] if quest_row else "a Basin Simulation quest"
            message = f"{display_name} completed {quest_title} in the Basin Simulation"
            kind, tier_out = "quest_completed", None

        activity_doc = {
            "timestamp": now_str, "user_id": user_id, "display_name": display_name,
            "kind": kind, "tier": tier_out, "message": message,
        }
        os_client.index(index="activity-feed", body=activity_doc)
        # The feed message carries the display name the raw event lacks --
        # broadcast it too so browsers can toast/prepend without a lookup.
        live_hub.broadcast({"type": "ActivityPosted", "data": activity_doc})

    # -------------------------------------------------------------
    # 5. WORLD WORKER — collective world-state (GAPS.md #5)
    # -------------------------------------------------------------
    # Every distinct (learner, mission) completion anywhere in the cohort
    # advances Keel's restoration; see evoke/world_state.py for the design
    # and its variants. Standalone `if` for the same reason the ACTIVITY
    # WORKER is: MissionCompleted is also consumed by the PROFILE WORKER's
    # elif chain above, and elif chains are mutually exclusive.
    if event_type == "MissionCompleted":
        user_id = event['data']['user_id']
        mission_id = event['data']['mission_id']
        now_str = datetime.datetime.now().isoformat()

        try:
            world = os_client.get(index="world-state", id="keel")['_source']
        except Exception:
            world = {"completions": 0, "stage": 0, "counted": {}, "history": []}

        # Dedupe by (user, mission): /api/submit-evidence publishes
        # MissionCompleted on *every* submission, including resubmissions of
        # the same mission — those shouldn't advance the world twice.
        counted = world.setdefault("counted", {})
        user_missions = counted.setdefault(user_id, [])
        if mission_id not in user_missions:
            user_missions.append(mission_id)
            world["completions"] = world.get("completions", 0) + 1
            old_stage = world.get("stage", 0)
            new_stage = world_state.stage_for(world["completions"])
            world["stage"] = new_stage
            world["updated_at"] = now_str

            if new_stage > old_stage:
                meta = world_state.stage_meta(new_stage)
                world.setdefault("history", []).append(
                    {"stage": new_stage, "title": meta["title"], "at": now_str}
                )
                producer.send(topic_for_event("WorldStateAdvanced"), value={
                    "event_type": "WorldStateAdvanced",
                    "version": "1.0.0",
                    "timestamp": now_str,
                    "data": {
                        "stage": new_stage,
                        "total_stages": meta["total_stages"],
                        "title": meta["title"],
                        "narrative": meta["narrative"],
                        "completions": world["completions"],
                    },
                })
                producer.flush()
                world_activity = {
                    "timestamp": now_str, "user_id": None, "display_name": "Keel",
                    "kind": "world_state", "tier": None,
                    "message": f"⚡ Keel Restoration reached Stage {new_stage}: {meta['title']} — {meta['narrative']}",
                }
                os_client.index(index="activity-feed", body=world_activity)
                live_hub.broadcast({"type": "ActivityPosted", "data": world_activity})
                print(f"[WORLD WORKER] Keel advanced to stage {new_stage} ({meta['title']}).")

            os_client.index(index="world-state", id="keel", body=world, refresh=True)

    # -------------------------------------------------------------
    # 5b. TEAM WHEEL WORKER (GAME_DESIGN §7.1, variants #1 + #3)
    # -------------------------------------------------------------
    # A team's wheel for a mission completes when every *current* roster
    # member has reflected on it (rolling roster, no deadline -- the doc's
    # own recommended combination). The team's evidence is one shared file,
    # not one per member, so "submitted" can't be the per-member signal
    # anymore -- the personal, per-member act under the team-evidence model
    # is the reflection (see mission_reflections / _complete_mission_for_user
    # in main.py). Purely additive/celebratory: publishes TeamWheelCompleted,
    # never gates anyone. MissionCompleted fires once per (user, mission),
    # so this fires exactly once, on the final member's completion.
    if event_type == "MissionCompleted":
        user_id = event['data']['user_id']
        mission_id = event['data']['mission_id']
        now_str = datetime.datetime.now().isoformat()
        try:
            team_rows = _db_fetch_all("SELECT team_id FROM team_members WHERE user_id = %s::uuid", (user_id,))
            for (team_id,) in team_rows:
                team_id = str(team_id)
                roster = [str(r[0]) for r in _db_fetch_all(
                    "SELECT user_id FROM team_members WHERE team_id = %s::uuid", (team_id,)
                )]
                if not roster:
                    continue
                completed = _db_fetch_all(
                    "SELECT DISTINCT user_id FROM mission_reflections WHERE mission_id = %s::uuid AND user_id = ANY(%s::uuid[])",
                    (mission_id, roster)
                )
                if len(completed) < len(roster):
                    continue
                team_name_row = _db_fetch_one("SELECT name FROM teams WHERE id = %s::uuid", (team_id,))
                mission_row = _db_fetch_one("SELECT title FROM missions WHERE id = %s::uuid", (mission_id,))
                team_name = team_name_row[0] if team_name_row else "A team"
                mission_title = mission_row[0] if mission_row else "a mission"
                producer.send(topic_for_event("TeamWheelCompleted"), value={
                    "event_type": "TeamWheelCompleted",
                    "version": "1.0.0",
                    "timestamp": now_str,
                    "data": {
                        "team_id": str(team_id), "team_name": team_name,
                        "mission_id": mission_id, "mission_title": mission_title,
                        "roster_size": len(roster),
                    },
                })
                producer.flush()
                wheel_activity = {
                    "timestamp": now_str, "user_id": None, "display_name": team_name,
                    "kind": "team_wheel", "tier": None,
                    "message": f"◎ Team {team_name} completed the wheel for {mission_title} — every member, nobody left behind",
                }
                os_client.index(index="activity-feed", body=wheel_activity)
                live_hub.broadcast({"type": "ActivityPosted", "data": wheel_activity})
                print(f"[TEAM WHEEL] {team_name} completed {mission_title} as a full roster.")
        except Exception as e:
            print(f"[TEAM WHEEL] evaluation failed: {e}")

    # -------------------------------------------------------------
    # 5c. STAGE / LINK ANNOUNCEMENTS
    # -------------------------------------------------------------
    if event_type in ("StageCompleted", "MinecraftLinked"):
        user_id = event['data']['user_id']
        now_str = datetime.datetime.now().isoformat()
        name_row = _db_fetch_one("SELECT display_name FROM users WHERE id = %s::uuid", (user_id,))
        display_name = name_row[0] if name_row else "An agent"
        if event_type == "StageCompleted":
            message = f"◍ {display_name} completed Stage {event['data']['stage']} — 100%, every mission in"
            kind = "stage_completed"
        else:
            message = f"⛏ {display_name} linked their Minecraft account — the Basin gains an agent"
            kind = "minecraft_linked"
        doc = {
            "timestamp": now_str, "user_id": user_id, "display_name": display_name,
            "kind": kind, "tier": None, "message": message,
        }
        os_client.index(index="activity-feed", body=doc)
        live_hub.broadcast({"type": "ActivityPosted", "data": doc})

    # Season drop (console-UX gap #10): a mission release is a cohort-wide
    # event, not tied to one learner's own actions -- no user_id to key the
    # feed doc on the way the other ANNOUNCEMENTS rows do above.
    if event_type == "MissionReleased":
        now_str = datetime.datetime.now().isoformat()
        doc = {
            "timestamp": now_str, "user_id": None, "display_name": None,
            "kind": "mission_released", "tier": None,
            "message": f"🎬 NEW MISSION — Week {event['data']['week']}: {event['data']['title']} is live",
        }
        os_client.index(index="activity-feed", body=doc)
        live_hub.broadcast({"type": "ActivityPosted", "data": doc})

    # Halyard Mob Arena web wiring: the bridge's heartbeat already read the
    # arenaBestWave scoreboard and only publishes this on a genuine new best
    # (see check_arena_progress in bridge.py) -- XPGranted for the reward,
    # this event purely for visibility (feed + live toast).
    if event_type == "ArenaWaveReached":
        user_id = event['data']['user_id']
        wave = event['data']['wave']
        now_str = datetime.datetime.now().isoformat()
        name_row = _db_fetch_one("SELECT display_name FROM users WHERE id = %s::uuid", (user_id,))
        display_name = name_row[0] if name_row else "An agent"
        doc = {
            "timestamp": now_str, "user_id": user_id, "display_name": display_name,
            "kind": "arena_wave", "tier": None,
            "message": f"⚔ {display_name} reached wave {wave} in Claude's Halyard Mob Arena",
        }
        os_client.index(index="activity-feed", body=doc)
        live_hub.broadcast({"type": "ActivityPosted", "data": doc})

    # The Mob Gauntlet web wiring -- same shape as ArenaWaveReached above
    # (see check_gauntlet_progress in bridge.py).
    if event_type == "GauntletWaveReached":
        user_id = event['data']['user_id']
        wave = event['data']['wave']
        now_str = datetime.datetime.now().isoformat()
        name_row = _db_fetch_one("SELECT display_name FROM users WHERE id = %s::uuid", (user_id,))
        display_name = name_row[0] if name_row else "An agent"
        doc = {
            "timestamp": now_str, "user_id": user_id, "display_name": display_name,
            "kind": "gauntlet_wave", "tier": None,
            "message": f"⚔ {display_name} reached wave {wave} in the Mob Gauntlet",
        }
        os_client.index(index="activity-feed", body=doc)
        live_hub.broadcast({"type": "ActivityPosted", "data": doc})

    # -------------------------------------------------------------
    # 6. PRESENCE WORKER — who's in the Basin right now
    # -------------------------------------------------------------
    # The bridge's presence loop publishes MinecraftPresence snapshots;
    # projecting them here (rather than the web app polling RCON itself)
    # keeps RCON access single-owner in the bridge, per the existing split.
    if event_type == "MinecraftPresence":
        os_client.index(index="minecraft-status", id="default", body={
            "server_online": event['data'].get('server_online', False),
            "online_players": event['data'].get('online_players', []),
            "linked_players": event['data'].get('linked_players', {}),
            "updated_at": datetime.datetime.now().isoformat(),
        }, refresh=True)

    # -------------------------------------------------------------
    # 7. FIELD REPORT WORKER — Word of Wisdom, generated async
    # -------------------------------------------------------------
    # Moved off /api/reflection's request path for the same reason the AI
    # Coach Worker's epic-tier award was: it used to block the learner's
    # HTTP response on a synchronous OpenWebUI call (timeout=90, same
    # cold-start risk). main.py now saves the reflection with wisdom=NULL,
    # returns immediately, and publishes this event; the real wisdom lands
    # here, gets written back, and reaches the browser live (WisdomReady
    # rides the generic broadcast at the bottom of this function -- no
    # separate live.py wiring needed for it).
    if event_type == "ReflectionFiled":
        user_id = event['data']['user_id']
        text = event['data']['text']
        wisdom = None
        try:
            if AI_ENABLED and ai_client is not None:
                response = ai_client.chat.completions.create(
                    model=AI_MODEL,
                    messages=[{
                        "role": "user",
                        "content": ("An Agent files their daily field report with you. It says: "
                                    f"\"{text[:600]}\" — Reply with ONE short word of wisdom in your own voice, "
                                    "1-2 sentences, no preamble, that honors what they said."),
                    }],
                    max_tokens=150,
                )
                wisdom = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[FIELD REPORT WORKER] Wisdom generation failed: {e}")
        if not wisdom:
            import random
            wisdom = random.choice(WISDOM_FALLBACKS)

        _db_execute(
            "UPDATE daily_reflections SET wisdom = %s WHERE user_id = %s::uuid AND reflection_date = CURRENT_DATE",
            (wisdom, user_id)
        )
        producer.send(topic_for_event("WisdomReady"), value={
            "event_type": "WisdomReady",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {"user_id": user_id, "wisdom": wisdom}
        })
        producer.flush()
        print(f"[FIELD REPORT WORKER] Wisdom ready for {user_id}.")

    # -------------------------------------------------------------
    # Live push — every processed event goes to connected browsers
    # -------------------------------------------------------------
    # The workers and the FastAPI app share one process/loop, so this is a
    # plain in-process fan-out (evoke/live.py). Browsers use it for
    # freshness only; the projections above remain the source of truth.
    live_hub.broadcast({"type": event_type, "data": event.get('data', {})})


async def evoke_workers_loop():
    await asyncio.sleep(5)

    try:
        consumer = KafkaConsumer(
            'evoke-events', 'minecraft-events',
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

#!/usr/bin/env python3
"""
Minecraft Reward Bridge - consumes RewardCollected events from Redpanda
and delivers rewards via RCON. Also runs a "heartbeat" loop (see
heartbeat_loop() below) that auto-links the first real Minecraft player to
the seeded Player One account and gives anyone online a small, continuous
sign the whole pipeline is alive: a trickle of XP, an occasional item, and
an occasional AI-generated in-character lore line.
"""

import asyncio
import json
import os
import random
import psycopg2
import requests
from psycopg2.pool import SimpleConnectionPool
import socket
import struct
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer

# Configuration
MINECRAFT_HOST = os.getenv("MINECRAFT_HOST", "minecraft")
MINECRAFT_PORT = int(os.getenv("MINECRAFT_RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "devsecret123")
REDPANDA_BROKER = os.getenv("REDPANDA_BROKER", "redpanda:29092")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://evoke:devsecret123@localhost:5432/evoke")
POLL_INTERVAL = 60  # Check for offline deliveries every 60s

# Heartbeat loop config -- deliberately small/rare. This is a liveness
# signal ("everything is working"), not a game-balance decision; see
# GAPS.md's "XP economy is undesigned" item for the real one.
HEARTBEAT_INTERVAL = 60
ONLINE_XP_AMOUNT = 5
ITEM_DROP_PROBABILITY = 0   # disabled during playtest -- was ~once per 10 online-minutes per player
LORE_MESSAGE_PROBABILITY = 0.05  # ~once per 20 online-minutes per player
PLAYER_ONE_EMAIL = "player1@evoke.local"  # must match evoke-infra/seed.py
# Off during real playtests -- ensure_first_player_linked() silently
# re-links the first unlinked online player to Player One on every
# heartbeat (every HEARTBEAT_INTERVAL) as long as Player One has no link,
# which fights any test of a genuine fresh-player linking flow (deleting
# the link doesn't stick -- it just gets re-created within a minute).
AUTO_LINK_PLAYER_ONE = os.getenv("AUTO_LINK_PLAYER_ONE", "true").lower() == "true"

# Presence loop -- faster than the heartbeat because it feeds the web's
# live "who's in the Basin" card, and 60s-stale presence reads as broken.
# Publishes on change immediately, and a keepalive snapshot every
# PRESENCE_KEEPALIVE seconds so the web side can distinguish "nobody
# online" from "bridge is down" (staleness check in /api/minecraft/status).
PRESENCE_INTERVAL = 15
PRESENCE_KEEPALIVE = 60

# Where the Keel Restoration Beacon gets built as the cohort advances the
# world state. Explicit coords via env for a real, curated world (pick a
# visible spot in Keel); unset, the bridge anchors it once, near the first
# player online at the moment of the first stage advance, and remembers
# the spot in Postgres (world_meta) so later stages stack on the same
# structure.
KEEL_BEACON_POS = os.getenv("KEEL_BEACON_POS", "")

# Routed through the LiteLLM gateway (GUARDRAILS_PLAN.md Phase 0/1), not
# straight at OpenWebUI -- same content-filter/Presidio guardrails as every
# other real AI call site in the app, since this one talks to a student's
# actual Minecraft chat.
AI_GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "http://litellm:4000")
AI_GATEWAY_KEY = os.getenv("AI_GATEWAY_KEY", "sk-devsecret123")

# Database pool
db_pool = SimpleConnectionPool(1, 5, DATABASE_URL)

def get_db_connection():
    return db_pool.getconn()

def return_db_connection(conn):
    db_pool.putconn(conn)

# Kafka producer (this service was consumer-only before -- XP has to go
# through the real event pipeline so workers.py's PROFILE WORKER updates
# the player-profile projection the web UI actually reads XP from; writing
# XP directly to Postgres here would silently desync from that projection)
_producer = None
def get_producer():
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=[REDPANDA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
    return _producer

# Mirrors evoke/clients.py's MINECRAFT_EVENT_TYPES exactly -- this process
# can't import the evoke package (separate service, separate deployment),
# so the two copies have to be kept in sync by hand if this list changes.
MINECRAFT_EVENT_TYPES = {
    "MinecraftPresence",
    "MinecraftLinkRequested",
    "MinecraftLinked",
    "ArenaWaveReached",
    "GauntletWaveReached",
    "RewardCollected",
}


def publish_event(event_type: str, data: dict):
    # Matches main.py's publish_event() envelope exactly -- workers.py
    # doesn't care which service published an event, only that the shape
    # matches what it already expects.
    event = {
        "event_type": event_type,
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    topic = "minecraft-events" if event_type in MINECRAFT_EVENT_TYPES else "evoke-events"
    get_producer().send(topic, value=event)
    get_producer().flush()

# RCON client — implements the actual Source RCON wire protocol
# (length-prefixed binary packets: SERVERDATA_AUTH=3, EXECCOMMAND=2).
#
# The previous version of this class sent raw text lines ("password ...\n",
# "list\n") over the socket, which is not RCON at all — the server accepts
# the TCP connection and then silently ignores everything, so every recv()
# returned b"". Nothing errored, but get_online_players() always parsed ""
# into [], which meant: no player ever read as online, no reward was ever
# delivered live, the heartbeat never auto-linked or XP-ticked anyone, and
# every in-game surface of the pipeline silently no-oped. Verified directly
# against the running server: the text approach gets empty responses; the
# packet protocol below authenticates and executes commands correctly.
class RCONClient:
    _AUTH = 3
    _EXECCOMMAND = 2

    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self._req_id = 0

    def _send_packet(self, ptype: int, payload: str) -> int:
        self._req_id += 1
        body = struct.pack("<ii", self._req_id, ptype) + payload.encode("utf-8") + b"\x00\x00"
        self.socket.sendall(struct.pack("<i", len(body)) + body)
        return self._req_id

    def _read_packet(self):
        raw_len = b""
        while len(raw_len) < 4:
            chunk = self.socket.recv(4 - len(raw_len))
            if not chunk:
                raise ConnectionError("RCON socket closed")
            raw_len += chunk
        (length,) = struct.unpack("<i", raw_len)
        data = b""
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise ConnectionError("RCON socket closed mid-packet")
            data += chunk
        req_id, ptype = struct.unpack("<ii", data[:8])
        return req_id, ptype, data[8:-2].decode("utf-8", errors="replace")

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self._send_packet(self._AUTH, self.password)
            req_id, _, _ = self._read_packet()
            if req_id == -1:  # protocol's explicit auth-failure marker
                print("RCON authentication failed (bad password)")
                self.close()
                return False
            return True
        except Exception as e:
            print(f"RCON connection failed: {e}")
            self.socket = None
            return False

    def execute_command(self, command: str) -> str:
        if not self.socket and not self.connect():
            return ""
        try:
            self._send_packet(self._EXECCOMMAND, command)
            _, _, payload = self._read_packet()
            return payload
        except Exception as e:
            print(f"RCON command failed: {e}")
            self.close()
            return ""

    def close(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None

    def get_online_players(self) -> list:
        """Get list of online player usernames"""
        try:
            response = self.execute_command("list")
            # Parse "There are X players online: player1, player2, ..."
            if "players online:" in response:
                player_str = response.split("players online:")[1].strip()
                if player_str:
                    return [p.strip() for p in player_str.split(",")]
            return []
        except:
            return []

# Reward delivery
def deliver_reward(rcon: RCONClient, player_name: str, reward: dict) -> bool:
    """Deliver a reward to a player"""
    try:
        reward_type = reward['reward_type']
        reward_value = reward['reward']
        amount = reward.get('reward_amount', 1)

        if reward_type == 'item':
            cmd = f"give {player_name} {reward_value} {amount}"
            rcon.execute_command(cmd)
        elif reward_type == 'effect':
            duration = reward.get('duration', 300)
            level = 1
            cmd = f"effect give {player_name} {reward_value} {duration // 20} {level}"
            rcon.execute_command(cmd)
        elif reward_type == 'command':
            cmd = reward_value.replace("<player>", player_name)
            rcon.execute_command(cmd)

        return True
    except Exception as e:
        print(f"Reward delivery failed: {e}")
        return False

async def process_event(event: dict):
    """Process a RewardCollected event"""
    try:
        event_type = event.get('event_type')
        data = event.get('data', {})

        if event_type == 'LevelUpped':
            handle_level_up(data)
            return
        if event_type == 'TeamWheelCompleted':
            handle_team_wheel(data)
            return
        if event_type == 'MissionCompleted':
            handle_mission_completed(data)
            return
        if event_type == 'WorldStateAdvanced':
            handle_world_advanced(data)
            return
        if event_type == 'MinecraftLinked':
            handle_minecraft_linked(data)
            return
        if event_type != 'RewardCollected':
            return

        award_id = data.get('award_id')
        user_id = data.get('user_id')
        mission_id = data.get('mission_id')
        tier = data.get('tier')

        print(f"Processing reward: award_id={award_id}, user_id={user_id}, tier={tier}")

        # Get player's Minecraft username
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT minecraft_username FROM minecraft_links WHERE user_id = %s::uuid AND server_id = 'default'",
                (user_id,)
            )
            result = cur.fetchone()
            if not result:
                print(f"No Minecraft link for user {user_id}")
                return

            player_name = result[0]

            # Get reward definition
            cur.execute(
                """SELECT reward_type, reward, reward_amount, duration, persistent FROM mc_reward_catalog
                   WHERE tier = %s LIMIT 1""",
                (tier,)
            )
            reward_result = cur.fetchone()
            if not reward_result:
                print(f"No reward catalog entry for tier {tier}")
                return

            reward_type, reward_value, amount, duration, persistent = reward_result
            reward = {
                'reward_type': reward_type,
                'reward': reward_value,
                'reward_amount': amount,
                'duration': duration,
                'persistent': persistent
            }

            # Create grant record
            cur.execute(
                """INSERT INTO mc_reward_grants (user_id, server_id, catalog_id, granted_at, active, executed)
                   SELECT %s::uuid, 'default', id, CURRENT_TIMESTAMP, true, false
                   FROM mc_reward_catalog WHERE tier = %s LIMIT 1""",
                (user_id, tier)
            )
            conn.commit()

            # Try to deliver immediately
            rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
            if rcon.connect():
                online_players = rcon.get_online_players()
                rcon.close()

                if player_name in online_players:
                    if deliver_reward(RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD), player_name, reward):
                        # Mark as executed
                        cur.execute(
                            "UPDATE mc_reward_grants SET executed = true WHERE user_id = %s::uuid ORDER BY granted_at DESC LIMIT 1",
                            (user_id,)
                        )
                        conn.commit()
                        print(f"✓ Delivered {tier} reward to {player_name}")
                else:
                    print(f"Player {player_name} offline, scheduled for later delivery")
        finally:
            cur.close()
            return_db_connection(conn)

    except Exception as e:
        print(f"Event processing error: {e}")

async def offline_delivery_loop():
    """Periodically check for pending offline rewards and deliver them"""
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)
            rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
            if not rcon.connect():
                continue

            online_players = rcon.get_online_players()
            rcon.close()

            conn = get_db_connection()
            try:
                cur = conn.cursor()

                # Get pending grants for online players
                cur.execute(
                    """SELECT g.id, g.user_id, c.reward_type, c.reward, c.reward_amount, c.duration
                       FROM mc_reward_grants g
                       JOIN mc_reward_catalog c ON g.catalog_id = c.id
                       JOIN minecraft_links ml ON g.user_id = ml.user_id
                       WHERE g.executed = false AND g.active = true
                       AND ml.minecraft_username = ANY(%s::text[])""",
                    (online_players,)
                )

                grants = cur.fetchall()
                for grant_id, user_id, reward_type, reward_value, amount, duration in grants:
                    player_name = None
                    # Find player name
                    for name in online_players:
                        cur.execute(
                            "SELECT user_id FROM minecraft_links WHERE minecraft_username = %s",
                            (name,)
                        )
                        if cur.fetchone()[0] == user_id:
                            player_name = name
                            break

                    if player_name:
                        reward = {
                            'reward_type': reward_type,
                            'reward': reward_value,
                            'reward_amount': amount,
                            'duration': duration
                        }

                        rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
                        if rcon.connect() and deliver_reward(rcon, player_name, reward):
                            cur.execute(
                                "UPDATE mc_reward_grants SET executed = true WHERE id = %s",
                                (grant_id,)
                            )
                            conn.commit()
                            print(f"✓ Offline delivery to {player_name}")
                        rcon.close()

            finally:
                cur.close()
                return_db_connection(conn)

        except Exception as e:
            print(f"Offline delivery loop error: {e}")

async def event_consumer_loop():
    """Consume events from Redpanda"""
    consumer = KafkaConsumer(
        'evoke-events', 'minecraft-events',
        bootstrap_servers=[REDPANDA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='minecraft-reward-bridge',
        auto_offset_reset='latest',
        enable_auto_commit=True
    )

    print("Minecraft Reward Bridge started, listening for events...")

    # Non-blocking poll, same pattern as evoke/workers.py -- the previous
    # `for message in consumer:` iterator blocks the thread indefinitely
    # between messages, which starved every other coroutine in the
    # asyncio.gather (offline delivery, heartbeat, presence): they ran
    # until their first await, then never again. With poll(), the event
    # loop breathes between batches and all four loops actually run.
    try:
        while True:
            msg_pack = consumer.poll(timeout_ms=500)
            for tp, messages in msg_pack.items():
                for message in messages:
                    try:
                        await process_event(message.value)
                    except Exception as e:
                        print(f"Event processing error (skipping one event): {e}")
            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"Consumer error: {e}")
        await asyncio.sleep(5)

_player_one_id_cache = None

def get_player_one_id(conn) -> str:
    """Player One's user_id, looked up once by its known-fixed email and
    cached -- it never changes for the life of this process."""
    global _player_one_id_cache
    if _player_one_id_cache:
        return _player_one_id_cache
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (PLAYER_ONE_EMAIL,))
        row = cur.fetchone()
        if row:
            _player_one_id_cache = str(row[0])
        return _player_one_id_cache
    finally:
        cur.close()

def ensure_first_player_linked(conn, online_players: list):
    """The first real Minecraft player this process ever sees online gets
    auto-linked to Player One -- a no-setup way to see the whole pipeline
    (XP, item drops, lore messages, mission reward delivery) actually
    working against a real login, not a seeded fake username. Only acts
    once: does nothing once Player One already has a link, and never
    steals a username someone else is already linked to."""
    player_one_id = get_player_one_id(conn)
    if not player_one_id or not online_players:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM minecraft_links WHERE user_id = %s::uuid AND server_id = 'default'",
            (player_one_id,)
        )
        if cur.fetchone():
            return  # already linked, nothing to do

        cur.execute(
            "SELECT minecraft_username FROM minecraft_links WHERE server_id = 'default' AND minecraft_username = ANY(%s::text[])",
            (online_players,)
        )
        already_linked = {r[0] for r in cur.fetchall()}
        candidate = next((p for p in online_players if p not in already_linked), None)
        if not candidate:
            return

        cur.execute(
            "INSERT INTO minecraft_links (user_id, server_id, minecraft_username) VALUES (%s::uuid, 'default', %s) ON CONFLICT DO NOTHING",
            (player_one_id, candidate)
        )
        conn.commit()
        print(f"✓ Auto-linked first-seen player '{candidate}' to Player One")
    finally:
        cur.close()

def get_online_linked_players(conn, online_players: list) -> dict:
    """{minecraft_username: user_id} for whichever online players already
    have a link -- run after ensure_first_player_linked so a just-linked
    Player One is included in the same heartbeat tick."""
    if not online_players:
        return {}
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT minecraft_username, user_id FROM minecraft_links WHERE server_id = 'default' AND minecraft_username = ANY(%s::text[])",
            (online_players,)
        )
        return {name: str(uid) for name, uid in cur.fetchall()}
    finally:
        cur.close()

ARENA_XP_PER_WAVE = 20
GAUNTLET_XP_PER_WAVE = 30


def _parse_scoreboard_value(response: str):
    """'<player> has <N> [<objective>]' -> N; None if the player has never
    touched that objective ("Can't get value of ... none is set")."""
    if "has" not in response:
        return None
    try:
        return int(response.split(" has ", 1)[1].split(" ", 1)[0])
    except (IndexError, ValueError):
        return None


def check_arena_progress(conn, rcon: "RCONClient", linked: dict):
    """Halyard Mob Arena web wiring: reads each online-linked player's
    arenaBestWave scoreboard (the datapack updates it in-world; this is the
    read-only bridge half). Own small table, same ownership split as
    world_meta (bridge-owned Postgres state, not main.py's schema) --
    mc_arena_best just remembers the last value we already granted XP for,
    so a heartbeat tick only reacts to a genuine new best, not the same
    wave reported again."""
    cur = conn.cursor()
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS mc_arena_best (user_id UUID PRIMARY KEY, best_wave INT NOT NULL DEFAULT 0)")
        conn.commit()
    finally:
        cur.close()

    for player_name, user_id in linked.items():
        response = rcon.execute_command(f"scoreboard players get {player_name} arenaBestWave")
        wave = _parse_scoreboard_value(response)
        if wave is None or wave <= 0:
            continue

        cur = conn.cursor()
        try:
            cur.execute("SELECT best_wave FROM mc_arena_best WHERE user_id = %s::uuid", (user_id,))
            row = cur.fetchone()
            known = row[0] if row else 0
            if wave <= known:
                continue
            cur.execute(
                """INSERT INTO mc_arena_best (user_id, best_wave) VALUES (%s::uuid, %s)
                   ON CONFLICT (user_id) DO UPDATE SET best_wave = EXCLUDED.best_wave""",
                (user_id, wave)
            )
            conn.commit()
        finally:
            cur.close()

        publish_event("XPGranted", {
            "user_id": user_id,
            "amount": ARENA_XP_PER_WAVE * (wave - known),
            "reason": "arena_wave",
        })
        publish_event("ArenaWaveReached", {"user_id": user_id, "wave": wave})
        print(f"✓ Arena progress: {player_name} reached wave {wave} (was {known})")


def check_gauntlet_progress(conn, rcon: "RCONClient", linked: dict):
    """The Mob Gauntlet's web wiring -- identical shape to
    check_arena_progress above, reading gauntletBestWave instead of
    arenaBestWave. Separate table (mc_gauntlet_best) since the two arenas
    are unrelated runs with independent progress, even though the ratchet/
    dedupe logic is the same idiom."""
    cur = conn.cursor()
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS mc_gauntlet_best (user_id UUID PRIMARY KEY, best_wave INT NOT NULL DEFAULT 0)")
        conn.commit()
    finally:
        cur.close()

    for player_name, user_id in linked.items():
        response = rcon.execute_command(f"scoreboard players get {player_name} gauntletBestWave")
        wave = _parse_scoreboard_value(response)
        if wave is None or wave <= 0:
            continue

        cur = conn.cursor()
        try:
            cur.execute("SELECT best_wave FROM mc_gauntlet_best WHERE user_id = %s::uuid", (user_id,))
            row = cur.fetchone()
            known = row[0] if row else 0
            if wave <= known:
                continue
            cur.execute(
                """INSERT INTO mc_gauntlet_best (user_id, best_wave) VALUES (%s::uuid, %s)
                   ON CONFLICT (user_id) DO UPDATE SET best_wave = EXCLUDED.best_wave""",
                (user_id, wave)
            )
            conn.commit()
        finally:
            cur.close()

        publish_event("XPGranted", {
            "user_id": user_id,
            "amount": GAUNTLET_XP_PER_WAVE * (wave - known),
            "reason": "gauntlet_wave",
        })
        publish_event("GauntletWaveReached", {"user_id": user_id, "wave": wave})
        print(f"✓ Gauntlet progress: {player_name} reached wave {wave} (was {known})")


def get_random_ambient_reward(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT reward_type, reward, reward_amount, duration, persistent
               FROM mc_reward_catalog WHERE tier = 'ambient' ORDER BY random() LIMIT 1"""
        )
        row = cur.fetchone()
        if not row:
            return None
        reward_type, reward_value, amount, duration, persistent = row
        return {"reward_type": reward_type, "reward": reward_value, "reward_amount": amount, "duration": duration}
    finally:
        cur.close()

def generate_lore_message() -> str:
    """A one-line, in-character 'did you know' fact from the real B1llbot
    model (GAME_DESIGN.md §10 persona, via OpenWebUI -- see
    evoke-infra/openwebui-bootstrap.py). A network/model failure here
    should never take down the heartbeat loop for other players, so this
    always returns *something* -- a plain fallback line if the call fails."""
    fallback = "Every drop counts. Even the small ones."
    try:
        r = requests.post(
            f"{AI_GATEWAY_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_GATEWAY_KEY}"},
            json={
                "model": "billbot",
                "messages": [{
                    "role": "user",
                    "content": "Give me one short 'did you know' fact about Keel, Halyard, Oasis, Alpha Dynamics, or the Brokers. ONE sentence only, in your own voice, no preamble."
                }],
            },
            timeout=90,
        )
        if r.status_code != 200:
            print(f"Lore message generation failed: HTTP {r.status_code}")
            return fallback
        text = (r.json().get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        return text or fallback
    except Exception as e:
        print(f"Lore message generation error: {e}")
        return fallback

def send_tellraw(rcon: "RCONClient", player_name: str, message: str):
    # json.dumps handles quote/backslash escaping into a valid Minecraft
    # JSON text component -- hand-escaping this string for the RCON command
    # line is exactly the kind of thing that silently breaks on an
    # apostrophe in the generated text otherwise.
    payload = json.dumps({"text": f"B1llbot: {message}", "color": "gray", "italic": True})
    rcon.execute_command(f"tellraw {player_name} {payload}")

# ---------------------------------------------------------------------------
# Transmedia reactions: web/cohort events made physical in the Basin
# ---------------------------------------------------------------------------

def _rcon():
    rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
    return rcon if rcon.connect() else None


def _linked_username(user_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT minecraft_username FROM minecraft_links WHERE user_id = %s::uuid AND server_id = 'default'",
            (user_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        return_db_connection(conn)


def handle_level_up(data: dict):
    """A learner ranked up on the web side -- if they're a linked, online
    player, make it land in-world: full-screen title, the classic level-up
    sound, a burst of totem particles. Version-safe commands only (title/
    playsound/particle), no NBT-heavy fireworks that break across
    Minecraft versions."""
    username = _linked_username(data.get('user_id', ''))
    if not username:
        return
    rcon = _rcon()
    if not rcon:
        return
    try:
        if username not in rcon.get_online_players():
            return
        level = data.get('level')
        title = data.get('title', '')
        rcon.execute_command(
            f'title {username} subtitle {json.dumps({"text": title, "color": "aqua"})}'
        )
        rcon.execute_command(
            f'title {username} title {json.dumps({"text": f"LEVEL {level}", "color": "gold", "bold": True})}'
        )
        rcon.execute_command(f'playsound minecraft:entity.player.levelup master {username}')
        rcon.execute_command(f'execute at {username} run particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.2 100')
        print(f"✓ In-game level-up celebration for {username} (Level {level} — {title})")
    finally:
        rcon.close()


def handle_mission_completed(data: dict):
    """Cohort visibility inside the game: any learner submitting mission
    evidence on the web announces in Basin chat, so players see the class
    moving even when the mover isn't in Minecraft at all. Skipped when
    nobody's online (no one to tell)."""
    rcon = _rcon()
    if not rcon:
        return
    try:
        if not rcon.get_online_players():
            return
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT display_name FROM users WHERE id = %s::uuid", (data.get('user_id', ''),))
            row = cur.fetchone()
            display_name = row[0] if row else "An agent"
        finally:
            return_db_connection(conn)
        payload = json.dumps([
            {"text": "✦ ", "color": "gold"},
            {"text": f"Agent {display_name} logged mission evidence — the Basin grows stronger.", "color": "yellow"},
        ])
        rcon.execute_command(f"tellraw @a {payload}")
    finally:
        rcon.close()


def _ensure_world_meta(conn):
    cur = conn.cursor()
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS world_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
    finally:
        cur.close()


def _get_beacon_anchor(conn, rcon: "RCONClient"):
    """(x, y, z) ground anchor for the Restoration Beacon. Priority:
    KEEL_BEACON_POS env (curated world, a chosen spot in Keel) > previously
    stored anchor (world_meta) > derive once from the first online player's
    position and store it. Returns None when nothing can be derived yet
    (nobody online at the moment of the advance) -- fine, because the
    builder always re-builds every layer up to the current stage, so the
    structure catches up on the next advance."""
    if KEEL_BEACON_POS:
        try:
            x, y, z = [int(float(p)) for p in KEEL_BEACON_POS.split()]
            return x, y, z
        except Exception:
            print(f"Bad KEEL_BEACON_POS {KEEL_BEACON_POS!r}; expected 'x y z'")

    _ensure_world_meta(conn)
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM world_meta WHERE key = 'beacon_pos'")
        row = cur.fetchone()
        if row:
            x, y, z = [int(p) for p in row[0].split()]
            return x, y, z

        players = rcon.get_online_players()
        if not players:
            return None
        # "Pos" query response looks like: "Player has the following entity
        # data: [12.5d, 64.0d, -3.25d]"
        response = rcon.execute_command(f"data get entity {players[0]} Pos")
        if "[" not in response:
            return None
        coords = response.split("[", 1)[1].split("]", 1)[0]
        px, py, pz = [int(float(c.strip().rstrip("d"))) for c in coords.split(",")]
        x, y, z = px + 6, py, pz + 6  # near, not on top of, the player
        rcon.execute_command(f"forceload add {x} {z}")  # survive chunk unloads for later stages
        cur.execute(
            "INSERT INTO world_meta (key, value) VALUES ('beacon_pos', %s) ON CONFLICT (key) DO NOTHING",
            (f"{x} {y} {z}",)
        )
        conn.commit()
        print(f"✓ Restoration Beacon anchored at {x} {y} {z} (near {players[0]})")
        return x, y, z
    finally:
        cur.close()


def _build_beacon(rcon: "RCONClient", anchor, stage: int, total_stages: int):
    """The physical, shared, growing monument to the cohort's progress: a
    polished-deepslate plinth plus one glowing column block per stage;
    completing the final stage caps it with a real, activated beacon
    (3x3 iron base + beacon block). Idempotent by construction -- every
    call rebuilds layers 1..stage, so a missed stage (server down, nobody
    online) self-heals on the next advance."""
    x, y, z = anchor
    # Idempotent + cheap; matters most for env-configured coords, whose
    # chunk may never have been loaded by a player at all.
    rcon.execute_command(f"forceload add {x-2} {z-2} {x+2} {z+2}")
    rcon.execute_command(f"fill {x-2} {y} {z-2} {x+2} {y} {z+2} minecraft:polished_deepslate")
    for n in range(1, stage + 1):
        block = "minecraft:sea_lantern" if n % 2 else "minecraft:glowstone"
        rcon.execute_command(f"setblock {x} {y+n} {z} {block}")
    if stage >= total_stages:
        rcon.execute_command(f"fill {x-1} {y+stage+1} {z-1} {x+1} {y+stage+1} {z+1} minecraft:iron_block")
        rcon.execute_command(f"setblock {x} {y+stage+2} {z} minecraft:beacon")


def handle_world_advanced(data: dict):
    """The cohort pushed Keel to a new restoration stage -- the flagship
    transmedia moment (GAPS.md #5). Everyone online gets the stage title
    full-screen, the narrative line in chat, a challenge-complete sound,
    totem particles, and the Restoration Beacon physically grows."""
    stage = data.get('stage', 0)
    total = data.get('total_stages', 8)
    title = data.get('title', '')
    narrative = data.get('narrative', '')

    rcon = _rcon()
    if not rcon:
        return
    try:
        rcon.execute_command(
            f'title @a subtitle {json.dumps({"text": title, "color": "aqua"})}'
        )
        rcon.execute_command(
            f'title @a title {json.dumps({"text": f"KEEL — STAGE {stage}", "color": "gold", "bold": True})}'
        )
        rcon.execute_command(
            f'tellraw @a {json.dumps([{"text": "⚡ ", "color": "gold"}, {"text": f"{title}: ", "color": "gold", "bold": True}, {"text": narrative, "color": "aqua"}])}'
        )
        rcon.execute_command("playsound minecraft:ui.toast.challenge_complete master @a")
        rcon.execute_command("execute at @a run particle minecraft:totem_of_undying ~ ~1 ~ 1 1 1 0.3 200")

        conn = get_db_connection()
        try:
            anchor = _get_beacon_anchor(conn, rcon)
        finally:
            return_db_connection(conn)
        if anchor:
            _build_beacon(rcon, anchor, stage, total)
            print(f"✓ Restoration Beacon grew to stage {stage} at {anchor}")
        else:
            print(f"World advanced to stage {stage}, but no beacon anchor yet (nobody online) — will catch up next stage")
    finally:
        rcon.close()


def handle_team_wheel(data: dict):
    """A whole team finished the same mission (GAME_DESIGN §7.1's Team
    Wheel) -- announce it in Basin chat, because 'nobody left behind' is
    exactly the ethic the shared world is supposed to celebrate."""
    rcon = _rcon()
    if not rcon:
        return
    try:
        if not rcon.get_online_players():
            return
        payload = json.dumps([
            {"text": "◎ ", "color": "aqua"},
            {"text": f"Team {data.get('team_name', 'Unknown')} — every member completed ", "color": "yellow"},
            {"text": data.get('mission_title', 'a mission'), "color": "gold", "bold": True},
            {"text": ". Nobody left behind.", "color": "yellow"},
        ])
        rcon.execute_command(f"tellraw @a {payload}")
        rcon.execute_command("playsound minecraft:ui.toast.challenge_complete master @a")
    finally:
        rcon.close()


def handle_minecraft_linked(data: dict):
    """The web app's two-channel link flow (evoke/main.py's confirm_link)
    is the first point a real minecraft_username is confirmed for a real
    EVOKE student -- whitelist them here instead of requiring a manual
    admin step. WHITELIST.md §4 originally proposed hooking this off the
    admin roster-import endpoint, but that endpoint no longer exists (team/
    roster provisioning moved to automatic Brightspace-login sync); this
    event does the same job at the point identity is actually confirmed.
    Doesn't require the player to still be online -- whitelist add works
    regardless of connection state."""
    username = data.get('minecraft_username')
    if not username:
        return
    rcon = _rcon()
    if not rcon:
        return
    try:
        rcon.execute_command(f"whitelist add {username}")
        print(f"✓ Whitelisted {username} after Minecraft link confirmation")
    finally:
        rcon.close()


# ---------------------------------------------------------------------------
# Scoreboard-driven quest completion: the world reports itself
# ---------------------------------------------------------------------------
# GAME_DESIGN §6.2's implementation note made real: the world's own
# mechanics (e.g. halyard_rent_functions' rentPaid scoreboard) complete
# quests automatically for linked players -- no self-report needed for
# mechanics the world can actually observe. Triggers live in
# mc_quest_triggers (seeded by the web app, extensible by world-builders
# without touching this code). Completion goes through the exact same
# idempotent path /api/mc-quests/{id}/submit uses: mc_quest_completions
# dedupe + QuestCompleted + XPGranted through the real pipeline.

QUEST_TRIGGER_INTERVAL = 30


def _score_for(rcon: "RCONClient", player: str, objective: str):
    """Read one player's score; None when unset/invalid. Response shape:
    '<player> has <N> [<objective>]' -- anything else means no score."""
    resp = rcon.execute_command(f"scoreboard players get {player} {objective}")
    if " has " not in resp:
        return None
    try:
        return int(resp.split(" has ", 1)[1].split()[0])
    except (ValueError, IndexError):
        return None


async def quest_trigger_loop():
    while True:
        try:
            await asyncio.sleep(QUEST_TRIGGER_INTERVAL)
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                # Linked players × triggers, minus already-completed quests.
                cur.execute(
                    """SELECT ml.minecraft_username, ml.user_id, t.quest_id, t.objective, t.threshold,
                              q.title, q.mission_id, q.kind
                       FROM mc_quest_triggers t
                       JOIN mc_quests q ON q.id = t.quest_id
                       CROSS JOIN minecraft_links ml
                       WHERE ml.server_id = 'default'
                         AND NOT EXISTS (SELECT 1 FROM mc_quest_completions c
                                         WHERE c.user_id = ml.user_id AND c.quest_id = t.quest_id)"""
                )
                pending = cur.fetchall()
            finally:
                return_db_connection(conn)

            if not pending:
                continue
            rcon = _rcon()
            if not rcon:
                continue
            try:
                for username, user_id, quest_id, objective, threshold, title, mission_id, kind in pending:
                    score = _score_for(rcon, username, objective)
                    if score is None or score < threshold:
                        continue
                    conn = get_db_connection()
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO mc_quest_completions (user_id, quest_id) VALUES (%s::uuid, %s::uuid) ON CONFLICT DO NOTHING",
                            (str(user_id), str(quest_id))
                        )
                        conn.commit()
                    finally:
                        return_db_connection(conn)
                    publish_event("QuestCompleted", {
                        "user_id": str(user_id),
                        "quest_id": str(quest_id),
                        "mission_id": str(mission_id) if mission_id else None,
                        "kind": kind,
                        "source": "scoreboard",
                    })
                    publish_event("XPGranted", {
                        "user_id": str(user_id),
                        "amount": 40,
                        "reason": "quest_completed",
                        "quest_id": str(quest_id),
                    })
                    if kind == "basin_archive":
                        payload = json.dumps([
                            {"text": "◈ ", "color": "aqua"},
                            {"text": f"Billbot recovered a memory: {title.replace('Archive: ', '')} — check your Field Tablet.", "color": "yellow"},
                        ])
                    else:
                        payload = json.dumps([
                            {"text": "✔ ", "color": "green"},
                            {"text": f"Quest logged: {title} — the Basin saw you do it.", "color": "yellow"},
                        ])
                    rcon.execute_command(f"tellraw {username} {payload}")
                    print(f"✓ Scoreboard trigger: {username} completed '{title}' ({objective}>={threshold}, score {score})")
            finally:
                rcon.close()
        except Exception as e:
            print(f"Quest trigger loop error: {e}")


# ---------------------------------------------------------------------------
# Presence: who's in the Basin right now (feeds the web's live card)
# ---------------------------------------------------------------------------

def _linked_players_info(conn, online_players: list) -> dict:
    """{minecraft_username: {user_id, display_name}} for online players
    with a link -- the web side wants names, not UUIDs."""
    if not online_players:
        return {}
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT ml.minecraft_username, u.id, u.display_name
               FROM minecraft_links ml JOIN users u ON u.id = ml.user_id
               WHERE ml.server_id = 'default' AND ml.minecraft_username = ANY(%s::text[])""",
            (online_players,)
        )
        return {name: {"user_id": str(uid), "display_name": dn} for name, uid, dn in cur.fetchall()}
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Two-channel Minecraft linking (BUILD_PLAN_2 §8)
# ---------------------------------------------------------------------------
# The web mints a 4-digit code; the player types `/trigger evoke_link set
# <code>` in-game (vanilla, player-executable, works on Bedrock via
# Geyser); this loop matches it and the learner's phone confirms. The
# trigger objective is (re-)created and (re-)enabled for online players
# every pass -- `/trigger` only works while enabled, and using it
# disables it again.

LINK_TRIGGER_INTERVAL = 10
LINK_OBJECTIVE = "evoke_link"
LINK_CODE_TTL_S = 600


async def link_code_loop():
    objective_ready = False
    while True:
        try:
            await asyncio.sleep(LINK_TRIGGER_INTERVAL)
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT code, user_id FROM mc_link_codes WHERE status = 'waiting' AND created_at > NOW() - INTERVAL '10 minutes'"
                )
                waiting = {code: str(uid) for code, uid in cur.fetchall()}
            finally:
                return_db_connection(conn)

            rcon = _rcon()
            if not rcon:
                continue
            try:
                if not objective_ready:
                    rcon.execute_command(f"scoreboard objectives add {LINK_OBJECTIVE} trigger")
                    objective_ready = True
                players = rcon.get_online_players()
                if not players:
                    continue
                rcon.execute_command(f"scoreboard players enable @a {LINK_OBJECTIVE}")
                if not waiting:
                    continue
                for player in players:
                    score = _score_for(rcon, player, LINK_OBJECTIVE)
                    if not score:
                        continue
                    rcon.execute_command(f"scoreboard players reset {player} {LINK_OBJECTIVE}")
                    rcon.execute_command(f"scoreboard players enable {player} {LINK_OBJECTIVE}")
                    if score not in waiting:
                        send_tellraw(rcon, player, "That code didn't match anything. Check your Field Kit and try again.")
                        continue
                    user_id = waiting.pop(score)
                    conn = get_db_connection()
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE mc_link_codes SET status = 'matched', minecraft_username = %s WHERE code = %s",
                            (player, score)
                        )
                        conn.commit()
                    finally:
                        return_db_connection(conn)
                    payload = json.dumps([
                        {"text": "✔ ", "color": "green"},
                        {"text": "Code accepted. Confirm the link on your Field Kit to finish.", "color": "yellow"},
                    ])
                    rcon.execute_command(f"tellraw {player} {payload}")
                    # The phone hears this over the live channel and pops
                    # the confirm; the REST poll is its fallback.
                    publish_event("MinecraftLinkRequested", {
                        "user_id": user_id, "minecraft_username": player, "code": score,
                    })
                    print(f"✓ Link code {score} matched by {player}; awaiting phone confirm")
            finally:
                rcon.close()
        except Exception as e:
            print(f"Link code loop error: {e}")


# ---------------------------------------------------------------------------
# Basin Archive world-progress detection + the Keel ticket office
# ---------------------------------------------------------------------------
# The web app seeds a 'basin_archive' quest chain (main.py) whose triggers
# are plain scoreboard objectives; this loop is what actually sets them.
# gotCoal is set by the world itself (verified command blocks at
# (-103,61,152)); the rest are bridge-observed: basinSeen when a linked
# player is online at all, and the position flags when a linked player is
# physically inside a named area. quest_trigger_loop then completes the
# quests through the normal pipeline — this loop never touches Postgres.

PROGRESS_INTERVAL = 15
PROGRESS_OBJECTIVES = ("basinSeen", "keelVisited", "minesVisited", "halyardVisited")
# (objective, (x1,y1,z1), (x2,y2,z2)) — inclusive world-coordinate boxes,
# all verified against the real world content (MINECRAFT_WORLD_MAP.md):
# Keel town bowl, the mines entrance street, the mines rooms themselves
# (players get teleported to y≈40, x -132..-104), and Halyard's day-job
# area including the train arrival point (5,93,96).
POSITION_FLAGS = (
    ("keelVisited", (-160, 40, 130), (30, 95, 240)),
    ("minesVisited", (-152, 55, 156), (-126, 78, 182)),
    ("minesVisited", (-145, 20, -125), (-90, 50, -70)),
    ("halyardVisited", (-25, 80, 40), (60, 110, 135)),
)


def _player_pos(rcon: "RCONClient", player: str):
    """[x, y, z] floats, or None. Response shape: '<player> has the
    following entity data: [12.5d, 64.0d, -3.25d]'"""
    resp = rcon.execute_command(f"data get entity {player} Pos")
    if "[" not in resp:
        return None
    try:
        coords = resp.split("[", 1)[1].split("]", 1)[0]
        return [float(c.strip().rstrip("d")) for c in coords.split(",")]
    except (ValueError, IndexError):
        return None


async def world_progress_loop():
    objectives_ready = False
    while True:
        try:
            await asyncio.sleep(PROGRESS_INTERVAL)
            rcon = _rcon()
            if not rcon:
                continue
            try:
                if not objectives_ready:
                    for obj in PROGRESS_OBJECTIVES:
                        rcon.execute_command(f"scoreboard objectives add {obj} dummy")
                    objectives_ready = True
                players = rcon.get_online_players()
                if not players:
                    continue
                conn = get_db_connection()
                try:
                    linked = get_online_linked_players(conn, players)
                finally:
                    return_db_connection(conn)
                for player in linked:
                    rcon.execute_command(f"scoreboard players set {player} basinSeen 1")
                    pos = _player_pos(rcon, player)
                    if not pos:
                        continue
                    x, y, z = pos
                    for obj, lo, hi in POSITION_FLAGS:
                        if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and lo[2] <= z <= hi[2]:
                            rcon.execute_command(f"scoreboard players set {player} {obj} 1")
            finally:
                rcon.close()
        except Exception as e:
            print(f"World progress loop error: {e}")


# The Keel economy office: coal selling + the Halyard ticket. Both were
# originally powered by the savs-common-economy mod's sign shops (the
# "[Admin Shop] | Coal | Buying" signs still standing in the mines rooms,
# and per the design docs "every coal sells back to Alpha's factory") —
# the school deployment doesn't run that mod, so the signs are dead and the
# train's paper ticket had no source at all. Until the mod is restored,
# this loop is Alpha's factory:
#   /trigger sellCoal  — sells every coal/coal block in inventory into the
#                        vanilla `money` scoreboard (the same currency the
#                        world's own Halyard machine already uses)
#   /trigger buyTicket — 300 credits -> the minecraft:paper the train at
#                        (-137,65,108) actually consumes
# Works for ALL online players, linked or not — the town economy shouldn't
# require a web account.

TICKET_OBJECTIVE = "buyTicket"
TICKET_PRICE = 100      # the original booth's price (shops.json: paper $100)
SELL_OBJECTIVE = "sellCoal"
COAL_PRICE = 1          # matches the mines' [Admin Shop] registration ($1/coal)
COAL_BLOCK_PRICE = 9    # 9 coal worth
ECONOMY_INTERVAL = 5


def _mod_balance(rcon: "RCONClient", player: str):
    """savs-common-economy balance via its console command. Response:
    \"<player>'s balance: $1000.0\" -- None if the mod didn't answer."""
    resp = rcon.execute_command(f"bal {player}")
    if "balance:" not in resp:
        return None
    try:
        return float(resp.split("balance:", 1)[1].strip().lstrip("$").replace(",", ""))
    except ValueError:
        return None


def _clear_count(rcon: "RCONClient", player: str, item: str) -> int:
    """Remove every <item> from the player and return how many were
    removed. Response shapes: 'Removed N matching item(s) from player X'
    or 'No items were found on player X'."""
    resp = rcon.execute_command(f"clear {player} {item}")
    if "Removed" not in resp:
        return 0
    try:
        return int(resp.split("Removed", 1)[1].strip().split(" ", 1)[0])
    except (ValueError, IndexError):
        return 0


async def ticket_office_loop():
    objectives_ready = False
    while True:
        try:
            await asyncio.sleep(ECONOMY_INTERVAL)
            rcon = _rcon()
            if not rcon:
                continue
            try:
                if not objectives_ready:
                    rcon.execute_command(f"scoreboard objectives add {TICKET_OBJECTIVE} trigger")
                    rcon.execute_command(f"scoreboard objectives add {SELL_OBJECTIVE} trigger")
                    objectives_ready = True
                players = rcon.get_online_players()
                if not players:
                    continue
                rcon.execute_command(f"scoreboard players enable @a {TICKET_OBJECTIVE}")
                rcon.execute_command(f"scoreboard players enable @a {SELL_OBJECTIVE}")
                for player in players:
                    if _score_for(rcon, player, SELL_OBJECTIVE):
                        rcon.execute_command(f"scoreboard players reset {player} {SELL_OBJECTIVE}")
                        rcon.execute_command(f"scoreboard players enable {player} {SELL_OBJECTIVE}")
                        coal = _clear_count(rcon, player, "minecraft:coal")
                        blocks = _clear_count(rcon, player, "minecraft:coal_block")
                        earned = coal * COAL_PRICE + blocks * COAL_BLOCK_PRICE
                        if earned:
                            rcon.execute_command(f"givemoney {player} {earned}")
                            balance = _mod_balance(rcon, player)
                            bal_txt = f" Balance: ${balance:g}." if balance is not None else ""
                            payload = json.dumps([
                                {"text": "⛏ ", "color": "gold"},
                                {"text": f"Alpha's factory bought {coal} coal and {blocks} coal blocks for ${earned}.{bal_txt}", "color": "yellow"},
                            ])
                            print(f"✓ Coal sale: {player} sold {coal}+{blocks}b for ${earned} (balance {balance})")
                        else:
                            payload = json.dumps([
                                {"text": "⛏ ", "color": "gray"},
                                {"text": "Nothing to sell — mine some coal first. The factory buys coal and coal blocks.", "color": "gray"},
                            ])
                        rcon.execute_command(f"tellraw {player} {payload}")

                    if not _score_for(rcon, player, TICKET_OBJECTIVE):
                        continue
                    rcon.execute_command(f"scoreboard players reset {player} {TICKET_OBJECTIVE}")
                    rcon.execute_command(f"scoreboard players enable {player} {TICKET_OBJECTIVE}")
                    balance = _mod_balance(rcon, player) or 0
                    if balance >= TICKET_PRICE:
                        rcon.execute_command(f"takemoney {player} {TICKET_PRICE}")
                        rcon.execute_command(f"give {player} minecraft:paper 1")
                        payload = json.dumps([
                            {"text": "🎫 ", "color": "gold"},
                            {"text": f"Ticket purchased for ${TICKET_PRICE}. Board the train to Halyard — it takes the ticket when you ride.", "color": "yellow"},
                        ])
                        print(f"✓ Ticket office: {player} bought a Halyard ticket (${balance:g} -> ${balance - TICKET_PRICE:g})")
                    else:
                        payload = json.dumps([
                            {"text": "🎫 ", "color": "gray"},
                            {"text": f"A ticket up to Halyard costs ${TICKET_PRICE} — you have ${balance:g}. Mine coal, then sell it at the mines shop or with /trigger sellCoal.", "color": "gray"},
                        ])
                    rcon.execute_command(f"tellraw {player} {payload}")
            finally:
                rcon.close()
        except Exception as e:
            print(f"Ticket office loop error: {e}")


async def presence_loop():
    """Publishes MinecraftPresence snapshots for the web's live "who's in
    the Basin" card. Change-triggered plus a keepalive every
    PRESENCE_KEEPALIVE seconds; /api/minecraft/status treats a silence
    longer than ~90s as "unknown", so the keepalive is what lets an empty
    server still read as *online*."""
    last_snapshot = None
    last_published = 0.0
    while True:
        try:
            await asyncio.sleep(PRESENCE_INTERVAL)
            rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
            server_online = rcon.connect()
            online_players = rcon.get_online_players() if server_online else []
            if server_online:
                rcon.close()

            linked = {}
            if online_players:
                conn = get_db_connection()
                try:
                    linked = _linked_players_info(conn, online_players)
                finally:
                    return_db_connection(conn)

            snapshot = (server_online, tuple(sorted(online_players)))
            now = asyncio.get_event_loop().time()
            if snapshot != last_snapshot or (now - last_published) >= PRESENCE_KEEPALIVE:
                publish_event("MinecraftPresence", {
                    "server_online": server_online,
                    "online_players": online_players,
                    "linked_players": linked,
                })
                last_snapshot = snapshot
                last_published = now
        except Exception as e:
            print(f"Presence loop error: {e}")


async def heartbeat_loop():
    """Runs continuously: auto-links the first real player to Player One,
    then gives everyone currently online a small XP tick plus occasional
    item/lore flavor. See the module docstring and GAPS.md for why this
    exists -- a zero-setup way to see the whole pipeline actually working."""
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
            if not rcon.connect():
                continue
            online_players = rcon.get_online_players()
            rcon.close()
            if not online_players:
                continue

            conn = get_db_connection()
            try:
                if AUTO_LINK_PLAYER_ONE:
                    ensure_first_player_linked(conn, online_players)
                linked = get_online_linked_players(conn, online_players)
            finally:
                return_db_connection(conn)

            if linked:
                arena_rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
                if arena_rcon.connect():
                    conn = get_db_connection()
                    try:
                        check_arena_progress(conn, arena_rcon, linked)
                        check_gauntlet_progress(conn, arena_rcon, linked)
                    finally:
                        return_db_connection(conn)
                    arena_rcon.close()

            for player_name, user_id in linked.items():
                publish_event("XPGranted", {
                    "user_id": user_id,
                    "amount": ONLINE_XP_AMOUNT,
                    "reason": "minecraft_online",
                })

                if random.random() < ITEM_DROP_PROBABILITY:
                    conn = get_db_connection()
                    try:
                        reward = get_random_ambient_reward(conn)
                    finally:
                        return_db_connection(conn)
                    if reward:
                        drop_rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
                        if drop_rcon.connect():
                            deliver_reward(drop_rcon, player_name, reward)
                            drop_rcon.close()
                            print(f"✓ Ambient item drop to {player_name}: {reward['reward']}")

                if random.random() < LORE_MESSAGE_PROBABILITY:
                    # Fire-and-forget: the model call can take up to ~90s
                    # (see main.py's identical timeout note), which
                    # shouldn't hold up XP/item delivery for every other
                    # online player waiting on this same loop iteration.
                    asyncio.create_task(send_lore_message(player_name))

        except Exception as e:
            print(f"Heartbeat loop error: {e}")

async def send_lore_message(player_name: str):
    try:
        message = await asyncio.to_thread(generate_lore_message)
        rcon = RCONClient(MINECRAFT_HOST, MINECRAFT_PORT, RCON_PASSWORD)
        if rcon.connect():
            send_tellraw(rcon, player_name, message)
            rcon.close()
            print(f"✓ Lore message to {player_name}: {message}")
    except Exception as e:
        print(f"Lore message delivery error: {e}")

async def main():
    """Main loop"""
    # Start all loops
    await asyncio.gather(
        event_consumer_loop(),
        offline_delivery_loop(),
        heartbeat_loop(),
        presence_loop(),
        quest_trigger_loop(),
        link_code_loop(),
        world_progress_loop(),
        ticket_office_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())

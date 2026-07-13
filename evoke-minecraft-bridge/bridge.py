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
ITEM_DROP_PROBABILITY = 0.1   # ~once per 10 online-minutes per player
LORE_MESSAGE_PROBABILITY = 0.05  # ~once per 20 online-minutes per player
PLAYER_ONE_EMAIL = "player1@evoke.local"  # must match evoke-infra/seed.py

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://open-webui:8080")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")

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
    get_producer().send("evoke-events", value=event)
    get_producer().flush()

# RCON client
class RCONClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self._authenticate()
            return True
        except Exception as e:
            print(f"RCON connection failed: {e}")
            return False

    def _authenticate(self):
        # RCON authentication
        auth_payload = f"password {self.password}\n"
        self.socket.sendall(auth_payload.encode())
        # Read response
        self.socket.recv(1024)

    def execute_command(self, command: str) -> str:
        if not self.socket:
            self.connect()

        try:
            self.socket.sendall(f"{command}\n".encode())
            response = self.socket.recv(4096).decode()
            return response
        except Exception as e:
            print(f"RCON command failed: {e}")
            self.connect()  # Reconnect
            return ""

    def close(self):
        if self.socket:
            self.socket.close()

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
        'evoke-events',
        bootstrap_servers=[REDPANDA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='minecraft-reward-bridge',
        auto_offset_reset='latest',
        enable_auto_commit=True
    )

    print("Minecraft Reward Bridge started, listening for events...")

    try:
        for message in consumer:
            event = message.value
            await process_event(event)
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
            f"{OPENWEBUI_URL}/api/chat/completions",
            headers={"Authorization": f"Bearer {OPENWEBUI_API_KEY}"} if OPENWEBUI_API_KEY else {},
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
                ensure_first_player_linked(conn, online_players)
                linked = get_online_linked_players(conn, online_players)
            finally:
                return_db_connection(conn)

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
        heartbeat_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())

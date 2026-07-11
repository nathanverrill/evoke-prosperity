#!/usr/bin/env python3
"""
Minecraft Reward Bridge - consumes RewardCollected events from Redpanda
and delivers rewards via RCON
"""

import asyncio
import json
import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import socket
from datetime import datetime
from kafka import KafkaConsumer

# Configuration
MINECRAFT_HOST = os.getenv("MINECRAFT_HOST", "minecraft")
MINECRAFT_PORT = int(os.getenv("MINECRAFT_RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "devsecret123")
REDPANDA_BROKER = os.getenv("REDPANDA_BROKER", "redpanda:29092")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://evoke:devsecret123@localhost:5432/evoke")
POLL_INTERVAL = 60  # Check for offline deliveries every 60s

# Database pool
db_pool = SimpleConnectionPool(1, 5, DATABASE_URL)

def get_db_connection():
    return db_pool.getconn()

def return_db_connection(conn):
    db_pool.putconn(conn)

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

async def main():
    """Main loop"""
    # Start both loops
    await asyncio.gather(
        event_consumer_loop(),
        offline_delivery_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())

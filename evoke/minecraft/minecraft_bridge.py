"""
Minecraft Bridge for EVOKE Prosperity

Delivers rewards to players on Minecraft servers.
Integrates with RCON for command execution.
Tracks reward deliveries and handles multiplayer scenarios.
"""

import logging
import os
from typing import Optional, Dict, List
from datetime import datetime

from .rcon_client import RconClient

logger = logging.getLogger(__name__)


class MinecraftBridge:
    """Bridge between EVOKE and Minecraft servers"""

    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 25575,
        rcon_password: str = "minecraft",
        timeout: float = 5.0,
    ):
        """
        Initialize Minecraft Bridge

        Args:
            server_host: Minecraft server hostname
            server_port: RCON port
            rcon_password: RCON password
            timeout: Connection timeout
        """
        self.server_host = server_host
        self.server_port = server_port
        self.rcon_password = rcon_password
        self.timeout = timeout
        self.connected = False
        self.delivery_history: List[Dict] = []

    async def connect(self) -> bool:
        """
        Connect to Minecraft server

        Returns:
            True if connection successful
        """
        try:
            self.rcon = RconClient(
                host=self.server_host,
                port=self.server_port,
                password=self.rcon_password,
                timeout=self.timeout,
            )

            connected = await self.rcon.connect()
            if connected:
                self.connected = True
                logger.info(f"Minecraft bridge connected to {self.server_host}:{self.server_port}")
            return connected

        except Exception as e:
            logger.error(f"Minecraft bridge connection failed: {e}")
            self.connected = False
            return False

    async def deliver_reward(
        self,
        player_name: str,
        reward_type: str,
        tier: str = "common",
        award_id: str = "",
    ) -> bool:
        """
        Deliver reward to player

        Args:
            player_name: Minecraft player name
            reward_type: Type of reward (badge, achievement, etc.)
            tier: Reward tier (common, epic, legendary)
            award_id: Award ID for tracking

        Returns:
            True if delivered successfully
        """
        if not self.connected:
            logger.error("Not connected to Minecraft server")
            return False

        try:
            items = self._get_reward_items(tier)

            # Give items to player
            for item, amount in items.items():
                success = await self.rcon.give_player_item(
                    player_name,
                    item,
                    amount
                )
                if not success:
                    logger.warning(f"Failed to give {item} to {player_name}")

            # Apply effect based on tier
            effect = self._get_reward_effect(tier)
            if effect:
                await self.rcon.apply_effect(
                    player_name,
                    effect["name"],
                    effect["duration"],
                    effect["amplifier"]
                )

            # Notify player
            message = self._get_reward_message(tier, award_id)
            await self.rcon.broadcast_message(f"{player_name} {message}")

            # Track delivery
            self._record_delivery(player_name, reward_type, tier, award_id)

            logger.info(f"Reward delivered to {player_name}: {tier} {reward_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to deliver reward to {player_name}: {e}")
            return False

    async def celebrate_achievement(
        self,
        player_name: str,
        achievement_name: str,
    ) -> bool:
        """
        Celebrate player achievement with effects

        Args:
            player_name: Player name
            achievement_name: Name of achievement

        Returns:
            True if successful
        """
        try:
            # Apply celebration effect
            await self.rcon.apply_effect(
                player_name,
                "glowing",
                duration=10,
                amplifier=0
            )

            # Broadcast message
            await self.rcon.broadcast_message(
                f"🎉 {player_name} unlocked: {achievement_name}!"
            )

            logger.info(f"Achievement celebrated for {player_name}: {achievement_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to celebrate achievement: {e}")
            return False

    async def apply_xp_boost(
        self,
        player_name: str,
        xp_amount: int = 100,
    ) -> bool:
        """
        Apply XP boost to player

        Args:
            player_name: Player name
            xp_amount: Amount of XP to add

        Returns:
            True if successful
        """
        try:
            command = f"experience add {player_name} {xp_amount}"
            response = await self.rcon.execute_command(command)
            return response is not None

        except Exception as e:
            logger.error(f"Failed to apply XP boost: {e}")
            return False

    async def get_online_players(self) -> Optional[List[str]]:
        """
        Get list of online players

        Returns:
            List of player names, or None if failed
        """
        try:
            response = await self.rcon.execute_command("list")

            if response and "players online" in response.lower():
                # Parse "There are X of max Y players online: player1, player2, ..."
                parts = response.split(": ")
                if len(parts) > 1:
                    players = [p.strip() for p in parts[1].split(",")]
                    return players

            return []

        except Exception as e:
            logger.error(f"Failed to get online players: {e}")
            return None

    async def check_server_health(self) -> bool:
        """
        Check if server is responding

        Returns:
            True if server healthy
        """
        try:
            response = await self.rcon.execute_command("help")
            return response is not None

        except Exception as e:
            logger.error(f"Server health check failed: {e}")
            return False

    def _get_reward_items(self, tier: str) -> Dict[str, int]:
        """
        Get items for reward tier

        Args:
            tier: Reward tier (common, epic, legendary)

        Returns:
            Dictionary of {item_id: amount}
        """
        rewards = {
            "common": {
                "diamond": 1,
                "iron_ingot": 5,
                "emerald": 2,
            },
            "epic": {
                "diamond": 5,
                "diamond_sword": 1,
                "emerald": 10,
                "enchanted_book": 1,
            },
            "legendary": {
                "diamond_block": 1,
                "netherite_ingot": 2,
                "enchanted_golden_apple": 1,
                "emerald": 32,
            },
        }

        return rewards.get(tier.lower(), rewards["common"])

    def _get_reward_effect(self, tier: str) -> Optional[Dict]:
        """
        Get potion effect for tier

        Args:
            tier: Reward tier

        Returns:
            Effect configuration or None
        """
        effects = {
            "common": {
                "name": "speed",
                "duration": 30,
                "amplifier": 1,
            },
            "epic": {
                "name": "strength",
                "duration": 60,
                "amplifier": 1,
            },
            "legendary": {
                "name": "strength",
                "duration": 120,
                "amplifier": 2,
            },
        }

        return effects.get(tier.lower())

    def _get_reward_message(self, tier: str, award_id: str) -> str:
        """
        Get message for reward tier

        Args:
            tier: Reward tier
            award_id: Award ID

        Returns:
            Message string
        """
        messages = {
            "common": "earned a Common Badge! 📕",
            "epic": "earned an Epic Badge! 📘",
            "legendary": "earned a Legendary Badge! 📙✨",
        }

        return messages.get(tier.lower(), "earned a Badge!")

    def _record_delivery(
        self,
        player_name: str,
        reward_type: str,
        tier: str,
        award_id: str,
    ) -> None:
        """
        Record reward delivery for tracking

        Args:
            player_name: Player name
            reward_type: Type of reward
            tier: Reward tier
            award_id: Award ID
        """
        self.delivery_history.append({
            "player": player_name,
            "reward_type": reward_type,
            "tier": tier,
            "award_id": award_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def disconnect(self) -> None:
        """Disconnect from Minecraft server"""
        if self.connected:
            await self.rcon.disconnect()
            self.connected = False
            logger.info("Minecraft bridge disconnected")

    def get_delivery_history(self) -> List[Dict]:
        """Get history of delivered rewards"""
        return self.delivery_history.copy()

    async def __aenter__(self):
        """Context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.disconnect()


# Global bridge instance
_bridge: Optional[MinecraftBridge] = None


def get_minecraft_bridge() -> MinecraftBridge:
    """
    Get or create global Minecraft bridge instance

    Returns:
        MinecraftBridge instance
    """
    global _bridge

    if _bridge is None:
        # Read from environment variables
        host = os.getenv("MINECRAFT_SERVER_HOST", "localhost")
        port = int(os.getenv("MINECRAFT_SERVER_PORT", "25575"))
        password = os.getenv("MINECRAFT_RCON_PASSWORD", "minecraft")
        timeout = float(os.getenv("MINECRAFT_RCON_TIMEOUT", "5.0"))

        _bridge = MinecraftBridge(
            server_host=host,
            server_port=port,
            rcon_password=password,
            timeout=timeout,
        )

    return _bridge

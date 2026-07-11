"""
Minecraft Integration Routes for FastAPI

Add these endpoints to evoke/main.py to enable Minecraft reward delivery.

Example:
    from evoke.minecraft_routes import setup_minecraft_routes

    app = FastAPI()
    setup_minecraft_routes(app)
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from evoke.minecraft import get_minecraft_bridge

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models
# ============================================================================

class RewardRequest(BaseModel):
    """Request to deliver reward to player"""
    player_name: str
    award_id: str
    tier: str = "common"  # common, epic, legendary
    reward_type: str = "badge"


class MinecraftStatusResponse(BaseModel):
    """Minecraft server status response"""
    connected: bool
    server_host: str
    server_port: int
    online_players: Optional[list] = None


# ============================================================================
# Routes
# ============================================================================

router = APIRouter(prefix="/api/minecraft", tags=["minecraft"])


@router.post("/reward/collect/{user_id}")
async def collect_reward(
    user_id: str,
    reward: RewardRequest,
) -> dict:
    """
    Collect reward from EVOKE and deliver to Minecraft

    This endpoint is called when a student collects an award in EVOKE.
    The reward is delivered to their Minecraft player.

    Args:
        user_id: EVOKE user ID
        reward: Reward details (player_name, award_id, tier)

    Returns:
        {"status": "success", "message": "Reward delivered"}

    Example:
        POST /api/minecraft/reward/collect/user-123
        {
            "player_name": "Steve",
            "award_id": "award-456",
            "tier": "legendary",
            "reward_type": "badge"
        }
    """
    try:
        bridge = get_minecraft_bridge()

        # Ensure bridge is connected
        if not bridge.connected:
            connected = await bridge.connect()
            if not connected:
                raise HTTPException(
                    status_code=503,
                    detail="Minecraft server unavailable"
                )

        # Deliver reward
        success = await bridge.deliver_reward(
            player_name=reward.player_name,
            reward_type=reward.reward_type,
            tier=reward.tier,
            award_id=reward.award_id,
        )

        if not success:
            logger.error(f"Failed to deliver reward to {reward.player_name}")
            raise HTTPException(
                status_code=500,
                detail="Failed to deliver reward"
            )

        logger.info(
            f"Reward delivered to {reward.player_name}: {reward.tier} {reward.reward_type}"
        )

        return {
            "status": "success",
            "message": f"Reward delivered to {reward.player_name}",
            "player": reward.player_name,
            "tier": reward.tier,
            "award_id": reward.award_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error collecting reward: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def minecraft_status() -> MinecraftStatusResponse:
    """
    Check Minecraft server status

    Returns:
        Minecraft connection status and online players

    Example:
        GET /api/minecraft/status
        {
            "connected": true,
            "server_host": "localhost",
            "server_port": 25575,
            "online_players": ["Steve", "Alex"]
        }
    """
    try:
        bridge = get_minecraft_bridge()

        # Ensure connected
        if not bridge.connected:
            connected = await bridge.connect()
            if not connected:
                return MinecraftStatusResponse(
                    connected=False,
                    server_host=bridge.server_host,
                    server_port=bridge.server_port,
                )

        # Get online players
        online_players = await bridge.get_online_players()

        return MinecraftStatusResponse(
            connected=True,
            server_host=bridge.server_host,
            server_port=bridge.server_port,
            online_players=online_players,
        )

    except Exception as e:
        logger.error(f"Error checking Minecraft status: {e}")
        return MinecraftStatusResponse(
            connected=False,
            server_host=bridge.server_host,
            server_port=bridge.server_port,
        )


@router.get("/players")
async def get_online_players() -> dict:
    """
    Get list of online players

    Returns:
        {"players": ["Steve", "Alex"], "count": 2}

    Example:
        GET /api/minecraft/players
    """
    try:
        bridge = get_minecraft_bridge()

        if not bridge.connected:
            connected = await bridge.connect()
            if not connected:
                raise HTTPException(
                    status_code=503,
                    detail="Minecraft server unavailable"
                )

        players = await bridge.get_online_players()

        if players is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to get players"
            )

        return {
            "players": players,
            "count": len(players),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/announce")
async def announce_message(message: str) -> dict:
    """
    Broadcast message to all players on server

    Args:
        message: Message to broadcast

    Returns:
        {"status": "success", "message": "Message announced"}

    Example:
        POST /api/minecraft/announce?message=Welcome%20to%20EVOKE!
    """
    try:
        bridge = get_minecraft_bridge()

        if not bridge.connected:
            connected = await bridge.connect()
            if not connected:
                raise HTTPException(
                    status_code=503,
                    detail="Minecraft server unavailable"
                )

        success = await bridge.rcon.broadcast_message(message)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to broadcast message"
            )

        return {
            "status": "success",
            "message": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error announcing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def minecraft_health() -> dict:
    """
    Health check for Minecraft integration

    Returns:
        {"status": "ok", "server_responding": bool}

    Example:
        GET /api/minecraft/health
    """
    try:
        bridge = get_minecraft_bridge()

        if not bridge.connected:
            connected = await bridge.connect()
            if not connected:
                return {
                    "status": "disconnected",
                    "server_responding": False,
                }

        health = await bridge.check_server_health()

        return {
            "status": "ok" if health else "unhealthy",
            "server_responding": health,
        }

    except Exception as e:
        logger.error(f"Error checking Minecraft health: {e}")
        return {
            "status": "error",
            "server_responding": False,
            "error": str(e),
        }


def setup_minecraft_routes(app) -> None:
    """
    Setup Minecraft routes on FastAPI app

    Args:
        app: FastAPI application instance

    Usage:
        from fastapi import FastAPI
        from evoke.minecraft_routes import setup_minecraft_routes

        app = FastAPI()
        setup_minecraft_routes(app)
    """
    app.include_router(router)
    logger.info("Minecraft routes configured")

"""
RCON (Remote Console) Client for Minecraft Servers

Handles communication with Minecraft servers via RCON protocol.
Supports both Java Edition and Bedrock Edition.
"""

import socket
import struct
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RconClient:
    """RCON client for Minecraft server communication"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 25575,
        password: str = "minecraft",
        timeout: float = 5.0,
    ):
        """
        Initialize RCON client

        Args:
            host: Minecraft server hostname/IP
            port: RCON port (default 25575)
            password: RCON password
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self.request_id = 0
        self.authenticated = False

    async def connect(self) -> bool:
        """
        Connect to Minecraft server

        Returns:
            True if connection successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()

            # Create socket connection
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)

            # Connect in thread pool to avoid blocking
            await loop.run_in_executor(
                None,
                self.socket.connect,
                (self.host, self.port)
            )

            logger.info(f"Connected to Minecraft server at {self.host}:{self.port}")

            # Authenticate
            return await self._authenticate()

        except Exception as e:
            logger.error(f"Failed to connect to Minecraft server: {e}")
            return False

    async def _authenticate(self) -> bool:
        """
        Authenticate with RCON server

        Returns:
            True if authentication successful
        """
        try:
            # Send login command
            await self._send_command(self.password, command_type=3)

            # Receive response
            response = await self._receive_response()

            if response is not None:
                self.authenticated = True
                logger.info("RCON authentication successful")
                return True
            else:
                logger.error("RCON authentication failed")
                return False

        except Exception as e:
            logger.error(f"RCON authentication error: {e}")
            return False

    async def execute_command(self, command: str) -> Optional[str]:
        """
        Execute command on Minecraft server

        Args:
            command: Command to execute (e.g., "give @p diamond")

        Returns:
            Command response, or None if failed
        """
        if not self.authenticated:
            logger.error("Not authenticated with RCON server")
            return None

        try:
            await self._send_command(command, command_type=2)
            response = await self._receive_response()
            return response

        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return None

    async def give_player_item(
        self,
        player_name: str,
        item: str,
        amount: int = 1,
    ) -> bool:
        """
        Give player an item

        Args:
            player_name: Player name or @p, @s, etc.
            item: Item ID (e.g., "diamond", "diamond_sword")
            amount: Number of items to give

        Returns:
            True if successful
        """
        command = f"give {player_name} {item} {amount}"
        response = await self.execute_command(command)
        return response is not None

    async def apply_effect(
        self,
        player_name: str,
        effect: str,
        duration: int = 30,
        amplifier: int = 0,
    ) -> bool:
        """
        Apply potion effect to player

        Args:
            player_name: Player name
            effect: Effect name (e.g., "speed", "strength")
            duration: Effect duration in seconds
            amplifier: Effect amplifier (0-255)

        Returns:
            True if successful
        """
        # Convert seconds to ticks (20 ticks = 1 second)
        ticks = duration * 20

        command = f"effect give {player_name} {effect} {ticks} {amplifier}"
        response = await self.execute_command(command)
        return response is not None

    async def broadcast_message(self, message: str) -> bool:
        """
        Broadcast message to all players

        Args:
            message: Message to broadcast

        Returns:
            True if successful
        """
        command = f"say {message}"
        response = await self.execute_command(command)
        return response is not None

    async def get_player_position(self, player_name: str) -> Optional[tuple]:
        """
        Get player position (requires datapacks)

        Args:
            player_name: Player name

        Returns:
            (x, y, z) coordinates or None if failed
        """
        command = f"data get entity {player_name} Pos"
        response = await self.execute_command(command)

        if response and "[" in response:
            try:
                # Parse coordinates from response
                # Response format: "X: 100.0, Y: 64.0, Z: 200.0"
                parts = response.split("[")[1].split("]")[0].split(",")
                coords = tuple(float(p.strip()) for p in parts)
                return coords
            except (ValueError, IndexError):
                return None

        return None

    async def teleport_player(
        self,
        player_name: str,
        x: float,
        y: float,
        z: float,
    ) -> bool:
        """
        Teleport player to coordinates

        Args:
            player_name: Player name
            x, y, z: Destination coordinates

        Returns:
            True if successful
        """
        command = f"tp {player_name} {x} {y} {z}"
        response = await self.execute_command(command)
        return response is not None

    async def _send_command(
        self,
        command: str,
        command_type: int = 2,
    ) -> bool:
        """
        Send RCON command packet

        Args:
            command: Command string
            command_type: 2=command, 3=login, 0=response

        Returns:
            True if sent successfully
        """
        if not self.socket:
            return False

        try:
            self.request_id += 1

            # Build RCON packet
            # Format: [Length (4 bytes)][RequestID (4 bytes)][Type (4 bytes)][Payload (variable)][Padding (2 bytes)]
            payload = command.encode("utf-8")
            packet_data = struct.pack("<i", self.request_id)
            packet_data += struct.pack("<i", command_type)
            packet_data += payload
            packet_data += b"\x00\x00"

            # Add length prefix
            packet_length = struct.pack("<i", len(packet_data))
            full_packet = packet_length + packet_data

            # Send packet
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.socket.sendall, full_packet)

            return True

        except Exception as e:
            logger.error(f"Failed to send RCON command: {e}")
            return False

    async def _receive_response(self) -> Optional[str]:
        """
        Receive RCON response packet

        Returns:
            Response string or None if failed
        """
        if not self.socket:
            return None

        try:
            loop = asyncio.get_event_loop()

            # Receive length
            length_data = await loop.run_in_executor(
                None,
                self.socket.recv,
                4
            )
            if not length_data or len(length_data) < 4:
                return None

            packet_length = struct.unpack("<i", length_data)[0]

            # Receive packet
            packet_data = await loop.run_in_executor(
                None,
                self.socket.recv,
                packet_length
            )

            if len(packet_data) < 10:
                return None

            # Parse packet
            request_id = struct.unpack("<i", packet_data[0:4])[0]
            response_type = struct.unpack("<i", packet_data[4:8])[0]
            response_text = packet_data[8:-2].decode("utf-8", errors="ignore")

            return response_text

        except Exception as e:
            logger.error(f"Failed to receive RCON response: {e}")
            return None

    async def disconnect(self) -> None:
        """Close RCON connection"""
        if self.socket:
            try:
                self.socket.close()
                logger.info("Disconnected from Minecraft server")
            except Exception as e:
                logger.error(f"Error closing RCON connection: {e}")
            finally:
                self.socket = None
                self.authenticated = False

    async def __aenter__(self):
        """Context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.disconnect()

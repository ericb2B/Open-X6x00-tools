"""TCI protocol client and message parsing."""

import asyncio
from typing import Dict, Callable, Optional
import websockets


class TCIParser:
    """Parser for TCI protocol messages."""
    
    @staticmethod
    def parse_info_message(data: bytes) -> Dict[str, str]:
        """Parse TCI info message and extract radio information."""
        result = {}
        try:
            # Extract the message part after "info:"
            message = data.decode('utf-8')[5:].strip()
            
            # Split by semicolon to get individual fields
            parts = message.split(';')
            
            # Process each field
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    result[key.strip().lower()] = value.strip()
                    
        except Exception as e:
            print(f"Error parsing TCI info: {e}")
            
        return result
    
    @staticmethod
    def format_s_meter(s_value: int) -> str:
        """Convert S-meter value to S-meter label."""
        if s_value >= 50:
            return f"S9+{s_value - 50}"
        elif s_value >= 40:
            return f"S9{chr(65 + (s_value - 40))}"
        else:
            return f"S{s_value}"


class TCIWebSocketClient:
    """WebSocket client for TCI protocol communication."""
    
    def __init__(self, ip: str, port: str, on_info_update: Optional[Callable] = None):
        self.uri = f"ws://{ip}:{port}"
        self.on_info_update = on_info_update
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            self._websocket = await websockets.connect(self.uri, max_size=None, ping_interval=20)
            self._connected = True
            return True
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            return False
    
    async def send(self, message: str) -> None:
        """Send a message to the server."""
        if self._websocket and self._connected:
            await self._websocket.send(message)
    
    async def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """Receive data from the server."""
        if not self._websocket or not self._connected:
            return None
            
        try:
            return await asyncio.wait_for(self._websocket.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"Receive error: {e}")
            return None
    
    async def start_audio(self) -> None:
        """Start audio streaming."""
        await self.send("audio_start:0;")
        await self.send("get_info;")
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._websocket:
            await self._websocket.close()
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._connected
"""WebSocket server for receiving audio from Glass/Phone devices.

This module implements a WebSocket server that receives PCM audio data from
Glass or phone apps and converts it to AudioFrame objects for processing.
"""
from __future__ import annotations

import asyncio
import struct
import time
from pathlib import Path
from typing import Callable

import numpy as np
import websockets
from websockets.server import WebSocketServerProtocol

from ..config import AppConfig
from ..logging_utils import log_event
from .audio_pipeline import AudioFrame


def pcm16_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert PCM 16-bit signed bytes to float32 normalized audio.

    Args:
        pcm_bytes: Raw PCM bytes (16-bit signed integers, little-endian)

    Returns:
        numpy array of float32 values in range [-1.0, 1.0]

    Example:
        pcm_bytes = b'\\x00\\x80\\xff\\x7f'  # -32768, 32767
        floats = pcm16_to_float32(pcm_bytes)
        # Returns: [-1.0, 0.999969482...]
    """
    if len(pcm_bytes) % 2 != 0:
        log_event("pcm_conversion_warning", {
            "message": "PCM bytes not multiple of 2, truncating",
            "length": len(pcm_bytes)
        })
        pcm_bytes = pcm_bytes[:-1]

    # Unpack as signed 16-bit integers (little-endian)
    num_samples = len(pcm_bytes) // 2
    pcm_int16 = struct.unpack(f'<{num_samples}h', pcm_bytes)

    # Convert to numpy array and normalize to [-1.0, 1.0]
    pcm_array = np.array(pcm_int16, dtype=np.float32)
    pcm_array /= 32768.0  # Divide by max int16 value

    return pcm_array


def float32_to_pcm16(float_audio: np.ndarray) -> bytes:
    """Convert float32 normalized audio to PCM 16-bit bytes.

    Args:
        float_audio: numpy array of float32 in range [-1.0, 1.0]

    Returns:
        Raw PCM bytes (16-bit signed integers, little-endian)
    """
    # Clip to valid range and scale to int16
    clipped = np.clip(float_audio, -1.0, 1.0)
    pcm_int16 = (clipped * 32767.0).astype(np.int16)

    # Pack as bytes
    return struct.pack(f'<{len(pcm_int16)}h', *pcm_int16)


class WebSocketAudioReceiver:
    """WebSocket server for receiving audio from remote devices.

    This server listens for WebSocket connections from Glass or phone apps,
    receives PCM audio data, and converts it to AudioFrame objects.

    Attributes:
        config: Application configuration
        on_audio_frame: Callback function called for each received frame
        server: Running WebSocket server instance
        clients: Set of connected client websockets
    """

    def __init__(
        self,
        config: AppConfig,
        on_audio_frame: Callable[[AudioFrame], None]
    ) -> None:
        """Initialize WebSocket audio receiver.

        Args:
            config: Application configuration with WebSocket settings
            on_audio_frame: Callback to handle each received audio frame
        """
        self.config = config
        self.on_audio_frame = on_audio_frame
        self.server = None
        self.clients: set[WebSocketServerProtocol] = set()
        self.is_running = False

    async def handle_client(
        self,
        websocket: WebSocketServerProtocol,
        path: str
    ) -> None:
        """Handle a connected WebSocket client.

        Args:
            websocket: Connected WebSocket client
            path: Request path (unused)
        """
        client_addr = websocket.remote_address
        log_event("websocket_client_connected", {
            "address": f"{client_addr[0]}:{client_addr[1]}",
            "path": path
        })

        self.clients.add(websocket)

        try:
            async for message in websocket:
                # Expecting binary PCM audio data
                if isinstance(message, bytes):
                    await self._process_audio_data(message)
                else:
                    log_event("websocket_text_message_ignored", {
                        "message": message[:100] if len(message) <= 100 else message[:100] + "..."
                    })

        except websockets.exceptions.ConnectionClosed as e:
            log_event("websocket_client_disconnected", {
                "address": f"{client_addr[0]}:{client_addr[1]}",
                "code": e.code,
                "reason": e.reason
            })

        except Exception as e:
            log_event("websocket_error", {
                "address": f"{client_addr[0]}:{client_addr[1]}",
                "error": str(e)
            })

        finally:
            self.clients.discard(websocket)

    async def _process_audio_data(self, pcm_bytes: bytes) -> None:
        """Process received PCM audio data.

        Args:
            pcm_bytes: Raw PCM 16-bit audio bytes
        """
        try:
            # Convert PCM to float
            float_samples = pcm16_to_float32(pcm_bytes)

            # Create AudioFrame
            frame = AudioFrame(
                timestamp=time.time(),
                samples=float_samples.tolist()
            )

            # Call the callback
            if self.on_audio_frame:
                self.on_audio_frame(frame)

            log_event("websocket_audio_frame_received", {
                "bytes": len(pcm_bytes),
                "samples": len(float_samples),
                "clients": len(self.clients)
            })

        except Exception as e:
            log_event("websocket_audio_processing_error", {
                "error": str(e),
                "bytes_length": len(pcm_bytes)
            })

    async def start_server(self) -> None:
        """Start the WebSocket server."""
        host = self.config.websocket.host
        port = self.config.websocket.port

        log_event("websocket_server_starting", {
            "host": host,
            "port": port
        })

        self.server = await websockets.serve(
            self.handle_client,
            host,
            port,
            # Increase message size limit for audio data
            max_size=10 * 1024 * 1024,  # 10 MB
            # Disable ping/pong timeout for audio streaming
            ping_timeout=None,
        )

        self.is_running = True

        log_event("websocket_server_started", {
            "host": host,
            "port": port,
            "listening": True
        })

        print(f"WebSocket server listening on ws://{host}:{port}")

    async def stop_server(self) -> None:
        """Stop the WebSocket server."""
        if self.server:
            log_event("websocket_server_stopping", {
                "active_clients": len(self.clients)
            })

            self.server.close()
            await self.server.wait_closed()
            self.is_running = False

            log_event("websocket_server_stopped", {})

    def start(self) -> None:
        """Start the WebSocket server in a background event loop.

        This method is non-blocking and starts the server in the asyncio loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.start_server())
        loop.run_forever()

    def stop(self) -> None:
        """Stop the WebSocket server."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.stop_server())


class WebSocketAudioStream:
    """Synchronous wrapper for WebSocket audio receiver.

    Provides a simpler interface for integrating with the existing
    audio pipeline that expects synchronous audio frames.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize WebSocket audio stream.

        Args:
            config: Application configuration
        """
        self.config = config
        self.frames: list[AudioFrame] = []
        self.receiver: WebSocketAudioReceiver | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    def _on_frame_received(self, frame: AudioFrame) -> None:
        """Callback for received audio frames.

        Args:
            frame: Received audio frame
        """
        self.frames.append(frame)

    def start(self) -> None:
        """Start receiving audio from WebSocket."""
        import threading

        self.receiver = WebSocketAudioReceiver(
            self.config,
            self._on_frame_received
        )

        # Start WebSocket server in background thread
        def run_server():
            self.receiver.start()

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

        log_event("websocket_stream_started", {
            "host": self.config.websocket.host,
            "port": self.config.websocket.port
        })

    def stop(self) -> None:
        """Stop receiving audio."""
        if self.receiver:
            self.receiver.stop()

        log_event("websocket_stream_stopped", {
            "frames_received": len(self.frames)
        })

    def get_frames(self) -> list[AudioFrame]:
        """Get all received audio frames.

        Returns:
            List of audio frames received since last call
        """
        frames = self.frames.copy()
        self.frames.clear()
        return frames


__all__ = [
    "WebSocketAudioReceiver",
    "WebSocketAudioStream",
    "pcm16_to_float32",
    "float32_to_pcm16",
]

#!/usr/bin/env python3
"""Test WebSocket client for AR-SmartAssistant.

This script simulates a Google Glass device sending audio to the PC WebSocket server.
It generates a test tone and sends it as PCM 16-bit audio in 100ms chunks.

Usage:
    python test_websocket_client.py [--host HOST] [--port PORT] [--duration SECONDS]

Example:
    python test_websocket_client.py --host localhost --port 8765 --duration 5
"""
from __future__ import annotations

import argparse
import asyncio
import struct
import sys

import numpy as np

try:
    import websockets
except ImportError:
    print("Error: websockets package not installed")
    print("Install with: pip install websockets")
    sys.exit(1)


async def send_test_audio(
    host: str = "localhost",
    port: int = 8765,
    duration: float = 3.0,
    frequency: float = 440.0,
) -> None:
    """Send test audio to WebSocket server.

    Args:
        host: WebSocket server hostname
        port: WebSocket server port
        duration: Duration of test audio in seconds
        frequency: Frequency of test tone in Hz
    """
    uri = f"ws://{host}:{port}"
    print(f"{'='*60}")
    print(f"WebSocket Audio Test Client")
    print(f"{'='*60}")
    print(f"Server: {uri}")
    print(f"Duration: {duration}s")
    print(f"Frequency: {frequency} Hz")
    print(f"Sample Rate: 16000 Hz")
    print(f"Encoding: PCM 16-bit signed little-endian")
    print(f"Chunk Size: 3200 bytes (100ms)")
    print(f"{'='*60}\n")

    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✓ Connected successfully!\n")

            # Generate test PCM audio (sine wave tone)
            sample_rate = 16000
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = np.sin(2 * np.pi * frequency * t)

            # Convert to PCM 16-bit signed integers
            audio = (audio * 32767).astype(np.int16)

            # Send in 100ms chunks (1600 samples = 3200 bytes)
            chunk_size = 1600  # 100ms at 16kHz
            total_chunks = len(audio) // chunk_size
            bytes_sent = 0

            print(f"Sending {total_chunks} chunks...")
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i : i + chunk_size]

                # Pack as PCM 16-bit little-endian
                pcm_bytes = struct.pack(f"<{len(chunk)}h", *chunk)

                # Send to WebSocket server
                await websocket.send(pcm_bytes)

                bytes_sent += len(pcm_bytes)
                chunk_num = (i // chunk_size) + 1
                print(
                    f"  [{chunk_num}/{total_chunks}] Sent {len(pcm_bytes)} bytes "
                    f"(total: {bytes_sent:,} bytes)"
                )

                # Simulate real-time streaming (100ms delay)
                await asyncio.sleep(0.1)

            print(f"\n✓ Test completed successfully!")
            print(f"Total sent: {bytes_sent:,} bytes")
            print(f"Duration: {duration}s")

    except websockets.exceptions.WebSocketException as e:
        print(f"\n❌ WebSocket error: {e}", file=sys.stderr)
        print("\nTroubleshooting:")
        print("1. Is the server running? (./run_ui.sh)")
        print("2. Is WebSocket enabled in config.yaml?")
        print("3. Check firewall allows port 8765")
        sys.exit(1)

    except ConnectionRefusedError:
        print(f"\n❌ Connection refused to {uri}", file=sys.stderr)
        print("\nServer is not running or not accepting connections")
        print("Start the server with: ./run_ui.sh")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Parse arguments and run test."""
    parser = argparse.ArgumentParser(
        description="Test WebSocket audio streaming to AR-SmartAssistant server"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="WebSocket server hostname (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket server port (default: 8765)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Duration of test audio in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--frequency",
        type=float,
        default=440.0,
        help="Frequency of test tone in Hz (default: 440.0 = A4 note)",
    )

    args = parser.parse_args()

    # Run async test
    asyncio.run(
        send_test_audio(
            host=args.host,
            port=args.port,
            duration=args.duration,
            frequency=args.frequency,
        )
    )


if __name__ == "__main__":
    main()

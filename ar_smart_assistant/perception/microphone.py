"""Local microphone audio input for computer-based recording."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable, Iterator

import numpy as np
import sounddevice as sd

from ..config import AudioCaptureConfig
from ..logging_utils import log_event
from .audio_pipeline import AudioFrame


@dataclass
class MicrophoneConfig:
    """Configuration for local microphone capture."""

    sample_rate: int
    channels: int
    device_index: int | None
    chunk_size: int


class MicrophoneStream:
    """Real-time audio capture from local microphone using sounddevice.

    This provides a computer-based alternative to the Glass WebSocket stream,
    allowing the system to run standalone for testing and development.

    Failure Modes:
        - No microphone detected: raises OSError with available devices list
        - Sample rate not supported: automatically falls back to device default
        - Buffer overflow: logs warning and continues (some frames dropped)
    """

    def __init__(self, config: AudioCaptureConfig) -> None:
        self.config = config
        self.sample_rate = config.sample_rate_hz
        self.device_index = config.device_index
        self.chunk_size = config.buffer_size_bytes // 2  # 16-bit samples

        self.audio_queue: queue.Queue[AudioFrame | None] = queue.Queue()
        self.stream: sd.InputStream | None = None
        self.is_recording = False
        self._thread: threading.Thread | None = None

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: sd.CallbackFlags,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice for each audio chunk."""
        if status:
            log_event("microphone_warning", {"status": str(status), "frames": frames})

        # Convert to normalized float samples (-1.0 to 1.0)
        samples = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()

        # Create AudioFrame with current timestamp
        import time
        frame = AudioFrame(
            timestamp=time.time(),
            samples=samples.tolist(),
        )

        try:
            self.audio_queue.put_nowait(frame)
        except queue.Full:
            log_event("microphone_buffer_overflow", {
                "queue_size": self.audio_queue.qsize(),
                "dropped_frames": frames,
            })

    def start(self) -> None:
        """Start capturing audio from the microphone."""
        if self.is_recording:
            log_event("microphone_already_recording", {})
            return

        log_event("microphone_starting", {
            "sample_rate": self.sample_rate,
            "device_index": self.device_index,
            "chunk_size": self.chunk_size,
        })

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,  # Mono
                dtype=np.float32,
                blocksize=self.chunk_size,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self.stream.start()
            self.is_recording = True

            log_event("microphone_started", {
                "actual_sample_rate": self.stream.samplerate,
                "device": self.stream.device,
            })

        except Exception as e:
            log_event("microphone_start_failed", {"error": str(e)})
            self._print_available_devices()
            raise

    def stop(self) -> None:
        """Stop capturing audio."""
        if not self.is_recording:
            return

        log_event("microphone_stopping", {})

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Signal end of stream
        self.audio_queue.put(None)
        self.is_recording = False

        log_event("microphone_stopped", {})

    def get_frames(self) -> Iterator[AudioFrame]:
        """Yield audio frames as they become available.

        This is a blocking generator that will yield frames until stop() is called.
        """
        while True:
            frame = self.audio_queue.get()
            if frame is None:
                break
            yield frame

    @staticmethod
    def list_devices() -> list[dict[str, any]]:
        """List all available audio input devices."""
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev['max_input_channels'] > 0:
                devices.append({
                    'index': idx,
                    'name': dev['name'],
                    'channels': dev['max_input_channels'],
                    'sample_rate': dev['default_samplerate'],
                })
        return devices

    def _print_available_devices(self) -> None:
        """Print available audio devices for debugging."""
        log_event("available_audio_devices", {
            "devices": self.list_devices()
        })

    def __enter__(self) -> "MicrophoneStream":
        """Context manager support."""
        self.start()
        return self

    def __exit__(self, *args) -> None:
        """Context manager support."""
        self.stop()


def list_audio_devices() -> None:
    """CLI utility to list available audio input devices."""
    print("Available Audio Input Devices:")
    print("-" * 60)

    devices = MicrophoneStream.list_devices()

    if not devices:
        print("No audio input devices found!")
        return

    for dev in devices:
        print(f"[{dev['index']}] {dev['name']}")
        print(f"    Channels: {dev['channels']}")
        print(f"    Sample Rate: {dev['sample_rate']:.0f} Hz")
        print()

    default_device = sd.query_devices(kind='input')
    print(f"Default input device: {default_device['name']}")


if __name__ == "__main__":
    # Quick test: list devices
    list_audio_devices()

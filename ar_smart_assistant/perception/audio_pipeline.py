"""Simplified audio pipeline for the AR-SmartAssistant reference app."""
from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Iterable, List, Sequence

from ..config import AppConfig
from ..database.repository import (
    AudioSegmentRecord,
    BrainDatabase,
    RawEventRecord,
    utcnow,
)
from ..logging_utils import log_event, sanitize_identifier


@dataclass
class AudioFrame:
    """PCM samples captured during a frame period.

    Enhanced with metadata for validation and debugging.

    Attributes:
        timestamp: Unix timestamp when frame was captured
        samples: Normalized float32 audio samples [-1.0, 1.0]
        sample_rate: Audio sample rate in Hz (for validation)
        source: Audio source identifier ("microphone", "websocket", etc.)
        sequence_number: Frame sequence number for detecting drops
    """

    timestamp: float
    samples: Sequence[float]
    sample_rate: int = 16000
    source: str = "unknown"
    sequence_number: int = 0

    def __post_init__(self) -> None:
        """Validate frame after initialization."""
        if not self.samples:
            raise ValueError("AudioFrame samples cannot be empty")
        if self.sample_rate <= 0:
            raise ValueError(f"Invalid sample_rate: {self.sample_rate}")
        # Validate sample range (only first/last for performance)
        if self.samples:
            for sample in [self.samples[0], self.samples[-1]]:
                if not -1.5 <= sample <= 1.5:  # Allow slight overflow
                    raise ValueError(f"Sample out of range [-1.5, 1.5]: {sample}")

    @property
    def duration_ms(self) -> float:
        """Calculate actual frame duration in milliseconds."""
        return (len(self.samples) / self.sample_rate) * 1000.0

    @property
    def rms_energy_db(self) -> float:
        """Calculate RMS energy in dB (cached)."""
        from .audio_pipeline import VadDetector
        return VadDetector.calculate_rms_db(self.samples)


@dataclass
class TranscriptEvent:
    session_id: int
    transcript: str
    asr_confidence: float
    speaker_id: str
    speaker_confidence: float
    predicted_intent: str
    audio_segment_id: int


class FrameRebuffer:
    """Rebuffer incoming audio frames to match VAD frame duration.

    Handles mismatch between incoming frame size (e.g., 100ms from WebSocket/mic)
    and VAD expected frame size (e.g., 30ms from config).

    Example:
        Input: 100ms frames (1600 samples @ 16kHz)
        Output: 30ms frames (480 samples @ 16kHz)
        Result: Each input frame yields 3 output frames + 160 samples buffered
    """

    def __init__(self, target_frame_duration_ms: int, sample_rate: int = 16000) -> None:
        """Initialize rebuffer.

        Args:
            target_frame_duration_ms: Desired output frame duration in ms
            sample_rate: Audio sample rate in Hz
        """
        self.target_frame_duration_ms = target_frame_duration_ms
        self.sample_rate = sample_rate
        self.target_samples_per_frame = int((target_frame_duration_ms / 1000.0) * sample_rate)
        self._buffer: list[float] = []
        self._sequence_counter = 0

    def rebuffer(self, frames: Iterable[AudioFrame]) -> Iterable[AudioFrame]:
        """Rebuffer frames to target duration.

        Args:
            frames: Input frames of any duration

        Yields:
            Frames of target_frame_duration_ms duration
        """
        for frame in frames:
            # Add samples to buffer
            self._buffer.extend(frame.samples)

            # Yield target-sized frames while we have enough samples
            while len(self._buffer) >= self.target_samples_per_frame:
                output_samples = self._buffer[:self.target_samples_per_frame]
                self._buffer = self._buffer[self.target_samples_per_frame:]

                yield AudioFrame(
                    timestamp=frame.timestamp,
                    samples=output_samples,
                    sample_rate=frame.sample_rate,
                    source=frame.source,
                    sequence_number=self._sequence_counter,
                )
                self._sequence_counter += 1

    def flush(self) -> Iterable[AudioFrame]:
        """Flush remaining buffered samples as final frame.

        Yields:
            Final frame with remaining buffered samples (may be smaller than target)
        """
        if self._buffer:
            import time
            yield AudioFrame(
                timestamp=time.time(),
                samples=self._buffer,
                sample_rate=self.sample_rate,
                source="rebuffer_flush",
                sequence_number=self._sequence_counter,
            )
            self._buffer = []
            self._sequence_counter += 1


class VadDetector:
    """Energy-based VAD with proper RMS calculation.

    Now uses correct RMS (Root Mean Square) energy formula:
    RMS_dB = 20 * log10(sqrt(mean(sample^2)))

    This is equivalent to:
    RMS_dB = 10 * log10(mean(sample^2))
    """

    def __init__(self, energy_threshold_db: float, min_speech_frames: int, padding_frames: int) -> None:
        self.energy_threshold_db = energy_threshold_db
        self.min_speech_frames = min_speech_frames
        self.padding_frames = padding_frames

    def segment(self, frames: Iterable[AudioFrame]) -> list[list[AudioFrame]]:
        """Segment audio frames into speech segments using energy-based VAD."""
        active_segment: list[AudioFrame] = []
        result: list[list[AudioFrame]] = []
        silence_count = 0

        for frame in frames:
            energy = self.calculate_rms_db(frame.samples)
            if energy > self.energy_threshold_db:
                active_segment.append(frame)
                silence_count = 0
            elif active_segment:
                silence_count += 1
                active_segment.append(frame)
                if silence_count >= self.padding_frames:
                    if len(active_segment) >= self.min_speech_frames:
                        result.append(active_segment[:-self.padding_frames])
                    active_segment = []
                    silence_count = 0

        if len(active_segment) >= self.min_speech_frames:
            result.append(active_segment)
        return result

    @staticmethod
    def calculate_rms_db(samples: Sequence[float]) -> float:
        """Calculate RMS energy in dB using correct formula.

        Formula: 20 * log10(RMS) where RMS = sqrt(mean(sample^2))
        Equivalent to: 10 * log10(mean(sample^2))

        Args:
            samples: Normalized audio samples [-1.0, 1.0]

        Returns:
            Energy in dB. Returns -120 dB for silence (empty or zero samples).
        """
        if not samples:
            return -120.0

        # Calculate mean of squared samples
        mean_square = fmean(sample * sample for sample in samples)

        # Handle silence (avoid log(0))
        if mean_square < 1e-10:
            return -120.0

        # Convert to dB: 10 * log10(mean_square)
        # This is equivalent to: 20 * log10(sqrt(mean_square))
        rms_db = 10.0 * math.log10(mean_square)
        return rms_db

    @staticmethod
    def _frame_energy(samples: Sequence[float]) -> float:
        """Legacy method for backward compatibility."""
        return VadDetector.calculate_rms_db(samples)


class MockAsrModel:
    """Heuristic ASR used for development without GPU dependencies."""

    def transcribe(self, segment: Sequence[AudioFrame]) -> tuple[str, float]:
        if not segment:
            return "", 0.0
        avg_energy = fmean(VadDetector._frame_energy(frame.samples) for frame in segment)
        words = ["hmm", "note", "remember", "buy", "call"]
        idx = min(int(max(avg_energy + 60, 0) // 5), len(words) - 1)
        transcript = f"{words[idx]} segment".strip()
        confidence = min(1.0, max(0.1, (avg_energy + 60) / 60))
        return transcript, confidence


class SpeakerIdentifier:
    """Energy-based heuristic speaker recognizer."""

    def __init__(self, self_threshold: float) -> None:
        self.self_threshold = self_threshold

    def identify(self, segment: Sequence[AudioFrame]) -> tuple[str, float]:
        if not segment:
            return "unknown", 0.0
        avg = fmean(VadDetector._frame_energy(frame.samples) for frame in segment)
        if avg > self.self_threshold:
            return "self", 0.85
        return "unknown", 0.55


class AudioPipeline:
    """Pipeline that writes transcript events to the database.

    Failure Modes:
        - ``IOError`` when writing audio spans to disk. The caller receives the
          raised exception so it can surface the error in the debug UI.
        - ``sqlite3.Error`` bubbling from :class:`BrainDatabase`. The caller must
          decide whether to pause the session or retry.
    """

    def __init__(self, config: AppConfig, database: BrainDatabase) -> None:
        self.config = config
        self.database = database
        vad_frames = config.audio.vad.min_speech_duration_ms // config.audio.vad.frame_duration_ms
        padding_frames = config.audio.vad.padding_duration_ms // config.audio.vad.frame_duration_ms
        self.vad = VadDetector(config.audio.vad.energy_threshold_db, vad_frames, padding_frames)
        self.rebuffer = FrameRebuffer(
            target_frame_duration_ms=config.audio.vad.frame_duration_ms,
            sample_rate=config.audio.capture.sample_rate_hz,
        )
        self.asr = MockAsrModel()
        self.speaker_identifier = SpeakerIdentifier(config.audio.speaker_id.self_match_threshold * 100)
        self.segment_root = config.storage_root / "audio_segments"
        self.segment_root.mkdir(parents=True, exist_ok=True)

    def process_frames(self, session_id: int, frames: Iterable[AudioFrame]) -> list[TranscriptEvent]:
        """Process audio frames through VAD, ASR, and speaker ID.

        Now includes frame rebuffering to handle duration mismatches.
        """
        # Rebuffer frames to match VAD frame duration
        rebuffered_frames = list(self.rebuffer.rebuffer(frames))

        # Segment using VAD
        segments = self.vad.segment(rebuffered_frames)
        events: list[TranscriptEvent] = []
        for index, segment in enumerate(segments):
            transcript, asr_confidence = self.asr.transcribe(segment)
            speaker_id, speaker_confidence = self.speaker_identifier.identify(segment)
            predicted_intent = self._predict_intent(transcript)
            audio_path = self._write_segment(session_id, index, segment)
            audio_record = AudioSegmentRecord(
                session_id=session_id,
                file_path=str(audio_path),
                start_time=utcnow(),
                end_time=utcnow(),
                duration_sec=len(segment) * (self.config.audio.vad.frame_duration_ms / 1000.0),
                raw_events_id=None,
            )
            audio_segment_id = self.database.insert_audio_segment(audio_record)
            event_payload = {
                "speaker_id": speaker_id,
                "speaker_confidence": speaker_confidence,
                "transcript": transcript,
                "asr_confidence": asr_confidence,
                "audio_segment_id": audio_segment_id,
            }
            raw_event_id = self.database.insert_raw_event(
                RawEventRecord(
                    session_id=session_id,
                    event_type="transcript",
                    timestamp=utcnow(),
                    payload=event_payload,
                    predicted_intent=predicted_intent,
                )
            )
            self.database.attach_audio_segment_to_event(audio_segment_id, raw_event_id)
            log_event(
                "transcript",
                {
                    "session_id": session_id,
                    "audio_path": audio_path,
                    "predicted_intent": predicted_intent,
                },
            )
            events.append(
                TranscriptEvent(
                    session_id=session_id,
                    transcript=transcript,
                    asr_confidence=asr_confidence,
                    speaker_id=speaker_id,
                    speaker_confidence=speaker_confidence,
                    predicted_intent=predicted_intent,
                    audio_segment_id=audio_segment_id,
                )
            )
        return events

    def _write_segment(self, session_id: int, index: int, segment: Sequence[AudioFrame]) -> Path:
        """Write audio segment to disk as WAV file (binary PCM 16-bit).

        Changed from CSV text format to WAV binary for 7x space savings.

        Args:
            session_id: Database session ID
            index: Segment index within session
            segment: Audio frames to write

        Returns:
            Path to written WAV file
        """
        file_name = f"session{session_id}_{index}_{sanitize_identifier(str(index))}.wav"
        path = self.segment_root / file_name

        # Concatenate all samples from frames
        all_samples = []
        for frame in segment:
            all_samples.extend(frame.samples)

        # Convert float32 [-1.0, 1.0] to PCM int16 [-32768, 32767]
        pcm_data = []
        for sample in all_samples:
            # Clamp to valid range
            clamped = max(-1.0, min(1.0, sample))
            pcm_value = int(clamped * 32767)
            pcm_data.append(pcm_value)

        # Pack as binary PCM 16-bit little-endian
        pcm_bytes = struct.pack(f'<{len(pcm_data)}h', *pcm_data)

        # Write as WAV file
        with wave.open(str(path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.config.audio.capture.sample_rate_hz)
            wav_file.writeframes(pcm_bytes)

        return path

    @staticmethod
    def _predict_intent(transcript: str) -> str:
        lowered = transcript.lower()
        if any(keyword in lowered for keyword in ("buy", "shopping")):
            return "shopping_candidate"
        if any(keyword in lowered for keyword in ("call", "todo")):
            return "todo_candidate"
        if lowered:
            return "memory_candidate"
        return "ignore"


__all__ = [
    "AudioFrame",
    "AudioPipeline",
    "FrameRebuffer",
    "TranscriptEvent",
    "VadDetector",
]

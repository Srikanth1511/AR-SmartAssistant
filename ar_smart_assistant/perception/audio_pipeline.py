"""Simplified audio pipeline for the AR-SmartAssistant reference app."""
from __future__ import annotations

from dataclasses import dataclass
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
    """PCM samples captured during ``frame_duration_ms``.

    The real implementation would store raw bytes. The proof-of-concept keeps the
    structure lightweight by using normalized floats for deterministic tests.
    """

    timestamp: float
    samples: Sequence[float]


@dataclass
class TranscriptEvent:
    session_id: int
    transcript: str
    asr_confidence: float
    speaker_id: str
    speaker_confidence: float
    predicted_intent: str
    audio_segment_id: int


class VadDetector:
    """Energy-based VAD that mirrors the YAML defaults."""

    def __init__(self, energy_threshold_db: float, min_speech_frames: int, padding_frames: int) -> None:
        self.energy_threshold_db = energy_threshold_db
        self.min_speech_frames = min_speech_frames
        self.padding_frames = padding_frames

    def segment(self, frames: Iterable[AudioFrame]) -> list[list[AudioFrame]]:
        active_segment: list[AudioFrame] = []
        result: list[list[AudioFrame]] = []
        silence_count = 0
        for frame in frames:
            energy = self._frame_energy(frame.samples)
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
    def _frame_energy(samples: Sequence[float]) -> float:
        if not samples:
            return -120
        return 20.0 * fmean(abs(sample) for sample in samples)


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
        self.asr = MockAsrModel()
        self.speaker_identifier = SpeakerIdentifier(config.audio.speaker_id.self_match_threshold * 100)
        self.segment_root = config.storage_root / "audio_segments"
        self.segment_root.mkdir(parents=True, exist_ok=True)

    def process_frames(self, session_id: int, frames: Iterable[AudioFrame]) -> list[TranscriptEvent]:
        segments = self.vad.segment(frames)
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
        file_name = f"session{session_id}_{index}_{sanitize_identifier(str(index))}.txt"
        path = self.segment_root / file_name
        with path.open("w", encoding="utf-8") as handle:
            for frame in segment:
                handle.write(",".join(f"{sample:.4f}" for sample in frame.samples) + "\n")
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


__all__ = ["AudioFrame", "AudioPipeline", "TranscriptEvent"]

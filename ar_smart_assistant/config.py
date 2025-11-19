"""Configuration loader for the AR-SmartAssistant reference implementation.

The YAML schema mirrors the Phase 1 audio-only proof of concept requirements
and intentionally keeps the structure close to the documentation to minimize
translation errors. Each helper exposes explicit `from_dict` constructors so
callers can validate external configuration before the rest of the system is
initialized.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - optional dependency
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback parser
    yaml = None


@dataclass(frozen=True)
class VadConfig:
    """Energy based VAD configuration.

    Failure Modes:
        - Missing threshold: `ValueError` is raised when the YAML omits
          `energy_threshold_db` because the runtime cannot derive a safe
          default.
        - Invalid durations: negative durations raise `ValueError`, preventing
          undefined segmentation latency downstream.
    """

    type: str
    energy_threshold_db: float
    frame_duration_ms: int
    min_speech_duration_ms: int
    padding_duration_ms: int

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VadConfig":
        required = {
            "type",
            "energy_threshold_db",
            "frame_duration_ms",
            "min_speech_duration_ms",
            "padding_duration_ms",
        }
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Missing VAD fields: {sorted(missing)}")
        frame_duration_ms = int(payload["frame_duration_ms"])
        min_speech_duration_ms = int(payload["min_speech_duration_ms"])
        padding_duration_ms = int(payload["padding_duration_ms"])
        for label, value in {
            "frame_duration_ms": frame_duration_ms,
            "min_speech_duration_ms": min_speech_duration_ms,
            "padding_duration_ms": padding_duration_ms,
        }.items():
            if value <= 0:
                raise ValueError(f"{label} must be positive")
        return cls(
            type=str(payload["type"]),
            energy_threshold_db=float(payload["energy_threshold_db"]),
            frame_duration_ms=frame_duration_ms,
            min_speech_duration_ms=min_speech_duration_ms,
            padding_duration_ms=padding_duration_ms,
        )


@dataclass(frozen=True)
class AsrConfig:
    """Subset of Faster-Whisper settings required for the POC."""

    model: str
    model_size: str
    device: str
    compute_type: str
    beam_size: int
    language: str
    confidence_threshold: float
    vad_filter: bool

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AsrConfig":
        beam_size = int(payload.get("beam_size", 5))
        if beam_size <= 0:
            raise ValueError("beam_size must be positive")
        confidence = float(payload.get("confidence_threshold", 0.7))
        if not 0 <= confidence <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        return cls(
            model=str(payload.get("model", "faster-whisper")),
            model_size=str(payload.get("model_size", "small.en")),
            device=str(payload.get("device", "cuda:0")),
            compute_type=str(payload.get("compute_type", "int8")),
            beam_size=beam_size,
            language=str(payload.get("language", "en")),
            confidence_threshold=confidence,
            vad_filter=bool(payload.get("vad_filter", True)),
        )


@dataclass(frozen=True)
class SpeakerIdConfig:
    """Speaker identification defaults for the prototype."""

    model: str
    embedding_dim: int
    similarity_metric: str
    self_match_threshold: float
    unknown_threshold: float
    required_phrases: int
    min_duration_per_phrase_sec: float
    max_embedding_std_dev: float

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SpeakerIdConfig":
        required_phrases = int(payload.get("required_phrases", 5))
        min_duration = float(payload.get("min_duration_per_phrase_sec", 6.0))
        max_std = float(payload.get("max_embedding_std_dev", 0.15))
        return cls(
            model=str(payload.get("model", "resemblyzer")),
            embedding_dim=int(payload.get("embedding_dim", 256)),
            similarity_metric=str(payload.get("similarity_metric", "cosine")),
            self_match_threshold=float(payload.get("self_match_threshold", 0.80)),
            unknown_threshold=float(payload.get("unknown_threshold", 0.65)),
            required_phrases=required_phrases,
            min_duration_per_phrase_sec=min_duration,
            max_embedding_std_dev=max_std,
        )


@dataclass(frozen=True)
class AudioCaptureConfig:
    sample_rate_hz: int
    encoding: str
    channel: str
    source: str
    buffer_size_bytes: int

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AudioCaptureConfig":
        sample_rate = int(payload.get("sample_rate_hz", 16_000))
        buffer_size = int(payload.get("buffer_size_bytes", 3_200))
        if sample_rate <= 0 or buffer_size <= 0:
            raise ValueError("sample_rate_hz and buffer_size_bytes must be positive")
        return cls(
            sample_rate_hz=sample_rate,
            encoding=str(payload.get("encoding", "PCM_16BIT")),
            channel=str(payload.get("channel", "MONO")),
            source=str(payload.get("source", "VOICE_RECOGNITION")),
            buffer_size_bytes=buffer_size,
        )


@dataclass(frozen=True)
class PreprocessingToggle:
    noise_suppressor: bool
    automatic_gain_control: bool
    acoustic_echo_canceler: bool

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PreprocessingToggle":
        pre = payload or {}
        return cls(
            noise_suppressor=bool(pre.get("noise_suppressor", {}).get("enabled", True)),
            automatic_gain_control=bool(pre.get("automatic_gain_control", {}).get("enabled", True)),
            acoustic_echo_canceler=bool(pre.get("acoustic_echo_canceler", {}).get("enabled", True)),
        )


@dataclass(frozen=True)
class AudioConfig:
    capture: AudioCaptureConfig
    preprocessing: PreprocessingToggle
    vad: VadConfig
    asr: AsrConfig
    speaker_id: SpeakerIdConfig

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AudioConfig":
        audio_payload = payload or {}
        return cls(
            capture=AudioCaptureConfig.from_dict(audio_payload.get("capture", {})),
            preprocessing=PreprocessingToggle.from_dict(audio_payload.get("preprocessing", {})),
            vad=VadConfig.from_dict(audio_payload.get("vad", {})),
            asr=AsrConfig.from_dict(audio_payload.get("asr", {})),
            speaker_id=SpeakerIdConfig.from_dict(audio_payload.get("speaker_id", {})),
        )


@dataclass(frozen=True)
class AppConfig:
    """Top-level immutable configuration."""

    audio: AudioConfig
    storage_root: Path
    session_replay_window_sec: int

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AppConfig":
        storage_root = Path(payload.get("storage_root", "./data"))
        session_replay_window_sec = int(payload.get("session_replay_window_sec", 300))
        if session_replay_window_sec <= 0:
            raise ValueError("session_replay_window_sec must be positive")
        return cls(
            audio=AudioConfig.from_dict(payload.get("audio", {})),
            storage_root=storage_root,
            session_replay_window_sec=session_replay_window_sec,
        )


DEFAULT_CONFIG = AppConfig.from_dict(
    {
        "storage_root": "./data",
        "session_replay_window_sec": 300,
        "audio": {
            "capture": {
                "sample_rate_hz": 16000,
                "encoding": "PCM_16BIT",
                "channel": "MONO",
                "source": "VOICE_RECOGNITION",
                "buffer_size_bytes": 3200,
            },
            "preprocessing": {
                "noise_suppressor": {"enabled": True},
                "automatic_gain_control": {"enabled": True},
                "acoustic_echo_canceler": {"enabled": True},
            },
            "vad": {
                "type": "energy_based",
                "energy_threshold_db": -45,
                "frame_duration_ms": 30,
                "min_speech_duration_ms": 300,
                "padding_duration_ms": 300,
            },
            "asr": {
                "model": "faster-whisper",
                "model_size": "small.en",
                "device": "cuda:0",
                "compute_type": "int8",
                "beam_size": 5,
                "language": "en",
                "confidence_threshold": 0.7,
                "vad_filter": True,
            },
            "speaker_id": {
                "model": "resemblyzer",
                "embedding_dim": 256,
                "similarity_metric": "cosine",
                "self_match_threshold": 0.80,
                "unknown_threshold": 0.65,
                "required_phrases": 5,
                "min_duration_per_phrase_sec": 6.0,
                "max_embedding_std_dev": 0.15,
            },
        },
    }
)


def load_config(path: Path | str) -> AppConfig:
    """Load configuration from disk.

    Args:
        path: Path to a YAML file. Missing files raise FileNotFoundError to
            avoid silently running with stale defaults.

    Returns:
        Parsed :class:`AppConfig` instance.

    Failure Modes:
        - File missing: propagates ``FileNotFoundError``.
        - YAML syntax error: re-raised ``yaml.YAMLError`` for explicit caller
          handling.
        - Schema mismatch: re-raised ``ValueError`` from the dataclass
          constructors.
    """

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        text = handle.read()
    if yaml is not None:
        payload = yaml.safe_load(text) or {}
    else:
        payload = _minimal_yaml_load(text)
    return AppConfig.from_dict(payload)


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    """Parse a very small subset of YAML for offline environments."""

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, _, value = raw_line.lstrip().partition(":")
        key = key.strip()
        value = value.strip()
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not value:
            new_dict: dict[str, Any] = {}
            parent[key] = new_dict
            stack.append((indent, new_dict))
        else:
            parent[key] = _parse_scalar(value)
    return root


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"')


__all__ = [
    "AppConfig",
    "AudioConfig",
    "AudioCaptureConfig",
    "AsrConfig",
    "PreprocessingToggle",
    "SpeakerIdConfig",
    "VadConfig",
    "DEFAULT_CONFIG",
    "load_config",
]

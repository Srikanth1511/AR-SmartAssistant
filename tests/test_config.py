from pathlib import Path

from ar_smart_assistant.config import DEFAULT_CONFIG, AppConfig, load_config


def test_default_config_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "audio:\n  vad:\n    type: energy_based\n    energy_threshold_db: -40\n    frame_duration_ms: 30\n    min_speech_duration_ms: 300\n    padding_duration_ms: 300\n",
        encoding="utf-8",
    )
    loaded = load_config(config_path)
    assert isinstance(loaded, AppConfig)
    assert loaded.audio.vad.energy_threshold_db == -40


def test_default_object_has_expected_audio_settings() -> None:
    assert DEFAULT_CONFIG.audio.capture.sample_rate_hz == 16_000
    assert DEFAULT_CONFIG.audio.asr.model == "faster-whisper"

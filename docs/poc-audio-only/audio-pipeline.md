# Audio Pipeline Specification

This file expands on Section 2 of the requirements and details the signal flow
from the Glass microphone to the PC, plus the baseline YAML configuration.

## 2.1 Signal Flow

```
Glass Mic
  ↓
[VOICE_RECOGNITION AudioSource]   ← Android speech-optimized capture
  ↓
[NoiseSuppressor]                 ← Background noise removal
  ↓
[AutomaticGainControl]            ← Volume normalization
  ↓
[AcousticEchoCanceler]            ← Echo/feedback removal
  ↓
16kHz PCM frames
  ↓
WebSocket → Phone → PC
  ↓
[Energy-based VAD]                ← Speech/silence segmentation
  ↓
[Audio Segment Recorder]          ← Save speech spans as WAV files
  ↓
[Faster-Whisper small.en]         ← ASR (speech segments only)
  ↓
[Resemblyzer embeddings]          ← Speaker embeddings
  ↓
Event bus → LLM orchestrator & DB (raw_events)
```

## 2.2 YAML Baseline

```yaml
audio:
  capture:
    sample_rate_hz: 16000
    encoding: "PCM_16BIT"
    channel: "MONO"
    source: "VOICE_RECOGNITION"
    buffer_size_bytes: 3200   # 200ms chunks at 16kHz

  preprocessing:
    noise_suppressor:
      enabled: true
    automatic_gain_control:
      enabled: true
    acoustic_echo_canceler:
      enabled: true

  vad:
    type: "energy_based"
    energy_threshold_db: -45
    frame_duration_ms: 30
    min_speech_duration_ms: 300
    padding_duration_ms: 300

  asr:
    model: "faster-whisper"
    model_size: "small.en"
    device: "cuda:0"
    compute_type: "int8"
    beam_size: 5
    language: "en"
    confidence_threshold: 0.7
    vad_filter: true

  speaker_id:
    model: "resemblyzer"
    embedding_dim: 256
    similarity_metric: "cosine"
    self_match_threshold: 0.80
    unknown_threshold: 0.65
    enrollment:
      required_phrases: 5
      min_duration_per_phrase_sec: 6.0
      max_embedding_std_dev: 0.15
```

Update this file if any part of the hardware path, preprocessing stack, or model
configuration changes. Also mirror changes into `requirements.md`.

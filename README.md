# AR-SmartAssistant
(WIP- not tested)
Audio-first remembrance agent inspired by the classic Remembrance Agent concept.
The current focus is a manual-session, audio-only proof of concept that runs all
inference locally (ASR, speaker ID, LLM, embeddings) and exposes a developer
debug UI for collecting, tagging, and approving memories.

## Quick Start

Get up and running in minutes:

```bash
# 1. Run automated setup
./setup.sh

# 2. Enroll your voice
./enroll_speaker.sh

# 3. Start the debug UI
./run_ui.sh
```

Open http://localhost:5000 in your browser and start recording sessions!

**📖 For detailed installation instructions, see [`INSTALL.md`](INSTALL.md)**

## Features

✅ **Local-First**: All processing runs on your machine (no cloud dependencies)
✅ **Audio Input**: PC microphone or Google Glass/phone streaming
✅ **Real-Time Transcription**: Faster-Whisper ASR with live display
✅ **Speaker Identification**: Know who said what
✅ **Memory Management**: Approve/reject individual memories
✅ **Debug UI**: Web-based interface for session control and review
✅ **Extensible**: Modular design for easy enhancement

## System Requirements

- **OS**: Linux, macOS, or Windows 10/11
- **Python**: 3.11+
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 10GB free space
- **Microphone**: Any USB or built-in microphone
- **GPU** (optional): NVIDIA GPU with 6GB+ VRAM for faster processing

## Getting Started

### For Users

1. **Install**: Follow the [installation guide](INSTALL.md)
2. **Enroll**: Create your voice profile with the enrollment tool
3. **Record**: Start a session and speak naturally
4. **Review**: Approve memories you want to keep

### For Developers

1. Read the engineering constraints in [`CONTRIBUTING.md`](CONTRIBUTING.md).
2. Skim the documentation index in [`docs/README.md`](docs/README.md).
3. Use the documentation workflow tips in
   [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) if you are extending the Markdown
   sources.
4. Dive into the audio-only POC requirements inside
   [`docs/poc-audio-only/`](docs/poc-audio-only/), starting with
   [`requirements.md`](docs/poc-audio-only/requirements.md).

## Background

Once the pipeline is in place, follow the requirements documentation to
implement manual audio sessions, persistent raw events, memory classification,
per-memory approvals, and versioned replays.

## Repository Layout (Reference Implementation)

```
ar_smart_assistant/
  config.py                ← YAML loader with strict validation
  database/                ← SQLite schema + repository helpers
  perception/audio_pipeline.py ← Energy-based VAD + mock ASR speaker heuristics
  llm/orchestrator.py      ← Deterministic classifier used for replay testing
  memory/approvals.py      ← Per-memory approval workflow + supervision hooks
  workflows/session_runner.py ← Coordinates the full pipeline in tests/CLI
tests/                      ← Pytest coverage for configuration, DB, and sessions
```

## Development Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

The prototype deliberately keeps inference lightweight—`perception.audio_pipeline`
implements the YAML-configured VAD and synthesizes transcripts so the rest of
the system (database, orchestration, approvals) can be exercised without a GPU.

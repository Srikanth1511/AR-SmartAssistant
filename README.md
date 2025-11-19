# AR-SmartAssistant

Audio-first remembrance agent inspired by the classic Remembrance Agent concept.
The current focus is a manual-session, audio-only proof of concept that runs all
inference locally (ASR, speaker ID, LLM, embeddings) and exposes a developer
debug UI for collecting, tagging, and approving memories.

## Getting Started

1. Review [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) to understand the repository
   layout and documentation rules.
2. Read the documentation index in [`docs/README.md`](docs/README.md).
3. Dive into the audio-only POC requirements inside
   [`docs/poc-audio-only/`](docs/poc-audio-only/), starting with
   [`requirements.md`](docs/poc-audio-only/requirements.md).

## Background

Set up the Glass-to-phone-to-PC pipeline using the reference implementation:
<https://github.com/Srikanth1511/GlassPhoneLink-AV-Server/tree/claude/feature-update-01HXtzZX1s1PfZyjaTSJFrVS>.
It provides a working audio/video link between the phone and the AR glasses.

Once the pipeline is in place, follow the requirements documentation to
implement manual audio sessions, persistent raw events, memory classification,
per-memory approvals, and versioned replays.

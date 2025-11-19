# Implementation Roadmap (Audio-Only POC)

Section 7 of the requirements outlines four delivery phases.

## Phase 0 – Infrastructure

- Initialize `brain_main.db` and `system_metrics.db` schemas.
- Seed `model_versions` and `config_change_log`.
- Build speaker enrollment script.
- Stand up a minimal Flask debug UI (buttons only).

## Phase 1 – Audio Worker & Events

- Implement the audio pipeline: VAD → WAV segments → Faster-Whisper →
  Resemblyzer.
- Persist `audio_segments` and `raw_events` with early `predicted_intent` tags.
- Implement baseline LLM classification (simple heuristics + JSON output).
- Start logging basic system metrics.

## Phase 2 – Approval & Tagging

- Finish per-memory approve/reject flow and UI review table.
- Add session finalization logic and embedding push to the vector store.
- Wire classifier tags + color mapping into the live transcript UI.

## Phase 3 – Replay & Versioning

- Implement `replay_session(session_id, new_model_version_id)` to re-run stored
  events with a new config and inspect differences.
- Use `model_versions` and `config_change_log` data during replay comparisons.

## Phase 4 – Supervised Learning Harness

- Persist low-confidence ASR segments, user rejections, and LLM JSON failures
  (including prompt+event payloads).
- Provide export scripts that package these artifacts for retraining.

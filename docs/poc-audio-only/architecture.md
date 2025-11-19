# Architecture Constraints & Clarifications

This file mirrors Section 1 of the full requirements and should be updated in
lockstep with `requirements.md`.

## 1.1 Critical Scope Reductions

**Out of scope for Phase 1**

- 24/7 continuous operation (sessions are manual only).
- Vision, YOLO, face recognition, or any frame processing.
- Vision-language models — the POC is text-only.
- Cloud inference — ASR, speaker ID, LLM, and embeddings must run locally.

**In scope for Phase 1**

- Manual audio sessions (2–8 minutes typical) controlled from the debug UI.
- Per-memory approval flow with granular accept/reject.
- Ability to replay sessions with new models/configs.
- Hooks for supervised learning (capture failures, rejections, artifacts).
- Color-coded, class-tagged transcripts so it is clear how each line is treated.

## 1.2 Session Model

- Mode: **manual** start/stop via UI button or API.
- Duration: **user controlled**, typically a few minutes.
- Frequency: **ad-hoc** when the user wants to capture memories.
- States:
  - Device can stream audio while idle (no persistence).
  - Only between `session_start` and `session_stop` do we persist events, run
    classification, and propose memories.

## 1.3 Approval Granularity

- Sessions are *not* all-or-nothing.
- Each session yields multiple `memory_items` that can be individually approved
  or rejected.
- Session-level statuses: `active`, `pending_review`, `partially_approved`,
  `fully_approved`, `rejected`.

## 1.4 Event-Level Persistence & Replay

- Raw events are immutable ground truth; LLM output is just one interpretation.
- Forward pass:
  1. Persist raw events + locations.
  2. LLM proposes memories.
  3. User approves/rejects per memory; only approved items get embedded.
- Replay:
  1. Load stored raw events.
  2. Re-run LLM with new prompt/config.
  3. Compare old vs. new memories and evaluate improvements.
- Requirements:
  - Store raw events in `raw_events`.
  - Store WAV spans in `audio_segments`.
  - Memory items reference their source event (and session).
  - Track model/config versions via `model_versions` + `config_change_log`.

## 1.5 LLM Input Format (Text Only)

- The LLM receives structured event JSON (timestamp, speaker, transcript, ASR
  confidence, location, context window, event class hint).
- No raw audio is ever passed to the LLM.
- Future Phase 2 vision context would add `visual_context` with objects/faces.

## 1.6 Supervised Learning Scope

Log the following for retraining/debugging:

- ASR issues (low confidence, WER spikes).
- Speaker ID issues (low confidence, ambiguous matches).
- LLM issues (JSON errors, misclassifications).
- System issues (transaction failures).
- User feedback (rejection reasons).

Whenever possible, capture related audio segment paths so the data can feed ASR,
speaker, and LLM improvements later.

# LLM Orchestrator, Classification & Tagging

This document mirrors Section 5 of the requirements and should be kept in sync
with `requirements.md`.

## 5.1 Event Classification with Self-Assessment

- **Input**: structured event JSON (timestamp, speaker, transcript, ASR
  confidence, location, context window, event class hint).
- **Output**: valid JSON only, shaped as:
  - `actions`: list of objects where each action includes:
    - `type`: `add_memory`, `add_shopping_item`, `none`, etc.
    - `text`: human-readable memory (for memory actions).
    - `tags`: topic tags array.
    - `importance`: float.
    - `predicted_intent`: string label.
    - `quality_assessment`:
      - `confidence`
      - `issues`: list of issue strings.
      - `suggestion`: remediation note.
- **Orchestrator duties**:
  - Parse JSON and handle errors.
  - Annotate each action with `llm_confidence` + `llm_suggested_issue`.
  - Persist `predicted_intent` and `llm_suggested_issue` into `memory_items`.

## 5.2 Live Event-Level Tags

- When the transcript is produced (pre-memory), assign an early intent tag:
  `ignore`, `small_talk`, `memory_candidate`, `shopping_candidate`,
  `todo_candidate`, etc.
- Store this tag in `raw_events.predicted_intent`.
- Map tag → color in the debug UI (e.g., memory=blue, shopping=yellow, todo=orange,
  ignore=gray, small talk=light green).
- Purpose: quickly see speaker detection quality and classification intuition.
- Final `memory_items` also include `predicted_intent`, but the mapping need not
  be 1:1 with the early tags.

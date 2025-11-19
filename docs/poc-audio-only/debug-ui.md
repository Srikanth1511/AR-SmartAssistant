# Debug UI Requirements (Flask + Plain JS)

Section 6 of the requirements specifies a developer-facing UI for controlling
sessions, reviewing memories, and running sanity checks.

## 6.1 Session Control

- Buttons: **Start Session**, **Stop Session**.
- Display the current state (`Idle`, `Recording (Session N)`, etc.) and the last
  session ID.

## 6.2 Live Metrics

- Query `system_metrics.db` once per second.
- Show rolling 60-second averages for ASR confidence and speaker confidence.
- Display queue depth and LLM latency (ms).

## 6.3 Live Transcript Stream

- Stream transcripts in real time with timestamp, speaker, transcript text, and
  early `predicted_intent`.
- Color each line based solely on `predicted_intent` with a configurable JS map
  (e.g., memory=blue, shopping=yellow, todo=orange, ignore=gray, small talk=light
  green).

## 6.4 Memory Review

- For the selected session, list every `memory_item` with timestamp, text, topic
  tags, predicted intent, importance, ASR/speaker/LLM confidence, and any
  `llm_suggested_issue`.
- Buttons:
  - **Approve** → set `approval_status = approved`.
  - **Reject** → collect reason, set `approval_status = rejected`, log event in
    `supervised_learning_events`.

## 6.5 Session Finalization

- Button: **Finalize Session** with optional “re-run LLM using current config”.
- After finalization:
  - Embed approved memories and push to the vector store (e.g., Chroma).
  - Update `sessions.status` and `approval_timestamp`.

## 6.6 Test Panel

- Button: **Run Verification Tests** covering:
  - Retrieval quality: each approved memory should retrieve itself from Chroma.
  - Speaker consistency: confirm a short “self” clip still matches the wearer
    profile.
  - LLM sanity: replay subset to ensure JSON output is valid.

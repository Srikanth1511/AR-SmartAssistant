# AR-SmartAssistant POC Requirements

This document consolidates the full requirements for the manual-session,
audio-only remembrance agent proof of concept. Each major section is also
available as its own markdown file for quick reference.

## 1. Architecture Constraints & Clarifications

### 1.1 Critical Scope Reductions

**What This Is NOT (Phase 1):**

- **Not 24/7 continuous operation**
  - Recording only happens in explicitly started sessions
- **Not vision-enabled**
  - No YOLO, no face recognition, no frame processing in POC
- **Not VLM-based**
  - Text-only LLM; vision-language comes in a later phase
- **Not cloud-dependent**
  - All inference is local (ASR, speaker ID, LLM, embeddings)

**What This IS:**

- Audio-only memory capture during **manual sessions** (typical 2–8 minutes)
- **Manual session control** via debug UI (Start / Stop / Review / Finalize)
- **Per-memory approval** (approve/reject individual memories)
- **Model replay**: run newer LLM/config on archived raw events
- **Supervised learning hooks**:
  - capture failures and user rejections cleanly
- **Color-coded, class-tagged transcripts** in the debug UI:
  - show primary speaker detection
  - show what class/tag the system is assigning (“memory”, “shopping”, “todo”, “ignore”)

### 1.2 Session Model

- Mode: **Manual**
  - Start/stop via debug UI button or API
- Duration: **User-controlled**, typical 2–8 minutes
- Frequency: **Ad-hoc**, when Glass is worn and user wants to capture
- State model:
  - Device can be worn & streaming but **not recording** (idle)
  - Only between `session_start` and `session_stop` do we:
    - persist events
    - run classification
    - propose memories

### 1.3 Approval Granularity

- **Not** all-or-nothing per session
- The LLM proposes **multiple memory_items** per session
- User can:
  - Approve a memory (goes into long-term vector store)
  - Reject a memory (goes into supervised training log)
  - Keep session partially approved
- Session-level status:
  - `active`
  - `pending_review`
  - `partially_approved`
  - `fully_approved`
  - `rejected` (if user discards everything)

### 1.4 Event-Level Persistence & Replay

Core idea: **raw events** are ground truth; LLM output is just one interpretation.

**Forward pass:**

```
Session N (Model v1.2, Config A)
  → Raw events serialized to DB (transcripts, locations)
  → LLM produces proposed memories (M1, M2, M3)
  → User approves M1, M3 — rejects M2
  → Only approved memories get embedded & used for retrieval
```

**Replay:**

```
Replay Session N with Model v1.3, Config B
  → Load same raw events
  → Re-run LLM classification with new prompt/config
  → Compare old memories vs new memories
  → User evaluates if new behavior is better
```

Requirements:

- **Raw events** stored in `raw_events` table
- **Audio segments** stored in a separate `audio_segments` table
- Memory items reference their **source event** (and thus session)
- Model and config versions recorded in `model_versions` and `config_change_log`

### 1.5 LLM Input Format (Text-Only)

LLM **never** sees raw audio. It sees structured events:

```json
{
  "timestamp": "2025-01-15T14:23:45Z",
  "speaker_id": "self",
  "speaker_confidence": 0.89,
  "transcript": "we're running out of sugar",
  "asr_confidence": 0.92,
  "location": "home_kitchen",
  "context_window": [
    "previous 30 seconds of transcript..."
  ],
  "event_class_hint": "shopping_candidate"
}
```

Future vision extension (Phase 2) will add:

```json
"visual_context": {
  "objects": [{"label": "sugar_jar", "state": "low", "confidence": 0.91}],
  "faces": []
}
```

### 1.6 Supervised Learning Scope

The system must log, in a structured way:

- **ASR issues**
  - low ASR confidence (< 0.7)
  - high WER segments (later, if available)
- **Speaker ID issues**
  - low speaker match confidence (< 0.8)
  - ambiguous matches
- **LLM issues**
  - JSON parse errors
  - classification errors
- **System issues**
  - memory write transaction failures
- **User feedback**
  - user-rejected memories + rejection reasons

And where feasible:

- File paths for corresponding **audio segments**
- All of the above are candidates for **ASR/speaker/LLM retraining** later

## 2. Audio Pipeline Specification (From Glass-Phone-Link)

### 2.1 Signal Flow

```
Glass Mic
  ↓
[VOICE_RECOGNITION AudioSource]   ← Android optimizations for speech
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
[Audio Segment Recorder]          ← Save each speech span as WAV (audio_segments table)
  ↓
[Faster-Whisper small.en]         ← ASR (only on speech segments)
  ↓
[Resemblyzer embeddings]          ← Speaker embedding
  ↓
Event bus → LLM orchestrator & DB (raw_events)
```

### 2.2 Audio Configuration (YAML baseline)

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

## 3. Database Design

Two physical DB files, for sanity and separation:

- **`brain_main.db`**
  - sessions
  - raw_events
  - audio_segments
  - model_versions
  - config_change_log
  - speaker_profiles
  - persons
  - locations
  - conversations
  - memory_items
  - shopping_items
  - supervised_learning_events
- **`system_metrics.db`**
  - system_metrics (time-series metrics for monitoring)

### 3.1 Core Design Principle

- **Raw events** (and audio segments) are immutable ground truth.
- **Memory items** are one interpretation (LLM vX, config Y).
- **Model versions** and **config logs** let you replay and compare behavior.

### 3.2 Schema Overview (Logical, not full SQL)

#### 3.2.1 model_versions

Tracks which models + prompts produced a given session’s memories.

Fields:

- `id`
- `version_tag` (e.g., `"v1.2.0"`)
- `llm_model` (e.g., `"llama3.1:8b"`)
- `asr_model` (e.g., `"faster-whisper-small.en"`)
- `speaker_model` (e.g., `"resemblyzer"` or `"titanet_s"`)
- `prompt_hash` (hash of classification prompt)
- `config_snapshot` (JSON dump of config)
- `created_at`

> Version bump rule:
> Any change in LLM weights, ASR model/thresholds, speaker model/thresholds,
> **or main classification prompt** → new model_versions row.

#### 3.2.2 config_change_log

Tracks config/prompts changes over time (for debugging “why did behavior change?”).

Fields:

- `id`
- `timestamp`
- `changed_by` (string: `"manual"`, `"cli"`, etc.)
- `old_config_hash`
- `new_config_hash`
- `change_summary` (short text)

#### 3.2.3 sessions

Fields:

- `id`
- `model_version_id` (FK → model_versions)
- `start_time`
- `end_time`
- `status` (`active`, `pending_review`, `partially_approved`, `fully_approved`, `rejected`)
- `approval_timestamp`
- `notes`
- `created_at`

#### 3.2.4 raw_events

Stores structured events (audio transcripts, location, etc.)

Fields:

- `id`
- `session_id` (FK → sessions)
- `event_type` (`transcript`, `location`)
- `timestamp`
- `payload` (JSON blob, includes transcript, ASR confidence, speaker info, location, `audio_segment_id`, etc.)
- `predicted_intent` (string; optional early classifier: `"memory_candidate"`, `"shopping_candidate"`, `"todo_candidate"`, `"ignore"`)
- `created_at`

Indexes:

- `session_id`
- `timestamp`

Example payload (for a transcript):

```json
{
  "speaker_id": "self",
  "speaker_confidence": 0.89,
  "transcript": "we're running out of sugar",
  "asr_confidence": 0.92,
  "location": "home_kitchen",
  "audio_segment_id": 42
}
```

#### 3.2.5 audio_segments

Separate table for retraining / supervised learning.

Fields:

- `id`
- `session_id` (FK → sessions)
- `file_path` (path to WAV)
- `start_time`
- `end_time`
- `duration_sec`
- `created_at`

Optional:

- `raw_events_id` (FK → raw_events; may be null if a segment never produced a transcript)

#### 3.2.6 speaker_profiles

Pure voice-based enrollment.

Fields:

- `id`
- `name` (e.g., `"Self"`, `"Alice"`)
- `embedding` (BLOB)
- `enrollment_quality`
- `sample_count`
- `enrollment_date`
- `last_matched`
- `created_at`

#### 3.2.7 persons

More general **person concept** so we don’t refactor later.

Fields:

- `id`
- `display_name`
- `primary_speaker_profile_id` (FK → speaker_profiles)
- `primary_face_profile_id` (NULL for now; future FK when vision added)
- `voice_embedding` (BLOB)
- `face_embeddings` (JSON array – prep for vision)
- `relationship_tags` (JSON array: `self`, `friend`, `family`, `colleague`, `service_staff`, `unknown`)
- `first_seen_at`
- `last_seen_at`
- `notes` (text)
- `notes_vector_ids` (JSON array linking to memory vectors)
- `created_at`

For audio-only POC:

- At least one `Person` with `relationship_tags=["self"]` and a linked `speaker_profile`.

#### 3.2.8 locations

Fields:

- `id`
- `label` (e.g., `"home_kitchen"`)
- `lat`, `lon`, `radius_m`
- `type` (`home`, `work`, `shop`, `outdoors`, `unknown`)

Insert default `"unknown"` location.

#### 3.2.9 conversations

Structured conversation roll-ups for transcripts + summaries.

Fields:

- `id`
- `participants` (JSON array of `persons.id`)
- `start_time`
- `end_time`
- `location_id` (FK → locations)
- `topics` (JSON array of tags)
- `raw_transcript`
- `summary_text`
- `summary_vector` (embedding)
- `importance` (0–1)
- `privacy` (`private`, `sensitive`, `shareable`)
- `created_at`

#### 3.2.10 memory_items

LLM-proposed memories.

Fields:

- `id`
- `session_id` (FK → sessions)
- `source_event_id` (FK → raw_events)
- `source_conversation_id` (FK → conversations)
- `timestamp`
- `person_id` (FK → persons; who this memory is mainly about; often `self`)
- `speaker_id` (FK → persons; explicit talker)
- `speaker_profile_id` (FK → speaker_profiles; optional)
- `location_id` (FK → locations)
- `text` (human-readable memory)
- `topic_tags` (JSON array of domains)
- `task_tags` (JSON array – shopping, todo, reminder, etc.)
- `domain_tags` (JSON array – work, family, sports, glass_ar, etc.)
- `modality_tags` (JSON array: `from_audio`, `from_video`, `from_location`, `from_manual_input`)
- `importance` (0–1)
- `urgency` (`low`, `medium`, `high`)
- `deadline` (timestamp)
- `repetition_count` (int)
- `last_accessed_at`
- `emotion`
- `vector` (embedding)
- `predicted_intent` (string: `"general_memory"`, `"shopping_item"`, `"todo"`, `"contact_info"`, etc.)
- `privacy_level` (`private`, `sensitive`, `public`)
- `shareable_to` (JSON array of entities)
- `approval_status` (`pending`, `approved`, `rejected`, `flagged`)
- `rejection_reason` (string)
- `llm_suggested_issue` (string, from LLM quality self-assessment)
- `confidence_asr`
- `confidence_speaker`
- `confidence_vision`
- `confidence_face`
- `confidence_llm`
- `created_at`
- `reviewed_at`

#### 3.2.11 shopping_items

Items the system thinks should go on a shopping list.

Fields:

- `id`
- `session_id` (FK → sessions)
- `source_memory_id` (FK → memory_items)
- `related_memory_id` (optional FK)
- `name`
- `quantity` (text)
- `status` (`pending`, `bought`, `dismissed`)
- `source` (`vision_low_level`, `user_spoken`, `manual`, `system`)
- `created_at`
- `last_updated_at`

#### 3.2.12 supervised_learning_events

Stores everything we may want to use later to improve models.

Fields:

- `id`
- `session_id` (FK → sessions)
- `category` (e.g., `"low_asr_confidence"`, `"user_rejected_memory"`, `"llm_json_error"`)
- `timestamp`
- `artifact_path` (e.g., path to audio or JSON dump)
- `metadata` (JSON)
- `reviewed` (boolean)

#### 3.2.13 system_metrics (in `system_metrics.db`)

Time-series metrics for monitoring.

Fields:

- `id`
- `session_id` (nullable, FK to sessions in `brain_main.db` via ID only)
- `timestamp`
- `metric_name` (e.g., `"asr_confidence"`, `"speaker_confidence"`, `"queue_depth"`, `"llm_latency_ms"`)
- `metric_value`
- `metadata` (JSON)

### 3.3 Tag & Metric Library

For clarity, the tags/metrics tied to the schema are:

- **Modality tags**: `from_audio`, `from_video`, `from_location`, `from_manual_input`
- **Task type tags**: `shopping`, `todo`, `reminder`, `contact_info`, `project_idea`, `research_topic`, `health`, `finance`, `travel`, `cooking`, `maintenance`
- **Topic/domain tags**: `people`, `work`, `school`, `family`, `friends`, `sports`, `cs_ml`, `aerospace`, `startup`, `hardware`, `glass_ar`
- **Relationship tags**: `self`, `spouse`, `family`, `close_friend`, `acquaintance`, `colleague`, `client`, `service_provider`, `stranger`
- **Importance & urgency metrics**: importance (0–1), urgency (`low`, `medium`, `high`), `deadline`, `repetition_count`, `last_accessed_at`
- **Confidence metrics**: `asr_confidence`, `vision_confidence`, `speaker_match_confidence`, `face_match_confidence`, `llm_decision_confidence`
- **Privacy & visibility**: `privacy_level`, `shareable_to`
## 4. Versioning & Config Logging

- **model_versions**
  - Each row = stable set of:
    - LLM model
    - ASR model + thresholds
    - Speaker model + thresholds
    - Classification prompt (hash)
    - Full config snapshot
- **config_change_log**
  - Any change to relevant config must insert a row with:
    - old_config_hash
    - new_config_hash
    - summary

Behavior:

- At session start:
  - System determines active `model_version_id`
  - Writes that into `sessions.model_version_id`
- For replays:
  - You can compare:
    - `old_model_version` vs `new_model_version`
    - Observed differences in `memory_items`

No hidden “silent config drift”: everything gets logged.

## 5. LLM Orchestrator, Classification & Tagging

### 5.1 Event Classification with Self-Assessment

Requirements for classification:

- Input: event JSON (as described before)
- Output: **valid JSON only**, containing:
  - `actions` (list)
  - Each action includes:
    - `type` (`add_memory`, `add_shopping_item`, `none`, etc.)
    - `text` (for memory actions)
    - `tags` (topic tags)
    - `importance`
    - `predicted_intent` (string)
    - `quality_assessment`:
      - `confidence`
      - `issues` (list of strings)
      - `suggestion`

- Orchestrator must:
  - Parse the JSON
  - Annotate each action with:
    - `llm_confidence`
    - `llm_suggested_issue`
  - Persist:
    - `predicted_intent` → `memory_items.predicted_intent`
    - `llm_suggested_issue` → `memory_items.llm_suggested_issue`

### 5.2 Live Event-Level Tags (for Debug UI & DB)

When a transcript is first produced (before final memory approval):

- System assigns **an early intent tag** for the event, like:
  - `"ignore"`
  - `"small_talk"`
  - `"memory_candidate"`
  - `"shopping_candidate"`
  - `"todo_candidate"`
- This tag:
  - Gets stored in `raw_events.predicted_intent`
  - Drives **color in UI**:
    - Example mapping:
      - `"memory_candidate"` → blue
      - `"shopping_candidate"` → yellow
      - `"todo_candidate"` → orange
      - `"ignore"` → grey
      - `"small_talk"` → light green
  - Makes it obvious what the model currently thinks each line is

Later, when the LLM consolidates events into `memory_items`, each memory has its
own `predicted_intent` (often mapping from those early event-level tags, but not
required to be 1:1).

## 6. Debug UI Requirements (Flask + Plain JS)

UI is for **you**, not for end users. Requirements:

### 6.1 Session Control

- Buttons:
  - **Start Session**
  - **Stop Session**
- Display:
  - Current status: `Idle`, `Recording (Session N)`, etc.
  - Last session ID

### 6.2 Live Metrics

Pull from `system_metrics.db` every second:

- Show:
  - Avg ASR confidence (last 60s)
  - Avg speaker confidence (last 60s)
  - Queue depth
  - LLM latency (ms)

### 6.3 Live Transcript Stream (Color-Coded)

- Pane that shows recent transcript lines in real time
- Each line shows:
  - Timestamp
  - Speaker (e.g., `self` or `unknown`)
  - Transcript text
  - Early `predicted_intent` (e.g., `"shopping_candidate"`)
- Color mapping:
  - Driven entirely by `predicted_intent`
  - Configurable mapping in a simple JS object in the template

Purpose:

- You can instantly see if:
  - It’s consistently tagging *you* as the primary speaker
  - It’s classifying “we're running out of sugar” as a shopping candidate, etc.

### 6.4 Memory Review

For a given session:

- List all `memory_items` for that session:
  - Timestamp
  - Text
  - Topic tags
  - Predicted intent
  - Importance
  - ASR/speaker/LLM confidence
  - LLM-suggested issues (if any)
- Buttons:
  - **Approve** → sets `approval_status = approved`
  - **Reject** → prompts for reason, sets `approval_status = rejected`, logs event in `supervised_learning_events`

### 6.5 Session Finalization

- Button: **Finalize Session**
  - Optional flag: re-run LLM on approved events with current config
  - After finalization:
    - Compute embeddings for approved memories
    - Add them to Chroma (or chosen vector store)
    - Update `sessions.status` and `approval_timestamp`

### 6.6 Test Panel

- Button: **Run Verification Tests**
  - Minimum tests:
    - Retrieval quality:
      - Query Chroma with each approved memory → verify it returns itself as top result
    - Speaker consistency:
      - Check if a short “self” sample still matches the enrolled `self` profile
    - LLM accuracy sanity:
      - Small replay subset: confirm JSON validity & basic behavior

## 7. Implementation Roadmap (Audio-Only POC)

### Phase 0: Infrastructure

- Set up:
  - `brain_main.db` (schema)
  - `system_metrics.db` (metrics schema)
  - `model_versions` and `config_change_log`
- Implement speaker enrollment script
- Get Flask debug UI skeleton running (no real backend logic yet)

### Phase 1: Audio Worker + Events

- Implement audio pipeline (VAD → WAV segments → Whisper → Resemblyzer)
- Persist:
  - `audio_segments`
  - `raw_events` with event-level `predicted_intent`
- Implement baseline LLM classification (simple hard triggers + JSON output)
- Basic metrics logging

### Phase 2: Approval & Tagging

- Implement:
  - Per-memory approve/reject flow
  - UI for memory review
  - Session finalization logic
  - Chroma embedding of approved memories
- Wire classifier tags + color mapping into live transcript UI

### Phase 3: Replay & Versioning

- Implement `replay_session(session_id, new_model_version_id)`:
  - Load raw events
  - Re-run LLM with new config
  - (Optionally) create new `memory_items` version or produce diff reports
- Use `model_versions` & `config_change_log` properly

### Phase 4: Supervised Learning Harness

- Save:
  - Low-confidence ASR segments
  - User-rejected memories
  - LLM JSON failures (with prompt + event)
- Simple scripts to export these as training datasets

---

This merged spec keeps the **audio-only, session-based RA POC** tight, while:

- Adding the **audio_segments table** cleanly
- Introducing a future-proof **person** concept (without refactors later)
- Splitting **brain_main.db** and **system_metrics.db**
- Making **versioning and config changes explicit and logged**
- Adding **intent tags + color-coded debug display** so you can see live what the
  model thinks each line is and how it’ll be stored.

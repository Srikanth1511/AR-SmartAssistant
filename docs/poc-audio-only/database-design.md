# Database Design

This document tracks Section 3 of the requirements and defines how data is split
between `brain_main.db` and `system_metrics.db`.

## 3.0 Physical Layout

- `brain_main.db`
  - sessions, raw_events, audio_segments, model_versions, config_change_log,
    speaker_profiles, persons, locations, conversations, memory_items,
    shopping_items, supervised_learning_events.
- `system_metrics.db`
  - system_metrics (time-series metrics for monitoring).

## 3.1 Core Principles

- Raw events and audio segments are immutable ground truth.
- Memory items are interpretations tied to a model/config version.
- Versioning tables enable replay to compare behavior across configs.

## 3.2 Logical Schemas

### model_versions

| Field | Notes |
| --- | --- |
| `id` | Primary key |
| `version_tag` | e.g., `v1.2.0` |
| `llm_model` | `llama3.1:8b`, etc. |
| `asr_model` | `faster-whisper-small.en` |
| `speaker_model` | `resemblyzer`, `titanet_s`, etc. |
| `prompt_hash` | Hash of classification prompt |
| `config_snapshot` | JSON dump of config |
| `created_at` | Timestamp |

> Version bump any time LLM weights, ASR thresholds, speaker thresholds, or the
> main classification prompt changes.

### config_change_log

Tracks why behavior changed.

| Field | Notes |
| --- | --- |
| `id` | PK |
| `timestamp` | When change was made |
| `changed_by` | `manual`, `cli`, etc. |
| `old_config_hash` | Hash before change |
| `new_config_hash` | Hash after change |
| `change_summary` | Short description |

### sessions

| Field | Notes |
| --- | --- |
| `id` | PK |
| `model_version_id` | FK to `model_versions` |
| `start_time`, `end_time` | Session bounds |
| `status` | `active`, `pending_review`, `partially_approved`, `fully_approved`, `rejected` |
| `approval_timestamp` | When final approval happened |
| `notes` | Optional |
| `created_at` | Insert timestamp |

### raw_events

| Field | Notes |
| --- | --- |
| `id` | PK |
| `session_id` | FK to `sessions` |
| `event_type` | `transcript`, `location` |
| `timestamp` | Event time |
| `payload` | JSON blob (transcript, ASR confidence, speaker info, location, `audio_segment_id`, etc.) |
| `predicted_intent` | Early classifier tag (`memory_candidate`, `shopping_candidate`, `todo_candidate`, `ignore`) |
| `created_at` | Insert timestamp |

Indexes: `session_id`, `timestamp`.

### audio_segments

| Field | Notes |
| --- | --- |
| `id` | PK |
| `session_id` | FK to `sessions` |
| `file_path` | Path to WAV |
| `start_time`, `end_time`, `duration_sec` | Segment timing |
| `created_at` | Insert timestamp |
| `raw_events_id` | Optional FK if transcript exists |

### speaker_profiles

| Field | Notes |
| --- | --- |
| `id` | PK |
| `name` | e.g., `Self`, `Alice` |
| `embedding` | BLOB |
| `enrollment_quality` | Score |
| `sample_count` | Enrollment utterances |
| `enrollment_date`, `last_matched` | Timestamps |
| `created_at` | Insert timestamp |

### persons

| Field | Notes |
| --- | --- |
| `id` | PK |
| `display_name` | Friendly name |
| `primary_speaker_profile_id` | FK to `speaker_profiles` |
| `primary_face_profile_id` | Placeholder FK for future vision |
| `voice_embedding` | BLOB for canonical voice |
| `face_embeddings` | JSON array of embeddings (vision-ready) |
| `relationship_tags` | JSON array (`self`, `friend`, `family`, `colleague`, `service_staff`, `unknown`) |
| `first_seen_at`, `last_seen_at` | Tracking |
| `notes` | Text |
| `notes_vector_ids` | JSON array linking to memory vectors |
| `created_at` | Insert timestamp |

At least one `Person` should represent the wearer with `relationship_tags=["self"]`.

### locations

| Field | Notes |
| --- | --- |
| `id` | PK |
| `label` | e.g., `home_kitchen` |
| `lat`, `lon`, `radius_m` | Optional geo data |
| `type` | `home`, `work`, `shop`, `outdoors`, `unknown` |

Seed with a default `unknown` row.

### conversations

| Field | Notes |
| --- | --- |
| `id` | PK |
| `participants` | JSON array of `persons.id` |
| `start_time`, `end_time` | Conversation bounds |
| `location_id` | FK to `locations` |
| `topics` | JSON array of tags |
| `raw_transcript` | Full transcript |
| `summary_text` | LLM summary |
| `summary_vector` | Embedding |
| `importance` | Float 0–1 |
| `privacy` | `private`, `sensitive`, `shareable` |
| `created_at` | Insert timestamp |

### memory_items

| Field | Notes |
| --- | --- |
| `id` | PK |
| `session_id` | FK to `sessions` |
| `source_event_id` | FK to `raw_events` |
| `source_conversation_id` | FK to `conversations` |
| `timestamp` | When the memory occurred |
| `person_id` | FK to `persons` |
| `speaker_id` | FK to `persons` (explicit speaker) |
| `speaker_profile_id` | Optional FK |
| `location_id` | FK to `locations` |
| `text` | Human-readable memory |
| `topic_tags` | JSON array (domain tags) |
| `task_tags` | JSON array (`shopping`, `todo`, `reminder`, etc.) |
| `domain_tags` | JSON array (e.g., `work`, `family`, `glass_ar`) |
| `modality_tags` | JSON array (`from_audio`, `from_video`, etc.) |
| `importance` | Float 0–1 |
| `urgency` | `low`, `medium`, `high` |
| `deadline` | Optional timestamp |
| `repetition_count` | Integer |
| `last_accessed_at` | Timestamp |
| `emotion` | Text label |
| `vector` | Embedding |
| `predicted_intent` | `general_memory`, `shopping_item`, `todo`, etc. |
| `privacy_level` | `private`, `sensitive`, `public` |
| `shareable_to` | JSON array of entities |
| `approval_status` | `pending`, `approved`, `rejected`, `flagged` |
| `rejection_reason` | Text |
| `llm_suggested_issue` | Text |
| `confidence_asr`, `confidence_speaker`, `confidence_vision`, `confidence_face`, `confidence_llm` | Floats |
| `created_at`, `reviewed_at` | Timestamps |

### shopping_items

| Field | Notes |
| --- | --- |
| `id` | PK |
| `session_id` | FK to `sessions` |
| `source_memory_id` | FK to `memory_items` (what triggered the list item) |
| `related_memory_id` | Optional FK for additional context |
| `name` | Item name |
| `quantity` | Free text |
| `status` | `pending`, `bought`, `dismissed` |
| `source` | `vision_low_level`, `user_spoken`, `manual`, `system` |
| `created_at` | Timestamp |
| `last_updated_at` | Timestamp |

### supervised_learning_events

| Field | Notes |
| --- | --- |
| `id` | PK |
| `session_id` | FK to `sessions` |
| `category` | `low_asr_confidence`, `user_rejected_memory`, `llm_json_error`, etc. |
| `timestamp` | When it happened |
| `artifact_path` | Audio or JSON reference |
| `metadata` | JSON blob |
| `reviewed` | Boolean |

### system_metrics (`system_metrics.db`)

| Field | Notes |
| --- | --- |
| `id` | PK |
| `session_id` | Optional FK reference (cross-db by ID) |
| `timestamp` | Metric timestamp |
| `metric_name` | e.g., `asr_confidence`, `speaker_confidence`, `queue_depth`, `llm_latency_ms` |
| `metric_value` | Float |
| `metadata` | JSON |

Update `requirements.md` whenever these schemas evolve.

## 3.3 Tag & Metric Library

To keep schema work visible, the following tag libraries map directly onto the
JSON fields described above:

- **Modality tags**: `from_audio`, `from_video`, `from_location`, `from_manual_input`
- **Task type tags**: `shopping`, `todo`, `reminder`, `contact_info`, `project_idea`, `research_topic`, `health`, `finance`, `travel`, `cooking`, `maintenance`
- **Topic/domain tags**: `people`, `work`, `school`, `family`, `friends`, `sports`, `cs_ml`, `aerospace`, `startup`, `hardware`, `glass_ar`
- **Relationship tags (persons)**: `self`, `spouse`, `family`, `close_friend`, `acquaintance`, `colleague`, `client`, `service_provider`, `stranger`
- **Importance & urgency metrics**: importance (0–1), urgency (`low`, `medium`, `high`), `deadline`, `repetition_count`, `last_accessed_at`
- **Confidence metrics**: `asr_confidence`, `vision_confidence`, `speaker_match_confidence`, `face_match_confidence`, `llm_decision_confidence`
- **Privacy & visibility**: `privacy_level`, `shareable_to`

# Failure Modes Summary

## Component: Audio Pipeline

### Happy Path
- Input: synthetic frames (30ms windows)
- Output: transcript events persisted to SQLite

### Failure Modes
1. **Disk IO failure**
   - Trigger: audio segment directory unwritable
   - Observable: IOError from `AudioPipeline._write_segment`
   - Recovery: bubble error so caller can halt the session
   - Mitigation: storage directory is created at startup, unit tests cover persistence

2. **Database constraint violation**
   - Trigger: session deleted while pipeline still writing
   - Observable: sqlite3.IntegrityError during `insert_raw_event`
   - Recovery: exception surfaces to runner, no partial writes thanks to transactions

## Component: LLM Orchestrator

### Failure Modes
1. **Missing transcript payload**
   - Trigger: corrupted raw event payload
   - Observable: event skipped, warning logged
   - Mitigation: accessor defaults keep orchestrator deterministic during replays

2. **Low ASR/Speaker confidence**
   - Trigger: heuristics detect confidence below thresholds
   - Observable: issues array contains `low_asr_confidence` or `low_speaker_confidence`
   - Mitigation: review UI surfaces these issues and they are stored with the memory

## Component: Approval Workflow

### Failure Modes
1. **Rejected memory requires audit**
   - Trigger: reviewer rejects a proposed memory
   - Observable: `SupervisedLearningEvent` row with category `user_rejected_memory`
   - Mitigation: rejection reason stored, workflow keeps session in `pending_review` until resolution

2. **Stale session status**
   - Trigger: approvals happen concurrently from multiple clients
   - Observable: status oscillates between states
   - Mitigation: workflow recomputes aggregate counts on each mutation

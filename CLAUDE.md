# CLAUDE.md - AI Assistant Guide for AR-SmartAssistant

> **Last Updated**: 2025-11-19
> **Project Version**: 0.1.0 (POC Phase)
> **Purpose**: Comprehensive guide for AI assistants working on this codebase

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Codebase Structure](#codebase-structure)
3. [Architecture & Design Philosophy](#architecture--design-philosophy)
4. [Development Workflow](#development-workflow)
5. [Key Conventions](#key-conventions)
6. [Common Tasks](#common-tasks)
7. [Testing Strategy](#testing-strategy)
8. [Performance & Resource Constraints](#performance--resource-constraints)
9. [Security & Privacy](#security--privacy)
10. [How to Use Claude Effectively](#how-to-use-claude-effectively)

---

## Project Overview

### What This System Is

AR-SmartAssistant is a **personal memory augmentation system** that records and processes audio to create structured, searchable memories. It's an audio-first remembrance agent inspired by the classic Remembrance Agent concept.

**Core Capabilities:**
- Records audio during manual sessions (2-8 minutes typical)
- Transcribes speech using local Faster-Whisper ASR
- Identifies speakers via voice embeddings (Resemblyzer)
- Classifies events into memories, shopping items, tasks using LLM
- Stores structured data + embeddings for semantic retrieval
- **Runs entirely locally** (no cloud APIs)

**Critical Constraints:**
- **POC Phase**: Audio-only, no vision processing
- **Manual sessions**: No 24/7 continuous operation yet
- **Local-first**: All inference runs on local hardware
- **Privacy-critical**: Stores sensitive biometric and conversational data

### Hardware Reality

This system is designed to run on specific hardware with strict resource budgets:

```yaml
RTX 2060 (6GB VRAM):
  Whisper small.en: 2.0GB
  Future YOLOv8n: 1.0GB
  Future InsightFace: 0.8GB
  Headroom: 2.2GB

RTX 5060 Ti (16GB VRAM):
  LLaMA 3.1 8B Q4: 5.5GB
  Nomic embeddings: 0.4GB
  Headroom: 10.1GB

System RAM (32GB):
  OS overhead: 4GB
  Chroma index: 2GB
  Event queues: 1GB
  Application: 23GB
  Reserved: 2GB
```

**Critical Rule**: Never suggest solutions that violate these budgets without explicit discussion of trade-offs.

---

## Codebase Structure

### Directory Layout

```
AR-SmartAssistant/
├── ar_smart_assistant/          # Main Python package
│   ├── config.py                # YAML configuration loader with validation
│   ├── logging_utils.py         # Structured logging utilities
│   │
│   ├── database/                # Database layer
│   │   ├── schema.py            # SQLite schema definitions
│   │   └── repository.py        # Database operations (no ORM)
│   │
│   ├── perception/              # Audio processing (no dependencies on llm/ or memory/)
│   │   ├── audio_pipeline.py   # Energy-based VAD + ASR + speaker ID
│   │   ├── microphone.py        # PC microphone capture
│   │   └── websocket_receiver.py # Glass/phone audio streaming
│   │
│   ├── llm/                     # LLM orchestration (depends on perception/)
│   │   └── orchestrator.py     # Event classification and memory proposal
│   │
│   ├── memory/                  # Memory management (depends on llm/)
│   │   └── approvals.py        # Per-memory approval workflow
│   │
│   ├── workflows/               # High-level orchestration
│   │   └── session_runner.py   # Coordinates full pipeline
│   │
│   ├── tools/                   # CLI utilities
│   │   └── enroll_speaker.py   # Voice enrollment tool
│   │
│   └── ui/                      # Debug web interface
│       └── app.py               # Flask application
│
├── tests/                       # Pytest test suite
│   ├── test_config.py
│   ├── test_database.py
│   └── test_workflow.py
│
├── docs/                        # Documentation
│   ├── poc-audio-only/          # Phase 1 requirements
│   │   ├── requirements.md
│   │   ├── architecture.md
│   │   ├── audio-pipeline.md
│   │   ├── database-design.md
│   │   └── llm-orchestrator.md
│   ├── adr/                     # Architecture Decision Records
│   └── templates/               # Documentation templates
│
├── glass-app/                   # Android app for Google Glass (separate)
├── data/                        # Runtime data (gitignored)
│   ├── audio_segments/          # WAV files
│   ├── chroma/                  # Vector database
│   ├── logs/                    # Application logs
│   ├── brain_main.db            # Main database
│   └── system_metrics.db        # Metrics database
│
├── config.yaml.example          # Configuration template
├── pyproject.toml               # Python project metadata
├── setup.sh                     # Automated setup script
├── INSTALL.md                   # Installation guide
├── CONTRIBUTING.md              # Development guidelines
└── README.md                    # Quick start guide
```

### Module Dependency Graph (Enforced)

```
perception/  (no dependencies on llm/ or memory/)
    ↓
llm/  (depends on perception/ events, not memory/ internals)
    ↓
memory/  (depends on llm/ outputs)
    ↓
ui/  (read-only dependency on all layers)
```

**Violation Example (Rejected)**:
```python
# In perception/audio_worker.py
from memory.db_operations import insert_memory  # WRONG!
```

**Correct Pattern**:
```python
# In perception/audio_worker.py
def process_audio(segment) -> TranscriptEvent:
    return TranscriptEvent(...)  # Return event, don't write to DB

# In workflows/session_runner.py
from memory.approvals import store_memory
result = perception.process_audio(segment)
memory.store_memory(result)  # Orchestrator coordinates
```

---

## Architecture & Design Philosophy

### Core Principles

From `CONTRIBUTING.md`, these are **non-negotiable**:

1. **Fail Visibly, Not Silently**
   - Crash rather than corrupt data
   - Log errors rather than guess at missing data
   - Return `None` explicitly rather than empty string
   - Raise exceptions rather than return success flags with hidden errors

2. **Document Failure Modes**
   - Every PR requires failure mode analysis
   - Document what happens when GPU OOMs, LLM times out, disk fills, etc.
   - See `docs/templates/FAILURE_MODES_TEMPLATE.md`

3. **Measure, Don't Guess**
   - Benchmarks required for performance claims
   - "It feels fast" is not acceptable
   - Profile memory usage under realistic load
   - p50/p95/p99 latency measurements

4. **Privacy by Design**
   - No PII in logs (sanitize or hash)
   - Level 2+ data encrypted at rest
   - Speaker embeddings are biometric data (extremely sensitive)

5. **Modularity Enforced**
   - Clear dependency graph (see above)
   - No circular imports
   - Explicit interfaces with type hints

### Session Model

**Manual sessions only** (not 24/7):
- User starts session via UI button
- System records audio and generates events
- User stops session when done
- System proposes memories for review
- User approves/rejects **per-memory** (granular control)
- Only approved memories are embedded and searchable

**States**: `active` → `pending_review` → `partially_approved` / `fully_approved` / `rejected`

### Event-Level Persistence & Replay

Raw events are **immutable ground truth**:
- Store raw audio segments as WAV files
- Store transcript events with timestamps, speaker IDs, confidence scores
- LLM output is just one interpretation (can be regenerated)
- Support replay: load raw events, re-run LLM with new config, compare results

This enables:
- Model upgrades without re-recording
- A/B testing of prompts
- Debugging classification errors
- Supervised learning from user corrections

---

## Development Workflow

### Getting Started

```bash
# Clone and setup
git clone https://github.com/Srikanth1511/AR-SmartAssistant.git
cd AR-SmartAssistant

# Automated setup
./setup.sh

# Or manual setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Initialize database
python -c "from ar_smart_assistant.database.repository import BrainDatabase; BrainDatabase('data/brain_main.db', 'data/system_metrics.db')"

# Run tests
pytest

# Start debug UI
python -m ar_smart_assistant.ui.app
# Open http://localhost:5000
```

### Git Branch Strategy

When working on this repository:

1. **Always work on feature branches** starting with `claude/`
2. **Never push to main/master** directly
3. **Use atomic commits**: each commit should build and pass tests
4. **Write clear commit messages**: focus on "why", not just "what"

Example workflow:
```bash
# Already on claude/claude-md-mi5idug3ioef6t9s-012Ta3FquNMfCRUq69mbrPQb
git status
git add <files>
git commit -m "Add comprehensive CLAUDE.md for AI assistant guidance"
git push -u origin claude/claude-md-mi5idug3ioef6t9s-012Ta3FquNMfCRUq69mbrPQb
```

### Code Review Checklist

Before requesting review:

- [ ] Type hints on all functions (`mypy --strict` passes)
- [ ] Docstrings with failure modes documented
- [ ] No PII in log statements (sanitize/hash sensitive data)
- [ ] DB writes wrapped in explicit transactions
- [ ] Chaos test for each external dependency (GPU, Ollama, filesystem)
- [ ] Benchmark shows <10% regression vs baseline
- [ ] Memory profile shows peak < budget (4GB for 8-min session)
- [ ] No circular imports (`pytest tests/test_imports.py`)
- [ ] Test coverage >80% for new code

**Auto-reject conditions**:
- Hardcoded file paths (use `config.yaml`)
- `try/except: pass` without logging
- Sleep statements in production code
- Bare `except:` clauses
- Global variables holding state
- Mutable default arguments

---

## Key Conventions

### Configuration Management

**Always use config, never hardcode**:
```python
# Good
from ar_smart_assistant.config import load_config
config = load_config("config.yaml")
db_path = config.storage.databases.brain_main

# Bad
db_path = "/home/user/data/brain_main.db"  # Hardcoded!
```

Configuration is loaded from `config.yaml` with strict validation:
- All required fields must be present
- Invalid values raise `ValueError` at startup (fail fast)
- See `config.yaml.example` for full schema

### Database Operations

**No ORM, explicit SQL only**:
```python
# Good
def insert_memory(db: sqlite3.Connection, session_id: int, text: str) -> int:
    """
    Insert memory item.

    Failure Modes:
        - Session not found: Raises IntegrityError (foreign key)
        - DB locked: Retries 3x with exponential backoff
    """
    with db:  # Explicit transaction
        cursor = db.execute(
            "INSERT INTO memory_items (session_id, text) VALUES (?, ?)",
            (session_id, text)
        )
        return cursor.lastrowid

# Bad - no transaction, no error handling
db.execute("INSERT INTO memory_items ...")  # Unsafe!
```

**Foreign key enforcement**:
```python
# At database initialization
db.execute("PRAGMA foreign_keys = ON")
```

### Logging Standards

**No PII in logs**:
```python
# Good
logger.info(f"Processing event type={event['type']} ts={event['timestamp']}")
audio_hash = hashlib.sha256(audio_path.encode()).hexdigest()[:16]
logger.debug(f"Processing segment hash={audio_hash}")

# Bad
logger.info(f"User said: {transcript}")  # PII leak!
logger.debug(f"Processing {speaker_name}'s audio")  # PII leak!
```

**Structured logging**:
```python
from ar_smart_assistant.logging_utils import log_metric

log_metric("asr_confidence", confidence, metadata={"session_id": session_id})
```

### Type Hints (Required)

All public functions must have complete type hints:
```python
from typing import Optional
import numpy as np

def process_audio_segment(
    segment: np.ndarray,
    config: AsrConfig
) -> Optional[dict[str, Any]]:
    """
    Process audio segment through ASR.

    Args:
        segment: 16kHz mono PCM audio, 10-30 seconds
        config: ASR configuration

    Returns:
        Dict with 'transcript' and 'confidence', or None if failed

    Raises:
        GPUOutOfMemoryError: If VRAM exhausted

    Failure Modes:
        - Segment too short (<1s): Returns None
        - GPU unavailable: Falls back to CPU (logs warning)
    """
    ...
```

### File and Function Limits

To keep code reviewable and maintainable:

- **No source file may exceed 300 lines**
- **Functions limited to 40 lines and 4 parameters**
- Split into helper functions before hitting limits
- When refactoring, show both pieces in the diff

---

## Common Tasks

### Adding a New Configuration Field

1. Update `config.yaml.example` with new field and comment
2. Add field to appropriate `@dataclass` in `ar_smart_assistant/config.py`
3. Add validation in `from_dict()` method
4. Update docstring with failure modes
5. Write test in `tests/test_config.py`

Example:
```python
@dataclass(frozen=True)
class AsrConfig:
    # ... existing fields ...
    new_field: float

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AsrConfig":
        new_field = float(payload.get("new_field", 0.5))
        if not 0 <= new_field <= 1:
            raise ValueError("new_field must be between 0 and 1")
        # ...
```

### Adding a New Database Table

1. Update schema in `ar_smart_assistant/database/schema.py`
2. Add migration logic (if DB already exists)
3. Update `BrainDatabase` class in `repository.py` with access methods
4. Write rollback test (simulate crash mid-transaction)
5. Document failure modes in PR description

### Running a Recording Session

**Via UI** (recommended):
```bash
python -m ar_smart_assistant.ui.app
# Open http://localhost:5000
# Click "Start Session", speak, click "Stop Session"
# Review and approve/reject memories
```

**Via Python**:
```python
from ar_smart_assistant.config import load_config
from ar_smart_assistant.database.repository import BrainDatabase
from ar_smart_assistant.workflows.session_runner import SessionRunner
from ar_smart_assistant.perception.microphone import MicrophoneStream

config = load_config("config.yaml")
db = BrainDatabase("data/brain_main.db", "data/system_metrics.db")
runner = SessionRunner(config, db)

# Record from microphone
mic = MicrophoneStream(config.audio.capture)
mic.start()
# ... speak for a while ...
mic.stop()

# Process session
frames = list(mic.get_frames())
result = runner.run_session(frames)
print(f"Session {result['session_id']} created with {len(result['events'])} events")
```

### Debugging Audio Pipeline

```bash
# List available audio devices
python -c "from ar_smart_assistant.perception.microphone import list_audio_devices; list_audio_devices()"

# Test microphone capture
python -c "
from ar_smart_assistant.config import load_config
from ar_smart_assistant.perception.microphone import MicrophoneStream
import time

config = load_config('config.yaml')
mic = MicrophoneStream(config.audio.capture)
mic.start()
time.sleep(5)
mic.stop()
frames = list(mic.get_frames())
print(f'Captured {len(frames)} frames')
"

# Check Whisper model
python -c "
from faster_whisper import WhisperModel
model = WhisperModel('small.en', device='cpu', compute_type='int8')
print('Whisper loaded successfully')
"
```

### Speaker Enrollment

```bash
# Interactive enrollment
python -m ar_smart_assistant.tools.enroll_speaker

# Follow prompts:
# 1. Select audio device
# 2. Read 5 phrases (6+ seconds each)
# 3. Verify quality
# 4. Save profile
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_config.py

# With verbose output
pytest -v

# With coverage
pytest --cov=ar_smart_assistant --cov-report=html
```

### Benchmarking Performance

```bash
# Example benchmark for audio worker
python -c "
import time
import numpy as np
from ar_smart_assistant.perception.audio_pipeline import AudioPipeline
from ar_smart_assistant.config import load_config

config = load_config('config.yaml')
pipeline = AudioPipeline(config.audio)

latencies = []
for i in range(10):
    # Generate 10s of audio at 16kHz
    audio = np.random.randn(16000 * 10).astype(np.float32)

    start = time.perf_counter()
    result = pipeline.process_segment(audio)
    end = time.perf_counter()

    latencies.append(end - start)

print(f'p50: {np.percentile(latencies, 50):.3f}s')
print(f'p95: {np.percentile(latencies, 95):.3f}s')
print(f'p99: {np.percentile(latencies, 99):.3f}s')
"
```

---

## Testing Strategy

### Test Hierarchy

1. **Unit Tests** (table stakes):
   ```python
   def test_vad_config_valid():
       """Happy path: valid config loads successfully"""
       config = VadConfig.from_dict({
           "type": "energy_based",
           "energy_threshold_db": -45,
           "frame_duration_ms": 30,
           "min_speech_duration_ms": 300,
           "padding_duration_ms": 300
       })
       assert config.energy_threshold_db == -45
   ```

2. **Boundary Tests**:
   ```python
   def test_vad_config_invalid_threshold():
       """Negative threshold should raise ValueError"""
       with pytest.raises(ValueError, match="frame_duration_ms must be positive"):
           VadConfig.from_dict({
               "type": "energy_based",
               "energy_threshold_db": -45,
               "frame_duration_ms": -10,  # Invalid!
               ...
           })
   ```

3. **Chaos Tests** (critical for production):
   ```python
   def test_audio_worker_gpu_oom_recovery():
       """
       Simulate GPU OOM, verify graceful degradation.

       This test is CRITICAL because GPU OOM during a session
       would otherwise lose all memories from that segment.
       """
       # Fill GPU to 95%
       fill_vram_to_95_percent()

       worker = AudioWorker()
       result = worker.process(SAMPLE_AUDIO)

       # Should fail gracefully, not crash
       assert result["status"] == "error"
       assert result["error_type"] == "gpu_oom"

       # Should recover on next call
       clear_vram()
       result2 = worker.process(SAMPLE_AUDIO)
       assert result2["status"] == "success"
   ```

4. **Integration Tests**:
   ```python
   def test_full_session_workflow():
       """End-to-end: start → record → events → approve → embed"""
       # Tests cross-module integration
       db = BrainDatabase(":memory:", ":memory:")
       config = load_config("config.yaml.example")
       runner = SessionRunner(config, db)

       # Simulate session
       audio_frames = generate_test_audio()
       result = runner.run_session(audio_frames)

       # Verify events created
       assert len(result["events"]) > 0

       # Approve memory
       memory_id = result["memories"][0]["id"]
       approve_memory(db, memory_id)

       # Verify embedding created
       embeddings = db.get_embeddings_for_memory(memory_id)
       assert len(embeddings) > 0
   ```

### When to Write Which Tests

- **Unit tests**: Every configuration class, utility function, data model
- **Boundary tests**: All input validation (config parsing, API inputs)
- **Chaos tests**: Required for:
  - GPU operations (OOM, device not available)
  - Network calls (Ollama timeout, connection refused)
  - File I/O (disk full, permission denied)
  - Database transactions (crash mid-write)
- **Integration tests**: Major workflows (session recording, approval, replay)

---

## Performance & Resource Constraints

### Latency Budgets

```yaml
Audio Pipeline (RTX 2060):
  VAD detection: <10ms per 30ms frame
  Whisper inference: <3s per 10s segment (p95)
  Speaker embedding: <100ms per segment

LLM Orchestrator (RTX 5060 Ti):
  Event classification: <1s per event (p95)
  Embedding generation: <200ms per text

End-to-end: Audio segment → DB write: <5s (p99)
```

**All performance-critical code must include benchmarks**. Example:
```python
@pytest.mark.benchmark
def test_whisper_latency():
    """Ensure Whisper stays within budget"""
    latencies = [measure_whisper(audio) for _ in range(100)]
    assert np.percentile(latencies, 95) < 3.0, "p95 exceeds 3s budget"
```

### Memory Budgets

Application memory budget: **~4GB** for an 8-minute session with 1 event/second.

**Required**: Memory profiling for all PRs touching core pipeline:
```bash
python -m memory_profiler profile_session.py
# Peak usage must be < 4GB
```

Example profile script:
```python
from memory_profiler import profile

@profile
def run_full_session():
    """Simulate 8-minute session with 1 event/sec"""
    session = SessionManager()
    session.start_session()

    for i in range(480):  # 8 min * 60 sec
        event = simulate_audio_event()
        process_event(event)
        time.sleep(0.1)

    session.stop_session()
```

### Regression Thresholds

- **Latency regression >10%**: Requires justification and approval
- **Memory increase >100MB/hour**: Blocking bug (memory leak)
- **Test coverage decrease**: Must maintain >80% for new code

---

## Security & Privacy

### Data Classification

```
Level 0 - Public:
  - Model weights (Whisper, embeddings)
  - Configuration schemas
  - Anonymized benchmarks

Level 1 - Private:
  - System metrics (latencies, queue depths)
  - Error logs (sanitized, no PII)

Level 2 - Sensitive:
  - Raw audio segments
  - Transcripts
  - Speaker embeddings
  - Location history (future)

Level 3 - Extremely Sensitive:
  - "self" speaker profile (biometric identifier)
  - Full session archives
```

**Rules**:
1. Level 2+ data must **never** appear in logs or git
2. All Level 2+ data should be encrypted at rest (future work)
3. Supervised learning exports must be manually reviewed before sharing

### Sanitization Patterns

```python
# Always sanitize before logging
logger.info(f"Processing event type={event['type']} ts={event['timestamp']}")
# NO: logger.info(f"User said: {transcript}")

# Hash sensitive identifiers
audio_hash = hashlib.sha256(audio_path.encode()).hexdigest()[:16]
logger.debug(f"Processing segment hash={audio_hash}")
# NO: logger.debug(f"Processing {audio_path}")

# Use structured logging
log_metric("asr_confidence", confidence, metadata={"session_id": session_id})
# NO: logger.info(f"ASR confidence {confidence} for speaker {name}")
```

---

## How to Use Claude Effectively

### Effective Prompts

**❌ Too vague**:
> "Help me optimize the audio worker"

Claude doesn't know which metric matters (latency? memory? accuracy?).

**✅ Specific with constraints**:
> "The audio worker drops 30% of segments when queue >50. I have 2.1s avg Whisper latency and 5 segments/sec burst rate. Propose solutions that don't increase VRAM usage and document failure modes."

**✅ Include measurements**:
> "I'm seeing p95 LLM latency of 1.8s, target is 1.0s. Here's my prompt template: [paste]. Suggest optimizations with benchmark methodology."

**✅ Request chaos testing**:
> "I need a chaos test for session approval. Simulate: (1) user approves memory, (2) process crashes during Chroma write, (3) restart. Verify rollback."

### What Claude Should Catch in Code Review

- Missing failure mode documentation
- Bare `except:` clauses
- Hardcoded paths (should use config)
- PII in log statements
- Missing type hints
- Unbounded loops or queues
- Mutable default arguments
- No transaction wrapping for DB writes
- Files/functions exceeding size limits (300 lines / 40 lines)

### When Claude Should Push Back

**1. Violating Constraints**:
> User: "Add GPT-4 for better classification"
> Claude: "Blocked: (1) Violates local-only constraint, (2) Adds network latency and privacy risk. If you want to experiment, document exit strategy."

**2. Insufficient Testing**:
> User: "Here's my DB migration"
> Claude: "Where's the rollback test? Schema changes can corrupt data. Need: (1) forward migration test, (2) rollback test, (3) test with existing data."

**3. Missing Measurements**:
> User: "I made it faster"
> Claude: "Show benchmarks. Run bench_*.py for before/after. Need p50/p95/p99 latencies."

**4. Scope Expansion**:
> User: "Let's add real-time object tracking"
> Claude: "Out of POC scope (audio-only). Vision is Phase 2+. Would require YOLOv8 (1GB VRAM), leaving only 1GB headroom. Document trade-offs in ADR first."

### Project-Specific Knowledge Claude Has

From documentation, Claude should know:

1. **Hardware allocation**: RTX 2060 for perception, 5060 Ti for LLM
2. **Audio pipeline**: VAD → Whisper → Speaker ID → Events
3. **Database design**: Separate raw events + LLM outputs for replay
4. **Session model**: Manual start/stop, per-memory approval
5. **Privacy constraints**: No PII in logs, Level 2+ data encrypted (future)
6. **Performance budgets**: <3s Whisper p95, <1s LLM p95, <5s end-to-end
7. **Modularity rules**: perception → llm → memory (no circular deps)
8. **Testing philosophy**: Stress failure modes, not just happy paths

**When asking questions**: You don't need to re-explain this context.

### Example Effective Interaction

**User**: "Audio worker drops segments when queue >50. How should I implement backpressure?"

**Claude**:
```
Options:

1. Drop oldest (FIFO):
   - Pro: Preserves recent context
   - Con: Loses conversation start
   - Failure mode: Silent data loss

2. Drop newest (reject at enqueue):
   - Pro: Clear error signal
   - Con: Misses real-time events
   - Failure mode: Visible in logs

3. Batch processing:
   - Pro: Increases throughput
   - Con: Increases latency 20%
   - Failure mode: Larger VRAM footprint

Recommend: Option 2 + supervised learning log for debugging.

Implementation:
```python
try:
    queue.put_nowait(event)
except Full:
    log_metric('segment_dropped_queue_full', 1)
    save_to_supervised('dropped_segments', event)
```

Then benchmark: Can we reduce Whisper latency to avoid queue limit?
```

---

## Red Flags - Immediate Warning Required

Claude should **immediately warn** when seeing:

- `except: pass` without logging
- Hardcoded paths (e.g., `/home/user/data`)
- Print statements in production code
- SQL string concatenation (injection risk)
- Storing plaintext biometrics
- No transaction for multi-step DB writes
- Promises of "5x faster" without benchmarks
- Ignoring hardware constraints
- "It works on my machine" without reproducible setup
- Files >300 lines or functions >40 lines

---

## Quick Reference

### File Locations

| What | Where |
|------|-------|
| Configuration schema | `ar_smart_assistant/config.py` |
| Database schema | `ar_smart_assistant/database/schema.py` |
| Audio pipeline | `ar_smart_assistant/perception/audio_pipeline.py` |
| LLM orchestration | `ar_smart_assistant/llm/orchestrator.py` |
| Session workflow | `ar_smart_assistant/workflows/session_runner.py` |
| Debug UI | `ar_smart_assistant/ui/app.py` |
| Requirements docs | `docs/poc-audio-only/requirements.md` |
| Architecture docs | `docs/poc-audio-only/architecture.md` |
| ADRs | `docs/adr/` |

### Key Commands

```bash
# Setup
./setup.sh                                    # Automated setup
python -m ar_smart_assistant.tools.enroll_speaker  # Voice enrollment

# Running
python -m ar_smart_assistant.ui.app           # Start debug UI

# Testing
pytest                                        # Run all tests
pytest -v tests/test_config.py                # Specific test

# Benchmarking
python bench_audio_worker.py                  # Performance tests
python -m memory_profiler profile_session.py  # Memory profiling

# Database
sqlite3 data/brain_main.db ".schema"          # View schema
sqlite3 data/brain_main.db "SELECT * FROM sessions"  # Query
```

### Performance Targets

| Component | Metric | Target |
|-----------|--------|--------|
| VAD | Latency | <10ms per 30ms frame |
| Whisper | p95 latency | <3s per 10s segment |
| Speaker ID | Latency | <100ms per segment |
| LLM | p95 latency | <1s per event |
| Embeddings | Latency | <200ms per item |
| End-to-end | p99 latency | <5s segment→DB |
| Session memory | Peak usage | <4GB for 8min session |

---

## The Prime Directive

**When in doubt, prefer the solution that fails visibly over the one that fails silently.**

Examples:
- Crash rather than corrupt the database
- Log an error rather than guess at missing data
- Return `None` explicitly rather than empty string
- Raise exception rather than success flag with hidden error

This system stores personal memories. Silent failures compound over months and become catastrophic. Loud failures during development are healthy.

---

## Questions?

- **Installation issues**: See `INSTALL.md`
- **Development guidelines**: See `CONTRIBUTING.md`
- **Architecture details**: See `docs/poc-audio-only/`
- **Design decisions**: See `docs/adr/`

**Remember**: Claude is a tool for exploring design space, generating boilerplate, and reviewing rigor—but **you** decide what's in scope, what trade-offs are acceptable, and when to ship.

This is your memory system. Own the architecture.

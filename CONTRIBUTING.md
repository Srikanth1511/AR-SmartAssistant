# CONTRIBUTING.md

## Engineering Discipline for a Personal Surveillance System

Make it modular, simple straightforward and easy to read, understnd and reporduce

This project records continuous audio, processes speaker identity, and stores lifetime memories. A bug doesn't just crash—it creates privacy violations, false memories, or data corruption that compounds over months. Contributors must internalize that **this is not a toy project**.

---

## Core Constraints (Non-Negotiable)

### Hardware Budget

```yaml
Compute Allocation:
  RTX 2060 (6GB VRAM):
    - Whisper small.en: 2.0GB
    - YOLOv8n (future): 1.0GB
    - InsightFace (future): 0.8GB
    - Headroom: 2.2GB
    Violation: Code that OOMs this GPU is rejected.
    
  RTX 5060 Ti (16GB VRAM):
    - LLaMA 3.1 8B Q4: 5.5GB
    - Nomic embeddings: 0.4GB
    - Headroom: 10.1GB
    Violation: Embeddings that grow >400MB are rejected.

  System RAM (32GB):
    - OS overhead: 4GB
    - Chroma index: 2GB
    - Event queues: 1GB
    - Application: 23GB
    - Reserved: 2GB
    Violation: Memory leaks that grow >100MB/hour are blocking bugs.
```

**All PRs must include memory profiling** showing peak usage under realistic load (8-minute session, 1 event/sec).

### Latency Budgets

```
Audio Pipeline (RTX 2060):
  VAD detection: <10ms per 30ms frame
  Whisper inference: <3s per 10s segment
  Speaker embedding: <100ms per segment
  
LLM Orchestrator (RTX 5060 Ti):
  Event classification: <1s per event (p95)
  Embedding generation: <200ms per text
  
End-to-end: Audio segment → DB write: <5s (p99)
```

**All performance-critical code must include benchmarks**. "It feels fast" is not a measurement.

### Database Integrity

This system is write-heavy (multiple events/sec during sessions) and read-light (retrieval queries during review). Database corruption is **catastrophic** because:

1. Raw audio archives are large (hundreds of MB per week)
2. Re-running inference on months of audio is infeasible
3. Cross-session references mean corruption spreads

**Requirements**:
- Every DB write must be wrapped in explicit transactions
- All foreign keys must be enforced (`PRAGMA foreign_keys = ON`)
- Schema migrations must be tested with rollback paths
- No ORM magic—explicit SQL only, with EXPLAIN QUERY PLAN for all SELECT statements with JOINs

**Test coverage**: Every DB operation must have a test that simulates mid-transaction crash (kill -9) and verifies rollback.

---

## Failure Mode Documentation (Required)

Code that only documents success paths is incomplete. Every PR touching critical paths must include `FAILURE_MODES.md` section:

### Template

```markdown
## Component: Audio Worker - Whisper ASR

### Happy Path
Input: 10s audio segment, 16kHz PCM
Output: Transcript with confidence score
Latency: 2.1s (avg), 2.8s (p95)

### Failure Modes

1. **GPU Out of Memory**
   - Trigger: Whisper + another process saturates 2060
   - Observable: CUDA OOM exception
   - Recovery: Drop segment, log to supervised learning, emit degraded event
   - User Impact: Missing transcript for 10s window
   - Mitigation: Queue depth limit (100 segments max)
   
2. **Model File Corrupted**
   - Trigger: Disk corruption, incomplete download
   - Observable: Model load fails at startup
   - Recovery: Exit with clear error code
   - User Impact: System won't start
   - Mitigation: Hash verification on model files (TODO: #47)
   
3. **VAD False Negative (Silence Misclassified as Speech)**
   - Trigger: Energy threshold too high, microphone saturation
   - Observable: No speech detected despite audio present
   - Recovery: None (lost data)
   - User Impact: Missing memories during session
   - Mitigation: Tunable threshold in config, supervised learning logs for manual review
   
4. **Speaker Embedding Drift**
   - Trigger: Voice changes (illness, aging), different microphone position
   - Observable: "self" speaker confidence drops below 0.8
   - Recovery: Flag for re-enrollment
   - User Impact: Memories attributed to "unknown" instead of "self"
   - Mitigation: Re-enrollment workflow (TODO: #23)
```

**Rejection criteria**: PR fails review if it doesn't document failure modes for code paths involving:
- GPU inference
- Database writes
- Network I/O
- File system operations
- External process calls (Ollama, Chroma)

---

## Privacy & Safety 

### Data Classification

```
Level 0 - Public:
  - Model weights
  - Configuration schemas
  - Anonymized benchmark results

Level 1 - Private:
  - System metrics (queue depths, latencies)
  - Error logs (sanitized, no PII)

Level 2 - Sensitive:
  - Raw audio segments
  - Transcripts
  - Speaker embeddings
  - Face embeddings (future)
  - Location history

Level 3 - Extremely Sensitive:
  - "self" speaker profile (unique biometric)
  - Full session archives (audio + transcripts + context)
```

**Rules**:
1. Level 2+ data must never appear or be added to github but the repo should warn that these are present.
2. All supervised learning exports must be manually reviewed before sharing



**REQUIRED**:
```python
# Sanitize before logging
logger.info(f"Processing event type={event['type']} ts={event['timestamp']}")

# Hash sensitive identifiers
audio_hash = hashlib.sha256(audio_path.encode()).hexdigest()[:16]
logger.debug(f"Processing audio segment hash={audio_hash}")

# Use structured logging with explicit levels
log_metric("asr_confidence", confidence, metadata={"session_id": session_id})
```

---

## Testing Philosophy: Stress Failure, Not Success

### Unit Tests (Minimum Bar)

```python
def test_audio_worker_processes_segment():
    """Happy path: valid audio → transcript"""
    worker = AudioWorker()
    result = worker.process(SAMPLE_10S_AUDIO)
    assert result["transcript"] != ""
    assert 0 < result["confidence"] < 1
```

This is **table stakes**. The real tests are:

### Chaos Tests (Required for Core Components)

```python
def test_audio_worker_gpu_oom_recovery():
    """
    Simulate GPU OOM by filling VRAM, verify graceful degradation.
    """
    # Fill GPU with dummy tensors
    fill_vram_to_90_percent()
    
    worker = AudioWorker()
    result = worker.process(SAMPLE_10S_AUDIO)
    
    # Should fail gracefully, not crash
    assert result["status"] == "error"
    assert result["error_type"] == "gpu_oom"
    
    # Should log for supervised learning
    assert supervised_log_contains("gpu_oom")
    
    # Should not corrupt state
    next_result = worker.process(SAMPLE_10S_AUDIO)
    assert next_result["status"] == "success"  # Recovers on next attempt

def test_database_write_mid_transaction_crash():
    """
    Kill process during transaction, verify rollback on restart.
    """
    session = SessionManager()
    session_id = session.start_session()
    
    # Write partial data
    insert_memory(session_id, "partial memory")
    
    # Simulate crash (force exit without commit)
    os.kill(os.getpid(), signal.SIGKILL)
    
    # On restart, verify rollback
    assert get_memory_count(session_id) == 0
    

def test_llm_malformed_json_response():
    """
    LLM returns markdown-wrapped JSON, verify parsing robustness.
    """
    response = """
    Sure! Here's the JSON:
    ```json
    {"actions": [{"type": "add_memory", "text": "test"}]}
    ```
    """
    
    result = parse_llm_response(response)
    assert result["actions"][0]["type"] == "add_memory"
    

def test_event_queue_overflow_backpressure():
    """
    Inject 1000 events/sec, verify queue doesn't grow unbounded.
    """
    queue = EventQueue(maxsize=100)
    
    for i in range(1000):
        try:
            queue.put_nowait({"id": i})
        except Full:
            pass  # Expected
    
    # Queue should be at capacity, not crashed
    assert queue.qsize() == 100
    
    # Oldest events should be preserved (or document drop policy)
    first_event = queue.get()
    assert first_event["id"] == 0  # FIFO, or document LIFO
```

**PR rejection criteria**: Any change to audio pipeline, LLM orchestrator, or DB layer without chaos tests.

---

## Performance Measurement (Not Optional)

### Benchmark Harness

Every performance-sensitive module must include `bench_<module>.py`:

```python
# bench_audio_worker.py
import time
import numpy as np
from audio_worker import AudioWorker


def bench_whisper_inference():
    """
    Measure Whisper latency distribution over 100 segments.
    """
    worker = AudioWorker()
    latencies = []
    
    for _ in range(100):
        audio = generate_10s_speech()  # Realistic speech, not silence
        
        start = time.perf_counter()
        result = worker.process(audio)
        end = time.perf_counter()
        
        latencies.append(end - start)
    
    print(f"p50: {np.percentile(latencies, 50):.3f}s")
    print(f"p95: {np.percentile(latencies, 95):.3f}s")
    print(f"p99: {np.percentile(latencies, 99):.3f}s")
    print(f"max: {max(latencies):.3f}s")
    
    # Assert against budget
    assert np.percentile(latencies, 95) < 3.0, "p95 latency exceeds 3s budget"


if __name__ == "__main__":
    bench_whisper_inference()
```

**CI requirement**: Benchmarks run on every PR. Regressions >10% fail CI.

### Memory Profiling

```python
# profile_memory.py
from memory_profiler import profile


@profile
def run_full_session():
    """
    Simulate 8-minute session with 1 event/sec.
    Measure peak memory usage.
    """
    session = SessionManager()
    session.start_session()
    
    for i in range(480):  # 8 minutes * 60 sec
        event = simulate_audio_event()
        process_event(event)
        time.sleep(0.1)  # Faster than realtime
    
    session.stop_session()


if __name__ == "__main__":
    run_full_session()
```

Output must show peak < 4GB application memory.

---

## Modularity & Interface Contracts

### Dependency Graph (Enforced)

```
perception/ (no dependencies on llm/ or memory/)
  ↓
llm/ (depends on perception/ events, no dependency on memory/ internals)
  ↓
memory/ (depends on llm/ outputs, no circular dependencies)
  ↓
debug/ (read-only dependency on all layers)
```

**Violation example** (rejected):
```python
# In perception/audio_worker.py
from memory.db_operations import insert_memory  # WRONG: perception shouldn't know about DB schema
```

**Correct**:
```python
# In perception/audio_worker.py
def process_audio(segment) -> TranscriptEvent:
    # Return event, let orchestrator decide what to do with it
    return TranscriptEvent(...)

# In llm/orchestrator.py
from memory.db_operations import insert_memory  # OK: orchestrator coordinates
```

### Interface Stability

Public interfaces (anything imported across module boundaries) require:

1. **Type annotations** (enforced by mypy):
   ```python
   def process_audio(segment: np.ndarray) -> TranscriptEvent:
       ...
   ```

2. **Docstrings with failure modes**:
   ```python
   def classify_event(event: dict) -> dict:
       """
       Classify event and decide actions.
       
       Args:
           event: TranscriptEvent dict with keys: timestamp, speaker_id, transcript
       
       Returns:
           dict with "actions" list
       
       Raises:
           OllamaConnectionError: If LLM server unreachable
           JSONDecodeError: If LLM returns malformed response (captured, logged)
       
       Failure Modes:
           - LLM timeout: Returns {"actions": [], "error": "timeout"}
           - Invalid event schema: Logs error, returns empty actions
       """
   ```

3. **Backward compatibility promise**:
   - Adding optional parameters: OK
   - Adding new return fields: OK
   - Changing required parameter types: Breaking change, requires major version bump
   - Removing return fields: Breaking change

---

## Code Review Checklist

Before requesting review, verify:

- [ ] Memory profiling shows peak < budget for 8-min session
- [ ] Benchmark shows p95 latency < budget
- [ ] All DB operations wrapped in transactions
- [ ] Chaos test for each external dependency (GPU, Ollama, filesystem)
- [ ] No Level 2+ data in log statements
- [ ] `FAILURE_MODES.md` section added to PR description
- [ ] Type hints pass `mypy --strict`
- [ ] No circular imports between modules
- [ ] Docstrings document failure modes, not just happy path
- [ ] Test coverage >80% for new code (but quality > quantity)

**Auto-reject conditions**:
- Hardcoded file paths (use config)
- `try/except: pass` without logging
- Sleep statements in production code (outside tests)
- Mutable default arguments
- Bare `except:` clauses
- Global variables holding state

---

## Contribution Workflow

### 1. Design Doc First (For Substantial Changes)

Don't code for 2 weeks then submit a 5000-line PR. Write a design doc:

```markdown
## Problem
Current ASR worker drops 30% of segments when queue >50 items.

## Root Cause Analysis
1. Whisper inference is blocking (2.1s avg)
2. VAD produces segments faster than Whisper consumes (5 segments/sec burst)
3. Queue fills during conversation bursts

## Proposed Solution
Implement batch processing:
- Accumulate up to 5 segments
- Process as batch (Whisper supports batch input)
- Reduces overhead, increases throughput to 7 segments/sec

## Trade-offs
- Increased latency: 2.1s → 2.8s (batching delay)
- Reduced memory safety: 5x segments in VRAM simultaneously
- Complexity: Batch assembly logic

## Alternative Considered
Upgrade to Whisper medium (rejected: 4GB VRAM, exceeds budget)

## Rollback Plan
Feature flag: `audio.asr.enable_batching = false`
```

Post design doc as issue, get feedback before coding.

### 2. Atomic Commits

Each commit should:
- Build successfully
- Pass all existing tests
- Change one logical thing

Bad commit: "Fix bug and add feature and refactor"
Good commits:
1. "Add chaos test for GPU OOM in audio worker"
2. "Implement graceful degradation on GPU OOM"
3. "Update failure modes doc for audio worker"

### 3. PR Size


Exception: Generated code (schema migrations, benchmark data).

### 4. Review SLA

Reviewers have 48 hours to respond. After 48h with no response, merge is permitted if:
- All CI checks pass
- Code review checklist completed
- Design doc (if applicable) was approved

---

## Security & Privacy Review (Blocking)

Changes touching these areas require security review:

- Speaker enrollment (biometric data collection)
- Database encryption
- Session approval workflow
- Supervised learning data export
- Debug server authentication (future)
- Raw audio file handling

**Review criteria**:
1. Data minimization: Could we achieve the goal with less PII?
2. Encryption at rest: Is Level 2+ data encrypted?
3. Access control: Who can read this data?
4. Retention policy: When is this data deleted?
5. Auditability: Can we prove what happened to this data?

---

## Dependency Management

### Allowed Dependencies

- Core ML: `torch`, `faster-whisper`, `resemblyzer`, `chromadb`
- LLM: `ollama` (via HTTP, not library dependency)
- Database: `sqlite3` (stdlib), `sqlalchemy` (banned—too much magic)
- Web: `flask`, `flask-cors`
- Testing: `pytest`, `pytest-benchmark`, `memory_profiler`
- Utilities: `pyyaml`, `numpy`, `opencv-python`

### Banned Dependencies

- Heavy frameworks: Django, FastAPI (Flask is sufficient)
- ORMs: SQLAlchemy, Peewee (raw SQL only)
- Async: asyncio, trio (adds complexity, no clear benefit)
- Pandas (memory hog for our use case)
- Jupyter (analysis notebooks should use scripts)

**Adding new dependency**: Requires justification in PR:
- What problem does it solve?
- Why can't we use existing dependencies?
- What's the maintenance burden (last release date, open issues)?
- What's the license?

---

## Documentation Standards

### Code Comments

**Don't**:
```python
# Increment counter
counter += 1
```

**Do**:
```python
# Track enrollment attempts to detect brute-force attacks
# See: https://github.com/project/issues/47
enrollment_attempts[speaker_id] += 1
```

Comments should explain **why**, not **what**. If you need to explain what, the code is too complex.

### Architecture Decision Records (ADRs)

When making significant design choices, document:

```markdown
# ADR-003: Use Resemblyzer for Speaker ID Instead of Pyannote

## Context
Need speaker identification with <100ms latency, <1GB VRAM.

## Decision
Use Resemblyzer (256-dim embeddings, 80ms latency).

## Consequences
Positive:
- Meets latency budget
- Simple API
- Small VRAM footprint (800MB)

Negative:
- Less accurate than Pyannote for noisy environments (87% vs 92% F1)
- Not actively maintained (last update 2021)
- No diarization support (future feature blocked)

## Alternatives Considered
- Pyannote: Too slow (300ms), too large (2GB VRAM)
- Custom model: 3+ months development time

## Review Date
2025-06-01 (revisit if latency budget increases or VRAM budget increases)
```

Store in `docs/adr/`.

---

## The Prime Directive

**When in doubt, prefer the solution that fails visibly over the one that fails silently.**

Examples:
- Crash the process rather than corrupt the database
- Log an error rather than guess at missing data
- Return `None` and handle it explicitly rather than empty string
- Raise an exception rather than return a success flag with hidden error state

This system stores your life. Debugging subtle memory corruption months later is catastrophic. Crashing during development is healthy.

---

## Questions?

Open an issue with the `question` label. Don't ask in PRs—that's for code review, not architecture discussion.

---

# CLAUDE.md

## Using Claude for AR-SmartAssistant Development

This document explains how to effectively use Claude (the AI assistant) on this project. Claude has context on the architecture, constraints, and design philosophy—use it.

---

## Project Context for Claude

### What This System Is

A personal memory augmentation system that:
- Records audio during manual sessions (2-8 minutes)
- Transcribes speech using local Whisper ASR
- Identifies speakers via voice embeddings
- Classifies events into memories, shopping items, tasks
- Stores structured data + embeddings for semantic retrieval
- Runs entirely locally (no cloud APIs)

**Critical constraint**: This is POC-phase. No vision processing yet (deferred). Audio-only.

### Hardware Reality

```
RTX 2060 (6GB):  Whisper small.en (2GB) + headroom (4GB)
RTX 5060 Ti (16GB): LLaMA 3.1 8B Q4 (5.5GB) + embeddings (0.4GB) + headroom (10GB)
32GB RAM: Application budget ~23GB
```

Claude should **never suggest** solutions that violate these budgets without explicit discussion of the trade-off.

### Design Philosophy

From `CONTRIBUTING.md`:
- **Fail visibly, not silently**: Crash rather than corrupt
- **Document failure modes**: Every PR requires failure analysis
- **Measure, don't guess**: Benchmarks required for performance claims
- **Privacy by design**: No PII in logs, encryption for biometrics
- **Modularity enforced**: Clear dependency graph, no circular imports

---

## Effective Prompts for This Project

### ❌ Bad Prompts

**Too vague**:
> "Help me optimize the audio worker"

Claude doesn't know which metric you care about (latency? memory? accuracy?).

**Missing constraints**:
> "Add face recognition to the system"

Violates project scope (audio-only POC). Claude should push back.

**No failure mode thinking**:
> "Write a function to classify events"

Doesn't specify what happens when LLM is unreachable, returns invalid JSON, times out, etc.

### ✅ Good Prompts

**Specific with constraints**:
> "The audio worker drops 30% of segments when queue >50. I have 2.1s avg Whisper latency and 5 segments/sec burst rate. Propose solutions that don't increase VRAM usage and document failure modes."

**Includes measurement**:
> "I'm seeing p95 LLM latency of 1.8s, target is 1.0s. Here's my current prompt template: [paste]. Suggest optimizations with before/after benchmark methodology."

**Requests chaos testing**:
> "I need a chaos test for the session approval workflow. Simulate: (1) user approves memory A, (2) process crashes during Chroma write, (3) restart. Verify rollback semantics."

**Asks for trade-off analysis**:
> "Should I use batched Whisper inference (5 segments at once) to increase throughput? Document latency trade-off, VRAM impact, and failure mode changes."

---

## Code Generation Standards

When asking Claude to generate code:

### 1. Always Request Type Hints

**Don't**:
> "Write a function to parse LLM JSON responses"

**Do**:
> "Write a function to parse LLM JSON responses with full type hints. Return type should be `dict[str, Any]` with specific keys documented. Handle markdown code block wrapping."

### 2. Demand Failure Mode Documentation

**Template**:
```python
def process_audio_segment(segment: np.ndarray) -> TranscriptEvent:
    """
    Process audio segment through Whisper ASR.
    
    Args:
        segment: 16kHz mono PCM audio, 10-30 seconds
        
    Returns:
        TranscriptEvent with transcript and confidence
        
    Raises:
        GPUOutOfMemoryError: If VRAM exhausted
        WhisperModelNotLoadedError: If model initialization failed
        
    Failure Modes:
        - Segment too short (<1s): Returns empty transcript, confidence=0
        - Segment too long (>30s): Truncates to 30s, logs warning
        - GPU unavailable: Falls back to CPU (50x slower, logs degradation)
        - Invalid audio format: Raises ValueError with specific format expected
    """
```

Ask Claude to fill in the docstring **before** writing the implementation.

### 3. Request Tests Alongside Code

**Workflow**:
```
User: "Write audio worker GPU OOM recovery"
Claude: [generates implementation]
User: "Now write the chaos test that verifies this recovery"
Claude: [generates test]
```

Don't accept implementation without test.

### 4. Specify Performance Budgets

**Example**:
> "Write embedding generation for memory items. Target: <200ms per item, batch size 10. Measure peak VRAM usage—must stay under 1GB."

Claude should include benchmark code:
```python
@pytest.mark.benchmark
def test_embedding_generation_latency():
    items = [generate_memory() for _ in range(10)]
    
    start = time.perf_counter()
    embeddings = generate_embeddings(items)
    end = time.perf_counter()
    
    assert (end - start) < 0.200, "Exceeds 200ms budget"
```

---

## Asking Claude to Review Code

### Effective Review Prompts

**Include context**:
> "Review this LLM orchestrator code. Constraints: RTX 5060 Ti 16GB, p95 latency budget 1s, must handle Ollama connection failures gracefully. Check for: (1) missing error handling, (2) PII in logs, (3) unbounded memory growth."

**Specify review focus**:
> "Security review: Does this speaker enrollment code protect against brute-force attacks? Are embeddings encrypted at rest? Are there timing side channels?"

**Request specific analysis**:
> "This DB transaction has 3 writes. If the process crashes after write 2, what's the state? Show me the exact rollback behavior."

### What Claude Should Catch

From `CONTRIBUTING.md`:
- Missing failure mode documentation
- Bare `except:` clauses
- Hardcoded paths (should use config)
- PII in log statements
- Missing type hints
- Unbounded loops or queues
- Mutable default arguments
- Sleep in production code
- No transaction wrapping for DB writes

---

## Architecture Questions

### When to Ask Claude vs. Check Docs

**Ask Claude**:
- Implementation details ("How should I structure the VAD → Whisper pipeline?")
- Trade-off analysis ("Batch inference vs. streaming—which for our latency budget?")
- Failure mode brainstorming ("What happens if Ollama crashes mid-inference?")
- Code review ("Is this transaction handling correct?")

**Check Docs First**:
- Hardware budgets → `config/system_config.yaml`
- Module interfaces → `src/<module>/__init__.py`
- Design decisions → `docs/adr/`
- Database schema → `schema_main.sql`

If docs are incomplete, ask Claude to draft an ADR.

---

## Common Pitfalls (Claude Should Warn About These)

### 1. Scope Creep

**User**: "Can we add real-time object tracking?"

**Claude Should Say**: "That's outside POC scope (audio-only). Vision is deferred to Phase 3. If you want to prototype, it would require YOLOv8 (1GB VRAM on RTX 2060), leaving only 1GB headroom. Acceptable for experiment, but document trade-offs."

### 2. Optimistic Assumptions

**User**: "Let's use GPT-4 API for better LLM classification"

**Claude Should Say**: "Violates local-only constraint. Introduces latency (200-500ms network RTT), cost ($0.03/1K tokens), and privacy risk (transcripts leave your machine). If you want to experiment, document exit strategy for production."

### 3. Missing Measurements

**User**: "I optimized the audio worker, it's much faster now"

**Claude Should Say**: "Great! Show me benchmarks. Before/after for: (1) p50/p95/p99 latency, (2) peak memory, (3) GPU utilization. Run `bench_audio_worker.py` and paste results."

### 4. Insufficient Error Handling

**User**: "Here's my LLM client" [pastes code with no try/except]

**Claude Should Say**: "Missing error handling for: (1) Ollama connection refused, (2) HTTP timeout, (3) malformed JSON response, (4) rate limiting. Add try/except blocks and document failure modes."

---

## Testing Methodology

### What to Ask Claude to Generate

1. **Happy path test** (table stakes):
   ```python
   def test_process_audio_valid_segment():
       result = worker.process(VALID_AUDIO)
       assert result["transcript"] != ""
   ```

2. **Boundary tests**:
   ```python
   def test_process_audio_too_short():
       result = worker.process(AUDIO_500MS)  # Min is 1s
       assert result["transcript"] == ""
       assert result["error"] == "segment_too_short"
   ```

3. **Chaos tests** (critical):
   ```python
   def test_process_audio_gpu_oom():
       fill_gpu_to_95_percent()
       result = worker.process(VALID_AUDIO)
       assert result["status"] == "error"
       assert result["error_type"] == "gpu_oom"
       # Verify recovery on next call
   ```

4. **Integration tests**:
   ```python
   def test_full_session_workflow():
       """End-to-end: start session → events → approve → finalize"""
       # Tests cross-module integration
   ```

**Ask Claude**: "Generate chaos tests for [component]. Focus on: GPU OOM, network failures, disk full, process crash mid-transaction."

---

## Performance Analysis Workflow

### 1. Identify Bottleneck

**User**: "System feels slow during sessions"

**Claude**: "Run profiler first. Use `python -m cProfile -o profile.stats src/main.py` then `snakeviz profile.stats`. Paste the top 10 functions by cumulative time."

### 2. Propose Solution with Measurements

**User**: [pastes profile showing 80% time in Whisper inference]

**Claude**: "Whisper is the bottleneck. Options:
1. Batching (increases latency 20%, reduces per-segment overhead)
2. Smaller model (small.en → tiny.en, 2x faster but -5% accuracy)
3. GPU upgrade (out of scope for POC)

Recommend: Prototype batching. Benchmark script:
```python
# Compare latency distribution for batch_size=[1, 5, 10]
```
"

### 3. Validate with Benchmarks

**User**: [implements batching]

**Claude**: "Before accepting: Run `bench_audio_worker.py` for batch_size=5. Compare p95 latency to baseline. If <10% regression and throughput >2x, approve. If latency increases >20%, reject—violates budget."

---

## Debugging Workflow

### Structured Debugging Prompts

**Instead of**: "It's broken, help"

**Use**:
```
Component: LLM Orchestrator
Symptom: classify_event() returns empty actions for 30% of events
Expected: <5% empty action rate
Observed: 30% empty, logs show "json_parse_error"
Context: Started after upgrading Ollama from 0.1.20 → 0.1.25
Logs: [paste last 20 lines]
Question: What changed in Ollama response format?
```

**Claude's Response Should**:
1. Hypothesize root cause
2. Suggest diagnostic steps (compare API responses before/after)
3. Propose fix with rollback plan
4. Recommend regression test to prevent recurrence

---

## Refactoring Guidance

**Before refactoring**, ask Claude:

> "I want to refactor the audio worker to use async/await for better concurrency. Constraints: (1) must maintain <3s p95 latency, (2) can't increase VRAM, (3) must preserve failure mode behavior. Analyze trade-offs."

**Claude Should Evaluate**:
- Complexity increase (async adds cognitive load)
- Does concurrency actually help? (GPU inference is inherently sequential)
- Risk of introducing new race conditions
- Backward compatibility with existing tests

**Claude Should Recommend**: "Async adds complexity without clear benefit—Whisper inference is GPU-bound, not I/O-bound. If goal is higher throughput, batching is simpler. If you proceed with async anyway, write async chaos tests for cancellation and timeout."

---

## Code Quality Gates


Before merging, ask Claude to verify:

```
Checklist:
[ ] Type hints on all functions
[ ] Docstrings with failure modes
[ ] No PII in log statements
[ ] DB writes wrapped in transactions
[ ] Chaos test for each external dependency
[ ] Benchmark shows <10% regression
[ ] Memory profile shows peak < budget
[ ] No circular imports (run: python -m pytest tests/test_imports.py)
```

**If any fail**: Claude should block and explain why.

---
## Guardrails for AI-assisted changes

To keep generated patches reviewable and debuggable, every contribution (human or AI-assisted) must follow the rules below.
## File and function limits

* No source file may exceed **300 lines**.
* Functions are limited to **40 lines** and **4 parameters**.
* Split work into helpers before hitting those limits. When a function grows, show both pieces in the diff.

## When Claude Should Push Back

### 1. Violating Constraints

**User**: "Add GPT-4 Vision for better scene understanding"

**Claude**: "Blocked: (1) Violates local-only constraint, (2) VLM is deferred to TODO, (3) No GPU budget for vision processing in Phase 1. If you want to explore, document trade-offs in ADR first."

### 2. Insufficient Testing

**User**: "Here's my new DB schema migration"

**Claude**: "Where's the rollback test? Schema changes are irreversible if they corrupt data. Need: (1) Forward migration test, (2) Rollback test, (3) Test with real session data (not empty DB)."

### 3. Missing Measurements

**User**: "I made it faster"

**Claude**: "Show benchmarks. `git diff` isn't a performance measurement. Run `bench_*.py` for before/after comparison."

### 4. Scope Expansion Without Justification

**User**: "Let's add a mobile app for session control"

**Claude**: "Out of scope for POC. Current debug web UI works. If you want mobile control, write ADR justifying: (1) problem with web UI, (2) development time estimate, (3) maintenance burden, (4) security implications (authentication)."

---

## Project-Specific Knowledge Claude Has

From previous conversations, Claude knows:

1. **Hardware allocation**: RTX 2060 for perception, 5060 Ti for LLM
2. **Audio pipeline**: Glass → Phone → PC with noise suppression, AGC, echo cancellation
3. **Database design**: Separate raw events + LLM outputs for replay capability
4. **Session model**: Manual start/stop, per-memory approval, optional LLM re-run
5. **Privacy constraints**: No PII in logs, Level 2+ data encrypted
6. **Performance budgets**: <3s Whisper p95, <1s LLM p95, <5s end-to-end
7. **Modularity rules**: Perception → LLM → Memory, no circular dependencies
8. **Testing philosophy**: Stress failure modes, not just happy paths

**When asking questions**: You don't need to re-explain this context. Claude should reference it.

---

## Example Conversation Flow

### Effective Interaction

**User**: "Audio worker is dropping segments when queue >50. How should I implement backpressure?"

**Claude**: "Current queue has no size limit (unbounded growth = OOM risk). Options:

1. **Drop oldest** (FIFO):
   - Pro: Preserves recent context
   - Con: Loses conversation start
   - Failure mode: Silent data loss

2. **Drop newest** (reject at enqueue):
   - Pro: Clear error signal
   - Con: Misses real-time events
   - Failure mode: Visible in logs

3. **Batch processing**:
   - Pro: Increases throughput
   - Con: Increases latency
   - Failure mode: Larger memory footprint

Recommend: Option 2 (drop newest) + supervised learning log. Allows debugging why queue filled. Implementation:

```python
try:
    queue.put_nowait(event)
except Full:
    log_metric('audio_segment_dropped_queue_full', 1)
    save_to_supervised_folder('dropped_segments', event)
```

Then benchmark: Can you reduce Whisper latency enough to never hit queue limit?"

**User**: "Let's go with option 2. Write the implementation and chaos test."

**Claude**: [generates code with tests]

**User**: "Benchmark shows p95 latency increased 10%. Acceptable?"

**Claude**: "10% regression is at threshold. Check if it's noise (run benchmark 3x). If consistent, profile to find cause. If unavoidable, document in commit message: 'Accept 10% latency increase for queue overflow protection.'"

---

## Red Flags (Claude Should Immediately Warn)

- `except: pass` without logging
- Hardcoded paths (e.g., `/home/user/data`)
- Print statements in production code
- SQL string concatenation (injection risk)
- Storing plaintext biometrics
- No transaction for multi-step DB writes
- Promises of "5x faster" without benchmarks
- Ignoring hardware constraints ("just add more RAM")
- "It works on my machine" without reproducible setup

---

## Final Note

Claude is a tool, not a decision-maker. Use it to:

- **Explore design space**: "What are the trade-offs?"
- **Generate boilerplate**: "Write the benchmark harness"
- **Review rigor**: "Did I miss any failure modes?"
- **Explain concepts**: "How does Chroma's HNSW index work?"

But **you** decide:
- What's in scope for this POC
- What performance trade-offs are acceptable
- When to ship vs. keep polishing
- What risks to accept

This is your memory system. Own the architecture.

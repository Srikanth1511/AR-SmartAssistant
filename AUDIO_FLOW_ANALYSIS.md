# AR-SmartAssistant Audio Data Flow Analysis
## Complete Incompatibility Report

**Analysis Date:** 2025-11-19  
**Severity:** CRITICAL - Multiple incompatible handoffs, missing components, and data type mismatches

---

## EXECUTIVE SUMMARY

The audio pipeline has **CRITICAL FAILURES** at multiple handoff points:
1. **Syntax error** in Android AudioConfig (prevents compilation)
2. **No WebSocket server** implementation to receive Glass audio
3. **Incompatible data format conversions** (PCM 16-bit ↔ float32 ↔ normalized floats)
4. **Missing type conversions** throughout the pipeline
5. **Buffer size and sample rate inconsistencies**
6. **Database schema vs code mismatches** (methods don't exist)

---

## 1. GLASS APP → WEBSOCKET (Audio Capture)

### File: `/home/user/AR-SmartAssistant/glass-app/app/src/main/java/com/arsmartassistant/glass/service/AudioCaptureService.kt`
### File: `/home/user/AR-SmartAssistant/glass-app/app/src/main/java/com/arsmartassistant/glass/model/AudioConfig.kt`

#### Issue 1.1: SYNTAX ERROR - Compilation Failure
**Location:** `AudioConfig.kt:11`
```kotlin
val enableNoiseSuppress or: Boolean = true,  // ❌ SYNTAX ERROR
```
**Problem:** Field name contains invalid characters (`or`). This will prevent Kotlin compilation.
**Expected:** 
```kotlin
val enableNoiseSuppressor: Boolean = true,  // Matches Android naming convention
```
**Impact:** HIGH - Project won't compile

---

#### Issue 1.2: Audio Format Specification (Android Side)
**Location:** `AudioCaptureService.kt:89-95`
```kotlin
val minBufferSize = AudioRecord.getMinBufferSize(
    config.sampleRate,        // 16000 Hz
    channelConfig,            // MONO
    audioFormat               // PCM_16BIT
)
val bufferSize = maxOf(minBufferSize, config.bufferSizeBytes)  // 3200 bytes
```

**Actual Format at Capture:**
- **Sample Rate:** 16000 Hz
- **Encoding:** PCM_16BIT (2 bytes per sample, signed integer)
- **Channels:** MONO (1 channel)
- **Buffer Size:** 3200 bytes
- **Duration:** 200ms (3200 bytes ÷ 2 bytes/sample ÷ 16000 Hz = 0.1s)
- **Sample Count:** 1600 samples per buffer

**Audio Source:** `MediaRecorder.AudioSource.VOICE_RECOGNITION` (preprocessed by OS)
- Applied effects: NoiseSuppressor, AutomaticGainControl, AcousticEchoCanceler
- Effects operate on RAW PCM 16-bit samples

---

#### Issue 1.3: Data Type at Glass Capture
**Location:** `AudioCaptureService.kt:188-206`
```kotlin
private suspend fun captureAudio(record: AudioRecord) {
    val bufferSize = audioConfig.bufferSizeBytes
    val buffer = ByteArray(bufferSize)  // ❌ Raw bytes, not decoded
    
    while (serviceScope.isActive && _sessionState.value == SessionState.RECORDING) {
        val bytesRead = record.read(buffer, 0, buffer.size)
        if (bytesRead > 0) {
            webSocketClient?.sendAudioData(buffer.copyOf(bytesRead))
        }
    }
}
```

**What Gets Sent:**
- Raw **PCM 16-bit signed integer bytes** in **little-endian order** (Android standard)
- Each pair of bytes = 1 sample
- Example: `[0xFF, 0x7F, 0x00, 0x80, ...]`  = 16-bit values `[0x7FFF, 0x8000, ...]`
- Range: -32768 to +32767 (signed 16-bit)

**What Should Be Converted:**
- Normalize to float range [-1.0, 1.0]
- Formula: `sample_float = sample_int16 / 32768.0`

---

### Issue 1.4: WebSocket Transmission Format
**Location:** `WebSocketClient.kt:62-72`
```kotlin
fun sendAudioData(audioData: ByteArray) {
    if (isOpen) {
        try {
            send(audioData)  // ❌ Raw binary, no framing/metadata
        } catch (e: Exception) {
            Timber.e(e, "Failed to send audio data")
        }
    }
}
```

**Problem:** WebSocket frame contains:
- No metadata (timestamp, sample rate, encoding info)
- No synchronization markers
- No payload size indication
- Binary frame received by **unknown server implementation** (NOT PROVIDED)

**Issue 1.5: MISSING WEBSOCKET SERVER**
No server implementation found to receive Glass audio. This means:
- Audio data is sent to nowhere
- No receiver to handle the `audioData` ByteArray
- Configuration in `config.py` specifies WebSocket config but nothing implements it:
  ```python
  websocket: WebSocketConfig(
      enabled=True,      # ❌ Says enabled
      host="0.0.0.0",
      port=8765
  )
  ```

---

## 2. WEBSOCKET → PC RECEPTION (Missing Implementation)

### Issue 2.1: No WebSocket Server Found
**Expected Location:** Missing file - `ar_smart_assistant/perception/websocket_receiver.py` (or similar)

**What should exist:**
```python
# ❌ THIS FILE DOES NOT EXIST
class WebSocketAudioReceiver:
    """Receive audio from Glass via WebSocket"""
    def handle_binary_frame(self, audioData: bytes) -> AudioFrame:
        # Convert PCM 16-bit bytes to normalized floats
        # Reconstruct proper AudioFrame
```

**Actual Status:** 
- No WebSocket server implementation
- No PCM-to-float conversion code
- No synchronization/buffering logic
- Audio from Glass is LOST

---

## 3. MICROPHONE INPUT (PC Alternative)

### File: `/home/user/AR-SmartAssistant/ar_smart_assistant/perception/microphone.py`

#### Issue 3.1: Incorrect Chunk Size Calculation
**Location:** `microphone.py:43`
```python
self.chunk_size = config.buffer_size_bytes // 2  # 16-bit samples
# 3200 bytes // 2 = 1600 samples ✓ Correct calculation
```

**Format Created:**
- **Type:** `np.ndarray` with `dtype=np.float32`
- **Range:** Already normalized [-1.0, 1.0] by `sounddevice`
- **Shape:** 1D array of 1600 samples
- **Sample Rate:** 16000 Hz

---

#### Issue 3.2: Conversion from numpy to AudioFrame
**Location:** `microphone.py:50-69`
```python
def _audio_callback(self, indata: np.ndarray, frames: int, ...) -> None:
    samples = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
    
    frame = AudioFrame(
        timestamp=time.time(),
        samples=samples.tolist(),  # ❌ Converts numpy array to Python list
    )
```

**Problems:**
1. **Type Mismatch:** `AudioFrame.samples` is `Sequence[float]` but receives Python list
2. **No Length Check:** Don't verify 1600 samples present
3. **Timestamp Issue:** Uses `time.time()` (wall clock) not synchronized with samples

**Result Type:**
```
AudioFrame(
    timestamp=1700406123.456,
    samples=[0.123, 0.456, ..., -0.234]  # List of 1600 floats
)
```

---

#### Issue 3.3: Queue Management
**Location:** `microphone.py:45, 71-77`
```python
self.audio_queue: queue.Queue[AudioFrame | None] = queue.Queue()
# Default maxsize=0 → UNBOUNDED queue (memory leak risk)

try:
    self.audio_queue.put_nowait(frame)
except queue.Full:
    log_event("microphone_buffer_overflow", {...})
    # ❌ Never raised because queue is unbounded!
```

**Issue:** Queue has no maximum size, so `queue.Full` exception never occurs. 
Microphone buffers UNLIMITED audio in memory if consumer is slow.

---

## 4. AUDIO PIPELINE PROCESSING

### File: `/home/user/AR-SmartAssistant/ar_smart_assistant/perception/audio_pipeline.py`

#### Issue 4.1: AudioFrame Definition Mismatch
**Location:** `audio_pipeline.py:20-28`
```python
@dataclass
class AudioFrame:
    """PCM samples captured during ``frame_duration_ms``.
    
    The real implementation would store raw bytes. The proof-of-concept keeps the
    structure lightweight by using normalized floats for deterministic tests.
    """
    
    timestamp: float
    samples: Sequence[float]  # ❌ Python Sequence, not numpy array or bytes
```

**Issues:**
1. **Stores as Python Sequence** - Inefficient for audio processing (no vectorization)
2. **Inconsistent with Glass input** - Should handle PCM 16-bit bytes
3. **Comment admits limitation** - "POC keeps lightweight" suggests incomplete design
4. **No sample rate stored** - Frame lacks metadata

**Expected (for real implementation):**
```python
@dataclass
class AudioFrame:
    timestamp: float
    samples: np.ndarray  # dtype=float32, shape=(1600,) for 16kHz
    sample_rate_hz: int  # 16000
    channels: int  # 1
    encoding: str  # "PCM_16BIT" or "FLOAT32"
```

---

#### Issue 4.2: VAD Energy Calculation
**Location:** `audio_pipeline.py:71-75`
```python
@staticmethod
def _frame_energy(samples: Sequence[float]) -> float:
    if not samples:
        return -120
    return 20.0 * fmean(abs(sample) for sample in samples)
```

**Problems:**
1. **Energy formula incorrect for normalized floats**
   - Expected: `20 * log10(rms)` for dB, where rms = sqrt(mean(samples²))
   - Actual: `20 * mean(|samples|)` ← NOT dB-scale logarithm!
2. **No log10 call** - Returns linear, not decibel scale
3. **Inconsistent with config threshold**
   - Config: `energy_threshold_db: -45` (expects dB)
   - Code: Returns arbitrary linear value

**Impact:** VAD segmentation is unreliable - threshold comparison meaningless

**Example:**
```
If samples = [0.1, 0.2, 0.3, ...]
  Actual: _frame_energy() = 20 * mean([0.1, 0.2, 0.3, ...]) ≈ 4.0
  Expected dB: 20 * log10(rms) ≈ -40 dB
  Comparison: Is 4.0 > -45? ✓ YES (but mathematically nonsense)
```

---

#### Issue 4.3: MockAsrModel Input Mismatch
**Location:** `audio_pipeline.py:78-89`
```python
class MockAsrModel:
    def transcribe(self, segment: Sequence[AudioFrame]) -> tuple[str, float]:
        if not segment:
            return "", 0.0
        avg_energy = fmean(VadDetector._frame_energy(frame.samples) 
                          for frame in segment)
        # ❌ Uses broken _frame_energy() result
        
        words = ["hmm", "note", "remember", "buy", "call"]
        idx = min(int(max(avg_energy + 60, 0) // 5), len(words) - 1)
        # Magic number: +60 to offset wrong scale, then // 5 to select word
```

**Problem:** 
- Takes "broken" energy value (not actual dB)
- Adds magic offset (+60) to "fix" scale
- Uses integer division (`// 5`) to map to word list
- Result is deterministic but semantically meaningless

---

#### Issue 4.4: Audio Segment Storage Format
**Location:** `audio_pipeline.py:183-189`
```python
def _write_segment(self, session_id: int, index: int, 
                   segment: Sequence[AudioFrame]) -> Path:
    file_name = f"session{session_id}_{index}_{sanitize_identifier(str(index))}.txt"
    path = self.segment_root / file_name
    with path.open("w", encoding="utf-8") as handle:
        for frame in segment:
            handle.write(",".join(f"{sample:.4f}" for sample in frame.samples) + "\n")
    return path
```

**What Gets Stored:**
```
session42_0_0.txt:
0.1234,0.5678,0.9012,...   (1600 comma-separated floats)
0.2345,0.6789,0.1234,...
...
```

**Problems:**
1. **Text format instead of binary** - Huge disk space waste
2. **No metadata** - Can't reconstruct: sample rate, channel count, timestamp
3. **Lossy compression** - `.4f` truncates to 4 decimal places
4. **Uncompressed** - No compression (unlike real audio)

**Space Estimate:**
- Real PCM 16-bit: 1 second = 16000 × 2 bytes = 32 KB
- Text format: 1 second ≈ (1600 samples/frame) × (10 chars + comma) × frames = 200+ KB

---

## 5. SESSION RUNNER WORKFLOW

### File: `/home/user/AR-SmartAssistant/ar_smart_assistant/workflows/session_runner.py`

#### Issue 5.1: Frame Source Mismatch
**Location:** `session_runner.py:40-53`
```python
def run_session(self, frames: Iterable[AudioFrame]) -> dict[str, Sequence[int]]:
    session_id = self.database.start_session(...)
    transcripts = self.audio_pipeline.process_frames(session_id, frames)
    # ✓ Frames passed through
    
    actions = self.orchestrator.propose_actions(session_id)
    memory_ids = self.orchestrator.persist_memories(session_id, actions)
    # ✓ Basic flow correct
    
    self.database.update_session_status(session_id, "pending_review", end_time=utcnow())
    return {"session_id": session_id, "memory_ids": memory_ids}
```

**Issues:**
1. **No connection to WebSocket input** - `frames` must come from Glass OR microphone
2. **No audio validation** - Doesn't check frames are properly formatted
3. **No error handling** - Exceptions in pipeline bubble up uncaught
4. **Assumes frames exist** - If Glass WebSocket receiver missing, no frames available

**Expected Flow:**
```
Glass App
  ↓ (PCM 16-bit bytes via WebSocket) [MISSING]
PC WebSocket Server [NOT IMPLEMENTED]
  ↓ (AudioFrame with float samples)
SessionRunner.run_session()
```

---

## 6. LLM ORCHESTRATOR

### File: `/home/user/AR-SmartAssistant/ar_smart_assistant/llm/orchestrator.py`

#### Issue 6.1: Confidence Mapping Issue
**Location:** `orchestrator.py:43`
```python
confidence = min(payload.get("asr_confidence", 0.5), 
                 payload.get("speaker_confidence", 0.5))
```

**Problem:** Takes MINIMUM of two confidences, not average or weighted sum
- If ASR=0.9 and Speaker=0.5 → confidence=0.5 (too conservative)
- Better: `(asr_conf + speaker_conf) / 2` or weighted average

**Data Flow Issue:** Confidences stored in database:
```python
AudioPipeline (audio_pipeline.py:82-83):
  asr_confidence=0.5  # Hardcoded by MockAsrModel
  speaker_confidence=0.55  # Hardcoded by SpeakerIdentifier
  
LLMOrchestrator (orchestrator.py:43-47):
  Gets these from payload, uses minimum
  Stores in database (confidence_asr, confidence_speaker)
```

---

## 7. DATABASE SCHEMA VS CODE MISMATCH

### File: `/home/user/AR-SmartAssistant/ar_smart_assistant/database/repository.py`
### File: `/home/user/AR-SmartAssistant/ar_smart_assistant/ui/app.py`

#### Issue 7.1: Missing Database Methods
**Location:** `app.py:141, 150, 155, 158, 172, 181, 193`

Methods called in Flask app but **NOT IMPLEMENTED** in `BrainDatabase`:
```python
# app.py calls:
sessions = self.db.list_sessions(limit=50)          # ❌ NOT IN repository.py
session = self.db.get_session(session_id)           # ❌ NOT IN repository.py
events = self.db.get_raw_events(session_id)         # ❌ NOT IN repository.py
memories = self.db.get_memories(session_id)         # ❌ NOT IN repository.py
self.db.update_memory_approval(memory_id, ...)      # ❌ NOT IN repository.py
self.db.log_supervised_event(...)                   # ✓ EXISTS (line 340)
metrics = self.db.get_recent_metrics(window_sec=60) # ❌ NOT IN repository.py
```

**Actual Available Methods in BrainDatabase:**
```python
# repository.py (lines 146-395):
✓ register_model_version()
✓ start_session()
✓ update_session_status()
✓ update_memory_status()
✓ memory_status_summary()
✓ insert_raw_event()
✓ insert_audio_segment()
✓ attach_audio_segment_to_event()
✓ insert_memory_item()
✓ log_supervised_event()
✓ log_metric()
✓ get_session_events()       # ← Used by app.py
✓ list_memory_items()
```

**Impact:** 
- UI routes will crash at runtime with `AttributeError`
- Session listing disabled
- Memory approval flow broken

---

#### Issue 7.2: Raw Event Payload Storage Type
**Location:** `repository.py:211-227`
```python
def insert_raw_event(self, record: RawEventRecord) -> int:
    payload_json = json.dumps(record.payload, sort_keys=True)
    # Stores as JSON string ✓
    
@dataclass
class RawEventRecord:
    payload: Mapping[str, Any]  # ← Should match expected structure
```

**Expected Payload Structure (from audio_pipeline.py:145-151):**
```python
event_payload = {
    "speaker_id": "self",           # string
    "speaker_confidence": 0.85,     # float
    "transcript": "buy segment",    # string
    "asr_confidence": 0.7,          # float
    "audio_segment_id": 42,         # int
}
```

**Storage Issue:** 
- Stored as TEXT field in database (sqlite3)
- Retrieved as JSON string, must parse:
  ```python
  # get_session_events() (line 376-395):
  payload = json.loads(row["payload"])  # Converts back to dict
  ```
- Type-safe initially, but loses type info in DB

---

## 8. BUFFER SIZE AND TIMING CONSISTENCY

### Cross-System Analysis

```
┌─────────────────────────────────────────────────────┐
│ BUFFER SIZE TRACKING                                 │
├─────────────────────────────────────────────────────┤
│ Glass AudioConfig:                                   │
│   bufferSizeBytes = 3200                             │
│   sampleRate = 16000                                 │
│   Duration = 3200 / (16000 * 2) = 0.1s (100ms)     │
│   Samples = 3200 / 2 = 1600 samples                 │
│                                                       │
│ Microphone Chunk Size:                               │
│   chunk_size = 3200 // 2 = 1600 samples             │
│   Duration = 1600 / 16000 = 0.1s (100ms) ✓          │
│   Creates np.ndarray(1600,) ✓                        │
│                                                       │
│ AudioFrame:                                          │
│   samples: Sequence[float]                           │
│   ← From microphone: list of 1600 floats ✓           │
│   ← From Glass: NEVER SET (missing receiver)         │
│                                                       │
│ VAD Detector:                                        │
│   min_speech_frames = 10 (config default)            │
│   min_speech_duration_ms = 300 (config default)      │
│   Calculated: 300 / 30 = 10 frames ✓                │
│   At 100ms/frame: 10 frames = 1 second of data ✓     │
│                                                       │
│ Sample Rate Consistency:                             │
│   All: 16000 Hz ✓                                    │
│                                                       │
│ VAD Frame Duration:                                  │
│   frame_duration_ms = 30 (config)                    │
│   Actual frame duration = 100ms (from buffers)       │
│   MISMATCH: ❌ Config says 30ms, actual is 100ms     │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Issue 8.1: VAD Frame Duration Mismatch
**Location:** `config.py:337-359`
```python
"vad": {
    "frame_duration_ms": 30,  # ← Config says 30ms
    "min_speech_duration_ms": 300,
    "padding_duration_ms": 300,
}
```

**Actual Frame Duration:** 100ms (3200 bytes / (16000 Hz * 2 bytes/sample) = 0.1s)

**Calculation Error:**
```python
# audio_pipeline.py:120-122
vad_frames = config.audio.vad.min_speech_duration_ms // config.audio.vad.frame_duration_ms
           = 300 // 30 = 10 frames

# But actual buffer is 100ms, so:
# Real calculation should be: 300 // 100 = 3 frames
# Actual silence timeout = 10 * 100ms = 1000ms (not 300ms)
```

**Impact:** VAD timeout is 3.33x longer than expected (1000ms vs 300ms desired)

---

## 9. TYPE CONVERSION PIPELINE

### Issue 9.1: Complete Type Conversion Chain

```
┌─────────────────────────────────────────────────────────────┐
│ GLASS APP                                                    │
├─────────────────────────────────────────────────────────────┤
│ 1. Microphone Input                                          │
│    ↓ Type: PCM signed 16-bit (raw bytes from HAL)           │
│ 2. Android Effects (NSuppressor, AGC, AEC)                  │
│    ↓ Still Type: PCM signed 16-bit bytes                    │
│ 3. AudioRecord.read(buffer)                                 │
│    ↓ Type: byte[] (little-endian 16-bit signed ints)       │
│    [0xFF, 0x7F, ...] → [0x7FFF, 0x8000, ...]                │
│ 4. WebSocketClient.sendAudioData(ByteArray)                 │
│    ↓ Type: Binary WebSocket frame (MISSING RECEIVER!)       │
│                                                               │
│ ❌ CONVERSION MISSING: PCM 16-bit → float [-1.0, 1.0]      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↓↓↓ UNKNOWN PATH ↓↓↓ (NO SERVER)
         
┌─────────────────────────────────────────────────────────────┐
│ PC ALTERNATIVE (MICROPHONE)                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Sounddevice Stream                                       │
│    ↓ Type: np.ndarray[float32]                             │
│    Range: [-1.0, 1.0] (already normalized)                 │
│ 2. _audio_callback extracts channel                        │
│    ↓ Type: np.ndarray[float32], shape=(1600,)             │
│ 3. Convert to list for AudioFrame                          │
│    ↓ Type: list[float]                                     │
│ 4. Create AudioFrame                                        │
│    ↓ AudioFrame(timestamp=float, samples=list[float])      │
│                                                               │
│ ✓ CONVERSION OK: OSB float32 → Python list[float]          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↓↓↓ TO PIPELINE
         
┌─────────────────────────────────────────────────────────────┐
│ AUDIO PIPELINE                                               │
├─────────────────────────────────────────────────────────────┤
│ 1. AudioFrame input                                         │
│    ↓ Type: list[float], normalized [-1.0, 1.0]            │
│ 2. VAD Energy calculation (BROKEN FORMULA)                  │
│    ↓ Type: float (claimed dB, actually linear mean)         │
│ 3. MockAsrModel.transcribe()                                │
│    ↓ Input: Sequence[AudioFrame] (list of 3+ frames)       │
│    ↓ Type: tuple[str, float]  (transcript, confidence)      │
│ 4. Write to disk                                            │
│    ↓ Type: CSV text file (format string)                    │
│    session42_0_0.txt: "0.1234,0.5678,...\n"                │
│                                                               │
│ ❌ CONVERSION ISSUE: float → str (lossy, space-inefficient)│
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↓↓↓ TO DATABASE
         
┌─────────────────────────────────────────────────────────────┐
│ DATABASE STORAGE                                             │
├─────────────────────────────────────────────────────────────┤
│ 1. raw_events table                                         │
│    payload: JSON TEXT field                                 │
│    Stored: {"asr_confidence": 0.5, "speaker_confidence": ...}
│    ↓ Type: TEXT (serialized JSON)                           │
│ 2. audio_segments table                                     │
│    file_path: TEXT field                                    │
│    Stored: "path/to/session42_0_0.txt"                      │
│    ↓ Type: TEXT                                             │
│ 3. memory_items table                                       │
│    confidence_asr: REAL field                               │
│    confidence_speaker: REAL field                           │
│    confidence_llm: REAL field                               │
│    ↓ Type: REAL (float in SQLite)                           │
│    ✓ CORRECT                                                │
│                                                               │
│ ❌ MIXED STORAGE: Metadata JSON, Audio text file, Confidence SQL │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. MISSING TRANSFORMATIONS CHECKLIST

| Transformation | Location | Status | Impact |
|---|---|---|---|
| **PCM 16-bit → float [-1.0, 1.0]** | Glass to PC | ❌ MISSING | Audio unprocessable |
| **Add sample rate metadata** | AudioFrame | ❌ MISSING | Can't validate timing |
| **Proper dB calculation** | VAD energy | ❌ BROKEN | VAD unreliable |
| **Timestamp synchronization** | Microphone callback | ❌ WEAK | Timing uncertain |
| **Buffer size validation** | Pipeline input | ❌ MISSING | Silent failures |
| **Type checking** | Session runner | ❌ MISSING | Type errors possible |
| **Binary audio storage** | Audio segment | ❌ TEXT USED | Inefficient storage |
| **WebSocket frame parsing** | PC receiver | ❌ MISSING | No Glass input |
| **Error handling** | All handoffs | ⚠️ MINIMAL | Errors uncaught |
| **Metric logging** | Pipeline | ⚠️ PARTIAL | Some metrics missing |

---

## CRITICAL PATH FAILURES

### Path 1: Glass Audio Input (BROKEN)
```
Glass App
  ↓ PCM 16-bit bytes via WebSocket
PC WebSocket Server [❌ NOT IMPLEMENTED]
  ↓ Missing receiver, no type conversion
SessionRunner ❌ NO AUDIO INPUT
```

### Path 2: PC Microphone Input (WORKS but INEFFICIENT)
```
Microphone
  ↓ np.ndarray[float32]
Microphone._audio_callback()
  ↓ list[float]
AudioFrame ✓ Created correctly
  ↓
VAD.segment() ❌ Energy formula broken
  ↓
MockAsrModel ❌ Heuristic not meaningful
  ↓
Audio._write_segment() ❌ Text format, lossy
  ↓
Database ✓ Stored but inefficiently
```

---

## PRIORITY FIXES

### P0 (BLOCKING)
1. **Fix AudioConfig.kt syntax error** (line 11: `enableNoiseSuppress or` → `enableNoiseSuppressor`)
2. **Implement WebSocket server** to receive Glass audio (`websocket_receiver.py`)
3. **Implement PCM-to-float conversion** for Glass input
4. **Add missing DB methods** (`list_sessions`, `get_session`, `get_raw_events`, `get_memories`, `update_memory_approval`, `get_recent_metrics`)

### P1 (HIGH)
5. **Fix VAD energy formula** - Use proper dB calculation with log10
6. **Fix VAD frame duration mismatch** - Align config (30ms) with actual buffer (100ms)
7. **Implement binary audio storage** instead of text CSV
8. **Add AudioFrame metadata** (sample_rate, encoding, channels)

### P2 (MEDIUM)
9. **Implement proper error handling** in pipeline
10. **Add buffer size validation** at each handoff
11. **Fix microphone queue unbounded** - Set maxsize
12. **Improve timestamp synchronization** between microphone and frames

---

## FILES TO CREATE/MODIFY

```
CREATE:
  - ar_smart_assistant/perception/websocket_receiver.py
  - Tests for type conversions
  - Tests for WebSocket integration

MODIFY:
  - glass-app/app/src/main/java/com/arsmartassistant/glass/model/AudioConfig.kt
    (Fix syntax error on line 11)
  - ar_smart_assistant/perception/audio_pipeline.py
    (Fix VAD energy formula, add metadata to AudioFrame)
  - ar_smart_assistant/perception/microphone.py
    (Fix queue size, improve timestamps)
  - ar_smart_assistant/database/repository.py
    (Add missing methods for UI)
  - ar_smart_assistant/config.py
    (Fix VAD frame duration mismatch: 30ms → 100ms OR buffer size change)
  - ar_smart_assistant/ui/app.py
    (Call correct DB methods when they're implemented)
```

---

## VERIFICATION TESTS

```python
# Test 1: PCM conversion
def test_pcm16_to_float_conversion():
    pcm_bytes = b'\x00\x00\xff\x7f'  # [0, 32767]
    floats = convert_pcm16_to_float(pcm_bytes)
    assert floats[0] == 0.0
    assert abs(floats[1] - 1.0) < 0.001

# Test 2: AudioFrame structure
def test_audioframe_has_required_metadata():
    frame = AudioFrame(samples=[], timestamp=0)
    assert hasattr(frame, 'sample_rate')
    assert hasattr(frame, 'encoding')

# Test 3: VAD energy in dB
def test_vad_energy_calculation():
    # For normalized float 0.5, energy should be ~-6dB
    samples = [0.5, 0.5, 0.5]
    energy = _frame_energy(samples)
    assert -7 < energy < -5, f"Expected ~-6dB, got {energy}"

# Test 4: DB methods exist
def test_database_has_required_methods():
    assert hasattr(BrainDatabase, 'list_sessions')
    assert hasattr(BrainDatabase, 'get_session')
    assert hasattr(BrainDatabase, 'get_raw_events')
    # ... more methods

# Test 5: WebSocket server accepts audio
def test_websocket_receives_binary_frames():
    # Mock client sending PCM bytes
    # Server should create AudioFrame with floats
    pass
```

---

## SUMMARY TABLE

| Component | Format | Size | Issues | Severity |
|---|---|---|---|---|
| Glass Capture | PCM 16-bit | 3200 B/frame | Syntax error in config | P0 |
| WebSocket TX | Binary | Variable | No metadata | P0 |
| WebSocket RX | - | - | ❌ NOT IMPLEMENTED | P0 |
| PC Microphone | float32 | 1600 samples | Works | ✓ |
| AudioFrame | list[float] | 1600 items | Missing metadata | P1 |
| VAD | Energy value | 1 float | Wrong formula | P1 |
| ASR Mock | String | Variable | Heuristic only | ✓ |
| Audio Storage | CSV text | 200+ KB/s | Lossy, inefficient | P2 |
| Database | JSON + SQL | Variable | Missing methods | P0 |


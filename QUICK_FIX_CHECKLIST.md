# Audio Flow Incompatibilities - Quick Fix Checklist

## P0: CRITICAL (Blocking)

### [ ] 1. Fix AudioConfig.kt Compilation Error
**File:** `glass-app/app/src/main/java/com/arsmartassistant/glass/model/AudioConfig.kt`  
**Line:** 11  
**Current:**
```kotlin
val enableNoiseSuppress or: Boolean = true,
```
**Fix:**
```kotlin
val enableNoiseSuppressor: Boolean = true,
```
**Verification:** Gradle build should succeed without syntax errors

---

### [ ] 2. Create WebSocket Server for Glass Audio
**Create:** `ar_smart_assistant/perception/websocket_receiver.py`

**Needs:**
```python
class WebSocketAudioReceiver:
    # Listen on ws://0.0.0.0:8765
    # Handle binary frames (PCM 16-bit bytes)
    # Convert to AudioFrame with metadata
    # Forward to audio pipeline
```

**Key Functions:**
- `convert_pcm16_to_float32(bytes) -> np.ndarray` - Scale [-32768..32767] to [-1.0..1.0]
- `frame_from_pcm(pcm_bytes, timestamp) -> AudioFrame` - Create AudioFrame with metadata
- `WebSocketAudioReceiver.start()` - Listen for Glass connections
- `WebSocketAudioReceiver.on_binary_message(data)` - Handle audio frames

**Verification:** 
- Test with mock Glass app sending PCM data
- Verify audio frames have timestamp, sample_rate, channels

---

### [ ] 3. Add Missing Database Methods
**File:** `ar_smart_assistant/database/repository.py`

**Add to BrainDatabase class:**

```python
def list_sessions(self, limit: int = 50) -> list[Dict[str, Any]]:
    """List recent sessions with basic info"""
    # SELECT id, start_time, status, (SELECT COUNT(*) FROM memory_items) as memory_count
    # ORDER BY start_time DESC LIMIT ?

def get_session(self, session_id: int) -> Dict[str, Any] | None:
    """Get session details"""
    # SELECT * FROM sessions WHERE id = ?

def get_raw_events(self, session_id: int) -> list[Dict[str, Any]]:
    """Get all raw events for session"""
    # SELECT id, event_type, timestamp, payload FROM raw_events WHERE session_id = ?

def get_memories(self, session_id: int) -> list[Dict[str, Any]]:
    """Get all memory items for session"""
    # SELECT * FROM memory_items WHERE session_id = ? ORDER BY timestamp

def update_memory_approval(self, memory_id: int, approval_status: str, reason: str | None) -> None:
    """Update memory approval status (replaces update_memory_status)"""
    # UPDATE memory_items SET approval_status = ?, rejection_reason = ?, reviewed_at = ? WHERE id = ?

def get_recent_metrics(self, window_sec: int = 60) -> list[Dict[str, Any]]:
    """Get metrics from last N seconds"""
    # SELECT * FROM system_metrics WHERE timestamp > datetime('now', '-' || ? || ' seconds')
```

**Verification:**
- UI routes should not throw AttributeError
- Can list sessions
- Can approve/reject memories

---

## P1: HIGH PRIORITY

### [ ] 4. Fix VAD Energy Formula
**File:** `ar_smart_assistant/perception/audio_pipeline.py`

**Current (Line 71-75):**
```python
def _frame_energy(samples: Sequence[float]) -> float:
    if not samples:
        return -120
    return 20.0 * fmean(abs(sample) for sample in samples)
```

**Fix:**
```python
import math

def _frame_energy(samples: Sequence[float]) -> float:
    """Calculate energy in dB (proper formula)"""
    if not samples:
        return -120
    
    # RMS (root mean square)
    rms = math.sqrt(fmean(s**2 for s in samples))
    
    # Avoid log(0) for silent audio
    if rms < 1e-10:
        return -120
    
    # Convert to dB: 20 * log10(rms / reference)
    # With reference = 1.0 for normalized float
    return 20.0 * math.log10(rms)
```

**Expected Results:**
- Silence (-1e-10 to 1e-10): -120 dB
- Sample 0.1: ~-20 dB
- Sample 0.5: ~-6 dB
- Sample 1.0: 0 dB
- Matches config threshold -45 dB ✓

**Verification:**
- Test with known sample values
- VAD segmentation should be more reliable
- Threshold -45dB should trigger for moderate speech

---

### [ ] 5. Fix VAD Frame Duration Mismatch
**File:** `ar_smart_assistant/config.py`

**Issue:** Buffer is 100ms but config says 30ms

**Option A - Update Config (Recommended):**
```python
"vad": {
    "type": "energy_based",
    "energy_threshold_db": -45,
    "frame_duration_ms": 100,  # ← Changed from 30
    "min_speech_duration_ms": 300,
    "padding_duration_ms": 300,
}
```

**Option B - Update Buffer Size:**
```python
"audio": {
    "capture": {
        "sample_rate_hz": 16000,
        "buffer_size_bytes": 960,  # ← Changed from 3200 to get ~30ms
        # 960 / (16000 * 2) = 0.03s = 30ms
```

**Option C - Update Pipeline Logic:**
```python
# audio_pipeline.py line 120-122
vad_frames = config.audio.vad.min_speech_duration_ms // config.audio.vad.frame_duration_ms

# Check actual buffer size
actual_frame_duration = (config.audio.capture.buffer_size_bytes / 2) / config.audio.capture.sample_rate_hz * 1000
vad_frames = config.audio.vad.min_speech_duration_ms // max(config.audio.vad.frame_duration_ms, int(actual_frame_duration))
```

**Verification:**
- VAD timeout = ~300-400ms (intended: 300ms with 300ms padding)
- Not 1000ms+ like currently

---

### [ ] 6. Convert Audio Storage to Binary
**File:** `ar_smart_assistant/perception/audio_pipeline.py`

**Current (Line 183-189) - Text CSV:**
```python
def _write_segment(self, session_id: int, index: int, segment: Sequence[AudioFrame]) -> Path:
    file_name = f"session{session_id}_{index}_{sanitize_identifier(str(index))}.txt"
    # ...writes CSV text
```

**Fix to Binary WAV:**
```python
import wave
import struct

def _write_segment(self, session_id: int, index: int, segment: Sequence[AudioFrame]) -> Path:
    file_name = f"session{session_id}_{index}_{sanitize_identifier(str(index))}.wav"
    path = self.segment_root / file_name
    
    if not segment:
        return path
    
    # Collect all samples
    all_samples = []
    for frame in segment:
        all_samples.extend(frame.samples)
    
    # Write WAV file
    with wave.open(str(path), 'wb') as wav_file:
        # Parameters: channels=1, sample_width=2 (16-bit), framerate=16000
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)
        
        # Convert float [-1.0..1.0] back to int16
        int_samples = [
            int(s * 32767) if s > 0 else int(s * 32768)
            for s in all_samples
        ]
        wav_file.writeframes(
            b''.join(struct.pack('<h', s) for s in int_samples)
        )
    
    return path
```

**Benefits:**
- 7x smaller file size (200KB → 30KB for 1 second)
- Standard format (WAV can be played/analyzed)
- No precision loss vs CSV
- No metadata loss

**Verification:**
- Files are actually WAV format
- Can be opened in any audio editor
- File sizes ~32KB per second

---

### [ ] 7. Add Metadata to AudioFrame
**File:** `ar_smart_assistant/perception/audio_pipeline.py`

**Current:**
```python
@dataclass
class AudioFrame:
    timestamp: float
    samples: Sequence[float]
```

**Fix:**
```python
@dataclass
class AudioFrame:
    timestamp: float
    samples: Sequence[float]
    sample_rate_hz: int = 16000
    channels: int = 1
    encoding: str = "FLOAT32"  # or "PCM_16BIT"
```

**Update Creation Points:**
- `microphone.py` line 66-69: Add metadata
- `websocket_receiver.py` (new file): Add metadata
- Tests in `test_workflow.py`: Update frame creation

**Verification:**
- All AudioFrames have sample_rate
- Pipeline validates sample_rate matches expected (16000)

---

## P2: MEDIUM PRIORITY

### [ ] 8. Fix Microphone Queue Memory Leak
**File:** `ar_smart_assistant/perception/microphone.py`

**Current (Line 45):**
```python
self.audio_queue: queue.Queue[AudioFrame | None] = queue.Queue()
```

**Fix:**
```python
# Bounded queue: max 10 frames (1 second of audio)
self.audio_queue: queue.Queue[AudioFrame | None] = queue.Queue(maxsize=10)
```

**Verification:**
- `queue.Full` exception is raised if consumer slow
- Not more than 1 second buffered in memory
- Logs warning when overflow detected

---

### [ ] 9. Improve Timestamp Synchronization
**File:** `ar_smart_assistant/perception/microphone.py`

**Current (Line 65):**
```python
frame = AudioFrame(
    timestamp=time.time(),
    samples=samples.tolist(),
)
```

**Better:**
```python
# Use time_info from callback (more accurate)
frame = AudioFrame(
    timestamp=time_info.currentTime,  # sounddevice provides this
    samples=samples.tolist(),
    sample_rate_hz=16000,
    channels=1,
)
```

**Verification:**
- Timestamps match actual sample times
- No gaps or overlaps in audio timeline

---

### [ ] 10. Implement Error Handling
**File:** `ar_smart_assistant/workflows/session_runner.py`

**Current:**
```python
def run_session(self, frames: Iterable[AudioFrame]) -> dict:
    # Direct execution, no error handling
```

**Add:**
```python
def run_session(self, frames: Iterable[AudioFrame]) -> dict[str, Any]:
    try:
        # Validate frames
        frames_list = list(frames)
        if not frames_list:
            raise ValueError("No audio frames provided")
        
        # Check frame format
        for i, frame in enumerate(frames_list):
            if not hasattr(frame, 'samples'):
                raise TypeError(f"Frame {i} missing samples attribute")
            if not hasattr(frame, 'sample_rate_hz'):
                raise TypeError(f"Frame {i} missing sample_rate_hz")
            if frame.sample_rate_hz != 16000:
                raise ValueError(f"Frame {i} has wrong sample rate: {frame.sample_rate_hz}")
        
        # Run pipeline
        session_id = self.database.start_session(...)
        try:
            transcripts = self.audio_pipeline.process_frames(session_id, frames_list)
            # ...rest of flow
        except Exception as e:
            self.database.update_session_status(session_id, "failed", notes=str(e))
            raise
            
    except Exception as e:
        log_event("session_runner_error", {
            "error": str(e),
            "type": type(e).__name__
        })
        raise
```

**Verification:**
- Meaningful errors instead of silent failures
- Sessions marked as "failed" if pipeline crashes
- Errors logged with context

---

## Testing Checklist

### [ ] Unit Tests
```python
# Test PCM conversion
test_pcm16_to_float_conversion()

# Test VAD energy formula
test_vad_energy_calculation()

# Test AudioFrame creation
test_audioframe_with_metadata()

# Test buffer size consistency
test_buffer_sizes_match()

# Test database methods exist
test_database_methods_exist()

# Test WebSocket reception
test_websocket_receives_pcm()
```

### [ ] Integration Tests
```python
# Test Glass → WebSocket → PC flow
test_glass_audio_to_database()

# Test PC microphone → database flow
test_microphone_audio_to_database()

# Test error handling
test_invalid_audio_frames_raise()
test_missing_fields_detected()

# Test UI routes work
test_ui_list_sessions()
test_ui_get_session()
test_ui_approve_memory()
```

### [ ] Manual Testing
- [ ] Glass app compiles without errors
- [ ] WebSocket receives audio from Glass
- [ ] PC microphone creates frames correctly
- [ ] VAD segments speech accurately
- [ ] Audio stored as WAV files
- [ ] UI lists sessions and memories
- [ ] Can approve/reject memories
- [ ] Database has correct data types

---

## Success Criteria

| Criteria | Current | Target |
|---|---|---|
| Kotlin compilation | ❌ Fails | ✓ Succeeds |
| Glass audio → PC | ❌ Lost | ✓ Received |
| Audio format | ❌ Mismatched | ✓ Consistent 16kHz PCM |
| VAD accuracy | ❌ Broken | ✓ ~300ms timeout |
| Storage efficiency | ❌ 200+ KB/s | ✓ 32 KB/s |
| UI functionality | ❌ Crashes | ✓ Lists/approves |
| Type safety | ⚠️ Partial | ✓ Full validation |
| Error handling | ❌ Silent fails | ✓ Logged errors |


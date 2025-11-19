# AR-SmartAssistant Audio Data Flow Analysis
## Complete Review of Audio Pipeline Incompatibilities

**Status:** CRITICAL ISSUES IDENTIFIED  
**Analysis Date:** 2025-11-19  
**Reviewer:** Claude Code Audio Flow Specialist

---

## Overview

This analysis traces the complete audio data flow from Glass microphone → WebSocket → PC → ASR → LLM → Database, identifying **12 critical incompatibilities** across the pipeline.

### Key Findings Summary

| Issue | Severity | Impact | Files Affected |
|-------|----------|--------|-----------------|
| Kotlin syntax error (AudioConfig.kt:11) | P0 | Project won't compile | glass-app/ |
| Missing WebSocket server implementation | P0 | Glass audio is lost | ar_smart_assistant/perception/ |
| Missing PCM→float conversion | P0 | Audio unprocessable | Both platforms |
| Missing database methods | P0 | UI crashes at runtime | ar_smart_assistant/database/ |
| Broken VAD energy formula | P1 | VAD unreliable | audio_pipeline.py |
| Frame duration mismatch (30ms vs 100ms) | P1 | VAD timeout 3.3x off | config.py |
| Inefficient audio storage (text CSV) | P1 | 7x space waste | audio_pipeline.py |
| Missing AudioFrame metadata | P1 | Type safety issues | audio_pipeline.py |
| Unbounded microphone queue | P2 | Memory leak risk | microphone.py |
| Mock ASR magic numbers | P2 | Heuristic unreliable | audio_pipeline.py |
| Weak timestamp sync | P2 | Timing uncertainty | microphone.py |
| Minimal error handling | P2 | Silent failures | Multiple |

---

## Documentation Files

### 1. **AUDIO_FLOW_ANALYSIS.md** (30 KB)
Comprehensive technical analysis covering:
- Glass App audio capture (PCM 16-bit, 16kHz, 3200 bytes/buffer)
- WebSocket transmission and missing server implementation
- Microphone input (numpy float32 → AudioFrame conversion)
- Audio pipeline processing (VAD, ASR, storage)
- Session runner workflow
- LLM orchestrator
- Database schema vs code mismatches
- Complete type conversion pipeline
- Missing transformations checklist
- Critical path failures
- Priority fixes (P0, P1, P2)

**Read this for:** Deep dive into each incompatibility with code examples

---

### 2. **AUDIO_FLOW_DIAGRAM.txt** (34 KB)
Visual representation including:
- Complete ASCII flow diagram from Glass → Database
- All handoff points marked with issues
- Data type transformations at each stage
- Critical issues summary (P0, P1, P2)
- Data type flow table
- Buffer size verification
- File modification priority

**Read this for:** Understanding the complete pipeline visually

---

### 3. **QUICK_FIX_CHECKLIST.md** (12 KB)
Actionable fix guide with:
- P0 fixes (Blocking - fix first)
  - AudioConfig.kt syntax error
  - WebSocket server implementation
  - Missing DB methods
- P1 fixes (High priority)
  - VAD energy formula
  - Frame duration mismatch
  - Audio storage format
  - AudioFrame metadata
- P2 fixes (Medium priority)
  - Memory leak fix
  - Timestamp sync
  - Error handling
- Testing checklist
- Success criteria

**Read this for:** Step-by-step instructions to fix each issue

---

## Critical Issues at a Glance

### BLOCKING (P0) - Fix Before Anything Else

```
1. AudioConfig.kt Line 11: SYNTAX ERROR
   enableNoiseSuppress or: Boolean  ← INVALID
   ↓
   enableNoiseSuppressor: Boolean   ← CORRECT
   
   Status: Project won't compile

2. WebSocket Server: NOT IMPLEMENTED
   Glass sends PCM bytes to ws://PC:8765
   No server listening → Audio is LOST
   
   Status: Audio from Glass completely lost

3. PCM 16-bit → float conversion: MISSING
   Glass sends: [-32768...32767] (16-bit)
   Code expects: [-1.0...1.0] (float32)
   No conversion code exists
   
   Status: Incompatible data types

4. Database Methods: 6 MISSING
   app.py calls:
     - list_sessions() ❌
     - get_session() ❌
     - get_raw_events() ❌
     - get_memories() ❌
     - update_memory_approval() ❌
     - get_recent_metrics() ❌
   
   Status: UI crashes with AttributeError
```

### HIGH PRIORITY (P1) - Fix After P0

```
5. VAD Energy Formula: BROKEN
   Config: energy_threshold_db = -45
   Code: return 20.0 * mean(|x|)  ← linear, not dB!
   Should: return 20.0 * log10(rms)  ← proper dB
   
   Status: Comparing mismatched scales

6. VAD Frame Duration: MISMATCH
   Config: frame_duration_ms = 30
   Actual: 100ms (3200 bytes / 16000 Hz / 2)
   Result: VAD timeout 3.3x longer than intended
   
   Status: Speech detection unreliable

7. Audio Storage: INEFFICIENT
   Current: CSV text file (0.1234,0.5678,...)
   Better: WAV binary file
   Space: 200+ KB/s vs 32 KB/s (6-7x waste)
   
   Status: Disk space and loading time bloat

8. AudioFrame: MISSING METADATA
   Has: timestamp, samples
   Needs: sample_rate_hz, encoding, channels
   
   Status: Can't validate audio format consistency
```

---

## Audio Data Flow Path

```
GLASS APP (Android)
    ↓ Microphone capture (PCM 16-bit, 16kHz)
    ↓ Audio preprocessing (NSuppressor, AGC, AEC)
    ↓ Buffer collection (3200 bytes = 100ms)
    ↓ WebSocket transmission (byte[])
    
    FORK 1: WebSocket Server ❌ NOT IMPLEMENTED
            (Audio is lost)
    
    FORK 2: PC Microphone (numpy.sounddevice)
            ↓ float32 stream (16kHz, normalized)
            ↓ _audio_callback() converts to list[float]
            ↓ AudioFrame created (timestamp, samples)
            
                ↓ Audio Pipeline
                ↓ VAD Detector (broken energy formula)
                ↓ MockAsrModel (heuristic ASR)
                ↓ _write_segment() (text CSV storage ❌)
                
                    ↓ Database Insert
                    ↓ Raw Events (JSON payload)
                    ↓ Audio Segments (file path)
                    ↓ Memory Items (confidences)
                    
                        ↓ LLM Orchestrator
                        ↓ Propose Actions
                        ↓ Persist Memories
                        
                            ↓ UI Routes (6 missing methods)
                            ↓ Flask Debug Interface ❌ CRASHES
```

---

## Critical Path Failures

### Path 1: Glass Audio (COMPLETELY BROKEN)
```
Glass sends PCM bytes → WebSocket server NOT FOUND → Audio LOST
Fix required: Implement websocket_receiver.py with PCM→float conversion
```

### Path 2: PC Microphone (WORKS but INEFFICIENT)
```
Microphone → numpy float32 → AudioFrame → VAD (broken) → ASR (mock) 
→ CSV storage (wasteful) → Database → UI (crashes)
Fix required: VAD formula, storage format, UI methods
```

---

## Impact Assessment

### Functional Impact
- ❌ Glass audio input completely non-functional
- ✓ PC microphone input partially working
- ❌ Audio storage format inefficient (7x space waste)
- ❌ VAD segmentation unreliable (wrong formula)
- ❌ UI completely broken (missing methods)

### Performance Impact
- Audio storage: 200+ KB/s vs optimal 32 KB/s (6-7x overhead)
- Memory: Unbounded queue can consume unlimited RAM
- Timing: VAD timeout 3.3x longer than intended

### Data Quality Impact
- Audio not properly normalized (type mismatches)
- VAD using wrong scale (linear vs dB)
- VAD frame duration not matching actual buffers
- Metadata missing (sample rate, encoding)

---

## Recommended Fix Order

### Phase 1: CRITICAL (Make it work)
1. Fix AudioConfig.kt syntax error (5 min)
2. Implement WebSocket server with PCM conversion (2-3 hours)
3. Add missing database methods (1-2 hours)

### Phase 2: HIGH (Make it right)
4. Fix VAD energy formula (30 min)
5. Fix frame duration mismatch (30 min)
6. Add AudioFrame metadata (1 hour)
7. Convert audio storage to WAV (1-2 hours)

### Phase 3: POLISH (Make it robust)
8. Fix microphone queue memory leak (15 min)
9. Improve timestamp synchronization (30 min)
10. Add comprehensive error handling (1-2 hours)
11. Add validation at handoff points (1-2 hours)

**Total Estimated Effort:** 10-15 hours

---

## Testing Strategy

### Unit Tests (Quick wins)
```python
test_pcm16_to_float_conversion()       # Verify PCM→float
test_vad_energy_calculation()           # Verify dB formula
test_audioframe_with_metadata()         # Verify structure
test_buffer_sizes_match()               # Verify consistency
test_database_methods_exist()           # Verify methods
```

### Integration Tests (End-to-end)
```python
test_glass_audio_to_database()          # Full Glass path
test_microphone_audio_to_database()     # Full microphone path
test_invalid_audio_frames_raise()       # Error handling
test_ui_list_sessions()                 # UI functionality
```

### Manual Testing (Real-world)
- Glass app compiles and runs
- WebSocket receives audio from Glass
- PC microphone captures audio correctly
- VAD segments speech with proper timeout
- Audio stored as playable WAV files
- UI lists sessions and allows approvals

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Kotlin compilation | ❌ Fails | ✓ Succeeds |
| Glass audio reception | ❌ None | ✓ Received & processed |
| Audio format consistency | ❌ Mismatched | ✓ 16kHz PCM throughout |
| VAD accuracy | ❌ Broken formula | ✓ ~300ms timeout |
| Storage efficiency | ❌ 200+ KB/s | ✓ ~32 KB/s |
| UI functionality | ❌ Crashes | ✓ Lists/approves/rejects |
| Type safety | ⚠️ Partial | ✓ Full validation |
| Error handling | ❌ Silent fails | ✓ Logged with context |

---

## References

### Key Code Locations
- **Android:** `glass-app/app/src/main/java/com/arsmartassistant/glass/`
- **Python Perception:** `ar_smart_assistant/perception/`
- **Database:** `ar_smart_assistant/database/repository.py`
- **UI:** `ar_smart_assistant/ui/app.py`
- **Config:** `ar_smart_assistant/config.py`

### Audio Specifications
- Sample Rate: 16000 Hz (16 kHz)
- Channels: 1 (MONO)
- Encoding: PCM 16-bit signed (Glass) → float32 [-1.0, 1.0] (PC)
- Buffer: 3200 bytes = 1600 samples = 100ms
- Effects: Noise Suppression, AGC, AEC (Glass only)

### Configuration
- WebSocket: `ws://0.0.0.0:8765`
- VAD Threshold: -45 dB
- Min Speech: 300ms
- Padding: 300ms
- Frame Duration: 30ms (config) ⚠️ 100ms (actual)

---

## Next Steps

1. **Read QUICK_FIX_CHECKLIST.md** for actionable steps
2. **Review AUDIO_FLOW_ANALYSIS.md** for technical deep dives
3. **Consult AUDIO_FLOW_DIAGRAM.txt** when implementing fixes
4. **Start with P0 fixes** (critical blocking issues)
5. **Test after each phase** with provided test cases
6. **Verify success criteria** before moving to next phase

---

## Contact & Questions

For clarifications on:
- **Audio formats:** See AUDIO_FLOW_ANALYSIS.md §1, §3
- **Data types:** See AUDIO_FLOW_ANALYSIS.md §9, AUDIO_FLOW_DIAGRAM.txt
- **Fixes:** See QUICK_FIX_CHECKLIST.md with code examples
- **Database:** See AUDIO_FLOW_ANALYSIS.md §7

All critical issues have been documented with:
- File location and line numbers
- Current (broken) code
- Expected (correct) code
- Impact assessment
- Verification steps


# AR-SmartAssistant Testing Checklist

**Purpose:** Verify all P0 blocking issues are fixed and the complete Glass-to-PC audio pipeline works end-to-end.

**Date:** 2025-11-19
**Branch:** `claude/cross-platform-setup-01TavfMfMAj3YeHHWfLqxnEt`

---

## ✅ Pre-Test Setup

### 1. Install Dependencies
```bash
# Install Python dependencies
pip install -e .

# Verify critical packages
python -c "import websockets; print('✓ websockets')"
python -c "import flask; print('✓ flask')"
python -c "import numpy; print('✓ numpy')"
```

**Expected:** All imports succeed without errors

---

### 2. Create Configuration File
```bash
# Copy example config
cp config.yaml.example config.yaml

# Edit for testing
nano config.yaml
```

**Required Settings:**
```yaml
audio:
  input_source: "microphone"  # Start with PC mic for initial test
  capture:
    sample_rate_hz: 16000
    encoding: "PCM_16BIT"
    channel: "MONO"
    buffer_size_bytes: 3200

websocket:
  enabled: true  # Enable for Glass testing
  host: "0.0.0.0"
  port: 8765

debug_ui:
  enabled: true
  host: "127.0.0.1"
  port: 5000
  auto_open_browser: true

storage:
  root: "./data"
```

**Expected:** Config file created successfully

---

### 3. Initialize Database
```bash
# Run setup script
./setup.sh

# Verify databases exist
ls -lh data/*.db
```

**Expected:**
- `data/brain_main.db` created
- `data/system_metrics.db` created
- No schema errors in output

---

## 🧪 Test 1: PC Microphone Mode (Local Audio)

**Goal:** Verify local microphone input works without Glass

### 1.1 Start UI Server
```bash
./run_ui.sh
```

**Expected Output:**
```
============================================================
AR-SmartAssistant Debug UI
============================================================
Server: http://127.0.0.1:5000
Storage: ./data
Audio Input: microphone
WebSocket: ws://0.0.0.0:8765
============================================================
```

**Check:**
- [ ] Server starts without errors
- [ ] Browser opens to http://localhost:5000
- [ ] WebSocket server starts (shown in output)
- [ ] No Python exceptions in console

---

### 1.2 Test Database Methods (API Calls)
```bash
# In another terminal, test API endpoints
curl http://localhost:5000/api/status | jq .
```

**Expected Response:**
```json
{
  "is_recording": false,
  "current_session_id": null,
  "storage_root": "./data",
  "input_source": "microphone",
  "websocket_enabled": true,
  "websocket_connected": false
}
```

**Check:**
- [ ] `/api/status` returns valid JSON
- [ ] `input_source` is "microphone"
- [ ] `websocket_enabled` is true
- [ ] No 500 errors

---

### 1.3 Test Session List (Database Method)
```bash
curl http://localhost:5000/api/sessions | jq .
```

**Expected Response:**
```json
{
  "sessions": []
}
```

**Check:**
- [ ] `/api/sessions` works (tests `list_sessions()` method)
- [ ] Returns empty array (no sessions yet)
- [ ] No AttributeError exceptions

---

### 1.4 Test Metrics Endpoint (Database Method)
```bash
curl http://localhost:5000/api/metrics/live | jq .
```

**Expected Response:**
```json
{
  "metrics": []
}
```

**Check:**
- [ ] `/api/metrics/live` works (tests `get_recent_metrics()` method)
- [ ] Returns empty array (no metrics yet)
- [ ] No AttributeError exceptions

---

### 1.5 Start Recording Session
**In Browser:**
1. Click "Start Session" button
2. Allow microphone access when prompted
3. Speak clearly: "Testing microphone input. One, two, three."
4. Wait 10 seconds
5. Click "Stop Session"

**Expected:**
- [ ] Session starts without errors
- [ ] Microphone indicator shows recording
- [ ] Console shows VAD activity
- [ ] Session stops cleanly

**Check API:**
```bash
curl http://localhost:5000/api/sessions | jq '.sessions[0]'
```

**Expected:**
- [ ] Session created in database
- [ ] Session has `id`, `start_time`, `status`
- [ ] `model_version_id` is set

---

## 🔌 Test 2: WebSocket Server (Glass Connectivity)

**Goal:** Verify WebSocket server accepts connections and receives PCM data

### 2.1 Switch to WebSocket Mode
**Edit config.yaml:**
```yaml
audio:
  input_source: "websocket"  # Change to websocket
```

**Restart server:**
```bash
# Ctrl+C to stop
./run_ui.sh
```

**Expected Output:**
```
Audio Input: websocket
WebSocket: ws://0.0.0.0:8765
WebSocket server started on 0.0.0.0:8765
```

**Check:**
- [ ] Server restarts successfully
- [ ] Input source shows "websocket"
- [ ] WebSocket server listening on port 8765

---

### 2.2 Test WebSocket Connection (Simulated Client)
**Create test script: `test_websocket_client.py`**
```python
#!/usr/bin/env python3
import asyncio
import websockets
import struct
import numpy as np

async def test_connection():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as websocket:
        print("✓ Connected!")

        # Generate test PCM audio (1 second of 440 Hz tone)
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0

        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * frequency * t)
        audio = (audio * 32767).astype(np.int16)

        # Send in 100ms chunks (1600 samples = 3200 bytes)
        chunk_size = 1600
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            pcm_bytes = struct.pack(f'<{len(chunk)}h', *chunk)
            await websocket.send(pcm_bytes)
            print(f"Sent {len(pcm_bytes)} bytes")
            await asyncio.sleep(0.1)

        print("✓ Test audio sent successfully!")

if __name__ == "__main__":
    asyncio.run(test_connection())
```

**Run test:**
```bash
python test_websocket_client.py
```

**Expected Output:**
```
Connecting to ws://localhost:8765...
✓ Connected!
Sent 3200 bytes
Sent 3200 bytes
...
✓ Test audio sent successfully!
```

**Check Server Logs:**
- [ ] WebSocket connection accepted
- [ ] Audio frames received
- [ ] PCM-to-float conversion working
- [ ] No exceptions in server console

---

## 📱 Test 3: Google Glass App Build

**Goal:** Verify Glass Android app compiles successfully

### 3.1 Build Debug APK
```bash
cd glass-app
./gradlew assembleDebug
```

**Expected:**
- [ ] Build succeeds (no Kotlin syntax errors)
- [ ] APK created: `app/build/outputs/apk/debug/app-debug.apk`
- [ ] No compilation errors about `enableNoiseSuppressor`

**Or use helper script:**
```bash
./build_apk.sh debug
```

---

### 3.2 Verify AudioConfig Fix
```bash
# Check the fixed line
grep "enableNoiseSuppressor" app/src/main/java/com/arsmartassistant/glass/model/AudioConfig.kt
```

**Expected:**
```kotlin
val enableNoiseSuppressor: Boolean = true,
```

**Check:**
- [ ] No typo (`enableNoiseSuppress or` is gone)
- [ ] Variable name is correct

---

## 🎯 Test 4: End-to-End Glass → PC Pipeline

**Goal:** Full integration test with real Glass device

### 4.1 Install Glass APK
```bash
# Connect Glass via USB debugging
adb devices

# Install APK
adb install glass-app/app/build/outputs/apk/debug/app-debug.apk
```

**Expected:**
- [ ] APK installs successfully
- [ ] App appears in Glass launcher

---

### 4.2 Configure Glass App
**On Glass:**
1. Launch "AR SmartAssistant"
2. Go to Settings
3. Set Server Address: `[YOUR_PC_IP]:8765`
4. Enable "Noise Suppressor"
5. Enable "AGC"
6. Enable "AEC"
7. Tap "Save"

**Get PC IP:**
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
# Example: 192.168.1.100
```

---

### 4.3 Start Recording Session
**On PC:**
1. Ensure `config.yaml` has `input_source: "websocket"`
2. Start UI: `./run_ui.sh`
3. Click "Start Session" in browser

**On Glass:**
1. Tap "Connect" button
2. Wait for "Connected" status
3. Tap "Start Session"
4. Speak clearly: "Testing Glass to PC audio pipeline"

**Expected:**
- [ ] Glass shows "Connected"
- [ ] Glass shows "Recording"
- [ ] PC server logs show WebSocket connection
- [ ] PC server logs show audio frames received

---

### 4.4 Verify Audio Processing
**Check PC console for:**
```
WebSocket client connected
Received audio frame: 3200 bytes
PCM-to-float conversion: 1600 samples
VAD detected speech
ASR processing segment...
```

**Expected:**
- [ ] Audio frames arriving at PC
- [ ] PCM conversion working (1600 samples from 3200 bytes)
- [ ] VAD detecting speech
- [ ] ASR transcribing audio

---

### 4.5 Stop and Review
**On Glass:**
1. Tap "Stop Session"

**On PC:**
1. Click "Stop Session"

**Check Database:**
```bash
curl http://localhost:5000/api/sessions | jq '.sessions[0]'
```

**Expected:**
- [ ] Session saved to database
- [ ] Audio segments recorded
- [ ] Transcripts generated
- [ ] Speaker ID attempted

---

## 📊 Test 5: UI Database Integration

**Goal:** Verify all 6 new database methods work in UI

### 5.1 Test Session Retrieval
```bash
# Get session ID from previous test
SESSION_ID=$(curl -s http://localhost:5000/api/sessions | jq -r '.sessions[0].id')

# Test get_session() method
curl http://localhost:5000/api/sessions/$SESSION_ID | jq .
```

**Expected:**
- [ ] Returns session details
- [ ] Includes `events` array
- [ ] Includes `memories` array
- [ ] No AttributeError

---

### 5.2 Test Memory Approval
```bash
# Get memory ID
MEMORY_ID=$(curl -s http://localhost:5000/api/sessions/$SESSION_ID | jq -r '.memories[0].id')

# Test approve
curl -X POST http://localhost:5000/api/memories/$MEMORY_ID/approve | jq .

# Test reject
curl -X POST http://localhost:5000/api/memories/$MEMORY_ID/reject \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test rejection"}' | jq .
```

**Expected:**
- [ ] Approve endpoint works (tests `update_memory_approval()`)
- [ ] Reject endpoint works
- [ ] Status updates in database

---

### 5.3 Test Metrics Query
```bash
# Generate some metrics (run a session first)
# Then query recent metrics
curl http://localhost:5000/api/metrics/live | jq '.metrics | length'
```

**Expected:**
- [ ] Returns metrics array
- [ ] Metrics have `timestamp`, `metric_name`, `metric_value`
- [ ] No errors

---

## 🔍 Test 6: Error Handling

### 6.1 Test Invalid Session ID
```bash
curl http://localhost:5000/api/sessions/99999 | jq .
```

**Expected:**
```json
{
  "error": "Session not found"
}
```

**Check:**
- [ ] Returns 404 status
- [ ] Returns error message
- [ ] No server crash

---

### 6.2 Test WebSocket Disconnection
**While recording:**
1. Kill Glass app
2. Check PC server logs

**Expected:**
- [ ] Server handles disconnect gracefully
- [ ] Session continues (buffered audio)
- [ ] No Python exceptions

---

### 6.3 Test Double Start
**In UI:**
1. Click "Start Session"
2. Immediately click "Start Session" again

**Expected:**
```json
{
  "error": "Already recording"
}
```

**Check:**
- [ ] Returns 400 error
- [ ] Doesn't crash
- [ ] Original session continues

---

## 📝 Final Verification Checklist

### Code Fixes
- [ ] ✅ Kotlin syntax error fixed (`enableNoiseSuppressor`)
- [ ] ✅ WebSocket server implemented (`websocket_receiver.py`)
- [ ] ✅ PCM-to-float conversion implemented
- [ ] ✅ 6 database methods added to `BrainDatabase`
- [ ] ✅ UI integrated with WebSocket receiver

### Functionality
- [ ] PC microphone mode works
- [ ] WebSocket server accepts connections
- [ ] Glass app compiles successfully
- [ ] Glass → PC audio streaming works
- [ ] Database methods work in UI
- [ ] Session creation works
- [ ] Memory approval/rejection works

### Error Handling
- [ ] Invalid requests return proper errors
- [ ] Server handles disconnections gracefully
- [ ] No unhandled exceptions

---

## 🐛 Known Issues / TODO

### P1 Issues (Non-Blocking)
1. **VAD Energy Calculation** - Formula may need adjustment
2. **Frame Duration Mismatch** - VAD expects 30ms, receiving 100ms chunks
3. **Audio Storage Format** - Consider using FLAC/Opus compression
4. **Metadata Extraction** - Add Whisper confidence scores

### Future Enhancements
- Add SSL/TLS for WebSocket (wss://)
- Implement authentication for Glass connections
- Add session resume capability
- Implement real-time transcript streaming via WebSockets
- Add speaker enrollment UI workflow

---

## 📞 Support

If any test fails:
1. Check server logs for exceptions
2. Verify config.yaml settings
3. Ensure all dependencies installed
4. Check firewall allows port 8765
5. Verify Glass and PC on same network

**Critical Logs:**
```bash
# Server output
tail -f data/logs/app.log

# Database queries
sqlite3 data/brain_main.db "SELECT * FROM sessions ORDER BY id DESC LIMIT 1;"
```

---

## ✅ Test Summary

**Date Tested:** _______________
**Tester:** _______________

**Results:**
- [ ] All PC microphone tests passed
- [ ] All WebSocket tests passed
- [ ] Glass app build successful
- [ ] End-to-end pipeline working
- [ ] Database integration working
- [ ] Ready for production use

**Notes:**
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________

# AR-SmartAssistant Installation Guide

Complete installation and setup guide for the AR-SmartAssistant audio-first remembrance agent.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [Manual Installation](#manual-installation)
4. [Configuration](#configuration)
5. [Speaker Enrollment](#speaker-enrollment)
6. [Running the Application](#running-the-application)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)

---

## System Requirements

### Minimum Requirements

- **OS**: Linux, macOS, or Windows 10/11
- **Python**: 3.11 or higher
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB free space (for models and recordings)
- **Microphone**: Any USB or built-in microphone

### Recommended for GPU Acceleration

- **GPU**: NVIDIA GPU with 6GB+ VRAM (RTX 2060 or better)
- **CUDA**: 11.8 or higher
- **RAM**: 32GB (as specified in CONTRIBUTING.md)

### Optional Components

- **Ollama**: For LLM-based memory classification (https://ollama.ai)
- **Google Glass**: For mobile audio capture (requires separate Android app)

---

## Quick Start

The fastest way to get started is using the automated setup script:

```bash
# Clone the repository (if not already done)
cd AR-SmartAssistant

# Run setup script
./setup.sh

# Enroll your voice
./enroll_speaker.sh

# Start the debug UI
./run_ui.sh
```

Open your browser to **http://localhost:5000** and you're ready to go!

---

## Manual Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/Srikanth1511/AR-SmartAssistant.git
cd AR-SmartAssistant
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 3: Install Dependencies

**For CPU-only mode:**

```bash
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -e .[dev]
```

**For CUDA (GPU) mode:**

```bash
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -e .[dev,gpu]
```

### Step 4: Create Directory Structure

```bash
mkdir -p data/audio_segments
mkdir -p data/logs
mkdir -p data/chroma
mkdir -p models
```

### Step 5: Create Configuration File

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` and adjust settings for your system (see [Configuration](#configuration) section).

### Step 6: Initialize Database

```bash
python3 << EOF
from ar_smart_assistant.database.repository import BrainDatabase

db = BrainDatabase(
    brain_db_path="data/brain_main.db",
    metrics_db_path="data/system_metrics.db"
)
print("Database initialized!")
EOF
```

### Step 7: Download Models

The Whisper ASR model will be automatically downloaded on first use, or you can pre-download it:

```bash
python3 << EOF
from faster_whisper import WhisperModel

model = WhisperModel("small.en", device="cpu", compute_type="int8")
print("Whisper model downloaded!")
EOF
```

---

## Configuration

### Audio Source Selection

The system supports two audio input modes:

#### 1. PC Microphone (Default)

Edit `config.yaml`:

```yaml
audio:
  input_source: "microphone"  # Use local PC microphone
  capture:
    device_index: null  # null = default device, or specify device number
```

**List available devices:**

```bash
python -c "from ar_smart_assistant.perception.microphone import list_audio_devices; list_audio_devices()"
```

#### 2. Phone/Glass WebSocket

For streaming audio from Google Glass or phone:

```yaml
audio:
  input_source: "websocket"  # Wait for WebSocket connection

websocket:
  enabled: true
  host: "0.0.0.0"  # Listen on all interfaces
  port: 8765
```

**Note**: The Android/Glass app is required for this mode (see Google Glass setup docs).

### GPU vs CPU

Edit `config.yaml`:

```yaml
audio:
  asr:
    device: "cuda"  # Change to "cpu" if no GPU
    compute_type: "int8"  # int8, float16, or float32
```

### Storage Locations

```yaml
storage:
  root: "./data"
  audio_segments: "./data/audio_segments"
  databases:
    brain_main: "./data/brain_main.db"
    system_metrics: "./data/system_metrics.db"
```

### LLM Configuration (Optional)

If you have Ollama installed:

```yaml
llm:
  provider: "ollama"
  model: "llama3.1:8b"
  base_url: "http://localhost:11434"
```

**Install Ollama:**

```bash
# Linux
curl https://ollama.ai/install.sh | sh

# macOS
brew install ollama

# Pull model
ollama pull llama3.1:8b
```

---

## Speaker Enrollment

Speaker enrollment creates a voice profile for identifying you in recordings.

### Interactive Enrollment

```bash
# Using the convenience script
./enroll_speaker.sh

# Or directly
python -m ar_smart_assistant.tools.enroll_speaker
```

### Enrollment Process

1. **Select Audio Device**: Choose your microphone from the list
2. **Record Phrases**: Read 5 phrases aloud (6+ seconds each)
3. **Verify Quality**: Review playback and accept/reject each recording
4. **Save Profile**: Confirm to save your voice profile

### Tips for Good Enrollment

- Use a quiet environment
- Speak naturally at normal volume
- Keep consistent distance from microphone
- Re-enroll if quality score is below 70%

---

## Running the Application

### Debug UI (Recommended)

The debug UI provides session control, live transcripts, and memory review:

```bash
# Using convenience script
./run_ui.sh

# Or directly
python -m ar_smart_assistant.ui.app
```

Open **http://localhost:5000** in your browser.

### UI Features

- **Session Control**: Start/stop recording sessions
- **Audio Source Toggle**: Switch between PC mic and Glass/phone
- **Live Transcript**: Color-coded real-time transcription
- **Memory Review**: Approve/reject individual memories
- **System Metrics**: Monitor ASR confidence, speaker ID, latency

### Command Line Mode

For advanced users:

```bash
python << EOF
from ar_smart_assistant.config import load_config
from ar_smart_assistant.database.repository import BrainDatabase
from ar_smart_assistant.workflows.session_runner import SessionRunner
from ar_smart_assistant.perception.microphone import MicrophoneStream

config = load_config("config.yaml")
db = BrainDatabase("data/brain_main.db", "data/system_metrics.db")

runner = SessionRunner(config, db)

# Record 30 seconds
mic = MicrophoneStream(config.audio.capture)
mic.start()
import time
time.sleep(30)
mic.stop()

frames = list(mic.get_frames())
result = runner.run_session(frames)

print(f"Session complete! ID: {result['session_id']}")
EOF
```

---

## Troubleshooting

### No Audio Devices Found

**Problem**: `No audio input devices found!`

**Solutions**:

- Check microphone is connected
- On Linux, install: `sudo apt-get install portaudio19-dev python3-pyaudio`
- List devices: `python -c "import sounddevice as sd; print(sd.query_devices())"`

### CUDA Out of Memory

**Problem**: `CUDA out of memory` error

**Solutions**:

1. Use CPU mode (slower but works):
   ```yaml
   audio:
     asr:
       device: "cpu"
   ```

2. Use smaller Whisper model:
   ```yaml
   audio:
     asr:
       model_size: "tiny.en"  # Options: tiny.en, base.en, small.en
   ```

### Module Import Errors

**Problem**: `ModuleNotFoundError: No module named 'ar_smart_assistant'`

**Solutions**:

- Activate virtual environment: `source .venv/bin/activate`
- Reinstall in development mode: `pip install -e .`

### Database Locked

**Problem**: `database is locked` error

**Solutions**:

- Ensure only one instance is running
- Check file permissions: `chmod 664 data/brain_main.db`
- Close any SQLite browser tools

### Poor ASR Quality

**Problem**: Transcriptions are inaccurate

**Solutions**:

1. Check microphone quality and positioning
2. Reduce background noise
3. Adjust VAD threshold in `config.yaml`:
   ```yaml
   audio:
     vad:
       energy_threshold_db: -50  # Lower = more sensitive
   ```

4. Use larger Whisper model:
   ```yaml
   audio:
     asr:
       model_size: "medium.en"  # Better accuracy, slower
   ```

### Low Speaker Confidence

**Problem**: Speaker identification confidence < 80%

**Solutions**:

- Re-enroll in a quieter environment
- Increase number of enrollment phrases
- Ensure consistent microphone distance
- Check speaker profile quality: Review enrollment summary

---

## Advanced Configuration

### Custom Audio Preprocessing

```yaml
audio:
  preprocessing:
    noise_suppressor:
      enabled: true
    automatic_gain_control:
      enabled: true
    acoustic_echo_canceler:
      enabled: true  # Disable if echo cancellation causes issues
```

### VAD Tuning

```yaml
audio:
  vad:
    energy_threshold_db: -45  # Lower = more sensitive
    min_speech_duration_ms: 300  # Minimum speech length
    padding_duration_ms: 300  # Pre/post speech padding
```

### Memory Storage

```yaml
embeddings:
  provider: "chromadb"
  model: "all-MiniLM-L6-v2"
  collection_name: "memories"
  persist_directory: "./data/chroma"
```

### Logging

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "./data/logs/app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5
```

### Running as a Service (Linux)

Create `/etc/systemd/system/ar-smartassistant.service`:

```ini
[Unit]
Description=AR-SmartAssistant Debug UI
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/AR-SmartAssistant
ExecStart=/path/to/AR-SmartAssistant/run_ui.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ar-smartassistant
sudo systemctl start ar-smartassistant
```

---

## Next Steps

- **Read**: [`CONTRIBUTING.md`](CONTRIBUTING.md) for development guidelines
- **Explore**: [`docs/poc-audio-only/`](docs/poc-audio-only/) for technical details
- **Experiment**: Start recording sessions and reviewing memories!

## Getting Help

- **Issues**: https://github.com/Srikanth1511/AR-SmartAssistant/issues
- **Docs**: [`docs/README.md`](docs/README.md)
- **Contributing**: [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

**Happy remembering! 🧠**

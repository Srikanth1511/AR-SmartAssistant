#!/bin/bash
# AR-SmartAssistant Setup Script
# Installs dependencies, downloads models, and initializes the system

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║          AR-SmartAssistant Setup Wizard              ║
║          Audio-First Remembrance Agent               ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    log_error "Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

log_success "Python $PYTHON_VERSION found"

# Check for CUDA (optional)
log_info "Checking for CUDA..."
if command -v nvidia-smi &> /dev/null; then
    CUDA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1)
    log_success "NVIDIA GPU detected (Driver: $CUDA_VERSION)"
    USE_CUDA=true
else
    log_warning "No NVIDIA GPU detected. Will use CPU mode (slower)."
    USE_CUDA=false
fi

# Create virtual environment
log_info "Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    log_success "Virtual environment created"
else
    log_info "Virtual environment already exists"
fi

# Activate virtual environment
log_info "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
log_info "Upgrading pip..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# Install PyTorch (with CUDA support if available)
log_info "Installing PyTorch..."
if [ "$USE_CUDA" = true ]; then
    log_info "Installing PyTorch with CUDA support..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
else
    log_info "Installing PyTorch (CPU only)..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi
log_success "PyTorch installed"

# Install main dependencies
log_info "Installing AR-SmartAssistant and dependencies..."
pip install -e .[dev]
log_success "Main dependencies installed"

# Install GPU-specific dependencies if CUDA is available
if [ "$USE_CUDA" = true ]; then
    log_info "Installing GPU-specific dependencies..."
    pip install -e .[gpu]
    log_success "GPU dependencies installed"
fi

# Create necessary directories
log_info "Creating directory structure..."
mkdir -p data/audio_segments
mkdir -p data/logs
mkdir -p data/chroma
mkdir -p models
log_success "Directories created"

# Create config.yaml if it doesn't exist
if [ ! -f "config.yaml" ]; then
    log_info "Creating config.yaml from example..."
    cp config.yaml.example config.yaml

    # Update device to CPU if no CUDA
    if [ "$USE_CUDA" = false ]; then
        sed -i 's/device: "cuda"/device: "cpu"/' config.yaml
        log_info "Updated config to use CPU mode"
    fi

    log_success "config.yaml created"
else
    log_info "config.yaml already exists (not overwriting)"
fi

# Download Whisper model
log_info "Downloading Faster-Whisper model (small.en)..."
log_info "This may take a few minutes..."

python3 << EOF
import sys
try:
    from faster_whisper import WhisperModel

    print("Initializing Whisper model...")
    device = "cuda" if $USE_CUDA else "cpu"
    compute_type = "int8" if device == "cuda" else "int8"

    model = WhisperModel("small.en", device=device, compute_type=compute_type)
    print("Whisper model downloaded and cached successfully!")

except Exception as e:
    print(f"Error downloading Whisper model: {e}", file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    log_success "Whisper model ready"
else
    log_warning "Whisper model download failed (will retry on first use)"
fi

# Initialize database
log_info "Initializing database..."
python3 << EOF
from ar_smart_assistant.database.repository import BrainDatabase

db = BrainDatabase(
    brain_db_path="data/brain_main.db",
    metrics_db_path="data/system_metrics.db"
)

print("Database initialized successfully!")
EOF

if [ $? -eq 0 ]; then
    log_success "Database initialized"
else
    log_error "Database initialization failed"
    exit 1
fi

# Check for Ollama (optional)
log_info "Checking for Ollama (for LLM features)..."
if command -v ollama &> /dev/null; then
    log_success "Ollama found"

    # Check if llama model is available
    if ollama list | grep -q "llama3.1:8b"; then
        log_success "llama3.1:8b model found"
    else
        log_warning "llama3.1:8b model not found"
        read -p "Would you like to download it now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Downloading llama3.1:8b (this may take a while)..."
            ollama pull llama3.1:8b
            log_success "llama3.1:8b downloaded"
        fi
    fi
else
    log_warning "Ollama not found. Install from: https://ollama.ai"
    log_info "LLM features will be disabled until Ollama is installed"
fi

# Display audio devices
log_info "Available audio input devices:"
python3 << EOF
from ar_smart_assistant.perception.microphone import list_audio_devices
list_audio_devices()
EOF

# Summary
echo
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                       ║${NC}"
echo -e "${GREEN}║          Setup Complete!                              ║${NC}"
echo -e "${GREEN}║                                                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo
log_info "Next steps:"
echo "  1. Enroll your voice:"
echo "     python -m ar_smart_assistant.tools.enroll_speaker"
echo
echo "  2. Start the debug UI:"
echo "     python -m ar_smart_assistant.ui.app"
echo
echo "  3. Open browser to:"
echo "     http://localhost:5000"
echo
echo "For more information, see INSTALL.md"
echo

# Create quick launch scripts
cat > run_ui.sh << 'LAUNCHER'
#!/bin/bash
source .venv/bin/activate
python -m ar_smart_assistant.ui.app "$@"
LAUNCHER
chmod +x run_ui.sh

cat > enroll_speaker.sh << 'ENROLL'
#!/bin/bash
source .venv/bin/activate
python -m ar_smart_assistant.tools.enroll_speaker "$@"
ENROLL
chmod +x enroll_speaker.sh

log_success "Created launch scripts: run_ui.sh, enroll_speaker.sh"

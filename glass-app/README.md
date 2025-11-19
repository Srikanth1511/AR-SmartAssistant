# AR-SmartAssistant - Google Glass App

Android application for Google Glass Enterprise Edition that captures audio and streams it to the AR-SmartAssistant PC server via WebSocket.

## Features

✅ **Real-Time Audio Capture**: High-quality audio recording optimized for speech
✅ **Audio Preprocessing**: Noise suppression, automatic gain control, echo cancellation
✅ **WebSocket Streaming**: Live audio streaming to PC server
✅ **Glass-Optimized UI**: Large touch targets and minimal interface
✅ **Auto-Connect**: Optional automatic connection and session start
✅ **Battery Monitoring**: Display battery level to avoid unexpected shutdowns
✅ **Reconnection Logic**: Automatic reconnection on network issues

---

## Requirements

### Hardware
- **Google Glass Enterprise Edition 2** (or compatible Android device for testing)
- **PC running AR-SmartAssistant server** (see main README.md)
- **Wi-Fi connection** (Glass and PC must be on same network or reachable)

### Software
- **Android Studio** Arctic Fox (2020.3.1) or newer
- **Android SDK**: API 27 or higher
- **Gradle**: 8.2 or higher
- **Kotlin**: 1.9.20 or higher

---

## Building the App

### 1. Open Project in Android Studio

```bash
cd AR-SmartAssistant/glass-app
# Open this directory in Android Studio
```

### 2. Sync Gradle

Android Studio should automatically sync Gradle dependencies. If not:
- Click **File → Sync Project with Gradle Files**

### 3. Build APK

**For Debug (Development):**
```bash
./gradlew assembleDebug
```
Output: `app/build/outputs/apk/debug/app-debug.apk`

**For Release (Production):**
```bash
./gradlew assembleRelease
```
Output: `app/build/outputs/apk/release/app-release.apk`

### 4. Sign APK (Release Only)

For production deployment, sign the APK:

1. Create keystore (one-time):
   ```bash
   keytool -genkey -v -keystore ar-smartassistant.keystore \
     -alias ar-smart-assistant -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Sign APK:
   ```bash
   jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
     -keystore ar-smartassistant.keystore \
     app/build/outputs/apk/release/app-release-unsigned.apk ar-smart-assistant
   ```

3. Align APK:
   ```bash
   zipalign -v 4 app/build/outputs/apk/release/app-release-unsigned.apk \
     app/build/outputs/apk/release/app-release.apk
   ```

---

## Installing on Google Glass

### Method 1: ADB (Recommended for Development)

1. **Enable Developer Mode on Glass:**
   - Go to Settings → About → Tap "Build number" 7 times
   - Go to Settings → Developer options → Enable "USB debugging"

2. **Connect Glass to PC:**
   ```bash
   # Connect via USB
   adb devices  # Verify Glass is detected
   ```

3. **Install APK:**
   ```bash
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

4. **Run App:**
   ```bash
   adb shell am start -n com.arsmartassistant.glass/.MainActivity
   ```

### Method 2: Over Wi-Fi (Wireless ADB)

1. **Connect Glass via USB first**

2. **Enable TCP/IP mode:**
   ```bash
   adb tcpip 5555
   ```

3. **Find Glass IP address:**
   ```bash
   adb shell ip addr show wlan0
   # Look for inet address (e.g., 192.168.1.50)
   ```

4. **Disconnect USB and connect wirelessly:**
   ```bash
   adb connect 192.168.1.50:5555
   adb devices  # Verify wireless connection
   ```

5. **Install as normal:**
   ```bash
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

### Method 3: Manual Transfer

1. Transfer APK to Glass via USB or cloud storage
2. Use a file manager app to locate the APK
3. Tap to install (requires "Unknown sources" enabled)

---

## Configuration

### First-Time Setup

1. **Launch App** on Glass
2. **Tap Settings** (gear icon in top-right)
3. **Enter PC Server Address:**
   - Server Address: Your PC's IP (e.g., `192.168.1.100`)
   - Server Port: `8765` (default)
4. **Optional Settings:**
   - Auto-connect on startup
   - Auto-start session when connected
   - Enable audio preprocessing
5. **Tap Save**

### Finding Your PC's IP Address

**Linux/Mac:**
```bash
ifconfig | grep inet
# or
ip addr show
```

**Windows:**
```cmd
ipconfig
```

Look for your local network IP (usually 192.168.x.x or 10.0.x.x)

---

## Usage

### Basic Workflow

1. **Ensure PC server is running:**
   ```bash
   cd AR-SmartAssistant
   ./run_ui.sh
   ```

2. **Launch Glass app**

3. **Connect to Server:**
   - Tap "Connect" button
   - Wait for "Connected" status (green indicator)

4. **Start Recording:**
   - Tap "Start Session"
   - Speak naturally
   - Audio is streamed to PC in real-time

5. **Stop Recording:**
   - Tap "Stop Session"

6. **Disconnect:**
   - Tap "Disconnect" when done

### Status Indicators

- **Grey**: Disconnected
- **Yellow**: Connecting...
- **Green**: Connected
- **Red**: Error

---

## Troubleshooting

### Connection Issues

**Problem**: "Connection failed" error

**Solutions**:
1. Verify Glass and PC are on same network
2. Check PC firewall allows port 8765
3. Verify PC server is running:
   ```bash
   # On PC
   netstat -an | grep 8765
   ```
4. Try ping from Glass to PC:
   ```bash
   adb shell ping <PC_IP>
   ```

### Audio Not Recording

**Problem**: Session starts but no audio captured

**Solutions**:
1. Grant microphone permission:
   - Settings → Apps → AR SmartAssistant → Permissions → Microphone
2. Check Glass microphone hardware:
   - Test with native audio recorder
3. Review logs:
   ```bash
   adb logcat | grep AudioCapture
   ```

### Poor Audio Quality

**Problem**: Audio is garbled or noisy

**Solutions**:
1. Enable audio preprocessing in Settings
2. Reduce distance to Glass microphone
3. Check network quality:
   ```bash
   adb shell ping -c 10 <PC_IP>
   # Check for packet loss
   ```
4. Use Wi-Fi instead of mobile data

### Battery Drain

**Problem**: Battery drains quickly during recording

**Solutions**:
1. This is expected (constant mic + network use)
2. Connect Glass to power during long sessions
3. Disable auto-start session when not needed
4. Stop sessions when not actively recording

---

## Development

### Project Structure

```
glass-app/
├── app/
│   ├── src/main/
│   │   ├── java/com/arsmartassistant/glass/
│   │   │   ├── GlassApplication.kt         # App initialization
│   │   │   ├── MainActivity.kt              # Main UI
│   │   │   ├── SettingsActivity.kt          # Settings UI
│   │   │   ├── model/
│   │   │   │   └── AudioConfig.kt           # Data models
│   │   │   ├── service/
│   │   │   │   ├── AudioCaptureService.kt   # Audio recording
│   │   │   │   └── WebSocketClient.kt       # Network streaming
│   │   │   └── util/
│   │   │       └── Preferences.kt           # Settings storage
│   │   ├── res/                             # UI resources
│   │   └── AndroidManifest.xml              # App manifest
│   └── build.gradle                         # App dependencies
├── build.gradle                             # Project config
└── README.md                                # This file
```

### Viewing Logs

**Real-time logs:**
```bash
adb logcat | grep -E "(AR-Smart|AudioCapture|WebSocket)"
```

**Filter by priority:**
```bash
adb logcat *:E  # Errors only
adb logcat *:W  # Warnings and above
adb logcat *:D  # Debug and above
```

### Testing on Emulator

While Glass-specific features won't work, you can test basic functionality:

1. Create Android Virtual Device (AVD) with API 27+
2. Run app from Android Studio
3. Configure server address as PC's IP (not localhost!)
4. Use emulator's built-in microphone

---

## Architecture

### Audio Processing Pipeline

```
Glass Microphone
    ↓
AudioRecord (VOICE_RECOGNITION source)
    ↓
Preprocessing:
  - NoiseSuppressor
  - AutomaticGainControl
  - AcousticEchoCanceler
    ↓
PCM 16-bit, 16kHz, Mono
    ↓
WebSocket Client (binary frames)
    ↓
PC Server (AR-SmartAssistant)
```

### Threading Model

- **Main Thread**: UI updates, user interactions
- **Service Thread**: Audio capture loop
- **WebSocket Thread**: Network I/O
- **Coroutines**: State management, async operations

---

## Performance

### Audio Specifications

- **Sample Rate**: 16,000 Hz
- **Encoding**: PCM 16-bit
- **Channels**: Mono
- **Buffer Size**: 3,200 bytes (200ms chunks)
- **Latency**: ~200-400ms end-to-end

### Network Usage

- **Bandwidth**: ~256 Kbps (32 KB/s)
- **Protocol**: WebSocket (binary frames)
- **Typical Session**: ~115 MB per hour

### Battery Impact

- **Idle**: Minimal (<1% per hour)
- **Connected**: Low (~2-3% per hour)
- **Recording**: Moderate (~10-15% per hour)

---

## Security

### Permissions

The app requests:
- **RECORD_AUDIO**: Required for microphone access
- **INTERNET**: Required for server connection
- **FOREGROUND_SERVICE**: Keeps recording active

### Network Security

- Currently uses **unencrypted WebSocket** (ws://)
- For production, implement **WSS (WebSocket Secure)**
- Audio data transmitted without encryption
- Recommended: Use VPN or secure local network

### Privacy

- No data stored locally on Glass
- All audio streamed to PC server only
- No cloud services or third-party APIs
- Microphone indicator shown during recording

---

## Known Limitations

1. **No SSL/TLS**: WebSocket connections are unencrypted
2. **No Offline Mode**: Requires active server connection
3. **Wi-Fi Only**: Mobile data not recommended (high bandwidth)
4. **Battery Drain**: Continuous recording impacts battery life
5. **Network Dependent**: Audio quality depends on network stability

---

## Future Enhancements

- [ ] WSS (secure WebSocket) support
- [ ] Local audio buffering for network interruptions
- [ ] Compression before transmission
- [ ] Voice activity detection on-device
- [ ] Support for Bluetooth microphones
- [ ] Multi-server configuration
- [ ] Session encryption
- [ ] Offline recording with sync

---

## Support

- **Issues**: https://github.com/Srikanth1511/AR-SmartAssistant/issues
- **Main Docs**: See `../INSTALL.md` for PC setup
- **Logs**: Use `adb logcat` for debugging

---

## License

Same as main AR-SmartAssistant project. See `../LICENSE`.

---

**Ready to stream audio from Glass to your PC!** 🥽🎤

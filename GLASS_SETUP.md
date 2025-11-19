# Google Glass Setup Guide

Complete guide for setting up the AR-SmartAssistant Android app on Google Glass Enterprise Edition.

## Overview

The Glass app captures audio from the Glass microphone, applies preprocessing (noise suppression, AGC, echo cancellation), and streams it in real-time to your PC running the AR-SmartAssistant server.

---

## Prerequisites

### What You Need

1. **Google Glass Enterprise Edition 2** (or Android device for testing)
2. **PC with AR-SmartAssistant** installed and running (see `INSTALL.md`)
3. **Android Studio** (for building the app)
4. **Wi-Fi network** (Glass and PC must be able to communicate)
5. **USB cable** (for initial setup)

---

## Quick Start

```bash
# 1. Build the Glass app
cd glass-app
./build_apk.sh debug

# 2. Install on Glass via USB
adb install app/build/outputs/apk/debug/app-debug.apk

# 3. On Glass: Configure server address in Settings

# 4. On PC: Start AR-SmartAssistant server
cd ..
./run_ui.sh

# 5. On Glass: Tap "Connect" then "Start Session"
```

---

## Detailed Setup

### Step 1: Build the Android App

#### Option A: Using Android Studio (Recommended)

1. **Open Android Studio**

2. **Open Project:**
   - File → Open
   - Select `AR-SmartAssistant/glass-app/`

3. **Sync Gradle:**
   - Android Studio should auto-sync
   - If not: File → Sync Project with Gradle Files

4. **Build APK:**
   - Build → Build Bundle(s) / APK(s) → Build APK(s)
   - APK location: `app/build/outputs/apk/debug/app-debug.apk`

#### Option B: Command Line

```bash
cd AR-SmartAssistant/glass-app
./build_apk.sh debug
```

---

### Step 2: Enable Developer Mode on Glass

1. **Access Settings** on Glass
2. **Navigate to:** Settings → About
3. **Tap "Build number"** 7 times
4. **Go to:** Settings → Developer options
5. **Enable "USB debugging"**

---

### Step 3: Install App on Glass

#### Via USB (Easiest)

1. **Connect Glass to PC** via USB

2. **Verify connection:**
   ```bash
   adb devices
   # Should show your Glass device
   ```

3. **Install APK:**
   ```bash
   cd AR-SmartAssistant/glass-app
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

4. **Grant permissions when prompted on Glass**

#### Via Wi-Fi (Wireless ADB)

1. **First connect via USB**

2. **Enable TCP/IP mode:**
   ```bash
   adb tcpip 5555
   ```

3. **Find Glass IP:**
   ```bash
   adb shell ip addr show wlan0
   # Look for: inet 192.168.x.x
   ```

4. **Disconnect USB, connect wirelessly:**
   ```bash
   adb connect 192.168.1.50:5555  # Use your Glass IP
   ```

5. **Install APK:**
   ```bash
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

---

### Step 4: Configure Network

#### Find Your PC's IP Address

**On PC (Linux/Mac):**
```bash
ifconfig | grep "inet "
# or
ip addr show
# Look for 192.168.x.x or 10.0.x.x
```

**On PC (Windows):**
```cmd
ipconfig
# Look for IPv4 Address under your network adapter
```

#### Ensure Firewall Allows WebSocket Port

**Linux (ufw):**
```bash
sudo ufw allow 8765/tcp
```

**Windows:**
- Control Panel → Windows Defender Firewall
- Advanced Settings → Inbound Rules → New Rule
- Port: 8765, Protocol: TCP

**Mac:**
- System Preferences → Security & Privacy → Firewall
- Firewall Options → Add AR-SmartAssistant

#### Verify Network Connectivity

From Glass to PC:
```bash
# On PC: Find PC IP
hostname -I

# From Glass via ADB
adb shell ping <PC_IP>
# Should see replies
```

---

### Step 5: Configure Glass App

1. **Launch AR-SmartAssistant** on Glass

2. **Tap Settings** (gear icon, top-right)

3. **Enter Configuration:**
   - **Server Address**: Your PC's IP (e.g., `192.168.1.100`)
   - **Server Port**: `8765` (default WebSocket port)
   - **Auto-connect**: Enable (optional)
   - **Auto-start session**: Enable (optional)
   - **Enable preprocessing**: Enable (recommended)

4. **Tap Save**

5. **Return to main screen**

---

### Step 6: Start PC Server

1. **On PC, start AR-SmartAssistant:**
   ```bash
   cd AR-SmartAssistant
   ./run_ui.sh
   ```

2. **Open web UI** in browser: http://localhost:5000

3. **In UI, select audio source:**
   - Dropdown: "Phone/Glass WebSocket"
   - (Not "PC Microphone")

4. **Wait for WebSocket server** to be ready (check console)

---

### Step 7: Connect and Record

1. **On Glass:**
   - Tap "Connect"
   - Wait for green status indicator
   - Tap "Start Session"

2. **On PC Web UI:**
   - You should see "Session started" message
   - Live transcripts will appear as you speak

3. **Speak naturally** into Glass microphone

4. **On Glass when done:**
   - Tap "Stop Session"
   - Tap "Disconnect" (optional)

---

## Troubleshooting

### Connection Issues

#### "Connection Failed" Error

**Symptoms**: Glass app shows "Connection failed"

**Checks:**
1. Verify PC server is running:
   ```bash
   # On PC
   ps aux | grep python.*ui.app
   ```

2. Verify WebSocket port is open:
   ```bash
   # On PC
   netstat -an | grep 8765
   # Should show LISTEN
   ```

3. Test connectivity from Glass:
   ```bash
   adb shell ping <PC_IP>
   ```

4. Check firewall isn't blocking:
   ```bash
   # Temporarily disable to test
   sudo ufw disable  # Linux
   ```

5. Verify same network:
   - Glass and PC must be on same Wi-Fi network
   - Or PC must be reachable from Glass network

#### WebSocket Server Not Starting

**Symptoms**: PC shows error when starting server

**Solutions:**
1. Check port not already in use:
   ```bash
   lsof -i :8765  # Linux/Mac
   netstat -ano | findstr :8765  # Windows
   ```

2. Change port in both:
   - PC: `config.yaml` → `websocket.port`
   - Glass: Settings → Server Port

#### Wrong IP Address

**Symptoms**: Can't reach server

**Solutions:**
- Don't use `127.0.0.1` or `localhost` (only works on same device)
- Use actual LAN IP (192.168.x.x or 10.0.x.x)
- On PC with multiple network adapters, use the one on same network as Glass

---

### Audio Issues

#### No Audio Captured

**Symptoms**: Session starts but no transcripts appear

**Checks:**
1. Grant microphone permission on Glass:
   ```bash
   adb shell pm grant com.arsmartassistant.glass android.permission.RECORD_AUDIO
   ```

2. Test Glass microphone:
   - Use native audio recorder app
   - Try "OK Glass" voice commands

3. Check logs:
   ```bash
   adb logcat | grep AudioCapture
   ```

#### Poor Audio Quality

**Symptoms**: Transcripts are inaccurate or garbled

**Solutions:**
1. Enable preprocessing in Glass Settings
2. Check network quality:
   ```bash
   adb shell ping -c 100 <PC_IP>
   # Check packet loss %
   ```
3. Move closer to Wi-Fi router
4. Speak clearly, 1-2 feet from Glass
5. Reduce background noise

#### Audio Lag/Delay

**Symptoms**: Noticeable delay between speaking and transcription

**Expected:** 200-400ms latency is normal

**Improvements:**
- Use 5GHz Wi-Fi (not 2.4GHz)
- Ensure PC is on wired connection
- Reduce network congestion
- Check PC CPU isn't maxed out

---

### Permission Issues

#### Microphone Permission Denied

**Manual Grant:**
```bash
adb shell pm grant com.arsmartassistant.glass android.permission.RECORD_AUDIO
```

#### Foreground Service Permission

**If app crashes on Android 14+:**
```bash
adb shell pm grant com.arsmartassistant.glass android.permission.FOREGROUND_SERVICE_MICROPHONE
```

---

### Viewing Logs

#### Real-time Logs

```bash
# All app logs
adb logcat | grep "AR-Smart\|AudioCapture\|WebSocket"

# Errors only
adb logcat *:E | grep "com.arsmartassistant"

# Clear logs first
adb logcat -c
adb logcat | grep AudioCapture
```

#### Save Logs to File

```bash
adb logcat -d > glass-app-logs.txt
```

---

## Advanced Configuration

### WebSocket Server on PC

The PC WebSocket server is configured in `config.yaml`:

```yaml
websocket:
  enabled: true
  host: "0.0.0.0"  # Listen on all interfaces
  port: 8765
```

**Important:**
- `host: "0.0.0.0"` allows connections from any device
- For security, use `host: "192.168.x.x"` (your PC's specific IP)

### Audio Configuration Matching

Glass and PC audio configs should match:

**Glass** (hardcoded in AudioConfig.kt):
- Sample Rate: 16,000 Hz
- Encoding: PCM 16-bit
- Channels: Mono
- Buffer: 3,200 bytes

**PC** (config.yaml):
```yaml
audio:
  capture:
    sample_rate_hz: 16000
    encoding: "PCM_16BIT"
    channel: "MONO"
    buffer_size_bytes: 3200
```

### Custom Server Port

To use a different port:

1. **On PC** (`config.yaml`):
   ```yaml
   websocket:
     port: 9000  # Your custom port
   ```

2. **On Glass** (Settings):
   - Server Port: `9000`

3. **Update firewall** to allow custom port

---

## Performance Tips

### Battery Optimization

- **Disable auto-start** when not actively recording
- **Stop sessions** between uses
- **Disconnect** when done
- **Use power bank** for extended sessions

### Network Optimization

- **Use 5GHz Wi-Fi** for better bandwidth
- **Reduce distance** to router
- **Avoid congested networks**
- **Use QoS** to prioritize WebSocket traffic

### Audio Quality

- **Speak 1-2 feet** from Glass
- **Reduce background noise**
- **Enable preprocessing**
- **Test different rooms** for acoustics

---

## Testing Without Glass

### Using Android Phone

The app works on any Android device:

1. Build and install on phone
2. Configure same as Glass
3. Use phone's microphone
4. Test in landscape mode for Glass-like experience

### Using Android Emulator

1. Create AVD with API 27+
2. Install app
3. Configure server with PC's actual IP (not localhost)
4. Limited: Can't test Glass-specific features

---

## Production Deployment

### Signing APK for Distribution

1. **Create keystore** (one-time):
   ```bash
   keytool -genkey -v -keystore release.keystore \
     -alias arsmartassistant -keyalg RSA -keysize 2048 \
     -validity 10000
   ```

2. **Configure in `app/build.gradle`**:
   ```gradle
   android {
       signingConfigs {
           release {
               storeFile file("../release.keystore")
               storePassword "your_password"
               keyAlias "arsmartassistant"
               keyPassword "your_password"
           }
       }
       buildTypes {
           release {
               signingConfig signingConfigs.release
           }
       }
   }
   ```

3. **Build release APK:**
   ```bash
   ./build_apk.sh release
   ```

### Enterprise Deployment

For deploying to multiple Glass devices:

1. **Use MDM** (Mobile Device Management)
2. **Configure via** remote config push
3. **Pre-configure** server addresses
4. **Enable auto-connect** and auto-start

---

## Security Considerations

### Current Limitations

⚠️ **Unencrypted Connection**: WebSocket uses `ws://` (not `wss://`)
⚠️ **No Authentication**: Anyone on network can connect
⚠️ **No Audio Encryption**: Audio sent in plaintext

### Recommendations

1. **Use trusted network** only
2. **VPN** for remote access
3. **Implement WSS** for production
4. **Add authentication** token
5. **Firewall rules** to limit access

---

## Next Steps

1. ✅ Build and install Glass app
2. ✅ Configure server connection
3. ✅ Test audio streaming
4. 📖 See `../INSTALL.md` for PC setup details
5. 📖 See `glass-app/README.md` for development

---

**Your Glass is now ready to stream audio to AR-SmartAssistant!** 🥽→💻

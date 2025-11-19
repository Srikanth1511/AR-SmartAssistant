package com.arsmartassistant.glass

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.os.BatteryManager
import android.os.Bundle
import android.os.IBinder
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.arsmartassistant.glass.databinding.ActivityMainBinding
import com.arsmartassistant.glass.model.AudioConfig
import com.arsmartassistant.glass.model.ConnectionState
import com.arsmartassistant.glass.model.SessionState
import com.arsmartassistant.glass.service.AudioCaptureService
import com.arsmartassistant.glass.service.AudioWebSocketClient
import com.arsmartassistant.glass.util.Preferences
import kotlinx.coroutines.launch
import timber.log.Timber
import java.net.URI

/**
 * Main activity for Google Glass AR-SmartAssistant app.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: Preferences

    private var audioService: AudioCaptureService? = null
    private var webSocketClient: AudioWebSocketClient? = null

    private var serviceBound = false

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as AudioCaptureService.AudioCaptureBinder
            audioService = binder.getService()
            serviceBound = true

            Timber.d("AudioCaptureService connected")

            // Observe session state
            lifecycleScope.launch {
                audioService?.sessionState?.collect { state ->
                    updateSessionState(state)
                }
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            audioService = null
            serviceBound = false
            Timber.d("AudioCaptureService disconnected")
        }
    }

    // Permission request launcher
    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            Timber.i("Microphone permission granted")
        } else {
            Toast.makeText(this, R.string.error_mic_permission, Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = Preferences.getInstance(this)

        setupUI()
        checkMicrophonePermission()
        updateBatteryLevel()

        // Bind to audio service
        bindAudioService()

        // Auto-connect if enabled
        if (prefs.autoConnect && prefs.isServerConfigured()) {
            connectToServer()
        }
    }

    private fun setupUI() {
        // Update server address display
        if (prefs.isServerConfigured()) {
            binding.serverAddressText.text = "Server: ${prefs.serverUrl}"
        } else {
            binding.serverAddressText.text = "Server: Not configured"
            binding.infoText.text = "Configure server in Settings"
        }

        // Connect button
        binding.connectButton.setOnClickListener {
            if (webSocketClient?.isOpen == true) {
                disconnectFromServer()
            } else {
                connectToServer()
            }
        }

        // Start session button
        binding.startSessionButton.setOnClickListener {
            if (audioService?.sessionState?.value == SessionState.RECORDING) {
                stopSession()
            } else {
                startSession()
            }
        }

        // Settings button
        binding.settingsButton.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // Initially disable session button
        binding.startSessionButton.isEnabled = false
    }

    private fun bindAudioService() {
        val intent = Intent(this, AudioCaptureService::class.java)
        startService(intent) // Start service first
        bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE)
    }

    private fun checkMicrophonePermission() {
        when {
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED -> {
                Timber.d("Microphone permission already granted")
            }
            shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO) -> {
                Toast.makeText(
                    this,
                    "Microphone access needed for audio recording",
                    Toast.LENGTH_LONG
                ).show()
                requestPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
            else -> {
                requestPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
    }

    private fun connectToServer() {
        if (!prefs.isServerConfigured()) {
            Toast.makeText(this, R.string.error_server_address, Toast.LENGTH_SHORT).show()
            return
        }

        try {
            updateConnectionState(ConnectionState.CONNECTING)

            val serverUri = URI(prefs.serverUrl)
            webSocketClient = AudioWebSocketClient(serverUri) { state ->
                runOnUiThread {
                    updateConnectionState(state)
                }
            }

            webSocketClient?.connect()

            Timber.i("Connecting to ${prefs.serverUrl}")

        } catch (e: Exception) {
            Timber.e(e, "Failed to connect to server")
            Toast.makeText(this, R.string.error_connection_failed, Toast.LENGTH_SHORT).show()
            updateConnectionState(ConnectionState.ERROR)
        }
    }

    private fun disconnectFromServer() {
        // Stop session if recording
        if (audioService?.sessionState?.value == SessionState.RECORDING) {
            stopSession()
        }

        webSocketClient?.disconnect()
        webSocketClient = null

        updateConnectionState(ConnectionState.DISCONNECTED)
        Timber.i("Disconnected from server")
    }

    private fun startSession() {
        val wsClient = webSocketClient

        if (wsClient == null || !wsClient.isOpen) {
            Toast.makeText(this, "Not connected to server", Toast.LENGTH_SHORT).show()
            return
        }

        if (!checkMicrophonePermissionGranted()) {
            Toast.makeText(this, R.string.error_mic_permission, Toast.LENGTH_SHORT).show()
            return
        }

        try {
            val audioConfig = AudioConfig(
                enableNoiseSuppressor = prefs.enablePreprocessing,
                enableAGC = prefs.enablePreprocessing,
                enableAEC = prefs.enablePreprocessing
            )

            audioService?.initialize(audioConfig, wsClient)
            audioService?.startRecording()

            Timber.i("Session started")

        } catch (e: Exception) {
            Timber.e(e, "Failed to start session")
            Toast.makeText(this, R.string.error_audio_init, Toast.LENGTH_SHORT).show()
        }
    }

    private fun stopSession() {
        audioService?.stopRecording()
        Timber.i("Session stopped")
    }

    private fun checkMicrophonePermissionGranted(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun updateConnectionState(state: ConnectionState) {
        when (state) {
            ConnectionState.DISCONNECTED -> {
                binding.statusText.text = getString(R.string.status_disconnected)
                binding.statusIndicator.backgroundTintList = ColorStateList.valueOf(
                    ContextCompat.getColor(this, R.color.gray)
                )
                binding.connectButton.text = getString(R.string.connect)
                binding.startSessionButton.isEnabled = false
            }

            ConnectionState.CONNECTING -> {
                binding.statusText.text = getString(R.string.status_connecting)
                binding.statusIndicator.backgroundTintList = ColorStateList.valueOf(
                    ContextCompat.getColor(this, R.color.warning)
                )
                binding.connectButton.isEnabled = false
            }

            ConnectionState.CONNECTED -> {
                binding.statusText.text = getString(R.string.status_connected)
                binding.statusIndicator.backgroundTintList = ColorStateList.valueOf(
                    ContextCompat.getColor(this, R.color.success)
                )
                binding.connectButton.text = getString(R.string.disconnect)
                binding.connectButton.isEnabled = true
                binding.startSessionButton.isEnabled = true

                // Auto-start session if enabled
                if (prefs.autoStartSession) {
                    startSession()
                }
            }

            ConnectionState.ERROR -> {
                binding.statusText.text = "Error"
                binding.statusIndicator.backgroundTintList = ColorStateList.valueOf(
                    ContextCompat.getColor(this, R.color.error)
                )
                binding.connectButton.text = getString(R.string.connect)
                binding.connectButton.isEnabled = true
                binding.startSessionButton.isEnabled = false
            }
        }
    }

    private fun updateSessionState(state: SessionState) {
        when (state) {
            SessionState.IDLE -> {
                binding.startSessionButton.text = getString(R.string.start_session)
                binding.infoText.text = "Ready to record"
            }

            SessionState.RECORDING -> {
                binding.startSessionButton.text = getString(R.string.stop_session)
                binding.infoText.text = "Recording in progress..."
                binding.statusText.text = getString(R.string.status_recording)
            }

            SessionState.PAUSED -> {
                binding.infoText.text = "Session paused"
            }
        }
    }

    private fun updateBatteryLevel() {
        val batteryManager = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val batteryLevel = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)

        binding.batteryText.text = getString(R.string.battery_level, batteryLevel)

        // Update every 30 seconds
        binding.root.postDelayed({
            if (!isDestroying) {
                updateBatteryLevel()
            }
        }, 30000)
    }

    override fun onResume() {
        super.onResume()

        // Refresh server address display
        if (prefs.isServerConfigured()) {
            binding.serverAddressText.text = "Server: ${prefs.serverUrl}"
        }
    }

    override fun onDestroy() {
        super.onDestroy()

        if (serviceBound) {
            unbindService(serviceConnection)
            serviceBound = false
        }

        webSocketClient?.disconnect()
    }
}

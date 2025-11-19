package com.arsmartassistant.glass.service

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import android.os.Binder
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.arsmartassistant.glass.GlassApplication
import com.arsmartassistant.glass.MainActivity
import com.arsmartassistant.glass.R
import com.arsmartassistant.glass.model.AudioConfig
import com.arsmartassistant.glass.model.SessionState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import timber.log.Timber
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Foreground service for capturing audio from the microphone.
 * Applies preprocessing (noise suppression, AGC, AEC) and streams to WebSocket.
 */
class AudioCaptureService : Service() {

    private val binder = AudioCaptureBinder()
    private val serviceScope = CoroutineScope(Dispatchers.Default + Job())

    private var audioRecord: AudioRecord? = null
    private var noiseSuppressor: NoiseSuppressor? = null
    private var automaticGainControl: AutomaticGainControl? = null
    private var acousticEchoCanceler: AcousticEchoCanceler? = null

    private val _sessionState = MutableStateFlow(SessionState.IDLE)
    val sessionState: StateFlow<SessionState> = _sessionState

    private var audioConfig = AudioConfig()
    private var webSocketClient: AudioWebSocketClient? = null

    private var recordingJob: Job? = null

    inner class AudioCaptureBinder : Binder() {
        fun getService(): AudioCaptureService = this@AudioCaptureService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        Timber.i("AudioCaptureService created")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Start as foreground service
        startForeground(NOTIFICATION_ID, createNotification())
        return START_STICKY
    }

    /**
     * Initialize audio capture with specified configuration.
     */
    fun initialize(config: AudioConfig, wsClient: AudioWebSocketClient) {
        this.audioConfig = config
        this.webSocketClient = wsClient

        val channelConfig = when (config.channel) {
            com.arsmartassistant.glass.model.AudioChannel.MONO -> AudioFormat.CHANNEL_IN_MONO
            com.arsmartassistant.glass.model.AudioChannel.STEREO -> AudioFormat.CHANNEL_IN_STEREO
        }

        val audioFormat = when (config.encoding) {
            com.arsmartassistant.glass.model.AudioEncoding.PCM_16BIT -> AudioFormat.ENCODING_PCM_16BIT
            com.arsmartassistant.glass.model.AudioEncoding.PCM_8BIT -> AudioFormat.ENCODING_PCM_8BIT
        }

        val minBufferSize = AudioRecord.getMinBufferSize(
            config.sampleRate,
            channelConfig,
            audioFormat
        )

        val bufferSize = maxOf(minBufferSize, config.bufferSizeBytes)

        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                config.sampleRate,
                channelConfig,
                audioFormat,
                bufferSize
            ).also { record ->
                // Initialize audio effects if enabled
                if (config.enableNoiseSuppressor && NoiseSuppressor.isAvailable()) {
                    noiseSuppressor = NoiseSuppressor.create(record.audioSessionId)?.apply {
                        enabled = true
                        Timber.d("NoiseSuppressor enabled")
                    }
                }

                if (config.enableAGC && AutomaticGainControl.isAvailable()) {
                    automaticGainControl = AutomaticGainControl.create(record.audioSessionId)?.apply {
                        enabled = true
                        Timber.d("AutomaticGainControl enabled")
                    }
                }

                if (config.enableAEC && AcousticEchoCanceler.isAvailable()) {
                    acousticEchoCanceler = AcousticEchoCanceler.create(record.audioSessionId)?.apply {
                        enabled = true
                        Timber.d("AcousticEchoCanceler enabled")
                    }
                }
            }

            Timber.i("Audio capture initialized: sampleRate=${config.sampleRate}, bufferSize=$bufferSize")

        } catch (e: Exception) {
            Timber.e(e, "Failed to initialize audio capture")
            throw e
        }
    }

    /**
     * Start recording audio.
     */
    fun startRecording() {
        if (_sessionState.value == SessionState.RECORDING) {
            Timber.w("Already recording")
            return
        }

        val record = audioRecord ?: run {
            Timber.e("AudioRecord not initialized")
            return
        }

        try {
            record.startRecording()
            _sessionState.value = SessionState.RECORDING

            // Start capture loop in coroutine
            recordingJob = serviceScope.launch {
                captureAudio(record)
            }

            Timber.i("Audio recording started")

        } catch (e: Exception) {
            Timber.e(e, "Failed to start recording")
            _sessionState.value = SessionState.IDLE
        }
    }

    /**
     * Stop recording audio.
     */
    fun stopRecording() {
        if (_sessionState.value != SessionState.RECORDING) {
            Timber.w("Not currently recording")
            return
        }

        recordingJob?.cancel()
        recordingJob = null

        audioRecord?.stop()
        _sessionState.value = SessionState.IDLE

        Timber.i("Audio recording stopped")
    }

    /**
     * Audio capture loop - reads from microphone and sends to WebSocket.
     */
    private suspend fun captureAudio(record: AudioRecord) {
        val bufferSize = audioConfig.bufferSizeBytes
        val buffer = ByteArray(bufferSize)

        Timber.d("Starting audio capture loop")

        while (serviceScope.isActive && _sessionState.value == SessionState.RECORDING) {
            val bytesRead = record.read(buffer, 0, buffer.size)

            if (bytesRead > 0) {
                // Send to WebSocket
                webSocketClient?.sendAudioData(buffer.copyOf(bytesRead))
            } else {
                Timber.w("Audio read returned $bytesRead")
            }
        }

        Timber.d("Audio capture loop ended")
    }

    /**
     * Release audio resources.
     */
    private fun releaseAudioResources() {
        noiseSuppressor?.release()
        noiseSuppressor = null

        automaticGainControl?.release()
        automaticGainControl = null

        acousticEchoCanceler?.release()
        acousticEchoCanceler = null

        audioRecord?.release()
        audioRecord = null

        Timber.d("Audio resources released")
    }

    override fun onDestroy() {
        super.onDestroy()
        stopRecording()
        releaseAudioResources()
        serviceScope.cancel()
        Timber.i("AudioCaptureService destroyed")
    }

    private fun createNotification(): Notification {
        val notificationIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            notificationIntent,
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, GlassApplication.CHANNEL_ID_AUDIO_RECORDING)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(getString(R.string.notification_text_recording))
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val NOTIFICATION_ID = 1001
    }
}

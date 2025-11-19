package com.arsmartassistant.glass.model

/**
 * Audio configuration matching the PC requirements.
 */
data class AudioConfig(
    val sampleRate: Int = 16000,
    val encoding: AudioEncoding = AudioEncoding.PCM_16BIT,
    val channel: AudioChannel = AudioChannel.MONO,
    val bufferSizeBytes: Int = 3200, // 200ms chunks at 16kHz
    val enableNoiseSuppress or: Boolean = true,
    val enableAGC: Boolean = true,
    val enableAEC: Boolean = true
)

enum class AudioEncoding {
    PCM_16BIT,
    PCM_8BIT
}

enum class AudioChannel {
    MONO,
    STEREO
}

/**
 * Connection state for WebSocket.
 */
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    ERROR
}

/**
 * Recording session state.
 */
enum class SessionState {
    IDLE,
    RECORDING,
    PAUSED
}

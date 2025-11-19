package com.arsmartassistant.glass.service

import com.arsmartassistant.glass.model.ConnectionState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import timber.log.Timber
import java.net.URI
import java.nio.ByteBuffer

/**
 * WebSocket client for streaming audio data to PC server.
 */
class AudioWebSocketClient(
    serverUri: URI,
    private val onStateChanged: (ConnectionState) -> Unit
) : WebSocketClient(serverUri) {

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState

    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 5

    init {
        connectionLostTimeout = 10 // seconds
    }

    override fun onOpen(handshakedata: ServerHandshake?) {
        Timber.i("WebSocket connected to server")
        _connectionState.value = ConnectionState.CONNECTED
        onStateChanged(ConnectionState.CONNECTED)
        reconnectAttempts = 0
    }

    override fun onMessage(message: String?) {
        Timber.d("Received message: $message")
        // Handle text messages from server (e.g., commands, status updates)
    }

    override fun onClose(code: Int, reason: String?, remote: Boolean) {
        Timber.w("WebSocket closed: code=$code, reason=$reason, remote=$remote")
        _connectionState.value = ConnectionState.DISCONNECTED
        onStateChanged(ConnectionState.DISCONNECTED)

        // Attempt reconnection if closed remotely
        if (remote && reconnectAttempts < maxReconnectAttempts) {
            attemptReconnect()
        }
    }

    override fun onError(ex: Exception?) {
        Timber.e(ex, "WebSocket error")
        _connectionState.value = ConnectionState.ERROR
        onStateChanged(ConnectionState.ERROR)
    }

    /**
     * Send audio data as binary to server.
     */
    fun sendAudioData(audioData: ByteArray) {
        if (isOpen) {
            try {
                send(audioData)
            } catch (e: Exception) {
                Timber.e(e, "Failed to send audio data")
            }
        } else {
            Timber.w("Cannot send audio data: WebSocket not open")
        }
    }

    /**
     * Send audio data as ByteBuffer.
     */
    fun sendAudioData(audioBuffer: ByteBuffer) {
        if (isOpen) {
            try {
                send(audioBuffer)
            } catch (e: Exception) {
                Timber.e(e, "Failed to send audio buffer")
            }
        } else {
            Timber.w("Cannot send audio data: WebSocket not open")
        }
    }

    /**
     * Attempt to reconnect to server.
     */
    private fun attemptReconnect() {
        reconnectAttempts++
        Timber.i("Attempting reconnect ($reconnectAttempts/$maxReconnectAttempts)")

        Thread {
            try {
                Thread.sleep(2000L * reconnectAttempts) // Exponential backoff
                if (!isOpen) {
                    reconnect()
                }
            } catch (e: Exception) {
                Timber.e(e, "Reconnect failed")
            }
        }.start()
    }

    /**
     * Safely disconnect from server.
     */
    fun disconnect() {
        reconnectAttempts = maxReconnectAttempts // Prevent auto-reconnect
        try {
            close()
        } catch (e: Exception) {
            Timber.e(e, "Error during disconnect")
        }
    }
}

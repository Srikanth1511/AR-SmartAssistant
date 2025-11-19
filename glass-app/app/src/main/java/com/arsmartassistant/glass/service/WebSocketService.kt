package com.arsmartassistant.glass.service

import android.app.Service
import android.content.Intent
import android.os.IBinder

/**
 * WebSocket service stub.
 * WebSocket functionality is currently integrated into AudioCaptureService.
 * This stub exists to satisfy the AndroidManifest declaration.
 */
class WebSocketService : Service() {

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Currently unused - WebSocket handled by AudioCaptureService
        return START_NOT_STICKY
    }
}

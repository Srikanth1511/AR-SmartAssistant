package com.arsmartassistant.glass.util

import android.content.Context
import android.content.SharedPreferences
import androidx.preference.PreferenceManager

/**
 * Utility class for managing app preferences.
 */
class Preferences(context: Context) {

    private val prefs: SharedPreferences = PreferenceManager.getDefaultSharedPreferences(context)

    var serverAddress: String
        get() = prefs.getString(KEY_SERVER_ADDRESS, DEFAULT_SERVER_ADDRESS) ?: DEFAULT_SERVER_ADDRESS
        set(value) = prefs.edit().putString(KEY_SERVER_ADDRESS, value).apply()

    var serverPort: Int
        get() = prefs.getInt(KEY_SERVER_PORT, DEFAULT_SERVER_PORT)
        set(value) = prefs.edit().putInt(KEY_SERVER_PORT, value).apply()

    var autoConnect: Boolean
        get() = prefs.getBoolean(KEY_AUTO_CONNECT, false)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_CONNECT, value).apply()

    var autoStartSession: Boolean
        get() = prefs.getBoolean(KEY_AUTO_START_SESSION, false)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_START_SESSION, value).apply()

    var enablePreprocessing: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_PREPROCESSING, true)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_PREPROCESSING, value).apply()

    val serverUrl: String
        get() = "ws://$serverAddress:$serverPort"

    fun isServerConfigured(): Boolean {
        return serverAddress.isNotBlank() && serverPort > 0
    }

    companion object {
        private const val KEY_SERVER_ADDRESS = "server_address"
        private const val KEY_SERVER_PORT = "server_port"
        private const val KEY_AUTO_CONNECT = "auto_connect"
        private const val KEY_AUTO_START_SESSION = "auto_start_session"
        private const val KEY_ENABLE_PREPROCESSING = "enable_preprocessing"

        private const val DEFAULT_SERVER_ADDRESS = ""
        private const val DEFAULT_SERVER_PORT = 8765

        @Volatile
        private var instance: Preferences? = null

        fun getInstance(context: Context): Preferences {
            return instance ?: synchronized(this) {
                instance ?: Preferences(context.applicationContext).also { instance = it }
            }
        }
    }
}

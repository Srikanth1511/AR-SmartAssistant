package com.arsmartassistant.glass

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.arsmartassistant.glass.databinding.ActivitySettingsBinding
import com.arsmartassistant.glass.util.Preferences
import timber.log.Timber

/**
 * Settings activity for configuring server connection and app preferences.
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding
    private lateinit var prefs: Preferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = Preferences.getInstance(this)

        loadSettings()
        setupSaveButton()
    }

    private fun loadSettings() {
        // Load current settings
        binding.serverAddressEdit.setText(prefs.serverAddress)
        binding.serverPortEdit.setText(prefs.serverPort.toString())
        binding.autoConnectSwitch.isChecked = prefs.autoConnect
        binding.autoStartSessionSwitch.isChecked = prefs.autoStartSession
        binding.enablePreprocessingSwitch.isChecked = prefs.enablePreprocessing
    }

    private fun setupSaveButton() {
        binding.saveButton.setOnClickListener {
            saveSettings()
        }
    }

    private fun saveSettings() {
        val address = binding.serverAddressEdit.text?.toString()?.trim() ?: ""
        val portText = binding.serverPortEdit.text?.toString()?.trim() ?: "8765"

        if (address.isEmpty()) {
            Toast.makeText(this, "Server address cannot be empty", Toast.LENGTH_SHORT).show()
            return
        }

        val port = try {
            portText.toInt()
        } catch (e: NumberFormatException) {
            Toast.makeText(this, "Invalid port number", Toast.LENGTH_SHORT).show()
            return
        }

        if (port < 1 || port > 65535) {
            Toast.makeText(this, "Port must be between 1 and 65535", Toast.LENGTH_SHORT).show()
            return
        }

        // Save preferences
        prefs.serverAddress = address
        prefs.serverPort = port
        prefs.autoConnect = binding.autoConnectSwitch.isChecked
        prefs.autoStartSession = binding.autoStartSessionSwitch.isChecked
        prefs.enablePreprocessing = binding.enablePreprocessingSwitch.isChecked

        Toast.makeText(this, "Settings saved", Toast.LENGTH_SHORT).show()
        Timber.i("Settings saved: server=${prefs.serverUrl}")

        // Return to main activity
        finish()
    }
}

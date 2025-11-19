"""Flask debug UI for AR-SmartAssistant.

This is a developer-facing interface for:
- Starting/stopping recording sessions
- Viewing live transcripts with color-coded intents
- Reviewing and approving/rejecting memories
- Monitoring system metrics
- Running verification tests
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from ..config import AppConfig, load_config
from ..database.repository import BrainDatabase
from ..perception.microphone import MicrophoneStream
from ..workflows.session_runner import SessionRunner


class DebugUI:
    """Main Flask application for the debug UI."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"),
        )
        CORS(self.app)

        # Database connections
        self.db = BrainDatabase(
            brain_db_path=str(config.storage.brain_main_db),
            metrics_db_path=str(config.storage.system_metrics_db),
        )

        # Session state
        self.current_session_id: int | None = None
        self.session_runner: SessionRunner | None = None
        self.microphone: MicrophoneStream | None = None
        self.recording_thread: threading.Thread | None = None
        self.is_recording = False

        # Live data buffers for UI updates
        self.live_transcripts: list[dict[str, Any]] = []
        self.live_metrics: dict[str, Any] = {}

        # Register routes
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all Flask routes."""

        @self.app.route("/")
        def index():
            """Main dashboard page."""
            return render_template("index.html")

        @self.app.route("/api/status")
        def get_status():
            """Get current system status."""
            return jsonify({
                "is_recording": self.is_recording,
                "current_session_id": self.current_session_id,
                "storage_root": str(self.config.storage.root),
            })

        @self.app.route("/api/session/start", methods=["POST"])
        def start_session():
            """Start a new recording session."""
            if self.is_recording:
                return jsonify({"error": "Already recording"}), 400

            try:
                # Initialize session runner
                self.session_runner = SessionRunner(self.config, self.db)

                # Start microphone
                self.microphone = MicrophoneStream(self.config.audio.capture)
                self.microphone.start()

                # Start recording in background thread
                self.is_recording = True
                self.live_transcripts.clear()

                def record():
                    frames = list(self.microphone.get_frames())
                    result = self.session_runner.run_session(frames)
                    self.current_session_id = result.get("session_id")
                    self.is_recording = False

                self.recording_thread = threading.Thread(target=record, daemon=True)
                self.recording_thread.start()

                return jsonify({
                    "status": "recording_started",
                    "message": "Recording session started"
                })

            except Exception as e:
                self.is_recording = False
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/session/stop", methods=["POST"])
        def stop_session():
            """Stop the current recording session."""
            if not self.is_recording:
                return jsonify({"error": "Not currently recording"}), 400

            try:
                if self.microphone:
                    self.microphone.stop()

                # Wait for processing to complete
                if self.recording_thread:
                    self.recording_thread.join(timeout=10)

                self.is_recording = False

                return jsonify({
                    "status": "recording_stopped",
                    "session_id": self.current_session_id,
                    "message": "Recording session stopped"
                })

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/sessions")
        def list_sessions():
            """List all recorded sessions."""
            try:
                sessions = self.db.list_sessions(limit=50)
                return jsonify({"sessions": sessions})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/sessions/<int:session_id>")
        def get_session(session_id):
            """Get details for a specific session."""
            try:
                session = self.db.get_session(session_id)
                if not session:
                    return jsonify({"error": "Session not found"}), 404

                # Get raw events for this session
                events = self.db.get_raw_events(session_id)

                # Get memories for this session
                memories = self.db.get_memories(session_id)

                return jsonify({
                    "session": session,
                    "events": events,
                    "memories": memories,
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/sessions/<int:session_id>/memories")
        def get_session_memories(session_id):
            """Get all memories for a session."""
            try:
                memories = self.db.get_memories(session_id)
                return jsonify({"memories": memories})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/memories/<int:memory_id>/approve", methods=["POST"])
        def approve_memory(memory_id):
            """Approve a memory."""
            try:
                self.db.update_memory_approval(memory_id, "approved", None)
                return jsonify({"status": "approved", "memory_id": memory_id})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/memories/<int:memory_id>/reject", methods=["POST"])
        def reject_memory(memory_id):
            """Reject a memory with optional reason."""
            try:
                data = request.get_json() or {}
                reason = data.get("reason", "No reason provided")

                self.db.update_memory_approval(memory_id, "rejected", reason)

                # Log to supervised learning
                self.db.log_supervised_event(
                    session_id=None,
                    category="user_rejected_memory",
                    metadata={"memory_id": memory_id, "reason": reason},
                )

                return jsonify({"status": "rejected", "memory_id": memory_id})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/transcripts/live")
        def get_live_transcripts():
            """Get live transcript stream (for polling)."""
            return jsonify({"transcripts": self.live_transcripts[-50:]})

        @self.app.route("/api/metrics/live")
        def get_live_metrics():
            """Get live system metrics."""
            try:
                metrics = self.db.get_recent_metrics(window_sec=60)
                return jsonify({"metrics": metrics})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/devices/audio")
        def list_audio_devices():
            """List available audio input devices."""
            try:
                from ..perception.microphone import MicrophoneStream
                devices = MicrophoneStream.list_devices()
                return jsonify({"devices": devices})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    def run(self) -> None:
        """Start the Flask development server."""
        host = self.config.debug_ui.host
        port = self.config.debug_ui.port

        print(f"\n{'='*60}")
        print(f"AR-SmartAssistant Debug UI")
        print(f"{'='*60}")
        print(f"Server: http://{host}:{port}")
        print(f"Storage: {self.config.storage.root}")
        print(f"Audio Input: {self.config.audio.input_source}")
        print(f"{'='*60}\n")

        # Auto-open browser if configured
        if self.config.debug_ui.auto_open_browser:
            import webbrowser
            threading.Timer(
                1.5,
                lambda: webbrowser.open(f"http://{host}:{port}")
            ).start()

        self.app.run(
            host=host,
            port=port,
            debug=False,  # Don't use Flask debug mode for production
            threaded=True,
        )


def create_app(config_path: str | None = None) -> Flask:
    """Application factory for WSGI deployment."""
    if config_path is None:
        config_path = "config.yaml"

    config = load_config(config_path)
    ui = DebugUI(config)
    return ui.app


def main() -> None:
    """Main entry point for running the debug UI."""
    import argparse

    parser = argparse.ArgumentParser(description="AR-SmartAssistant Debug UI")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}")
        print("Please create config.yaml from config.yaml.example")
        return

    # Initialize and run
    ui = DebugUI(config)
    ui.run()


if __name__ == "__main__":
    main()

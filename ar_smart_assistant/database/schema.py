"""SQLite schema helpers for the AR-SmartAssistant reference implementation."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


BRAIN_TABLES = {
    "model_versions": """
        CREATE TABLE IF NOT EXISTS model_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_tag TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            asr_model TEXT NOT NULL,
            speaker_model TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            config_snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """,
    "config_change_log": """
        CREATE TABLE IF NOT EXISTS config_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            old_config_hash TEXT NOT NULL,
            new_config_hash TEXT NOT NULL,
            change_summary TEXT NOT NULL
        );
    """,
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,
            approval_timestamp TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(model_version_id) REFERENCES model_versions(id)
        );
    """,
    "raw_events": """
        CREATE TABLE IF NOT EXISTS raw_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload TEXT NOT NULL,
            predicted_intent TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
    """,
    "audio_segments": """
        CREATE TABLE IF NOT EXISTS audio_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_sec REAL NOT NULL,
            raw_events_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(session_id) REFERENCES sessions(id),
            FOREIGN KEY(raw_events_id) REFERENCES raw_events(id)
        );
    """,
    "speaker_profiles": """
        CREATE TABLE IF NOT EXISTS speaker_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            embedding BLOB NOT NULL,
            enrollment_quality REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            enrollment_date TEXT NOT NULL,
            last_matched TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """,
    "persons": """
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            primary_speaker_profile_id INTEGER,
            primary_face_profile_id INTEGER,
            voice_embedding BLOB,
            face_embeddings TEXT NOT NULL DEFAULT '[]',
            relationship_tags TEXT NOT NULL,
            first_seen_at TEXT,
            last_seen_at TEXT,
            notes TEXT,
            notes_vector_ids TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(primary_speaker_profile_id) REFERENCES speaker_profiles(id)
        );
    """,
    "locations": """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            lat REAL,
            lon REAL,
            radius_m REAL,
            type TEXT NOT NULL
        );
    """,
    "conversations": """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participants TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            location_id INTEGER,
            topics TEXT NOT NULL DEFAULT '[]',
            raw_transcript TEXT NOT NULL,
            summary_text TEXT,
            summary_vector BLOB,
            importance REAL NOT NULL DEFAULT 0.5,
            privacy TEXT NOT NULL DEFAULT 'private',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(location_id) REFERENCES locations(id)
        );
    """,
    "memory_items": """
        CREATE TABLE IF NOT EXISTS memory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            source_event_id INTEGER NOT NULL,
            source_conversation_id INTEGER,
            timestamp TEXT NOT NULL,
            person_id INTEGER,
            speaker_id INTEGER,
            speaker_profile_id INTEGER,
            location_id INTEGER,
            text TEXT NOT NULL,
            topic_tags TEXT NOT NULL DEFAULT '[]',
            task_tags TEXT NOT NULL DEFAULT '[]',
            domain_tags TEXT NOT NULL DEFAULT '[]',
            modality_tags TEXT NOT NULL DEFAULT '[]',
            importance REAL NOT NULL,
            urgency TEXT,
            deadline TEXT,
            repetition_count INTEGER NOT NULL DEFAULT 0,
            last_accessed_at TEXT,
            emotion TEXT,
            vector BLOB,
            predicted_intent TEXT NOT NULL,
            privacy_level TEXT NOT NULL DEFAULT 'private',
            shareable_to TEXT,
            approval_status TEXT NOT NULL,
            rejection_reason TEXT,
            llm_suggested_issue TEXT,
            confidence_asr REAL,
            confidence_speaker REAL,
            confidence_vision REAL,
            confidence_face REAL,
            confidence_llm REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id),
            FOREIGN KEY(source_event_id) REFERENCES raw_events(id),
            FOREIGN KEY(source_conversation_id) REFERENCES conversations(id),
            FOREIGN KEY(person_id) REFERENCES persons(id),
            FOREIGN KEY(speaker_id) REFERENCES persons(id),
            FOREIGN KEY(location_id) REFERENCES locations(id)
        );
    """,
    "shopping_items": """
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            source_memory_id INTEGER NOT NULL,
            related_memory_id INTEGER,
            name TEXT NOT NULL,
            quantity TEXT,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_updated_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id),
            FOREIGN KEY(source_memory_id) REFERENCES memory_items(id),
            FOREIGN KEY(related_memory_id) REFERENCES memory_items(id)
        );
    """,
    "supervised_learning_events": """
        CREATE TABLE IF NOT EXISTS supervised_learning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            category TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            artifact_path TEXT,
            metadata TEXT NOT NULL,
            reviewed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
    """,
}


METRICS_TABLES = {
    "system_metrics": """
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            timestamp TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metadata TEXT NOT NULL
        );
    """,
}


class SchemaManager:
    """Apply schema definitions to SQLite files."""

    def __init__(self, brain_path: Path, metrics_path: Path) -> None:
        self.brain_path = brain_path
        self.metrics_path = metrics_path

    def initialize(self) -> None:
        """Create both schemas and seed defaults."""

        with sqlite3.connect(self.brain_path) as brain:
            self._execute_statements(brain, BRAIN_TABLES.values())
            brain.execute(
                "INSERT INTO locations (label, type)"
                " SELECT 'unknown', 'unknown'"
                " WHERE NOT EXISTS (SELECT 1 FROM locations WHERE label='unknown')"
            )
        with sqlite3.connect(self.metrics_path) as metrics:
            self._execute_statements(metrics, METRICS_TABLES.values())

    @staticmethod
    def _execute_statements(conn: sqlite3.Connection, statements: Iterable[str]) -> None:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


__all__ = ["SchemaManager", "BRAIN_TABLES", "METRICS_TABLES"]

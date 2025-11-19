"""SQLite repository primitives for the AR-SmartAssistant prototype."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Sequence

from .schema import SchemaManager


@dataclass
class ModelVersion:
    version_tag: str
    llm_model: str
    asr_model: str
    speaker_model: str
    prompt_hash: str
    config_snapshot: str


@dataclass
class SessionRecord:
    model_version_id: int
    start_time: str
    status: str
    end_time: str | None = None
    approval_timestamp: str | None = None
    notes: str | None = None


@dataclass
class RawEventRecord:
    session_id: int
    event_type: str
    timestamp: str
    payload: Mapping[str, Any]
    predicted_intent: str | None = None


@dataclass
class AudioSegmentRecord:
    session_id: int
    file_path: str
    start_time: str
    end_time: str
    duration_sec: float
    raw_events_id: int | None = None


@dataclass
class MemoryItemRecord:
    session_id: int
    source_event_id: int
    timestamp: str
    text: str
    topic_tags: Sequence[str]
    modality_tags: Sequence[str]
    importance: float
    predicted_intent: str
    approval_status: str
    task_tags: Sequence[str] = ()
    domain_tags: Sequence[str] = ()
    source_conversation_id: int | None = None
    person_id: int | None = None
    speaker_id: int | None = None
    speaker_profile_id: int | None = None
    location_id: int | None = None
    urgency: str | None = None
    deadline: str | None = None
    repetition_count: int = 0
    last_accessed_at: str | None = None
    privacy_level: str | None = None
    shareable_to: Sequence[str] | None = None
    emotion: str | None = None
    vector: bytes | None = None
    rejection_reason: str | None = None
    llm_suggested_issue: str | None = None
    confidence_asr: float | None = None
    confidence_speaker: float | None = None
    confidence_vision: float | None = None
    confidence_face: float | None = None
    confidence_llm: float | None = None


@dataclass
class SupervisedLearningEvent:
    session_id: int | None
    category: str
    timestamp: str
    metadata: Mapping[str, Any]
    artifact_path: str | None = None
    reviewed: bool = False


@dataclass
class SystemMetric:
    session_id: int | None
    metric_name: str
    metric_value: float
    timestamp: str
    metadata: Mapping[str, Any]


class BrainDatabase:
    """High level repository for both SQLite files.

    The constructor initializes both schema files to guarantee that downstream
    components can rely on required tables. Each method is intentionally small
    and synchronous so it can be wrapped by higher level async orchestrators.
    """

    def __init__(self, brain_path: Path, metrics_path: Path) -> None:
        self.brain_path = brain_path
        self.metrics_path = metrics_path
        SchemaManager(brain_path, metrics_path).initialize()

    @contextmanager
    def _brain_transaction(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.brain_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _metrics_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.metrics_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def register_model_version(self, record: ModelVersion) -> int:
        with self._brain_transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_versions (
                    version_tag, llm_model, asr_model, speaker_model, prompt_hash, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.version_tag,
                    record.llm_model,
                    record.asr_model,
                    record.speaker_model,
                    record.prompt_hash,
                    record.config_snapshot,
                ),
            )
            return cursor.lastrowid

    def start_session(self, record: SessionRecord) -> int:
        with self._brain_transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (
                    model_version_id, start_time, end_time, status, approval_timestamp, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.model_version_id,
                    record.start_time,
                    record.end_time,
                    record.status,
                    record.approval_timestamp,
                    record.notes,
                ),
            )
            return cursor.lastrowid

    def update_session_status(self, session_id: int, status: str, end_time: str | None = None) -> None:
        with self._brain_transaction() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, end_time=COALESCE(?, end_time) WHERE id=?",
                (status, end_time, session_id),
            )

    def update_memory_status(
        self,
        memory_id: int,
        approval_status: str,
        rejection_reason: str | None,
    ) -> None:
        with self._brain_transaction() as conn:
            conn.execute(
                "UPDATE memory_items SET approval_status=?, rejection_reason=?, reviewed_at=? WHERE id=?",
                (approval_status, rejection_reason, utcnow(), memory_id),
            )

    def memory_status_summary(self, session_id: int) -> dict[str, int]:
        with sqlite3.connect(self.brain_path) as conn:
            rows = conn.execute(
                "SELECT approval_status, COUNT(*) FROM memory_items WHERE session_id=? GROUP BY approval_status",
                (session_id,),
            ).fetchall()
        return {row[0]: row[1] for row in rows}

    def insert_raw_event(self, record: RawEventRecord) -> int:
        payload_json = json.dumps(record.payload, sort_keys=True)
        with self._brain_transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO raw_events (session_id, event_type, timestamp, payload, predicted_intent)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.event_type,
                    record.timestamp,
                    payload_json,
                    record.predicted_intent,
                ),
            )
            return cursor.lastrowid

    def insert_audio_segment(self, record: AudioSegmentRecord) -> int:
        with self._brain_transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audio_segments (
                    session_id, file_path, start_time, end_time, duration_sec, raw_events_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.file_path,
                    record.start_time,
                    record.end_time,
                    record.duration_sec,
                    record.raw_events_id,
                ),
            )
            return cursor.lastrowid

    def attach_audio_segment_to_event(self, segment_id: int, raw_event_id: int) -> None:
        with self._brain_transaction() as conn:
            conn.execute(
                "UPDATE audio_segments SET raw_events_id=? WHERE id=?",
                (raw_event_id, segment_id),
            )

    def insert_memory_item(self, record: MemoryItemRecord) -> int:
        topic_tags_json = json.dumps(list(record.topic_tags), sort_keys=True)
        task_tags_json = json.dumps(list(record.task_tags), sort_keys=True)
        domain_tags_json = json.dumps(list(record.domain_tags), sort_keys=True)
        modality_tags_json = json.dumps(list(record.modality_tags), sort_keys=True)
        privacy_level = record.privacy_level or "private"
        shareable_to_json = (
            json.dumps(list(record.shareable_to), sort_keys=True)
            if record.shareable_to is not None
            else None
        )
        columns = [
            "session_id",
            "source_event_id",
            "source_conversation_id",
            "timestamp",
            "person_id",
            "speaker_id",
            "speaker_profile_id",
            "location_id",
            "text",
            "topic_tags",
            "task_tags",
            "domain_tags",
            "modality_tags",
            "importance",
            "urgency",
            "deadline",
            "repetition_count",
            "last_accessed_at",
            "emotion",
            "vector",
            "predicted_intent",
            "privacy_level",
            "shareable_to",
            "approval_status",
            "rejection_reason",
            "llm_suggested_issue",
            "confidence_asr",
            "confidence_speaker",
            "confidence_vision",
            "confidence_face",
            "confidence_llm",
        ]
        values = (
            record.session_id,
            record.source_event_id,
            record.source_conversation_id,
            record.timestamp,
            record.person_id,
            record.speaker_id,
            record.speaker_profile_id,
            record.location_id,
            record.text,
            topic_tags_json,
            task_tags_json,
            domain_tags_json,
            modality_tags_json,
            record.importance,
            record.urgency,
            record.deadline,
            record.repetition_count,
            record.last_accessed_at,
            record.emotion,
            record.vector,
            record.predicted_intent,
            privacy_level,
            shareable_to_json,
            record.approval_status,
            record.rejection_reason,
            record.llm_suggested_issue,
            record.confidence_asr,
            record.confidence_speaker,
            record.confidence_vision,
            record.confidence_face,
            record.confidence_llm,
        )
        placeholders = ", ".join(["?"] * len(columns))
        with self._brain_transaction() as conn:
            cursor = conn.execute(
                f"INSERT INTO memory_items ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            return cursor.lastrowid

    def log_supervised_event(self, record: SupervisedLearningEvent) -> int:
        with self._brain_transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO supervised_learning_events (
                    session_id, category, timestamp, artifact_path, metadata, reviewed
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.category,
                    record.timestamp,
                    record.artifact_path,
                    json.dumps(record.metadata, sort_keys=True),
                    int(record.reviewed),
                ),
            )
            return cursor.lastrowid

    def log_metric(self, record: SystemMetric) -> int:
        with self._metrics_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO system_metrics (session_id, timestamp, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.timestamp,
                    record.metric_name,
                    record.metric_value,
                    json.dumps(record.metadata, sort_keys=True),
                ),
            )
            return cursor.lastrowid

    def get_session_events(self, session_id: int) -> list[Dict[str, Any]]:
        with sqlite3.connect(self.brain_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, event_type, timestamp, payload, predicted_intent FROM raw_events WHERE session_id=? ORDER BY timestamp",
                (session_id,),
            ).fetchall()
        events: list[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload"])
            events.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "payload": payload,
                    "predicted_intent": row["predicted_intent"],
                }
            )
        return events

    def list_memory_items(self, session_id: int) -> list[Dict[str, Any]]:
        with sqlite3.connect(self.brain_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memory_items WHERE session_id=? ORDER BY timestamp",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sessions(self, limit: int = 50) -> list[Dict[str, Any]]:
        """List recent sessions ordered by start time (most recent first)."""
        with sqlite3.connect(self.brain_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT s.*, mv.version_tag, mv.llm_model, mv.asr_model
                FROM sessions s
                JOIN model_versions mv ON s.model_version_id = mv.id
                ORDER BY s.start_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: int) -> Dict[str, Any] | None:
        """Get a single session by ID with model version details."""
        with sqlite3.connect(self.brain_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT s.*, mv.version_tag, mv.llm_model, mv.asr_model, mv.speaker_model
                FROM sessions s
                JOIN model_versions mv ON s.model_version_id = mv.id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_raw_events(self, session_id: int) -> list[Dict[str, Any]]:
        """Get all raw events for a session (alias for get_session_events)."""
        return self.get_session_events(session_id)

    def get_memories(self, session_id: int) -> list[Dict[str, Any]]:
        """Get all memory items for a session (alias for list_memory_items)."""
        return self.list_memory_items(session_id)

    def update_memory_approval(
        self,
        memory_id: int,
        approval_status: str,
        reason: str | None = None,
    ) -> None:
        """Update memory approval status with optional reason (wrapper for update_memory_status)."""
        self.update_memory_status(memory_id, approval_status, reason)

    def get_recent_metrics(self, window_sec: int = 60) -> list[Dict[str, Any]]:
        """Get system metrics from the last N seconds."""
        with sqlite3.connect(self.metrics_path) as conn:
            conn.row_factory = sqlite3.Row
            # Calculate timestamp threshold (SQLite datetime arithmetic)
            rows = conn.execute(
                """
                SELECT * FROM system_metrics
                WHERE datetime(timestamp) >= datetime('now', '-' || ? || ' seconds')
                ORDER BY timestamp DESC
                """,
                (window_sec,),
            ).fetchall()
        metrics: list[Dict[str, Any]] = []
        for row in rows:
            metric_dict = dict(row)
            # Parse JSON metadata if present
            if metric_dict.get("metadata"):
                try:
                    metric_dict["metadata"] = json.loads(metric_dict["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            metrics.append(metric_dict)
        return metrics


def utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


__all__ = [
    "AudioSegmentRecord",
    "BrainDatabase",
    "MemoryItemRecord",
    "ModelVersion",
    "RawEventRecord",
    "SessionRecord",
    "SupervisedLearningEvent",
    "SystemMetric",
    "utcnow",
]

"""Orchestrates the perception → LLM → memory pipeline for a single session."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterable, Sequence

from ..config import AppConfig
from ..database.repository import BrainDatabase, ModelVersion, SessionRecord, utcnow
from ..logging_utils import log_metric
from ..memory.approvals import ApprovalWorkflow
from ..llm.orchestrator import LLMOrchestrator
from ..perception.audio_pipeline import AudioFrame, AudioPipeline


class SessionRunner:
    """Small coordinator used by tests and the CLI."""

    def __init__(self, config: AppConfig, database: BrainDatabase) -> None:
        self.config = config
        self.database = database
        self.audio_pipeline = AudioPipeline(config, database)
        self.orchestrator = LLMOrchestrator(database)
        self.approval_workflow = ApprovalWorkflow(database)
        self.model_version_id = self._ensure_model_version()

    def _ensure_model_version(self) -> int:
        snapshot = asdict(self.config)
        snapshot["storage_root"] = str(self.config.storage_root)
        payload = ModelVersion(
            version_tag="v0.1.0",
            llm_model="heuristic",
            asr_model=self.config.audio.asr.model,
            speaker_model=self.config.audio.speaker_id.model,
            prompt_hash="heuristic_v1",
            config_snapshot=json.dumps(snapshot, sort_keys=True, default=str),
        )
        return self.database.register_model_version(payload)

    def run_session(self, frames: Iterable[AudioFrame]) -> dict[str, Sequence[int]]:
        session_id = self.database.start_session(
            SessionRecord(
                model_version_id=self.model_version_id,
                start_time=utcnow(),
                status="active",
            )
        )
        transcripts = self.audio_pipeline.process_frames(session_id, frames)
        log_metric("transcript_count", len(transcripts), {"session_id": session_id})
        actions = self.orchestrator.propose_actions(session_id)
        memory_ids = self.orchestrator.persist_memories(session_id, actions)
        self.database.update_session_status(session_id, "pending_review", end_time=utcnow())
        return {"session_id": session_id, "memory_ids": memory_ids}


__all__ = ["SessionRunner"]

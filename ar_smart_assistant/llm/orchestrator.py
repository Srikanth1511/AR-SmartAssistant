"""LLM-inspired heuristics for the POC orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..database.repository import BrainDatabase, MemoryItemRecord, utcnow


@dataclass
class OrchestratedAction:
    action_type: str
    text: str
    tags: list[str]
    importance: float
    predicted_intent: str
    issues: list[str]
    confidence: float
    event_id: int


class LLMOrchestrator:
    """Transforms transcript events into proposed memories.

    The reference implementation uses deterministic heuristics to keep tests
    stable while still exercising the approval and persistence layers.
    """

    def __init__(self, database: BrainDatabase) -> None:
        self.database = database

    def propose_actions(self, session_id: int) -> list[OrchestratedAction]:
        events = self.database.get_session_events(session_id)
        actions: list[OrchestratedAction] = []
        for event in events:
            payload = event["payload"]
            transcript = payload.get("transcript", "")
            intent = event.get("predicted_intent") or "ignore"
            if intent == "ignore" or not transcript:
                continue
            text = transcript.capitalize()
            issues = []
            confidence = min(payload.get("asr_confidence", 0.5), payload.get("speaker_confidence", 0.5))
            if payload.get("asr_confidence", 0) < 0.5:
                issues.append("low_asr_confidence")
            if payload.get("speaker_confidence", 0) < 0.7:
                issues.append("low_speaker_confidence")
            importance = 0.6 if intent == "memory_candidate" else 0.8
            actions.append(
                OrchestratedAction(
                    action_type="add_memory",
                    text=text,
                    tags=[intent.replace("_candidate", "")],
                    importance=importance,
                    predicted_intent=intent,
                    issues=issues,
                    confidence=confidence,
                    event_id=event["id"],
                )
            )
        return actions

    def persist_memories(self, session_id: int, actions: Iterable[OrchestratedAction]) -> list[int]:
        memory_ids: list[int] = []
        events = {event["id"]: event for event in self.database.get_session_events(session_id)}
        for action in actions:
            event = events.get(action.event_id)
            if event is None:
                continue
            record = MemoryItemRecord(
                session_id=session_id,
                source_event_id=event["id"],
                timestamp=utcnow(),
                text=action.text,
                topic_tags=action.tags,
                modality_tags=["audio"],
                importance=action.importance,
                predicted_intent=action.predicted_intent,
                approval_status="pending",
                rejection_reason=None,
                llm_suggested_issue=",".join(action.issues) if action.issues else None,
                confidence_asr=event["payload"].get("asr_confidence"),
                confidence_speaker=event["payload"].get("speaker_confidence"),
                confidence_llm=action.confidence,
            )
            memory_ids.append(self.database.insert_memory_item(record))
        return memory_ids


__all__ = ["LLMOrchestrator", "OrchestratedAction"]

"""Approval utilities for per-memory review."""
from __future__ import annotations

from dataclasses import dataclass

from ..database.repository import BrainDatabase, SupervisedLearningEvent, utcnow


@dataclass
class ApprovalResult:
    session_status: str
    memory_counts: dict[str, int]


class ApprovalWorkflow:
    """Encapsulates approval and rejection paths."""

    def __init__(self, database: BrainDatabase) -> None:
        self.database = database

    def approve(self, session_id: int, memory_id: int) -> ApprovalResult:
        self.database.update_memory_status(memory_id, "approved", None)
        return self._update_session_status(session_id)

    def reject(self, session_id: int, memory_id: int, reason: str) -> ApprovalResult:
        rejection_reason = reason or "unspecified"
        self.database.update_memory_status(memory_id, "rejected", rejection_reason)
        self.database.log_supervised_event(
            SupervisedLearningEvent(
                session_id=session_id,
                category="user_rejected_memory",
                timestamp=utcnow(),
                artifact_path=None,
                metadata={"memory_id": memory_id, "reason": rejection_reason},
            )
        )
        return self._update_session_status(session_id)

    def _update_session_status(self, session_id: int) -> ApprovalResult:
        summary = self.database.memory_status_summary(session_id)
        approved = summary.get("approved", 0)
        pending = summary.get("pending", 0)
        rejected = summary.get("rejected", 0)
        if approved > 0 and pending == 0 and rejected == 0:
            status = "fully_approved"
        elif approved > 0:
            status = "partially_approved"
        elif rejected > 0 and pending == 0:
            status = "rejected"
        else:
            status = "pending_review"
        self.database.update_session_status(session_id, status)
        return ApprovalResult(session_status=status, memory_counts=summary)


__all__ = ["ApprovalWorkflow", "ApprovalResult"]

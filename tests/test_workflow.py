from pathlib import Path
from typing import Iterable

from ar_smart_assistant.config import DEFAULT_CONFIG
from ar_smart_assistant.database.repository import BrainDatabase
from ar_smart_assistant.memory.approvals import ApprovalWorkflow
from ar_smart_assistant.perception.audio_pipeline import AudioFrame
from ar_smart_assistant.workflows.session_runner import SessionRunner


def build_frames() -> Iterable[AudioFrame]:
    frames = []
    for index in range(30):
        samples = [0.8 if index % 2 == 0 else 0.1 for _ in range(5)]
        frames.append(AudioFrame(timestamp=index * 0.03, samples=samples))
    return frames


def test_session_runner_creates_memories(tmp_path: Path) -> None:
    brain = tmp_path / "brain.db"
    metrics = tmp_path / "metrics.db"
    db = BrainDatabase(brain, metrics)
    runner = SessionRunner(DEFAULT_CONFIG, db)
    result = runner.run_session(build_frames())
    assert result["memory_ids"], "expected at least one proposed memory"


def test_approval_workflow_updates_status(tmp_path: Path) -> None:
    brain = tmp_path / "brain.db"
    metrics = tmp_path / "metrics.db"
    db = BrainDatabase(brain, metrics)
    runner = SessionRunner(DEFAULT_CONFIG, db)
    result = runner.run_session(build_frames())
    workflow = ApprovalWorkflow(db)
    memory_id = result["memory_ids"][0]
    approval = workflow.approve(result["session_id"], memory_id)
    assert approval.session_status in {"partially_approved", "fully_approved"}

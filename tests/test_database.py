import json
from pathlib import Path

import pytest

from ar_smart_assistant.database.repository import (
    BrainDatabase,
    MemoryItemRecord,
    ModelVersion,
    RawEventRecord,
    SessionRecord,
    SupervisedLearningEvent,
    utcnow,
)


@pytest.fixture
def database(tmp_path: Path) -> BrainDatabase:
    brain = tmp_path / "brain.db"
    metrics = tmp_path / "metrics.db"
    return BrainDatabase(brain, metrics)


def register_defaults(db: BrainDatabase) -> int:
    return db.register_model_version(
        ModelVersion(
            version_tag="v-test",
            llm_model="heuristic",
            asr_model="mock",
            speaker_model="mock",
            prompt_hash="hash",
            config_snapshot=json.dumps({"unit": "test"}),
        )
    )


def test_transaction_rolls_back_on_fk_error(database: BrainDatabase) -> None:
    with pytest.raises(Exception):
        database.insert_raw_event(
            RawEventRecord(
                session_id=999,
                event_type="transcript",
                timestamp=utcnow(),
                payload={"transcript": "hello"},
            )
        )


def test_memory_status_summary(database: BrainDatabase) -> None:
    model_version_id = register_defaults(database)
    session_id = database.start_session(
        SessionRecord(model_version_id=model_version_id, start_time=utcnow(), status="active")
    )
    raw_event_id = database.insert_raw_event(
        RawEventRecord(
            session_id=session_id,
            event_type="transcript",
            timestamp=utcnow(),
            payload={"transcript": "remember"},
        )
    )
    memory_id = database.insert_memory_item(
        MemoryItemRecord(
            session_id=session_id,
            source_event_id=raw_event_id,
            timestamp=utcnow(),
            text="Remember", 
            topic_tags=["memory"],
            modality_tags=["audio"],
            importance=0.7,
            predicted_intent="memory_candidate",
            approval_status="pending",
        )
    )
    summary = database.memory_status_summary(session_id)
    assert summary == {"pending": 1}
    database.update_memory_status(memory_id, "approved", None)
    summary_after = database.memory_status_summary(session_id)
    assert summary_after.get("approved") == 1


def test_memory_item_captures_extended_metadata(database: BrainDatabase) -> None:
    model_version_id = register_defaults(database)
    session_id = database.start_session(
        SessionRecord(model_version_id=model_version_id, start_time=utcnow(), status="active")
    )
    raw_event_id = database.insert_raw_event(
        RawEventRecord(
            session_id=session_id,
            event_type="transcript",
            timestamp=utcnow(),
            payload={"transcript": "pick up sugar"},
        )
    )
    database.insert_memory_item(
        MemoryItemRecord(
            session_id=session_id,
            source_event_id=raw_event_id,
            timestamp=utcnow(),
            text="Add sugar to shopping list",
            topic_tags=["cooking"],
            modality_tags=["from_audio"],
            importance=0.8,
            predicted_intent="shopping_item",
            approval_status="pending",
            task_tags=["shopping"],
            domain_tags=["family"],
            shareable_to=["spouse"],
            urgency="high",
            deadline=utcnow(),
            emotion="concerned",
            repetition_count=2,
            last_accessed_at=utcnow(),
            privacy_level="sensitive",
            confidence_asr=0.9,
            confidence_speaker=0.85,
            confidence_vision=0.5,
            confidence_face=0.4,
            confidence_llm=0.95,
        )
    )
    items = database.list_memory_items(session_id)
    assert len(items) == 1
    row = items[0]
    assert json.loads(row["task_tags"]) == ["shopping"]
    assert json.loads(row["domain_tags"]) == ["family"]
    assert row["urgency"] == "high"
    assert row["privacy_level"] == "sensitive"
    assert json.loads(row["shareable_to"]) == ["spouse"]


def test_supervised_event_logging(database: BrainDatabase) -> None:
    event_id = database.log_supervised_event(
        SupervisedLearningEvent(
            session_id=None,
            category="llm_json_error",
            timestamp=utcnow(),
            metadata={"details": "bad json"},
        )
    )
    assert isinstance(event_id, int)

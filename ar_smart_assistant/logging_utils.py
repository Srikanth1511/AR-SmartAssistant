"""Shared logging helpers that enforce the privacy guidance from CONTRIBUTING."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Mapping


LOGGER_NAME = "ar_smart_assistant"
logger = logging.getLogger(LOGGER_NAME)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structured logging for the app."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def sanitize_identifier(raw: str) -> str:
    """Return a 16-char hash to avoid leaking PII in logs."""

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:16]


def log_metric(name: str, value: float, metadata: Mapping[str, Any] | None = None) -> None:
    """Emit a structured metric log."""

    payload = {
        "metric": name,
        "value": value,
        "metadata": metadata or {},
        "ts": datetime.utcnow().isoformat(timespec="milliseconds"),
    }
    logger.info("METRIC %s", json.dumps(payload, sort_keys=True))


def log_event(event_type: str, metadata: Mapping[str, Any]) -> None:
    """Log sanitized event metadata."""

    safe_metadata = metadata.copy()
    if "audio_path" in safe_metadata:
        safe_metadata["audio_path_hash"] = sanitize_identifier(str(safe_metadata.pop("audio_path")))
    logger.info("EVENT %s", json.dumps(safe_metadata, sort_keys=True))


__all__ = ["configure_logging", "log_event", "log_metric", "logger", "sanitize_identifier"]

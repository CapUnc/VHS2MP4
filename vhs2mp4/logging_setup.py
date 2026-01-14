"""Structured logging configuration."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """Simple JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.__dict__.get("event"):
            payload["event"] = record.__dict__["event"]
        if record.__dict__.get("context"):
            payload["context"] = record.__dict__["context"]
        return json.dumps(payload)


def setup_logging(logs_dir: Path) -> None:
    """Configure logging to stdout and a file in the data directory."""

    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "app.log"

    formatter = JsonFormatter()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(logfile)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

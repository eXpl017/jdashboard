"""Structured logging shared by the web app and the CLI scripts.

Logs are emitted as one JSON object per line so they can be grepped or piped
into a log collector without parsing free text.
"""

import json
import logging

from app.config import settings


class JsonLogFormatter(logging.Formatter):
    """Format a log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str | None = None) -> None:
    """Install the JSON formatter on the root logger."""
    resolved = (level or settings.log_level or "INFO").upper()
    numeric = getattr(logging, resolved, logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.setLevel(numeric)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)

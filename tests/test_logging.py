import json
import logging

from app.logging_config import JsonLogFormatter, configure_logging


def _record(message: str, level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="app.services.refresh",
        level=level,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_formatter_emits_single_line_json() -> None:
    formatter = JsonLogFormatter()

    output = formatter.format(_record("refresh started"))

    assert "\n" not in output
    payload = json.loads(output)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.services.refresh"
    assert payload["message"] == "refresh started"
    assert "ts" in payload


def test_json_formatter_includes_traceback() -> None:
    formatter = JsonLogFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record("source failed", logging.ERROR)
        record.exc_info = sys.exc_info()

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "ERROR"
    assert "ValueError: boom" in payload["exc"]


def test_configure_logging_sets_level_and_handler() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        configure_logging("DEBUG")

        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)

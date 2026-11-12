from datetime import UTC, datetime

from scripts.inspect_source import _since


def test_since_is_timezone_aware_utc() -> None:
    cutoff = _since(3)

    assert cutoff.tzinfo is not None
    assert cutoff.utcoffset().total_seconds() == 0
    assert cutoff < datetime.now(UTC)

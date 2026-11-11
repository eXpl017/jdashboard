import re
from datetime import UTC, date, datetime, time, timedelta, timezone

from dateutil import parser as date_parser

JST = timezone(timedelta(hours=9))

_JAPANESE_DATE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _ensure_aware(value: datetime, default_tz: timezone = JST) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=default_tz)
    return value


def parse_iso_datetime(value: str | None, default_tz: timezone = JST) -> datetime | None:
    """Parse an ISO-8601 timestamp. Naive values are assumed to be in ``default_tz``."""
    if not value:
        return None
    try:
        parsed = date_parser.isoparse(value.strip())
    except (ValueError, TypeError, OverflowError):
        return None
    return _ensure_aware(parsed, default_tz)


def parse_date_only(value: str | None, tz: timezone = JST) -> datetime | None:
    """Parse a date-only value into midnight in ``tz``."""
    if not value:
        return None
    try:
        parsed_date: date = date_parser.parse(value.strip()).date()
    except (ValueError, TypeError, OverflowError):
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=tz)


def parse_japanese_date(value: str | None, tz: timezone = JST) -> datetime | None:
    """Parse ``2026年11月9日`` or fall back to a generic date parse."""
    if not value:
        return None
    match = _JAPANESE_DATE.search(value)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return datetime(year, month, day, tzinfo=tz)
    return parse_date_only(value, tz)


def to_utc(value: datetime, default_tz: timezone = JST) -> datetime:
    """Convert an aware datetime to UTC; naive values are assumed to be in ``default_tz``."""
    return _ensure_aware(value, default_tz).astimezone(UTC)


def days_ago(days: int, tz: timezone = JST) -> datetime:
    """Return the UTC timestamp for ``days`` ago in ``tz``."""
    return (datetime.now(tz) - timedelta(days=days)).astimezone(UTC)

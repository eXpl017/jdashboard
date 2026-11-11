from datetime import UTC, datetime

from app.services.dates import (
    JST,
    days_ago,
    parse_date_only,
    parse_iso_datetime,
    parse_japanese_date,
    to_utc,
)


def test_parse_iso_datetime_converts_jst_to_utc():
    parsed = parse_iso_datetime("2026-11-09T10:00:00+09:00")
    assert parsed == datetime(2026, 11, 9, 1, 0, tzinfo=UTC)


def test_parse_iso_datetime_assumes_jst_for_naive_values():
    parsed = parse_iso_datetime("2026-11-09T10:00:00")
    assert parsed == datetime(2026, 11, 9, 10, 0, tzinfo=JST)


def test_parse_date_only_uses_jst_midnight():
    parsed = parse_date_only("2026-11-09")
    assert parsed == datetime(2026, 11, 9, 0, 0, tzinfo=JST)


def test_parse_japanese_date():
    parsed = parse_japanese_date("2026年11月9日")
    assert parsed == datetime(2026, 11, 9, 0, 0, tzinfo=JST)


def test_parse_japanese_date_falls_back_to_generic_date():
    parsed = parse_japanese_date("2026-11-09")
    assert parsed == datetime(2026, 11, 9, 0, 0, tzinfo=JST)


def test_to_utc_treats_naive_as_jst():
    assert to_utc(datetime(2026, 11, 9, 9, 0)) == datetime(2026, 11, 9, 0, 0, tzinfo=UTC)


def test_invalid_values_return_none():
    assert parse_iso_datetime("not a date") is None
    assert parse_iso_datetime("") is None
    assert parse_date_only("") is None
    assert parse_japanese_date(None) is None


def test_days_ago_is_in_the_past():
    assert days_ago(3) < datetime.now(UTC)

"""Tests for the SuomiJazz zero-duration patch."""

from datetime import datetime, timedelta, timezone

from icalendar import Event

from jazz_calendar.patch import patch_event

UTC = timezone.utc


def _make(source: str, start: datetime, end: datetime) -> Event:
    e = Event()
    e["UID"] = "u@x"
    e["DTSTART"] = start
    e["DTEND"] = end
    e["X-JAZZHKI-SOURCE"] = source
    return e


def test_patch_suomijazz_dtstart_equals_dtend() -> None:
    start = datetime(2026, 4, 30, 14, 0, tzinfo=UTC)
    e = _make("suomijazz", start, start)
    patch_event(e)
    assert e["DTEND"].dt == start + timedelta(hours=2)
    flag = e["DTEND"].params["X-JAZZHKI-DURATION-ESTIMATED"]
    assert str(flag).lower() == "true"


def test_patch_suomijazz_real_duration_left_alone() -> None:
    start = datetime(2026, 4, 30, 14, 0, tzinfo=UTC)
    end = datetime(2026, 4, 30, 16, 0, tzinfo=UTC)
    e = _make("suomijazz", start, end)
    patch_event(e)
    assert e["DTEND"].dt == end
    assert "X-JAZZHKI-DURATION-ESTIMATED" not in e["DTEND"].params


def test_patch_gcal_event_unchanged() -> None:
    start = datetime(2026, 4, 30, 14, 0, tzinfo=UTC)
    e = _make("gcal", start, start)
    patch_event(e)
    assert e["DTEND"].dt == start
    assert "X-JAZZHKI-DURATION-ESTIMATED" not in e["DTEND"].params

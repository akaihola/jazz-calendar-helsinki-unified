"""Tests for the time-window filter."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event

from jazz_calendar.window import in_window

FIXTURES = Path(__file__).parent / "fixtures"

NOW = datetime(2026, 4, 27, 6, 0, tzinfo=timezone.utc)


def _ev(start: datetime, rrule: dict | None = None) -> Event:
    e = Event()
    e.add("DTSTART", start)
    if rrule is not None:
        e.add("RRULE", rrule)
    return e


def _events_from(path: Path) -> list[Event]:
    cal = Calendar.from_ical(path.read_text(encoding="utf-8"))
    return [c for c in cal.walk("VEVENT")]


def test_event_within_past_30_days_kept() -> None:
    ev = _ev(NOW - timedelta(days=29))
    assert in_window(ev, now=NOW) is True


def test_event_older_than_30_days_dropped() -> None:
    ev = _ev(NOW - timedelta(days=31))
    assert in_window(ev, now=NOW) is False


def test_future_event_kept() -> None:
    ev = _ev(NOW + timedelta(days=365))
    assert in_window(ev, now=NOW) is True


def test_recurring_open_ended_kept_even_if_master_old() -> None:
    ev = _events_from(FIXTURES / "recurring_open_ended.ics")[0]
    assert in_window(ev, now=NOW) is True


def test_recurring_with_expired_until_dropped() -> None:
    ev = _events_from(FIXTURES / "recurring_with_until.ics")[0]
    assert in_window(ev, now=NOW) is False


def test_recurring_with_future_until_kept() -> None:
    ev = _ev(
        datetime(2014, 1, 6, 18, 0, tzinfo=timezone.utc),
        rrule={"FREQ": ["WEEKLY"], "UNTIL": [datetime(2030, 1, 1, tzinfo=timezone.utc)]},
    )
    assert in_window(ev, now=NOW) is True

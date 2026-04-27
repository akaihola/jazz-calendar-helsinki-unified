"""Tests for the dedup module."""

from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar, Event

from jazz_calendar.dedup import dedup, default_prefer
from jazz_calendar.source import tag_source

FIXTURES = Path(__file__).parent / "fixtures"


def _events_from(path: Path) -> list[Event]:
    cal = Calendar.from_ical(path.read_text(encoding="utf-8"))
    return [c for c in cal.walk("VEVENT")]


def _ev(start: datetime, location: str, uid: str) -> Event:
    e = Event()
    e.add("DTSTART", start)
    e.add("LOCATION", location)
    e.add("UID", uid)
    return e


def test_dedup_real_world_collision() -> None:
    sj = list(tag_source(_events_from(FIXTURES / "manala_collision_suomijazz.ics"), "suomijazz"))
    gc = list(tag_source(_events_from(FIXTURES / "manala_collision_gcal.ics"), "gcal"))
    result = dedup(sj + gc)
    assert len(result) == 1
    assert str(result[0]["X-JAZZHKI-SOURCE"]) == "gcal"


def test_dedup_keeps_distinct_events() -> None:
    base = datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc)
    later = datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc)
    e1 = _ev(base, "Storyville, Helsinki", "a@x")
    e2 = _ev(later, "Storyville, Helsinki", "b@x")
    tagged = list(tag_source([e1, e2], "suomijazz"))
    result = dedup(tagged)
    assert len(result) == 2


def test_dedup_keeps_same_time_distinct_venues() -> None:
    when = datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc)
    e1 = _ev(when, "Storyville, Helsinki", "a@x")
    e2 = _ev(when, "Manala, Helsinki", "b@x")
    tagged = list(tag_source([e1, e2], "suomijazz"))
    result = dedup(tagged)
    assert len(result) == 2


def test_dedup_passes_through_event_missing_dtstart() -> None:
    missing = list(tag_source(_events_from(FIXTURES / "missing_dtstart.ics"), "suomijazz"))
    normal = list(tag_source(
        [_ev(datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc), "Storyville", "n@x")],
        "suomijazz",
    ))
    result = dedup(missing + normal)
    assert len(result) == 2


def test_dedup_passes_through_event_missing_location() -> None:
    e = Event()
    e.add("DTSTART", datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc))
    e.add("UID", "noloc@x")
    normal = _ev(datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc), "Storyville", "n@x")
    tagged = list(tag_source([e, normal], "suomijazz"))
    result = dedup(tagged)
    assert len(result) == 2


def test_default_prefer_gcal_over_suomijazz() -> None:
    sj = next(tag_source([Event()], "suomijazz"))
    gc = next(tag_source([Event()], "gcal"))
    assert default_prefer(gc) > default_prefer(sj)

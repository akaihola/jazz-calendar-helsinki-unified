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


def _ev(
    start: datetime, location: str, uid: str, summary: str | None = None
) -> Event:
    e = Event()
    e.add("DTSTART", start)
    e.add("LOCATION", location)
    e.add("UID", uid)
    if summary is not None:
        e.add("SUMMARY", summary)
    return e


def test_dedup_real_world_collision() -> None:
    sj = list(tag_source(_events_from(FIXTURES / "manala_collision_suomijazz.ics"), "suomijazz"))
    gc = list(tag_source(_events_from(FIXTURES / "manala_collision_gcal.ics"), "gcal"))
    result = dedup(sj + gc)
    assert len(result) == 1
    assert str(result[0]["X-JAZZFI-SOURCE"]) == "gcal"


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


def _pair(
    when: datetime,
    sj_loc: str,
    gc_loc: str,
    sj_sum: str,
    gc_sum: str,
) -> list[Event]:
    sj = _ev(when, sj_loc, "sj@x", sj_sum)
    gc = _ev(when, gc_loc, "gc@x", gc_sum)
    return list(tag_source([sj], "suomijazz")) + list(tag_source([gc], "gcal"))


def test_dedup_collapses_venue_with_floor_suffix() -> None:
    when = datetime(2026, 4, 27, 16, 0, tzinfo=timezone.utc)
    events = _pair(
        when,
        "Promenadisali, Yrjönkatu 17, Pori, FI",
        "Promenadisali 1.krs, Yrjönkatu 17, 28100 Pori, Suomi",
        "Bill Frisell & Eyvind Kang at Promenadisali",
        "Validi Karkia 15v: Bill Frisell & Eyvind Kang",
    )
    result = dedup(events)
    assert len(result) == 1
    assert str(result[0]["X-JAZZFI-SOURCE"]) == "gcal"


def test_dedup_collapses_ampersand_vs_and() -> None:
    when = datetime(2026, 5, 9, 14, 0, tzinfo=timezone.utc)
    events = _pair(
        when,
        "The Tower Wine and Craft Beer, Firdonkatu 2B, Helsinki, FI",
        "The Tower - Wine & Craft Beer, Firdonkatu 2B, 00520 Helsinki, Suomi",
        "Towerin jazzlauantai at The Tower Wine and Craft Beer",
        "Tower: Ilkka Uksila ja Lassi Kouvo",
    )
    result = dedup(events)
    assert len(result) == 1
    assert str(result[0]["X-JAZZFI-SOURCE"]) == "gcal"


def test_dedup_collapses_street_typo_via_address_and_token() -> None:
    when = datetime(2026, 6, 4, 16, 0, tzinfo=timezone.utc)
    events = _pair(
        when,
        "Äänen Lumo, Nokiankatu 2-4, Helsinki, FI",
        "Äänen Lumo ry, Nokiantie 2-4, 00510 Helsinki, Suomi",
        "Suhina-klubi at Äänen Lumo",
        "Suhina: Nebbia, Corsano & Kääriäinen",
    )
    result = dedup(events)
    assert len(result) == 1
    assert str(result[0]["X-JAZZFI-SOURCE"]) == "gcal"


def test_dedup_address_key_alone_does_not_collapse_unrelated_events() -> None:
    """Same start time + same house number + same city is not enough on its own."""
    when = datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc)
    e1 = _ev(when, "Storyville, Mainstreet 5, Helsinki, FI", "a@x", "Quartet Alpha")
    e2 = _ev(when, "Manala, Sidestreet 5, Helsinki, FI", "b@x", "Trio Beta")
    tagged = list(tag_source([e1], "suomijazz")) + list(tag_source([e2], "gcal"))
    result = dedup(tagged)
    assert len(result) == 2


def test_default_prefer_gcal_over_suomijazz() -> None:
    sj = next(tag_source([Event()], "suomijazz"))
    gc = next(tag_source([Event()], "gcal"))
    assert default_prefer(gc) > default_prefer(sj)

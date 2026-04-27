"""Tests for the source-tagging helper."""

from icalendar import Event

from jazz_calendar.source import tag_source


def _ev() -> Event:
    e = Event()
    e["UID"] = "u@x"
    return e


def test_tag_source_writes_property() -> None:
    e1, e2 = _ev(), _ev()
    out = list(tag_source([e1, e2], "gcal"))
    assert len(out) == 2
    for e in out:
        assert str(e["X-JAZZHKI-SOURCE"]) == "gcal"


def test_tag_source_idempotent_overwrite() -> None:
    e = _ev()
    list(tag_source([e], "suomijazz"))
    list(tag_source([e], "gcal"))
    # Final value is "gcal", not duplicated.
    assert str(e["X-JAZZHKI-SOURCE"]) == "gcal"

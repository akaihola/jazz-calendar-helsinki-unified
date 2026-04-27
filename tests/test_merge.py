"""Tests for the merge orchestration module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from icalendar import Calendar, Event

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_fetch(url_to_path: dict[str, Path]):
    def _read(url: str, *, timeout: float = 30.0) -> bytes:
        return Path(url_to_path[url]).read_bytes()

    return _read


def _setup_env(monkeypatch, tmp_path: Path, *, now: str) -> Path:
    """Wire env vars + fetch monkeypatch for the standard collision fixtures."""
    sj_url = "file://suomijazz"
    gcal_url = "file://gcal"
    out = tmp_path / "out.ics"
    monkeypatch.setenv("SUOMIJAZZ_URL", sj_url)
    monkeypatch.setenv("GCAL_URL", gcal_url)
    monkeypatch.setenv("JAZZ_CALENDAR_OUTPUT", str(out))
    monkeypatch.setenv("JAZZ_CALENDAR_NOW", now)
    fake = _fake_fetch(
        {
            sj_url: FIXTURES / "manala_collision_suomijazz.ics",
            gcal_url: FIXTURES / "manala_collision_gcal.ics",
        }
    )
    monkeypatch.setattr("jazz_calendar.merge.fetch_feed", fake)
    return out


def test_merge_happy_path_writes_valid_ics(monkeypatch, tmp_path: Path) -> None:
    out = _setup_env(monkeypatch, tmp_path, now="2026-04-27T06:00:00+00:00")

    from jazz_calendar import merge

    merge.main()

    cal = Calendar.from_ical(out.read_bytes())
    vevents = list(cal.walk("VEVENT"))
    assert len(vevents) >= 1

    from jazz_calendar.normalize import normalize_location

    matching = []
    target = datetime(2026, 4, 30, 14, 0, tzinfo=timezone.utc)
    for ev in vevents:
        loc = ev.get("LOCATION")
        if loc is None:
            continue
        if normalize_location(str(loc)) != "ravintola manala":
            continue
        dtstart = ev.get("DTSTART")
        if dtstart is None:
            continue
        dt = dtstart.dt
        if not isinstance(dt, datetime):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        if dt == target:
            matching.append(ev)
    assert len(matching) == 1


def test_merge_zero_events_aborts(monkeypatch, tmp_path: Path) -> None:
    out = _setup_env(monkeypatch, tmp_path, now="2099-01-01T00:00:00+00:00")
    out.write_bytes(b"PREVIOUS")

    from jazz_calendar import merge

    with pytest.raises(SystemExit) as excinfo:
        merge.main()
    exc: SystemExit = excinfo.value  # type: ignore[assignment]
    assert exc.code not in (0, None)
    assert out.read_bytes() == b"PREVIOUS"


def test_merge_below_50pct_aborts(monkeypatch, tmp_path: Path) -> None:
    out = _setup_env(monkeypatch, tmp_path, now="2026-04-27T06:00:00+00:00")

    # Pre-write a 100-event "previous" calendar.
    prev = Calendar()
    prev.add("PRODID", "-//test//prev//EN")
    prev.add("VERSION", "2.0")
    for i in range(100):
        e = Event()
        e.add("UID", f"prev-{i}@test")
        e.add("DTSTART", datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc))
        e.add("SUMMARY", f"Prev {i}")
        prev.add_component(e)
    prev_bytes = prev.to_ical()
    out.write_bytes(prev_bytes)

    from jazz_calendar import merge

    with pytest.raises(SystemExit) as excinfo:
        merge.main()
    exc: SystemExit = excinfo.value  # type: ignore[assignment]
    assert exc.code not in (0, None)
    assert out.read_bytes() == prev_bytes


def test_merge_round_trip_parse_failure_aborts(monkeypatch, tmp_path: Path) -> None:
    out = _setup_env(monkeypatch, tmp_path, now="2026-04-27T06:00:00+00:00")
    out.write_bytes(b"PREVIOUS")

    from jazz_calendar import merge

    monkeypatch.setattr(
        "jazz_calendar.merge.Calendar.to_ical",
        lambda self, *a, **kw: b"INVALID NOT ICS",
    )

    with pytest.raises(SystemExit) as excinfo:
        merge.main()
    exc: SystemExit = excinfo.value  # type: ignore[assignment]
    assert exc.code not in (0, None)
    assert out.read_bytes() == b"PREVIOUS"

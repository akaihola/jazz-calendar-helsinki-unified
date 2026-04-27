"""Orchestrate fetch -> tag -> patch -> window -> dedup -> guards -> write."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar

from .dedup import dedup
from .fetch import fetch_feed
from .patch import patch_event
from .source import tag_source
from .window import in_window

SUOMIJAZZ_URL = os.environ.get(
    "SUOMIJAZZ_URL", "https://suomijazz.com/?feed=gigpress-ical"
)
GCAL_URL = os.environ.get(
    "GCAL_URL",
    "https://calendar.google.com/calendar/ical/"
    "ub9hkd0tjl3vk82t9jn5qudemc%40group.calendar.google.com/public/basic.ics",
)
JAZZ_CALENDAR_OUTPUT = Path(
    os.environ.get("JAZZ_CALENDAR_OUTPUT", "docs/calendar.ics")
)

PRODID = "-//akaihola//jazz-calendar-finland//EN"


def _now_utc() -> datetime:
    raw = os.environ.get("JAZZ_CALENDAR_NOW")
    if raw:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _previous_event_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        cal = Calendar.from_ical(path.read_bytes())
    except Exception:
        return 0
    return sum(1 for _ in cal.walk("VEVENT"))


def _extract_vtimezone(cal: Calendar):
    for tz in cal.walk("VTIMEZONE"):
        return tz
    return None


def _abort(msg: str) -> None:
    print(f"jazz_calendar.merge: ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    now = _now_utc()
    # Re-read env-overridable knobs at call time so tests can monkeypatch
    # without reloading the module.
    sj_url = os.environ.get("SUOMIJAZZ_URL", SUOMIJAZZ_URL)
    gcal_url = os.environ.get("GCAL_URL", GCAL_URL)
    output = Path(os.environ.get("JAZZ_CALENDAR_OUTPUT", str(JAZZ_CALENDAR_OUTPUT)))

    sj_bytes = fetch_feed(sj_url)
    sj_cal = Calendar.from_ical(sj_bytes)
    sj_events = [
        patch_event(e) for e in tag_source(sj_cal.walk("VEVENT"), "suomijazz")
    ]

    gcal_bytes = fetch_feed(gcal_url)
    gcal_cal = Calendar.from_ical(gcal_bytes)
    gcal_events = [
        patch_event(e) for e in tag_source(gcal_cal.walk("VEVENT"), "gcal")
    ]

    all_events = sj_events + gcal_events
    windowed = [e for e in all_events if in_window(e, now=now)]
    kept = dedup(windowed)

    if len(kept) == 0:
        _abort("zero events after pipeline")
    previous = _previous_event_count(output)
    if previous and len(kept) < 0.5 * previous:
        _abort(f"kept {len(kept)} < 50% of previous {previous}")

    out = Calendar()
    out.add("PRODID", PRODID)
    out.add("VERSION", "2.0")
    out.add("CALSCALE", "GREGORIAN")
    out.add("METHOD", "PUBLISH")
    out.add("X-WR-CALNAME", "Jazz Finland (unified)")
    out.add("X-WR-TIMEZONE", "Europe/Helsinki")
    vtimezone = _extract_vtimezone(gcal_cal)
    if vtimezone is not None:
        out.add_component(vtimezone)
    for ev in kept:
        out.add_component(ev)

    serialized = out.to_ical()
    try:
        Calendar.from_ical(serialized)
    except Exception as exc:
        _abort(f"round-trip parse failed: {exc}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(serialized)


if __name__ == "__main__":
    main()

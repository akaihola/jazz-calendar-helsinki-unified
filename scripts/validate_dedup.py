"""Validate de-duplication by inspecting cross-source same-minute events.

Fetches both upstream feeds in full (no time window), finds events whose
DTSTART falls on the same minute as at least one event from the other
source, runs those candidates through :func:`dedup`, and prints a table of
venues and summaries for the events that survived dedup as separate entries
within a same-minute cross-source bucket.

Usage:
    uv run python scripts/validate_dedup.py
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

from icalendar import Calendar, Event

from jazz_calendar.dedup import dedup
from jazz_calendar.fetch import fetch_feed
from jazz_calendar.merge import GCAL_URL, SUOMIJAZZ_URL
from jazz_calendar.patch import patch_event
from jazz_calendar.source import tag_source


def _start_minute(event: Event) -> datetime | None:
    dtstart = event.get("DTSTART")
    if dtstart is None:
        return None
    dt = dtstart.dt
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).replace(second=0, microsecond=0)
    if isinstance(dt, date):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return None


def _source(event: Event) -> str:
    return str(event.get("X-JAZZFI-SOURCE", "?"))


def _summary(event: Event) -> str:
    return str(event.get("SUMMARY", "")).strip()


def _location(event: Event) -> str:
    loc = event.get("LOCATION")
    if loc is None:
        return ""
    return str(loc).strip().splitlines()[0]


def _load_suomijazz(url: str) -> list[Event]:
    cal = Calendar.from_ical(fetch_feed(url))
    return [patch_event(e) for e in tag_source(cal.walk("VEVENT"), "suomijazz")]


def _load_gcal(url: str) -> list[Event]:
    cal = Calendar.from_ical(fetch_feed(url))
    return [patch_event(e) for e in tag_source(cal.walk("VEVENT"), "gcal")]


def main() -> None:
    sj_events = _load_suomijazz(SUOMIJAZZ_URL)
    gcal_events = _load_gcal(GCAL_URL)
    print(f"fetched: suomijazz={len(sj_events)}  gcal={len(gcal_events)}")

    buckets: dict[datetime, list[Event]] = defaultdict(list)
    for ev in sj_events + gcal_events:
        start = _start_minute(ev)
        if start is not None:
            buckets[start].append(ev)

    candidates: list[Event] = []
    cross_buckets: dict[datetime, list[Event]] = {}
    for start, evs in buckets.items():
        sources = {_source(e) for e in evs}
        if "suomijazz" in sources and "gcal" in sources:
            cross_buckets[start] = evs
            candidates.extend(evs)

    print(
        f"cross-source same-minute buckets: {len(cross_buckets)}  "
        f"candidate events: {len(candidates)}"
    )

    kept = dedup(candidates)
    kept_ids = {id(e) for e in kept}

    surviving_by_bucket: dict[datetime, list[Event]] = {}
    for start, evs in cross_buckets.items():
        surviving = [e for e in evs if id(e) in kept_ids]
        if len({_source(e) for e in surviving}) > 1:
            surviving_by_bucket[start] = surviving

    total_rows = sum(len(v) for v in surviving_by_bucket.values())
    print(
        f"buckets where dedup did NOT merge across sources: "
        f"{len(surviving_by_bucket)}  rows: {total_rows}"
    )
    print()

    if not surviving_by_bucket:
        return

    rows: list[tuple[str, str, str, str]] = []
    for start in sorted(surviving_by_bucket):
        for ev in surviving_by_bucket[start]:
            rows.append(
                (
                    start.strftime("%Y-%m-%d %H:%M"),
                    _source(ev),
                    _location(ev),
                    _summary(ev),
                )
            )

    headers = ("start (UTC)", "source", "venue", "title")
    widths = [
        max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)
    ]
    widths[2] = min(widths[2], 50)
    widths[3] = min(widths[3], 60)

    def _fmt(parts: tuple[str, str, str, str]) -> str:
        return "  ".join(p[: widths[i]].ljust(widths[i]) for i, p in enumerate(parts))

    print(_fmt(headers))
    print("  ".join("-" * w for w in widths))
    prev_start = None
    for r in rows:
        if prev_start is not None and r[0] != prev_start:
            print()
        print(_fmt(r))
        prev_start = r[0]


if __name__ == "__main__":
    main()

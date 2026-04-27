"""Heuristic de-duplication of events across upstream sources.

Events are bucketed by ``(round_dt_to_15min(DTSTART), normalize_location(LOCATION))``.
Within a bucket, the event with the highest ``prefer`` score wins; ties keep the
first seen. Events missing DTSTART or LOCATION receive a deterministic unique
key and pass through unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from icalendar import Event

from .normalize import normalize_location, round_dt_to_15min


def default_prefer(event: Event) -> int:
    """Score events by source: gcal (2) > suomijazz (1) > unknown (0)."""
    src = str(event.get("X-JAZZHKI-SOURCE", ""))
    return {"gcal": 2, "suomijazz": 1}.get(src, 0)


def _key(event: Event, counter: list[int]) -> tuple:
    dtstart = event.get("DTSTART")
    location = event.get("LOCATION")
    if dtstart is None or location is None:
        counter[0] += 1
        return ("__unique__", counter[0])
    dt = dtstart.dt
    # Coerce date → datetime at midnight UTC for all-day events.
    if not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return (round_dt_to_15min(dt), normalize_location(str(location)))


def dedup(
    events: Iterable[Event],
    *,
    prefer: Callable[[Event], int] = default_prefer,
) -> list[Event]:
    """Collapse events that share a ``(rounded DTSTART, normalized venue)`` key."""
    counter = [0]
    best: dict = {}
    for ev in events:
        k = _key(ev, counter)
        if k not in best or prefer(ev) > prefer(best[k]):
            best[k] = ev
    return list(best.values())

"""Time-window filter with RRULE-aware semantics.

Single events are kept iff DTSTART >= now - past_days. Recurring events are
kept if their RRULE is open-ended, or its UNTIL extends to >= the floor.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def _to_utc(dt: object) -> datetime | None:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if isinstance(dt, date):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return None


def in_window(event, *, now: datetime, past_days: int = 30) -> bool:
    """True if ``event`` falls within the [now - past_days, +inf) window."""
    floor = now - timedelta(days=past_days)
    dtstart = event.get("DTSTART")
    start = _to_utc(dtstart.dt) if dtstart is not None else None

    rrule = event.get("RRULE")
    if rrule is not None:
        until_list = rrule.get("UNTIL")
        if not until_list:
            # Open-ended series — always in window.
            return True
        until_utc = _to_utc(until_list[0])
        if until_utc is None:
            return True
        return until_utc >= floor

    if start is None:
        return False
    return start >= floor

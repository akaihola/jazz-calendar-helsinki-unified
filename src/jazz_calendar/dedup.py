"""Heuristic de-duplication of events across upstream sources.

Two events are treated as duplicates if they share a rounded start time
(15-minute granularity) and either:

* a normalized venue head (``normalize_venue``), **or**
* an address key — ``(house_number, city)`` extracted from LOCATION —
  combined with at least one shared word (≥ 4 chars) between their
  summaries or venue heads.

Within a duplicate group the event with the highest ``prefer`` score wins;
ties keep the first seen. Events missing DTSTART or LOCATION receive a
deterministic unique key and pass through unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from icalendar import Event

from .normalize import (
    address_key,
    normalize_venue,
    round_dt_to_15min,
    summary_tokens,
)


def default_prefer(event: Event) -> int:
    """Score events by source: gcal (2) > suomijazz (1) > unknown (0)."""
    src = str(event.get("X-JAZZHKI-SOURCE", ""))
    return {"gcal": 2, "suomijazz": 1}.get(src, 0)


def _rounded_start(event: Event) -> datetime | None:
    dtstart = event.get("DTSTART")
    if dtstart is None:
        return None
    dt = dtstart.dt
    if not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return round_dt_to_15min(dt)


def _venue_address_summary(
    event: Event,
) -> tuple[str | None, tuple[str, str] | None, set[str]]:
    location = event.get("LOCATION")
    if location is None:
        return (None, None, set())
    loc_str = str(location)
    venue = normalize_venue(loc_str) or None
    addr = address_key(loc_str)
    tokens = summary_tokens(str(event.get("SUMMARY", "")))
    if venue:
        tokens |= summary_tokens(venue)
    return (venue, addr, tokens)


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


def dedup(
    events: Iterable[Event],
    *,
    prefer: Callable[[Event], int] = default_prefer,
) -> list[Event]:
    """Collapse cross-source duplicates using venue and address heuristics."""
    evs = list(events)
    n = len(evs)
    starts = [_rounded_start(e) for e in evs]
    derived = [_venue_address_summary(e) for e in evs]

    uf = _UnionFind(n)

    venue_index: dict[tuple[datetime, str], int] = {}
    address_index: dict[tuple[datetime, tuple[str, str]], list[int]] = {}

    for i, (start, (venue, addr, _tokens)) in enumerate(zip(starts, derived)):
        if start is None or evs[i].get("LOCATION") is None:
            continue
        if venue:
            key = (start, venue)
            if key in venue_index:
                uf.union(venue_index[key], i)
            else:
                venue_index[key] = i
        if addr is not None:
            address_index.setdefault((start, addr), []).append(i)

    for members in address_index.values():
        if len(members) < 2:
            continue
        for a in range(len(members)):
            ia = members[a]
            tokens_a = derived[ia][2]
            for b in range(a + 1, len(members)):
                ib = members[b]
                if uf.find(ia) == uf.find(ib):
                    continue
                if tokens_a & derived[ib][2]:
                    uf.union(ia, ib)

    groups: dict[int, list[int]] = {}
    unique_counter = 0
    for i, e in enumerate(evs):
        if starts[i] is None or e.get("LOCATION") is None:
            unique_counter += 1
            groups[-unique_counter] = [i]
        else:
            groups.setdefault(uf.find(i), []).append(i)

    kept: list[Event] = []
    for members in groups.values():
        best_idx = members[0]
        best_score = prefer(evs[best_idx])
        for idx in members[1:]:
            score = prefer(evs[idx])
            if score > best_score:
                best_idx = idx
                best_score = score
        kept.append(evs[best_idx])
    return kept

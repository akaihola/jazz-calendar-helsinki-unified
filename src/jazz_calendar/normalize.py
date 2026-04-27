"""Field normalization helpers for cross-source event matching."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

_WS_RE = re.compile(r"\s+")


def _strip_diacritics(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _collapse_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def normalize_location(loc: str) -> str:
    """Normalize a location string for fuzzy matching.

    Takes the first comma-separated segment, strips whitespace, lowercases,
    removes diacritics via NFKD, and collapses internal whitespace.
    """
    head = loc.split(",", 1)[0]
    head = _strip_diacritics(head).lower()
    return _collapse_ws(head)


def normalize_summary(s: str) -> str:
    """Normalize an event summary: lowercase, NFKD strip, collapse whitespace."""
    return _collapse_ws(_strip_diacritics(s).lower())


def round_dt_to_15min(dt: datetime) -> datetime:
    """Round a datetime to the nearest 15-minute boundary in UTC.

    Naive inputs are assumed to be UTC. Aware inputs are converted to UTC
    before rounding. Ties (e.g. minute 7.5) round up — minute 7 → 0,
    minute 8 → 15.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Drop sub-minute precision, then round minutes to nearest 15.
    dt = dt.replace(second=0, microsecond=0)
    minute = dt.minute
    remainder = minute % 15
    if remainder < 8:
        delta = -remainder
    else:
        delta = 15 - remainder
    return dt + timedelta(minutes=delta)

"""Field normalization helpers for cross-source event matching."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

_WS_RE = re.compile(r"\s+")
_HOUSE_NUMBER_RE = re.compile(r"\b(\d+[a-z]?(?:-\d+[a-z]?)?)\b")
_POSTAL_RE = re.compile(r"\b\d{5}\b")
_VENUE_TRAILING_RE = re.compile(
    r"(?:\s+(?:ry|oy|ay|ab|ltd))$"
    r"|(?:\s+\d+\.?\s*krs\.?)$"
    r"|(?:\s+(?:1st|2nd|3rd)\s*floor)$"
)


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


def normalize_venue(loc: str) -> str:
    """Aggressively normalize the venue head for fuzzy bucketing.

    Like ``normalize_location`` but also: replaces ``&`` with ``and``,
    drops trailing legal/floor suffixes (``ry``, ``oy``, ``1.krs``…),
    and collapses any non-alphanumeric run to a single space.
    """
    head = _strip_diacritics(loc.split(",", 1)[0]).lower()
    head = head.replace("&", " and ")
    head = re.sub(r"[^a-z0-9]+", " ", head)
    head = _collapse_ws(head)
    while True:
        new = _VENUE_TRAILING_RE.sub("", head).strip()
        if new == head:
            break
        head = new
    return head


def address_key(loc: str) -> tuple[str, str] | None:
    """Extract a ``(house_number, city)`` key from a LOCATION string.

    Returns ``None`` if either component cannot be identified. The house
    number tolerates letter suffixes (``2b``) and ranges (``2-4``); the
    city is the alphabetic portion of the segment carrying the postal
    code, or — failing that — the segment immediately before a country
    suffix (``FI``/``Suomi``).
    """
    segments = [_collapse_ws(s) for s in loc.split(",")]
    house: str | None = None
    for seg in segments:
        m = _HOUSE_NUMBER_RE.search(seg)
        if m and not _POSTAL_RE.fullmatch(m.group(1)):
            house = m.group(1).lower()
            break
    if house is None:
        return None
    city: str | None = None
    for seg in segments:
        if _POSTAL_RE.search(seg):
            stripped = _POSTAL_RE.sub("", seg).strip()
            stripped = _strip_diacritics(stripped).lower()
            stripped = re.sub(r"[^a-z]+", " ", stripped).strip()
            if stripped:
                city = stripped.split()[0]
                break
    if city is None:
        for seg in reversed(segments):
            low = _strip_diacritics(seg).lower().strip()
            if low in {"fi", "suomi", "finland"}:
                continue
            low = re.sub(r"[^a-z]+", " ", low).strip()
            if low:
                city = low.split()[-1]
                break
    if city is None:
        return None
    return (house, city)


def summary_tokens(s: str, *, min_len: int = 4) -> set[str]:
    """Return the set of normalized word tokens of length ≥ ``min_len``."""
    norm = re.sub(r"[^a-z0-9]+", " ", _strip_diacritics(s).lower())
    return {tok for tok in norm.split() if len(tok) >= min_len}


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

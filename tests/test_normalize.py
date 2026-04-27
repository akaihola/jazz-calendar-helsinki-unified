"""Tests for jazz_calendar.normalize."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from jazz_calendar.normalize import (
    normalize_location,
    normalize_summary,
    round_dt_to_15min,
)

UTC = timezone.utc


def test_normalize_location_takes_first_segment() -> None:
    assert (
        normalize_location("Koko Jazz Club, Hämeentie 3, Helsinki, FI")
        == "koko jazz club"
    )


def test_normalize_location_strips_diacritics() -> None:
    assert normalize_location("Töölö Jazzklubi") == "toolo jazzklubi"


def test_normalize_location_collapses_whitespace() -> None:
    assert normalize_location("  Koko   Jazz Club ") == "koko jazz club"


def test_round_dt_to_15min_below_boundary() -> None:
    assert round_dt_to_15min(datetime(2026, 4, 27, 22, 53, tzinfo=UTC)) == datetime(
        2026, 4, 27, 23, 0, tzinfo=UTC
    )


def test_round_dt_to_15min_above_boundary() -> None:
    assert round_dt_to_15min(datetime(2026, 4, 27, 22, 7, tzinfo=UTC)) == datetime(
        2026, 4, 27, 22, 0, tzinfo=UTC
    )


def test_round_dt_to_15min_converts_aware_to_utc() -> None:
    helsinki = ZoneInfo("Europe/Helsinki")
    dt = datetime(2026, 4, 27, 2, 7, tzinfo=helsinki)
    assert round_dt_to_15min(dt) == datetime(2026, 4, 26, 23, 0, tzinfo=UTC)


def test_normalize_summary() -> None:
    assert (
        normalize_summary("Bill Frisell & Eyvind Kang at Promenadisali")
        == "bill frisell & eyvind kang at promenadisali"
    )

"""Tag iCalendar events with their upstream source via ``X-JAZZHKI-SOURCE``."""

from collections.abc import Iterable, Iterator
from typing import Literal

from icalendar import Event


def tag_source(
    events: Iterable[Event], source: Literal["gcal", "suomijazz"]
) -> Iterator[Event]:
    """Yield each event after stamping ``X-JAZZHKI-SOURCE`` with ``source``.

    Assigning the key replaces any prior value (icalendar's ``Event`` is dict-like
    and a single key cannot occur twice), so this is safe to apply repeatedly.
    """
    for e in events:
        e["X-JAZZHKI-SOURCE"] = source
        yield e

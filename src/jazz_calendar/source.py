"""Tag iCalendar events with their upstream source via ``X-JAZZFI-SOURCE``."""

from collections.abc import Iterable, Iterator
from typing import Literal

from icalendar import Event


def tag_source(
    events: Iterable[Event], source: Literal["gcal", "suomijazz"]
) -> Iterator[Event]:
    """Yield each event after stamping ``X-JAZZFI-SOURCE`` with ``source``.

    Assigning the key replaces any prior value (icalendar's ``Event`` is dict-like
    and a single key cannot occur twice), so this is safe to apply repeatedly.
    """
    for e in events:
        e["X-JAZZFI-SOURCE"] = source
        yield e

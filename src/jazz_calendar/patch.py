"""Patch SuomiJazz events that have zero duration with an estimated 2h end time."""

from datetime import timedelta

from icalendar import Event

ESTIMATED_DURATION = timedelta(hours=2)


def patch_event(event: Event) -> Event:
    """If ``event`` is a SuomiJazz event with DTSTART == DTEND, push DTEND out by 2h.

    The replacement DTEND carries an ``X-JAZZHKI-DURATION-ESTIMATED=true`` parameter
    so downstream consumers can tell the duration is a placeholder, not authoritative.
    Events from other sources, or with a real duration, are returned unchanged.
    """
    if str(event.get("X-JAZZHKI-SOURCE", "")) != "suomijazz":
        return event
    dtstart = event.get("DTSTART")
    dtend = event.get("DTEND")
    if dtstart is None or dtend is None:
        return event
    if dtstart.dt != dtend.dt:
        return event
    new_end_dt = dtstart.dt + ESTIMATED_DURATION
    del event["DTEND"]
    event.add(
        "DTEND",
        new_end_dt,
        parameters={"X-JAZZHKI-DURATION-ESTIMATED": "true"},
    )
    return event

# jazz-calendar-finland

[![Built with Claude Code](https://img.shields.io/badge/Built_with-Claude_Code-6f42c1?logo=anthropic&logoColor=white)](https://claude.ai/code)

> This project is developed by an AI coding agent ([Claude Code](https://claude.ai/code)), with human oversight and direction.

A unified, de-duplicated public iCalendar (RFC 5545) feed of jazz concerts in Finland. The feed merges two upstream sources, refreshes every 6 hours, and is served by GitHub Pages at:

<https://akaihola.github.io/jazz-calendar-finland/calendar.ics>

Subscribe to that URL in Google Calendar, Apple Calendar, Thunderbird, or any other RFC 5545 client.

## Upstream feeds

- GigPress / SuomiJazz: <https://suomijazz.com/?feed=gigpress-ical>
- Public Google Calendar (Jazz-kalenteri): <https://calendar.google.com/calendar/ical/ub9hkd0tjl3vk82t9jn5qudemc%40group.calendar.google.com/public/basic.ics>

## Development

```sh
uv sync
uv run pytest
uv run python -m jazz_calendar.merge
```

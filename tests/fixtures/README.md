# Test fixtures

Captured upstream iCalendar feeds and hand-crafted edge-case fixtures used by the
`jazz_calendar` test suite.

## Captured upstream snapshots

| File             | Source                                                                                                              | Captured (UTC) |
| ---------------- | ------------------------------------------------------------------------------------------------------------------- | -------------- |
| `suomijazz.ics`  | <https://suomijazz.com/?feed=gigpress-ical>                                                                         | 2026-04-27     |
| `gcal.ics`       | `https://calendar.google.com/calendar/ical/ub9hkd0tjl3vk82t9jn5qudemc%40group.calendar.google.com/public/basic.ics` | 2026-04-27     |

Capture commands (run from the repository root):

```sh
curl -sL --max-time 60 -o tests/fixtures/suomijazz.ics \
  "https://suomijazz.com/?feed=gigpress-ical"
curl -sL --max-time 60 -o tests/fixtures/gcal.ics \
  "https://calendar.google.com/calendar/ical/ub9hkd0tjl3vk82t9jn5qudemc%40group.calendar.google.com/public/basic.ics"
```

**These files are byte-exact snapshots of the upstream feeds at the capture
date and MUST NOT be regenerated automatically.** Tests rely on the specific
events and quirks present at this capture; refreshing the snapshots would
silently invalidate test expectations. Re-capture only as a deliberate,
reviewed change.

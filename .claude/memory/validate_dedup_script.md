---
name: validate_dedup script
description: Standalone tool to inspect cross-source same-minute events that survive dedup as separate entries
type: project
originSessionId: e09468c6-154f-487d-8e1a-0cd9f152b78d
---
`scripts/validate_dedup.py` fetches both upstream feeds in full, buckets events by exact start minute, keeps only buckets that contain events from BOTH sources (suomijazz and gcal), runs them through `jazz_calendar.dedup.dedup`, and prints a table of the events that survived as separate entries within a cross-source bucket. Run with `uv run python scripts/validate_dedup.py`.

**Why:** Manual sanity check that dedup is neither too aggressive (false positives would not appear in surviving output, so check by reading the table — venues should be genuinely different) nor too lax (missed merges show up as same-venue rows).

**How to apply:** Re-run after any change to `dedup.py` or `normalize.py`. The script lives outside the test suite because it makes real network calls and reports qualitative output.

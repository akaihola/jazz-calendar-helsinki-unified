---
title: Jazz Calendar Helsinki — Unified iCalendar Merger
date: 2026-04-27
status: draft
owner: akaihola (with Claude Code)
repo: github.com/akaihola/jazz-calendar-helsinki-unified
---

# Jazz Calendar Helsinki — Unified iCalendar Merger

## 1. Purpose

Publish a single public iCalendar (RFC 5545) feed that is the de-duplicated union of two upstream feeds of jazz concerts in the Helsinki metropolitan area:

- **GigPress / SuomiJazz**: `https://suomijazz.com/?feed=gigpress-ical`
- **Public Google Calendar (Jazz-kalenteri)**: `https://calendar.google.com/calendar/ical/ub9hkd0tjl3vk82t9jn5qudemc%40group.calendar.google.com/public/basic.ics`

The merged feed is consumed by ordinary calendar clients (Google Calendar subscribe, Apple Calendar, Thunderbird, etc.). The project is operated end-to-end by Claude Code: planning, implementation, deployment, and ongoing maintenance.

## 2. Goals & non-goals

### Goals

1. A stable public URL serving valid `text/calendar` iCalendar 2.0 content.
2. De-duplicated union of the two upstream feeds.
3. Refreshes on a 6-hour cadence.
4. Survives upstream outages: the previously published feed continues to serve.
5. Zero monetary cost.
6. Fully resumable by a future Claude Code session with no human in the loop, using only the contents of the public GitHub repository.

### Non-goals

- No web UI, search, RSS, or email digest. iCalendar only.
- No write API. Read-only republishing.
- No geographic filtering at this stage. All events from both upstream feeds are passed through (subject to the time window in §6).
- No analytics, accounts, or rate-limiting beyond what GitHub Pages provides.
- No internationalisation of event content. Event titles and descriptions are forwarded verbatim from upstream.

## 3. Architecture

A single public GitHub repository, `akaihola/jazz-calendar-helsinki-unified`, contains:

- A Python script that fetches both upstream feeds, merges them, and writes `docs/calendar.ics`.
- A GitHub Actions workflow that runs the script on a 6-hour schedule and on pushes to `main`, then commits any change to `docs/calendar.ics`.
- GitHub Pages configured to serve the `docs/` directory of `main`.

### 3.1 Public URL

`https://akaihola.github.io/jazz-calendar-helsinki-unified/calendar.ics`

This is the only contract with consumers.

### 3.2 Data flow

```
                       ┌──────────────────────────────┐
                       │  GitHub Actions cron          │
                       │  (every 6h + on push)         │
                       └──────────────┬───────────────┘
                                      │ runs
                                      ▼
   ┌──────────────────┐   fetch    ┌────────────────┐    fetch    ┌────────────────────┐
   │ suomijazz.com    │◀───────────│ merge.py       │────────────▶│ calendar.google.com│
   │ (GigPress, ~73K) │            │ (Python+icalend.│            │ (Jazz-kalenteri,    │
   └──────────────────┘            └────────┬───────┘             │  ~20MB historical)  │
                                            │ writes              └────────────────────┘
                                            ▼
                                 docs/calendar.ics  (committed if changed)
                                            │
                                            │ served by GitHub Pages
                                            ▼
                  https://akaihola.github.io/jazz-calendar-helsinki-unified/calendar.ics
```

### 3.3 Repository layout

```
.
├── .github/workflows/refresh.yml     # cron + on-push workflow
├── docs/
│   ├── calendar.ics                  # the published feed (committed by CI)
│   └── index.html                    # one-page README pointing at the feed
├── src/
│   ├── merge.py                      # merge entry point (uv run src/merge.py)
│   ├── fetch.py                      # upstream HTTP fetch
│   ├── dedup.py                      # collision detection + fold
│   ├── window.py                     # time-window filter
│   └── normalize.py                  # location/title normalization helpers
├── tests/
│   ├── fixtures/                     # captured upstream samples
│   ├── test_dedup.py
│   ├── test_window.py
│   └── test_merge.py
├── pyproject.toml                    # uv-managed deps
├── README.md
├── .gitignore
└── docs/superpowers/specs/...        # this document and successors
```

`docs/index.html` is a 10-line static page so visitors who hit the project root get a hint about the feed URL; nothing else.

## 4. Components

Each component is a small Python module with a single responsibility, importable in isolation, and unit-testable without network or filesystem fixtures beyond `tests/fixtures/`.

### 4.1 `fetch.py` — Upstream fetch

- Public function: `fetch_feed(url: str, *, timeout: float = 30.0) -> bytes`
- Uses `urllib.request` (stdlib) to keep the dependency surface minimal.
- Sends a `User-Agent: jazz-calendar-helsinki-unified/1.0 (+https://github.com/akaihola/jazz-calendar-helsinki-unified)`.
- Raises a typed `FetchError` on non-2xx, network failure, or timeout. The caller (the workflow) decides whether to abort.
- No retry logic in v1: the workflow already retries every 6 hours.

### 4.2 `normalize.py` — Field normalisation

- `normalize_location(loc: str) -> str`: take the first comma-separated segment, strip whitespace, lowercase, NFD-strip diacritics, collapse internal whitespace.
- `round_dt_to_15min(dt: datetime) -> datetime`: convert to UTC, round to nearest 15-minute boundary.
- `normalize_summary(s: str) -> str`: lowercase, strip diacritics, collapse whitespace; used only for tie-breaker logging, not as a primary key.

### 4.3 `dedup.py` — De-duplication

- Public function: `dedup(events: Iterable[VEvent], *, prefer: Callable[[VEvent], int]) -> list[VEvent]`
- Computes a key per event: `(round_dt_to_15min(DTSTART_utc), normalize_location(LOCATION))`.
- On collision, picks the event whose `prefer(...)` returns the highest integer.
- The default `prefer` returns `2` for Google Calendar events (richer data, real DTEND, proper VTIMEZONE) and `1` for SuomiJazz events.
- Events with missing or unparsable DTSTART or LOCATION are passed through unchanged with a synthetic uniquifier in the key, so they cannot collide. They are logged at WARNING level.

### 4.4 `window.py` — Time-window filter

- Public function: `in_window(event: VEvent, *, now: datetime, past_days: int = 30) -> bool`
- Keeps events whose DTSTART (UTC) is `>= now - past_days` OR is in the future. There is no upper bound.
- Recurring events: handled in v1 by including the master `VEVENT` whenever any of its instances are in the window. This is approximate but matches what calendar clients do anyway.

### 4.5 `merge.py` — Orchestration

- Reads `SUOMIJAZZ_URL` and `GCAL_URL` (overridable by env var for tests).
- Calls `fetch_feed` for each.
- Parses each with `icalendar.Calendar.from_ical(...)`.
- Pipes events through `window.in_window` then `dedup.dedup`.
- Special handling for SuomiJazz events where `DTSTART == DTEND`: sets `DTEND = DTSTART + 2h` and adds an `X-JAZZHKI-DURATION-ESTIMATED: true` parameter to record the change. (Tested as a separate unit.)
- Builds a new `Calendar` with:
  - `PRODID:-//akaihola//jazz-calendar-helsinki-unified//EN`
  - `VERSION:2.0`
  - `CALSCALE:GREGORIAN`
  - `METHOD:PUBLISH`
  - `X-WR-CALNAME:Jazz Helsinki (unified)`
  - `X-WR-TIMEZONE:Europe/Helsinki`
  - The `Europe/Helsinki` `VTIMEZONE` taken from the GCal feed (canonical).
- Writes the result to `docs/calendar.ics` via a temp-file-then-rename to keep the served file atomic on the filesystem.
- Exits non-zero on any unrecoverable error so the workflow does not commit a broken file.

### 4.6 `.github/workflows/refresh.yml` — Workflow

- Triggers:
  - `schedule: cron: '17 */6 * * *'` (00:17, 06:17, 12:17, 18:17 UTC — off-the-hour to avoid the GitHub Actions cron rush).
  - `workflow_dispatch` (manual trigger from CLI / UI).
  - `push` to `main` for paths `src/**` or `pyproject.toml` (so code changes regenerate immediately).
- Steps:
  1. `actions/checkout@v4` with `persist-credentials: true`.
  2. Install `uv` via `astral-sh/setup-uv@v3`.
  3. Run `uv sync --frozen`.
  4. Run `uv run python -m src.merge`.
  5. If `git status --porcelain docs/calendar.ics` is non-empty, configure committer identity, `git add docs/calendar.ics`, `git commit -m "chore(feed): refresh $(date -u +%FT%TZ)"`, and `git push`.
  6. On any failure, the job exits non-zero. The previously published `docs/calendar.ics` is unchanged.
- Permissions: `contents: write` is granted only to this workflow.
- Concurrency: `concurrency: { group: refresh, cancel-in-progress: false }` to prevent overlapping runs from racing each other.

## 5. De-duplication algorithm — detailed

### 5.1 Key

```
key = (
    round_dt_to_15min(event.DTSTART.in_utc()),
    normalize_location(event.LOCATION.first_segment()),
)
```

### 5.2 Rationale

The two upstream feeds use disjoint UID schemes (`<dt>-<id>-maene…@gmail.com` vs `<random>@google.com`), so UID-based dedup is impossible. A confirmed real-world collision exists: the 2026-04-30 17:00 EEST Manala Afterwork Jazz event appears in both feeds with different titles ("VAPPUSPECIAL" qualifier in one, absent in the other) but identical venue and start time. Two distinct concerts at the same venue starting within 15 minutes are vanishingly rare in practice; we accept that boundary.

### 5.3 Tie-breaking

When the key collides, keep the event whose source has higher priority. GCal > SuomiJazz, because GCal carries proper VTIMEZONE, real DTEND, and richer descriptions. The discarded event's source URL is recorded in a debug log for the run; the merged feed itself contains only the kept event.

### 5.4 Edge cases

| Case | Behaviour |
|---|---|
| Same time, similar venue spelled differently (e.g. "Koko Jazz Club" vs "Koko Jazz") | `normalize_location` keys on the **first** comma-segment, so "Koko Jazz Club" survives but "Koko Jazz Club, Hämeentie 3, Helsinki, FI" matches. Mismatch on the head string ⇒ treated as separate events; this is the conservative choice. |
| Missing LOCATION | Synthetic uniquifier in key; passes through unchanged. |
| Missing DTSTART | Logged WARNING; passes through unchanged with synthetic uniquifier. (Calendar clients will ignore it.) |
| All-day event (`VALUE=DATE`) | Treated as starting at 00:00 local; rounding still produces a stable 15-min key. |
| Recurring event | Master VEVENT is keyed by its first DTSTART. Instances are not exploded. |
| SuomiJazz `DTSTART == DTEND` | DTEND set to DTSTART + 2 hours before dedup. Documented in `X-JAZZHKI-DURATION-ESTIMATED`. |

## 6. Time window

- **Past floor:** `now_utc - 30 days`. Events older than this are dropped.
- **Future ceiling:** none. All future events are kept.
- `now_utc` is captured once at the start of `merge.py` and reused for both filters, so the boundary is consistent within a run.

## 7. Failure handling

| Failure | Result |
|---|---|
| Either upstream returns non-2xx, times out, or returns invalid ICS | `merge.py` exits non-zero; the workflow step fails; previous `docs/calendar.ics` continues to serve unchanged. GitHub Actions emails the repo owner on failure (default behavior). |
| Both upstreams succeed but produce zero events | Treated as suspicious: `merge.py` exits non-zero rather than publishing an empty calendar. (Unit-tested.) |
| Output is byte-identical to the previously committed file | No commit; workflow exits 0. Avoids commit churn. |
| One upstream is down, the other works | v1 behaviour: the run fails, last-good is served. (See §11 future work.) |
| `git push` is rejected (e.g., concurrent push) | Workflow fails; next scheduled run will succeed. Concurrency group prevents overlap from this workflow itself. |

A future Claude Code session diagnoses by running:

```
gh run list --workflow refresh.yml --limit 10
gh run view <id> --log
git log -p docs/calendar.ics | head
```

These three commands cover ~all expected diagnostics.

## 8. Testing strategy

- **Unit tests** (`pytest`) cover `normalize`, `dedup`, `window`, and the SuomiJazz duration patch in isolation. No network.
- **Integration test** runs `merge.py` against captured upstream samples in `tests/fixtures/` and snapshots the output. Snapshot is committed and reviewed in PRs.
- **Validation test** runs the produced ICS through `icalendar.Calendar.from_ical` (round-trip) and asserts no parser warnings.
- **CI** runs the full test suite on every push and PR via a separate workflow `.github/workflows/test.yml`. The refresh workflow does not run tests (it only publishes).
- **No live-network tests in CI** — fixtures are captured manually and refreshed when upstream formats change.

## 9. Operations

- **Initial setup (one-time):**
  1. Create the repo `akaihola/jazz-calendar-helsinki-unified` on GitHub (public).
  2. Push the initial commit from `atom`.
  3. In repo Settings → Pages, set source to `Deploy from a branch` → `main` → `/docs`.
  4. First workflow run produces `docs/calendar.ics`; subsequent visit to the Pages URL serves it.
- **Ongoing:** none. The workflow runs every 6 hours.
- **Triggering an out-of-band refresh:** `gh workflow run refresh.yml` from any clone with auth, or push any change under `src/`.
- **Rotating credentials:** none required; the workflow uses the default `GITHUB_TOKEN`.

## 10. Cost & maintenance

- **Money:** $0/year. Public repos get unlimited Actions minutes; this workflow uses ~30 s/run × 4 runs/day ≈ 12 min/month. GitHub Pages bandwidth on a static <1 MB file is well within the 100 GB/month soft limit even with thousands of subscribers.
- **Agent-hours/year:** estimated <2 h, dominated by responding to upstream format changes (e.g., GigPress plugin upgrade). Routine operation: zero.

## 11. Future work (out of scope for v1)

- **Partial-success mode:** if one upstream is down, publish a feed from the other plus a synthetic VEVENT noting the degraded state. Requires a state file or a query of the previous output.
- **Feed validation badge** in `README.md` showing the timestamp of the last successful merge.
- **Custom domain** if `akaihola.github.io/jazz-calendar-helsinki-unified` is unsatisfactory.
- **Geographic filtering** if the user later decides to restrict to Helsinki metro.
- **Description merging** when a collision is found, instead of dropping one source.

## 12. Open items

None blocking. All clarifying questions were resolved during brainstorming (no geo filter; +30 days history; Proposal 1; repo name `akaihola/jazz-calendar-helsinki-unified`; 6-hour cadence).

---
title: Jazz Calendar Finland — Unified iCalendar Merger
date: 2026-04-27
status: draft
owner: akaihola (with Claude Code)
repo: github.com/akaihola/jazz-calendar-finland
---

# Jazz Calendar Finland — Unified iCalendar Merger

## 1. Purpose

Publish a single public iCalendar (RFC 5545) feed that is the de-duplicated union of two upstream feeds of jazz concerts in the Finland:

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

A single public GitHub repository, `akaihola/jazz-calendar-finland`, contains:

- A Python script that fetches both upstream feeds, merges them, and writes `docs/calendar.ics`.
- A GitHub Actions workflow that runs the script on a 6-hour schedule and on pushes to `main`, then commits any change to `docs/calendar.ics`.
- GitHub Pages configured to serve the `docs/` directory of `main`.

### 3.1 Public URL

`https://akaihola.github.io/jazz-calendar-finland/calendar.ics`

This is the only contract with consumers.

### 3.2 Data flow

```
                       ┌──────────────────────────────┐
                       │  GitHub Actions cron          │
                       │  (every 6h + on push)         │
                       └──────────────┬───────────────┘
                                      │ runs
                                      ▼
   ┌──────────────────┐   fetch    ┌──────────────────────┐ fetch ┌────────────────────┐
   │ suomijazz.com    │◀───────────│ jazz_calendar.merge  │──────▶│ calendar.google.com│
   │ (GigPress, ~73K) │            │ (Python + icalendar) │       │ (Jazz-kalenteri,   │
   └──────────────────┘            └──────────┬───────────┘       │  ~20MB historical) │
                                              │ writes            └────────────────────┘
                                            ▼
                                 docs/calendar.ics  (committed if changed)
                                            │
                                            │ served by GitHub Pages
                                            ▼
                  https://akaihola.github.io/jazz-calendar-finland/calendar.ics
```

### 3.3 Repository layout

```
.
├── .github/workflows/
│   ├── refresh.yml                   # cron + on-push workflow (publishes feed)
│   └── test.yml                      # runs pytest on push/PR
├── docs/
│   ├── calendar.ics                  # the published feed (committed by CI)
│   └── index.html                    # one-page README pointing at the feed
├── src/jazz_calendar/                # importable package
│   ├── __init__.py
│   ├── merge.py                      # entry point (uv run python -m jazz_calendar.merge)
│   ├── fetch.py                      # upstream HTTP fetch
│   ├── source.py                     # tag VEvents with their source (gcal|suomijazz)
│   ├── patch.py                      # source-specific patches (e.g. SuomiJazz DTEND fix)
│   ├── dedup.py                      # collision detection + fold
│   ├── window.py                     # time-window filter (incl. RRULE handling)
│   └── normalize.py                  # location/title normalization helpers
├── tests/
│   ├── fixtures/                     # captured upstream samples
│   ├── test_fetch.py
│   ├── test_normalize.py
│   ├── test_source.py
│   ├── test_patch.py
│   ├── test_dedup.py
│   ├── test_window.py
│   └── test_merge.py
├── pyproject.toml                    # uv-managed deps; declares jazz_calendar package
├── uv.lock
├── README.md
├── .gitignore
└── docs/superpowers/specs/...        # this document and successors
```

`pyproject.toml` uses the `uv_build` backend:

```
[build-system]
requires = ["uv_build>=0.11.0,<0.12.0"]
build-backend = "uv_build"
```

so `python -m jazz_calendar.merge` works after `uv sync`. Required Python: `>=3.13`. Pinned runtime deps: `icalendar>=7,<8`. Pinned dev deps: `pytest>=9,<10`.

`docs/index.html` is a 10-line static page so visitors who hit the project root get a hint about the feed URL; nothing else.

### 3.4 Vibe-coded labeling

The repository is labeled as AI-developed, in line with the maintainer's policy for similar projects (cf. `github.com/akaihola/pykoclaw`):

- **GitHub topics** on the repo: `vibe-coded`, `claude-code` (set during bootstrap, §9.1).
- **README badge** at the top:
  `[![Built with Claude Code](https://img.shields.io/badge/Built_with-Claude_Code-6f42c1?logo=anthropic&logoColor=white)](https://claude.ai/code)`
- **README notice** immediately under the title:
  `> This project is developed by an AI coding agent ([Claude Code](https://claude.ai/code)), with human oversight and direction.`
- **`docs/index.html`** carries the same notice in plain HTML so visitors to the published Pages site see it without clicking through to the repo.

## 4. Components

Each component is a small Python module with a single responsibility, importable in isolation, and unit-testable without network or filesystem fixtures beyond `tests/fixtures/`.

### 4.1 `fetch.py` — Upstream fetch

- Public function: `fetch_feed(url: str, *, timeout: float = 30.0) -> bytes`
- Uses `urllib.request` (stdlib) to keep the dependency surface minimal.
- Sends a `User-Agent: jazz-calendar-finland/1.0 (+https://github.com/akaihola/jazz-calendar-finland)`.
- Raises a typed `FetchError` on non-2xx, network failure, or timeout. The caller (the workflow) decides whether to abort.
- No retry logic in v1: the workflow already retries every 6 hours.

### 4.2 `normalize.py` — Field normalisation

- `normalize_location(loc: str) -> str`: take the first comma-separated segment, strip whitespace, lowercase, NFD-strip diacritics, collapse internal whitespace.
- `round_dt_to_15min(dt: datetime) -> datetime`: convert to UTC, round to nearest 15-minute boundary.
- `normalize_summary(s: str) -> str`: lowercase, strip diacritics, collapse whitespace; used only for tie-breaker logging, not as a primary key.

### 4.3 `source.py` — Source tagging

- Public function: `tag_source(events: Iterable[VEvent], source: Literal["gcal", "suomijazz"]) -> Iterator[VEvent]`
- Adds an `X-JAZZFI-SOURCE` property to each event with value `"gcal"` or `"suomijazz"`.
- Called immediately after parsing each upstream feed, before any other transformation. This is the only mechanism by which downstream stages know an event's origin.

### 4.4 `patch.py` — Source-specific patches

- Public function: `patch_event(event: VEvent) -> VEvent` (mutates and returns the same instance).
- Currently performs one transform: when `event["X-JAZZFI-SOURCE"] == "suomijazz"` and `DTSTART == DTEND`, sets `DTEND = DTSTART + 2 hours` and adds the parameter `X-JAZZFI-DURATION-ESTIMATED=true` to the DTEND property.
- Designed as a chain so future per-source patches can be added without touching `merge.py`.
- Tested as a unit: `tests/test_patch.py`.

### 4.5 `dedup.py` — De-duplication

- Public function: `dedup(events: Iterable[VEvent], *, prefer: Callable[[VEvent], int] = default_prefer) -> list[VEvent]`
- Computes a key per event: `(round_dt_to_15min(DTSTART_utc), normalize_location(LOCATION))`.
- On collision, keeps the event whose `prefer(...)` returns the highest integer; logs the discarded event's source and UID at INFO.
- `default_prefer(event)` reads `X-JAZZFI-SOURCE`: returns `2` for `"gcal"`, `1` for `"suomijazz"`, `0` otherwise. This is the contract between §4.3 (tagger) and §4.5 (resolver).
- Events with missing or unparsable DTSTART or LOCATION get a synthetic uniquifier in the key (so they cannot collide); they are passed through unchanged and logged at WARNING level.

### 4.6 `window.py` — Time-window filter

- Public function: `in_window(event: VEvent, *, now: datetime, past_days: int = 30) -> bool`
- For non-recurring events, returns `True` iff `DTSTART_utc >= now - past_days` (no upper bound on the future).
- For recurring events (VEVENT with an `RRULE` property): returns `True` iff **either** (a) `DTSTART_utc >= now - past_days`, **or** (b) `RRULE` has no `UNTIL` parameter (open-ended series), **or** (c) `RRULE.UNTIL >= now - past_days`. The master VEVENT is then emitted unchanged; instances are not exploded. Calendar clients perform their own expansion.
- This rule keeps long-running recurring series (whose master DTSTART may be from 2014) visible while still filtering out series that ended over 30 days ago.

### 4.7 `merge.py` — Orchestration

- The two upstream URLs are module-level constants (`SUOMIJAZZ_URL`, `GCAL_URL`) and may be overridden by same-named environment variables (test seam). Captures `now_utc = datetime.now(UTC)` once.
- Pipeline:
  1. `fetch_feed(SUOMIJAZZ_URL)` → `Calendar.from_ical(...)` → `tag_source(..., "suomijazz")` → `patch_event(...)` per event.
  2. `fetch_feed(GCAL_URL)` → `Calendar.from_ical(...)` → `tag_source(..., "gcal")` → `patch_event(...)` per event (no-op for gcal today).
  3. Concatenate both event streams.
  4. Filter via `window.in_window(now=now_utc)`.
  5. `dedup.dedup(events)`.
- Sanity guards (any failure ⇒ exit non-zero, no file written):
  - Total kept events must be > 0.
  - Total kept events must be ≥ 50% of the count published in the previous `docs/calendar.ics` (when one exists). Reads the previous file from disk before regenerating.
- Builds the output `Calendar` with:
  - `PRODID:-//akaihola//jazz-calendar-finland//EN`
  - `VERSION:2.0`
  - `CALSCALE:GREGORIAN`
  - `METHOD:PUBLISH`
  - `X-WR-CALNAME:Jazz Finland (unified)`
  - `X-WR-TIMEZONE:Europe/Helsinki`
  - The `Europe/Helsinki` `VTIMEZONE` taken from the GCal feed (canonical).
- Validates the serialised output by round-tripping it through `Calendar.from_ical(...)`; aborts on parse error.
- Writes the result to `docs/calendar.ics` (plain `Path.write_bytes`; atomicity at the FS layer is unnecessary because consumers read the committed git blob, not the working tree).
- Exits non-zero on any unrecoverable error so the workflow does not commit a broken file.

### 4.8 `.github/workflows/refresh.yml` — Workflow

- Triggers:
  - `schedule: cron: '17 */6 * * *'` (00:17, 06:17, 12:17, 18:17 UTC — off-the-hour to dodge the GitHub Actions cron rush).
  - `workflow_dispatch` (manual trigger from CLI / UI).
  - `push` to `main` for paths `src/**`, `pyproject.toml`, `uv.lock`, or `.github/workflows/refresh.yml` (so code, dependency, and workflow changes regenerate immediately).
- Steps:
  1. `actions/checkout@v6` with `persist-credentials: true`.
  2. Install `uv` via `astral-sh/setup-uv@v8` (pinned `version: 0.11.x`).
  3. Run `uv sync --frozen`.
  4. Run `uv run python -m jazz_calendar.merge`.
  5. If `git status --porcelain docs/calendar.ics` is non-empty, configure committer identity, `git add docs/calendar.ics`, `git commit -m "chore(feed): refresh $(date -u +%FT%TZ)"`, and `git push`. **No deduplication of "trivial" changes.** Each scheduled run that produces any byte-difference (including DTSTAMP drift from upstream) creates a commit. This is intentional simplicity; see §7 row "Trivial-only diff" for the rationale.
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
| SuomiJazz `DTSTART == DTEND` | DTEND set to DTSTART + 2 hours before dedup. Documented in `X-JAZZFI-DURATION-ESTIMATED`. |

## 6. Time window

- **Past floor:** an event is kept iff its `DTSTART_utc >= now_utc - 30 days` (or it is a recurring series whose `RRULE` keeps it alive past that floor; see §4.6).
- **Future ceiling:** none. All future events are kept.
- `now_utc` is captured once at the start of `jazz_calendar.merge` and reused for both filters, so the boundary is consistent within a run.

## 7. Failure handling

| Failure | Result |
|---|---|
| Either upstream returns non-2xx, times out, or returns invalid ICS | `merge.py` exits non-zero; the workflow step fails; previous `docs/calendar.ics` continues to serve unchanged. GitHub Actions emails the repo owner on failure (default behavior). |
| Round-trip parse of generated output fails | `merge.py` exits non-zero before writing the file. Tested in `test_merge.py`. |
| Output contains zero events | `merge.py` exits non-zero; previous file unchanged. Tested. |
| Output contains < 50 % of the previously published event count | `merge.py` exits non-zero; previous file unchanged. Tested. (Catches partial-parse regressions that would otherwise sneak through.) |
| Output is byte-identical to the previously committed file | No commit; workflow exits 0. (This is rare in practice; see "Trivial-only diff" below.) |
| Trivial-only diff (only DTSTAMP / re-formatted property order differs) | A commit is still created. v1 accepts this commit churn — at 4 runs/day × ~365 days that is ~1.5k commits/year on a single small file, well within Git's pack efficiency. The simpler diff logic is preferred over a content-hash compare. |
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

**Implementation discipline:** every module is built using strict red/green TDD. For each unit:

1. **Red.** Write the failing test(s) first. Run `uv run pytest -q tests/test_<module>.py` and confirm a *red* result (test fails for the expected reason — assertion failure, not import error).
2. **Green.** Write the smallest implementation that makes the tests pass. Run the same command and confirm green.
3. **Refactor** if needed, keeping the suite green.

Modules are built in the order: `fetch` → `normalize` → `source` → `patch` → `dedup` → `window` → `merge`. Each stage's tests use only the previously-built modules plus stdlib.

- **Unit tests** (`pytest`) cover every module listed in §4 in isolation, with no network:
  - `test_fetch.py` — happy path with a mocked `urllib.request.urlopen`; `FetchError` paths for non-2xx, timeout, and connection error.
  - `test_normalize.py` — comma-segment extraction, NFD diacritic stripping, 15-minute rounding incl. boundary cases (e.g. 22:53 → 23:00).
  - `test_source.py` — `tag_source` writes the expected `X-JAZZFI-SOURCE` value; calling it twice on the same event leaves the value at the latest call (idempotent shape).
  - `test_patch.py` — SuomiJazz `DTSTART == DTEND` ⇒ `DTEND = DTSTART + 2h` with `X-JAZZFI-DURATION-ESTIMATED=true`; gcal events untouched.
  - `test_dedup.py` — confirmed real-world Manala collision (fixture); preference of gcal over suomijazz; passthrough for missing DTSTART/LOCATION.
  - `test_window.py` — past-30-days cutoff; future events kept; recurring events with `UNTIL` in the past dropped; recurring events with no `UNTIL` kept regardless of master DTSTART age.
  - `test_merge.py` — zero-event guard, < 50 % drop guard, round-trip parse guard, end-to-end snapshot.
- **Integration test** in `test_merge.py` runs the full pipeline against captured upstream samples in `tests/fixtures/` and snapshots the output. Snapshot is committed and reviewed in PRs.
- **Fixtures** are byte copies of the two upstream feeds captured at spec time, plus minimal hand-crafted feeds for edge cases. `tests/fixtures/README.md` records when and how each was captured.
- **CI**: `.github/workflows/test.yml` runs `uv run pytest -q` on every push and PR. The refresh workflow does not run tests (it only publishes).
- **No live-network tests in CI** — fixtures are refreshed manually when upstream formats change.

## 9. Operations

### 9.1 Bootstrap (one-time)

The "no human operators" framing in §1 applies to *steady-state* operation. The first deploy is performed once by Claude Code from the host that has GitHub push authority for the owner's account. The bootstrap steps are:

1. Create the public repo via `gh repo create akaihola/jazz-calendar-finland --public --source=. --push`.
2. Add GitHub topics: `gh repo edit --add-topic vibe-coded --add-topic claude-code --add-topic icalendar --add-topic finland --add-topic jazz`.
3. Enable GitHub Pages: `gh api repos/akaihola/jazz-calendar-finland/pages -X POST -f source.branch=main -f source.path=/docs`.
4. Trigger the first run: `gh workflow run refresh.yml`.
5. Confirm the published feed at the public URL.

After this, no human or host-specific action is required.

### 9.2 Steady state

- The workflow runs every 6 hours unattended.
- Triggering an out-of-band refresh: `gh workflow run refresh.yml` from any clone with auth, or push any change under `src/`.
- Rotating credentials: none required; the workflow uses the default `GITHUB_TOKEN`.

## 10. Cost & maintenance

- **Money:** $0/year. Public repos get unlimited Actions minutes; this workflow uses ~30 s/run × 4 runs/day ≈ 12 min/month. GitHub Pages bandwidth on a static <1 MB file is well within the 100 GB/month soft limit even with thousands of subscribers.
- **Agent-hours/year:** estimated <2 h, dominated by responding to upstream format changes (e.g., GigPress plugin upgrade). Routine operation: zero.

## 11. Future work (out of scope for v1)

- **Partial-success mode:** if one upstream is down, publish a feed from the other plus a synthetic VEVENT noting the degraded state. Requires a state file or a query of the previous output.
- **Feed validation badge** in `README.md` showing the timestamp of the last successful merge.
- **Last-merge timestamp on `docs/index.html`** extracted from the most recent commit message (free observability without a separate badge).
- **Quarterly fixture refresh job** that opens a PR re-capturing `tests/fixtures/` from upstream, so format-drift tests stay realistic.
- **Custom domain** if `akaihola.github.io/jazz-calendar-finland` is unsatisfactory.
- **Geographic filtering** if the user later decides to restrict to a sub-region (e.g. Helsinki metro).
- **Description merging** when a collision is found, instead of dropping one source.
- **Content-stable DTSTAMP** to eliminate commit churn, if the per-run commit pattern in §7 becomes a problem.

## 12. Open items

None blocking. All clarifying questions were resolved during brainstorming (no geo filter; +30 days history; Proposal 1; repo name `akaihola/jazz-calendar-finland`; 6-hour cadence).

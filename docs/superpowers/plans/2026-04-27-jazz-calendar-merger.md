# Jazz Calendar Helsinki — Implementation Plan

> **For agentic workers:** REQUIRED: Use `superpowers:subagent-driven-development` (if subagents available) or `superpowers:executing-plans` to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, and deploy the de-duplicated unified iCalendar feed described in the spec.

**Architecture:** A small Python package (`jazz_calendar`) is run by a 6-hourly GitHub Actions workflow, which commits the merged `docs/calendar.ics` to `main`; GitHub Pages serves it.

**Tech Stack:** Python ≥3.13, `icalendar` 7.x, `pytest` 9.x, `uv` + `uv_build` 0.11.x, GitHub Actions (`actions/checkout@v6`, `astral-sh/setup-uv@v8`), GitHub Pages.

---

## Resuming this plan in a fresh session

If you (a future Claude Code session) are picking this plan up cold, do this in order, then continue from the first unchecked task:

1. `cd /home/akaihola/prg/jazz-calendar-helsinki-unified` (or the equivalent worktree).
2. Read the spec: `docs/superpowers/specs/2026-04-27-jazz-calendar-merger-design.md` — single source of truth for behavior. The plan refers to spec sections as `[spec §N]`.
3. Read this plan and run `git log --oneline -- docs/superpowers/plans/2026-04-27-jazz-calendar-merger.md src/ tests/ .github/` to see what has already been committed.
4. Look at this file (`docs/superpowers/plans/2026-04-27-jazz-calendar-merger.md`) — completed tasks have `[x]` checkboxes; resume at the first `[ ]`.
5. Captured upstream samples used by tests live under `tests/fixtures/` once Chunk 1 is done. They are byte snapshots, not regenerated automatically.
6. Bootstrap (Chunk 10) is the only chunk that mutates anything outside the repo. Skip Chunk 10 entirely if both `gh repo view akaihola/jazz-calendar-helsinki-unified` returns success **and** `gh api repos/akaihola/jazz-calendar-helsinki-unified/pages` returns an `html_url`. Otherwise run only the tasks whose preconditions are not yet met (each task in Chunk 10 carries its own idempotency check).
7. Network is required for Task 1.3 (capturing fixtures) and the manual smoke step in Task 8.2. Other tasks run offline. If network is unavailable when those tasks run, abort and surface the blockage to the user.

**Discipline:** strict red/green TDD per [spec §8]. For every task: write the test first, run pytest and observe red, write the smallest implementation that makes it green, commit. Do not batch tests-and-implementation into one commit unless this plan says so.

**Verification command (used after every implementation step):** `uv run pytest -q`. Add `-x` to stop on the first failure.

**Conventional Commits:** all commits use Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`, `ci:`, `fix:`, `build:`).

---

## Chunk 1: Project skeleton

### Task 1.1: pyproject.toml + package init

**Files:**
- Create: `pyproject.toml`
- Create: `src/jazz_calendar/__init__.py` (empty)

- [ ] Write `pyproject.toml` with: project name `jazz-calendar-helsinki-unified`, version `0.1.0`, `requires-python = ">=3.13"`, runtime dep `icalendar>=7,<8`, dev dep `pytest>=9,<10`, build-system using `uv_build>=0.11.0,<0.12.0`. Match the conventions in [spec §3.3].
- [ ] Create empty `src/jazz_calendar/__init__.py`.
- [ ] Run `uv sync` — expect a fresh `uv.lock`.
- [ ] Run `uv run python -c "import jazz_calendar"` — expect no output, exit 0.
- [ ] Commit: `build: scaffold uv_build python package`.

### Task 1.2: README with vibe-coded labeling

**Files:**
- Create: `README.md`

Per [spec §3.4]. Include:

- [ ] Title `# jazz-calendar-helsinki-unified`.
- [ ] Built-with-Claude-Code badge (use the exact shields.io URL from §3.4).
- [ ] The blockquote notice from §3.4.
- [ ] One paragraph describing the project and the public feed URL `https://akaihola.github.io/jazz-calendar-helsinki-unified/calendar.ics`.
- [ ] List of upstream feeds.
- [ ] A "Development" subsection: `uv sync`, `uv run pytest`, `uv run python -m jazz_calendar.merge`.
- [ ] Commit: `docs: add README with vibe-coded labeling`.

### Task 1.3: Captured upstream fixtures

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/fixtures/suomijazz.ics` (byte copy of `https://suomijazz.com/?feed=gigpress-ical`)
- Create: `tests/fixtures/gcal.ics` (byte copy of the public Google Calendar feed; URL in [spec §1])
- Create: `tests/fixtures/README.md` (one paragraph: when captured, how, and the warning that they must not be regenerated automatically)

- [ ] `curl -sL --max-time 60 -o tests/fixtures/suomijazz.ics "https://suomijazz.com/?feed=gigpress-ical"`
- [ ] `curl -sL --max-time 60 -o tests/fixtures/gcal.ics "https://calendar.google.com/calendar/ical/ub9hkd0tjl3vk82t9jn5qudemc%40group.calendar.google.com/public/basic.ics"`
- [ ] Spot-check both: `head -3 tests/fixtures/*.ics` should show `BEGIN:VCALENDAR` lines.
- [ ] Write `tests/fixtures/README.md` recording capture date and reproducer commands.
- [ ] Commit: `test: capture upstream feed fixtures`.

### Task 1.4: Hand-crafted edge-case fixtures

**Files:**
- Create: `tests/fixtures/manala_collision_suomijazz.ics` — a minimal VCALENDAR with the single SuomiJazz Manala event from the captured fixture.
- Create: `tests/fixtures/manala_collision_gcal.ics` — same event from gcal.
- Create: `tests/fixtures/recurring_with_until.ics` — one VEVENT with `RRULE:FREQ=WEEKLY;UNTIL=20140601T000000Z` (long expired).
- Create: `tests/fixtures/recurring_open_ended.ics` — one VEVENT with `RRULE:FREQ=WEEKLY` and master DTSTART in 2014.
- Create: `tests/fixtures/missing_dtstart.ics` — one VEVENT with no DTSTART.

These fixtures are test data, not code, so there is no red/green cycle for this task — only creation and validation.

- [ ] Extract the Manala VEVENTs from the captured fixtures (the spec's confirmed collision example: 2026-04-30 17:00 EEST at Ravintola Manala, [spec §5.2]). Each extracted file must be a complete VCALENDAR (`BEGIN:VCALENDAR` … `END:VCALENDAR`) containing exactly one VEVENT and a minimal `VERSION:2.0` + `PRODID:...` header.
- [ ] Hand-craft the recurring-event and missing-DTSTART fixtures (≤15 lines each).
- [ ] Verify each new fixture parses cleanly: `for f in tests/fixtures/{manala_collision_suomijazz,manala_collision_gcal,recurring_with_until,recurring_open_ended,missing_dtstart}.ics; do uv run python -c "from icalendar import Calendar; c=Calendar.from_ical(open('$f','rb').read()); n=len(list(c.walk('VEVENT'))); print('$f', n); assert n==1" || exit 1; done`
- [ ] Commit: `test: add edge-case ICS fixtures`.

---

## Chunk 2: `fetch` module

[spec §4.1]

### Task 2.1: Test cases for `fetch_feed`

**Files:**
- Create: `tests/test_fetch.py`

Cover three behaviors:

- [ ] `test_fetch_feed_returns_bytes_on_2xx` — patch `urllib.request.urlopen` to return a fake response with `read()` returning `b"BEGIN:VCALENDAR..."`; assert `fetch_feed("https://example/")` returns those bytes.
- [ ] `test_fetch_feed_raises_on_non_2xx` — patch `urlopen` to raise `urllib.error.HTTPError` with `code=500`; assert `FetchError` is raised, with the URL and status code in the message.
- [ ] `test_fetch_feed_raises_on_timeout` — patch `urlopen` to raise `socket.timeout`; assert `FetchError`.
- [ ] `test_fetch_feed_sends_user_agent` — assert the `Request` passed to `urlopen` carries the `User-Agent` from [spec §4.1].
- [ ] Run `uv run pytest tests/test_fetch.py -v` — expect 4 reds (module not found).
- [ ] Commit: `test(fetch): add failing tests for HTTP fetch contract`.

### Task 2.2: Implement `fetch_feed`

**Files:**
- Create: `src/jazz_calendar/fetch.py`

- [ ] Implement `FetchError(Exception)` and `fetch_feed(url, *, timeout=30.0) -> bytes` per [spec §4.1]. Use stdlib `urllib.request` only.
- [ ] Run `uv run pytest tests/test_fetch.py -v` — expect 4 greens.
- [ ] Commit: `feat(fetch): implement upstream HTTP fetch`.

---

## Chunk 3: `normalize` module

[spec §4.2]

### Task 3.1: Tests for normalize helpers

**Files:**
- Create: `tests/test_normalize.py`

- [ ] `test_normalize_location_takes_first_segment` — `"Koko Jazz Club, Hämeentie 3, Helsinki, FI"` → `"koko jazz club"` (lower, no diacritics, head segment).
- [ ] `test_normalize_location_strips_diacritics` — `"Töölö Jazzklubi"` → `"toolo jazzklubi"`.
- [ ] `test_normalize_location_collapses_whitespace` — `"  Koko   Jazz Club "` (head segment) → `"koko jazz club"`.
- [ ] `test_round_dt_to_15min_below_boundary` — `2026-04-27 22:53` (UTC) → `2026-04-27 23:00`.
- [ ] `test_round_dt_to_15min_above_boundary` — `2026-04-27 22:07` (UTC) → `2026-04-27 22:00`.
- [ ] `test_round_dt_to_15min_converts_naive_or_aware_to_utc` — pass a `datetime` with `Europe/Helsinki` tz; assert the UTC rounding is correct.
- [ ] `test_normalize_summary` — `"Bill Frisell & Eyvind Kang at Promenadisali"` → `"bill frisell & eyvind kang at promenadisali"`.
- [ ] Run pytest — expect reds.
- [ ] Commit: `test(normalize): add failing tests for normalization helpers`.

### Task 3.2: Implement normalize

**Files:**
- Create: `src/jazz_calendar/normalize.py`

- [ ] Implement `normalize_location`, `round_dt_to_15min`, `normalize_summary` per [spec §4.2]. Use `unicodedata.normalize("NFKD", s)` then strip combining marks.
- [ ] Run pytest — green.
- [ ] Commit: `feat(normalize): implement field normalization helpers`.

---

## Chunk 4: `source` module

[spec §4.3]

### Task 4.1: Tests for `tag_source`

**Files:**
- Create: `tests/test_source.py`

- [ ] `test_tag_source_writes_property` — given two `icalendar.Event` instances, `tag_source([e1, e2], "gcal")` yields events whose `e["X-JAZZHKI-SOURCE"]` equals `"gcal"`.
- [ ] `test_tag_source_idempotent_overwrite` — calling `tag_source(..., "suomijazz")` then `tag_source(..., "gcal")` on the same event leaves the property at `"gcal"`.
- [ ] Run pytest — red.
- [ ] Commit: `test(source): add failing tests for X-JAZZHKI-SOURCE tagging`.

### Task 4.2: Implement source tagging

**Files:**
- Create: `src/jazz_calendar/source.py`

- [ ] Implement `tag_source(events, source) -> Iterator[Event]` per [spec §4.3]. Use `Event.__setitem__` (icalendar 7 API).
- [ ] Run pytest — green.
- [ ] Commit: `feat(source): tag events with X-JAZZHKI-SOURCE`.

---

## Chunk 5: `patch` module

[spec §4.4]

### Task 5.1: Tests for `patch_event`

**Files:**
- Create: `tests/test_patch.py`

- [ ] `test_patch_suomijazz_dtstart_equals_dtend` — Event with `X-JAZZHKI-SOURCE=suomijazz` and `DTSTART==DTEND` is patched: `DTEND = DTSTART + 2h`, parameter `X-JAZZHKI-DURATION-ESTIMATED=true` on DTEND.
- [ ] `test_patch_suomijazz_real_duration_left_alone` — Event with `DTSTART < DTEND` is unchanged.
- [ ] `test_patch_gcal_event_unchanged` — Event with `X-JAZZHKI-SOURCE=gcal` is never modified, even if `DTSTART==DTEND`.
- [ ] Run pytest — red.
- [ ] Commit: `test(patch): add failing tests for SuomiJazz duration patch`.

### Task 5.2: Implement patch

**Files:**
- Create: `src/jazz_calendar/patch.py`

- [ ] Implement `patch_event(event) -> Event` mutating in place per [spec §4.4]. Two-hour delta as `timedelta(hours=2)`.
- [ ] Run pytest — green.
- [ ] Commit: `feat(patch): fix SuomiJazz zero-duration events`.

---

## Chunk 6: `dedup` module

[spec §4.5]

### Task 6.1: Tests for `dedup`

**Files:**
- Create: `tests/test_dedup.py`

- [ ] `test_dedup_real_world_collision` — load `tests/fixtures/manala_collision_*.ics`, run `tag_source` on each, concatenate, run `dedup`. Expect exactly one event in the result, and that event's `X-JAZZHKI-SOURCE` is `"gcal"`.
- [ ] `test_dedup_keeps_distinct_events` — two events at the same venue but 60 min apart are both kept.
- [ ] `test_dedup_keeps_same_time_distinct_venues` — two events at the same start time but different venues are both kept.
- [ ] `test_dedup_passes_through_event_missing_dtstart` — an event without DTSTART is kept (with synthetic uniquifier so it never collides).
- [ ] `test_dedup_passes_through_event_missing_location` — same for missing LOCATION.
- [ ] `test_default_prefer_gcal_over_suomijazz` — `default_prefer(gcal_event) > default_prefer(suomijazz_event)`.
- [ ] Run pytest — red.
- [ ] Commit: `test(dedup): add failing tests for collision resolution`.

### Task 6.2: Implement dedup

**Files:**
- Create: `src/jazz_calendar/dedup.py`

- [ ] Implement `default_prefer(event) -> int` and `dedup(events, *, prefer=default_prefer) -> list[Event]` per [spec §4.5]. Synthetic uniquifier for missing DTSTART/LOCATION should be `id(event)` or a counter.
- [ ] Run pytest — green.
- [ ] Commit: `feat(dedup): heuristic de-duplication keyed on (DTSTART, venue head)`.

---

## Chunk 7: `window` module

[spec §4.6, §6]

### Task 7.1: Tests for `in_window`

**Files:**
- Create: `tests/test_window.py`

Use a fixed `now = datetime(2026, 4, 27, 6, 0, tzinfo=UTC)` and **pass it explicitly** to every `in_window(...)` call (synthesized events and fixture-loaded events alike). Do not call `datetime.now(...)` inside any test.

- [ ] `test_event_within_past_30_days_kept` — event at `now - 29d` ⇒ True.
- [ ] `test_event_older_than_30_days_dropped` — event at `now - 31d` ⇒ False.
- [ ] `test_future_event_kept` — event at `now + 365d` ⇒ True.
- [ ] `test_recurring_open_ended_kept_even_if_master_old` — load `recurring_open_ended.ics` (master DTSTART 2014, no UNTIL); call `in_window(event, now=now)` ⇒ True.
- [ ] `test_recurring_with_expired_until_dropped` — load `recurring_with_until.ics` (UNTIL 2014-06-01); call `in_window(event, now=now)` ⇒ False.
- [ ] `test_recurring_with_future_until_kept` — synthesize an event with master DTSTART in 2014 and `RRULE:FREQ=WEEKLY;UNTIL=20300101T000000Z` ⇒ True.
- [ ] Run pytest — red.
- [ ] Commit: `test(window): add failing tests for time window incl. RRULE`.

### Task 7.2: Implement window

**Files:**
- Create: `src/jazz_calendar/window.py`

- [ ] Implement `in_window(event, *, now, past_days=30) -> bool` per [spec §4.6]. Parse the event's `RRULE` via `icalendar.vRecur`/`event["RRULE"]`; read `UNTIL`.
- [ ] Run pytest — green.
- [ ] Commit: `feat(window): time-window filter with RRULE-aware semantics`.

---

## Chunk 8: `merge` orchestration

[spec §4.7]

### Task 8.1: Test the orchestration guards

**Files:**
- Create: `tests/test_merge.py`

Tests drive `merge.py` through a documented test seam — three module-level constants overridable by same-named env vars: `SUOMIJAZZ_URL`, `GCAL_URL`, `JAZZ_CALENDAR_OUTPUT` (output path), plus `JAZZ_CALENDAR_NOW` (an ISO-8601 UTC timestamp used in place of `datetime.now(UTC)` when set). All four are added in Task 8.2. Tests also `monkeypatch` `fetch.fetch_feed` to read from local fixture paths instead of the network.

Note: byte-identical "skip the commit" behavior lives in the workflow ([spec §4.8] step 5), not in `merge.py` — `merge.py` always writes. So this chunk does not test that case.

- [ ] `test_merge_happy_path_writes_valid_ics` — point both URLs at the captured fixtures; run `jazz_calendar.merge.main()`; read the written file; round-trip through `Calendar.from_ical`; assert ≥ 1 VEVENT and presence of the Manala event exactly once.
- [ ] `test_merge_zero_events_aborts` — set `JAZZ_CALENDAR_NOW` to a date far in the future (e.g. `2099-01-01T00:00:00+00:00`) so the window drops every fixture event; assert `main()` raises `SystemExit` non-zero and the output file is not modified.
- [ ] `test_merge_below_50pct_aborts` — pre-write a fake "previous" `calendar.ics` containing 100 synthetic VEVENTs; configure fixtures yielding only 30 events; assert non-zero exit and the previous file is byte-unchanged.
- [ ] `test_merge_round_trip_parse_failure_aborts` — monkey-patch the serializer (`Calendar.to_ical` or the round-trip step) to emit deliberately broken bytes; assert non-zero exit and the previous file is byte-unchanged.
- [ ] Run pytest — red.
- [ ] Commit: `test(merge): add failing tests for orchestration guards`.

### Task 8.2: Implement merge

**Files:**
- Create: `src/jazz_calendar/merge.py`

- [ ] Implement `main()` per [spec §4.7] pipeline: fetch → parse → tag → patch → window → dedup → guards (zero-event, <50%, round-trip parse) → build VCALENDAR → write `Path.write_bytes`. Take VTIMEZONE from the gcal feed [spec §4.7]. The "<50%" guard reads the existing `docs/calendar.ics` (if present) and counts its VEVENTs.
- [ ] Add the four env-var test seams (`SUOMIJAZZ_URL`, `GCAL_URL`, `JAZZ_CALENDAR_OUTPUT`, `JAZZ_CALENDAR_NOW`) as module-level constants overridden by `os.environ.get(...)`.
- [ ] Add `if __name__ == "__main__": main()`.
- [ ] Run pytest — green.
- [ ] `[network-required]` Live smoke test: `uv run python -m jazz_calendar.merge` — expect `docs/calendar.ics` to appear or update. Validate: `uv run python -c "from icalendar import Calendar; print(len(list(Calendar.from_ical(open('docs/calendar.ics','rb').read()).walk('VEVENT'))))"`. Skip this step if offline.
- [ ] Commit: `feat(merge): orchestrate fetch/tag/patch/window/dedup/write`.

### Task 8.3: Landing page + first published `docs/calendar.ics`

**Files:**
- Create: `docs/index.html`
- Modify (already created in Task 8.2 smoke test, or generate now): `docs/calendar.ics`

Per [spec §3.4]. Minimal HTML: page title, the vibe-coded notice as `<p>` with the same wording, a paragraph linking to `calendar.ics` with copy-paste subscribe instructions for Google/Apple/Thunderbird, link to the GitHub repo. Keep under 60 lines.

- [ ] Write `docs/index.html`.
- [ ] If `docs/calendar.ics` is missing or stale (e.g., the smoke test in 8.2 was skipped), regenerate it: `uv run python -m jazz_calendar.merge` (`[network-required]`). If offline, commit only `docs/index.html` and leave `docs/calendar.ics` to be created by the first workflow run in Task 10.4.
- [ ] Commit: `feat: publish first calendar.ics + landing page` (or `feat: add landing page` if calendar.ics was deferred).

---

## Chunk 9: GitHub Actions workflows

[spec §4.8, §8]

### Task 9.1: Test workflow

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] On `push` and `pull_request` to `main`. Job runs on `ubuntu-latest`. Steps: `actions/checkout@v6`, `astral-sh/setup-uv@v8` (pin `version: 0.11.x`), `uv sync --frozen`, `uv run pytest -q`.
- [ ] Commit: `ci: add pytest workflow`.
- [ ] Verify locally with `act` if available, otherwise rely on the first push.

### Task 9.2: Refresh workflow

**Files:**
- Create: `.github/workflows/refresh.yml`

Per [spec §4.8]. Notes:
- Schedule: `cron: '17 */6 * * *'`.
- Triggers: `schedule`, `workflow_dispatch`, `push` paths `src/**`, `pyproject.toml`, `uv.lock`, `.github/workflows/refresh.yml`.
- Permissions: `contents: write`.
- Concurrency: `group: refresh, cancel-in-progress: false`.
- Steps: checkout (`persist-credentials: true`), setup-uv, `uv sync --frozen`, `uv run python -m jazz_calendar.merge`, then a final shell step that — only if `git status --porcelain docs/calendar.ics` is non-empty — runs:

      git config user.name "github-actions[bot]"
      git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
      git add docs/calendar.ics
      git commit -m "chore(feed): refresh $(date -u +%FT%TZ)"
      git push

- [ ] Write the workflow YAML.
- [ ] Commit: `ci: add 6-hourly refresh workflow`.

---

## Chunk 10: Bootstrap (one-time)

This chunk mutates external state (creates the public repo, enables Pages). Each task carries its own idempotency guard so re-running it on an already-bootstrapped project is safe.

### Task 10.1: Create the GitHub repo

- [ ] Precondition check: `gh repo view akaihola/jazz-calendar-helsinki-unified >/dev/null 2>&1` — if it succeeds, skip the create.
- [ ] Otherwise: `gh repo create akaihola/jazz-calendar-helsinki-unified --public --source=. --push --description "Public iCalendar feed merging two Helsinki jazz calendars (vibe-coded)."`
- [ ] Verify: `gh repo view akaihola/jazz-calendar-helsinki-unified` exits 0.

### Task 10.2: Add topics

`gh repo edit --add-topic` is idempotent (re-adding an existing topic is a no-op), so no precondition guard is needed.

- [ ] `gh repo edit akaihola/jazz-calendar-helsinki-unified --add-topic vibe-coded --add-topic claude-code --add-topic icalendar --add-topic helsinki --add-topic jazz`.

### Task 10.3: Enable GitHub Pages

`gh api ... pages -X POST` returns 409 Conflict if Pages is already enabled, so guard explicitly:

- [ ] If already enabled, skip:

      if gh api repos/akaihola/jazz-calendar-helsinki-unified/pages 2>/dev/null | jq -e .html_url >/dev/null; then
        echo "Pages already enabled; skipping."
      else
        gh api repos/akaihola/jazz-calendar-helsinki-unified/pages -X POST -f source.branch=main -f source.path=/docs
      fi

- [ ] Wait ~30 s, then `gh api repos/akaihola/jazz-calendar-helsinki-unified/pages | jq .html_url` — should print the Pages URL.

### Task 10.4: First scheduled run

This task is intentionally re-runnable — `workflow_dispatch` can be triggered any number of times.

- [ ] `gh workflow run refresh.yml --repo akaihola/jazz-calendar-helsinki-unified`
- [ ] Poll `gh run list --repo akaihola/jazz-calendar-helsinki-unified --workflow refresh.yml --limit 1` until status is `success` (or `failure` — investigate via `gh run view <id> --log`).
- [ ] Confirm Pages build is built: `gh api repos/akaihola/jazz-calendar-helsinki-unified/pages/builds/latest | jq .status` — expect `"built"`.
- [ ] `curl -sI https://akaihola.github.io/jazz-calendar-helsinki-unified/calendar.ics` — assert `HTTP/2 200` and `content-type` header is either `text/calendar` or `application/octet-stream` (both are acceptable for `.ics` on Pages).
- [ ] Commit nothing (this task only triggers external state).

### Task 10.5: Smoke-subscribe check

- [ ] `curl -s https://akaihola.github.io/jazz-calendar-helsinki-unified/ | grep -F "AI coding agent"` — expect a hit on the vibe-coded notice (browser optional).
- [ ] Done.

---

## Done criteria

All checkboxes above are `[x]`. The published feed at the public URL parses cleanly with `icalendar`, contains the de-duplicated union of both upstream feeds across the past-30-days + future window, and is regenerated by the workflow every six hours without intervention.

## If you get stuck

- Spec is the truth: re-read [spec §<N>] before deviating.
- Workflow logs: `gh run list --workflow refresh.yml` then `gh run view <id> --log`.
- File history: `git log -p docs/calendar.ics | head -200`.
- Live local run: `uv run python -m jazz_calendar.merge && diff -u <(git show HEAD:docs/calendar.ics) docs/calendar.ics | head`.

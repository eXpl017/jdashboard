# Roadmap

The order is intentional: build the data layer and scraper contract before any
source, and build one source end-to-end before adding the rest.

## Phase 0 — Decisions and scaffolding

**Tasks**

- Confirm the open questions in [questions.md](questions.md).
- Create `pyproject.toml` with runtime and dev dependencies.
- Create `.env.example`, `.gitignore`, `Makefile`, and `README.md`.
- Create the `app/` package skeleton and empty modules.
- Add `ruff` and `pytest` configuration.
- Add a trivial health route and a test for it.

**Acceptance**

- [ ] `uv sync --extra dev` succeeds.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run pytest` passes (at least the health test).
- [ ] `uv run uvicorn app.main:app --reload` serves `GET /health`.

## Phase 1 — Database and query API

**Tasks**

- Implement `app/db.py` with SQLite engine, session factory, and PRAGMAs.
- Implement SQLAlchemy models: `Job`, `JobTag`, `ScrapeRun`,
  `ScrapeSourceResult`, `SourceState`.
- Implement `repository.py`:
  - `upsert_job`
  - `upsert_many`
  - `query_jobs`
  - `get_job`
  - `stats`
  - `create_run`, `finish_run`, `create_source_result`, `finish_source_result`
- Implement Pydantic schemas for API responses.
- Implement `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/stats`.
- Add repository tests with an in-memory SQLite database.
- Add API tests with `TestClient`.

**Acceptance**

- [ ] Fixture jobs can be inserted and queried.
- [ ] Filters (`q`, `source`, `days`, `remote`, `tag`, `role`, `language`,
      `location_scope`, `visa`) work.
- [ ] Default query returns technical roles and excludes `international_remote`.
- [ ] Duplicate fingerprints do not create duplicate rows.
- [ ] `first_seen_at` is preserved on update.
- [ ] Tests pass without network access.

## Phase 2 — Scraper framework and refresh service

**Tasks**

- Implement `ScrapedJob`, `ScrapeResult`, `BaseScraper`, and `ScraperError`.
- Implement `services/http.py`:
  - httpx client
  - robots.txt cache and check
  - retry/backoff
  - per-host rate limit
  - concurrency semaphore
- Implement `services/dates.py`, `normalize.py`, `classify.py`, including
  `detect_language`, `detect_location_scope`, `detect_overseas_eligible`, and
  `role_category` assignment.
- Implement `registry.py` with the five source classes (stubs at first).
- Implement `services/refresh.py`:
  - `asyncio.Lock`
  - run creation
  - per-source progress
  - partial failure handling
  - upsert and run statistics
- Implement `POST /api/refresh` and `GET /api/refresh/status`.
- Add a fake scraper for tests.
- Add tests for:
  - lock/409 behavior
  - partial failure
  - run records
  - progress transitions

**Acceptance**

- [ ] A fake scraper runs end-to-end and writes jobs.
- [ ] A failing source produces `partial`, not a crash.
- [ ] A second refresh while running returns `409`.
- [ ] Run and source results are persisted.
- [ ] No scraping happens at startup.

## Phase 3 — Source scrapers

Do one source at a time. For each: save fixtures, implement parser, add tests,
run a live smoke test, update docs.

### Phase 3a — Michael Page

- Listing: `https://www.michaelpage.co.jp/en/jobs/it-security`
- Detail: JSON-LD `JobPosting`.
- Acceptance:
  - [ ] Parses 20+ candidates from a fixture.
  - [ ] Parses `datePosted`, salary, location, remote.
  - [ ] Live smoke test returns at least one security job.
  - [ ] No more than 25 detail requests per run.

### Phase 3b — JapanDev

- Listing: `https://japan-dev.com/security-jobs-in-japan`
- Detail: JSON-LD `JobPosting`.
- Acceptance:
  - [ ] Extracts unique job links, not nav/related links.
  - [ ] Parses `datePosted`, `validThrough`, salary, location.
  - [ ] Classifier demotes clearly unrelated roles.
  - [ ] Live smoke test works.

### Phase 3c — TokyoDev

- Listing: `https://www.tokyodev.com/jobs/security`
- Detail: JSON-LD `JobPosting`; Atom fallback.
- Acceptance:
  - [ ] Parses the Security category.
  - [ ] Parses `datePosted` from detail pages.
  - [ ] Optionally parses "Verified as active" into `source_updated_at`.
  - [ ] Atom fallback is tested with a fixture.

### Phase 3d — Daijob

- Listing: `https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0`
- Detail: HTML labels (`Activated`, `Updated`).
- Acceptance:
  - [ ] Follows the redirect to `search_result`.
  - [ ] Parses the Security System SE category.
  - [ ] Parses `Activated` and `Updated`.
  - [ ] Deduplicates detail IDs across category/keyword searches.
  - [ ] Does not fetch company/member/apply pages.

### Phase 3e — Robert Half

- Listing: `https://www.roberthalf.com/jp/en/jobs`
- Detail: embedded JSON + detail page.
- Acceptance:
  - [ ] Parses the escaped `initialResults` JSON.
  - [ ] Parses `date_posted`, salary, remote, employment type.
  - [ ] Stops pagination at the cutoff.
  - [ ] Detail fetch is optional and capped.

## Phase 4 — UI and refresh experience

**Tasks**

- Implement `templates/base.html` and `index.html`.
- Implement `static/app.css` and `static/app.js`.
- Build the header, summary cards, filters, job list, and refresh panel.
- Wire filters to `/api/jobs`.
- Wire Refresh to `/api/refresh` and poll `/api/refresh/status`.
- Add empty, loading, partial, and error states.
- Add responsive layout and dark mode.
- Add accessibility checks.

**Acceptance**

- [x] Dashboard loads with no jobs and a clear empty state.
- [x] Refresh shows per-source progress.
- [ ] New jobs appear after refresh without a full page reload (implemented;
      verify live during Phase 5).
- [x] Filters update the list, including Role type, Language, Location scope,
      and Visa/overseas.
- [x] Default view hides GRC/audit/consulting/sales/management and
      `international_remote` roles.
- [x] Language, visa, and overseas badges render when known and are omitted when
      unknown.
- [x] A source error is visible and does not hide other jobs.
- [ ] Keyboard navigation works (native controls implemented; manual check
      pending).
- [x] No external JS/CSS dependencies.

## Phase 5 — Hardening and documentation

**Tasks**

- [x] Add structured logging (single-line JSON via `JsonLogFormatter`).
- [x] Add request caps and per-source timeouts (settings already present; reused by scrapers).
- [x] Add retry/backoff tests (HTTP layer).
- [x] Add robots-disallowed test (HTTP layer).
- [x] Add parser edge-case tests (missing salary, Japanese title, remote, expired; expired now inferred from `expires_at`).
- [x] Add `scripts/refresh.py` and `scripts/inspect_source.py`.
- [x] Complete `README.md` and `docs/operations.md`.
- [x] Add a "how to add a source" walkthrough.
- [x] Review for secrets and unsafe logging.
- [x] Run a full live refresh and record the result.

**Acceptance**

- [ ] Full refresh completes in a reasonable time (target < 60 s). Measured
      full refresh (all sources, default 3-day window): ~2m04s, `status=success`;
      runtime is throttle-bound by the deliberate ~1 req/s per-host policy.
- [x] One broken source yields `partial`, with a clear error (covered by tests).
- [x] `pytest` and `ruff check` pass (120 tests, clean).
- [x] No secrets or cookies in the repo (reviewed).
- [ ] README setup steps work from a clean environment (pending manual run).
- [x] Database survives an app restart (verified live).

## Phase 6 — Optional enhancements

Prioritize only after v1 is stable.

- Cross-source deduplication/grouping.
- Additional sources: JobsInJapan, Wantedly, GaijinPot (Playwright).
- CSV/JSON export.
- Saved filter presets.
- Daily digest (would require a scheduler; out of scope for v1).
- Japanese translation/summarization (optional LLM).
- [x] Dockerfile and a local compose setup (`Dockerfile`, `docker-compose.yml`).
- Alembic migrations.

## Suggested commit sequence

1. `chore: scaffold project and tooling`
2. `feat: add database models and repository`
3. `feat: add job query API`
4. `feat: add scraper framework and refresh service`
5. `feat: add Michael Page scraper`
6. `feat: add JapanDev scraper`
7. `feat: add TokyoDev scraper`
8. `feat: add Daijob scraper`
9. `feat: add Robert Half scraper`
10. `feat: add dashboard UI`
11. `test: add parser and API coverage`
12. `docs: add operations and source onboarding guide`

## Definition of done for v1

The checklist in [PLAN.md](../PLAN.md#11-acceptance-criteria-for-v1) is fully
satisfied, and a fresh clone can be set up and refreshed using only the README.

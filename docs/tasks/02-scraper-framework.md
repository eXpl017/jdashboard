# Task 02 — Scraper Framework and Refresh Service

## Goal

Build the shared scraper contract, HTTP utilities, normalization, classification,
and the manual refresh service.

## Read first

- `docs/scrapers.md`
- `docs/architecture.md`
- `docs/data-model.md`

## Deliverables

### Scraper contract

- `app/scrapers/base.py`:
  - `ScrapedJob`
  - `ScrapeResult`
  - `BaseScraper`
  - `ScraperError`, `RobotsDisallowed`, `SourceChanged`, `RateLimited`,
    `ParseError`
- `app/scrapers/registry.py`:
  - source ID → scraper class
  - enabled/disabled handling

### HTTP

- `app/services/http.py`:
  - `httpx.AsyncClient` wrapper
  - clear `User-Agent`
  - timeouts, redirects
  - retries with exponential backoff + jitter
  - per-host rate limit
  - per-source concurrency semaphore
  - robots.txt cache and check
  - raise typed errors

### Normalization

- `app/services/dates.py`:
  - ISO datetime, date-only, Japanese date parsing
  - UTC conversion, JST helpers
- `app/services/normalize.py`:
  - HTML stripping
  - whitespace/width normalization
  - salary parsing
  - remote/employment detection
  - language detection (`en` / `ja` / `bilingual` / `unknown`)
  - location-scope derivation (Japan onsite/hybrid/remote vs. international)
  - overseas-eligibility detection
  - canonical URL + fingerprint
- `app/services/classify.py`:
  - security keyword sets (English + Japanese)
  - score and tags
  - negative terms
  - role-category assignment (engineering, operations, grc, consulting, sales,
    management, other)

### Refresh service

- `app/services/refresh.py`:
  - `asyncio.Lock`
  - create run
  - per-source progress
  - run sources sequentially
  - upsert results
  - partial failure handling
  - finish run
- `POST /api/refresh`
- `GET /api/refresh/status`

### Tests

- `tests/test_dates.py`
- `tests/test_normalize.py`
- `tests/test_classify.py`
- `tests/test_refresh.py` with a fake scraper:
  - success
  - partial failure
  - lock/409
  - progress transitions
- `tests/test_http.py` with `respx`:
  - retry on 429/5xx
  - robots disallow
  - rate-limit behavior (unit-level)

## Acceptance

- [ ] Fake scraper runs end-to-end and writes jobs.
- [ ] A failing source yields `partial`, not a crash.
- [ ] Second refresh returns `409`.
- [ ] Run/source rows are persisted.
- [ ] No scraping at startup.
- [ ] Language, role-category, location-scope, and overseas-eligibility helpers
      have unit tests with English and Japanese examples.
- [ ] `ruff check .` and `pytest` pass.

## Notes

- Do not implement the five real scrapers here.
- Do not add Playwright.
- Keep the HTTP wrapper injectable for tests.
- Keep the refresh progress state in memory; the DB is the durable record.

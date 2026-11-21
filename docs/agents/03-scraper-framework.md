# Phase 2 — Scraper framework and refresh service

**Goal:** define the contract every source implements, make the HTTP layer
polite by default, and run sources one at a time with visible progress and a
durable record.

## The scraper contract (`app/scrapers/base.py`)

```python
class BaseScraper:
    source_id: str
    source_name: str
    listing_url: str
    max_detail_requests: int = 40
    is_security_category: bool = False

    async def scrape(self, since: datetime) -> ScrapeResult: ...
```

- A scraper **fetches and parses only**. It returns `ScrapedJob` objects and
  never touches the database.
- `since` is timezone-aware UTC. A naive datetime crashes the comparison in
  every scraper — this bit the CLI once (see Phase 5).
- One bad job must not fail the source: log a warning with the URL and
  continue. A source-wide failure raises `ScraperError` (or the more specific
  `RobotsDisallowed`, `RateLimited`, `SourceChanged`).

## The polite HTTP client (`app/services/http.py`)

One `HttpClient` for everything:

- **robots.txt** is fetched once per host and cached. A disallowed path raises
  `RobotsDisallowed`; the source is then reported as `skipped`, not `error`.
  Per RFC 9309 an unreachable robots.txt means "assume disallow".
- **Throttle**: at least one request per second per host.
- **Retries** with backoff on timeouts and transient failures.
- **Per-source concurrency cap** (`max_detail_concurrency`) via a semaphore.
- A clear, configurable `User-Agent`.

## The refresh service (`app/services/refresh.py`)

- Sources run **sequentially**, not in parallel: predictable request rate per
  host and a readable progress log.
- **One `asyncio.Lock`** guards the whole refresh. A second request gets
  `409` instead of starting a second run. The lock is released on success,
  partial failure, and exception.
- **Progress lives in memory** (`RefreshProgress` / `SourceProgress`) and is
  what `GET /api/refresh/status` returns.
- **History lives in the database**: a `scrape_runs` row plus one
  `scrape_source_results` row per source, with found/new/updated/skipped/errors
  counts and a short error message.
- **Per-source isolation**: a failing source is recorded and the run
  continues. The overall status is `success` (all sources fine), `partial`
  (some failed), or `failed` (none succeeded).
- The service classifies and normalizes each job (security score, tags, role
  category, salary, remote, language, location scope) before upserting.

## Shared utilities

- `services/dates.py` — JST/UTC parsing; date-only values become JST
  midnight.
- `services/normalize.py` — salary, remote, employment type, language,
  location scope, overseas eligibility, canonical URL, fingerprint.
- `services/classify.py` — security score, tags, and a **title-first**
  `role_category` ("security consultant" is consulting, "CISO" is management).
- `services/jsonld.py` — `JobPosting` extraction, recursing through `@graph`
  and `mainEntity`.

## Traps hit

- The in-memory lock is the only thing preventing two concurrent refreshes;
  it is not persisted, so a crashed process leaves no lock behind (a restart
  clears it) but also leaves a `scrape_runs` row with `status=running`.
- The refresh window is applied by comparing `posted_at` with `since`. A
  listing with no date is kept but hidden until "include older listings" is
  enabled.

## How to verify

```bash
uv run pytest tests/test_http.py tests/test_refresh.py -q
curl -s -X POST http://127.0.0.1:8001/api/refresh -d '{"window_days":3}' -H 'Content-Type: application/json'
curl -s http://127.0.0.1:8001/api/refresh/status
```

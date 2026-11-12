# Architecture

## 1. System context

```text
┌──────────────────────────────────────────────────────────────┐
│ Browser                                                      │
│  - single HTML page                                          │
│  - vanilla JS: fetch jobs, start refresh, poll status        │
└───────────────┬──────────────────────────────────────────────┘
                │ HTTP (localhost)
┌───────────────▼──────────────────────────────────────────────┐
│ FastAPI app                                                  │
│                                                              │
│  Routes                                                      │
│   GET  /                  -> Jinja2 page shell               │
│   GET  /api/jobs          -> filtered job list               │
│   GET  /api/jobs/{id}     -> job detail                      │
│   GET  /api/stats         -> counts + last run               │
│   GET  /api/sources       -> source metadata/health          │
│   POST /api/refresh       -> start a manual refresh          │
│   GET  /api/refresh/status-> progress + per-source results   │
│   GET  /health            -> liveness                        │
│                                                              │
│  Services                                                    │
│   RefreshService  (asyncio.Lock + background task)           │
│   JobQueryService (filters, sorting, pagination)             │
│   Normalizer      (dates, salary, location, remote, type,    │
│                    language, location scope, overseas)       │
│   Classifier      (security relevance, tags, role category)  │
│   HttpClient      (robots, retries, rate limit, UA)          │
│                                                              │
│  Scrapers (one module per source)                            │
│   michael_page, japan_dev, tokyo_dev, daijob, robert_half    │
└───────────────┬──────────────────────────────────────────────┘
                │ SQLAlchemy
┌───────────────▼──────────────────────────────────────────────┐
│ SQLite  data/jobs.db                                         │
│   jobs, job_tags, scrape_runs, scrape_source_results,        │
│   source_state                                               │
└──────────────────────────────────────────────────────────────┘
```

## 2. Planned project layout

```text
jdashboard/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory, lifespan, routes include
│   ├── config.py               # pydantic-settings; .env loading
│   ├── db.py                   # engine, session factory, PRAGMAs
│   ├── models.py               # SQLAlchemy models
│   ├── schemas.py              # Pydantic request/response models
│   ├── repository.py           # job upserts, queries, run records
│   ├── api/
│   │   ├── __init__.py
│   │   ├── jobs.py
│   │   ├── refresh.py
│   │   ├── sources.py
│   │   └── stats.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── refresh.py          # orchestration + lock + progress state
│   │   ├── normalize.py        # text/date/salary/location/language/scope normalization
│   │   ├── classify.py         # security keywords, tags, score, role category
│   │   ├── dates.py            # parsing and timezone helpers
│   │   └── http.py             # httpx wrapper, robots, retry, rate limit
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseScraper, ScrapedJob, ScrapeResult
│   │   ├── registry.py         # source_id -> scraper class
│   │   ├── michael_page.py
│   │   ├── japan_dev.py
│   │   ├── tokyo_dev.py
│   │   ├── daijob.py
│   │   └── robert_half.py
│   ├── templates/
│   │   ├── base.html
│   │   └── index.html
│   └── static/
│       ├── app.css
│       └── app.js
├── data/
│   ├── jobs.db                 # gitignored
│   └── logs/                   # gitignored
├── tests/
│   ├── fixtures/
│   │   ├── michael_page_list.html
│   │   ├── michael_page_detail.html
│   │   ├── japan_dev_list.html
│   │   ├── japan_dev_detail.html
│   │   ├── tokyo_dev_list.html
│   │   ├── tokyo_dev_detail.html
│   │   ├── daijob_list.html
│   │   ├── daijob_detail.html
│   │   ├── robert_half_list.html
│   │   └── robert_half_detail.html
│   ├── conftest.py
│   ├── test_dates.py
│   ├── test_normalize.py
│   ├── test_classify.py
│   ├── test_repository.py
│   ├── test_api.py
│   └── test_scrapers.py
├── scripts/
│   ├── refresh.py              # developer CLI refresh
│   └── inspect_source.py       # dump parsed jobs for one source
├── docs/
├── .opencode/
├── .env.example
├── .gitignore
├── pyproject.toml
├── Makefile
├── README.md
└── PLAN.md
```

## 3. Application lifecycle

- `create_app()` builds the FastAPI app, mounts static files, includes routers,
  and creates the SQLite schema if it does not exist.
- The database file defaults to `data/jobs.db`.
- On startup, **no scraping occurs**. The app only opens the database and
  prepares the refresh lock.
- On shutdown, the app waits briefly for an in-flight refresh, then closes the
  HTTP client.

## 4. Refresh flow

```text
User click
   │
   ▼
POST /api/refresh
   │
   ├─ lock already held? ──yes──> 409 {detail: "refresh already running"}
   │
   ▼
create scrape_runs(status=running)
   │
   ▼
spawn asyncio task (return 202 {run_id})
   │
   ▼
for each source in registry:
   ├─ update in-memory progress: source=running
   ├─ create scrape_source_results(status=running)
   ├─ scraper.scrape(since=now-window)
   │    ├─ robots check
   │    ├─ fetch listing
   │    ├─ extract candidate URLs
   │    ├─ fetch details (limited concurrency)
   │    ├─ parse + normalize + classify
   │    └─ return jobs or raise ScraperError
   ├─ repository.upsert_many(jobs)
   ├─ update source result (found/new/updated/errors)
   └─ update in-memory progress: source=ok|error
   │
   ▼
finish scrape_runs(status=success|partial|failed)
release lock
   │
   ▼
UI poll sees finished -> reload /api/jobs and /api/stats
```

### Why a background task?

A refresh with 5 sources and detail pages can take 20–60 seconds. A synchronous
HTTP request risks browser/server timeouts and gives no progress feedback.
The background task keeps the request fast while the UI polls for status.

### Locking

- One process-wide `asyncio.Lock` in `RefreshService`.
- If the lock is held, `POST /api/refresh` returns `409`.
- The UI disables the button while a refresh is running.
- A refresh run that crashes must release the lock in a `finally` block.

### Progress state

In-memory state is sufficient for a single-user local app:

```python
@dataclass
class RefreshProgress:
    run_id: int
    status: str                  # running | success | partial | failed
    started_at: datetime
    finished_at: datetime | None
    sources: dict[str, SourceProgress]
```

The database is the durable record; in-memory state is only for live UI polling.
On restart, the UI shows the last completed run from the database.

## 5. HTTP client policy

`services/http.py` wraps `httpx.AsyncClient` with:

- A clear `User-Agent`, e.g.
  `JDashboard/0.1 (personal job dashboard; +http://127.0.0.1:8000)`.
- `timeout=20s`, `follow_redirects=True`.
- Retries: 2 retries on timeouts, 429, and 5xx, with exponential backoff
  (1s, 2s) plus jitter.
- Per-host rate limit: at least 1 second between requests by default.
- Per-source concurrency limit: 2–3 concurrent detail requests.
- `robots.txt` check per host, cached for the process lifetime.
- If `robots.txt` disallows the path: raise `RobotsDisallowed` and record a
  source error. Do not attempt to bypass.
- Optional `ETag`/`Last-Modified` cache later; not required for v1.

## 6. Error handling

Error classes:

- `ScraperError` — base class.
- `RobotsDisallowed` — source skipped due to robots.txt.
- `SourceChanged` — expected selector/JSON key missing.
- `RateLimited` — 429 after retries.
- `ParseError` — a single job could not be parsed.

Rules:

- A single bad job must not fail the whole source: log it, count it, continue.
- A source failure must not fail the whole run: mark that source `error`, keep
  the other sources' results, finish the run as `partial`.
- If every source fails, finish as `failed`.
- Store a short, user-safe error message in `scrape_source_results.error_message`
  and the full traceback in the application log.
- The UI shows per-source status and a "last successful refresh" timestamp.

## 7. Configuration

Environment variables (`.env`):

```dotenv
APP_NAME=Japan Cybersecurity Jobs
DATABASE_URL=sqlite:///./data/jobs.db
HOST=127.0.0.1
PORT=8000
DEFAULT_WINDOW_DAYS=3
DEFAULT_ROLE_SCOPE=technical
DEFAULT_LOCATION_SCOPE=japan
REQUEST_TIMEOUT_SECONDS=20
MIN_REQUEST_INTERVAL_SECONDS=1.0
MAX_DETAIL_CONCURRENCY=2
USER_AGENT=JDashboard/0.1 (personal job dashboard; +http://127.0.0.1:8000)
LOG_LEVEL=INFO
```

Optional per-source switches:

```dotenv
ENABLE_MICHAEL_PAGE=true
ENABLE_JAPAN_DEV=true
ENABLE_TOKYO_DEV=true
ENABLE_DAIJOB=true
ENABLE_ROBERT_HALF=true
```

Do not commit `.env`. Commit `.env.example` only.

## 8. Security and privacy

- No dashboard authentication in v1; bind to `127.0.0.1` by default.
- If the app is exposed to a LAN or the internet, put it behind a reverse proxy
  with authentication and TLS. Document this in `operations.md`.
- Do not store job-site credentials, cookies, or session tokens for the five
  launch sources.
- Do not log full HTML pages or personal data. Log source, URL, status, and a
  short error message.
- Store job descriptions as text/HTML from public pages; do not store recruiter
  contact details unless they are part of the public listing and needed.
- Keep `data/jobs.db` and `data/logs/` out of git.

## 9. Testing strategy

- **Unit tests** for date parsing, salary parsing, text normalization, remote
  detection, employment-type detection, language detection, role-category
  assignment, location-scope derivation, overseas-eligibility detection, and
  security classification.
- **Parser tests** against saved HTML/JSON fixtures. No live network in tests.
- **Repository tests** against an in-memory SQLite database.
- **API tests** with FastAPI `TestClient` and a temporary database.
- **Refresh tests** with a fake scraper injected into the registry.
- **Live smoke tests** are a manual developer command, not part of CI:
  `python -m scripts.refresh --source michael_page --window-days 3`.

## 10. Observability

- Console logs with timestamp, level, source, and message.
- Rotating file log at `data/logs/app.log` (optional in v1; console is enough).
- `GET /health` returns app and database status.
- `GET /api/stats` returns per-source counts and last run status.
- The UI's source panel is the primary operational view.

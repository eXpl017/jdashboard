# AGENTS.md — `app/` package

FastAPI application package. Layering is strict: **api → services → scrapers →
repository → db**. A module may only call downwards.

| Layer | May import | Must not |
| --- | --- | --- |
| `api/` | `repository`, `schemas`, `services.refresh`, `scrapers.registry` (metadata only) | open HTTP connections, scrape, write SQL by hand |
| `services/` | `models`, `config`, other services | import `api` |
| `scrapers/` | `services.http`, `services.dates`, `services.normalize`, `services.jsonld` | import `repository`/`db`, write to the database |
| `repository.py` | `models`, `db` | import `api`, `services`, `scrapers` |
| `db.py` | `config` | import anything from the app except config |

## Rules

- **Scrapers never touch the database.** They return `ScrapedJob` /
  `ScrapeResult` and the refresh service persists.
- **The repository owns all SQL.** API and service code call
  `repository.query_jobs`, `repository.get_stats`, `repository.upsert_job`.
- **Only the refresh service writes.** `api/refresh.py` starts it; nothing else
  mutates job rows.
- **One refresh at a time.** `RefreshService` holds a single `asyncio.Lock`; a
  second start raises `RefreshAlreadyRunning` → HTTP 409.
- **Per-source isolation.** One source failing marks that source `error` (or
  `skipped` for robots) and the run continues; the run status becomes
  `partial`.
- **Progress is in memory; history is in the DB.** `scrape_runs` and
  `scrape_source_results` are the durable record.

## Files worth knowing

- `config.py` — every setting is an env var with a default; per-source flags
  are `enable_<source_id>`.
- `models.py` — SQLAlchemy 2.0 typed mappings; `Job.security_tags` is JSON
  stored as text on SQLite.
- `repository.py` — `_job_conditions()` is the single source of truth for
  filters; `query_jobs` and `get_stats` both use it so counts and lists agree.
  `get_stats` applies filters to the totals but keeps `by_source`,
  `by_role_category`, and `by_tag` global so filter dropdowns never collapse.
- `schemas.py` — response models; `UtcDateTime` serializes to `...Z`.
- `api/sources.py` — per-source metadata plus last status from the latest
  source result.
- `logging_config.py` — `configure_logging()` installs the JSON formatter; the
  app calls it in the lifespan and the CLI scripts call it in `main()`.

## API surface

| Route | Purpose |
| --- | --- |
| `GET /` | the dashboard UI (Jinja2) |
| `GET /health` | liveness |
| `GET /api/jobs` | filtered list; defaults `role=technical`, `location_scope=japan`, `days=3` |
| `GET /api/jobs/{id}` | one job, 404 when unknown |
| `GET /api/stats` | summary counts; accepts the same filters as `/api/jobs` |
| `GET /api/sources` | source metadata and last refresh status |
| `POST /api/refresh` | start a manual refresh → 202, or 409 when one is running |
| `GET /api/refresh/status` | in-memory progress of the current/last run |

`/docs` and `/openapi.json` are served by FastAPI.

## Conventions

- New endpoints: Pydantic schema in `schemas.py`, route in `api/<name>.py`,
  registered in `api/__init__.py`, tests in `tests/test_api.py`.
- Datetime handling: store UTC, return `...Z`, display JST in the UI.
- Never log request bodies, cookies, or full HTML.

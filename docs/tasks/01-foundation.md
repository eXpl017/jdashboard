# Task 01 — Foundation

## Goal

Create the project skeleton, configuration, database layer, and job query API.

## Read first

- `PLAN.md`
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/ui.md` (API section)

## Deliverables

### Project files

- `pyproject.toml` with:
  - runtime: fastapi, uvicorn[standard], jinja2, httpx, beautifulsoup4, lxml,
    sqlalchemy, pydantic-settings, python-dateutil
  - dev: pytest, pytest-asyncio, respx, ruff
- `.env.example`
- `.gitignore` (ignore `.env`, `data/`, `__pycache__/`, `.pytest_cache/`,
  `.ruff_cache/`, `.venv/`)
- `Makefile` with `install`, `run`, `test`, `lint`, `format`
- `app/` package skeleton

### Database

- `app/db.py`:
  - SQLite engine
  - session factory
  - `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`
- `app/models.py`:
  - `Job`, `JobTag`, `ScrapeRun`, `ScrapeSourceResult`, `SourceState`
- `app/repository.py`:
  - `upsert_job`, `upsert_many`
  - `query_jobs`, `get_job`, `stats`
  - `create_run`, `finish_run`
  - `create_source_result`, `finish_source_result`

### API

- `GET /health`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/stats`

### Tests

- `tests/conftest.py` with an in-memory or temporary SQLite database.
- `tests/test_repository.py`
- `tests/test_api.py`

## Acceptance

- [ ] App starts and serves `/health`.
- [ ] Fixture jobs can be inserted and queried.
- [ ] Filters work: `q`, `source`, `role`, `language`, `location`,
      `location_scope`, `remote`, `visa`, `tag`, `days`, `sort`.
- [ ] Default query returns `engineering` + `operations` roles and excludes
      `international_remote`.
- [ ] Duplicate fingerprints do not insert twice.
- [ ] `first_seen_at` is preserved on update.
- [ ] `ruff check .` and `pytest` pass.

## Notes

- Do not build scrapers in this task.
- Do not add a scheduler.
- Keep the API response shape consistent with `docs/ui.md`.
- Use UTC ISO 8601 strings for timestamps.

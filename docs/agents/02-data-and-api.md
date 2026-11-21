# Phase 1 — Data model and query API

**Goal:** a store that can hold every listing a source returns, and a query
layer whose filters mean the same thing to the UI and to the tests.

## What was built

### Schema (`app/models.py`, `docs/data-model.md`)

- `Job` — one row per source listing. Identity is
  `sha256(source_id + canonical_url)`; canonical URLs drop tracking
  parameters and keep the source-native job id.
- `JobTag` — a normalized tag table. **Created by the schema but never
  written**: tags live in `jobs.security_tags` as JSON text, and the tag
  filter matches it with a `LIKE`. The table is kept so a later migration can
  populate it without a schema change.
- `ScrapeRun` and `ScrapeSourceResult` — the durable history of refreshes.
- `SourceState` — reserved for per-source health caching; the current
  implementation derives health from the latest source result instead.

### Repository (`app/repository.py`)

- `upsert_job` / `upsert_many` — insert or refresh by fingerprint, preserving
  `first_seen_at` and updating `last_seen_at`.
- `query_jobs` — the single filter implementation for the list.
- `get_stats` — summary counts.
- `get_source_health` — latest status and last success per source.
- Run/result lifecycle helpers: `create_run`, `finish_run`,
  `create_source_result`, `finish_source_result`.

### API (`app/api/`)

`GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/stats`, `GET /health`.

Defaults that everything downstream inherits: `role=technical`
(`engineering` + `operations`), `location_scope=japan` (excludes
`international_remote`), `days=3`, `sort=posted_desc`.

## The refactor that matters

Filter logic was duplicated between the list query and the statistics. It was
extracted into `_job_conditions()` so `query_jobs` and `get_stats` always
agree. `get_stats` applies the filters to `total_jobs`, `new_in_window`, and
`relocation_friendly`, but keeps `by_source`, `by_role_category`, and `by_tag`
**global** — otherwise the filter dropdowns would collapse to the current
selection and the user could no longer widen the view.

## Traps hit

- SQLite returns naive datetimes. The normaliser converts source times (which
  are JST) to UTC before storing, and the API serializes them with a `Z`
  suffix through the `UtcDateTime` annotated type.
- `security_tags` is JSON stored as text on SQLite, so the tag filter needs
  `CAST(security_tags AS TEXT) LIKE '%"tag"%'`.
- A job whose source has no date is stored with `posted_at = NULL` and
  `date_confidence = "low"`; it is only visible with "include older listings".

## How to verify

```bash
uv run pytest tests/test_repository.py tests/test_api.py -q
sqlite3 data/jobs.db "SELECT fingerprint, COUNT(*) c FROM jobs GROUP BY fingerprint HAVING c>1;"
```

# AGENTS.md — Japan Cybersecurity Jobs Dashboard

Single-user, local dashboard that aggregates cybersecurity job listings in
Japan from five public job boards into SQLite and serves a minimal web UI.
**Nothing is scraped until a human clicks Refresh** (or runs the CLI).

This file is the entry point for any agent working in this repository. It is
loaded automatically. Read `docs/README.md` for the documentation index, and
the per-directory `AGENTS.md` files for directory-specific rules.

## Status

The build is complete: scaffold, database and query API, scraper framework,
refresh service, five source scrapers, the web UI, hardening, and the agent
workflow for adding sources.

- 128 tests pass, `ruff check .` is clean.
- Sources: Michael Page Japan, JapanDev, TokyoDev, Daijob, Robert Half Japan.
- What was built and why: `docs/agents/`. What is deliberately not built:
  `docs/agents/08-open-options.md`.

## Layout

```text
app/
  main.py            FastAPI app, lifespan, static mount, "/" route
  config.py          Settings (env/.env), per-source enable flags
  db.py              SQLite engine, WAL pragmas, SessionLocal
  models.py          SQLAlchemy models (Job, JobTag, ScrapeRun, ...)
  repository.py      upserts, queries, stats, source health  ← no HTTP, no scraping
  schemas.py         Pydantic response models
  logging_config.py  JSON log formatter (app + CLI)
  api/               HTTP layer: /, /api/jobs, /api/stats, /api/sources, /api/refresh
  services/          shared logic
    http.py          polite async client: robots, throttle, retries, concurrency
    refresh.py       refresh service: lock, progress, persistence
    normalize.py     salary/remote/employment/language/location-scope parsing
    classify.py      security score, tags, role_category
    dates.py         JST/UTC parsing helpers
    jsonld.py        JSON-LD JobPosting extraction
  scrapers/          one module per source; registry.py maps source id → class
  templates/         Jinja2 pages (base.html, index.html)
  static/            app.css, app.js (no CDN, no external assets)
tests/               pytest suite + fixtures/ (committed HTML samples)
scripts/             CLI: refresh.py, inspect_source.py, check_port.py
docs/                topic documentation (see docs/README.md)
.opencode/           agents, skills, and commands for AI-assisted work
data/                local SQLite database (gitignored)
```

## Commands

Run everything from the repository root.

```bash
uv sync --extra dev                 # install
make run                            # dev server on 127.0.0.1:8001 (host DB)
make run DEV_PORT=8002              # another dev port
uv run pytest -q                    # default offline suite (no network; UI tests excluded)
uv run pytest -m ui -q              # automated browser UI tests (Playwright)
uv run playwright install chromium  # one-time browser install for UI tests
uv run ruff check .                 # lint
uv run python -m scripts.inspect_source <source> --limit 3   # live scrape, no DB writes
uv run python -m scripts.refresh --source <source> --window-days 3   # live refresh, writes DB
uv run python scripts/check_port.py 8001   # pre-flight port check
```

## Architecture in one paragraph

`scrapers/<source>.py` fetches and parses one site and returns `ScrapedJob`
objects — it never touches the database. `services/refresh.py` runs the enabled
scrapers sequentially under one lock, classifies/normalizes each job, and
upserts it through `repository.py` into SQLite, while recording a durable
`scrape_runs` / `scrape_source_results` history. `api/` exposes that data as
JSON; `templates/` + `static/` render it.

## Non-negotiable rules

- **Manual refresh only.** No scheduler, no startup scrape, no background
  polling. Scraping happens only from `POST /api/refresh` or the CLI.
- **Respect robots.txt** at runtime and keep to ~1 request/second per host.
  Never bypass a login, CAPTCHA, Cloudflare challenge, paywall, or rate limit.
- **No headless browser** for anti-bot evasion.
- **Store, don't drop.** Non-technical roles (`grc`, `consulting`, `sales`,
  `management`) and `international_remote` rows are stored; the UI filters them.
- **Never guess** salary, visa sponsorship, or overseas eligibility. Leave them
  unknown (`NULL`) unless the source states it.
- **One row per source listing.** Cross-source dedup is deferred.
- **Tests must not touch the network.** Use the committed fixtures.
- **No secrets, cookies, or tokens** in the repo, the database, or the logs.
- The UI has **no external JS/CSS/CDN** and no authentication; it binds to
  localhost only.

## Conventions

- Python 3.11+, `ruff` (line length 100), type hints, `from __future__` not
  required (3.11+), stdlib `logging` via `app.logging_config.configure_logging()`.
- Times: store UTC (naive in SQLite), display Asia/Tokyo, default window
  **3 days** based on the source's `posted_at`.
- Default view: `role=technical` (`engineering` + `operations`) and
  `location_scope=japan`.
- New listings get `first_seen_at`; that drives the "New" badge.
- Job identity is `sha256(source_id + canonical_url)`; canonical URLs drop
  tracking parameters.
- Docs are part of the change: a new source updates `docs/sources.md`,
  `docs/scrapers.md`, and `README.md` in the same commit.

## Common tasks

| Task | How |
| --- | --- |
| Add a job source | `/add-source <source>` (command) → `source-onboarding` skill → `source-researcher` → `scraper-builder` → `source-integrator` → `qa-reviewer`. Manual steps: `docs/scrapers.md` §8. |
| Evaluate a candidate source | `/research-source <source>` → brief in `docs/research/<source>.md` |
| Repair a scraper | `scraper-authoring` skill; fixtures in `tests/fixtures/` |
| Review a change | `dashboard-qa` skill; `qa-reviewer` subagent |
| Verify the UI in a browser | `/verify-ui` → `ui-verification` skill (host dev server, `127.0.0.1:8001`) |
| Verify a change end to end | `docs/verification.md` |
| Change the UI or API | `docs/ui.md`; the UI is `app/templates/` + `app/static/` |

## Gotchas

- Scripts are **modules**: `python -m scripts.refresh`, not
  `python scripts/refresh.py`.
- `scripts/inspect_source.py` must receive a timezone-aware UTC cutoff; naive
  datetimes break the scrapers' comparisons.
- `job_tags` exists in the schema but is not written; tags live in
  `jobs.security_tags` as JSON text.
- `data/` and `.env` are gitignored — never commit them.

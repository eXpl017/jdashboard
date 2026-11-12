# Operations Guide

This is the runbook for the planned application. Commands become runnable after
the implementation phases are complete.

## 1. Prerequisites

- Python 3.11 or newer.
- `uv` (recommended) or `pip` + `venv`.
- Git.
- A network connection for scraping.

Check:

```bash
python3 --version
uv --version
```

## 2. First-time setup

```bash
git clone <your-repo-url> jdashboard
cd jdashboard

# Install runtime + dev dependencies
uv sync --extra dev

# Create local config
cp .env.example .env
```

Edit `.env` only if you need to change the database path, port, or rate limits.

## 3. Run the dashboard

```bash
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

The app binds to `127.0.0.1` by default. Do not expose it to the internet
without authentication.

## 4. Refresh jobs

1. Open the dashboard.
2. Click **Refresh**.
3. Watch the per-source status panel.
4. When the run finishes, the job list and summary cards reload.

A refresh is the **only** time the app makes outbound requests to job sites.
There is no cron, scheduler, startup scrape, or background poll.

## 5. Developer CLI

Useful for parser work and smoke tests:

```bash
# Refresh one source and print parsed jobs without writing to the DB
uv run python -m scripts.inspect_source michael_page --limit 3

# Refresh all sources into the DB (same code path as the UI)
uv run python -m scripts.refresh --window-days 3

# Refresh one source
uv run python -m scripts.refresh --source japan_dev --window-days 3
```

The CLI uses the same rate limits, robots checks, and normalization as the UI.

## 6. Docker

The image is defined in `Dockerfile`; `docker-compose.yml` builds and runs it.

```bash
# Build the image
docker compose build

# Start in the background
docker compose up -d

# Status and logs
docker compose ps
docker compose logs -f dashboard

# Stop, keep the database volume
docker compose down

# Stop and delete the database volume too
docker compose down -v
```

Image details:

- Base: `python:3.13-slim` with `uv` used only to install locked runtime
  dependencies (`uv sync --frozen --no-dev --no-install-project`).
- Runs as the unprivileged user `appuser` (uid 10001).
- Listens on `0.0.0.0:8000` inside the container; Compose publishes it on
  `127.0.0.1:8000` by default.
- Health check hits `GET /health` every 30 s.
- The SQLite database lives in the `dashboard-data` volume at `/data`.

Useful in-container commands:

```bash
# Refresh from the CLI
docker compose exec dashboard python -m scripts.refresh --window-days 3

# Inspect one source
docker compose exec dashboard python -m scripts.inspect_source michael_page --limit 3

# Read the database
docker compose exec dashboard python -c \
  "import sqlite3; print(sqlite3.connect('/data/jobs.db').execute('select count(*) from jobs').fetchone())"

# Copy the database out
docker compose cp dashboard:/data/jobs.db ./jobs.db
```

Configuration comes from the environment; Compose reads the project `.env` file
for `${VAR:-default}` substitution. Useful keys:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DASHBOARD_BIND` | `127.0.0.1` | Host interface to publish on |
| `DASHBOARD_PORT` | `8000` | Host port |
| `LOG_LEVEL` | `INFO` | Log level inside the container |
| `DATABASE_URL` | `sqlite:////data/jobs.db` | Keep the `/data` path in sync with the volume |
| `ENABLE_*` | `true` | Per-source switches |

Troubleshooting:

- `docker compose up` fails with a port conflict: change `DASHBOARD_PORT`.
- The container is unhealthy: `docker compose logs dashboard` and check
  `GET /health`; the app never scrapes on startup, so a failure here is a
  config or database problem, not a network one.
- After changing `pyproject.toml` or `uv.lock`, rebuild:
  `docker compose build --no-cache && docker compose up -d`.

## 7. Tests and lint

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests must not hit the live network. Use fixtures and `respx`.

## 8. Database

Default path: `data/jobs.db`.

Inspect with `sqlite3`:

```bash
sqlite3 data/jobs.db ".tables"
sqlite3 data/jobs.db "SELECT source, COUNT(*) FROM jobs GROUP BY source;"
sqlite3 data/jobs.db "SELECT id, status, started_at, total_new FROM scrape_runs ORDER BY id DESC LIMIT 5;"
```

Backup while the app is stopped:

```bash
cp data/jobs.db data/jobs.backup-$(date +%Y%m%d).db
```

Live backup:

```bash
sqlite3 data/jobs.db "VACUUM INTO 'data/jobs.backup.db';"
```

Reset the database (destructive):

```bash
rm data/jobs.db
# restart the app; the schema is recreated
```

## 9. Logs

- Console output from Uvicorn and the app, emitted as single-line JSON objects
  (`ts`, `level`, `logger`, `message`, plus `exc` when a traceback is attached).
- Optional rotating file: `data/logs/app.log`.
- Log level via `LOG_LEVEL` in `.env`.

What is logged:

- Refresh start/finish.
- Per-source start/finish, counts, and short errors.
- HTTP status codes and retry attempts.
- Parse errors with the source and URL, not the full page.

What is not logged:

- Cookies, tokens, or credentials.
- Full HTML pages.
- Personal data from listings beyond what is needed for debugging.

## 10. Troubleshooting

### The dashboard shows no jobs

1. Check the last run status in the source panel.
2. If all sources are `success` with 0 new, there may be no jobs in the 3-day
   window. Switch to 7 days or enable "Include active older listings".
3. If a source is `error`, read its message and the logs.
4. Confirm the database is writable: `ls -l data/`.

### A source returns 403 or 429

- 403: likely an anti-bot block. Stop. Do not add bypass logic. Disable the
  source in `.env` and document the change.
- 429: increase `MIN_REQUEST_INTERVAL_SECONDS`, reduce
  `MAX_DETAIL_CONCURRENCY`, and retry later.

### A source returns 0 candidates but no error

- The listing page structure likely changed.
- Compare the live page with the saved fixture.
- Update the parser and fixture, then add a regression test.

### Refresh button stays disabled

- A previous refresh may still be running. Check
  `GET /api/refresh/status`.
- If the process crashed, restart the app; the in-memory lock is reset.
- Check the latest `scrape_runs` row for `status=running` and fix it manually if
  needed.

### Database is locked

- Ensure WAL mode and `busy_timeout` are enabled.
- Do not run two app processes against the same SQLite file.
- Close external `sqlite3` sessions that hold write transactions.

### Japanese text looks wrong

- Ensure responses are decoded as UTF-8.
- Ensure the database and terminal use UTF-8.
- Check `normalize_width` does not strip meaningful characters.

## 11. robots.txt and terms policy

Before enabling a source:

1. Fetch `https://<host>/robots.txt`.
2. Confirm the listing and detail paths are allowed for `User-agent: *`.
3. Read the site's terms of use for personal scraping restrictions.
4. Do not scrape login, member, apply, or company-profile pages.
5. Do not bypass CAPTCHAs, Cloudflare challenges, or paywalls.
6. Use a clear `User-Agent` and a low request rate.
7. Stop using a source if the site asks you to.

The app should check robots at runtime and skip a disallowed path with a clear
error. A manual review is still required when adding a source.

## 12. Adding a new source

1. Research the source and write a brief in `docs/sources.md`.
2. Add a source ID and enable flag to `.env.example` and `config.py`.
3. Save listing/detail fixtures under `tests/fixtures/`.
4. Implement `app/scrapers/<source>.py`.
5. Register it in `app/scrapers/registry.py`.
6. Add parser tests.
7. Run `ruff check` and `pytest`.
8. Run `scripts/inspect_source.py <source> --limit 3`.
9. Update the README source list and docs.
10. Confirm robots/terms compliance.

Use the `scraper-authoring` skill and the `scraper-builder` subagent for this
workflow.

## 13. Security notes

- The dashboard has no login. Keep it on `127.0.0.1`.
- If you expose it to a LAN, use a reverse proxy with authentication and TLS.
- The container image runs as an unprivileged user (`appuser`) and only writes
  to the `/data` volume.
- Do not commit `.env` or `data/`.
- Do not add job-site credentials or cookies unless you explicitly decide to
  support an authenticated source. If you do, store them in `.env` and never in
  the database or logs.
- Keep dependencies updated and run `ruff`/`pytest` before committing.

## 14. Deployment options

### Local (v1)

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### LAN (not recommended without auth)

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Add a reverse proxy (Caddy/Nginx) with basic auth or an SSO layer first.

### Docker (recommended for a long-running instance)

```bash
docker compose build
docker compose up -d
```

See [section 6](#6-docker) for the full runbook, backups, and configuration
keys. The container serves the app only; there is no scheduler and no startup
scrape.

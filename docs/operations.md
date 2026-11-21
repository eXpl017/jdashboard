# Operations Guide

This is the runbook for the application.

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
make run
```

Open <http://127.0.0.1:8001>.

`make run` starts the development server on **port 8001** and checks the port
first, so it never collides with another process. Override the dev port with
`make run DEV_PORT=8002`.

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

## 6. Tests and lint

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest -q` runs the default offline suite (network-free) and excludes
browser UI tests. Use fixtures and `respx`; tests must not hit the live network.

### Automated browser UI tests (Playwright)

The `tests/browser/` suite exercises the dashboard UI in a real browser against a
throwaway local server with a seeded temporary SQLite database. It is separate
from the default offline suite and does not scrape live job sites.

```bash
uv sync --extra dev
uv run playwright install chromium
uv run pytest -m ui -q
```

Notes:

- Browser tests are marked `ui` and are excluded from `uv run pytest -q` by
  default.
- The suite starts its own `uvicorn` instance on a free local port; it does not
  require `make run` or an existing database.
- `/api/refresh` is never used to scrape live sources in these tests.

### Browser verification (agent-driven)

The browser checklist in `docs/verification.md` §2 can also be run by an agent
in a real browser against the host dev server:

```bash
make run          # 127.0.0.1:8001
/verify-ui        # in the OpenCode TUI; runs the ui-verification skill
```

This is separate from `uv run pytest`/`pytest -m ui` and is not part of CI. It
talks only to `127.0.0.1:8001`; it never scrapes job sites unless you explicitly
run a live refresh.

## 7. Database

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

## 8. Logs

- Console output from Uvicorn and the app, emitted as single-line JSON objects
  (`ts`, `level`, `logger`, `message`, plus `exc` when a traceback is attached).
- No file log is configured; use the console.
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

## 9. Troubleshooting

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

## 10. robots.txt and terms policy

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

## 11. Adding a new source

The fastest route is the `/add-source <source>` command in the TUI, which runs
the `source-onboarding` skill end to end. `/research-source <source>` stops
after the research brief.

The workflow is split across four subagents so each phase stays focused:

| Phase | Subagent | Writes |
| --- | --- | --- |
| Research | `source-researcher` | `docs/research/<source>.md` (verdict + robots evidence) |
| Implement | `scraper-builder` | `app/scrapers/<source>.py`, fixtures, parser tests |
| Integrate | `source-integrator` | enable flag, registry entry, docs, green suite, live smoke |
| Review | `qa-reviewer` | findings on the finished diff |

Manual steps, if you do not want to use the agents:

1. Research the source: write the evidence in `docs/research/<source>.md` and
   the adopted summary in `docs/sources.md`.
2. Add a source ID and enable flag to `.env.example` and `config.py`.
3. Save listing/detail fixtures under `tests/fixtures/`.
4. Implement `app/scrapers/<source>.py`.
5. Register it in `app/scrapers/registry.py`.
6. Add parser tests.
7. Run `ruff check` and `pytest`.
8. Run `uv run python -m scripts.inspect_source <source> --limit 3`.
9. Update the README source list and docs.
10. Confirm robots/terms compliance.

Use the `scraper-authoring` skill and the `scraper-builder` subagent for this
workflow.

## 12. Security notes

- The dashboard has no login. Keep it on `127.0.0.1`.
- If you expose it to a LAN, use a reverse proxy with authentication and TLS.
- Do not commit `.env` or `data/`.
- Do not add job-site credentials or cookies unless you explicitly decide to
  support an authenticated source. If you do, store them in `.env` and never in
  the database or logs.
- Keep dependencies updated and run `ruff`/`pytest` before committing.

## 13. Deployment options

### Local (v1)

```bash
make run                  # development server on 127.0.0.1:8001
```

### LAN (not recommended without auth)

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Add a reverse proxy (Caddy/Nginx) with basic auth or an SSO layer first.

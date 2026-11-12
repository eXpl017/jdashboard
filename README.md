# Japan Cybersecurity Jobs Dashboard

A small, single-user dashboard that collects cybersecurity job listings in Japan
from public job boards and shows the newest ones in a simple web UI.

**Status: in progress.** Phases 0–4 are implemented: the app scaffold, the
database and query API, the scraper framework plus manual refresh service, all
five launch-source scrapers, and the minimal web UI. Phase 5 covers hardening,
scripts, and documentation.
Start with [PLAN.md](PLAN.md), then read the topic docs in [docs/](docs/).

## What it will do

- Scrape 5 public sources when **you** click **Refresh**.
- Store normalized job listings in a local SQLite database.
- Show jobs posted in the last 3 days by default, with filters and source health.
- Focus on **engineering/technical security roles** (GRC, audit, consulting,
  sales, and management are hidden by default).
- Include **English and Japanese** listings, with a language filter.
- Include **Japan-based and remote-within-Japan** roles; exclude international
  remote roles. Show visa-sponsorship and overseas-application information.
- Never scrape on a schedule, at startup, or in the background without a click.
- Require no login to the dashboard and no login to any of the launch sources.

## Planned stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ |
| Web app | FastAPI + Jinja2 + vanilla HTML/CSS/JS |
| Database | SQLite + SQLAlchemy 2.0 |
| HTTP client | httpx (async) |
| HTML parsing | BeautifulSoup + lxml, plus JSON-LD parsing |
| Tests / lint | pytest, respx, ruff |

## Quick start

The API is runnable now; the dashboard UI is served at
<http://127.0.0.1:8001/> (development server) or
<http://127.0.0.1:8000/> (container).

```bash
# 1. Install
uv sync --extra dev

# 2. Configure
cp .env.example .env

# 3. Run (development server on port 8001; the container uses 8000)
make run

# 4. Open http://127.0.0.1:8001/ for the dashboard
#    or http://127.0.0.1:8001/docs for the API
```

## Manual refresh and source inspection

```bash
# Refresh all sources into the local database (same path as the UI button)
uv run python -m scripts.refresh --window-days 3

# Refresh a single source
uv run python -m scripts.refresh --source japan_dev --window-days 3

# Scrape one source and print parsed jobs (no database writes)
uv run python -m scripts.inspect_source michael_page --limit 3
```

Both scripts use the same rate limits, robots checks, and normalization as the
dashboard.

## Run with Docker

The image is built from [`Dockerfile`](Dockerfile) and run with
[`docker-compose.yml`](docker-compose.yml).

```bash
# 1. Build the image
docker compose build

# 2. Start the dashboard (published on http://127.0.0.1:8000)
docker compose up -d

# 3. Follow the logs
docker compose logs -f

# 4. Stop it (the database volume is kept)
docker compose down
```

The image installs only runtime dependencies from `uv.lock`, runs as a non-root
user, and keeps the SQLite database in the `dashboard-data` volume mounted at
`/data`.

```bash
# Run a refresh inside the container
docker compose exec dashboard python -m scripts.refresh --window-days 3

# Inspect a single source inside the container
docker compose exec dashboard python -m scripts.inspect_source michael_page --limit 3

# Rebuild after code changes
docker compose build && docker compose up -d

# Check the container health
docker compose ps

# Back up the database
docker compose exec dashboard python -c \
  "import sqlite3; sqlite3.connect('/data/jobs.db').execute(\"VACUUM INTO '/data/jobs.backup.db'\")"
docker compose cp dashboard:/data/jobs.backup.db ./jobs.backup.db

# Delete the container and the database volume
docker compose down -v
```

Notes:

- The dashboard is published on `127.0.0.1` only and has no authentication.
  Set `DASHBOARD_BIND=0.0.0.0` in `.env` to expose it on your network — not
  recommended unless you put your own authentication in front of it.
- `DASHBOARD_PORT` changes the host port (default `8000`).
- The image has no dev dependencies; run `uv run pytest` on the host.

## Launch sources

1. **Michael Page Japan** — IT Security category
2. **JapanDev** — Security jobs landing page
3. **TokyoDev** — Security jobs category
4. **Daijob** — Security System SE category + Japanese security keywords
5. **Robert Half Japan** — IT / security listings

All five were checked during planning: they return public HTML/JSON without a
login and their listing pages are not disallowed by `robots.txt`.
See [docs/sources.md](docs/sources.md) for the evidence and caveats.

## Important operating rules

- Respect each site's `robots.txt`, terms, and rate limits.
- Identify the scraper with a clear `User-Agent`.
- Keep request rates low (about 1 request per second per host).
- Do not bypass logins, paywalls, CAPTCHAs, or Cloudflare challenges.
- Scrape only on an explicit user action.

## Documentation map

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Entry point for AI agents: layout, commands, conventions, rules |
| [PLAN.md](PLAN.md) | Master plan, scope, phases (executed) |
| [docs/README.md](docs/README.md) | Index of all documentation |
| [docs/sources.md](docs/sources.md) | Source research, URLs, fields, robots, login notes |
| [docs/architecture.md](docs/architecture.md) | Components, refresh flow, concurrency, errors |
| [docs/data-model.md](docs/data-model.md) | SQLite schema, normalization, dedup, retention |
| [docs/scrapers.md](docs/scrapers.md) | Scraper contract, per-source strategy, testing |
| [docs/ui.md](docs/ui.md) | Minimal UI and HTTP API specification |
| [docs/roadmap.md](docs/roadmap.md) | Ordered implementation phases and status |
| [docs/operations.md](docs/operations.md) | Setup, run, troubleshoot, add a source |
| [docs/verification.md](docs/verification.md) | Verification playbook: run the app and check it |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/questions.md](docs/questions.md) | Planning questions and their resolutions (historical) |
| [docs/tasks/](docs/tasks/) | Task briefs for AI-assisted implementation |

## OpenCode helpers

The repository ships the workflow used to build it, so a new source can be
added with one instruction.

**Commands** (`.opencode/commands/`)

- `/add-source <source>` — add a source end to end: research, brief, scraper,
  fixtures, tests, registration, live smoke, review.
- `/research-source <source>` — evaluate a candidate source and write a brief
  without writing code.

**Skills** (`.opencode/skills/`)

- `source-onboarding` — the full onboarding workflow, phases, gates, and
  handoffs.
- `scraper-authoring` — the parser-level checklist and per-field mapping.
- `dashboard-qa` — the review checklist for any change.

**Subagents** (`.opencode/agents/`)

- `source-researcher` — robots/terms research and the source brief.
- `scraper-builder` — scraper module, fixtures, parser tests.
- `source-integrator` — enable flag, registry, docs, full suite, live smoke.
- `qa-reviewer` — read-only review of the finished diff.

Example:

```text
/add-source wantedly
```

# Japan Cybersecurity Jobs Dashboard

A small, single-user dashboard that collects cybersecurity job listings in Japan
from public job boards and shows the newest ones in a simple web UI.

**Status: complete.** Phases 0–6 are implemented: the app scaffold, the database
and query API, the scraper framework plus manual refresh service, all five
launch-source scrapers, the web UI, hardening, and the agent
workflow for adding sources.
Start with [AGENTS.md](AGENTS.md), then read the topic docs indexed in
[docs/README.md](docs/README.md).

## What it does

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

## Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ |
| Web app | FastAPI + Jinja2 + vanilla HTML/CSS/JS |
| Database | SQLite + SQLAlchemy 2.0 |
| HTTP client | httpx (async) |
| HTML parsing | BeautifulSoup + lxml, plus JSON-LD parsing |
| Tests / lint | pytest, respx, ruff |

## Quick start

The dashboard is runnable now; the UI is served at
<http://127.0.0.1:8001/> (development server).

```bash
# 1. Install
uv sync --extra dev

# 2. Configure
cp .env.example .env

# 3. Run (development server on port 8001)
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

## Launch sources

1. **Michael Page Japan** — IT Security category
2. **JapanDev** — Security jobs landing page
3. **TokyoDev** — Security jobs category
4. **Daijob** — Security System SE category + Japanese security keywords
5. **Robert Half Japan** — IT / security listings

All five were checked during source research: they return public HTML/JSON without a
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
| [docs/README.md](docs/README.md) | Index of all documentation |
| [docs/sources.md](docs/sources.md) | Source research, URLs, fields, robots, login notes |
| [docs/architecture.md](docs/architecture.md) | Components, refresh flow, concurrency, errors |
| [docs/data-model.md](docs/data-model.md) | SQLite schema, normalization, dedup, retention |
| [docs/scrapers.md](docs/scrapers.md) | Scraper contract, per-source strategy, testing |
| [docs/ui.md](docs/ui.md) | Minimal UI and HTTP API specification |
| [docs/operations.md](docs/operations.md) | Setup, run, troubleshoot, add a source |
| [docs/verification.md](docs/verification.md) | Verification playbook: run the app and check it |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/agents/](docs/agents/README.md) | How the project was built, phase by phase |

## OpenCode helpers

The repository ships the workflow used to build it, so a new source can be
added with one instruction.

**Commands** (`.opencode/commands/`)

- `/add-source <source>` — add a source end to end: research, brief, scraper,
  fixtures, tests, registration, live smoke, review.
- `/research-source <source>` — evaluate a candidate source and write a brief
  without writing code.
- `/verify-ui` — verify the running dashboard in a real browser against the
  host dev server (`127.0.0.1:8001`): layout, filters, states, accessibility,
  console/network. Separate from `uv run pytest -q` and the automated
  `pytest -m ui` suite.

**Skills** (`.opencode/skills/`)

- `source-onboarding` — the full onboarding workflow, phases, gates, and
  handoffs.
- `scraper-authoring` — the parser-level checklist and per-field mapping.
- `dashboard-qa` — the review checklist for any change.
- `ui-verification` — the agent-driven browser checklist for the running UI.

**Subagents** (`.opencode/agents/`)

- `source-researcher` — robots/terms research and the source brief.
- `scraper-builder` — scraper module, fixtures, parser tests.
- `source-integrator` — enable flag, registry, docs, full suite, live smoke.
- `qa-reviewer` — read-only review of the finished diff.

Example:

```text
/add-source wantedly
```

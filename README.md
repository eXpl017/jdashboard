# Japan Cybersecurity Jobs Dashboard

A small, single-user dashboard that collects cybersecurity job listings in Japan
from public job boards and shows the newest ones in a simple web UI.

**Status: planning only.** No application code has been written yet.
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

## Planned quick start

These commands are the target after implementation, not runnable yet.

```bash
# 1. Install
uv sync --extra dev

# 2. Configure
cp .env.example .env

# 3. Run
uv run uvicorn app.main:app --reload

# 4. Open http://127.0.0.1:8000 and click Refresh
```

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
| [PLAN.md](PLAN.md) | Master plan, scope, phases, acceptance criteria |
| [docs/sources.md](docs/sources.md) | Source research, URLs, fields, robots, login notes |
| [docs/architecture.md](docs/architecture.md) | Components, refresh flow, concurrency, errors |
| [docs/data-model.md](docs/data-model.md) | SQLite schema, normalization, dedup, retention |
| [docs/scrapers.md](docs/scrapers.md) | Scraper contract, per-source strategy, testing |
| [docs/ui.md](docs/ui.md) | Minimal UI and HTTP API specification |
| [docs/roadmap.md](docs/roadmap.md) | Ordered implementation phases |
| [docs/operations.md](docs/operations.md) | Setup, run, troubleshoot, add a source |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/questions.md](docs/questions.md) | Decisions needed from you |
| [docs/tasks/](docs/tasks/) | Task briefs for AI-assisted implementation |

## OpenCode helpers planned

- Skills: `.opencode/skills/scraper-authoring/`, `.opencode/skills/dashboard-qa/`
- Subagents: `.opencode/agents/scraper-builder.md`, `.opencode/agents/qa-reviewer.md`,
  `.opencode/agents/source-researcher.md`

These encode the repeatable workflow so each new source is added consistently.

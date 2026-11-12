# Master Plan — Japan Cybersecurity Jobs Dashboard

## 1. Goal

Build a small, reliable, single-user dashboard that answers one question:

> What cybersecurity jobs in Japan were posted in the last 3 days?

The dashboard must be easy to run locally, easy to extend with new sources, and
honest about where each listing came from and when it was last seen.

## 2. Scope

### In scope (v1)

- Python application, run locally.
- Five public job sources, one scraper module per source.
- Manual refresh from the dashboard only.
- SQLite persistence.
- Default 3-day window, based on the source's posting date.
- Minimal HTML/CSS/JS UI with search, source, role-type, language, location,
  location-scope, remote, visa/overseas, tag, and date-window filters, plus
  per-source refresh status.
- Per-source error isolation: one broken source must not break the dashboard.
- Tests for parsing, normalization, classification, repository, and API.
- Documentation for adding a new source.

### Out of scope (v1)

- User accounts, login, permissions, multi-tenancy.
- Scheduled/automatic scraping, cron, background daemons.
- Applying to jobs, saving applications, cover letters.
- Email/Slack notifications.
- Resume upload or candidate profiles.
- Scraping sites that require a login, paywall, CAPTCHA bypass, or Cloudflare
  challenge bypass.
- LLM summarization/translation (possible later, but not part of v1).
- Mobile app.

## 3. Product decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Role scope | **Engineering/technical security roles only** | Matches the user's choice; GRC, audit, consulting, sales, and management roles are stored but hidden by default |
| Language | **English and Japanese, tagged** | Broad coverage; the UI can filter to English-friendly or Japanese roles |
| Location | **All Japan; remote OK, no international remote** | The user intends to relocate to Japan and work there |
| Relocation | Track `visa_sponsorship` and `overseas_eligible` | The user needs to move to Japan; make these requirements visible |
| UI stack | FastAPI + Jinja2 + vanilla JS | Python-native, no Node build, enough for a minimal dashboard |
| Database | SQLite + SQLAlchemy 2.0 | Zero-ops, single file, easy backup |
| HTTP | httpx async | Works well with FastAPI, supports timeouts/retries |
| Parsing | BeautifulSoup + lxml + JSON-LD | All five sources expose HTML/JSON-LD; no headless browser needed |
| Refresh | Manual only, background task with progress | Avoids request timeouts, keeps scraping user-initiated |
| Time window | 3 days by default, based on source `posted_at` | Matches the requirement; a 7/30/all toggle prevents empty days |
| Timezone | Store UTC, display Asia/Tokyo | Correct date math; Japan-focused UX |
| Auth | None for the dashboard; none for launch sources | Local single-user app; all launch sources are public |
| Dedup | Per-source URL fingerprint in v1 | Simple and safe; cross-source grouping is a later enhancement |
| Host binding | `127.0.0.1` by default | No accidental exposure of a no-auth dashboard |

## 4. Launch sources

| # | Source | Why it is included | Access method |
| --- | --- | --- | --- |
| 1 | Michael Page Japan | Dedicated IT Security category with strong roles (SOC, CSIRT, GRC, CISO, threat intel) | Public HTML listing + JSON-LD on detail pages |
| 2 | JapanDev | English-friendly tech jobs, dedicated Security landing page | Public Nuxt HTML + JSON-LD on detail pages |
| 3 | TokyoDev | English-friendly tech jobs, dedicated Security category | Public HTML + JSON-LD on detail pages; Atom feed available |
| 4 | Daijob | Large bilingual board with a Security System SE category | Public HTML search + detail pages |
| 5 | Robert Half Japan | Recruitment agency with daily IT/security roles | Public HTML with embedded JSON |

Detailed evidence, URL patterns, robots notes, and excluded sources are in
[docs/sources.md](docs/sources.md).

## 5. Architecture at a glance

```text
Browser (HTML/CSS/JS)
    |
    | GET /, GET /api/jobs, POST /api/refresh, GET /api/refresh/status
    v
FastAPI application
    |-- Job query API  ----------> SQLite (data/jobs.db)
    |-- Refresh service (lock) --> Scraper registry
                                     |-- MichaelPageScraper
                                     |-- JapanDevScraper
                                     |-- TokyoDevScraper
                                     |-- DaijobScraper
                                     |-- RobertHalfScraper
                                     |
                                     +--> HttpClient (robots, retry, rate limit)
                                     +--> Normalizer / Classifier
                                     +--> Repository (upsert + run stats)
```

Full detail: [docs/architecture.md](docs/architecture.md).

## 6. Refresh behavior

1. User clicks **Refresh**.
2. `POST /api/refresh` acquires a process-wide lock. If a refresh is already
   running, return `409 Conflict`.
3. A `scrape_runs` row is created with `status=running`.
4. Sources run sequentially by default. Within a source, detail-page requests
   use a small concurrency limit (2–3) and a minimum delay.
5. Each source returns normalized `ScrapedJob` objects. The repository upserts
   by fingerprint, updates `last_seen_at`, and records new/updated counts.
6. Per-source results are written to `scrape_source_results`.
7. The run finishes as `success`, `partial`, or `failed`.
8. The UI polls `GET /api/refresh/status` and reloads jobs when done.

No scheduler, no startup scrape, no hidden background refresh.

## 7. Date semantics

- `posted_at`: the source's original posting date, normalized to UTC.
- `source_updated_at`: the source's "updated/verified" date, if available.
- `first_seen_at`: when this dashboard first saw the listing.
- `last_seen_at`: when this dashboard last saw the listing.
- `expires_at`: source expiry date, if available.
- `date_confidence`: `high` when the source gives an explicit date, `low` when
  we fall back to `first_seen_at`.

Default view: `posted_at >= now - 3 days` in Asia/Tokyo. A toggle can include
older active listings, and a separate badge can show "new to dashboard" based
on `first_seen_at`.

## 8. Security relevance

The dashboard is for cybersecurity jobs, so every listing is scored and tagged.

- Core keywords: security, cybersecurity, infosec, information security,
  セキュリティ, 情報セキュリティ, サイバーセキュリティ.
- Domains: SOC, CSIRT, SIEM, SOAR, incident response, threat intelligence,
  penetration testing, vulnerability management, AppSec, product security,
  cloud security, IAM, GRC, ISMS, ISO 27001, audit, CISO, malware, forensics,
  zero trust, DevSecOps, SAST/DAST, WAF, EDR/XDR, PKI, cryptography.
- Japanese terms: 脆弱性, 脅威インテリジェンス, ペネトレーションテスト,
  インシデントレスポンス, 情報セキュリティ, セキュリティエンジニア, 監査,
  暗号, フォレンジック.
- Negative terms to demote: 警備, security guard, security camera, 防犯,
  food security, social security.

The score is a ranking aid, not a hard truth. Source category pages (Michael
Page IT Security, TokyoDev Security, JapanDev Security, Daijob Security System
SE) provide a strong prior. The UI shows tags so the user can judge.

**Role scope:** the default view includes technical/engineering roles
(security engineer, AppSec, cloud security, SOC analyst, incident response,
threat intelligence, pentest, vulnerability management, IAM, DevSecOps, security
architecture). It excludes GRC, audit, compliance, consulting, sales, and
management roles by default. Those rows may still be stored with a
`role_category` so the rule can be changed later without re-scraping.

**Language:** detect `en`, `ja`, or `bilingual` from the title/description and
expose a language filter. Do not machine-translate in v1.

**Location:** include Japan-based, hybrid, and remote-within-Japan roles. Exclude
"remote anywhere/worldwide" roles that are not Japan-eligible. Track
`visa_sponsorship` and `overseas_eligible` because the user intends to relocate
to Japan.

## 9. UI

One page:

- Header: title, last refresh time, Refresh button.
- Summary cards: total jobs, new in window, sources healthy, last run status.
- Filters: keyword, source, location, remote type, tag, date window, sort.
- Job list: title link, company, location, salary, source badge, posted date,
  tags, expandable description.
- Refresh panel: per-source progress and errors.

Full spec: [docs/ui.md](docs/ui.md).

## 10. Implementation phases

| Phase | Deliverable | Acceptance |
| --- | --- | --- |
| 0 | Decisions, skeleton, tooling | `uv sync`, `ruff check`, `pytest` run |
| 1 | Database + repository + query API | Fixture jobs can be inserted and filtered |
| 2 | Scraper framework + refresh service | Fake scraper runs end-to-end, run rows recorded |
| 3a | Michael Page scraper | Fixture + live smoke test pass |
| 3b | JapanDev scraper | Fixture + live smoke test pass |
| 3c | TokyoDev scraper | Fixture + live smoke test pass |
| 3d | Daijob scraper | Fixture + live smoke test pass |
| 3e | Robert Half scraper | Fixture + live smoke test pass |
| 4 | UI + refresh polling | Click Refresh, see progress and new jobs |
| 5 | Hardening, tests, docs | Full refresh works; failures isolated; docs complete |
| 6 | Optional | Cross-source dedup, extra sources, export |

Detailed tasks: [docs/roadmap.md](docs/roadmap.md) and
[docs/tasks/](docs/tasks/).

## 11. Acceptance criteria for v1

- [ ] App starts with `uv run uvicorn app.main:app --reload`.
- [ ] Dashboard loads at `http://127.0.0.1:8000`.
- [ ] No network requests happen until the user clicks Refresh.
- [ ] Refresh runs all five scrapers and shows per-source progress.
- [ ] A failure in one source is visible but does not abort the others.
- [ ] Jobs are stored in SQLite and survive a restart.
- [ ] Default view shows jobs with `posted_at` in the last 3 days.
- [ ] User can switch to 7 days or all active listings.
- [ ] Default view shows technical/engineering roles; GRC/audit/consulting/
      sales/management are hidden by default.
- [ ] User can filter by language (`en`, `ja`, `bilingual`).
- [ ] Default view includes Japan-based/remote-in-Japan roles and excludes
      international-remote roles.
- [ ] Visa sponsorship and overseas-application eligibility are visible.
- [ ] Duplicate URLs from the same source are not inserted twice.
- [ ] Every job links to its original source.
- [ ] `pytest` passes without live network access.
- [ ] `ruff check` passes.
- [ ] README explains setup, refresh, and how to add a source.
- [ ] No credentials or cookies are required for the five launch sources.

## 12. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Source HTML changes | One module per source, saved fixtures, parser tests, easy disable |
| Rate limiting or blocking | 1 req/sec, retries with backoff, clear UA, request caps |
| robots.txt/ToS changes | Runtime robots check, documented policy, disable source if needed |
| Few jobs in 3 days | 7/30/all toggle, "new to dashboard" badge, source health panel |
| Duplicate jobs across sources | Source badge in v1; cross-source grouping in phase 6 |
| Date ambiguity/timezones | Store UTC + raw date, display JST, confidence flag |
| Japanese text handling | UTF-8 everywhere, normalize width, no translation in v1 |
| No-auth dashboard exposed | Bind to 127.0.0.1; document reverse proxy/auth if exposed |
| Scraper drift | Task briefs + `scraper-authoring` skill + QA subagent |

## 13. Decisions

The product questions in [docs/questions.md](docs/questions.md) are answered:

- Engineering/technical security roles only by default; other categories are
  stored but hidden.
- English and Japanese listings, tagged with a language filter.
- The 3-day window uses the source's original `posted_at`.
- All Japan, including remote within Japan; no international remote.
- One row per source; cross-source dedup is deferred.
- Public sources only; no login or authenticated scraping.
- FastAPI + Jinja2 + vanilla JS, SQLite, manual refresh.

Relocation handling is resolved: the default sort stays **newest first**, and
visa/overseas information appears as badges (`Visa support`, `Overseas OK`,
`Japan residents only`). Jobs are not reordered by relocation eligibility.

## 14. Status and next actions

**This plan has been executed.** Phases 0–5 are complete: the application,
the database and query API, the scraper framework and refresh service, all
five launch-source scrapers, the web UI, and the hardening/documentation work.

Current state:

- 128 tests pass; `ruff check .` is clean.
- The dashboard runs locally (`make run`, port 8001) or in Docker
  (`docker compose up -d`, port 8000).
- `AGENTS.md` is the entry point for agents; `docs/README.md` indexes the
  documentation.

Remaining optional work is Phase 6 in [`docs/roadmap.md`](docs/roadmap.md):
cross-source deduplication, CSV/JSON export, saved filter presets, additional
sources, and Alembic migrations.

To pick the project up again:

1. Install Python 3.11+ and `uv` (or use `pip` + `venv`).
2. `uv sync --extra dev` and `cp .env.example .env`.
3. Read [`AGENTS.md`](AGENTS.md) and [`docs/README.md`](docs/README.md).

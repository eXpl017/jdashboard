# Overview — how the project was built

## The question the app answers

> What cybersecurity jobs in Japan were posted in the last 3 days?

Everything else follows from that: a short default window, honest source
labels, filters that matter to someone relocating (language, remote scope,
visa eligibility), and refreshes that only happen when a human asks for them.

## The phases

| Phase | Delivered |
| --- | --- |
| 0 — Foundation | Decisions, scaffold, tooling (`uv`, `ruff`, `pytest`) |
| 1 — Data and API | SQLite schema, repository layer, query/filter API |
| 2 — Scraper framework | `BaseScraper` contract, polite HTTP client, refresh service |
| 3 — Sources | Michael Page, JapanDev, TokyoDev, Daijob, Robert Half |
| 4 — UI | One page, filters, job cards, live refresh panel |
| 5 — Hardening | CLI scripts, JSON logging, expiry handling, docs |
| 6 — AI workflow | Commands, skills, and subagents for adding a source |

## Shape of the system

```text
  browser ──► GET /api/jobs ──► repository ──► SQLite
      │                            ▲
      │  POST /api/refresh         │ upsert (normalized + classified)
      ▼                            │
  refresh service ──► scraper ────┘
      │                  │
      │                  └── HTTP client: robots.txt, 1 req/s, retries, caps
      └── progress in memory + scrape_runs / scrape_source_results in SQLite
```

## Decisions that shaped everything

1. **Manual refresh only.** No scheduler, no startup scrape, no polling. A
   refresh is a user action, and it takes minutes — so the UI shows progress.
2. **Plain HTTP only.** No headless browser, no login, no bypass. If a site
   blocks a plain client, the source is deferred and documented.
3. **Store everything, filter in the UI.** GRC, consulting, sales, management,
   and international-remote roles are stored with their real category. The
   default view hides them; the filters bring them back without re-scraping.
4. **One row per source listing.** Cross-source deduplication was deferred so
   a listing is never silently merged or lost.
5. **The source's own date is the truth.** The 3-day window uses `posted_at`;
   `first_seen_at` only drives the "New" badge.
6. **Never guess.** Salary, visa sponsorship, and overseas eligibility stay
   unknown unless the source states it.

## Where to look next

- The rules a change must respect: repository `AGENTS.md`.
- The topic specs: `docs/architecture.md`, `docs/data-model.md`,
  `docs/scrapers.md`, `docs/ui.md`.
- How to run and check it: `docs/verification.md`.
- Why a choice was made: `docs/decisions.md`.

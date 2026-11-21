---
name: Source Onboarding
description: Add a new job source to the Japan cybersecurity jobs dashboard end to end - robots/terms research, source brief, scraper implementation with fixtures and tests, registration, live smoke test, and documentation. Use when asked to add, support, integrate, or evaluate a new job board or source.
---

# Source Onboarding

Use this skill when a new job source has to be added to the dashboard, or when
a candidate source needs to be evaluated before any code is written.

The entry points are the `/add-source <source>` and `/research-source <source>`
commands in `.opencode/commands/`.

## Read before starting

1. `AGENTS.md` — project rules and conventions.
2. `docs/scrapers.md` — the scraper contract, shared utilities, per-source notes.
3. `docs/data-model.md` — field meanings, date semantics, fingerprints.
4. `docs/sources.md` — existing sources and their quirks.
5. `docs/operations.md` — robots/terms policy and troubleshooting.
6. `.opencode/skills/scraper-authoring/SKILL.md` — the parser-level checklist.

## Who does what

| Phase | Owner | Artifact |
| --- | --- | --- |
| 1. Research | `source-researcher` subagent | `docs/research/<source>.md` |
| 2. Brief | main agent | `docs/sources.md` section (+ the research brief) |
| 3. Implement | `scraper-builder` subagent | `app/scrapers/<source>.py`, fixtures, parser tests |
| 4. Integrate | `source-integrator` subagent | config flag, registry, docs, green test suite |
| 5. Review | `qa-reviewer` subagent | findings report |
| 6. Report | main agent | summary for the user |

Run the phases in order. Each phase hands a written artifact to the next one;
do not start implementing before the research verdict is `implement`.

## Phase 1 — Research (gate)

Delegate to the `source-researcher` subagent.

Gate conditions, all required before code is written:

- Listing and detail pages load without a login.
- `robots.txt` allows the listing and detail paths for `User-agent: *`.
- No CAPTCHA, Cloudflare challenge, or paywall stands between a plain HTTP
  client and the data.
- The source carries a usable volume of security roles.

If any gate fails, stop. Report the blocker and recommend `defer` or `reject`.
Never attempt a bypass.

## Phase 2 — Brief

From the research artifact, write:

- A section in `docs/sources.md`: listing URL, detail pattern, date semantics,
  language(s), visa/overseas wording, remote wording, quirks, and the health
  expectation for a normal day.
- The research brief stays in `docs/research/<source>.md`; the adopted summary
  goes into `docs/sources.md` with the goal, inputs, acceptance criteria, and
  the files the scraper will touch.
- Add the source to the launch/deferred matrix in `docs/sources.md`.

## Phase 3 — Implement

Delegate to the `scraper-builder` subagent with the brief.

The scraper must:

- Subclass `BaseScraper` and use the shared `HttpClient` (robots, throttle,
  retries, per-source concurrency cap).
- Return `ScrapedJob` objects only. It never touches the database.
- Prefer JSON-LD or embedded JSON, with an HTML fallback.
- Keep selectors in small module-level constants.
- Tolerate one bad job (log and skip) instead of failing the source.
- Set `role_category`, `language`, `location_scope`, and `overseas_eligible`
  only from explicit source evidence; otherwise leave them to the shared
  classifier.
- Save listing and detail fixtures under `tests/fixtures/` and add parser tests
  that run without network access.

## Phase 4 — Integrate

Delegate to the `source-integrator` subagent. It handles the wiring that sits
outside `app/scrapers/`:

- `enable_<source>` flag in `app/config.py` and `.env.example`.
- Registration in `app/scrapers/registry.py`.
- Per-source notes in `docs/scrapers.md` and the source list in `README.md`.
- `ruff check .` and `pytest` green.
- Live smoke: `uv run python -m scripts.inspect_source <source> --limit 3`.

## Phase 5 — Review

Delegate to the `qa-reviewer` subagent over the finished diff. Fix every Blocker
and High finding, then re-run the suite.

## Phase 6 — Report

Report to the user:

```text
Source: <id>
Verdict/robots evidence: <allowed path + how you know>
Files changed: ...
Fixtures added: ...
Tests: <command and result>
Live smoke test: <result>
Open risks: ...
```

## Hard rules

- No login, CAPTCHA, Cloudflare, or paywall bypass. No Playwright for
  anti-bot evasion.
- No scraping at startup, on page load, or on a timer. Refresh stays manual.
- Do not drop non-technical or `international_remote` rows in the scraper; the
  UI filters them.
- Do not guess salary, visa sponsorship, or overseas eligibility.
- Do not change the behaviour of existing sources while adding a new one.
- Do not commit secrets, cookies, tokens, or full HTML dumps of pages that
  contain personal data.

## Details

- `references/pipeline.md` — the phase-by-phase procedure, commands, and
  handoff artifacts.
- `references/definition-of-done.md` — the checklists to close each phase.

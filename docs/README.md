# Documentation Index

Every document in this repository, what it is for, and when to read it.

## Start here

| File | Purpose | Read it when |
| --- | --- | --- |
| [`../AGENTS.md`](../AGENTS.md) | Agent entry point: layout, commands, rules | you are an agent picking up the project |
| [`../README.md`](../README.md) | Human overview and quick start | you want the short version |
| [`verification.md`](verification.md) | How to run the app and check it works | you are verifying a change |
| [`operations.md`](operations.md) | Setup, refresh, backup, troubleshooting | you are running or operating the app |

## Topic docs

| File | Purpose | Read it when |
| --- | --- | --- |
| [`architecture.md`](architecture.md) | Components, refresh flow, concurrency, errors | you change how data flows |
| [`data-model.md`](data-model.md) | SQLite schema, field meanings, dates, fingerprints | you touch models, queries, or dates |
| [`scrapers.md`](scrapers.md) | The scraper contract, shared utilities, per-source notes, checklist for new sources | you write or repair a scraper |
| [`sources.md`](sources.md) | Source research: URLs, quirks, robots notes, health expectations, deferred candidates | you add or evaluate a source |
| [`ui.md`](ui.md) | UI specification and the HTTP API contract | you change the page or the API |
| [`decisions.md`](decisions.md) | Architecture decision records (ADR-001 … ADR-014) | you need the "why" behind a choice |

## Working material

| Path | Purpose |
| --- | --- |
| [`research/`](research/README.md) | Briefs for candidate sources that were evaluated |
| [`agents/`](agents/README.md) | How the project was built, phase by phase, and why |

## Other places with agent instructions

| Path | Scope |
| --- | --- |
| [`../app/AGENTS.md`](../app/AGENTS.md) | Application package layering and API surface |
| [`../app/scrapers/AGENTS.md`](../app/scrapers/AGENTS.md) | Scraper contract and field rules |
| [`../tests/AGENTS.md`](../tests/AGENTS.md) | Test conventions and fixture rules |
| [`../scripts/AGENTS.md`](../scripts/AGENTS.md) | CLI conventions |
| [`../.opencode/AGENTS.md`](../.opencode/AGENTS.md) | How to edit commands, skills, and subagents |
| [`AGENTS.md`](AGENTS.md) | How to keep these docs accurate |

## Conventions

- Times are stored in UTC and displayed in Asia/Tokyo.
- The default window is 3 days, based on the source's posting date.
- The default view is technical roles in Japan (`engineering` + `operations`,
  `location_scope=japan`); other rows are stored but hidden.
- Scraping only ever happens on an explicit user action.

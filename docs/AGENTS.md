# AGENTS.md — `docs/`

Documentation for humans and agents. `docs/README.md` is the index; this file
explains how to keep the docs honest.

## Index

| File | Read it when |
| --- | --- |
| `README.md` | you need the map of all docs |
| `architecture.md` | you are changing how data flows (scraper → refresh → repository → API) |
| `data-model.md` | you touch the schema, fields, dates, or fingerprints |
| `scrapers.md` | you write or repair a scraper (contract + per-source notes) |
| `sources.md` | you add or evaluate a source (URLs, quirks, health expectations) |
| `ui.md` | you change the UI or the HTTP API |
| `operations.md` | you run, troubleshoot, back up, or deploy the app |
| `verification.md` | you are checking that a change works (playbook) |
| `decisions.md` | you need the "why" behind an architectural choice (ADRs) |
| `agents/` | how the project was built, phase by phase, and what is still open |
| `research/` | briefs for candidate sources that were evaluated |

## Rules

- Docs are part of the change. A behaviour change lands with the doc change in
  the same commit.
- Update the index above when you add a document.
- Keep code snippets runnable. A snippet that no longer works is worse than no
  snippet.
- Use the same vocabulary as the code: `role_category`, `location_scope`,
  `posted_at`, `first_seen_at`, `source_id`.
- Record *observed* behaviour, including its limits ("0 candidates is not an
  error", "a full refresh takes ~2 minutes because of the 1 req/s throttle").
- Do not paste full HTML pages or personal data into docs; reference the
  fixture files instead.
- ADRs are append-only: add a new ADR rather than rewriting an old one.

## Related

- The repository root `AGENTS.md` is the entry point for any agent.
- `docs/verification.md` is the checklist to run after a change.

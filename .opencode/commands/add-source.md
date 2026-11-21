---
description: Add a new job source to the dashboard end-to-end (research, brief, scraper, tests, registration, live smoke, docs)
agent: build
---

Add a new job source to the Japan cybersecurity jobs dashboard.

Source to add: $ARGUMENTS

Load the `source-onboarding` skill and follow it end to end. Work through the
phases in order; do not skip a gate.

## Phases

1. **Research** — delegate to the `source-researcher` subagent. It writes
   `docs/research/<source>.md` with the verdict, robots.txt evidence, URL
   patterns, available fields, and risks.
   - Verdict `reject` → stop and report why.
   - Verdict `defer` → report the blocker; do not write code.
2. **Brief** — turn the research into a source brief: keep the detailed
   evidence in `docs/research/<source>.md` and the adopted summary in
   `docs/sources.md`.
3. **Implement** — delegate to the `scraper-builder` subagent. It writes
   `app/scrapers/<source>.py`, the fixtures under `tests/fixtures/`, and the
   parser tests.
4. **Integrate** — delegate to the `source-integrator` subagent. It adds the
   enable flag, registers the scraper, updates the docs, and runs the full
   test suite plus a live smoke test.
5. **Review** — delegate to the `qa-reviewer` subagent on the finished diff.
   Fix everything it reports as Blocker or High.
6. **Report** — summarize what changed, the test and smoke results, the
   robots/terms evidence, and the remaining risks.

## Hard rules

- Never bypass a login, CAPTCHA, Cloudflare challenge, paywall, or rate limit.
- Respect `robots.txt`; if the listing or detail path is disallowed, stop and
  document it instead of working around it.
- Scraping happens only when the user asks for it: manual refresh in the UI or
  the developer CLI. No scheduler, no startup scrape.
- A new source must not change the behaviour of existing sources.
- Non-technical and `international_remote` rows are stored, not dropped; the UI
  filters them.
- Do not guess visa sponsorship or overseas eligibility; leave them unknown
  unless the source states it.

## Useful commands

```bash
uv run python -m scripts.inspect_source <source> --limit 3   # live scrape, no DB writes
uv run python -m scripts.refresh --source <source> --window-days 3   # live refresh into the DB
uv run pytest && uv run ruff check .
```

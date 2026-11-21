---
name: Dashboard QA
description: Review and test changes to the Japan cybersecurity jobs dashboard for correctness, source isolation, manual-refresh behavior, data integrity, accessibility, and secrets/robots compliance.
---

# Dashboard QA

Use this skill when reviewing or testing a change to the dashboard, especially
before committing or handing work back.

## Read before reviewing

1. `AGENTS.md` — project rules and conventions.
2. `docs/architecture.md` — refresh flow and error handling.
3. `docs/data-model.md` — upsert and date semantics.
4. `docs/ui.md` — API and UI expectations.
5. `docs/operations.md` — runtime and troubleshooting.

## Review checklist

### Behavior

- [ ] No scraping happens at startup, on page load, or on a timer.
- [ ] Scraping starts only from `POST /api/refresh` or the developer CLI.
- [ ] A second refresh while one is running returns `409`.
- [ ] The refresh lock is released on success, partial failure, and exception.
- [ ] A single source failure does not abort other sources.
- [ ] A run finishes as `success`, `partial`, or `failed` correctly.
- [ ] The UI shows per-source status and the last successful refresh.

### Data integrity

- [ ] Fingerprints are stable; the same URL is not inserted twice.
- [ ] `first_seen_at` is preserved on update.
- [ ] `last_seen_at` is updated on every successful sighting.
- [ ] Jobs are not deactivated merely because a source did not return them.
- [ ] Date-only values are normalized to JST midnight and stored as UTC.
- [ ] `posted_at`, `source_updated_at`, and `first_seen_at` are not conflated.
- [ ] Salary numbers are only set when parseable; `salary_text` is always kept.
- [ ] Japanese text is stored and displayed correctly.
- [ ] `role_category` is assigned title-first; "security consultant" is not
      mislabeled as engineering.
- [ ] `language` reflects the listing text, not the URL path.
- [ ] `location_scope` distinguishes `japan_remote` from
      `international_remote`.
- [ ] `overseas_eligible` and `visa_sponsorship` are only set from explicit
      source text; unknown stays `NULL`, not `0`.
- [ ] Non-technical and international-remote rows are stored, not silently
      dropped by the scraper.

### API and UI

- [ ] `GET /api/jobs` filters work: `q`, `source`, `role`, `language`,
  `location`, `location_scope`, `remote`, `visa`, `tag`, `days`, `sort`,
  `limit`, `offset`.
- [ ] Default view returns `engineering` + `operations` roles and excludes
  `international_remote`.
- [ ] Language filter: `en`/`ja` also match `bilingual`; `any` matches all.
- [ ] Visa filter: `overseas` uses `overseas_eligible=1`, `sponsored` uses
  `visa_sponsorship IS NOT NULL`, `either` is the union.
- [ ] Non-technical categories and international-remote roles are reachable
  only by explicitly widening the filters.
- [ ] `GET /api/jobs/{id}` returns 404 for unknown IDs.
- [ ] `GET /api/stats` and `/api/sources` match the UI.
- [ ] The UI handles empty, loading, partial, and failed states.
- [ ] The refresh button is disabled while running.
- [ ] Job descriptions are rendered as text, not raw HTML.
- [ ] No external JS/CSS/CDN dependency.
- [ ] Keyboard navigation and labels work.
- [ ] `aria-live` is used for refresh status.

### Compliance and safety

- [ ] `robots.txt` is checked at runtime.
- [ ] Rate limits and concurrency caps are enforced.
- [ ] User-Agent is clear and configurable.
- [ ] No login/CAPTCHA/Cloudflare bypass.
- [ ] No secrets, cookies, or tokens in the repo, DB, or logs.
- [ ] No full HTML pages or personal data in logs.
- [ ] `data/` and `.env` are gitignored.
- [ ] The app binds to `127.0.0.1` by default.

### Quality

- [ ] `ruff check .` passes.
- [ ] `pytest` passes without live network.
- [ ] New behavior has tests.
- [ ] Fixtures are committed and small.
- [ ] Docs are updated.
- [ ] No unrelated refactors or dead code.

## Test commands

```bash
uv run ruff check .
uv run pytest
uv run pytest tests/test_scrapers.py -q
uv run python -m scripts.inspect_source <source> --limit 3
```

## Report format

List findings by severity, with file and line references:

```text
[Blocker] ...
[High] ...
[Medium] ...
[Low] ...
Tests run: ...
Not tested: ...
```

If there are no findings, say so explicitly and list what was tested.

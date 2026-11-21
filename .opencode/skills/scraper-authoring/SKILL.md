---
name: Scraper Authoring
description: Add or repair a job-source scraper for the Japan cybersecurity dashboard, including research, fixtures, parsing, normalization, tests, and robots/rate-limit compliance.
---

# Scraper Authoring

Use this skill when adding a new job source or repairing an existing scraper in
this project.

For a brand-new source, the `source-onboarding` skill covers the whole flow
(research → brief → implement → integrate → review) and the `/add-source`
command runs it. Use this skill for the parser-level checklist and for repairs
to an existing scraper.

## Read before editing

1. `AGENTS.md` — project rules and conventions.
2. `docs/sources.md` — the source brief and robots notes.
3. `docs/scrapers.md` — the scraper contract and per-source strategy.
4. `docs/data-model.md` — field meanings and normalization rules.
5. `docs/research/<source>.md` — the research brief for the source, if it exists.

## Non-negotiable rules

- Do not bypass a login, CAPTCHA, Cloudflare challenge, paywall, or other access
  control.
- Check `robots.txt` for the listing and detail paths. If disallowed, stop and
  document it.
- Use the shared HTTP client. Do not create an unconfigured `httpx` client.
- Keep request rates at or below the configured limit (default 1 req/sec/host).
- Identify the scraper with the configured `User-Agent`.
- Do not fetch apply, login, member, or company-profile pages.
- Scrapers return `ScrapedJob` objects. They do not write to the database.
- A single bad job must not fail the whole source. Log and skip it.
- A source-wide failure must raise `ScraperError` with a user-safe message.
- Do **not** drop rows just because the default UI would hide them. Store
  non-technical (`grc`, `consulting`, `sales`, `management`) and
  `international_remote` rows; the UI filters them.
- Set `role_category`, `language`, `location_scope`, and `overseas_eligible`
  from explicit source evidence, or leave them for the shared
  normalizer/classifier. Never guess visa or overseas eligibility.

## Workflow

1. **Research**
   - Fetch the listing page and one detail page with a normal HTTP client.
   - Record the listing URL, detail URL pattern, date field, salary field,
     location field, language(s), visa/overseas statements, and any anti-bot
     behavior.
   - Add or update the source brief in `docs/sources.md`.
2. **Fixture**
   - Save a listing page and a detail page under `tests/fixtures/`.
   - Add one edge case: missing salary, Japanese title, remote, or expired.
   - Strip unnecessary assets if the fixture is large, but keep the structures
     the parser needs.
3. **Implement**
   - Create `app/scrapers/<source>.py`.
   - Subclass `BaseScraper`.
   - Reuse `services/http.py`, `services/dates.py`, `services/normalize.py`,
     and `services/classify.py`.
   - Parse JSON-LD first when available; fall back to stable HTML selectors.
   - Keep selectors/labels in small module-level constants.
4. **Register**
   - Add the scraper to `app/scrapers/registry.py`.
   - Add an `ENABLE_<SOURCE>` flag if the project uses per-source flags.
5. **Test**
   - Parser tests against fixtures.
   - Normalization tests for unusual salary/date/location values.
   - A mocked end-to-end test with `respx` if useful.
   - Run `ruff check .` and `pytest`.
6. **Smoke test**
   - Run `uv run python -m scripts.inspect_source <source> --limit 3`.
   - Confirm title, company, posted date, and URL look correct.
   - Do not write to the database during inspection.
7. **Document**
   - Update `docs/sources.md`, `docs/scrapers.md`, and `README.md`.
   - Note any source-specific quirk.

## Field mapping checklist

- [ ] `source` and `source_job_id`
- [ ] canonical `url`
- [ ] `title`, `company`, `location`
- [ ] `remote_type`, `employment_type`
- [ ] `salary_text` always; `salary_min/max` only when parseable
- [ ] `posted_at` (source original) and `posted_at_raw`
- [ ] `source_updated_at` and `expires_at` when available
- [ ] `description_text` (and `description_html` only if needed)
- [ ] `japanese_level`, `visa_sponsorship` when available
- [ ] `overseas_eligible` only when the source states it
- [ ] `role_category` (technical vs. GRC/consulting/sales/management)
- [ ] `language` (`en` / `ja` / `bilingual` / `unknown`)
- [ ] `location_scope` (`japan_onsite` / `japan_hybrid` / `japan_remote` /
      `international_remote` / `unknown`)
- [ ] `security_tags` from the shared classifier
- [ ] `raw` compact debug data

## Common traps

- **Date-only values:** normalize to the start of the day in Asia/Tokyo.
- **Timezone:** store UTC, display JST.
- **Agency vs employer:** recruitment sites may put the agency in
  `hiringOrganization`; do not present the agency as the client.
- **Escaped JSON:** Robert Half embeds `JSON.parse('...')` with `\x22` escapes.
- **Broad keyword search:** Daijob's `kw=security` is noisy; prefer the category.
- **Old but active jobs:** TokyoDev may show "verified active" for older posts;
  keep `posted_at` and `source_updated_at` separate.
- **Duplicate links:** deduplicate by canonical detail URL before fetching.
- **English URL, Japanese body:** Daijob and Michael Page serve `/en/` pages
  whose detail text is Japanese. Detect language from the text, not the URL.
- **"Remote" is ambiguous:** "remote in Japan" is `japan_remote`; "work from
  anywhere / worldwide" is `international_remote` and is hidden by default.
- **Visa statements:** only set `visa_sponsorship` / `overseas_eligible` from
  explicit text. "English-speaking team" is not evidence of visa support.
- **Non-technical titles:** "security consultant", "security sales engineer",
  and "CISO" contain "security" but belong to `consulting`, `sales`, and
  `management`.

## Report format

When done, report:

```text
Source: <id>
Files changed: ...
Fixtures added: ...
Tests: <command and result>
Live smoke test: <result or not run>
robots/terms: <allowed/not allowed and evidence>
Open risks: ...
```

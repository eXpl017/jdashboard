# Task 06 — Daijob Scraper

## Goal

Implement `app/scrapers/daijob.py` for the Security System SE category and a
small set of curated Japanese security keywords.

## Read first

- `docs/sources.md` (section 4)
- `docs/scrapers.md` (section 4.4)
- `docs/data-model.md` (normalization rules)

## Source facts

- Category listing:
  `https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0`
- Redirects to `search_result?job_types[]=503&job_search_form_hidden=1`.
- About 22 jobs, 20 per page.
- Keyword search uses `kw` and redirects to `keywords=...`; it is broad.
- Detail pages contain `Updated YYYY-MM-DD` and `Activated YYYY-MM-DD`.
- robots allows search results; disallows company/member/apply pages.

## Implementation

1. Fetch the category page (`pg=0`), follow redirects.
2. Extract unique `/en/jobs/detail/<id>` links.
3. Optionally fetch `pg=1`.
4. Optionally run 2–3 keyword searches:
   `サイバーセキュリティ`, `情報セキュリティ`, `SOC`, `CSIRT`, `脆弱性`.
5. Deduplicate detail IDs.
6. Fetch detail pages, capped at 40.
7. Parse:
   - `Updated` → `source_updated_at`
   - `Activated` → `posted_at`
   - company, job type, industry, location, salary, Japanese level, description
8. Normalize and classify with strict title/description rules.
9. Return all parsed jobs; the refresh service applies the date window.

## Fixtures

- `tests/fixtures/daijob_list.html`
- `tests/fixtures/daijob_detail.html`
- `tests/fixtures/daijob_detail_japanese.html`

## Tests

- Extracts unique detail IDs.
- Parses `Activated` and `Updated`.
- Parses company, location, salary, Japanese level.
- Handles Japanese text.
- Sets `language` / `japanese_level` and `role_category` correctly for
  Japanese-language listings.
- Deduplicates IDs across category/keyword pages.
- Does not fetch company/member/apply pages.

## Acceptance

- [ ] Fixture tests pass.
- [ ] Live smoke test works.
- [ ] No more than 40 detail requests.
- [ ] No login/cookies.
- [ ] Docs updated if the page structure differs.

## Notes

- Prefer the category over the broad `kw=security` search.
- Do not scrape `/company/` or `/members/`.
- Detail pages are HTML, not JSON-LD; use stable labels and fixtures.

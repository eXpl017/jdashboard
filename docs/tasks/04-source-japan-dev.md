# Task 04 — JapanDev Scraper

## Goal

Implement `app/scrapers/japan_dev.py` for the Security landing page.

## Read first

- `docs/sources.md` (section 2)
- `docs/scrapers.md` (section 4.2)
- `docs/data-model.md` (normalization rules)

## Source facts

- Listing: `https://japan-dev.com/security-jobs-in-japan`
- Nuxt server-rendered HTML.
- About 37 unique `/jobs/<company>/<slug>` links; ~7 explicitly security-titled.
- Detail pages contain JSON-LD `JobPosting` with `datePosted`, `validThrough`,
  `hiringOrganization`, `jobLocation`, `baseSalary`, `employmentType`.
- robots allows the site except two blog/salary-guide resources.

## Implementation

1. Fetch the security landing page.
2. Extract unique job detail links.
3. Fetch up to 40 detail pages with the shared HTTP client.
4. Parse the first JSON-LD `JobPosting`.
5. Map fields:
   - title, description, datePosted, validThrough
   - hiringOrganization.name → company
   - jobLocation → location
   - baseSalary → salary
   - employmentType → employment type
6. Normalize and classify with a source prior (security landing page).
7. Return all parsed jobs; the refresh service applies the date window.

## Fixtures

- `tests/fixtures/japan_dev_list.html`
- `tests/fixtures/japan_dev_detail.html`
- `tests/fixtures/japan_dev_detail_japanese.html`

## Tests

- Extracts unique job links, not nav/related links.
- Parses title, company, location, datePosted, validThrough.
- Parses salary.
- Classifier demotes a clearly unrelated role.
- Handles Japanese text.
- Detects `language` and assigns `role_category`.
- Handles missing optional fields.

## Acceptance

- [ ] Fixture tests pass.
- [ ] Live smoke test returns security jobs.
- [ ] No more than 40 detail requests.
- [ ] No login/cookies.
- [ ] Docs updated if the page structure differs.

## Notes

- The landing page includes related roles; rely on classification.
- `datePosted` is date-only; normalize to JST midnight.
- Do not fetch the blog or salary-guide PDF.

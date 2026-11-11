# Task 03 — Michael Page Japan Scraper

## Goal

Implement `app/scrapers/michael_page.py` for the IT Security category.

## Read first

- `docs/sources.md` (section 1)
- `docs/scrapers.md` (section 4.1)
- `docs/data-model.md` (normalization rules)

## Source facts

- Listing: `https://www.michaelpage.co.jp/en/jobs/it-security`
- About 22 unique `/job-detail/...` links.
- Detail pages contain JSON-LD `JobPosting`.
- `datePosted` is date-only.
- `hiringOrganization.name` is Michael Page (agency), not the client.
- robots allows the category and detail pages.

## Implementation

1. Fetch the category page.
2. Extract unique `href` values containing `/job-detail/`.
3. Resolve relative URLs to absolute.
4. Fetch detail pages with the shared HTTP client, capped at 25.
5. Parse the first JSON-LD `JobPosting`.
6. Map fields:
   - title, description, datePosted, employmentType, industry
   - hiringOrganization.name → company
   - baseSalary min/max/unitText → salary fields
   - jobLocation address → location
   - jobLocationType TELECOMMUTE → remote
   - URL reference → source_job_id
7. Normalize and classify.
8. Filter by `posted_at >= since` in the refresh service, not in the scraper
   (the scraper may return all category jobs).

## Fixtures

- `tests/fixtures/michael_page_list.html`
- `tests/fixtures/michael_page_detail.html`
- `tests/fixtures/michael_page_detail_no_salary.html`

## Tests

- Extracts the expected number of unique detail URLs.
- Parses title, company, location, datePosted.
- Parses salary min/max.
- Handles missing salary.
- Handles remote (`TELECOMMUTE`).
- Assigns `role_category` and detects `language`; does not force `en`.
- Ignores non-job links.

## Acceptance

- [ ] Fixture tests pass.
- [ ] Live smoke test returns at least one security job.
- [ ] No more than 25 detail requests.
- [ ] No login/cookies.
- [ ] Docs updated if the page structure differs.

## Notes

- Do not fetch apply pages.
- Do not guess the client company if it is confidential.
- If JSON-LD is missing, fail the job with `ParseError`, not the whole source.

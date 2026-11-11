# Task 07 — Robert Half Japan Scraper

## Goal

Implement `app/scrapers/robert_half.py` for Robert Half Japan's public job
search.

## Read first

- `docs/sources.md` (section 5)
- `docs/scrapers.md` (section 4.5)
- `docs/data-model.md` (normalization rules)

## Source facts

- Listing: `https://www.roberthalf.com/jp/en/jobs`
- Pagination: `?pagenumber=2`, `?pagenumber=3`, ...
- Embedded JSON:
  `aemSettings.rh_job_search.initialResults = JSON.parse('...')`
- Fields include `date_posted`, `date_end`, `functional_role`, `city`,
  `country`, `payrate_min`, `payrate_max`, `salary_currency`, `remote`,
  `emptype`, `job_detail_url`, `summary`, `industry`.
- Public search endpoint observed:
  `https://prd-dr.jps.api.roberthalfonline.com/search` (fallback, not required).
- robots allows `/jp/en/jobs`; disallows `/jp/en/search?param=*`.
- `keywords` did not reliably filter during planning.

## Implementation

1. Fetch `/jp/en/jobs`.
2. Extract the `initialResults` JSON string.
3. Unescape `\x22`, `\u002D`, and similar sequences; parse JSON.
4. Iterate jobs and map:
   - title ← `functional_role`
   - company ← "Robert Half Japan" (agency) or parsed client
   - location ← `city` + `country`
   - posted_at ← `date_posted`
   - expires_at ← `date_end`
   - salary_min/max ← `payrate_min/max` (`8.0M` → 8,000,000)
   - remote_type ← `remote`
   - employment_type ← `emptype`
   - url ← `job_detail_url`
   - source_job_id ← `sf_jo_number`
   - description_text ← `summary`
5. Paginate until all jobs on a page are older than the cutoff.
6. Fetch detail pages only if the summary is missing or too short, capped at 10.
7. Normalize and classify.

## Fixtures

- `tests/fixtures/robert_half_list.html`
- `tests/fixtures/robert_half_detail.html`

## Tests

- Parses the escaped JSON payload.
- Parses `date_posted` with timezone.
- Parses salary `8.0M` and `14.0M`.
- Parses remote and employment type.
- Derives `location_scope`; does not mark non-Japan roles as Japan-eligible.
- Stops pagination at the cutoff.
- Handles a page with no jobs.

## Acceptance

- [ ] Fixture tests pass.
- [ ] Live smoke test works.
- [ ] No more than 10 detail requests.
- [ ] No login/cookies.
- [ ] Docs updated if the page structure differs.

## Notes

- Do not rely on the search API until its request shape is documented.
- Do not scrape `/jp/en/search?param=*`.
- The agency is not the hiring company; label it clearly in the UI.

# Task 05 — TokyoDev Scraper

## Goal

Implement `app/scrapers/tokyo_dev.py` for the Security category, with the Atom
feed as an optional discovery fallback.

## Read first

- `docs/sources.md` (section 3)
- `docs/scrapers.md` (section 4.3)
- `docs/data-model.md` (normalization rules)

## Source facts

- Listing: `https://www.tokyodev.com/jobs/security`
- About 9 jobs.
- Detail pages contain JSON-LD `JobPosting` with `datePosted`.
- Atom feed: `https://www.tokyodev.com/jobs/atom.xml` (20 latest entries).
- Some jobs are older but show "Verified as active <date>".
- robots allows `/` and disallows `/c/`, `/contest`, `/frames/`.

## Implementation

1. Fetch the Security category page.
2. Extract unique `/companies/<company>/jobs/<slug>` links.
3. Fetch up to 15 detail pages.
4. Parse the first JSON-LD `JobPosting`.
5. Map fields:
   - title, description, datePosted
   - hiringOrganization.name → company
   - jobLocation → location
   - baseSalary → salary
   - employmentType → employment type
   - jobLocationType / text → remote type
6. Optionally parse "Verified as active <date>" into `source_updated_at`.
7. Optional fallback: fetch the Atom feed, parse entries, and use recent links
   only as discovery. Detail JSON-LD remains authoritative.
8. Normalize and classify with a source prior.

## Fixtures

- `tests/fixtures/tokyo_dev_list.html`
- `tests/fixtures/tokyo_dev_detail.html`
- `tests/fixtures/tokyo_dev_atom.xml`

## Tests

- Extracts unique job links.
- Parses datePosted from detail.
- Parses Atom entries (`published`, `updated`, `link`, `title`, `summary`).
- Handles a job with no salary.
- Handles remote.
- Derives `location_scope` (Japan remote vs. international remote).
- Does not confuse `source_updated_at` with `posted_at`.

## Acceptance

- [ ] Fixture tests pass.
- [ ] Live smoke test works.
- [ ] No more than 15 detail requests.
- [ ] No login/cookies.
- [ ] Docs updated if the page structure differs.

## Notes

- The category page has no dates; detail pages are required.
- Do not treat "verified active" as a new posting.
- Keep the Atom parser small and well-tested.

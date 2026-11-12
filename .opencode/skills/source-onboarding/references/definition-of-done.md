# Definition of done

Close each phase only when every box is ticked.

## Research

- [ ] Source is not already implemented.
- [ ] Listing page loads without a login.
- [ ] Detail page loads without a login.
- [ ] `robots.txt` checked; listing and detail paths allowed for
      `User-agent: *`; evidence recorded.
- [ ] Terms notes recorded (personal-use or scraping restrictions).
- [ ] Anti-bot behaviour recorded (none / 403 / Cloudflare / other).
- [ ] Listing and detail URL patterns recorded, including pagination.
- [ ] Date field identified, with granularity (date-only vs. timestamp) and
      timezone.
- [ ] Salary, remote, employment type, Japanese level, and visa/overseas
      fields checked for availability.
- [ ] Approximate volume of security roles recorded.
- [ ] Verdict written: `implement`, `defer`, or `reject`.

## Brief

- [ ] `docs/sources.md` section written with URLs, date semantics, language(s),
      visa/overseas wording, remote wording, quirks, health expectation.
- [ ] `docs/tasks/<NN>-source-<source>.md` written with goal, inputs,
      acceptance criteria, files to touch.
- [ ] Source matrix updated.

## Implementation

- [ ] `app/scrapers/<source>.py` subclasses `BaseScraper`.
- [ ] Shared `HttpClient` used; no ad-hoc `httpx` client.
- [ ] Listing + detail fixtures committed under `tests/fixtures/`.
- [ ] Parser test file `tests/test_<source>.py` added.
- [ ] At least one edge case covered (missing salary, Japanese title, remote,
      expired, missing date).
- [ ] `source`, `source_job_id`, canonical `url`, `title` always set.
- [ ] `salary_text` always set when the source publishes it; `salary_min`/
      `salary_max` only when parseable.
- [ ] `posted_at` set when the source publishes it; `posted_at_raw` kept.
- [ ] `role_category`, `language`, `location_scope`, `overseas_eligible` set
      only from explicit evidence.
- [ ] Non-technical and `international_remote` rows are returned, not dropped.
- [ ] One bad job is skipped and logged, not fatal.
- [ ] `is_security_category` set only when the listing is a security category.
- [ ] `max_detail_requests` set to a sane cap.
- [ ] Tests never touch the network.

## Integration

- [ ] `enable_<source>` added to `app/config.py` and `.env.example`.
- [ ] Scraper registered in `app/scrapers/registry.py`.
- [ ] `docs/scrapers.md` per-source section added.
- [ ] `README.md` source list updated.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run pytest` passes.
- [ ] Live smoke returns sane titles, companies, dates, and URLs.
- [ ] Smoke did not write to the database.

## Review

- [ ] `qa-reviewer` ran over the diff.
- [ ] All Blocker and High findings fixed.
- [ ] Suite re-run green after fixes.
- [ ] No secrets, cookies, tokens, or personal data in the diff.

## Report

- [ ] Source ID, robots evidence, files changed, fixtures added.
- [ ] Test command and result.
- [ ] Live smoke result.
- [ ] Open risks and anything intentionally left out.

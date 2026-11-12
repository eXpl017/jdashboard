# AGENTS.md — `app/scrapers/`

One module per source. A scraper fetches one site, parses it, and returns
`ScrapedJob` objects. **It never touches the database and never writes files.**

## Contract

```python
class MySourceScraper(BaseScraper):
    source_id = "my_source"          # snake_case id used in the DB and the API
    source_name = "My Source"        # display name
    listing_url = "https://…/jobs"   # public listing page
    max_detail_requests = 40        # hard cap on detail page fetches
    is_security_category = False    # True only if the listing IS a security category

    async def scrape(self, since: datetime) -> ScrapeResult:
        ...
```

- `since` is **timezone-aware UTC**. Compare with `job.posted_at` only after
  converting both to the same awareness.
- Return every listing the source shows; the refresh service filters by the
  window and the window itself is applied by the caller.
- Use `self.http` (`services/http.py`) for every request: it enforces
  robots.txt, the per-host delay, retries, and the detail-request cap.
- Parse JSON-LD first when the page has it; fall back to stable HTML
  selectors. Keep selectors and labels in module-level constants.
- One bad job must not fail the source: catch, log a warning with the URL,
  and continue.
- A source-wide failure raises `ScraperError` (or `RobotsDisallowed` /
  `RateLimited` / `SourceChanged`) with a short, user-safe message.

## Field rules

- Always set `source`, `url` (canonical, no tracking params), `title`,
  `source_job_id` when the source has a stable id.
- `salary_text` whenever the source publishes it; `salary_min`/`salary_max`
  only when confidently parseable. Never invent either.
- `posted_at` from the source's own date; keep `posted_at_raw` and
  `source_updated_at` separate.
- Set `role_category`, `language`, `location_scope`, `overseas_eligible`,
  `japanese_level`, `visa_sponsorship` **only** from explicit source text.
  Otherwise leave them `None` and let `services/classify.py` and
  `services/normalize.py` decide.
- Store non-technical and `international_remote` rows. The UI filters them.

## Registering a new source

1. Implement `app/scrapers/<source>.py`.
2. Add the class to `SCRAPER_CLASSES` in `registry.py`
   (`SOURCE_NAMES` is derived from that mapping).
3. Add `enable_<source>` to `app/config.py` and `ENABLE_<SOURCE>` to
   `.env.example`.
4. Save listing/detail fixtures in `tests/fixtures/` and add
   `tests/test_<source>.py`.
5. Update `docs/sources.md` and `docs/scrapers.md`.

The `source-integrator` subagent does steps 2–5 for you; the
`source-onboarding` skill and `/add-source` command run the whole flow.

## Hard rules

- No login, CAPTCHA, Cloudflare, paywall, or rate-limit bypass.
- Do not fetch apply, login, member, or company-profile pages.
- No scheduler, no automatic refresh, no requests outside a scrape call.
- Keep the request rate at the configured limit (default 1 req/s per host).

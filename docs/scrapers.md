# Scraper Design

## 1. Goals

- One module per source, with a shared contract.
- Parsers are testable without live network access.
- A broken source is isolated and visible, never fatal to the whole refresh.
- Scraping is polite: robots-aware, rate-limited, retried with backoff, and
  clearly identified.

## 2. Scraper contract

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

@dataclass(slots=True)
class ScrapedJob:
    source: str
    url: str
    title: str
    source_job_id: str | None = None
    company: str | None = None
    location: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "JPY"
    salary_text: str | None = None
    description_text: str | None = None
    description_html: str | None = None
    posted_at: datetime | None = None
    posted_at_raw: str | None = None
    source_updated_at: datetime | None = None
    expires_at: datetime | None = None
    japanese_level: str | None = None
    visa_sponsorship: str | None = None
    overseas_eligible: bool | None = None
    role_category: str | None = None      # filled by the classifier when omitted
    language: str | None = None           # filled by the normalizer when omitted
    location_scope: str | None = None     # filled from remote_type + location
    security_tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScrapeResult:
    source: str
    jobs: list[ScrapedJob]
    found: int
    skipped: int
    errors: list[str]


class BaseScraper:
    source_id: ClassVar[str]
    source_name: ClassVar[str]
    listing_url: ClassVar[str]
    max_detail_requests: ClassVar[int] = 40

    def __init__(self, http: "HttpClient", settings: "Settings") -> None:
        self.http = http
        self.settings = settings

    async def scrape(self, since: datetime) -> ScrapeResult:
        """Fetch, parse, normalize, and return jobs. Never writes to the DB."""
        raise NotImplementedError
```

Rules:

- Scrapers do **not** touch the database. They return `ScrapedJob` objects.
- Scrapers do **not** decide the final security score; they may set tags, but
  the shared classifier computes the score, `role_category`, and `language`.
- Scrapers may set `language`, `role_category`, `location_scope`, and
  `overseas_eligible` when the source states them explicitly (e.g. Daijob's
  Japanese-level field). Otherwise they leave them `None` and the shared
  normalizer/classifier fills them.
- Scrapers must keep the source URL stable and canonical.
- Scrapers must not fetch apply pages, login pages, member pages, or company
  profile pages.
- Scrapers should log a short warning for a single bad job and continue.
- A source-wide failure raises `ScraperError` with a user-safe message.

## 3. Shared utilities

### `services/http.py`

- `get_text(url) -> str`
- `get_json(url) -> Any`
- Robots check per host.
- Per-host delay and concurrency semaphore.
- Retry on timeout, 429, and 5xx.
- Raise `RobotsDisallowed`, `RateLimited`, `SourceChanged`.

### `services/dates.py`

- `parse_iso_datetime(value, default_tz=JST) -> datetime | None`
- `parse_date_only(value, tz=JST) -> datetime | None`
- `parse_japanese_date(value) -> datetime | None`
- `to_utc(value) -> datetime`
- `days_ago(days, tz=JST) -> datetime`

### `services/normalize.py`

- `strip_html(html) -> str`
- `normalize_whitespace(text) -> str`
- `normalize_width(text) -> str` (full-width → half-width for matching)
- `parse_salary(text) -> SalaryParts`
- `detect_remote(text) -> str`
- `detect_employment_type(text) -> str`
- `detect_language(title, description) -> str` (`en` | `ja` | `bilingual` | `unknown`)
- `detect_location_scope(location, remote_type, description) -> str`
- `detect_overseas_eligible(text) -> bool | None`
- `canonical_url(url, allowed_query_params=()) -> str`
- `fingerprint(source, url) -> str`

### `services/classify.py`

- `classify(title, description, source_tags, source_is_security_category) -> Classification`
- Returns `score`, `tags`, `role_category`, `language`, and a short `reason`.
- Uses normalized lowercase text and both English and Japanese keyword sets.
- `role_category` is title-first (see `docs/data-model.md` §5). Non-technical
  families are still returned so the row can be stored and filtered later.
- `language` counts Japanese characters versus Latin words; it never translates.
- The UI hides `grc`, `consulting`, `sales`, and `management` by default, so the
  classifier must be conservative about labeling a genuinely technical role as
  one of those.

### JSON-LD helper

```python
def extract_job_posting_jsonld(html: str) -> dict | None:
    """Return the first schema.org JobPosting object from <script type=application/ld+json>."""
```

Handle:

- A single object.
- A list of objects.
- `@graph` arrays.
- HTML entities and escaped Unicode.

## 4. Per-source implementation notes

### 4.1 Michael Page Japan (`michael_page.py`)

**Flow**

1. `GET https://www.michaelpage.co.jp/en/jobs/it-security`
2. Extract unique `href` values containing `/job-detail/`.
3. Normalize relative URLs to absolute.
4. Fetch up to `max_detail_requests` detail pages.
5. Parse JSON-LD `JobPosting`.
6. Map:
   - `title` ← `title`
   - `description_html` ← `description`
   - `description_text` ← `strip_html(description)`
   - `posted_at` ← `datePosted` (date only, JST midnight)
   - `company` ← `hiringOrganization.name` (agency; note in UI)
   - `employment_type` ← `employmentType`
   - `salary_min/max` ← `baseSalary.value.minValue/maxValue`
   - `salary_text` ← formatted min/max
   - `location` ← `jobLocation.address.addressLocality` + region
   - `remote_type` ← `jobLocationType == "TELECOMMUTE"` → remote; else detect
   - `source_job_id` ← the `jn-...` reference from the URL
   - `language` ← detect from the listing text (Michael Page publishes EN and JA
     versions; do not assume English)
   - `overseas_eligible` ← only if the description says so; many Michael Page
     roles expect Japan residency even when the page is in English
7. Classify. `location_scope` is derived from `location` + `remote_type`.

**Gotchas**

- The category page may include non-security jobs; keep the classifier.
- `datePosted` has no time; use JST midnight.
- The client company may be confidential; do not invent it.

### 4.2 JapanDev (`japan_dev.py`)

**Flow**

1. `GET https://japan-dev.com/security-jobs-in-japan`
2. Extract unique `href` values matching `/jobs/<company>/<slug>`.
3. Fetch up to `max_detail_requests` detail pages.
4. Parse JSON-LD `JobPosting`.
5. Map:
   - `title`, `description`, `datePosted`, `validThrough`
   - `company` ← `hiringOrganization.name`
   - `location` ← `jobLocation.address.addressLocality`
   - `salary` ← `baseSalary`
   - `employment_type` ← `employmentType`
   - `language` ← mostly `en`; still detect, because some listings include
     Japanese text
6. Classify with a source prior (security landing page). JapanDev is
   English-first, but do not force `language=en` if the body is Japanese.

**Gotchas**

- The page includes related/non-security roles; classify.
- The landing page may not paginate; if it grows, inspect the Nuxt payload.
- `datePosted` is date-only.

### 4.3 TokyoDev (`tokyo_dev.py`)

**Flow**

1. `GET https://www.tokyodev.com/jobs/security`
2. Extract unique `href` values matching `/companies/<company>/jobs/<slug>`.
3. Fetch up to `max_detail_requests` detail pages.
4. Parse JSON-LD `JobPosting`.
5. Map:
   - `title`, `description`, `datePosted`
   - `company` ← `hiringOrganization.name`
   - `location` ← `jobLocation.address.addressLocality`
   - `salary` ← `baseSalary`
   - `employment_type` ← `employmentType`
   - `remote_type` ← `jobLocationType` or text
   - `language` ← mostly `en`; detect, since TokyoDev occasionally lists
     Japanese-required roles
6. Optionally parse "Verified as active <date>" into `source_updated_at`.
7. Classify with a source prior. Derive `location_scope` from the location and
   remote text; treat "remote in Japan" as `japan_remote`, not
   `international_remote`.

**Fallback**

- `GET https://www.tokyodev.com/jobs/atom.xml`
- Parse `<entry>` items for `title`, `published`, `updated`, `link`, `summary`.
- Use the feed only to discover recent job URLs; detail JSON-LD is authoritative.

**Gotchas**

- The category page has no dates; detail pages are required.
- Some jobs are older but verified active; do not confuse `datePosted` with
  `source_updated_at`.

### 4.4 Daijob (`daijob.py`)

**Flow**

1. `GET https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0`
2. Follow the redirect to the `search_result` URL.
3. Extract unique `/en/jobs/detail/<id>` links.
4. Fetch page 2 of the category and the first page of two curated keyword
   searches (`サイバーセキュリティ`, `情報セキュリティ`).
5. Deduplicate detail IDs and fetch detail pages (max 40).
6. Parse:
   - `Updated YYYY-MM-DD` → `source_updated_at`
   - `Activated YYYY-MM-DD` → `posted_at`
   - company name, job type, industry, location, salary, Japanese level,
     description
   - `japanese_level` ← the source's required-Japanese field (e.g. `Business`,
     `Fluent`, `Not required`)
   - `language` ← often `bilingual` or `ja`; detect from the text, do not
     assume the `/en/` URL means English
   - `overseas_eligible` ← set only when the listing says overseas applications
     are accepted
7. Classify with strict title/description rules. Daijob carries many
   Japanese-language and non-engineering roles, so `role_category` and
   `language` matter more here than on the English-first sources.

**Keyword searches (optional, 2–3 per run)**

```text
サイバーセキュリティ
情報セキュリティ
SOC
CSIRT
脆弱性
ペネトレーションテスト
GRC
IAM
インシデントレスポンス
```

**Gotchas**

- The `kw=security` search is broad (242 results); do not fetch all details.
  A live `サイバーセキュリティ` search returned 76 results. The category plus
  two keyword searches produced 60 unique detail links, so the 40-detail cap
  matters: fetch the category first, then keyword candidates.
- Prefer the Security System SE category.
- Do not scrape `/company/`, `/members/`, or apply pages.
- Detail pages expose a schema.org `JobPosting` JSON-LD block **and** stable
  HTML labels. Use the `Activated`/`Updated` labels as the authoritative dates
  and use the JSON-LD only for enrichment (identifier, salary, location). Keep
  the HTML selectors as the primary contract and cover both paths in fixtures.

### 4.5 Robert Half Japan (`robert_half.py`)

**Flow**

1. `GET https://www.roberthalf.com/jp/en/jobs`
2. Extract the embedded JSON:
   `aemSettings.rh_job_search.initialResults = JSON.parse('...')`.
3. Parse the JSON string (unescape `\x22`, `\u002D`, etc.).
4. Iterate jobs; map:
   - `title` ← `functional_role` or the page title
   - `company` ← "Robert Half Japan" (agency) or parsed client
   - `location` ← `city` + `country`
   - `posted_at` ← `date_posted`
   - `expires_at` ← `date_end`
   - `salary_min/max` ← `payrate_min/max` (convert `8.0M` → 8,000,000)
   - `remote_type` ← `remote`
   - `employment_type` ← `emptype`
   - `url` ← `job_detail_url`
   - `source_job_id` ← `sf_jo_number`
   - `description_text` ← `summary` or detail page
   - `language` ← detect; the `/jp/en/` listing is mostly English but the
     detail text can be Japanese
   - `overseas_eligible` ← only from explicit text
5. If the summary is too short, fetch the detail page.
6. Paginate with `?pagenumber=2`, stopping when all jobs on a page are older
   than the cutoff.
7. Classify. Derive `location_scope` from `city`/`country` + `remote`; a
   non-Japan city with no Japan eligibility is `international_remote` and is
   hidden by default.

**Fallback**

- The search API endpoint `https://prd-dr.jps.api.roberthalfonline.com/search`
  was observed in the page source. Do not rely on it until its request shape is
  documented and tested.

**Gotchas**

- The `keywords` query parameter did not reliably filter during planning.
- The embedded JSON is escaped; write a helper and test it with a fixture.
- Salary values like `8.0M` need a parser.

## 5. Fixtures

For each source, save at least:

- One listing page fixture.
- One detail page fixture.
- One edge-case fixture (missing salary, Japanese title, remote, expired).

Fixtures live in `tests/fixtures/` and are committed. Keep them small; strip
unnecessary scripts and images if needed, but preserve the structures the parser
depends on.

Suggested naming:

```text
tests/fixtures/michael_page_list.html
tests/fixtures/michael_page_detail.html
tests/fixtures/japan_dev_list.html
tests/fixtures/japan_dev_detail.html
tests/fixtures/tokyo_dev_list.html
tests/fixtures/tokyo_dev_detail.html
tests/fixtures/tokyo_dev_atom.xml
tests/fixtures/daijob_list.html
tests/fixtures/daijob_detail.html
tests/fixtures/robert_half_list.html
tests/fixtures/robert_half_detail.html
```

## 6. Parser tests

For each source:

- `test_<source>_extracts_expected_number_of_candidates`
- `test_<source>_parses_title_company_location`
- `test_<source>_parses_posted_at`
- `test_<source>_parses_salary`
- `test_<source>_detects_language`
- `test_<source>_assigns_role_category`
- `test_<source>_derives_location_scope`
- `test_<source>_handles_missing_optional_fields`
- `test_<source>_ignores_non_job_links`

Use `respx` to mock HTTP responses for end-to-end scraper tests, or call the
parser functions directly with fixture text. Prefer direct parser tests for
speed and clarity.

## 7. Live smoke test

A manual developer command, not part of CI:

```bash
python scripts/inspect_source.py michael_page --limit 3
```

It should:

- Fetch live data.
- Print the parsed jobs (title, company, posted_at, URL).
- Never write to the database.
- Respect the same rate limits and robots rules.

## 8. Adding a new source — checklist

1. Research the source: robots.txt, terms, listing URL, detail URL, date field,
   login/anti-bot behavior.
2. Write a source brief in `docs/sources.md` (or `docs/research/<source>.md`).
3. Add a source ID and enable flag in config.
4. Save listing and detail fixtures.
5. Implement `app/scrapers/<source>.py` using `BaseScraper`.
6. Add the scraper to `registry.py`.
7. Add parser tests.
8. Add normalization/classification cases if the source has unique fields.
9. Run `ruff check` and `pytest`.
10. Run a live smoke test with `--limit 3`.
11. Update `docs/sources.md` and `README.md`.
12. Confirm no login, no CAPTCHA bypass, and robots compliance.

## 9. Common failure modes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| 0 candidates | Listing selector changed | Inspect fixture vs live HTML |
| 403 | Anti-bot block | Stop; do not bypass; document and disable |
| 429 | Too many requests | Increase delay, reduce concurrency |
| Empty JSON-LD | Page layout changed | Add a fallback HTML parser |
| Wrong dates | Timezone/date-only parsing | Add fixture and unit test |
| Duplicate rows | Fingerprint unstable | Canonicalize URL, use source ID |
| Missing salary | Source does not publish it | Keep `salary_text` NULL, do not invent |
| Japanese text garbled | Encoding issue | Ensure UTF-8 and `response.encoding` |

# Source Research

This document records what was checked during planning, what the scraper should
expect, and what was deliberately excluded.

> All checks below were made with a plain HTTP client and a normal browser-like
> `User-Agent`. No login, cookies, CAPTCHA solving, or Cloudflare bypass was used.
> Re-check `robots.txt` and site terms before implementation and periodically
> afterwards.

## Launch source matrix

| Source | ID | Listing URL | Detail data | Posted date | Approx. volume |
| --- | --- | --- | --- | --- | --- |
| Michael Page Japan | `michael_page` | `https://www.michaelpage.co.jp/en/jobs/it-security` | JSON-LD `JobPosting` | `datePosted` | 22 |
| JapanDev | `japan_dev` | `https://japan-dev.com/security-jobs-in-japan` | JSON-LD `JobPosting` | `datePosted` | 37 links, ~7 security-titled |
| TokyoDev | `tokyo_dev` | `https://www.tokyodev.com/jobs/security` | JSON-LD `JobPosting`; Atom feed | `datePosted` | 9 |
| Daijob | `daijob` | `https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0` | HTML detail page | `Activated` / `Updated` | 22 category, 242 keyword |
| Robert Half Japan | `robert_half` | `https://www.roberthalf.com/jp/en/jobs` | Embedded JSON + detail page | `date_posted` | ~15 per page |

All five:

- Return public data without a login.
- Have listing pages that are not disallowed for a generic crawler.
- Can be scraped with plain HTTP; no headless browser is required for v1.
- Should be fetched at roughly 1 request per second per host.

---

## 1. Michael Page Japan

**Why it is a launch source:** It has a dedicated `/en/jobs/it-security`
category with real cybersecurity roles (security engineer, CSIRT, SOC,
threat intelligence, GRC, CISO, security consultant).

**Listing**

```text
https://www.michaelpage.co.jp/en/jobs/it-security
```

- Server-rendered HTML.
- About 22 unique `/job-detail/...` links on the page.
- No pagination links were observed for this category. If more pages appear
  later, inspect the category's pager before assuming one page.
- The general keyword search (`?keywords=security`) did **not** reliably filter
  results during planning. Use the category page, not the keyword search.

**Detail page**

```text
https://www.michaelpage.co.jp/job-detail/<slug>/ref/jn-<ref>?lang=en
https://www.michaelpage.co.jp/en/job-detail/<slug>/ref/jn-<ref>
```

- Contains a JSON-LD `JobPosting` block.
- Useful fields observed: `title`, `description`, `datePosted`,
  `hiringOrganization`, `employmentType`, `industry`, `baseSalary`,
  `jobLocation`, `jobLocationType`, `url`.
- `datePosted` is a date (for example `2026-10-19`), not a full timestamp.
  Treat it as the start of that day in Asia/Tokyo, with `date_confidence=high`.
- `hiringOrganization.name` is **Michael Page**, the agency. The actual client
  may be confidential or described in the "About Our Client" section. Store the
  agency as the source company; optionally extract a client name later.

**robots.txt notes**

- Generic `User-agent: *` rules allow normal content.
- Disallowed paths include `/search/`, `/job-apply/`, `/job-apply-external/`,
  `/user/login`, and some query-parameter filters.
- `/en/jobs/it-security` and `/job-detail/` were allowed in the checked file.
- Do not fetch apply pages or login pages.

**Scraper approach**

1. Fetch the IT Security category page.
2. Extract unique job-detail URLs.
3. Fetch each detail page (rate-limited, max ~25 requests).
4. Parse JSON-LD.
5. Normalize salary, location, remote type, and employment type.
6. Filter by `datePosted >= since` unless "include active older" is enabled.

---

## 2. JapanDev

**Why it is a launch source:** English-friendly tech jobs in Japan, with a
curated Security landing page and structured JSON-LD on every job detail.

**Listing**

```text
https://japan-dev.com/security-jobs-in-japan
```

- Nuxt server-rendered HTML.
- About 37 unique `/jobs/<company>/<slug>` links; roughly 7 are explicitly
  security-titled. The rest are related roles from the same companies.
- The page includes filters for Japanese level, remote work, and visa support.
  These are not required for v1.
- No reliable pagination was observed. For a 3-day window, the first page is
  sufficient; if the page grows, inspect the Nuxt payload or add category
  pagination.

**Detail page**

```text
https://japan-dev.com/jobs/<company>/<slug>
```

- Contains a JSON-LD `JobPosting` block.
- Useful fields observed: `title`, `description`, `datePosted`,
  `validThrough`, `hiringOrganization`, `jobLocation`, `baseSalary`,
  `employmentType`.
- `datePosted` is a date (`YYYY-MM-DD`). Normalize to the start of that day in
  Asia/Tokyo.
- `hiringOrganization.name` is the actual employer.
- `validThrough` can populate `expires_at`.

**robots.txt notes**

- `User-agent: *` allows the site except two blog/salary-guide resources.
- A sitemap is published at `https://japan-dev.com/sitemap.xml`.

**Scraper approach**

1. Fetch the security landing page.
2. Extract unique job-detail URLs.
3. Fetch each detail page (max ~40 requests, 1 req/sec).
4. Parse JSON-LD.
5. Use the landing page as a security prior; still classify title/description
   so clearly unrelated roles can be demoted.
6. Filter by `datePosted`.

---

## 3. TokyoDev

**Why it is a launch source:** English-friendly tech jobs in Japan, with a
dedicated Security category and clean JSON-LD on job detail pages.

**Listing**

```text
https://www.tokyodev.com/jobs/security
```

- Server-rendered HTML.
- About 9 jobs in the Security category.
- The listing itself does not expose posting dates; detail pages do.
- There is also an Atom feed: `https://www.tokyodev.com/jobs/atom.xml`.
  It contains the 20 most recent jobs with `published`, `updated`, `link`,
  `title`, `summary`, and `author`.

**Detail page**

```text
https://www.tokyodev.com/companies/<company>/jobs/<slug>
```

- Contains a JSON-LD `JobPosting` block.
- Useful fields observed: `title`, `description`, `datePosted`,
  `hiringOrganization`, `jobLocation`, `employmentType`, `baseSalary`,
  `jobLocationType`, `applicantLocationRequirements`.
- Some listings are older but show "Verified as active <date>" on the page.
  If that text is parseable, store it as `source_updated_at`; do not treat it as
  `posted_at`.

**robots.txt notes**

- `User-agent: *` allows `/` and disallows `/c/`, `/contest`, and `/frames/`.
- The job category and detail pages were allowed.

**Scraper approach**

1. Fetch the Security category page.
2. Extract unique job-detail URLs.
3. Fetch each detail page (max ~12 requests).
4. Parse JSON-LD.
5. Optionally use the Atom feed as a discovery fallback for recent updates.
6. Filter by `datePosted`; expose `source_updated_at` separately.

---

## 4. Daijob

**Why it is a launch source:** Large bilingual job board with an explicit
Security System SE job type and a large pool of IT/security listings.

**Listing**

```text
https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0
```

- Redirects to:
  `https://www.daijob.com/en/jobs/search_result?job_types[]=503&job_search_form_hidden=1`
- `js_jt[]=503` is the **Security System SE** job type.
- About 22 jobs in that category, 20 per page.
- Keyword search uses `kw` and redirects to `search_result?...&keywords=...`.
  A search for `security` returned 242 broad results, so keyword search alone is
  noisy. Prefer the category plus curated Japanese keywords.
- Pagination uses `pg=0`, `pg=1`, ... or the `page` links in the result page.

**Detail page**

```text
https://www.daijob.com/en/jobs/detail/<id>
```

- Contains `Updated YYYY-MM-DD` and `Activated YYYY-MM-DD`.
  - `Activated` = first published date → `posted_at`.
  - `Updated` = last edited date → `source_updated_at`.
- Also contains company name, job type, industry, location, salary, Japanese
  level, and the full description.

**robots.txt notes**

- The generic rules allow `/jobs/search_result` (the old disallow is commented
  out in the file that was checked).
- Disallowed areas include `/company/`, `/members/`, `/dj/ja/biz*`,
  `/dj/ja/overseas`, `/uploads`, and several campaign pages.
- Do **not** scrape company profiles, member pages, or apply flows.

**Scraper approach**

1. Fetch the Security System SE category pages (`pg=0`, then `pg=1` if needed).
2. Optionally run 2–3 curated keyword searches:
   `サイバーセキュリティ`, `情報セキュリティ`, `SOC`, `CSIRT`, `脆弱性`,
   `ペネトレーションテスト`, `GRC`, `IAM`, `インシデントレスポンス`.
3. Deduplicate detail IDs.
4. Fetch detail pages only for candidates (max ~40).
5. Parse `Activated`/`Updated`, company, location, salary, Japanese level,
   description.
6. Filter by `posted_at`; keep `source_updated_at` for display.

---

## 5. Robert Half Japan

**Why it is a launch source:** A major recruitment agency with daily IT and
security roles, structured posting dates, and public search pages.

**Listing**

```text
https://www.roberthalf.com/jp/en/jobs
https://www.roberthalf.com/jp/en/jobs?pagenumber=2
```

- Server-rendered HTML with an embedded JSON payload:
  `aemSettings.rh_job_search.initialResults = JSON.parse('...')`.
- The payload contains fields such as `date_posted`, `date_end`, `functional_role`,
  `city`, `country`, `payrate_min`, `payrate_max`, `salary_currency`, `remote`,
  `emptype`, `job_detail_url`, `summary`, and `industry`.
- A public search endpoint was also observed:
  `https://prd-dr.jps.api.roberthalfonline.com/search`.
  The embedded payload is sufficient for v1; the endpoint is a fallback.
- The `keywords` query parameter did not reliably filter during planning.
  Fetch the latest pages and filter by title/description, or use the search API.

**Detail page**

```text
https://www.roberthalf.com/jp/en/job/<city>/<slug>/<reference>-jpen
```

- Contains the full description and structured job metadata.
- `date_posted` is a full ISO 8601 timestamp with timezone (`Z`).

**robots.txt notes**

- Generic rules allow normal content.
- `/jp/en/search?param=*` and `/jp/en/c/*` are disallowed.
- `/jp/en/jobs` was allowed in the checked file.

**Scraper approach**

1. Fetch `/jp/en/jobs`, then subsequent `?pagenumber=N` pages.
2. Parse the embedded JSON payload (preferred) or the search API.
3. Stop paging when all jobs on a page are older than the cutoff.
4. Filter by security keywords.
5. Fetch detail pages only if the description is missing or too short.
6. Filter by `date_posted`.

---

## Excluded or deferred sources

### LinkedIn Jobs

- **Status:** excluded.
- **Why:** Login wall and terms of service. A guest search endpoint sometimes
  returns public job cards without login, but it is unstable and using it
  violates LinkedIn's terms.
- **No-login workaround:** none that is both reliable and compliant.
- **If you need it:** use LinkedIn's official partner/talent APIs, or provide a
  logged-in `li_at` session cookie and `JSESSIONID` in `.env`. The scraper would
  then use them with very low request rates. This is not planned for v1.

### Indeed Japan

- **Status:** excluded.
- **Why:** Anti-bot protection and terms of service. There is no public job
  search API for personal use.
- **No-login workaround:** none reliable.
- **If you need it:** apply to the Indeed Publisher API (approval required) or
  provide an authenticated browser session/cookies. Not planned for v1.

### GaijinPot Jobs

- **Status:** deferred.
- **Why:** `jobs.gaijinpot.com` returned `403 Access Denied` to a plain HTTP
  client (AWS WAF-style block). The main `gaijinpot.com` site loads, but the job
  board is on the blocked subdomain.
- **No-login workaround:** a real browser session (Playwright) and possibly a
  residential IP may work. No login is needed for public listings.
- **If you need it:** add a Playwright-based scraper in phase 6, or provide
  browser cookies. Not planned for v1.

### CareerCross

- **Status:** excluded.
- **Why:** Cloudflare "Just a moment..." challenge on the checked request.
- **No-login workaround:** browser automation or a valid `cf_clearance` cookie
  tied to the same IP and User-Agent.
- **If you need it:** use Playwright with a persistent profile, or provide
  cookies. Not planned for v1.

### Glassdoor

- **Status:** excluded.
- **Why:** Cloudflare and login walls.
- **No-login workaround:** none reliable/compliant.

### doda / Recruit / other large Japanese boards

- **Status:** excluded.
- **Why:** Anti-bot protection and terms-of-service restrictions.
- **No-login workaround:** not reliable without a browser session or official
  partnership.

### JobsInJapan

- **Status:** optional 6th source.
- **Why deferred:** It is scrapeable (server-rendered, `dateTime` attributes,
  `/jobs/?sort=latest`), but its IT category has fewer cybersecurity roles than
  the five launch sources.
- **robots note:** Generic `User-agent: *` allows `/jobs/`, but the file has
  special rules disallowing AI crawlers from `/jobs/`. Use a normal,
  rate-limited personal scraper UA and be conservative; or skip this source if
  you want to avoid the ambiguity.

### Wantedly

- **Status:** optional 6th source.
- **Why deferred:** Scrapeable via `__NEXT_DATA__` and public project pages, but
  it is project-based hiring and mostly Japanese-language startup roles.
- **robots note:** `/projects` is not disallowed; login/member paths are.

---

## Source health expectations

| Source | Expected result on a normal day | If it returns 0 |
| --- | --- | --- |
| Michael Page | Several security roles; some older than 3 days | Category page changed or all roles older than window |
| JapanDev | A few security roles; dates may be older | Landing page changed or no new security roles |
| TokyoDev | 0–2 new security roles; category has ~9 active | No new security posts in window |
| Daijob | A few new security roles; category has ~22 | Category ID changed or search redirect changed |
| Robert Half | A few new IT/security roles per page | Payload key changed or keyword filter too strict |

A source returning 0 jobs is not automatically an error. The UI should
distinguish "success, 0 new" from "failed".

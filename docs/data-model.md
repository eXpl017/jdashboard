# Data Model

## 1. Principles

- One row per **source listing** in v1. The same job posted on two sources is
  two rows, each with its own source badge. Cross-source grouping is a phase 6
  enhancement.
- Store timestamps in UTC as ISO 8601 strings (`YYYY-MM-DDTHH:MM:SSZ`).
- Store the source's raw date string too, so parsing mistakes are diagnosable.
- Store the source URL; it is the user's path back to the original listing.
- Keep the schema small and explicit. Avoid premature normalization.

## 2. Tables

### `jobs`

```sql
CREATE TABLE jobs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint         TEXT    NOT NULL UNIQUE,
    source              TEXT    NOT NULL,
    source_job_id       TEXT,
    url                 TEXT    NOT NULL,
    title               TEXT    NOT NULL,
    company             TEXT,
    location            TEXT,
    remote_type         TEXT,       -- onsite | hybrid | remote | unknown
    employment_type     TEXT,       -- full_time | contract | part_time | internship | unknown
    salary_min          INTEGER,    -- annual JPY when parseable
    salary_max          INTEGER,
    salary_currency     TEXT    NOT NULL DEFAULT 'JPY',
    salary_text         TEXT,       -- original salary string
    description_text    TEXT,
    description_html    TEXT,
    posted_at           TEXT,       -- ISO 8601 UTC, source's original post date
    posted_at_raw       TEXT,       -- original string from the source
    source_updated_at   TEXT,       -- ISO 8601 UTC, if the source exposes it
    expires_at          TEXT,       -- ISO 8601 UTC, if the source exposes it
    first_seen_at       TEXT    NOT NULL,
    last_seen_at        TEXT    NOT NULL,
    is_active           INTEGER NOT NULL DEFAULT 1,
    security_score      REAL    NOT NULL DEFAULT 0,
    security_tags       TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    role_category       TEXT    NOT NULL DEFAULT 'other', -- engineering | operations | grc | consulting | sales | management | other
    language            TEXT    NOT NULL DEFAULT 'unknown', -- en | ja | bilingual | unknown
    location_scope      TEXT    NOT NULL DEFAULT 'unknown', -- japan_onsite | japan_hybrid | japan_remote | international_remote | unknown
    overseas_eligible   INTEGER,    -- 1 yes, 0 no, NULL unknown
    japanese_level      TEXT,
    visa_sponsorship    TEXT,
    date_confidence     TEXT    NOT NULL DEFAULT 'low', -- high | low
    raw_json            TEXT,
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL
);

CREATE INDEX idx_jobs_posted_at    ON jobs(posted_at DESC);
CREATE INDEX idx_jobs_source       ON jobs(source);
CREATE INDEX idx_jobs_active       ON jobs(is_active);
CREATE INDEX idx_jobs_company      ON jobs(company);
CREATE INDEX idx_jobs_security     ON jobs(security_score DESC);
CREATE INDEX idx_jobs_role         ON jobs(role_category);
CREATE INDEX idx_jobs_language     ON jobs(language);
CREATE INDEX idx_jobs_location     ON jobs(location_scope);
```

**Field notes**

| Field | Meaning |
| --- | --- |
| `fingerprint` | `sha256(f"{source}:{canonical_url}")`; prevents duplicate inserts |
| `source_job_id` | Source-native ID when available (Daijob numeric ID, Robert Half reference) |
| `remote_type` | Normalized from source text (`Remote`, `Hybrid`, `TELECOMMUTE`, `在宅`) |
| `employment_type` | Normalized from source text (`FULL_TIME`, `Perm`, `Contract`, `Part Time`) |
| `salary_min` / `salary_max` | Annual JPY integers when the source gives enough detail; otherwise `NULL` |
| `salary_text` | Always keep the original display string, e.g. `¥8M ~ ¥17M` |
| `posted_at` | Source's original posting date, normalized to UTC |
| `source_updated_at` | Source's last-updated/verified date, if available |
| `first_seen_at` | When this dashboard first inserted the row |
| `last_seen_at` | When this dashboard last saw the row in a successful source fetch |
| `is_active` | `0` only when the source explicitly marks the job expired or `expires_at` has passed |
| `security_score` | 0–100 relevance score from the classifier |
| `security_tags` | JSON array, e.g. `["soc","incident-response","japanese"]` |
| `role_category` | Normalized role family; the UI hides non-technical families by default (see below) |
| `language` | Primary listing language: `en`, `ja`, `bilingual`, `unknown` |
| `location_scope` | Japan/remote eligibility bucket; the UI hides `international_remote` by default |
| `overseas_eligible` | `1` = source says overseas applicants considered, `0` = explicitly local-only, `NULL` = unknown |
| `japanese_level` | Source wording for required Japanese ability |
| `visa_sponsorship` | Source wording for visa sponsorship, never inferred |
| `date_confidence` | `high` if the source gave an explicit date; `low` if fallback to `first_seen_at` |
| `raw_json` | Optional compact JSON of the parsed source fields for debugging |

**Enumerations**

```text
role_category:   engineering | operations | grc | consulting | sales | management | other
language:        en | ja | bilingual | unknown
location_scope:  japan_onsite | japan_hybrid | japan_remote | international_remote | unknown
```

`engineering` and `operations` are the default technical scope. `grc`,
`consulting`, `sales`, and `management` are stored but hidden by default so the
user can widen the view without re-scraping. See §5 for classification rules.

### `job_tags`

Optional normalized tag table for fast filtering. If used, keep `jobs.security_tags`
as the display copy and write rows here for SQL filtering.

```sql
CREATE TABLE job_tags (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    tag    TEXT    NOT NULL,
    PRIMARY KEY (job_id, tag)
);

CREATE INDEX idx_job_tags_tag ON job_tags(tag);
```

For v1, a JSON column plus `LIKE` is acceptable for a few hundred jobs. The
normalized table is the cleaner choice if tag filters become important.

### `scrape_runs`

```sql
CREATE TABLE scrape_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    status          TEXT    NOT NULL,  -- running | success | partial | failed
    trigger         TEXT    NOT NULL,  -- manual | cli
    window_days     INTEGER NOT NULL,
    total_found     INTEGER NOT NULL DEFAULT 0,
    total_new       INTEGER NOT NULL DEFAULT 0,
    total_updated   INTEGER NOT NULL DEFAULT 0,
    total_errors    INTEGER NOT NULL DEFAULT 0,
    error_summary   TEXT
);

CREATE INDEX idx_scrape_runs_started ON scrape_runs(started_at DESC);
```

### `scrape_source_results`

```sql
CREATE TABLE scrape_source_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    source          TEXT    NOT NULL,
    status          TEXT    NOT NULL,  -- running | success | error | skipped
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    found           INTEGER NOT NULL DEFAULT 0,
    new             INTEGER NOT NULL DEFAULT 0,
    updated         INTEGER NOT NULL DEFAULT 0,
    skipped         INTEGER NOT NULL DEFAULT 0,
    errors          INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT
);

CREATE INDEX idx_source_results_run ON scrape_source_results(run_id);
```

### `source_state`

Optional but useful for source health and debugging.

```sql
CREATE TABLE source_state (
    source          TEXT PRIMARY KEY,
    last_success_at TEXT,
    last_error_at   TEXT,
    last_error      TEXT,
    etag            TEXT,
    last_modified   TEXT
);
```

## 3. Fingerprint and canonical URL

```text
canonical_url =
  lowercase scheme + host
  + path with duplicate slashes removed
  + sorted, allow-listed query params (usually none)
  + no fragment

fingerprint = sha256(f"{source_id}:{canonical_url}")
```

Rules:

- Keep source-native job IDs in the URL when they are the stable identifier
  (Daijob `/en/jobs/detail/1563361`, Robert Half `.../06940-0013539172-jpen`).
- Strip tracking parameters (`utm_*`, `ref` only if it is not part of the job ID;
  check each source).
- Do not use the title as the primary key; titles change.
- If a source has no stable URL, fall back to
  `sha256(source + company + title + location + posted_at_raw)` and mark
  `date_confidence=low` only if the date is also missing.

## 4. Upsert policy

On each successful source fetch, for every parsed job:

1. Compute `fingerprint`.
2. If it does not exist:
   - Insert with `first_seen_at = now`, `last_seen_at = now`, `is_active = 1`.
   - Count as `new`.
3. If it exists:
   - Update mutable fields: title, company, location, salary, description,
     `posted_at`, `source_updated_at`, `expires_at`, tags, score.
   - Set `last_seen_at = now`, `is_active = 1`.
   - Do **not** change `first_seen_at`.
   - Count as `updated` if any field changed, otherwise `unchanged`.
4. If `expires_at` is in the past, set `is_active = 0`.
5. Never delete a job automatically. Keep history for the dashboard and for
   debugging. A manual cleanup command can delete rows older than N months.

**Important:** do not mark jobs inactive just because they were not returned in
this run. Sources return different slices (security category, latest page), so
absence is not proof of expiry. Only explicit expiry or a source "closed" flag
should deactivate a row.

## 5. Normalization rules

### Dates

- Parse source date strings into timezone-aware datetimes.
- Convert to UTC before storing.
- Display in Asia/Tokyo.
- Date-only values (Michael Page, JapanDev) become `00:00:00+09:00` on that date.
- Full timestamps (Robert Half, TokyoDev, Daijob if time present) keep their
  original offset, then convert to UTC.
- Keep `posted_at_raw` exactly as the source showed it.

### Salary

- Keep `salary_text` always.
- Parse annual JPY when possible:
  - `¥8M ~ ¥17M` → 8,000,000 / 17,000,000.
  - `8 million yen` → 8,000,000.
  - `¥2,000 – ¥2,300 / Hour` → store hourly text; do not convert to annual unless
    the source gives hours. Leave `salary_min/max` NULL and set a
    `salary_period=hourly` tag (future field).
- Do not invent numbers. If parsing is ambiguous, keep the text and leave the
  numeric fields NULL.

### Location

- Keep the source's location text.
- Add a normalized `location_region` later if needed (Tokyo, Osaka, etc.).
- Treat `Japan`, `Tokyo`, `Remote`, `Anywhere in Japan` as valid values.
- For Michael Page, `jobLocation.address.addressLocality` plus region.

### Remote type

Map to `onsite`, `hybrid`, `remote`, `unknown`:

- `Remote`, `Fully remote`, `TELECOMMUTE`, `在宅`, `リモート` → `remote`
- `Hybrid`, `Partially remote`, `一部在宅` → `hybrid`
- `Onsite`, `No remote`, `出社` → `onsite`
- Otherwise `unknown`

### Employment type

Map to `full_time`, `contract`, `part_time`, `internship`, `unknown`:

- `FULL_TIME`, `Perm`, `Permanent`, `正社員` → `full_time`
- `Contract`, `契約`, `業務委託` → `contract`
- `Part Time`, `パート` → `part_time`
- `Intern`, `Internship`, `インターン` → `internship`

### Japanese level

Keep the source's wording, e.g. `Not required`, `Business`, `Fluent`, `N1`,
`Japanese required`. This is a useful filter even if not perfectly normalized.

### Visa sponsorship

Keep the source's wording, e.g. `Yes`, `No`, `Future possibility`,
`Apply from abroad`. Do not infer beyond the source.

### Overseas eligibility

Set `overseas_eligible` only from explicit source text:

- `1` — "applications from overseas welcome", "overseas candidates considered",
  "apply from abroad", `海外からの応募可`, `ビザサポートあり` combined with an
  overseas-application statement.
- `0` — "must currently reside in Japan", "Japanese residency required",
  `日本在住の方`, `国内在住必須`.
- `NULL` — nothing explicit. This is the common case; do not guess.

`visa_sponsorship` and `overseas_eligible` are independent: a job may sponsor a
visa but still expect the candidate to interview in Japan, or accept overseas
applications without sponsoring.

### Role category

Classify from the title first, then the description. Title wins when the two
disagree.

| Category | Signals (EN / JA) |
| --- | --- |
| `engineering` | security engineer, AppSec, product security, cloud security, DevSecOps, security architect, IAM engineer, pentest, vulnerability management, セキュリティエンジニア, 脆弱性診断, セキュリティ設計 |
| `operations` | SOC analyst, CSIRT, incident response, threat intelligence, security operations, blue team, red team, 監視, インシデント対応, 脅威インテリジェンス |
| `grc` | GRC, governance/risk/compliance, ISMS, ISO 27001, audit, 監査, 内部統制, コンプライアンス |
| `consulting` | security consultant, advisory, コンサルタント |
| `sales` | sales engineer, solutions engineer, pre-sales, 営業 |
| `management` | CISO, security manager, head of security, director, 部長, マネージャー |
| `other` | no clear signal |

Rules:

- "Security consultant" is `consulting` even though the title contains
  "security"; it is hidden by default.
- "Security sales engineer" and "solutions architect (pre-sales)" are `sales`.
- A management title that also names a technical domain (e.g. "Security
  Engineering Manager") is `management`; the UI can still surface it when the
  user opts in.
- Titles like "セキュリティエンジニア" and "脆弱性診断員" are `engineering`.
- "警備", "防犯", and "security guard" are not cybersecurity; mark `other` and
  let `security_score` demote them.

### Language

Infer the primary listing language from the title and description; never
machine-translate.

- `en` — title and description are overwhelmingly English.
- `ja` — title and description are overwhelmingly Japanese.
- `bilingual` — both languages are substantially present (a common pattern on
  Daijob and Michael Page Japan), or the listing explicitly asks for bilingual
  ability and publishes both versions.
- `unknown` — too little text to decide.

Heuristics:

- Count Japanese characters (hiragana, katakana, kanji) versus Latin words.
- If Japanese characters exceed ~20% of the text, it is at least partly
  Japanese.
- English-only job text with a Japanese company name stays `en`.
- Store the result; the UI filter treats `bilingual` as matching both `en` and
  `ja` requests when the user asks for either.

### Location scope

Derive from `remote_type` plus the location and description text:

| Scope | Rule |
| --- | --- |
| `japan_onsite` | Location is in Japan and `remote_type = onsite` (or unspecified but clearly office-based) |
| `japan_hybrid` | Location is in Japan and `remote_type = hybrid` |
| `japan_remote` | `remote_type = remote` and the role is limited to Japan (e.g. "remote in Japan", "在宅勤務（全国）") |
| `international_remote` | "remote anywhere", "worldwide", "work from anywhere", or a non-Japan location with no Japan eligibility |
| `unknown` | no location/remote signal |

Rules:

- The user wants to relocate to Japan, so `japan_remote` is in scope and
  `international_remote` is hidden by default.
- A role that is remote but requires Japanese residency is `japan_remote`.
- A role advertised as "remote" with a non-Japan HQ but open to Japan-based
  candidates is `japan_remote`; if it is open worldwide, it is
  `international_remote`.
- Keep the source's raw `location` text alongside the normalized scope.
- If `remote_type` is `unknown` but the location is a Japanese city, use
  `japan_onsite` only when the description implies office work; otherwise
  `unknown`.

## 6. Security classification

`security_score` is a 0–100 ranking score. Suggested weights:

| Signal | Weight |
| --- | --- |
| Source is a dedicated security category | +40 |
| Title contains a core security term | +30 |
| Title contains a domain term (SOC, GRC, IAM, etc.) | +20 |
| Description contains 3+ domain terms | +15 |
| Tags from source (e.g. "Security jobs") | +10 |
| Negative term in title (警備, security guard, food security) | −40 |
| No security signal at all | 0 |

Suggested tags:

```text
appsec, cloud-security, grc, iam, incident-response, isms, network-security,
penetration-testing, product-security, red-team, blue-team, security-engineering,
security-operations, soc, threat-intelligence, vulnerability-management,
ciso, audit, forensics, cryptography, devsecops, japanese
```

The UI should show tags and allow filtering. The score is a heuristic; the user
can always search the raw description.

## 7. Example queries

```sql
-- Default view: technical roles, Japan-eligible, posted in the last 3 days
SELECT *
FROM jobs
WHERE is_active = 1
  AND posted_at >= datetime('now', '-3 days')
  AND role_category IN ('engineering', 'operations')
  AND location_scope IN ('japan_onsite', 'japan_hybrid', 'japan_remote')
ORDER BY posted_at DESC
LIMIT 50;

-- English-friendly technical roles, newest first
SELECT *
FROM jobs
WHERE is_active = 1
  AND role_category IN ('engineering', 'operations')
  AND language IN ('en', 'bilingual')
  AND location_scope IN ('japan_onsite', 'japan_hybrid', 'japan_remote')
ORDER BY posted_at DESC;

-- Relocation-friendly roles: explicit overseas eligibility or visa sponsorship
SELECT *
FROM jobs
WHERE is_active = 1
  AND role_category IN ('engineering', 'operations')
  AND (overseas_eligible = 1 OR visa_sponsorship IS NOT NULL)
ORDER BY overseas_eligible DESC, posted_at DESC;

-- New to the dashboard in the last 3 days, even if the source date is older
SELECT *
FROM jobs
WHERE first_seen_at >= datetime('now', '-3 days')
ORDER BY first_seen_at DESC;

-- Jobs from one source with a security tag
SELECT j.*
FROM jobs j
JOIN job_tags t ON t.job_id = j.id
WHERE j.source = 'michael_page'
  AND t.tag = 'soc'
ORDER BY j.posted_at DESC;

-- Source health for the latest run
SELECT s.source, s.status, s.found, s.new, s.errors, s.error_message
FROM scrape_source_results s
JOIN scrape_runs r ON r.id = s.run_id
WHERE r.id = (SELECT MAX(id) FROM scrape_runs);
```

## 8. Retention and backup

- Keep all rows by default; the database will stay small (thousands of rows).
- Optional cleanup: mark rows inactive after 90 days, delete after 1 year.
- Backup: copy `data/jobs.db` while the app is stopped, or use SQLite's
  `VACUUM INTO` for a live backup.
- Enable WAL mode for better read/write behavior:
  `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`
- Use `PRAGMA busy_timeout=5000;` to avoid transient locks.

## 9. Migration strategy

- v1: `Base.metadata.create_all()` on startup for a fresh database.
- Add a `schema_version` table or use Alembic once the schema starts changing.
- Do not use `create_all()` as a migration tool for existing data; it does not
  alter tables. If a column changes, add a migration.

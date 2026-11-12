# UI and API Specification

## 1. Design goals

- Minimal: one page, no framework, no build step.
- Fast: server-rendered shell, small JSON API, no heavy assets.
- Clear: the user can see what was scraped, when, and from where.
- Honest: empty states, per-source errors, and "last successful refresh" are
  visible.
- Accessible: semantic HTML, labels, keyboard support, good contrast.

## 2. Page layout

```text
┌──────────────────────────────────────────────────────────────┐
│  Japan Cybersecurity Jobs                     Last refresh…  │
│  Public listings from 5 sources                [ Refresh ]   │
├──────────────────────────────────────────────────────────────┤
│  [ 42 jobs ] [ 8 new in 3d ] [ 5/5 sources ] [ Last: ok ]    │
├──────────────────────────────────────────────────────────────┤
│  Search [________________]  Source [All ▾]  Role [Technical ▾]│
│  Language [Any ▾]  Location [____]  Remote [Any ▾]           │
│  Visa [Any ▾]  Tag [Any ▾]  Window [3 days ▾]  Sort [New ▾]  │
├──────────────────────────────────────────────────────────────┤
│  ▸ Security Engineer — Acme Corp                             │
│    Tokyo · ¥8M–¥12M · Michael Page · Posted 2 days ago       │
│    [security-engineering] [cloud-security]                   │
│                                                              │
│  ▸ SOC Analyst — Example KK                                  │
│    Remote · ¥6M–¥9M · Daijob · Posted 1 day ago              │
│    [soc] [incident-response]                                 │
│                                                              │
│  …                                                           │
├──────────────────────────────────────────────────────────────┤
│  Refresh status: Michael Page ✓  JapanDev ✓  TokyoDev …      │
│  Data from public job boards. Respect each source's terms.   │
└──────────────────────────────────────────────────────────────┘
```

## 3. Components

### Header

- Title: `Japan Cybersecurity Jobs`
- Subtitle: `Public listings from 5 sources`
- Last refresh: relative time (`2 minutes ago`) plus absolute tooltip.
- Refresh button:
  - Enabled when idle.
  - Disabled and shows `Refreshing…` while running.
  - Shows a spinner or subtle animation.

### Summary cards

- `Total jobs` — active jobs matching the current filters.
- `New in window` — jobs with `posted_at` in the selected window.
- `Sources healthy` — `ok/total` from the last run.
- `Last run` — `success`, `partial`, or `failed`, with color.

### Filters

- Keyword search: title, company, description (server-side `LIKE` for v1).
- Source: multi-select or single-select with "All".
- **Role type**: `Technical` (default; `engineering` + `operations`), `All roles`,
  and individual categories (`Engineering`, `Operations`, `GRC`, `Consulting`,
  `Sales`, `Management`, `Other`). Non-technical categories are opt-in.
- **Language**: `Any`, `English`, `Japanese`, `Bilingual`. `Any` includes all
  values; `English` matches `en` and `bilingual`; `Japanese` matches `ja` and
  `bilingual`.
- Location: text input (e.g., `Tokyo`, `Osaka`).
- Remote: `Any`, `Remote`, `Hybrid`, `Onsite`.
- **Location scope**: `Japan (all)` (default; excludes `international_remote`),
  `Japan onsite`, `Japan hybrid`, `Japan remote`, `International remote`,
  `Unknown`.
- **Visa / overseas**: `Any`, `Overseas eligible`, `Visa sponsorship`,
  `Overseas eligible or visa sponsorship`. These filter on
  `overseas_eligible = 1` and `visa_sponsorship IS NOT NULL`.
- Tag: dropdown populated from `/api/sources` or `/api/stats`.
- Window: `3 days` (default), `7 days`, `30 days`, `All active`.
- Sort: `Newest`, `Oldest`, `Company A–Z`, `Relevance`.
- "Include active older listings" toggle, shown when window is 3/7/30 days.
- Clear filters button.

Default filter combination: `role=technical`, `language=any`,
`location_scope=japan`, `visa=any`, `days=3`, `sort=newest`. This keeps the
default view to technical, Japan-eligible roles without hiding non-sponsored
jobs. Relocation status is shown as badges, not used to reorder the list by
default.

### Job list

Each row:

- Title (link to source, opens in a new tab).
- Company.
- Location plus location-scope hint (`Tokyo · hybrid`, `Remote (Japan)`).
- Salary text (if available).
- Source badge.
- Language badge: `EN`, `JA`, or `EN/JA`.
- Visa/overseas badges when known: `Visa support`, `Overseas OK`,
  `Japan residents only`. Unknown stays unlabelled rather than showing "No".
- Posted date (`2 days ago`, with exact date tooltip).
- Tags.
- Expandable description:
  - Use `<details>`/`<summary>` for zero-JS expansion, or a JS toggle.
  - Show plain text, preserve line breaks.
  - Cap height with a "Show more" control.

Visual states:

- New badge if `first_seen_at` is within the selected window.
- `date_confidence=low` shows a subtle `date estimated` note.
- Expired/inactive rows are hidden by default; if shown, muted.

### Refresh status panel

Per source:

- Name.
- Status: `pending`, `running`, `success`, `error`, `skipped`.
- Counts: found / new / updated.
- Error message (short, user-safe).
- Last success time.

Global:

- Progress text: `Scraping Michael Page (2/5)…`
- If partial: `Completed with 1 source error.`
- If failed: `Refresh failed. See source details.`

### Footer

- `Data from public job boards. Respect each source's terms.`
- Link to `README.md` or an `/about` section.
- Version string.

## 4. Empty and error states

| State | Message |
| --- | --- |
| No jobs in window | `No jobs posted in the last 3 days. Try 7 days, or refresh.` |
| No technical roles in window | `No technical security roles posted in the last 3 days. Try All roles, 7 days, or refresh.` |
| No Japan-eligible roles | `No Japan-eligible roles in this window. International-remote roles are hidden by default; widen Location scope to see them.` |
| No jobs at all | `No jobs yet. Click Refresh to fetch listings.` |
| Source error | `Michael Page failed: listing page changed. Other sources are unaffected.` |
| Refresh already running | `A refresh is already running.` |
| Database error | `Could not read the database. Check the logs.` |

## 5. HTTP API

### `GET /api/jobs`

Query parameters:

| Param | Type | Default | Notes |
| --- | --- | --- | --- |
| `q` | string | — | Search title/company/description |
| `source` | string (repeatable) | all | Source ID |
| `role` | string | `technical` | `technical` (`engineering`+`operations`), `all`, or a single category |
| `language` | string | — | `en`, `ja`, `bilingual`; `en`/`ja` also match `bilingual` |
| `location` | string | — | Case-insensitive contains |
| `location_scope` | string | `japan` | `japan` (three Japan buckets), a single bucket, or `all` |
| `remote` | string | — | `remote`, `hybrid`, `onsite` |
| `visa` | string | — | `overseas`, `sponsored`, `either` |
| `tag` | string | — | Security tag |
| `days` | int | 3 | 3, 7, 30; `0` = all active |
| `include_active` | bool | false | Include older active listings |
| `sort` | string | `posted_desc` | `posted_desc`, `posted_asc`, `company`, `relevance` |
| `limit` | int | 50 | Max 200 |
| `offset` | int | 0 | Pagination |

Response:

```json
{
  "items": [
    {
      "id": 1,
      "title": "Security Engineer",
      "company": "Acme Corp",
      "location": "Tokyo",
      "remote_type": "hybrid",
      "employment_type": "full_time",
      "salary_text": "¥8M – ¥12M",
      "salary_min": 8000000,
      "salary_max": 12000000,
      "source": "michael_page",
      "source_name": "Michael Page",
      "url": "https://…",
      "posted_at": "2026-11-09T00:00:00Z",
      "first_seen_at": "2026-11-10T01:00:00Z",
      "security_score": 85,
      "security_tags": ["security-engineering", "cloud-security"],
      "role_category": "engineering",
      "language": "en",
      "location_scope": "japan_hybrid",
      "japanese_level": "Not required",
      "visa_sponsorship": "Yes",
      "overseas_eligible": 1,
      "date_confidence": "high",
      "is_new": true
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

### `GET /api/jobs/{id}`

Returns the full job, including `description_text`, `description_html`,
`posted_at_raw`, `source_updated_at`, `expires_at`, and `raw_json` (optional,
behind a debug flag).

### `GET /api/stats`

```json
{
  "total_jobs": 42,
  "new_in_window": 8,
  "by_source": {
    "michael_page": 12,
    "japan_dev": 7,
    "tokyo_dev": 5,
    "daijob": 10,
    "robert_half": 8
  },
  "by_role_category": {
    "engineering": 24,
    "operations": 11,
    "grc": 3,
    "consulting": 2,
    "sales": 1,
    "management": 1,
    "other": 0
  },
  "relocation_friendly": 6,
  "last_run": {
    "id": 7,
    "status": "success",
    "started_at": "2026-11-11T09:00:00Z",
    "finished_at": "2026-11-11T09:00:45Z",
    "total_new": 8,
    "total_errors": 0
  }
}
```

### `GET /api/sources`

```json
{
  "sources": [
    {
      "id": "michael_page",
      "name": "Michael Page",
      "url": "https://www.michaelpage.co.jp/en/jobs/it-security",
      "enabled": true,
      "last_success_at": "2026-11-11T09:00:40Z",
      "last_status": "success",
      "last_error": null
    }
  ]
}
```

### `POST /api/refresh`

- Request body: `{ "window_days": 3 }` (optional).
- Returns `202 Accepted`:

```json
{ "run_id": 8, "status": "running" }
```

- Returns `409 Conflict` if a refresh is already running:

```json
{ "detail": "A refresh is already running." }
```

### `GET /api/refresh/status`

```json
{
  "run_id": 8,
  "status": "running",
  "started_at": "2026-11-11T09:10:00Z",
  "finished_at": null,
  "current_source": "tokyo_dev",
  "sources": {
    "michael_page": {"status": "success", "found": 22, "new": 3, "updated": 0, "errors": 0},
    "japan_dev": {"status": "success", "found": 37, "new": 2, "updated": 0, "errors": 0},
    "tokyo_dev": {"status": "running", "found": 0, "new": 0, "updated": 0, "errors": 0},
    "daijob": {"status": "pending", "found": 0, "new": 0, "updated": 0, "errors": 0},
    "robert_half": {"status": "pending", "found": 0, "new": 0, "updated": 0, "errors": 0}
  }
}
```

### `GET /health`

```json
{ "status": "ok", "database": "ok", "version": "0.1.0" }
```

## 6. Client behavior

- On page load: `GET /api/jobs` with default filters (`role=technical`,
  `location_scope=japan`, `days=3`), `GET /api/stats`, `GET /api/sources`,
  `GET /api/refresh/status`.
- On filter change: debounce 250 ms, then `GET /api/jobs` and `GET /api/stats`.
- On Refresh click:
  1. `POST /api/refresh`.
  2. If `202`, disable the button and poll `GET /api/refresh/status` every 1 s.
  3. Update the per-source panel from the response.
  4. When status is `success`, `partial`, or `failed`, reload jobs and stats,
     re-enable the button.
- On `409`, show "A refresh is already running" and start polling.
- Use `fetch` with `AbortController` to cancel stale job queries.
- No external JS libraries. No CDN. Works offline once loaded.

## 7. CSS

- Single `app.css`.
- System font stack:
  `system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans JP", sans-serif`.
- CSS variables for colors, spacing, and radii.
- Light and dark mode via `prefers-color-scheme`.
- Responsive:
  - Desktop: table-like rows.
  - Mobile: stacked cards, filters collapse into a `<details>` panel.
- Focus-visible outlines for keyboard users.
- Minimum contrast ratio 4.5:1 for text.

## 8. Accessibility checklist

- [ ] Every input has a `<label>`.
- [ ] Buttons are `<button>` elements, not clickable `<div>`s.
- [ ] Job titles are real links with descriptive text.
- [ ] Status changes use `aria-live="polite"`.
- [ ] Color is not the only way to convey source/status.
- [ ] Keyboard-only navigation works.
- [ ] Page has a meaningful `<title>` and `<h1>`.
- [ ] Tables/lists use semantic markup.

## 9. Non-goals for the UI

- No drag-and-drop kanban.
- No saved searches or user accounts.
- No charts or analytics dashboards.
- No application tracking.
- No AI chat interface.

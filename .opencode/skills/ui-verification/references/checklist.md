# UI Verification Checklist

Mapped to `docs/verification.md` §2. Run against `http://127.0.0.1:8001/`.
Every browser call needs the `tabID` from `browser.tabs.open`.

## 1. Load and chrome

- [ ] `browser.tabs.open({ url: "http://127.0.0.1:8001/" })` returns a tab.
- [ ] `browser.wait({ tabID, condition: "load" })`.
- [ ] `browser.snapshot({ tabID })` shows: header title, subtitle, summary
      cards (Jobs, New in window, Sources, Last run), the filter bar, the
      refresh panel, and the footer.
- [ ] `browser.screenshot({ tabID, fullPage: true })`, then
      `browser.preview({ path })` to show the user.
- [ ] `browser.evaluate({ tabID, script: "document.title" })` is
      `Japan Cybersecurity Jobs`.

## 2. Console and network

- [ ] `browser.console({ tabID, level: "error" })` returns no messages.
- [ ] `browser.network.list({ tabID, limit: 100 })` shows only
      `127.0.0.1:8001` requests (document, script, css, fetch/xhr). No CDN and
      no external hosts.

## 3. Filters

For each filter, change it and verify the job list and summary counts update,
and that the URL query string reflects the change
(`browser.evaluate({ tabID, script: "window.location.search" })`).

- [ ] Role: default `technical`; switch to `all` (more rows if non-technical
      rows exist); switch back.
- [ ] Location scope: `japan` (default) hides `international_remote`; switch
      to `international_remote` (those rows appear); back to `japan`.
- [ ] Window: 3 → 7 → 30 → 0 (All active) changes the count.
- [ ] Source: pick one source → only that source's rows.
- [ ] Language: `en`, `ja`, `bilingual` narrow the list.
- [ ] Remote: `remote`, `hybrid`, `onsite` narrow the list.
- [ ] Visa/eligibility: `overseas`, `sponsored`, `either`.
- [ ] Tag: pick a tag → only tagged rows.
- [ ] Sort: `posted_desc`, `posted_asc`, `company`, `relevance` reorder rows.
- [ ] Search: type `security` → filtered; clear.
- [ ] "Include older listings": widens the window.
- [ ] "Clear filters": returns to `role=technical`, `location_scope=japan`,
      `days=3`, `sort=posted_desc`.
- [ ] The URL keeps the filters (shareable / reload-safe).

## 4. States

- [ ] Empty: search `zzzz` → "No jobs found" plus a reason (window, role,
      location scope). Screenshot.
- [ ] Loading: change a filter and snapshot immediately; a loading indicator
      or `aria-busy` state is visible.
- [ ] No jobs at all: with an empty DB, "No jobs yet" plus the Refresh prompt.
- [ ] Error: only if the user asks — stop the app or block `/api/jobs`, then
      verify "Could not load jobs" and the Retry button.

## 5. Accessibility

- [ ] Every input has a `<label>`: `browser.evaluate` to compare
      `document.querySelectorAll('input,select,textarea')` against labelled
      controls.
- [ ] Keyboard: `Tab` reaches the skip link, every filter, the refresh
      button, and each job link; `Enter` toggles a job's Details disclosure.
- [ ] `aria-live="polite"` is present on `#job-list` and
      `#refresh-status-line`.
- [ ] `browser.lighthouse({ tabID })` — record the accessibility score and
      any failures.
- [ ] Color is not the only signal: badges carry text.

## 6. Dark mode and responsive

- [ ] `browser.evaluate` →
      `window.matchMedia('(prefers-color-scheme: dark)').matches`; report the
      active scheme.
- [ ] If dark mode is active, verify the dark palette with a screenshot.
- [ ] Responsive: the OpenCode browser tools cannot resize the viewport. Ask
      the user to resize the window, or verify manually, and note it in the
      report.

## 7. Refresh (opt-in, live network)

Only when the user explicitly asks. Warn first: this scrapes the five real
job sites (~2 minutes, ~1 req/s) and writes `./data/jobs.db`.

- [ ] Click **Refresh now**: the button disables and shows "Refreshing…".
- [ ] The refresh panel shows per-source progress (pending → running →
      success/error) and counts.
- [ ] When the run finishes, the button re-enables and the list/stats reload
      without a full page reload.
- [ ] A second Refresh while one is running does not start a duplicate run.
- [ ] `browser.network.list` shows rate-limited requests to the source hosts.

## Seeding (optional, with approval)

If the DB is empty and the user agrees, insert a few rows into
`./data/jobs.db` covering the default-visible and hidden cases, then re-run
§3–§5.

```bash
sqlite3 data/jobs.db "INSERT INTO jobs
  (fingerprint, source, url, title, company, location, remote_type,
   employment_type, salary_min, salary_max, salary_text, posted_at,
   posted_at_raw, first_seen_at, last_seen_at, is_active, security_score,
   security_tags, role_category, language, location_scope, overseas_eligible,
   japanese_level, visa_sponsorship, date_confidence, created_at, updated_at)
VALUES
  ('seed-eng-hybrid','michael_page','https://example.com/jobs/seed-1','Security Engineer','Acme Corp','Tokyo','hybrid','full_time',8000000,12000000,'¥8M - ¥12M',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),'yesterday',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),1,85,'[\"security-engineering\"]','engineering','en','japan_hybrid',NULL,NULL,NULL,'high',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day')),
  ('seed-ops-remote','daijob','https://example.com/jobs/seed-2','SOC Analyst','Example KK','Remote','remote','full_time',6000000,9000000,'¥6M - ¥9M',strftime('%Y-%m-%dT%H:%M:%SZ','now','-2 day'),'2 days ago',strftime('%Y-%m-%dT%H:%M:%SZ','now','-2 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-2 day'),1,75,'[\"soc\",\"incident-response\"]','operations','en','japan_remote',NULL,NULL,NULL,'high',strftime('%Y-%m-%dT%H:%M:%SZ','now','-2 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-2 day')),
  ('seed-grc','michael_page','https://example.com/jobs/seed-3','GRC Analyst','Acme Corp','Tokyo','onsite','full_time',7000000,10000000,'¥7M - ¥10M',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),'yesterday',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),1,60,'[\"grc\"]','grc','en','japan_onsite',NULL,NULL,NULL,'high',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day')),
  ('seed-intl','japan_dev','https://example.com/jobs/seed-4','Cloud Security Engineer','Global Corp','Remote','remote','full_time',9000000,15000000,'¥9M - ¥15M',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),'yesterday',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),1,80,'[\"cloud-security\"]','engineering','en','international_remote',NULL,NULL,NULL,'high',strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'),strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day'));"

# Confirm
curl -s 'http://127.0.0.1:8001/api/jobs?limit=1' | python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])'
```

Delete the seed rows afterwards if the user asks:

```bash
sqlite3 data/jobs.db "DELETE FROM jobs WHERE fingerprint LIKE 'seed-%';"
```

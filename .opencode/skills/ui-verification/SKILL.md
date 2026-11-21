---
name: UI Verification
description: Verify the dashboard UI in a real browser against the host dev server using the OpenCode browser tools. Use for visual checks, filter behavior, refresh states, accessibility, and console/network inspection.
---

# UI Verification

Agent-driven browser verification of the running dashboard. This is separate
from `uv run pytest`; it does not modify the offline suite and is not part of
CI.

## Read before starting

1. `AGENTS.md` — project rules.
2. `docs/verification.md` §2 — the manual checklist this skill executes.
3. `docs/ui.md` — the UI and API contract.
4. `references/checklist.md` — the step-by-step browser procedure.

## Prerequisites

1. Start the host dev server:

   ```bash
   make run
   ```

   Confirm it is up:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/
   # 200
   ```

2. Open a tab and keep the returned `tabID` for every browser call:

   ```js
   tools.browser.tabs.open({ url: "http://127.0.0.1:8001/" })
   ```

3. Check whether the local database has rows:

   ```bash
   curl -s 'http://127.0.0.1:8001/api/jobs?limit=1' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])'
   ```

   - **Rows present:** run the full checklist.
   - **Empty:** verify the empty state, then ask the user whether to seed demo
     rows (see `references/checklist.md` §Seeding) or run a live refresh. Do
     neither without approval.

## Rules

- **Localhost only.** The browser must only talk to `127.0.0.1:8001`. Never
  point it at a job site.
- **No live refresh by default.** Refresh scrapes real sites (~2 minutes,
  ~1 req/s) and writes `./data/jobs.db`. Do it only when the user explicitly
  asks, and warn them first.
- **No stealth/anti-bot browsers.** Use the normal OpenCode browser.
- **Report, do not fix.** Do not edit application code unless the user asks.

## Workflow

1. Load the page, wait for load, snapshot, screenshot; verify the header,
   summary cards, filter bar, refresh panel, and footer.
2. Check `browser.console` for errors and `browser.network.list` for external
   requests.
3. Exercise every filter; verify the list, counts, and URL query string change,
   and that "Clear filters" resets the defaults.
4. Verify empty and loading states.
5. Verify labels, keyboard navigation, `aria-live` regions, and run a
   Lighthouse audit.
6. Report dark mode and responsive limitations honestly.
7. Optionally, only if asked, run a live refresh and verify the refresh flow.
8. Report with the format below.

## Tool patterns

- `browser.snapshot({ tabID })` returns refs; `browser.click({ tabID, ref })`
  acts on one. Re-snapshot after any DOM change — refs expire.
- `browser.find({ tabID, text: "Refresh now" })` locates text.
- `browser.wait({ tabID, condition: "text", text: "No jobs found" })`.
- `browser.screenshot({ tabID, fullPage: true })`, then
  `browser.preview({ path })` to show the image to the user.
- `browser.console({ tabID, level: "error" })`.
- `browser.network.list({ tabID, limit: 100 })`.
- `browser.evaluate({ tabID, script: "window.location.search" })` for DOM,
  URL, and media checks.

## Report format

```text
UI verification — http://127.0.0.1:8001/
Data: <n jobs / empty>
Passed: ...
Findings:
  [Blocker] ...
  [High] ...
  [Medium] ...
  [Low] ...
Console errors: ...
External requests: ...
Not verified: <dark mode / responsive / live refresh / ...>
```

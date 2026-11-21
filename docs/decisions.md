# Architecture Decision Records

Each record captures a decision, why it was made, and what it costs.

## ADR-001 — FastAPI + Jinja2 + vanilla JS

**Status:** accepted.

**Context:** The dashboard needs a Python backend, a small UI, and no build
pipeline. The UI requirements are minimal: a list, filters, a refresh button,
and progress status.

**Decision:** Use FastAPI for the HTTP API and Jinja2 for the page shell, with
plain CSS and vanilla JavaScript. No React, Vue, or Node toolchain.

**Consequences:**

- One language and one dependency manager.
- Fast startup and easy local development.
- No component framework; the UI must stay simple.
- If the UI grows significantly, a frontend framework can be added later
  without changing the API.

## ADR-002 — SQLite + SQLAlchemy 2.0

**Status:** accepted.

**Context:** Single-user, local, small data volume, no concurrent writers.

**Decision:** Use SQLite with SQLAlchemy 2.0. Enable WAL mode, foreign keys, and
a busy timeout.

**Consequences:**

- Zero operations, one file, easy backup.
- Not suitable for multiple app instances writing concurrently.
- A future multi-user deployment would need PostgreSQL and a migration.

## ADR-003 — Manual refresh only

**Status:** accepted.

**Context:** The user explicitly wants scraping to happen only when they click
Refresh. Automatic scraping would create background load and surprise requests.

**Decision:** No scheduler, cron, startup scrape, or periodic poll. The only
outbound scraping path is `POST /api/refresh` (and the developer CLI, which uses
the same code path).

**Consequences:**

- Data can be stale until the user refreshes.
- The UI must show the last refresh time and source health.
- The refresh must be robust and reasonably fast.

## ADR-004 — Public pages only; no login/CAPTCHA bypass

**Status:** accepted.

**Context:** Some job sites require login, block bots, or use Cloudflare. The
user asked for no-login workarounds where possible and auth requirements where
not.

**Decision:** Launch only with sources that expose public listings and do not
require bypassing a protection. Do not implement CAPTCHA solving, Cloudflare
bypass, or credential stuffing. For excluded sources, document the official API
or cookie-based option, but do not build it by default.

**Consequences:**

- Fewer sources, but a defensible and maintainable project.
- LinkedIn, Indeed, GaijinPot, and CareerCross are deferred.
- If the user later provides cookies or API keys, an authenticated adapter can
  be added behind an explicit feature flag.

## ADR-005 — One row per source listing; cross-source dedup deferred

**Status:** accepted for v1.

**Context:** The same job may appear on multiple boards. True deduplication
requires fuzzy matching and can hide legitimate differences (salary, location,
agency).

**Decision:** Store one row per source listing. Show a source badge. Defer
cross-source grouping to a later phase (see `docs/agents/08-open-options.md`).

**Consequences:**

- Simple, predictable data model.
- Some duplicate-looking rows in the UI.
- The user can compare sources and see which one has the most complete listing.

## ADR-006 — Date window uses the source's posting date

**Status:** accepted.

**Context:** "Past 3 days" can mean the source's original posting date, the date
the dashboard first saw it, or the date the source last updated it.

**Decision:** Use `posted_at` (source's original date) for the default 3-day
window. Store `first_seen_at`, `last_seen_at`, and `source_updated_at`
separately. Provide a "new to dashboard" badge and an "include active older"
toggle.

**Consequences:**

- Matches the literal requirement.
- Some days will have few or zero results because sources post infrequently.
- Users can switch to a wider window or "new to dashboard" view.

## ADR-007 — Plain HTTP + JSON-LD; no headless browser in v1

**Status:** accepted.

**Context:** All five launch sources returned usable HTML/JSON to a plain HTTP
client during planning. A headless browser adds weight, flakiness, and resource
use.

**Decision:** Use `httpx` + BeautifulSoup/lxml + JSON-LD parsing. Defer
Playwright to sources that genuinely require it (for example, GaijinPot).

**Consequences:**

- Faster, lighter, easier to test.
- Some future sources will need a browser adapter.
- The scraper contract should allow a browser-based implementation later.

## ADR-008 — No dashboard authentication; bind to localhost

**Status:** accepted for v1.

**Context:** Single-user local dashboard, no login requirement.

**Decision:** Bind to `127.0.0.1` by default. Do not build user accounts.

**Consequences:**

- Simple.
- The app must not be exposed to the internet without a reverse proxy and auth.
- Document the risk clearly.

## ADR-009 — Per-source error isolation

**Status:** accepted.

**Context:** Scrapers are brittle. One changed selector should not break the
whole dashboard.

**Decision:** Catch errors per source, record them in
`scrape_source_results`, continue with other sources, and finish the run as
`partial`.

**Consequences:**

- The dashboard remains useful when one source breaks.
- The UI must clearly show which source failed and why.
- The user can disable a broken source via config.

## ADR-010 — Store descriptions as text and HTML

**Status:** accepted.

**Context:** The UI needs readable descriptions; debugging needs the original
markup.

**Decision:** Store `description_text` (stripped, normalized) for display and
`description_html` (sanitized) for optional rendering. For v1, the UI can render
plain text only.

**Consequences:**

- More storage, but still small.
- Sanitization is required if HTML is rendered.
- Plain text is safer and sufficient for the minimal UI.

## ADR-011 — Configurable source enable flags

**Status:** accepted.

**Context:** A source may break or become non-compliant.

**Decision:** Each source has an `ENABLE_<SOURCE>` environment flag. Disabled
sources are skipped and shown as `skipped` in the UI.

**Consequences:**

- Easy to disable a source without a code change.
- The UI must handle a variable number of sources.

## ADR-012 — Technical-only default, with stored role categories

**Status:** accepted.

**Context:** The user wants engineering/technical security roles. Security job
titles are broad, and a strict scraper-level filter would throw away data that
could become useful if the rule changes.

**Decision:** Store every security-relevant row with a `role_category`
(`engineering`, `operations`, `grc`, `consulting`, `sales`, `management`,
`other`). The default UI shows `engineering` + `operations`; the other categories
are opt-in. Classification is title-first.

**Consequences:**

- No re-scraping needed to widen the view.
- The classifier must distinguish "security consultant" from "security
  engineer".
- The UI needs a role-type filter.

## ADR-013 — Language tagging, no translation

**Status:** accepted.

**Context:** The user reads both English and Japanese listings but wants to know
which is which. Machine translation adds cost and ambiguity.

**Decision:** Detect `en`, `ja`, `bilingual`, or `unknown` from the listing text.
Expose a language filter. Do not translate in v1.

**Consequences:**

- The user can choose English-friendly or Japanese roles.
- Detection is heuristic and may mislabel short listings.
- Translation can be added later without a schema change.

## ADR-014 — Japan-only scope, including remote within Japan

**Status:** accepted.

**Context:** The user intends to relocate to Japan and work there. "Remote" roles
vary from Japan-only to worldwide.

**Decision:** Track `location_scope` with `japan_onsite`, `japan_hybrid`,
`japan_remote`, `international_remote`, and `unknown`. Hide
`international_remote` by default. Also track `visa_sponsorship` and
`overseas_eligible` from explicit source text so relocation-friendly roles are
visible. Keep the default sort **newest first**; show relocation status as
badges rather than reordering jobs.

**Consequences:**

- The default view matches the user's relocation goal.
- Scrapers must parse remote wording carefully.
- Unknown visa/overseas status is left `NULL`, not guessed as "no".
- Relocation-friendly roles are visible but not artificially pushed to the top.

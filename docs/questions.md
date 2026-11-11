# Open Questions

These are the decisions that affect the build. Each has a recommended default so
work can start without blocking.

## 1. Which roles count as "cybersecurity"?

**Options**

- A. All security-domain roles: engineering, SOC, GRC, audit, consulting,
  sales engineer, PM, CISO. Tag each category so the user can filter.
- B. Engineering/technical only: security engineer, AppSec, cloud security,
  SOC analyst, incident response, pentest, etc.
- C. Engineering + GRC/consulting, excluding sales and PM.

**Recommended:** A, with tags. It gives the broadest coverage, and the UI can
filter to technical roles. Security job titles vary widely in Japan, and a
strict filter would hide relevant roles.

## 2. Language scope

**Options**

- A. Both English and Japanese listings, with a language tag/filter.
- B. English-friendly listings only (English job description or "no Japanese
  required").
- C. Japanese-language listings only.

**Recommended:** A. Michael Page, JapanDev, TokyoDev, and Robert Half provide
English-friendly roles; Daijob adds Japanese-language roles. A language filter
keeps the dashboard useful for either goal.

## 3. What does "past 3 days" mean?

**Options**

- A. Original source posting date (`posted_at`).
- B. First time this dashboard saw the listing (`first_seen_at`).
- C. Either posted or updated/verified by the source in the last 3 days.

**Recommended:** A as the default, with:
- a "new to dashboard" badge based on `first_seen_at`;
- a 7/30/all toggle;
- an "include active older listings" toggle.

This matches the literal requirement while avoiding an empty dashboard on quiet
days.

## 4. Location scope

**Options**

- A. All Japan.
- B. Tokyo only.
- C. Remote-only roles.
- D. Tokyo + remote.

**Recommended:** A, with location and remote filters. The data model keeps the
source location, so narrowing later is easy.

## 5. UI stack

**Options**

- A. FastAPI + Jinja2 + vanilla JS.
- B. Flask + Jinja2 + vanilla JS.
- C. Static HTML + a separate Python API.
- D. Something else.

**Recommended:** A. It is Python-native, async-friendly, and needs no Node
build. The UI is small enough that a framework would add more cost than value.

## 6. Cross-source deduplication in v1?

**Options**

- A. No; show one row per source with a source badge.
- B. Yes; group obvious duplicates by company + title + location.

**Recommended:** A for v1. Deduplication is a fuzzy problem and can hide
differences in salary or agency. Add grouping in phase 6 after seeing real data.

## 7. Do you want an authenticated source later?

**Options**

- A. No; public sources only.
- B. Yes, LinkedIn via a user-provided session cookie.
- C. Yes, Indeed via an official API/partner account.
- D. Yes, GaijinPot via a Playwright browser session.

**Recommended:** A for v1. If you want B/C/D later, we will add an explicit
feature flag and document the credential handling. No credentials will be
committed or stored in the database.

## 8. Deployment target

**Options**

- A. Local only, `127.0.0.1`.
- B. LAN access with a reverse proxy and auth.
- C. Docker container.
- D. Public server.

**Recommended:** A for v1. The dashboard has no login, so localhost is the safe
default.

## 9. Salary display

**Options**

- A. Show the source's salary text and parsed annual JPY when available.
- B. Normalize everything to annual JPY, even if the source gives hourly/daily.
- C. Hide salary.

**Recommended:** A. Do not invent conversions. Keep the original text and parse
only when the source provides enough information.

## 10. Contact / User-Agent

**Options**

- A. Use `JDashboard/0.1 (personal job dashboard; +http://127.0.0.1:8000)`.
- B. Include your email or website in the User-Agent.

**Recommended:** A for local use. If you deploy it publicly, use B so site
operators can contact you.

## 11. Should the app show jobs older than the window by default?

**Options**

- A. No; default is strictly the last 3 days.
- B. Yes; show all active jobs, with new ones highlighted.

**Recommended:** A, with a visible toggle. The requirement is a 3-day window;
the toggle handles quiet days.

## 12. Do you want a CLI refresh command?

**Options**

- A. Yes, for development and smoke tests (same code path as the UI).
- B. No; UI only.

**Recommended:** A. It makes parser development and troubleshooting much easier,
and it does not add a scheduler.

## Decision log

Answers received on 2026-11-11:

| Question | Decision | Date |
| --- | --- | --- |
| 1. Role scope | **Engineering/technical only** | 2026-11-11 |
| 2. Language scope | **Both English and Japanese, with language tags** | 2026-11-11 |
| 3. 3-day semantics | **Original source posting date** (`posted_at`) | 2026-11-11 |
| 4. Location scope | **All Japan; remote is OK, but no international remote** | 2026-11-11 |
| 5. UI stack | **FastAPI + Jinja2 + vanilla JS** | 2026-11-11 |
| 6. Cross-source dedup | **One row per source in v1** | 2026-11-11 |
| 7. Authenticated source | **No; public sources only** | 2026-11-11 |
| 8. Deployment | Default local only (`127.0.0.1`) | proposed |
| 9. Salary display | Source text + parsed annual JPY when available | proposed |
| 10. User-Agent | `JDashboard/0.1 (personal job dashboard; +http://127.0.0.1:8000)` | proposed |
| 11. Older jobs default | Strict 3-day default, with a 7/30/all toggle | proposed |
| 12. CLI refresh | Yes, for development and smoke tests | proposed |

### Relocation follow-up

The user said: "I need to shift to Japan and work." That implies relocation and
possibly visa sponsorship. The plan now includes:

- `visa_sponsorship` and `overseas_eligible` fields.
- A UI filter/badge for "open to overseas applicants" and "visa sponsorship".
- A default that does **not** hide jobs just because they require Japanese
  residency, but makes the requirement obvious.

**Resolved 2026-11-11:** keep the default sort **newest first** and surface
relocation information as **badges** (`Visa support`, `Overseas OK`, `Japan
residents only`). Do not reorder jobs by visa/overseas eligibility by default.

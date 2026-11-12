# Implementation Tasks

These task briefs are written for an AI coding agent (or a human) to execute one
phase at a time. Each brief is self-contained but assumes the master plan and
topic docs have been read.

## Workflow

1. Read `PLAN.md` and the relevant topic doc.
2. Pick the next uncompleted task.
3. Create a branch or worktree if desired.
4. Implement, test, and update docs.
5. Run `ruff check .` and `pytest`.
6. Report: files changed, tests run, open risks.

## Task order

| # | Task | Depends on | Status |
| --- | --- | --- | --- |
| 01 | [Foundation](01-foundation.md) | — | done |
| 02 | [Scraper framework](02-scraper-framework.md) | 01 | done |
| 03 | [Michael Page scraper](03-source-michael-page.md) | 02 | done |
| 04 | [JapanDev scraper](04-source-japan-dev.md) | 02 | done |
| 05 | [TokyoDev scraper](05-source-tokyo-dev.md) | 02 | done |
| 06 | [Daijob scraper](06-source-daijob.md) | 02 | done |
| 07 | [Robert Half scraper](07-source-robert-half.md) | 02 | done |
| 08 | [Refresh service + UI](08-refresh-and-ui.md) | 02 | done |
| 09 | [Hardening and docs](09-hardening.md) | 03–08 | done |

Later work (UI polish, Docker packaging, the source-onboarding workflow) was
tracked in [`../roadmap.md`](../roadmap.md); those items are also complete.
The open, optional items are the Phase 6 entries in the roadmap.

## Definition of done for every task

- Code follows the existing style and structure.
- New behavior has tests.
- No live network in tests.
- No secrets or credentials.
- `ruff check .` passes.
- `pytest` passes.
- Relevant docs are updated.
- The task report lists what was done and what remains.

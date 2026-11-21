# Build History

How this project was built, phase by phase, and why it looks the way it does.
Read this when you want the reasoning behind the current code rather than the
current interface.

Each file covers one phase: the goal, the decisions taken, what was built, the
traps that were hit, and how to verify the result.

| File | Phase | Outcome |
| --- | --- | --- |
| [00-overview.md](00-overview.md) | — | The whole build in one page |
| [01-foundation.md](01-foundation.md) | Phase 0 | Decisions, scaffold, tooling |
| [02-data-and-api.md](02-data-and-api.md) | Phase 1 | SQLite models, repository, query API |
| [03-scraper-framework.md](03-scraper-framework.md) | Phase 2 | Scraper contract, polite HTTP client, refresh service |
| [04-scrapers.md](04-scrapers.md) | Phase 3 | The five launch sources and their quirks |
| [05-ui.md](05-ui.md) | Phase 4 | The web UI, filters, refresh panel |
| [06-hardening.md](06-hardening.md) | Phase 5 | Scripts, logging, expiry handling, docs |
| [07-ai-workflow.md](07-ai-workflow.md) | Phase 6 | The agent workflow for adding sources |
| [08-open-options.md](08-open-options.md) | — | What is deliberately not built yet |

## How to use these documents

- **New to the project?** Read [00-overview.md](00-overview.md), then the
  repository `AGENTS.md`, then the topic doc for your task.
- **Changing a scraper?** [04-scrapers.md](04-scrapers.md) lists the per-source
  traps that have already bitten this codebase.
- **Touching the refresh path?** [03-scraper-framework.md](03-scraper-framework.md)
  explains the lock, the progress model, and the durable records.
- **Planning work?** [08-open-options.md](08-open-options.md) lists what is
  deliberately deferred and why.

The living specifications live next to this folder: `docs/architecture.md`,
`docs/data-model.md`, `docs/scrapers.md`, `docs/sources.md`, `docs/ui.md`,
`docs/operations.md`, `docs/verification.md`, and `docs/decisions.md`.

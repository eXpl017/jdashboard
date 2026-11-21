# Pipeline detail

Each phase lists its inputs, the work, the artifact it produces, and the gate
that must pass before the next phase starts.

## Phase 1 — Research

**Owner:** `source-researcher` subagent.

**Inputs:** source name or URL. Optionally `docs/sources.md` (to avoid
duplicating an existing source) and the deferred-sources list.

**Work**

1. Confirm the source is not already implemented.
2. Fetch `robots.txt` and record the result for the exact listing and detail
   paths.
3. Fetch one listing page and one detail page with a plain HTTP client.
4. Note pagination, date field and granularity, salary format, remote wording,
   employment type, Japanese level, and any visa/overseas statement.
5. Estimate volume and how often new security roles appear.

**Artifact:** `docs/research/<source>.md` using the template in the
subagent prompt.

**Gate:** verdict `implement`.

## Phase 2 — Brief

**Owner:** main agent.

**Work**

1. Write the `docs/sources.md` section: URLs, date semantics, language(s),
   visa/overseas wording, remote wording, quirks, health expectation.
2. Expand `docs/research/<source>.md` with:
   - Goal
   - Inputs (listing/detail URLs, robots finding)
   - Acceptance criteria
   - Files to create or touch
3. Add the adopted summary and a row to the source matrix in `docs/sources.md`.

**Artifact:** the research brief and the `docs/sources.md` summary.

**Gate:** the brief names every field the scraper is expected to fill and the
date semantics it must use.

## Phase 3 — Implement

**Owner:** `scraper-builder` subagent.

**Work**

1. Save listing and detail fixtures under `tests/fixtures/<source>_*`.
2. Implement `app/scrapers/<source>.py`.
3. Add `tests/test_<source>.py` with parser tests and at least one edge case
   (missing salary, Japanese title, remote, expired, or missing date).
4. Run `uv run ruff check .` and `uv run pytest`.

**Artifact:** scraper module, fixtures, tests.

**Gate:** suite green, tests never touch the network.

## Phase 4 — Integrate

**Owner:** `source-integrator` subagent.

**Work**

1. `enable_<source>` in `app/config.py` and `.env.example`.
2. Register the scraper in `app/scrapers/registry.py`.
3. Add the per-source section to `docs/scrapers.md` and the source to the
   `README.md` list.
4. Run `uv run ruff check .` and `uv run pytest`.
5. Live smoke: `uv run python -m scripts.inspect_source <source> --limit 3`.

**Artifact:** wired source, green suite, smoke output.

**Gate:** the live smoke returns parsed jobs with sane titles, companies, dates,
and URLs.

## Phase 5 — Review

**Owner:** `qa-reviewer` subagent over the diff.

**Work:** fix every Blocker and High finding, then re-run the suite and the
smoke test.

**Artifact:** findings resolved.

## Phase 6 — Report

**Owner:** main agent.

Report the source, robots evidence, files changed, fixtures added, test and
smoke results, and open risks. Mention anything deliberately left out (for
example a source disabled by default because it returned 0 jobs).

## Useful commands

```bash
# Live scrape of one source; prints parsed jobs and never writes to the DB
uv run python -m scripts.inspect_source <source> --limit 3

# Live refresh of one source into the local database
uv run python -m scripts.refresh --source <source> --window-days 3

# Suite and lint
uv run pytest
uv run ruff check .
```

## When a phase fails

- **Blocked by robots, login, or anti-bot:** stop the pipeline, write the
  evidence into the research brief, and report `defer` or `reject`. Do not
  attempt a workaround.
- **Zero candidates but no error:** the listing layout probably changed.
  Compare the live page with the fixture, fix the parser, add a regression
  test.
- **403/429:** stop. Lower the request rate or disable the source via
  `ENABLE_<SOURCE>=false` and document it.
- **Dates wrong:** the source is probably JST date-only. Normalize date-only
  values to JST midnight and store UTC; keep `posted_at` and `source_updated_at`
  separate.

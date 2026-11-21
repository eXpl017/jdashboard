# Phase 5 — Hardening, scripts, logging, and expiry handling

**Goal:** make the app operable by someone other than its author, and prove the
operational scripts and logging behave as documented.

## What was built

### Developer CLI (`scripts/`)

- `scripts/refresh.py` — runs the same refresh service as the UI and prints a
  JSON summary. `--window-days`, `--source`.
- `scripts/inspect_source.py` — scrapes one source and prints the parsed
  jobs. **It never writes to the database.**
- `scripts/check_port.py` — pre-flight port check used by `make run`.

All three are run as modules (`python -m scripts.refresh`), because running
the file directly puts `scripts/` — not the project root — on `sys.path`.

### Structured logging (`app/logging_config.py`)

One JSON object per line: `ts`, `level`, `logger`, `message`, and `exc` when
a traceback is attached. The app installs it in the lifespan; the CLI scripts
install it in `main()`. Before this, script output was plain text while the
app's was JSON — the first CLI run exposed the inconsistency.

### Expiry handling

Listings whose `expires_at` has passed are stored with `is_active = 0` and
drop out of the default view. The refresh service sets the flag when building
the job, and the repository propagates it on update instead of unconditionally
resurrecting the row.

### Documentation

`docs/operations.md` (runbook), `docs/verification.md` (playbook),
`docs/decisions.md` (ADRs), `docs/data-model.md`, `docs/scrapers.md`,
`docs/sources.md`, `docs/ui.md`.

## What the operational checks found

Running the operational checks for real (rather than trusting the scripts)
surfaced two bugs that unit tests had missed:

1. `scripts/inspect_source.py` passed a **naive** UTC cutoff, so every
   scraper raised `can't compare offset-naive and offset-aware datetimes`.
2. CLI logs were plain text while the app's were JSON.

Both were fixed, with tests (`tests/test_scripts.py`, `tests/test_logging.py`).

## Live refresh record

A full five-source refresh with the default 3-day window: `status=success`,
~2m04s, 36 new jobs, 2 expected Michael Page detail 404s. The runtime is
throttle-bound, not compute-bound.

## How to verify

```bash
uv run pytest -q && uv run ruff check .
uv run python -m scripts.check_port.py 8001
uv run python -m scripts.inspect_source michael_page --limit 3
```

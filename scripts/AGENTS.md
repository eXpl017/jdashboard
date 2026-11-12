# AGENTS.md — `scripts/`

Command-line entry points. They are thin wrappers around the same services the
web app uses, so they must stay behaviourally identical to the UI.

| Script | Purpose | Writes the DB? |
| --- | --- | --- |
| `scripts/refresh.py` | Run a manual refresh (one source or all) | yes |
| `scripts/inspect_source.py` | Scrape one source and print the parsed jobs | **no** |
| `scripts/check_port.py` | Pre-flight check that a port is free | no |

## Rules

- **Run them as modules**: `uv run python -m scripts.refresh`, never
  `uv run python scripts/refresh.py` (the package import would fail).
- Every script must call `configure_logging()` so its output is JSON like the
  app's.
- Exit codes: `0` on success, `1` on failure (or `partial` for
  `inspect_source` when a source reported errors), `2` for bad arguments
  (`parser.error`).
- Print machine-readable JSON to stdout; send human hints to stderr.
- `inspect_source.py` must **never** write to the database.
- Cutoffs passed to scrapers must be **timezone-aware UTC**
  (`datetime.now(UTC) - timedelta(days=...)`); a naive datetime breaks the
  scrapers' comparisons.
- Validate `--window-days` / `--days` to the 1–30 range the API accepts.
- Document new flags in `docs/operations.md` and the README.

## Commands

```bash
uv run python -m scripts.refresh --window-days 3
uv run python -m scripts.refresh --source japan_dev --window-days 3
uv run python -m scripts.inspect_source michael_page --limit 3
uv run python scripts/check_port.py 8001
```

In the container:

```bash
sg docker -c "docker compose exec -T dashboard python -m scripts.refresh --source japan_dev --window-days 3"
```

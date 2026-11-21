# Phase 0 — Foundation

**Goal:** settle the open questions, then scaffold the project so every later
phase is mechanical.

## Decisions taken

Recorded as ADRs in `docs/decisions.md`:

- FastAPI + Jinja2 + vanilla JS, SQLite + SQLAlchemy 2.0, httpx + BeautifulSoup
  + JSON-LD (ADR-001, ADR-002).
- Manual refresh only; public pages only; no login or CAPTCHA bypass
  (ADR-003, ADR-004).
- One row per source listing; the window uses the source's posting date
  (ADR-005, ADR-006).
- Plain HTTP and JSON-LD, no headless browser in v1 (ADR-007).
- No dashboard authentication; bind to localhost (ADR-008).
- Per-source error isolation (ADR-009).
- Store descriptions as text and HTML (ADR-010).
- Configurable per-source enable flags (ADR-011).
- Technical-only default with stored role categories (ADR-012).
- Language tagging, no translation (ADR-013).
- Japan-only scope, including remote within Japan (ADR-014).

## What was built

- `pyproject.toml` with runtime and dev dependencies, `ruff` and `pytest`
  configuration (line length 100, `asyncio_mode = auto`).
- `uv.lock` — the dependency set is reproducible; dependencies are installed
  from it.
- `Makefile` with `install`, `run`, `test`, `lint`, `format`, and `verify`
  targets.
- `.env.example` and `.gitignore` (`.env`, `data/`, `logs/`, caches).
- The `app/` package skeleton, `app/config.py` with `Settings`, and
  `app/main.py` with a health route and a lifespan that creates the schema.
- A first test (`tests/test_health.py`) so the toolchain was proven before
  any feature code.

## Traps hit

- The default `Settings` object is created at import time. That is fine for a
  local single-user app, but it means `.env` is read once per process.
- `pydantic-settings` ignores unknown environment variables by default, which
  is what lets operational settings live in `.env`.

## How to verify

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
curl -s http://127.0.0.1:8001/health
```

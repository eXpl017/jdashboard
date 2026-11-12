# AGENTS.md — `tests/`

pytest suite. **Tests must never touch the network** — that is what proves the
parsers are deterministic.

## Layout

```text
tests/
  conftest.py        shared fixtures: in-memory SQLite session, TestClient, make_job
  fixtures/          committed HTML/JSON samples (one file per source per page type)
  test_<area>.py     one file per area: api, repository, refresh, http, ui, logging…
```

## Rules

- Use `respx` to mock HTTP, or parse a committed fixture. A test that reaches
  the internet is a bug.
- Fixtures are committed and kept small. Trim CSS/JS payloads but keep the
  structures the parser reads. Do not paste a full page with personal data.
- One behaviour per test; name it after the behaviour
  (`test_daijob_parses_japanese_detail_without_jsonld`).
- Assert on exact values (dates, salary numbers, role category, language), not
  just truthiness.
- Cover the edge cases that break scrapers: missing salary, missing date,
  Japanese title, remote wording, expired listing, missing JSON-LD, a 404
  detail page, a source that returns zero candidates.
- The default filters matter: a job must not leak into the default
  `role=technical` + `location_scope=japan` view by accident.
- Keep the suite offline-capable: `uv run pytest -q` must pass with the
  machine disconnected.

## Fixtures

- `tests/fixtures/<source>_list.html`, `<source>_detail.html`, … — the same
  naming the scraper tests expect.
- When a source's layout changes, update the fixture **and** the parser in the
  same commit, and add a regression test for the new shape.
- `tests/fixtures/` is committed (not gitignored) — it is the source of truth
  for the parsers.

## Useful fixtures

- `session` — in-memory SQLite with the schema created.
- `client` — `TestClient` with `get_session` overridden to that session.
- `make_job(**overrides)` — a `Job` with sensible defaults; override
  `role_category`, `location_scope`, `posted_at`, `security_tags`, … to build
  the case you need.

## Commands

```bash
uv run pytest -q                     # everything
uv run pytest tests/test_daijob.py -q
uv run pytest -q -k "fingerprint"    # by name
uv run ruff check .
```

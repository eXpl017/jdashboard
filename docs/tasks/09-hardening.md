# Task 09 — Hardening, Tests, and Documentation

## Goal

Make the dashboard reliable, observable, and easy to maintain.

## Read first

- `docs/operations.md`
- `docs/scrapers.md`
- `docs/roadmap.md`

## Deliverables

### Reliability

- Per-source timeouts and request caps.
- Retry/backoff tests.
- Robots-disallowed test.
- Graceful handling of a source returning 0 candidates.
- Graceful handling of a source returning malformed JSON/HTML.
- Ensure a failed source does not roll back successful sources.
- Ensure the refresh lock is released on every code path.

### Tests

- Parser edge cases for all five sources:
  - missing salary
  - Japanese title/description
  - remote
  - expired
  - malformed JSON-LD
- Repository:
  - duplicate fingerprint
  - update preserves `first_seen_at`
  - inactive/expired behavior
- API:
  - filters
  - pagination
  - 404 for unknown job
  - 409 for concurrent refresh
- Refresh:
  - success
  - partial
  - failed
  - progress transitions

### Scripts

- `scripts/refresh.py`:
  - `--source`, `--window-days`, `--dry-run`
  - same code path as UI
- `scripts/inspect_source.py`:
  - `source`, `--limit`
  - prints parsed jobs, never writes

### Documentation

- Complete `README.md` quick start.
- Complete `docs/operations.md`.
- Add a "how to add a source" walkthrough.
- Record the live smoke test results.
- Note any source-specific quirks discovered during implementation.

### Security review

- No secrets in the repo.
- No cookies or credentials in logs.
- No raw HTML rendered in the UI.
- No bypass logic for CAPTCHAs/Cloudflare.
- `robots.txt` checked at runtime.
- User-Agent is clear.
- Rate limits are enforced.

## Acceptance

- [ ] Full refresh completes in under 60 seconds on a normal connection.
- [ ] One broken source yields `partial`.
- [ ] `pytest` and `ruff check .` pass.
- [ ] No live network in tests.
- [ ] README works from a clean environment.
- [ ] Database survives restart.
- [ ] No secrets or unsafe HTML rendering.
- [ ] Source health is visible in the UI.

## Notes

- Do not add a scheduler to "make it easier".
- Do not add a source that requires login/CAPTCHA bypass without an explicit
  decision and documentation.
- Prefer small, focused commits.

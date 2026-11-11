# Task 08 — Refresh Service and UI

## Goal

Finish the manual refresh experience and build the minimal dashboard UI.

## Read first

- `docs/ui.md`
- `docs/architecture.md`
- `PLAN.md` (refresh behavior)

## Deliverables

### Backend

- Ensure `POST /api/refresh` and `GET /api/refresh/status` are complete.
- Ensure `GET /api/jobs`, `/api/stats`, and `/api/sources` support the UI.
- Add a `GET /` route that renders `templates/index.html`.
- Mount `static/`.

### Templates

- `app/templates/base.html`:
  - meta, title, CSS link, JS defer
  - header/footer blocks
- `app/templates/index.html`:
  - header + refresh button
  - summary cards
  - filter bar
  - job list container
  - refresh status panel
  - empty/error templates or hidden elements

### CSS

- `app/static/app.css`:
  - variables, reset, layout, cards, badges, filters, job rows
  - light/dark via `prefers-color-scheme`
  - responsive breakpoints
  - focus-visible styles

### JS

- `app/static/app.js`:
  - load jobs/stats/sources/status
  - debounce filters
  - `AbortController` for stale requests
  - refresh + poll every 1 s
  - render job rows and source status
  - safe text rendering (no `innerHTML` with untrusted content)
  - relative time formatting

## Acceptance

- [ ] Empty state is clear.
- [ ] Refresh shows per-source progress.
- [ ] New jobs appear without a full page reload.
- [ ] Filters work: q, source, role type, language, location, location scope,
      remote, visa/overseas, tag, window, sort.
- [ ] Default view is technical-only and excludes international remote.
- [ ] Language, visa, and overseas badges render when known and are omitted
      when unknown.
- [ ] A source error is visible and does not hide other jobs.
- [ ] Refresh button disabled while running; `409` handled.
- [ ] Keyboard navigation and labels work.
- [ ] No external JS/CSS dependencies.
- [ ] No scheduler or automatic scrape.

## Notes

- Keep the UI minimal; do not add a chart library.
- Render job descriptions as text, not raw HTML, in v1.
- Use `aria-live="polite"` for refresh status.
- Test with an empty DB and with fixture data.

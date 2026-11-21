# Phase 3 — The five launch sources

**Goal:** one scraper per launch source, each with a fixture, a parser test,
and a live smoke result. The per-source notes in `docs/scrapers.md` are the
operational reference; this page is the history.

## The sources and what made each one different

| Source | Shape | What made it hard |
| --- | --- | --- |
| Michael Page Japan | Category page + detail pages, JSON-LD | JSON-LD `description` contains literal newlines (needs `json.loads(..., strict=False)`); detail pages 404 for expired listings |
| JapanDev | Landing page + per-company detail pages | `applicantLocationRequirements` decides whether foreigners may apply; English/JSON-LD listings |
| TokyoDev | Category listing + company detail pages | `identifier.value` holds the job id; the page carries remote/overseas/Japanese-level labels; an Atom feed is the fallback when the listing yields no links |
| Daijob | Category page + keyword searches + detail pages | The category redirects to a search URL; the HTML `Activated`/`Updated` labels are authoritative for dates, JSON-LD is enrichment only; Japanese detail pages |
| Robert Half Japan | SPA payload with embedded JSON | `initialResults` JSON is escaped; pagination overlaps slightly; the detail page repeats the data in `jobDetails` |

## Discovery decisions

- **Daijob** uses the Security System SE category first, then two curated
  keyword searches to fill the remaining detail budget. Broad keyword search
  alone is noisy.
- **Robert Half** is a broad recruiter: its live snapshot was mostly finance,
  HR and legal roles, and its security roles were GRC/consulting. Those rows
  are stored and hidden by the default technical filter — that is expected,
  not a bug.
- **Robert Half** uses the listing `description` as the primary description
  and only fetches the detail page when both description and summary are
  under 80 characters, capped at 10 detail requests.
- **Robert Half** maps non-Japan remote to `international_remote` and
  non-Japan on-site to `unknown`.

## Rules the scrapers follow

- Prefer JSON-LD, fall back to stable HTML selectors.
- Respect `max_detail_requests`; Daijob and TokyoDev use 40, Michael Page 25,
  Robert Half 10.
- Strip tracking pixels and active content (`img`, `script`, `iframe`,
  `object`, `embed`) from stored HTML.
- Store non-technical and international-remote rows; the UI filters them.
- Set `overseas_eligible` / `visa_sponsorship` only from explicit text.

## Live smoke results at the time of writing

| Source | Found | In 30-day window | Skipped | Errors |
| --- | --- | --- | --- | --- |
| Michael Page | 22 | 6 | 14 | 2 (404 detail pages) |
| JapanDev | 36 | 12 | 24 | 0 |
| TokyoDev | 9 | 2 | 7 | 0 |
| Daijob | 60 | 33 | 7 | 0 |
| Robert Half | 123 | 81 | 39 | 0 |

A full five-source refresh takes roughly **two minutes**, dominated by the
one-request-per-second-per-host throttle, not by parsing.

## Traps hit

- Two different "remote" meanings: "remote within Japan" is `japan_remote`;
  "work from anywhere" is `international_remote`.
- Agency vs employer: recruiters sometimes put the agency in
  `hiringOrganization`; do not present the agency as the client.
- An English URL does not mean an English listing — Daijob and Michael Page
  serve `/en/` pages with Japanese detail text. Detect language from the text.

## How to verify

```bash
uv run pytest tests/test_michael_page.py tests/test_japan_dev.py \
  tests/test_tokyo_dev.py tests/test_daijob.py tests/test_robert_half.py -q
uv run python -m scripts.inspect_source michael_page --limit 3
```

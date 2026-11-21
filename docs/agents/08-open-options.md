# Open options

What is deliberately **not** built yet, and what it would take. None of this is
required for the dashboard to do its job.

## Cross-source deduplication

The same role is often posted on several boards. Today each board gets its
own row (ADR-005), which keeps provenance honest but shows duplicates.

To add it: group by a normalised title + company + location signature, keep
the earliest `first_seen_at` as the primary row, and link the others. Do it
as a *view* first — it is reversible, unlike merging rows.

## Export

CSV and JSON export of the current filter selection. The list endpoint
already returns everything the export needs (`GET /api/jobs` with the same
query parameters), so this is mostly an endpoint plus a UI button.

## Saved filter presets

The filter state already lives in the URL query string. Presets would store
named parameter sets locally — in the browser, not the server, because the
app has no user accounts.

## More sources

Candidates and their state are tracked in `docs/sources.md`:

| Candidate | State |
| --- | --- |
| Wantedly | Deferred — listings come from an internal GraphQL endpoint; research brief in `docs/research/wantedly.md` |
| JobsInJapan | Deferred — see `docs/sources.md` |
| LinkedIn / Indeed | Rejected — login required |
| GaijinPot | Deferred — would need a headless browser, which v1 forbids (ADR-007) |

Use `/add-source <name>` to evaluate and implement one.

## Alembic migrations

The schema is created with `Base.metadata.create_all()` at startup. That is
fine for a local app that recreates its database freely, but it cannot express
a column rename on an existing database. Alembic would be the fix if the
schema ever needs to change in place.

## Japanese translation and summaries

Listing descriptions are stored as-is, with a `language` tag and a language
filter (ADR-013). Translation was consciously left out: an LLM in the loop
would add cost, latency, and a hallucination risk to a tool whose value is
that the text is verbatim from the source.

## Daily digest and scheduler

The app never scrapes on its own (ADR-003). A daily digest would need a
scheduler, which contradicts that decision — it would have to be a separate,
explicitly configured job (cron calling `scripts/refresh.py`, for example)
rather than something the dashboard does on its own.

## Authentication

There is none (ADR-008), and the app binds to localhost. Exposing it to a
network needs a reverse proxy with authentication and TLS in front of it.

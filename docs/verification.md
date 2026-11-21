# Verification Playbook

How to run the dashboard and check that it behaves. Every command here is
copy-pasteable **from the repository root** (`/home/expl017/projects/jdashboard`):

```bash
cd /home/expl017/projects/jdashboard
```

The root matters: `make` needs the `Makefile`, `uv run python -m scripts...` needs
the `app/` and `scripts/` packages on the path, and `sqlite3 data/jobs.db` uses a
path relative to it.

The browser checks in §2 can be run by an agent with the `/verify-ui` command
(the `ui-verification` skill), which drives a real browser against the host dev
server at `127.0.0.1:8001`. They are also covered by the automated Playwright
suite in `tests/browser/` (`uv run pytest -m ui -q`), which runs against a
throwaway local server with a seeded temporary database and never scrapes live
job sites.

## 0. Choose how to run it

The dashboard runs as a local development server.

| | Start | URL | Database | Logs |
| --- | --- | --- | --- | --- |
| Local development server | `make run` | http://127.0.0.1:8001 | `./data/jobs.db` | terminal output |

**No port conflicts:** the development server uses port 8001. `make run` checks
the port before starting and prints an actionable message if it is taken:

```bash
make run                      # port 8001
make run DEV_PORT=8002        # pick another port
uv run python scripts/check_port.py 8001   # check any port
```

First-time setup (host):

```bash
uv sync --extra dev
cp .env.example .env
```

## 1. Quick health check

Set `BASE` to the host development server you are checking:

```bash
BASE=http://127.0.0.1:8001

curl -s $BASE/health          # {"status":"ok","version":"0.1.0"}
curl -s -o /dev/null -w '%{http_code}\n' $BASE/              # 200 (HTML)
curl -s -o /dev/null -w '%{http_code}\n' $BASE/static/app.css   # 200
curl -s -o /dev/null -w '%{http_code}\n' $BASE/static/app.js    # 200
```

Interactive API docs: `$BASE/docs` (Swagger), `/redoc`, and `/openapi.json`.

## 2. What to check in the browser

Open <http://127.0.0.1:8001/> (development server).

**Layout and chrome**

- [ ] Header shows the title, the subtitle, and "Last refresh: …" (or "never").
- [ ] Four summary cards render: Jobs, New in window, Sources, Last run.
- [ ] The filter bar shows: Search, Source, Role, Language, Location,
      Location scope, Remote, Visa/eligibility, Tag, Window, Sort, "Include
      older listings", and "Clear filters".
- [ ] Job cards show title (as a link), company, location, salary, source
      name, and a relative posted time.
- [ ] The refresh panel at the bottom lists each source with its status.

**Filters (each should update the list without a page reload)**

- [ ] Role: "Technical (engineering / operations)" is the default. Switching to
      "All roles" reveals GRC, consulting, sales and management rows.
- [ ] Location scope: "Japan (default)" hides `international_remote`; pick
      "International remote" to see them.
- [ ] Window: 3 / 7 / 30 days / All active changes the result count.
- [ ] Source, Language, Remote, Visa/eligibility, Tag and Sort all narrow or
      reorder the list.
- [ ] "Clear filters" returns everything to the defaults.
- [ ] The URL keeps the filters (shareable / reload-safe).

**Refresh flow**

- [ ] Click **Refresh now**: the button disables and shows "Refreshing…".
- [ ] The refresh panel shows per-source progress (pending → running →
      success/error) and counts (found, new, updated, skipped, errors).
- [ ] When the run finishes, the button re-enables, the summary cards update,
      and the job list reloads **without a full page reload**.
- [ ] A second refresh while one is running is refused (no duplicate run).

**States and accessibility**

- [ ] Empty state: search for something impossible (e.g. `zzzz`) → "No jobs
      found" plus a reason (window, role, location scope).
- [ ] Loading state is visible while a filter change is in flight.
- [ ] Keyboard only: `Tab` reaches the skip link, every filter, the refresh
      button, and each job link; `Enter` toggles a job's Details disclosure.
- [ ] Badges: language, remote, location scope, "Overseas eligible",
      "Japan residents only", and "Visa support" appear only when known; "New"
      appears for newly seen jobs.
- [ ] Dark mode: in devtools, emulate `prefers-color-scheme: dark` → the page
      follows.
- [ ] Narrow window (mobile width) → filters stack, cards stay readable.

## 3. API checks (expected behaviour)

```bash
BASE=http://127.0.0.1:8001

# Defaults: role=technical, location_scope=japan, days=3
curl -s '$BASE/api/jobs' | python3 -m json.tool | head -40

# Widen the role and location filters: more rows than the default query
curl -s '$BASE/api/jobs?role=all&location_scope=all' | python3 -c \
  'import json,sys; print("total:", json.load(sys.stdin)["total"])'

# Per-source counts and the last run
curl -s '$BASE/api/stats' | python3 -m json.tool

# Source metadata and health
curl -s '$BASE/api/sources' | python3 -m json.tool

# Unknown job -> 404
curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/jobs/999999

# Start a refresh -> 202; a second one while running -> 409
curl -s -X POST $BASE/api/refresh \
  -H 'Content-Type: application/json' -d '{"window_days":3}'

# Progress
curl -s $BASE/api/refresh/status | python3 -m json.tool
```

Things to look for:

- [ ] `items[].source_name` is a friendly name ("Michael Page Japan"), not an
      ID.
- [ ] `posted_at` is UTC with a `Z` suffix.
- [ ] `total` matches the number of jobs shown for the active filters.
- [ ] `/api/stats` totals agree with `/api/jobs` for the same filters.
- [ ] `/api/sources` shows `last_status` and `last_success_at` per source.

## 4. Refresh from the CLI

```bash
# Live scrape of one source; prints parsed jobs and writes nothing to the DB
uv run python -m scripts.inspect_source michael_page --limit 3

# Live refresh of one source into the local database
uv run python -m scripts.refresh --source japan_dev --window-days 3
```

Expect JSON log lines plus a final JSON summary with per-source counts.

## 5. Database checks (SQLite)

Host database: `./data/jobs.db`.

```bash
sqlite3 data/jobs.db ".tables"

# Rows per source
sqlite3 data/jobs.db "SELECT source, COUNT(*) FROM jobs GROUP BY source;"

# No duplicate fingerprints
sqlite3 data/jobs.db \
  "SELECT fingerprint, COUNT(*) c FROM jobs GROUP BY fingerprint HAVING c > 1;"

# Expired listings are inactive
sqlite3 data/jobs.db "SELECT COUNT(*) FROM jobs WHERE is_active = 0;"

# Recent runs and per-source results
sqlite3 data/jobs.db "SELECT id, status, window_days, total_found, total_new, total_errors FROM scrape_runs ORDER BY id DESC LIMIT 5;"
sqlite3 data/jobs.db "SELECT source, status, found, new, skipped, errors FROM scrape_source_results ORDER BY id DESC LIMIT 10;"
```

Expected: the duplicate-fingerprint query returns no rows.

## 6. Tests and lint

```bash
uv run pytest -q          # default offline suite (network-free; UI browser tests excluded)
uv run pytest -m ui -q    # automated browser UI tests (Playwright, throwaway local server)
uv run ruff check .
uv run ruff format --check .
```

First-time browser test setup:

```bash
uv sync --extra dev
uv run playwright install chromium
```

The default suite must pass with the machine offline; that is what proves the
tests do not hit the live network. The browser UI suite is marked `ui`, starts a
seeded temporary server on a free local port, and must not scrape live job
sites.

## 7. Compliance spot-checks

- [ ] User-Agent is set in `.env` (`USER_AGENT=…`) and used for every request.
- [ ] robots.txt is honoured at runtime: a disallowed path makes the source
      report `skipped` (see `last_status` in `/api/sources`), never an error.
- [ ] No scraping at startup: restart the app and watch the logs — no outbound
      requests until you press Refresh.
- [ ] No secrets in the repo:
      `grep -rniE 'api[_-]?key|secret|password|bearer' --include='*.py' --include='*.md' . | grep -v '.venv'`
      (only harmless matches in `app/services/normalize.py` and the docs).
- [ ] `.env` and `data/` are gitignored: `git check-ignore -v .env data/jobs.db`.

## 8. Troubleshooting

| Symptom | Check | Fix |
| --- | --- | --- |
| "Address already in use" | `uv run python scripts/check_port.py <port>` | stop the other process, or `make run DEV_PORT=<other>` |
| Empty list, no errors | `curl .../api/refresh/status` | widen the Window filter, or press Refresh |
| Refresh button stuck disabled | `curl .../api/refresh/status` | a run is still active; restart the app to clear the in-memory lock |
| `pytest` fails after a source change | `uv run pytest -q` | a fixture or parser expectation needs updating |

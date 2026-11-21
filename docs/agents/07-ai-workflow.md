# Phase 6 — The AI-assisted source workflow

**Goal:** make "add this job board" a one-line request, so a new source can be
brought in without re-deriving the workflow each time.

## What was built

```text
/add-source <source>            # command
  └─ source-onboarding skill    # phases, gates, handoffs
       ├─ source-researcher     # robots/terms research -> docs/research/<source>.md
       ├─ (brief)               # adopted summary -> docs/sources.md
       ├─ scraper-builder       # app/scrapers/<source>.py + fixtures + tests
       ├─ source-integrator     # enable flag, registry, docs, suite, live smoke
       └─ qa-reviewer           # findings on the finished diff
```

`/research-source <source>` stops after the research phase.

- **Commands** (`.opencode/commands/`) — the user-facing entry point.
- **Skills** (`.opencode/skills/`) — `source-onboarding` (the whole workflow),
  `scraper-authoring` (the parser checklist), `dashboard-qa` (the review
  checklist).
- **Subagents** (`.opencode/agents/`) — one owner per phase, each with
  explicit file permissions so two agents cannot fight over the same file.

## Why the split

Each subagent owns files the others must not touch:

| Agent | Owns | Must not edit |
| --- | --- | --- |
| `source-researcher` | `docs/research/**`, `docs/sources.md` | any code |
| `scraper-builder` | `app/scrapers/**`, `tests/**` | `app/config.py`, `.env.example`, `README.md` |
| `source-integrator` | `app/config.py`, `registry.py`, `.env.example`, docs, README | the scraper internals |
| `qa-reviewer` | nothing (read-only) | everything |

`source-integrator` existed because the original `scraper-builder` was scoped
to `app/scrapers/**` and could not touch the enable flag, the registry, or the
README — the wiring had no owner.

## The gates

The workflow refuses to continue on a bad source: the research phase must
return a verdict of `implement` before any code is written. A blocked source
(login, CAPTCHA, robots disallow, anti-bot) is documented and deferred, never
worked around.

## Validation

Every asset is checked with a strict-YAML frontmatter parse. That check found
a real bug: the `source-researcher` description contained an unquoted colon,
which strict YAML rejects.

## Known limitation

Subagent runs that use tools need provider quota. When the free tier is
exhausted, the research phase can be run directly by the main agent and the
artifact is written in the same format.

## How to verify

```bash
uv run --with pyyaml python - <<'PY'
import pathlib, yaml
root = pathlib.Path(".opencode")
for path in list(root.glob("agents/*.md")) + list(root.glob("skills/*/SKILL.md")) + list(root.glob("commands/*.md")):
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---\n", 3)
    yaml.safe_load(text[4:end])
    print(path, "ok")
PY
```

Then run `/research-source <candidate>` and confirm the brief appears in
`docs/research/`.

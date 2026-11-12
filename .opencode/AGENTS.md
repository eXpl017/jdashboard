# AGENTS.md — `.opencode/`

AI-assistant assets for this repository: commands, skills, and subagents. They
encode the workflow that built the project so it can be repeated.

```text
.opencode/
  commands/          slash commands (.md) -> /add-source, /research-source
  skills/            SKILL.md bundles the model can load on demand
    source-onboarding/   end-to-end "add a source" workflow
    scraper-authoring/   parser-level checklist and field mapping
    dashboard-qa/        review checklist
  agents/            subagents (.md) with their own permissions
    source-researcher/   research + brief (no code)
    scraper-builder/     scraper + fixtures + tests
    source-integrator/   config, registry, docs, suite, live smoke
    qa-reviewer/         read-only review of a diff
```

## How they fit together

```text
/add-source <source>
  └─ source-onboarding skill (phases, gates, handoffs)
       ├─ source-researcher   -> docs/research/<source>.md
       ├─ (brief)             -> docs/sources.md + docs/tasks/<NN>-source-<source>.md
       ├─ scraper-builder     -> app/scrapers/<source>.py + fixtures + tests
       ├─ source-integrator   -> config flag, registry, docs, green suite, live smoke
       └─ qa-reviewer         -> findings on the finished diff
```

`/research-source <source>` runs only the first phase.

## Rules for editing these files

- **Frontmatter is YAML.** Quote any description containing a colon; keep
  `name`/`description` present so the model can discover the skill.
- **Commands**: body is the prompt template, `$ARGUMENTS` is the user's
  argument. Name the file after the command (`add-source.md` → `/add-source`).
- **Skills**: the file path is the skill ID (`.opencode/skills/<id>/SKILL.md`
  → id `<id>`). Keep the body focused and push detail into `references/`.
- **Agents**: `mode: subagent`, a `description` (the model picks the agent from
  it), and explicit `permissions`. Start from deny-all, then allow the
  specific paths the agent owns.
- Permissions are ordered and the **last match wins**: keep the broad deny
  first and the narrow allows after it.
- Keep the subagent split meaningful: each agent owns files the others must
  not touch, so two agents cannot fight over the same file.
- Update `docs/operations.md` §12 and the README when the flow changes.

## Validate after editing

```bash
uv run --with pyyaml python - <<'PY'
import pathlib, yaml
root = pathlib.Path(".opencode")
for path in list(root.glob("agents/*.md")) + list(root.glob("skills/*/SKILL.md")) + list(root.glob("commands/*.md")):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        print(path, "NO FRONTMATTER"); continue
    end = text.index("\n---\n", 3)
    yaml.safe_load(text[4:end])
    print(path, "ok")
PY
```

Then confirm the skill still loads (`skill` tool) and the command appears in
the command list.

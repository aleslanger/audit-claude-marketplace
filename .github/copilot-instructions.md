# Copilot instructions — market repository

A curated collection of Claude Code skills. Skills are pure markdown — no build step, no runtime handlers.

## Validate skills

```bash
python3 scripts/validate-skills.py       # validate all SKILL.md frontmatter
```

## Architecture

```
.claude-plugin/plugin.json   # plugin manifest for Claude Code
skills/
  <skill-name>/
    SKILL.md                 # skill definition (YAML frontmatter + markdown body)
scripts/
  validate-skills.py         # CI validation script
.github/workflows/ci.yml     # runs validate-skills.py on push/PR
```

Skills are markdown-only. There are no code handlers or runtime dependencies.

## Key conventions

- Skill files are named `SKILL.md` (uppercase), one per `skills/<name>/` directory.
- Every `SKILL.md` must have YAML frontmatter with at minimum `name` and `description`. The `argument-hint` field is optional but recommended.
- Directory name must be kebab-case and should match the `name` frontmatter field.
- Frontmatter is at the very top of the file, delimited by `---`.

## Adding a skill

1. Create `skills/<skill-name>/SKILL.md` with frontmatter.
2. Run `python scripts/validate-skills.py` locally.
3. Open a PR — CI validates automatically.

## Frontmatter reference

```yaml
---
name: skill-name          # required, kebab-case
description: ...          # required, one sentence used by the agent to decide when to invoke
argument-hint: '[...]'    # optional, CLI arg documentation
---
```

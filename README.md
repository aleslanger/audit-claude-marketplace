# Audit Claude Marketplace

A curated collection of Claude Code skills for auditing codebases and driving them to a clean state.

## Skills

| Skill | Description |
| --- | --- |
| [app-audit-plan](skills/app-audit-plan/SKILL.md) | Produces a phased, tool-assigned plan for auditing an application — checks whether screens and features are actually functional, finds missing CRUD/admin operations, dead buttons and placeholders |
| [audit-to-plan](skills/audit-to-plan/SKILL.md) | Language-agnostic code audit — discovers all issues and writes a structured `FIX_PLAN.md` with `ISSUE-NNN` IDs |
| [quality-loop](skills/quality-loop/SKILL.md) | Iterative fix-verify-commit workflow — drives the codebase to ≥95% clean on a dedicated branch, then opens a PR |

## Usage

Invoke a skill from a Claude Code or Copilot CLI client:

```
/skill audit-to-plan --scope full --output docs/FIX_PLAN.md
/skill quality-loop --plan docs/FIX_PLAN.md --threshold 95
```

For clients without a plugin system, load `skills/<skill>/SKILL.md` as the prompt prefix — see
[Codex / generic LLM wrappers](#codex--generic-llm-wrappers).

### Finding model

`app-audit-plan` and `audit-to-plan` share one canonical finding model: findings
are identified by a positional `ISSUE-NNN` id plus a `fingerprint` that stays
stable across audits, and every non-`OK` finding carries evidence stating what it
proves. `AUDIT.json` (machine-readable) and `AUDIT.md` (human) are generated from
the same model, and `AUDIT.json` projects onto the `FIX_PLAN.md` that
`quality-loop` already consumes.

- [`finding-model.md`](skills/app-audit-plan/references/finding-model.md) — IDs,
  fingerprints, evidence, severity vs priority, coverage
- [`audit-schema.md`](skills/app-audit-plan/references/audit-schema.md) —
  `AUDIT.json` schema, validation rules, `FIX_PLAN` bridge

The `F-01` finding format is **legacy**: it may be read, never written.

### Suggested workflow

1. Run `audit-to-plan` with `--scope diff` to collect issues.
2. Inspect `docs/FIX_PLAN.md` (and `FIX_PLAN.json` if you generated it).
3. Run `quality-loop` with `--dry-run` to preview the commits it would make.
4. When comfortable, run with `--apply` and `--no-push` to create commits locally, then push and open a PR.

> Always run audit workflows with `--dry-run` first to avoid accidental commits.

## Installation

### Claude Code (primary)

This repo contains a Claude Code manifest at `.claude-plugin/plugin.json`. The client discovers it
automatically and lists every skill found under `skills/`.

- Install directly from the Claude Code client using the GitHub repo URL.
- Install from a local path for development:

```bash
git clone <repo-url>
# point your Claude Code client at the local repo path
```

### Copilot CLI

This repo includes a Copilot CLI manifest at `.github/plugin/plugin.json`.

```bash
gh copilot plugin install <repo-url>     # from GitHub
gh copilot plugin install /path/to/repo  # from a local path
gh copilot plugin list                   # verify
```

### Codex / generic LLM wrappers

Codex and most LLM clients are not plugin systems. Use a small wrapper that loads the skill
instructions, composes a prompt with the user arguments, and sends it to the API:

```python
from pathlib import Path
import os
from openai import OpenAI

skill = Path('skills/audit-to-plan/SKILL.md').read_text()
prompt = skill + "\n\nUser: run audit --scope diff"

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
resp = client.responses.create(
    model=os.environ.get('PREFERRED_MODEL', 'gpt-4o-mini'),
    input=prompt,
)
print(resp.output_text)
```

Use environment variables for secrets (`OPENAI_API_KEY`) and never commit them.
More examples: [`platform_templates/codex/README.md`](platform_templates/codex/README.md).

### Gemini CLI

Gemini clients vary. If the client supports plugins, install using a client-specific manifest.
Otherwise use a wrapper like the Codex example above. See
[`platform_templates/gemini/README.md`](platform_templates/gemini/README.md).

## Platform support

| Path | Platform |
| --- | --- |
| `.claude-plugin/plugin.json` | Claude Code (primary) |
| `.github/plugin/plugin.json` | Copilot CLI |
| `platform_templates/codex/` | Codex / generic LLM wrappers |
| `platform_templates/copilot/` | Copilot CLI notes |
| `platform_templates/gemini/` | Gemini CLI |

To add a platform, create a manifest in `platform_templates/<platform>/` and document the install
steps there.

## Local development

```bash
git clone <repo-url>
cd market
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -U pip
# optional: pip install openai pytest
```

Reference scripts under `scripts/` mirror what the skills do, and are useful for testing:

```bash
# Validate every SKILL.md frontmatter
python3 scripts/validate-skills.py

# Generate a fix plan (default output: docs/FIX_PLAN.md)
python3 scripts/audit_to_plan.py --scope diff --write-json

# Convert an existing FIX_PLAN.md to JSON
python3 scripts/fix_plan_parser.py --md tests/fixtures/sample_FIX_PLAN.md --json FIX_PLAN.json

# Validate an AUDIT.json against the canonical finding model
python3 scripts/audit_schema.py tests/fixtures/sample_AUDIT.json

# Project an AUDIT.json onto a FIX_PLAN.md for quality-loop
python3 scripts/audit_schema.py tests/fixtures/sample_AUDIT.json --fix-plan docs/FIX_PLAN.md

# Run the reference runner (dry-run by default)
python3 scripts/quality_loop.py --plan docs/FIX_PLAN.md --dry-run
```

## Adding a new skill

1. Create `skills/<skill-name>/SKILL.md` with the required frontmatter:

```markdown
---
name: your-skill-name
description: One sentence that triggers when to use this skill.
argument-hint: '[--option value]'
---

# Your Skill Title
...
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | ✓ | kebab-case, matches the directory name |
| `description` | ✓ | trigger description shown to the agent |
| `argument-hint` | — | optional, documents CLI arguments |

2. Validate locally:

```bash
python3 scripts/validate-skills.py
```

3. Open a PR — CI runs the same validation automatically.

## License

MIT

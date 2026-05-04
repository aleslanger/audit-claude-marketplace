# Audit Claude Marketplace

A curated collection of Claude Code skills.

## Skills

| Skill                                          | Description                                                                                                    |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| [audit-to-plan](skills/audit-to-plan/SKILL.md) | Language-agnostic code audit — discovers all issues and writes a structured `FIX_PLAN.md` with `ISSUE-NNN` IDs |
| [quality-loop](skills/quality-loop/SKILL.md)   | Iterative fix-verify-commit workflow — drives the codebase to  clean on a dedicated branch, then opens a PR    |

## Installation

Platform-specific install steps for this marketplace.

### Claude Code (primary)

This repo contains a Claude Code manifest at `.claude-plugin/plugin.json`.

Options:

- Install directly from the Claude Code client using the GitHub repo URL (client discovers `.claude-plugin` automatically).
- Install from a local path for development:

```bash
git clone <repo-url>
# point your Claude Code client at the local repo path
```

Notes:

- The client will list available skills found under `skills/`.
- Always run audit workflows with `--dry-run` first to avoid accidental commits.

### Copilot CLI

This repo includes a Copilot CLI manifest at `.github/plugin/plugin.json`.

Install from GitHub:

```bash
gh copilot plugin install <repo-url>
```

Install from local path (development):

```bash
gh copilot plugin install /path/to/local/repo
```

Verify installation:

```bash
gh copilot plugin list
```

### Codex / OpenAI / generic LLM wrappers

Codex and many LLM clients are not plugin systems. Use a small wrapper that:

1. Loads `skills/<skill>/SKILL.md` to get the instructions.
2. Composes a prompt with user arguments.
3. Sends the prompt to the LLM API and returns the output.

Example (minimal Python wrapper):

```python
from pathlib import Path
import os
from openai import OpenAI

skill = Path('skills/audit-to-plan/SKILL.md').read_text()
user_input = 'run audit --scope diff'
prompt = skill + "\n\nUser: " + user_input

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
resp = client.responses.create(model=os.environ.get('PREFERRED_MODEL', 'gpt-4o-mini'), input=prompt)
print(resp.output_text)
```

Safety:

- Always test with `--dry-run` or `--simulate` before enabling any auto-apply behavior.
- Use environment variables for secrets (`OPENAI_API_KEY`) and never commit them.

See `platform_templates/codex/README.md` for more examples.

### Gemini CLI

Gemini clients vary. If the client supports plugins, install using a client-specific manifest. Otherwise use a wrapper similar to the Codex example above. See `platform_templates/gemini/README.md` for guidance.

### Local usage & developer testing

Clone the repository and run the included helper scripts locally (safe defaults):

```bash
git clone <repo-url>
cd market
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -U pip
# (optional) pip install openai pytest

# Validate skill manifests
python3 scripts/validate-skills.py

# Convert sample FIX_PLAN.md to JSON
python3 scripts/fix_plan_parser.py --md tests/fixtures/sample_FIX_PLAN.md --json FIX_PLAN.json

# Run the reference runner (dry-run by default)
python3 scripts/quality_loop.py --plan docs/FIX_PLAN.md --dry-run
```

### Suggested workflow (safe)

1. Run `audit-to-plan` with `--scope diff` to collect issues.
2. Inspect `docs/FIX_PLAN.md` (and `FIX_PLAN.json` if you generated it).
3. Run `quality-loop` with `--dry-run` to preview commits.
4. When comfortable, run with `--apply` and `--no-push` to create commits locally, then push and open a PR.

---

If you need platform-specific examples added to README (e.g., a step-by-step for a specific Claude Code client or Gemini deployment), tell me which client and I will add exact commands.

## Usage

Examples:

- Claude / Copilot style:
  
  ```
  /skill audit-to-plan --scope full --output ISSUES.md
  ```

- Codex / generic LLM wrapper (pseudo):
  
  ```python
  from pathlib import Path
  prompt = Path('skills/audit-to-plan/SKILL.md').read_text()
  prompt += "\n\nUser: run audit --scope diff"
  # send prompt to LLM and print response
  ```

## Platform support

This marketplace includes manifests and guidance for multiple platforms:

- `.claude-plugin/plugin.json` — Claude Code (primary)
- `.github/plugin/plugin.json` — Copilot CLI manifest
- `platform_templates/codex/` — guidance for Codex / generic LLM wrappers
- `platform_templates/gemini/` — guidance for Gemini CLI integrations

To add a platform, create a manifest in `platform_templates/<platform>/` and document the install steps there.

## Adding a New Skill

1. Create `skills/<skill-name>/SKILL.md` with required frontmatter:

```markdown
---
name: your-skill-name
description: One sentence that triggers when to use this skill.
argument-hint: '[--option value]'
---

# Your Skill Title
...
```

2. Validate locally:

```bash
python3 scripts/validate-skills.py
```

3. Open a PR — CI will validate the manifest automatically.

## Required frontmatter fields

| Field           | Required | Notes                                  |
| --------------- | -------- | -------------------------------------- |
| `name`          | ✓        | kebab-case, matches directory name     |
| `description`   | ✓        | trigger description shown to the agent |
| `argument-hint` | —        | optional, documents CLI arguments      |

## CI

```bash
python3 scripts/validate-skills.py   # validate all SKILL.md frontmatter
```

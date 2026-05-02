# Gemini CLI integration guidance

Gemini "CLI" integrations and developer tools vary. This document explains two ways to use this marketplace with Gemini-based workflows:

1) If your Gemini client supports plugin manifests

- Create a small manifest that references the repository and the `skills/` directory.
- Install the plugin using your client's install command (check the client's docs).
- The client should then expose skill invocation in a session similar to Claude/Copilot.

2) If your environment uses a wrapper to call Gemini models (recommended and portable)

- Build a tiny wrapper that:
  - Reads `skills/<skill>/SKILL.md` to obtain the skill instructions
  - Accepts user CLI-style arguments and composes a final prompt
  - Sends the prompt to the Gemini API or local runtime and returns the response

Example (pseudocode):

```python
from pathlib import Path
skill = Path('skills/audit-to-plan/SKILL.md').read_text()
user_input = 'run audit --scope diff'
prompt = skill + '\n\nUser: ' + user_input
# send prompt to Gemini API and print response
```

Notes & safety:

- Always include `--dry-run` or `--simulate` when testing an automatic fixer.
- Prefer the model guidance tiers in each SKILL.md: use the cheapest tier sufficient for the task.
- Document exact install steps for any Gemini client you support in a platform-specific README under `platform_templates/gemini/`.

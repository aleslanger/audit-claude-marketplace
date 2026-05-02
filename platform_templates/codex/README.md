# Codex / LLM integration guide

OpenAI Codex and similar LLMs are not plugin platforms with a standard manifest. To
use this marketplace with Codex or other LLM integrations, create a small wrapper that:

1. Loads the selected `skills/<skill>/SKILL.md` file to obtain the skill instructions.
2. Maps CLI-style arguments to prompt variables.
3. Sends the composed prompt to the Codex/LLM API and returns the response to the user.

Example (pseudocode):

```python
from pathlib import Path
from openai import OpenAI

skill = Path('skills/audit-to-plan/SKILL.md').read_text()
user_input = 'run audit --scope diff'
prompt = skill + '\n\nUser: ' + user_input
client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
resp = client.responses.create(model='codex-..', input=prompt)
print(resp.output_text)
```

Guidance:
- Keep prompts concise; use the `Model Guidance` section in each SKILL.md to choose a suitable model tier.
- Provide a `--dry-run` or `--simulate` flag to avoid destructive operations.
- Consider adding a translations layer if you want to support non-English prompts or outputs.

This repo includes a `platform_templates/codex` directory with this guidance for contributors.

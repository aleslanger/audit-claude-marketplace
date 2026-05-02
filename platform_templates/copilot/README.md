# Copilot CLI integration

This repository includes a Copilot CLI-compatible manifest at `.github/plugin/plugin.json`.

How Copilot CLI works with this repo:

- Each skill lives in `skills/<skill>/SKILL.md` (uppercase `SKILL.md` required).
- The Copilot CLI discovers `.github/plugin/plugin.json` when installing from a repo.

If you maintain a Copilot CLI-specific manifest, ensure the `name`, `description`, and
`version` fields are set. The CLI will use the `skills/` directory by convention.

Example manifest (this repo includes a working copy):

```json
{
  "name": "Audit claude marketplace",
  "description": "A curated collection of skills for Copilot CLI and other clients",
  "version": "0.1.0",
  "author": { "name": "Aleš Langer" },
  "license": "MIT"
}
```

Notes:
- Copilot CLI uses `gh copilot plugin install <repo-url>` to install.
- Keep skill files language-agnostic and in English to maximize cross-platform reuse.

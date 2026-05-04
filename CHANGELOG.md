# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-05-04
### Added
- Hook output: `scripts/hooks/fix-plan-suggest-quality-loop.sh` now emits structured `hookSpecificOutput` including `suggestedActions` and an `ask` confirm so clients can offer interactive "Run quality-loop" actions.
- CLI: `scripts/audit_to_plan.py` — new audit-to-plan helper that defaults to `docs/FIX_PLAN.md` and creates the `docs/` directory before writing the plan.
- Tests: added `tests/test_hook_output.py` to validate hook JSON output and preferred `docs/FIX_PLAN.md` path.

### Changed
- Standardized default plan path to `docs/FIX_PLAN.md` across skills, scripts, and README.
- Updated `skills/*` examples and README to reference `docs/FIX_PLAN.md`.
- `scripts/quality_loop.py` default `--plan` set to `docs/FIX_PLAN.md`.

## [0.1.0] - 2026-05-03
### Added
- Initial release: updated `audit-to-plan` (language detection, ISSUE-NNN IDs, model tiers)
- New `quality-loop` skill: iterative fix-verify-commit workflow
- FIX_PLAN parser, reference runner (dry-run), tests and fixtures
- Platform manifests for Claude Code and Copilot CLI
- CI: skill validation and pytest


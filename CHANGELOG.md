# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-08-13

Follows the `0.1.3` tag. Entries for `0.1.2` and `0.1.3` were never written and
are not reconstructed here.

### Added
- `app-audit-plan`: canonical finding model — `references/finding-model.md`
  (`ISSUE-NNN` id separate from a cross-audit `fingerprint`, evidence records
  stating what they prove, severity vs priority, coverage arithmetic, threat-model
  activation) and `references/audit-schema.md` (`AUDIT.json` schema and validation
  rules).
- `app-audit-plan`: `references/post-implementation-review.md` — review protocol
  for changes made after an audit, including a rule against churning settled
  decisions.
- `scripts/audit_schema.py` — validates `AUDIT.json`, round-trips it, and projects
  it onto the `FIX_PLAN.md` that `quality-loop` already consumes.
- `supersedes` field carrying finding continuity across a file rename, which
  necessarily changes the fingerprint.
- Tests: `tests/test_audit_schema.py` and golden fixture
  `tests/fixtures/sample_AUDIT.json` (IDOR, cross-tenant leak, dead control,
  duplicate mutation, unseeded permission, `CANNOT VERIFY`, monorepo scope trap).
- CI: canonical schema validation step.
- Inventory manifest: coverage denominators are checked against enumerated items
  rather than taken on trust, and every discovered item must end reviewed,
  excluded, or explicitly `not_reviewed` — there is no unaccounted state. Modes
  may share one enumeration with `same_as`, but none may omit it.
- `compare_audits()` classifies findings across two audits as `FIXED` /
  `DISAPPEARED` / `STILL_OPEN` / `REGRESSED` / `NEW`. A finding missing from the
  current audit counts as fixed only if its location was re-reviewed; otherwise it
  resolves to `CANNOT VERIFY`.
- `decay_confidence()` lowers `CONFIRMED` to `PROBABLE` when evidence cites a
  revision the file has since moved past. Evidence without a recorded `commit`
  is untouched, so audits without git context are unaffected.
- `authorized_scope`: finding **and evidence** locations must fall inside the
  scope the audit was permitted to read — citing a file proves it was opened.
- `review_summary()` and `diff_inventory()` helpers.

### Changed
- `app-audit-plan` findings use `ISSUE-NNN` instead of `F-01`. The `F-01` format is
  legacy — readable, never written; conversion is positional.
- Report template gained a coverage table reporting static and runtime separately.
- Removed `plugins/audit-claude-marketplace/`, a second copy of `audit-to-plan`
  and `quality-loop` that stopped being updated in May while `skills/` moved on.
  The hook and `hooks.json` lived only there and moved to `scripts/hooks/` and the
  repository root, where the rest of the tooling already expected them.
- `skills/quality-loop/SKILL.md` documents `docs/FIX_PLAN.md`, matching what both
  scripts already default to.
- Plugin and marketplace manifests all report the same version.

### Fixed
- CI `push` trigger ran on `main`, which does not exist in this repository, so it
  never fired on push. Now `master`.

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


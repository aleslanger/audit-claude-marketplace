# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-08-18

Follows `0.2.0`. Hardens the audit schema validator against documents that
validated clean while asserting things the rules were written to forbid, and
closes domain and methodology gaps in the skill itself.

### Added
- `AUDIT.json` schema version `1.1`. Rules that reject output `1.0` accepted are
  gated on it, so audits already delivered keep validating; crash and immutability
  fixes apply to every version, because a traceback is never the right answer to
  bad input. Details and per-rule rationale in `references/audit-schema.md`.
- Optional `rule` field, completing the `(category, location, rule)` fingerprint
  identity the spec always described. Without it two defects in one file shared an
  identity, which is the collision the model says must stay visible.
- `references/security-checklist.md`: a third mark, `[—] not applicable, because
  <reason>`. A checkbox has two states and a security control has three — without
  it an unchecked box read as a missing control, contradicting the threat-model
  activation rule in `finding-model.md` §6.
- Domain coverage the checklists never named: secrets committed to the repository
  (including history), dependency advisories with a stated reachable path,
  personal-data deletion that actually deletes, identity-keyed caches, money
  arithmetic and rounding, schema-migration safety, feature flags as a dead-code
  and authorization source, timezone and locale boundaries, and a background-job
  failure-mode table.
- `references/audit-phases.md` Phase 1: the enumeration unit is named before
  anything is counted (routes, endpoints, CLI commands, public API, screens,
  consumers), and "files I read" is explicitly never a unit. The methodology
  previously defined the coverage denominator as coming from "the filesystem and
  router config", leaving a CLI, a library, or a pipeline with no unit at all.
- Phase 1 guidance for a manifest that outgrows the working context: record items
  to the deliverable as they are enumerated, and report `SAMPLED` with the
  truncation stated rather than a quietly shortened `discovered`.
- Phase 1 standing exclusion class for generated, vendored, and build output, with
  the exclusion naming its generator, and the rule that a defect in generated code
  is reported against its source of truth.
- Phase 1b, a shallow authorization sweep between inventory and functional
  verification. Rule 5 ranks missing server-side authorization above everything,
  but security was the fourth phase — so an audit that ran out of time produced no
  authorization findings at all.
- `tests/test_audit_hardening.py` — 64 tests, each named after what it prevents.

### Fixed
- Two crashes where malformed input raised `TypeError` instead of returning a
  violation, aborting validation and hiding every other error in the document:
  `depends_on` holding a non-list, and an unhashable value in any enum field.
  A third, in the priority matrix lookup, was found by the new tests.
- `authorized_scope` compared with a raw `startswith`, so `apps/admin` accepted a
  finding in `apps/admin-secrets`, and `apps/admin/../../etc/passwd` counted as
  inside `apps/admin/`. Now compared at path-segment boundaries with `..` resolved.
- `authorized_scope` given as a bare string silently disabled both scope rules with
  no error. It is the one control nobody else audits, so a malformed boundary now
  fails loudly instead of turning itself off.
- Omitting `reviewed_items` returned early and skipped rules 19–23 in one move,
  including "FULL by name" — leaving exactly the count rule 23 says is not enough.
- `mode: FULL` over an empty denominator validated: excluding every discovered item
  then claiming FULL was arithmetically true and substantively empty.
- Coverage counts accepted booleans (`isinstance(True, int)` is true in Python),
  negatives, and absences that defaulted to `0` — making `{"mode": "FULL"}` valid.
- `not_reviewed` was neither type-checked nor membership-checked; a bare string
  became a set of its characters, accounting for nothing. Duplicates in
  `reviewed_items` inflated the numerator while satisfying the count rule.
- `quote` was the one evidence field never required, so `CONFIRMED` + `code-read`
  — the strongest claim in the model — could be made with no quoted line.
- Every "non-empty" rule tested truthiness, so `"  "` and `True` satisfied it.
  `priority_override_reason=True` was a one-token bypass of the priority matrix.
- `fingerprint` was checked only for truthiness despite the spec saying 12 hex
  characters. `True` was accepted, and `True == 1` aliased it with any integer
  fingerprint in the collision map, merging two distinct defects.
- The `file:line` pattern was unanchored, so `":42"` passed — and `":42"`
  normalized to `""`, which prefix-matched every `authorized_scope` entry.
- `to_fix_plan_md` interpolated `title` unescaped, so a newline closed the heading
  and the remainder became fabricated issues that `quality-loop` read as real work.
  Fixed at both ends: the renderer flattens, and the schema rejects a multi-line
  title.
- An unknown `severity` was counted in the FIX_PLAN header but rendered in no
  group, so the issue vanished from the plan it claimed to contain.
- `decay_confidence` returned a shallow copy sharing the caller's `evidence` list,
  breaking the immutability its own docstring promised; it also crashed on
  `current_commits=None` and reported only the first stale record.
- The CLI raised raw tracebacks on unreadable or malformed input instead of the
  `FAIL:` report its docstring promised.
- `references/audit-phases.md` Phase 5 was prose with nothing checkable in it
  ("assess navigation consistency"), unlike every comparable phase. Now a table
  scored with the same `status` enum.
- `SKILL.md` description did not mention reviewing a diff of audit fixes, so the
  post-implementation-review mode — the largest reference file — was invisible to
  skill selection.
- `app-audit-plan`: the capability matrix and Phase 2 offered an `UNCLEAR` status
  that was in no enum — not in `finding-model.md` §3 and not in `STATUSES` — so a
  cell filled with it could not be serialized into `AUDIT.json`. Replaced by
  `CANNOT VERIFY`, whose required `resolves_when` is the point: "unclear" with no
  resolution condition is indistinguishable from "not looked at".
- `app-audit-plan`: Phase 8 defined `P0`–`P3` in prose alongside the normative
  severity × likelihood matrix in `finding-model.md` §4, so a rare `CRITICAL`
  finding got `P0` by prose and `P1` by matrix — rejected by the validator as
  `PRIORITY_MISMATCH`. The phase now derives priority from the matrix and points
  at `priority_override_reason` for deviations.
- `audit-schema.md`: two distinct validation rules were both numbered 18. The
  security rule is now 27.
- `report-template.md`: states that the `FIX_PLAN` projection is a subset — `OK`
  and `CANNOT VERIFY` findings are excluded — so a finding absent from the fix
  plan is not read as a finding that went away.
- `post-implementation-review.md`: records that `RV-NNN` is a review-local
  counter with deliberately no schema and no validator, with the counter-argument
  it survived, and how a review finding that outlives the review is promoted to a
  canonical `ISSUE-NNN`.

### Fixed during review of this release
- The version gate compared versions as **strings**, and `"1.10" >= "1.9"` is
  False as text — so a future 1.10 would have silently dropped to the permissive
  1.0 reading. A gate whose failure mode is "accept less" is worse than no gate,
  because nothing announces it. Now compared as integer tuples.
- Phase 1b claimed its findings leave as `INFERRED`, contradicting
  `finding-model.md` §3: the sweep reads the handler, which is `code-read`, not
  `static-reasoning`. Rewritten to say what was actually meant — the phase emits
  **candidates, not findings** — with the reason: `code-read` does support "no
  check appears in this function" and does not support "this endpoint is
  exploitable".
- "enumerated from the filesystem and router config" survived verbatim in
  `SKILL.md` and `finding-model.md` after the enumeration-unit section was written
  to replace exactly that phrasing. Generalized in all three places.
- `_one_line` had a fallback that let a title of only `#` characters through
  unchanged. Simplified; `\r`, `\r\n`, U+2028, and U+0085 breaks are now pinned by
  test, since a newline-specific filter would have missed all four.
- Mutation-tested every new guard: 17 of 17 reverts fail at least one test, so no
  new rule is enforced only by prose.
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


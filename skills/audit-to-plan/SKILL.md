---
name: audit-to-plan
description: Use when auditing code for all problems and saving findings as an actionable fix plan to a markdown file. Triggers on requests to find all issues, create a remediation plan, or systematically discover tech debt. Works with any programming language.
argument-hint: '[--output <path>] [--scope diff|full]'
---

# Audit to Plan

Comprehensive, language-agnostic code audit that writes all discovered problems into a structured
markdown fix-plan file. Each finding gets a unique `ISSUE-NNN` ID for tracking by automated workflows.

## When to Use

- User asks to find all problems and save them
- User wants a remediation plan as a document
- User asks for a full review before a big refactor
- User wants to track tech debt systematically
- Called internally by the `quality-loop` skill

## Arguments

| Argument | Default | Meaning |
|----------|---------|---------|
| `--scope diff` | ✓ default | Only files changed vs HEAD |
| `--scope full` | | Entire tracked codebase |
| `--output <path>` | `FIX_PLAN.md` | Output file path |

## Model Guidance

Use the cheapest model tier adequate for each task:

| Tier | Use for |
|------|---------|
| **Nano** (fastest, cheapest) | Reading files, building context lists, gathering file paths |
| **Standard** (default) | Running analysis agents, writing findings, deduplication |
| **Power** (most capable) | Only when Standard cannot reason about complex security or architectural issues |

Apply this guidance when dispatching agents: pass the tier hint in agent prompts so each sub-agent
self-selects appropriately.

## Process

### 1. Determine scope

```bash
# --scope diff (default): staged + unstaged changes
git diff --name-only HEAD
git diff --name-only --cached

# --scope full: all tracked files
git ls-files
```

If user did not pass `--scope`, default to `diff`. Do not ask interactively.

### 2. Detect languages

From the scoped file list, detect which languages are present by file extension:

| Extensions | Language agent to spawn |
|-----------|------------------------|
| `.ts .tsx .js .jsx .mjs .cjs` | TypeScript/JavaScript |
| `.py .pyw` | Python |
| `.go` | Go |
| `.php` | PHP |
| `.rb .erb` | Ruby |
| `.java .kt .kts` | Java/Kotlin |
| `.rs` | Rust |
| `.c .cpp .cc .h .hpp .cxx` | C/C++ |
| `.cs` | C# |

Spawn a language agent **only if** that language's extensions appear in the scoped files.

### 3. Run parallel analysis agents

Dispatch all applicable agents **in parallel** (single Agent tool message with multiple blocks).

**Always run** (language-independent):

| Agent | Focus |
|-------|-------|
| Code quality | Patterns, naming, complexity, dead code |
| Security | OWASP Top 10, secrets, injection, auth, input validation |
| Silent failures | Swallowed errors, bad fallbacks, missing error propagation |
| Type design | Type invariants, encapsulation, unsafe casts, data model correctness |

**Language agents** (only for detected languages — see table above):

| Language | Focus |
|----------|-------|
| TypeScript/JavaScript | Type safety, async correctness, prototype pollution |
| Python | PEP 8, type hints, unsafe eval/exec, dependency issues |
| Go | Error handling, goroutine leaks, context usage, idiomatic patterns |
| PHP | Type safety, framework conventions, SQL injection, runtime safety |
| Ruby | Security, metaprogramming misuse, Rails conventions (if applicable) |
| Java/Kotlin | Null safety, checked exceptions, thread safety, resource leaks |
| Rust | Unsafe blocks, ownership correctness, panic paths |
| C/C++ | Memory safety, buffer overflows, undefined behavior |
| C# | Async/await correctness, IDisposable, null reference safety |

When prompting general-purpose agents (silent failures, type design): include the agent's role
description and the explicit list of files to inspect.

### 4. Collect and deduplicate

Merge all findings:
1. Group by `(file, line_range)` — same location = same issue
2. When two agents flag the same location: keep higher severity, merge descriptions
3. Remove findings with identical `(file, problem_text)` after normalization

Assign sequential IDs **after** deduplication: `ISSUE-001`, `ISSUE-002`, … (ascending by severity,
CRITICAL first).

### 5. Write plan file

Output path: `--output` arg or `FIX_PLAN.md` in project root.

**Every issue MUST include a file path and line number. Issues without line numbers are not actionable.**

```markdown
# Fix Plan — <project name>
Generated: <ISO 8601 timestamp>
Scope: <diff | full repo> — <N> files
Total issues: <N> (CRITICAL: X · HIGH: Y · MEDIUM: Z · LOW: W)

---

## Critical

### [CRITICAL] ISSUE-001 — <Short title>
- **ID:** `ISSUE-001`
- **File:** `path/to/file.go:42`
- **Problem:** <what is wrong>
- **Fix:** <concrete action — specific change to make>
- **Why:** <security/correctness/data-loss risk>
- **Status:** `open`

---

## High

### [HIGH] ISSUE-002 — <Short title>
- **ID:** `ISSUE-002`
- **File:** `path/to/file.py:88`
- **Problem:** ...
- **Fix:** ...
- **Status:** `open`

---

## Medium

### [MEDIUM] ISSUE-003 — <Short title>
- **ID:** `ISSUE-003`
- **File:** ...
- **Problem:** ...
- **Fix:** ...
- **Status:** `open`

---

## Low

### [LOW] ISSUE-004 — <Short title>
- **ID:** `ISSUE-004`
- **File:** ...
- **Problem:** ...
- **Fix:** ...
- **Status:** `open`

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | X |
| HIGH | Y |
| MEDIUM | Z |
| LOW | W |
| **Total** | **N** |
```

### 6. Report to user

- Path to generated file
- Total issue count by severity
- Whether CRITICAL issues exist (blocks commit until resolved)

## Severity Mapping

| Level | Meaning |
|-------|---------|
| CRITICAL | Security vulnerability, data loss, crash |
| HIGH | Bug, broken contract, significant quality issue |
| MEDIUM | Maintainability, missing test coverage, tech debt |
| LOW | Style, naming, minor suggestions |

## Common Mistakes

- Launching agents sequentially — always parallel, single message, multiple Agent blocks
- Deduplication by text only — deduplicate by `(file, line_range)` first
- Vague fix descriptions — every fix needs file path + line + concrete change
- Skipping silent-failure agent — swallowed errors are invisible to other agents
- Running diff scope but missing staged files — always check both `git diff HEAD` and `git diff --cached`
- Writing issues without line numbers — unactionable, always resolve to exact location
- Assigning IDs before deduplication — IDs must be assigned after merging to stay stable

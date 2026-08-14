---
name: quality-loop
description: Use when you want to automatically fix all code quality issues found by audit-to-plan. Runs an iterative fix-verify-commit loop on a dedicated branch until ≥95% of issues are resolved, then opens a PR. Works with any programming language.
argument-hint: '[--scope diff|full] [--plan <path>] [--threshold <0-100>] [--output <path>]'
---

# Quality Loop

Automated fix-verify-commit workflow that drives a codebase to ≥95% clean by iterating through
all issues discovered by `audit-to-plan`, applying the smallest possible fix for each, verifying
the fix, and committing it — all on a dedicated branch with a PR at the end.

## When to Use

- User wants all code quality issues fixed automatically
- User wants a clean branch with atomic, traceable fix commits
- User wants a PR that resolves audit findings
- Used after `audit-to-plan` has already produced a `docs/FIX_PLAN.md`, or to run the full pipeline

## Arguments

| Argument | Default | Meaning |
|----------|---------|---------|
| `--scope diff\|full` | `full` | Scope passed to `audit-to-plan` when running a fresh audit |
| `--plan <path>` | _(run fresh audit)_ | Use an existing `docs/FIX_PLAN.md` instead of re-auditing |
| `--threshold <N>` | `95` | Stop when ≥N% of issues are resolved (0–100) |
| `--output <path>` | `docs/FIX_PLAN.md` | Output path for the fix plan (when running a fresh audit) |

## Model Guidance

| Tier | Use for |
|------|---------|
| **Nano** (fastest, cheapest) | Reading files, building context, writing commit messages, simple style/naming fixes |
| **Standard** (default) | Applying logic/correctness fixes, running verification re-audits, writing the PR description |
| **Power** (most capable) | Applying CRITICAL security fixes, multi-method architectural changes |

Always start at Nano; upgrade only when the task genuinely requires more reasoning.

## Process

### 1. Pre-flight checks

```bash
# Abort if there are uncommitted changes
git status --porcelain
```

If the working tree is dirty, stop and tell the user to commit or stash their changes first.
Record the current branch name as `base-branch`.

### 2. Create fix branch

```bash
git checkout -b fix/YYYYMMDD-quality-loop
```

Use today's date in `YYYYMMDD` format (UTC).

### 3. Audit (if no `--plan` provided)

Run `audit-to-plan --scope full --output docs/FIX_PLAN.md` (or use the `--scope` argument if provided).

Load the resulting `docs/FIX_PLAN.md`:
- Parse all issues, extract `ISSUE-NNN`, severity, file, status
- Record `total_issues` = count of all issues with status `open`

If `--plan` was provided, load that file directly.

### 4. Fix loop

Repeat until the threshold is met or no open issues remain:

#### 4a. Select next issue

Pick the highest-severity open issue: CRITICAL → HIGH → MEDIUM → LOW.
Within the same severity, process in `ISSUE-NNN` order.

#### 4b. Determine fix granularity

Choose the **smallest atomic unit** that contains the problem:

| Granularity | When to use |
|------------|-------------|
| Function/method | Default — issue is contained within a single function |
| Class/struct | Issue spans multiple methods of the same type |
| File | Issue is structural (missing import, wrong organization) |

**Never** fix multiple unrelated issues in the same edit. One commit = one issue.

#### 4c. Apply fix

Use the appropriate model tier (see Model Guidance above).

Read only the relevant file section — do not load the entire file unless required.
Apply the minimal change that resolves the issue without introducing unrelated edits.

#### 4d. Verify fix

Re-audit only the changed file(s) using the same agent types that originally detected the issue.
(Use Standard tier for verification.)

**Verification passes if both conditions hold:**
1. `ISSUE-NNN` no longer appears in the re-audit output
2. No new CRITICAL or HIGH issues were introduced in the changed files

If verification fails: undo the change, increment the retry counter for this issue.

#### 4e. Commit or retry

- **Verified:** commit the fix and mark the issue resolved in `docs/FIX_PLAN.md`:
  ```
  git add <changed files>
  git commit -m "fix(ISSUE-NNN): <issue title in lowercase>"
  ```
  Update issue status: `open` → `resolved`

- **Failed (retry < 3):** undo the edit, try a different approach. Use Standard or Power tier
  on subsequent attempts.

- **Failed (retry = 3):** mark issue as `blocked` in `docs/FIX_PLAN.md`, move to the next issue.
  Blocked issues do **not** count as unresolved when calculating the threshold.

#### 4f. Check threshold

```
resolved / (total_issues - blocked) >= threshold / 100
```

If the threshold is met, exit the loop.

### 5. Finalize fix plan

Update `docs/FIX_PLAN.md` — append a completion section:

```markdown
---

## Quality Loop Results

Completed: <ISO 8601 timestamp>
Threshold: <N>%

| Status | Count |
|--------|-------|
| Resolved | R |
| Blocked | B |
| Open (skipped) | S |
| **Total** | **N** |

Cleanliness: <resolved / (total - blocked) * 100>%
```

Commit the updated plan:
```
git commit -m "chore: update docs/FIX_PLAN.md with quality-loop results"
```

### 6. Push and open PR

```bash
git push -u origin fix/YYYYMMDD-quality-loop
```

Open a PR from `fix/YYYYMMDD-quality-loop` → `base-branch` with:

**Title:** `Quality loop: R/N issues resolved (X% clean)`

**Body:**
```markdown
## Quality Loop Results

Automated fix pass using `quality-loop` skill.

**Threshold:** N% | **Achieved:** X%

### Resolved (R issues)
- ISSUE-001: <title> — `path/to/file:line`
- ISSUE-002: <title> — `path/to/file:line`
...

### Blocked (B issues)
> Blocked issues require manual intervention.
- ISSUE-NNN: <title> — `path/to/file:line` — _<reason blocked>_
...

### Skipped
S issues were below the threshold cutoff and were not attempted.

---
*Generated by [quality-loop](../skills/quality-loop/SKILL.md)*
```

Use Standard tier to write the PR description.

### 7. Report to user

Print a summary:
- Branch name and PR URL
- Resolved / blocked / skipped counts
- Final cleanliness percentage
- List of blocked issues (so the user knows what needs manual attention)

## Fix Granularity Rules (expanded)

The workflow agent decides the scope of each edit:

1. **Prefer function-level** — if the issue is inside a single function, change only that function
2. **Method-level for class issues** — if the issue spans methods, change the class but not the file
3. **File-level as last resort** — only for structural issues (import order, missing file header)
4. **Cross-file is forbidden** — never touch more than one file per commit unless the fix is literally
   adding an import to a second file that the primary file depends on

## Error Handling

| Situation | Action |
|-----------|--------|
| Working tree dirty at start | Abort; tell user to commit or stash |
| Branch already exists | Abort; suggest `git branch -D fix/YYYYMMDD-quality-loop` |
| Fix introduces new CRITICAL/HIGH | Revert; count as a failed attempt |
| All issues blocked | Exit loop; report 0% improvement; no PR |
| `git push` fails | Report branch name; ask user to push and create PR manually |

## Common Mistakes

- Applying a fix without verifying — always re-audit after every change
- Committing multiple issue fixes in one commit — one commit per issue, always
- Reading entire large files for context — read only the relevant function/section
- Using Power tier for simple fixes — default to Nano/Standard, upgrade only when needed
- Counting blocked issues as unresolved in the threshold — they are excluded from the denominator
- Fixing issues outside the declared scope — only touch files relevant to the current issue

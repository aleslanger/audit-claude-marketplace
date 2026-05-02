# Fix Plan — sample project
Generated: 2026-05-03T00:00:00Z
Scope: full — 2 files
Total issues: 2 (CRITICAL: 1 · HIGH: 1 · MEDIUM: 0 · LOW: 0)

---

## Critical

### [CRITICAL] ISSUE-001 — Unsafe SQL construction
- **ID:** `ISSUE-001`
- **File:** `app/query.py:42`
- **Problem:** Unsafe string interpolation into SQL query allows injection
- **Fix:** Use parameterized queries (db.execute(query, params))
- **Status:** `open`

---

## High

### [HIGH] ISSUE-002 — Use of eval on untrusted data
- **ID:** `ISSUE-002`
- **File:** `scripts/build.py:10`
- **Problem:** `eval` is used on input that may be attacker-controlled
- **Fix:** Replace eval with ast.literal_eval or a safer parser
- **Status:** `open`

# Report structure

Use this order. It moves from verified fact toward plan, so a reader who stops
halfway still has the part that is trustworthy.

## Scaling the report down

The full structure below suits a full-scope audit. A narrower question — or a
user who explicitly does not want an elaborate document — gets a shorter report,
not a padded one. Scale by **dropping whole sections, never by thinning the
evidence**.

Keep always, at any size:

- the verdict, stated in the first two lines
- findings with `file:line`, ordered by priority
- what was **not** audited, so silence never reads as "fine"
- `CANNOT VERIFY` items

Drop when the scope did not cover them: architecture, UI/UX, missing
functionality, consistency, solution variants, target state, implementation
plan, test plan, pre-production checklist.

A short report still names its own limits. "Not audited: architecture,
performance, accessibility — deliberately, given the time box" is one line and
prevents the most expensive misreading of an audit.

---

## 1. Verifiable facts

Only what is directly confirmed in code. Each item carries a `file:line`
pointer. No inference here.

## 2. Unknowns

What cannot be determined from the current code or context. Each entry states
what would resolve it (run the app, read infra config, ask the product owner).
Use the literal marker `CANNOT VERIFY`.

## 3. Scope overview

State what was audited and what was deliberately left out. Then list every
discovered section and its purpose.

| Section | Route / entry point | Entities | Purpose | Backing endpoints / actions |
|---|---|---|---|---|

## 4. Capability matrix

One row per section. Values: `OK` / `MISSING` / `PARTIAL` / `BROKEN` /
`UNCLEAR`.

Adapt the columns to the domain. The CRUD-shaped default:

| Section | List | Detail | Create | Edit | Delete | Archive | Status change | Search | Filter | Sort | Pagination | Bulk | Import | Export | Validation | Permissions | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

For non-CRUD areas replace the operation columns with the domain's real verbs
(start, cancel, retry, publish, approve, refund, sync) and keep `Validation`,
`Permissions`, and `Status`. State which default columns you dropped and why.

Follow the table with a short note for every non-`OK` cell: what exactly is
missing or broken.

## 5. Findings

One block per finding, ordered by priority.

```
### F-01 — <short title>

- **Location:** path/to/file.ts:123
- **Problem:** what is wrong
- **Evidence:** quoted code or trace showing it
- **Type:** bug | missing feature | UX | architecture | security
- **Impact:** what goes wrong for a user or the data
- **Likelihood:** how often this is hit in practice
- **Priority:** P0 | P1 | P2 | P3
- **Size:** S | M | L
- **Depends on:** F-xx, or none
- **Proposed fix:** what to change and WHY that is the right change
```

## 6. Security findings

Same block format. Always precedes non-security findings of equal priority.
State for each whether it is exploitable today or requires another
precondition.

## 7. Architectural findings

Same block format, plus explicit trade-offs of the proposed design.

## 8. UI/UX findings

Same block format.

## 9. Missing functionality

Each entry marked `ASSUMPTION` unless directly evidenced. State what evidence
in the codebase suggests it (an unused endpoint, a schema column never exposed,
a status enum with unreachable values).

## 10. Solution variants and trade-offs

Where more than one reasonable approach exists, describe each option, its
consequences, its cost, and a recommendation with reasoning.

## 11. Target state

How the audited area should look once the work is done. Concrete: which
patterns are standard, which components are shared, what every comparable
section provides.

## 12. Implementation plan

Phases ordered to minimize regression risk. Typical ordering:

1. Security fixes that need no refactor (server-side authorization, IDOR).
2. Broken functionality and data-integrity fixes.
3. Shared abstractions (table, form, confirmation, error handling) — introduced
   without changing behavior.
4. Migration of sections onto the shared abstractions, one at a time.
5. Missing functionality.
6. UX and consistency polish.

For each phase: contents, dependencies, risk, rough size, and how to verify the
phase did not regress anything.

## 13. Test plan

See `test-plan.md`.

## 14. Pre-production checklist

See `test-plan.md`.

---

## Closing summary

Six short lists, no prose padding:

1. Most critical problems
2. Biggest security risks
3. Biggest missing functionality
4. Biggest architectural debt
5. Biggest UI/UX problems
6. Recommended implementation order

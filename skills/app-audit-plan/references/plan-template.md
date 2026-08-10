# Audit plan structure

The plan is written before any auditing. It is short enough to read in one
sitting and specific enough that someone else could execute it.

---

## 1. Scope

- What is being audited — applications, areas, routes, packages.
- What is explicitly **out** of scope, and why.
- Stack: framework and version, rendering model, data layer, auth mechanism.
- Entry point of the audited area.
- If the repository holds several applications (monorepo, symlinked or nested
  workspaces): which ones are in scope, which are not.

## 2. Available tooling

Filled from the environment discovery step. Only entries verified to exist in
this session. One row per tool.

| Tool | Type | Used for | Phase |
|---|---|---|---|
| | skill / agent / MCP / project command | | |

Then a short list: **relevant tooling looked for and not available here**, and
what each absence changes about the plan. Examples of consequences worth
stating — no code-graph server means manual tracing and a larger inventory
phase; no E2E harness means the test plan proposes adding one and prices it;
no security-review capability means the security phase is done by hand against
the checklist.

## 3. Phases

One block per phase.

```
### Phase N — <name>

- **Objective:** what this phase must establish
- **Method:** how, concretely
- **Tooling:** which entries from the table above
- **Evidence produced:** what artifacts or findings come out
- **Done when:** completion criterion, not a time estimate
- **Effort:** S | M | L
- **Risk of overrun:** what would make this phase blow up
```

Default sequence — drop a phase only with a stated reason:

1. Inventory
2. Functional verification
3. Architecture
4. Security
5. UI/UX
6. Cross-module consistency
7. Missing functionality
8. Prioritization
9. Report

## 4. Execution order and parallelism

- Inventory is a prerequisite for everything else.
- Phases 3, 4, and 5 are independent and can run concurrently where the
  environment supports subagents or worktrees.
- Phase 6 needs the results of Phase 2 across all modules.
- Phases 8 and 9 need all findings and come last.

State which phases will fan out, how the work is split, and how the results
are merged. Parallel findings still need de-duplication before prioritization.

## 5. Deliverables

- The report, and where it goes. Default is a file at `docs/audit-<scope>.md` —
  but if the user asked for the output in the conversation, or restricted
  writing to the repository, deliver it there instead. Rule 1 forbids changing
  the audited application; it does not forbid writing the report, and a user's
  explicit instruction about output location always wins over the default.
- Capability matrix.
- Prioritized findings list.
- Test plan.
- Pre-production checklist.

Scope the deliverable list to the phases actually planned. An audit answering
one narrow question does not owe a test plan and a pre-production checklist —
`report-template.md` says how to scale down without losing the parts that make
a report trustworthy.

## 6. Assumptions and open questions

- Anything assumed in order to produce the plan, labelled `ASSUMPTION`.
- Questions whose answer would change the plan — asked now, not after the
  audit has run on the wrong scope.

---

## Presenting the plan

Keep it to what the user needs to decide: scope, tooling, phases, effort,
open questions. If they asked for a plan only, stop here and ask whether to
execute. If they asked for the audit, present the plan and proceed unless it
surfaced a question that materially changes the scope.

---
name: app-audit-plan
description: Use when asked to audit an application or any part of it, review whether its screens and features are actually functional, check for missing CRUD or admin operations, dead buttons and placeholders, or assess a codebase before production. Also use when planning such an audit before executing it.
---

# Application Audit Plan

Produces an **audit plan** — a phased, tool-assigned work plan for auditing an
application or a bounded part of it — and then executes it if the user wants
the audit itself.

The plan is the deliverable. It says what will be examined, in what order, with
which tooling available in **this** environment, what evidence each phase must
produce, and what the resulting report will contain.

## The two modes

Read the request before choosing:

| User asks for | Deliver |
|---|---|
| "plan the audit", "how would you audit", "prepare an audit plan" | The plan only. Stop after it. |
| "audit X", "check whether X works", "review X before production" | The plan first, then execute it phase by phase. |

When it is genuinely ambiguous, produce the plan and ask whether to execute.
Never execute without a plan — an audit written from an impression of the first
ten files is the main failure mode here.

## Hard rules

These override the desire to be helpful or fast.

1. **Auditing changes nothing.** No edits, no migrations, no fixes, no "small
   cleanups". The deliverable is a plan and a report. Fixes are a separate task
   the user asks for separately.
2. **Never judge a feature by the presence of a component or a button.** Trace
   the whole flow: UI element → handler → API route / server action → business
   logic → persistence → response → cache invalidation → UI feedback. A button
   wired to a handler that returns early is NOT a working feature.
3. **Unverifiable things are marked `CANNOT VERIFY`**, with what would resolve
   them. Runtime behavior, external services, data volumes, and infra config
   usually land here.
4. **Inferences are marked `ASSUMPTION`.** A guess is never presented as an
   existing requirement. Do not invent requirements the application does not
   imply.
5. **Security outranks cosmetics.** A missing server-side authorization check is
   always reported above a misaligned button.
6. **Every recommendation states WHY**, not only what.
7. **New technology needs justification.** Proposing a framework, library, or
   architectural pattern the project does not already use requires stating what
   in the existing stack cannot express the fix.

## Step 1 — Discover the environment's tooling

Do this **before** writing the plan, every time. Available tooling differs per
machine, per project, and over time; a plan naming tools that do not exist here
is worse than a plan naming none.

Enumerate what this session actually has:

- **Skills** — from the available-skills listing. Relevant kinds: security
  review, code review for the detected stack, codebase exploration, flow
  tracing, testing and E2E, verification, production readiness, repo scanning.
- **Agents** — from the agent-types listing: stack-matched reviewers, security
  reviewers, explorers, planners.
- **MCP servers** — code-graph and symbol search, documentation lookup, browser
  automation, database access.
- **Project tooling** — `package.json` scripts, `Makefile`, CI config: linters,
  type checkers, test runners, coverage, dead-code detectors, audit commands.
- **Repository documentation** — `CLAUDE.md`, `README`, `docs/`, and any prior
  audit or plan documents, which say what was already examined and suspected.

Verify each candidate exists before naming it — check the listing or the file.
Names change between versions and recall is not evidence.

Record the result as the plan's tooling table. Anything relevant you looked for
and did **not** find gets a line too: its absence changes the plan. No
code-graph server means manual tracing and a bigger inventory phase; no E2E
harness means the test plan proposes adding one and prices it.

## Step 2 — Establish scope and stack

Determine:

- Framework and version, rendering model (SSR / SPA / RSC / server actions).
- Data layer (ORM, query builder, raw SQL, external API).
- Auth mechanism and where identity is resolved.
- Where the audited area begins: route prefix, layout, middleware, guard,
  package boundary, or service entry point.
- Whether the target is one application or several — monorepos, symlinked
  workspaces, and multi-app repositories are common and change the scope
  materially. State which applications are in and which are out.

If the area cannot be located, ask for the entry point rather than guessing.

Scope shifts the emphasis:

| Scope | Emphasis |
|---|---|
| Back-office / admin | Privilege model, destructive operations, CRUD completeness, bulk actions, audit trail |
| Customer-facing area | Auth boundaries, tenant isolation, empty/error states, performance under real data, accessibility |
| API / service | Contract correctness, validation, per-endpoint authorization, idempotency, versioning, rate limits |
| Single module / feature | Full flow tracing, integration points, edge cases, consistency with sibling modules |
| Whole application | Inventory first, then depth on the highest-risk areas; state explicitly what got shallow coverage |

## Step 3 — Write the plan

Use `references/plan-template.md`. The plan assigns, per phase: objective,
method, tooling from Step 1, evidence required, and completion criteria.

The phases below are the default sequence. Drop one only when it provably does
not apply, and record that it was dropped and why.

| # | Phase | Produces |
|---|---|---|
| 1 | Inventory | Complete list of routes, screens, components, endpoints, models, permissions, jobs |
| 2 | Functional verification | Capability matrix + edge-case results, evidence-backed |
| 3 | Architecture | Layering, duplication, consistency, data flow, performance findings |
| 4 | Security | Authorization, input, sensitive data, destructive-operation findings |
| 5 | UI/UX | Navigation, feedback, states, accessibility findings |
| 6 | Cross-module consistency | Divergences between comparable modules, unification proposal |
| 7 | Missing functionality | Sensible absent capabilities, each labelled |
| 8 | Prioritization | Every finding classified P0–P3 with size and dependencies |
| 9 | Report | The structured deliverable |

Phase detail — what each phase examines and the checklists it works
through — lives in `references/audit-phases.md`, with supporting checklists in
`references/security-checklist.md` and `references/edge-cases.md`.

Where the environment offers parallelism (subagents, worktrees), the plan says
which phases fan out and which must be sequential. Inventory precedes
everything. Phases 3–5 are independent of each other and parallelize well.
Prioritization and reporting need all findings and come last.

Estimate effort per phase in relative terms (S/M/L) rather than wall-clock, and
state what would make each phase overrun — usually inventory turning out larger
than the first pass suggested.

A narrow question, or a stated time box, narrows the **plan**, not the method.
Run the phases the question needs, drop the rest explicitly, and record which
ones were dropped — that list goes into the report so an unmentioned area never
reads as an audited one. Dropping phases is a scoping decision and is fine;
skipping the plan, or reporting an unexamined area as fine, is not.

## Step 4 — Execute, if the user wants the audit

Follow the plan phase by phase. Report findings in the format from
`references/report-template.md`, and the test plan and pre-production checklist
from `references/test-plan.md`.

If a phase reveals the plan was wrong — the scope is bigger, a tool does not
work as expected, an assumption failed — say so and revise the plan rather than
quietly deviating from it.

## Evidence standard

Strength of evidence, in decreasing order: (1) read the full path end to end
and quote the decisive lines; (2) a test exercising the path, and what it
asserts; (3) a caller proving the code is reachable; (4) static reasoning about
code shape — weakest, and labelled as such.

`PARTIAL` and `BROKEN` require a `file:line` pointer. `UNCLEAR` must state what
would resolve it.

**A finding you delegated is evidence level 4 until you verify it yourself.** A
subagent's confident `file:line` citation still rests on which files it chose to
search — a repository with several services or workspaces will happily yield a
consistent, well-cited, wrong conclusion drawn from the wrong one. Before any
delegated P0 or P1 enters the report, re-check its decisive claim against the
component you know to be the right one. Findings that survive get reported;
findings that do not get dropped, not softened.

A control can be dead without anything in its own source looking wrong — a
component nobody routes to, a request nobody subscribes to, a permission code
nobody seeded. `references/edge-cases.md` holds the detection table for these
patterns; work it during Phase 2 rather than trusting the component's source.

## Rationalizations

| Excuse | Reality |
|---|---|
| "The user is in a hurry, I'll skip the plan" | The plan is what prevents an audit of whatever happened to be read first. It costs minutes. |
| "Component exists, so the feature works" | Rule 2. Trace it or mark it `UNCLEAR`. |
| "Senior team / prior review, so it is probably fine" | Prior review is not evidence about this code. Audit it or say you did not. |
| "This is obviously fine, no need to check" | Then quoting the two lines that prove it costs nothing. |
| "I'll note the tools I usually use" | Tools differ per environment. Verify each one exists in this session first. |
| "The subagent cited file:line, so it is confirmed" | It cited a line in whichever files it chose to search. Re-verify every delegated P0/P1 yourself. |
| "A short answer means a short plan is not worth writing" | Shorten the plan's scope, not its existence. Discovery is a few tool calls and is what catches the wrong scope. |
| "Nothing found in that directory, so it is empty" | Check for symlinks, nested workspaces, and ignore rules before concluding absence. |
| "I'll just fix this one obvious bug while I'm here" | Rule 1. Record it as a finding. |
| "Too many sections to inventory them all" | Then the plan says which got shallow coverage. Silent partial inventory reads as "all fine". |

## Red flags — stop and re-read the rules

- Writing report sections before inventory is complete
- Naming a tool without having verified it exists here
- A capability matrix cell filled from the component name alone
- Any `OK` for something never traced to persistence
- Editing a file during an audit
- A finding with no `file:line`
- Concluding "no issues" for an area that was never opened

## Common mistakes

- **Plan with no tooling section** — the plan then says nothing the user could
  not have guessed.
- **Inventory by memory** — enumerate from the filesystem and router config,
  not from what got read along the way.
- **Matrix without notes** — every non-`OK` cell needs a sentence saying what
  exactly is missing.
- **Security findings mixed into UX findings** — they are separately ranked for
  a reason.
- **Recommendations without trade-offs** — architectural proposals state cost,
  not only benefit.

## Reference files

- `references/plan-template.md` — plan structure and tooling table
- `references/audit-phases.md` — what each phase examines
- `references/report-template.md` — report structure and capability matrix
- `references/security-checklist.md` — full security checklist
- `references/edge-cases.md` — edge cases and what to look for in code
- `references/test-plan.md` — test plan and pre-production checklist

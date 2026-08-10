# Audit phases — what each one examines

Detail for the phases named in the plan. Work them in order; phases 3–5 are
independent of each other.

---

## Phase 1 — Inventory

Enumerate from the filesystem and router configuration, never from memory of
what got read along the way. A partial list silently becomes "everything is
fine" for the parts you missed.

- routes / pages / layouts / screens in scope
- components, tables, forms, dialogs, menus, tabs
- API endpoints, server actions, RPC handlers, message consumers
- data models / schema tables the area touches
- permission definitions, roles, policy files, and their seed data
- background jobs, scheduled tasks, side effects

Before concluding a directory is empty: check for symlinks, nested workspaces,
and ignore rules. A file search that follows neither will report zero files for
a full application.

For each section record: purpose, entities involved, operations exposed in the
UI (or in the public contract, for an API), operations existing in the backend,
operations that plausibly belong given the entity's nature.

Cross-reference in **both** directions — the mismatches are the highest-value
findings:

- **backend-only** — capability exists server-side but is unreachable from the
  UI or absent from the contract
- **UI-only** — UI element exists but no backend supports it
- **orphaned** — component or route fully implemented but referenced by nothing

## Phase 2 — Functional verification

Verify each operation against the implementation and fill the capability matrix
(`report-template.md`).

Default operations: list, detail, create, edit, delete, archive/deactivate,
status change, bulk actions, search, filter, sort, pagination, import, export,
confirmation dialogs, form/payload validation, role-based permissions.

For non-CRUD areas substitute the domain's real verbs (start, cancel, retry,
publish, approve, refund, sync) and keep the same rigor. State which default
columns were dropped and why.

Status values: `OK` / `MISSING` / `PARTIAL` / `BROKEN` / `UNCLEAR`.

Then work `edge-cases.md`.

## Phase 3 — Architecture

Assess: layering (UI / business logic / data), code duplication, consistency of
comparable implementations, component reuse, form handling, data fetching and
mutation, cache invalidation after mutation, error handling consistency,
loading state consistency, mutation idempotency, race conditions, transactional
consistency, entity dependencies, client-side vs server-side
pagination/filter/sort, N+1 queries, redundant requests, oversized payloads,
I/O bottlenecks, expected Big-O of the problematic operations.

For each significant problem propose a better design **and its trade-offs**.

## Phase 4 — Security

Work `security-checklist.md` in full. Core axes:

- **AuthN/AuthZ** — the surface is protected; every endpoint independently
  protected; authorization not achieved by hiding a UI control; every sensitive
  operation has a server-side check; object access cannot be manipulated via
  ID/URL/API (IDOR/BOLA); roles correct; no privilege escalation; tenant
  isolation holds.
- **Input** — validated client AND server; SQL/NoSQL injection, command
  injection, XSS, HTML injection, template injection, path traversal, unsafe
  file upload, mass assignment, ID manipulation, unvalidated enum/status values.
- **Sensitive data** — over-fetching to the client, secrets in logs, secrets
  reachable in the client bundle, data shown to users lacking rights, data sent
  to third-party hosts.
- **Destructive operations** — authorization, confirmation, double-execution
  protection, idempotency, audit trail, recovery path.

## Phase 5 — UI/UX

Audit as a frequent user of that area would — a daily operator for back-office,
a first-time visitor for a signup flow.

Navigation consistency, information hierarchy, action naming, visibility of
primary actions, primary vs secondary vs destructive distinction, forms, inline
validation, error messages, loading states, empty states, success feedback,
disabled states, destructive confirmation, post-action navigation, preservation
of filters and pagination when returning from detail, responsiveness,
accessibility, keyboard operation, focus management, table readability,
long-content overflow, modal vs dedicated page, excessive click count.

Weight heavily the moments where the user cannot tell: what just happened,
whether it succeeded, why it failed, or what to do next.

For a pure API scope, replace this phase with contract ergonomics — error shape
consistency, status codes, message usefulness.

## Phase 6 — Cross-module consistency

Compare comparable modules. Typical divergences: one table sorts and another
does not; one section allows editing and a comparable one does not; differing
confirmation dialogs; differing error reporting; different buttons for the same
action; different post-save navigation; different validation of the same value
type; different pagination/filter/search implementations.

Propose what should be unified — and which existing implementation should
become the standard.

## Phase 7 — Missing functionality

From existing entities, APIs, schema, and business logic, identify absent but
sensible functionality. Label each `ASSUMPTION` unless its need is directly
evidenced by implementation or stated requirements.

## Phase 8 — Prioritization

- **P0 Critical** — security flaw, data loss, or fundamentally broken area.
- **P1 High** — important missing/broken function, serious authorization or
  data-integrity problem.
- **P2 Medium** — significant UX, architectural, operational, or
  maintainability problem.
- **P3 Low** — minor UX, consistency, or quality-of-life improvement.

Each finding carries impact, likelihood, size `S`/`M`/`L`, dependencies.

When findings arrive from parallel work, de-duplicate before prioritizing —
the same root cause often surfaces in several modules and should be ranked once.

## Phase 9 — Report

Write it per `report-template.md`, with the test plan and pre-production
checklist from `test-plan.md`.

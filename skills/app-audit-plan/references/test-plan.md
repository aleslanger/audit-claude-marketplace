# Test plan and pre-production checklist

## Test plan structure

Propose tests only at levels the project already supports. If a level does not
exist (no E2E harness, for example), say so and state the cost of adding it
instead of silently assuming it.

### Unit tests

- Validation schemas: valid input, each invalid field, boundary values, unknown
  fields rejected.
- Permission helpers: each role against each operation, including the deny path.
- Pure business logic: status transitions, computed fields, formatting.

### Integration tests

- Each repository/service operation in scope against a real (or test) database.
- Referential behavior on delete: cascade, block, null-out.
- Transactional behavior of multi-step operations, including rollback on
  mid-operation failure.

### API tests

Per endpoint:

- Happy path with a valid payload.
- Missing required fields.
- Wrong types, out-of-range values, invalid enum values.
- Extra fields present (mass-assignment probe).
- Nonexistent ID.
- Pagination bounds: page 0, page beyond the last, oversized page size.
- Filter and sort by an unsupported field.

### Authorization tests

The highest-value block — write one per endpoint, not one per section:

- Unauthenticated request.
- Authenticated but insufficient role.
- Correct role, another tenant's/owner's object ID (IDOR).
- Privilege escalation attempt: self role change, elevating another user.
- Endpoint called directly, bypassing the UI path that hides the control.

### E2E scenarios

Cover the user's real path, not the individual widget. Adapt the flows below to
the domain — they are CRUD-shaped examples, not a fixed list:

- List → filter → open detail → edit → save → return to list with filters intact.
- Create → validation error → correct → save → the record appears in the list.
- Delete with confirmation → record gone → dependent views consistent.
- Bulk action over a selection → per-item result visible.
- Import a file → validation report → applied state.
- Export → file contains exactly the filtered set.

### Negative scenarios

- Server returns 500 during save: is the error shown, is form state preserved?
- Network drop mid-mutation.
- Session expiry mid-form.
- Deleting a record another tab already deleted.

### Race condition and idempotency tests

- Two parallel updates of the same record.
- Same create request sent twice (with the same idempotency key if one exists).
- Delete sent twice.
- Bulk operation overlapping a single-item operation on the same record.

### Regression tests

- One test per fixed finding, named after the finding ID (`ISSUE-001`), asserting
  the specific broken behavior no longer occurs. Prefer naming by `fingerprint`
  where the test must survive renumbering between audits — `id` is positional and
  changes whenever the finding set does.
- Snapshot of the capability matrix as an executable checklist where feasible.

## Pre-production checklist

Concrete and checkable — each line either passes or blocks.

**Security**

- [ ] Every endpoint in scope rejects unauthenticated requests.
- [ ] Every endpoint in scope rejects insufficient roles.
- [ ] Object-level authorization verified for every ID-taking endpoint.
- [ ] No secrets in the client bundle.
- [ ] No sensitive values in logs.
- [ ] Destructive operations have confirmation, audit trail, and server-side
      double-execution protection.
- [ ] Rate limits on sensitive endpoints.

**Functionality**

- [ ] Capability matrix contains no `BROKEN` cells.
- [ ] Every remaining `MISSING` cell is a conscious, recorded decision.
- [ ] No dead buttons, no placeholders, no `TODO` in shipped code paths.
- [ ] Every mutation invalidates the data it affects.

**Data integrity**

- [ ] Referential rules enforced at the database level, not only in code.
- [ ] Multi-step operations are transactional.
- [ ] Concurrency handled on records edited by more than one person.

**UX**

- [ ] Every section has loading, empty, error, and success feedback.
- [ ] Destructive actions visually distinct and confirmed.
- [ ] Filters, sort, and page survive reload and back-navigation.
- [ ] Long content does not break layouts.
- [ ] Primary actions reachable by keyboard; focus moves correctly in dialogs.

**Operations**

- [ ] Errors are logged with enough context to diagnose, without sensitive data.
- [ ] Audit trail covers who did what and when.
- [ ] Recovery path documented for each destructive operation.
- [ ] Test suite green; coverage on the audited paths meets the project's
      threshold.

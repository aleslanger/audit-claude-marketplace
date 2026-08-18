# Edge-case checklist

For each section in scope, check each case against the implementation and record
`OK` / `MISSING` / `BROKEN` / `CANNOT VERIFY`. The right-hand column is what to
look for in code — not what to click.

| Case | What to look for |
|---|---|
| Empty list | Is there an empty state, or does the table render a bare header? Does the count/pagination handle zero? |
| Large result set | Is pagination server-side? Does the endpoint have a LIMIT? Does the client fetch everything and slice? |
| Nonexistent record | Does detail/edit handle a 404 — redirect, message — or crash on `undefined`? |
| Concurrent edit | Any optimistic concurrency (version, updatedAt check)? Or does last write silently win? |
| Double form submit | Is the submit guarded server-side, or only by a disabled button? Is the mutation idempotent? |
| Repeated Delete/Create click | Does a second delete of the same ID error out loudly? Does a second create make a duplicate? |
| Failed request | Is the error surfaced to the user, or swallowed in a `catch` that logs and returns? |
| Timeout | Is there a timeout at all? What state does the UI sit in afterwards? |
| Partial failure in bulk op | Is the bulk operation transactional, or does it half-apply and report success? Is per-item outcome reported? |
| Delete of a referenced entity | Cascade, block, or dangling reference? Is the constraint at DB level or only in code? |
| Refresh mid-operation | Does the operation complete server-side? Can the user tell what state it ended in? |
| Direct URL to detail/edit | Is data fetched and authorized on that route itself, or only when navigated to from the list? |
| Filters/sort in URL | Are filter/sort/page in the URL so they survive reload and back-navigation? |
| Return from detail to list | Are filters and page preserved, or reset to defaults? |
| Stale data after mutation | Is the cache invalidated / list refetched after create, edit, delete? |
| Long content | Does a long name, address, or note break the table layout? |
| Simultaneous status change | Can two users move the same record into conflicting states? |
| Import of a malformed file | Validated before applying? All-or-nothing, or partial import with no report? |
| Export of a large set | Streamed or buffered fully in memory? Authorized per record? |
| Money arithmetic | Are amounts integers (minor units) or `Decimal`, or binary floats? Is rounding direction defined and applied once, not per intermediate step? Do multi-currency conversions record the rate used? Off-by-a-cent errors compound and reconcile to nothing. |
| Schema migration | Is a dropped or renamed column released together with the code that stops reading it, or does the old version break mid-deploy? Is a backfill batched, or one statement locking a large table? Is there a down path? |
| Feature flag | What happens in each state of a flag nobody flips? A flag gating a security control, defaulting open, is an authorization finding. A flag whose off-branch no longer compiles against current code is dead functionality that looks live. |
| Timezone and locale boundary | Are day boundaries computed in the user's zone or the server's? Is a date-only value stored as a timestamp and shifted by conversion? Does number or date parsing depend on the process locale? Applies where the audited area genuinely spans zones or locales. |

## Dead and half-wired code patterns

A control can be non-functional without looking broken. These patterns all
present as a normal, enabled UI element that does nothing. Check each
explicitly — none is visible from the component's own source alone.

| Pattern | How to detect |
|---|---|
| Component never routed | Grep the component name across routes and template imports. Zero hits outside its own files = unreachable, however complete it is. |
| Route exists, nothing links to it | Grep for the path in navigation and templates. An implemented edit screen with no entry point is a missing feature, not a working one. |
| Handler never subscribed / never awaited | Cold observables, unawaited promises, and returned-but-discarded requests never fire. Check that the call site consumes the result. |
| Element reference resolved inside a conditional | A view/element reference declared inside an `if` block is undefined while that block is closed. Optional-chained calls on it silently no-op. |
| Class or attribute toggled with no rule behind it | Grep the toggled class in the stylesheets. No matching rule = the toggle changes nothing visible. |
| Method defined, template calls a different one | Compare every handler in the class against the names actually referenced in the template. |
| Service method with no caller | A backend-backed method nobody calls means the capability is unreachable from the UI. |
| Permission code enforced but never seeded | Cross-check codes used in route guards against the permission seed data. An unseeded code cannot be granted to any role — the feature is permanently locked for non-superusers. |
| Enum written in one casing, filtered in another | Compare the values written at each call site against the values the filter offers. An exact-match filter over mismatched casing always returns zero rows. |
| Frontend bypasses its own authenticated proxy | Compare each client base URL against the backend's proxy routes. A direct call to the upstream service skips auth and permission checks. |
| Placeholder persistence | Search for fabricated paths, hardcoded IDs, and comments like "would need backend" near save handlers. The record saves; the referenced artifact was never stored. |
| Field submitted but absent from the server contract | Compare form fields against the request DTO. A field the server ignores produces a success message and no change. |

## Background jobs and queues

Jobs are inventoried in Phase 1 but fail in ways a request never does. For each
job in scope:

| Case | What to look for |
|---|---|
| Job raises | Retried, dead-lettered, or silently swallowed? Does a `catch` that logs count as handling? |
| Poison message | Does one permanently-failing item block the queue, or retry forever? Is there an attempt limit? |
| Duplicate delivery | At-least-once delivery means the handler runs twice — is the side effect idempotent? (Judge with retry, per `finding-model.md` §6.) |
| Job never runs | Is the schedule registered anywhere, and does anything alert when a run is missed? A job nobody scheduled is dead code with a plausible name. |
| Overlapping runs | Can a long run still be executing when the next one starts? Is there a lock? |

## Notes

- A guard implemented only in the client counts as `MISSING`, not `PARTIAL`.
- If a case cannot be established without running the app, write
  `CANNOT VERIFY` and state what run would settle it.
- Cases that recur across every section belong in the architecture findings as
  a single systemic issue, not repeated per section.

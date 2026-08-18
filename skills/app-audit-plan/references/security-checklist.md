# Security checklist

Every item below is checked against the server implementation, never against
the UI. Privileged surfaces — back-office, admin APIs, anything mutating other
users' data — get the strictest reading, but the checklist applies to any
authenticated area.

## Three marks, not two

A checkbox has two states, and a security control has three. Record each item as:

```
[x] holds        [ ] missing — a finding        [—] not applicable, because <reason>
```

**`[—]` is mandatory where the trust boundary does not exist.** Checks are
activated by boundaries this application actually has (`finding-model.md` §6): a
single-tenant system owes no tenant-isolation finding, and a service with no file
uploads owes no upload finding. Without the third mark, an unchecked box reads as
a missing control, and the audit reports absent mechanisms the system never
needed — which buries the real findings under noise and costs the report its
credibility.

The reason is what makes `[—]` honest rather than a way out: "not applicable —
single-tenant, one `organization_id` in the schema and no tenant column on any
table" is checkable. "N/A" is not.

Where applicability is what you could not determine, that is `CANNOT VERIFY` with
a `resolves_when`, not `[—]`.

## Authentication and authorization

- [ ] The surface itself requires authentication where it should.
- [ ] Every API endpoint / server action enforces auth independently of the page
      that calls it. Middleware or layout guards alone are not enough — confirm
      the endpoint is not reachable without them.
- [ ] Authorization is not achieved by hiding a UI control. Hidden button +
      unprotected endpoint = unprotected endpoint.
- [ ] Every sensitive operation has an explicit server-side permission check.
- [ ] Object-level access is enforced: an ID from URL, body, or query cannot be
      swapped to reach another tenant's or user's record (IDOR / BOLA).
- [ ] Tenant / workspace isolation holds on every query, not only on the entry
      query.
- [ ] Caches are keyed by whoever the data belongs to. A per-user or per-tenant
      response cached under a key that omits identity serves one account's data to
      another — check application caches, HTTP cache headers, and any CDN in front.
- [ ] Role definitions are consistent between UI and server.
- [ ] No privilege escalation: a user cannot grant themselves a role, edit their
      own permissions, or change another user's role beyond their level.
- [ ] Session/token handling: expiry enforced server-side, no long-lived
      privileged tokens in client storage without cause.

## Input validation

Validate at the boundary, on the server, for every field — not only fields the
form exposes.

- [ ] SQL / NoSQL injection — no string concatenation into queries; parameterized
      or ORM-bound everywhere.
- [ ] Command injection — no user data reaching shell execution unescaped.
- [ ] XSS — output escaped; check every raw-HTML injection point
      (`dangerouslySetInnerHTML`, `v-html`, `innerHTML`, template raw filters).
- [ ] HTML injection in emails, exports, PDFs generated from user-supplied data.
- [ ] Template injection where user data is fed to a template engine.
- [ ] Path traversal in file download/upload/export paths.
- [ ] Unsafe file upload — type, size, extension, storage location, and whether
      uploaded files can be served back as executable content.
- [ ] Mass assignment — request body spread directly into a model/update call.
- [ ] ID manipulation — IDs trusted from the client for ownership decisions.
- [ ] Enum / status values validated against the allowed set server-side.
- [ ] Numeric bounds, string length, and date sanity enforced server-side.

## Sensitive data

- [ ] API responses do not return more fields than the UI needs (password
      hashes, tokens, internal flags, other users' PII).
- [ ] List endpoints do not over-serialize related entities.
- [ ] Sensitive values are not written to logs (credentials, tokens, full
      request bodies of auth endpoints, personal data where regulated).
- [ ] No secrets in client-side code or in the bundle (API keys, service
      credentials, privileged config).
- [ ] No secrets committed to the repository: `.env` files tracked in git, keys
      hardcoded in server code, credentials in CI config or fixtures. Check git
      history, not only the working tree — a removed secret stays in the history
      and stays valid until rotated.
- [ ] The area does not display data to roles that must not see it.
- [ ] Error responses do not leak stack traces, SQL, or internal paths.
- [ ] Deletion of personal data actually deletes it. A "delete user" that soft-flags
      the row while PII stays in the table, in backups, in logs, and in analytics is
      not erasure — trace where each copy lives. Applies wherever a retention
      window or a right to erasure is claimed.

## Destructive operations

For delete, disable, reset, refund, permission change, bulk action:

- [ ] Server-side authorization on the exact operation, not just on the section
      or route it lives under.
- [ ] Explicit confirmation before execution.
- [ ] Protection against double execution (disabled control is not enough —
      needs server-side guard or idempotency key).
- [ ] Idempotent, or safely rejecting a repeated request.
- [ ] Audit trail: who, what, when, from where.
- [ ] Recovery path where appropriate (soft delete, restore, undo window).
- [ ] Referential safety: deleting an entity referenced elsewhere either cascades
      deliberately, blocks with a clear message, or nulls out — never leaves
      dangling references silently.

## Dependencies

A dependency finding needs a reachable impact path like any other
(`finding-model.md` §6): "uses an old library" with nothing reaching the
vulnerable code is not a P0. What makes it worth checking anyway is that the
tooling is cheap and the answer is often decisive.

- [ ] Lockfile present and committed, so the built artifact is reproducible.
- [ ] Known advisories in direct dependencies triaged — `npm audit`,
      `pip-audit`, `cargo audit`, or the ecosystem's equivalent. Record which
      command was run; an untriaged advisory list is not a finding, and neither
      is silence about whether anyone looked.
- [ ] For each advisory that matters, the reachable path stated: which call site
      reaches the vulnerable function with attacker-influenced input.
- [ ] Dependencies pulled from unexpected sources — a git URL, a fork, a private
      registry, a package name one character from a popular one.

## Rate limiting and abuse

- [ ] Sensitive endpoints (login, reset, bulk export, anything expensive) rate
      limited.
- [ ] Bulk operations bounded in size.
- [ ] Export endpoints bounded, or streamed, and authorized per record set.

## Reporting

For each finding state:

- Whether it is exploitable **today** or requires an additional precondition.
- The minimal proof from the code (quoted lines).
- The smallest fix that closes it — prefer a server-side check over a UI change.

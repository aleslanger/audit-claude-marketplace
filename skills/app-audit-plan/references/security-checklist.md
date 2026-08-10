# Security checklist

Every item below is checked against the server implementation, never against
the UI. Privileged surfaces — back-office, admin APIs, anything mutating other
users' data — get the strictest reading, but the checklist applies to any
authenticated area.

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
- [ ] The area does not display data to roles that must not see it.
- [ ] Error responses do not leak stack traces, SQL, or internal paths.

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

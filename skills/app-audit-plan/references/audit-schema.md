# AUDIT.json schema and validation

Machine-readable form of the canonical model in `finding-model.md`. Field
meanings live there; this file specifies the wire format, the validation rules,
and the bridge to `FIX_PLAN.json`.

Reference implementation: `scripts/audit_schema.py`.

---

## Document shape

```json
{
  "schema_version": "1.0",
  "generated": "2026-08-13T10:00:00",
  "scope": "admin area",
  "authorized_scope": ["apps/admin/"],
  "inventory": {
    "static": {
      "items": ["/admin/users", "/admin/orders", "/admin/reports"],
      "method": "next router config + glob app/**/page.tsx",
      "command": "rg -l 'export default' app --glob '*/page.tsx'"
    }
  },
  "coverage": {
    "static":  { "mode": "FULL",    "discovered": 3, "excluded": 1, "reviewed": 2,
                 "reviewed_items": ["/admin/users", "/admin/orders"] },
    "runtime": { "mode": "PARTIAL", "discovered": 3, "excluded": 0, "reviewed": 0,
                 "not_reviewed": ["/admin/users", "..."] }
  },
  "excluded": [ { "item": "/admin/reports", "reason": "scheduled for removal" } ],
  "findings": [ ... ]
}
```

`inventory` and `authorized_scope` are optional — documents predating them still
validate — but when `inventory` is present the coverage denominator is checked
against it rather than taken on trust.

`coverage` carries `static` and `runtime` separately; they are never summed.
Either may be omitted when that mode was not attempted — an omitted mode is not
a claim of coverage.

## Finding object

```json
{
  "id": "ISSUE-001",
  "fingerprint": "a3f2c1d4e5b6",
  "title": "Delete endpoint has no server-side authorization",
  "category": "security",
  "severity": "CRITICAL",
  "likelihood": "LIKELY",
  "priority": "P0",
  "status": "BROKEN",
  "confidence": "CONFIRMED",
  "location": "src/api/users/route.ts:42",
  "evidence": [
    {
      "kind": "code-read",
      "location": "src/api/users/route.ts:42",
      "quote": "export async function DELETE(req) { await db.user.delete(...) }",
      "proves": "handler deletes without reading session or checking role"
    }
  ],
  "impact": "any authenticated user can delete any account",
  "proposed_fix": "assert caller role server-side before delete",
  "size": "S",
  "depends_on": []
}
```

### Field reference

| Field | Required | Values |
|---|---|---|
| `id` | ✓ | `ISSUE-NNN`, unique in document |
| `fingerprint` | ✓ | 12 hex chars, stable across audits |
| `title` | ✓ | free text |
| `category` | ✓ | `security` `bug` `missing-feature` `architecture` `ux` `data-integrity` `performance` `consistency` |
| `severity` | ✓ | `CRITICAL` `HIGH` `MEDIUM` `LOW` |
| `likelihood` | ✓ | `CERTAIN` `LIKELY` `OCCASIONAL` `RARE` |
| `priority` | ✓ | `P0` `P1` `P2` `P3` |
| `status` | ✓ | `OK` `PARTIAL` `BROKEN` `MISSING` `CANNOT VERIFY` |
| `confidence` | ✓ | `CONFIRMED` `PROBABLE` `INFERRED` |
| `location` | ✓ | `path:line`, or `-` for `MISSING` |
| `evidence` | ✓ | array; may be empty **only** when `status` is `OK` |
| `blocked_by` / `resolves_when` | required when `status` is `CANNOT VERIFY` | free text |
| `depends_on` | — | array of `id` values present in the document |
| `supersedes` | — | fingerprint of the same problem from an earlier audit, when the file has since moved; must differ from this finding's own fingerprint |
| `needs_reverification` / `confidence_note` | — | set by `decay_confidence` when evidence predates the current revision of the file it cites |
| `impact` `proposed_fix` `size` | — | free text / `S` `M` `L` |

Each evidence record may also carry `commit` — the revision the file was read at.
It is optional, so audits without git context are unaffected; when present, it is
what lets stale evidence be detected later.

Unknown fields are preserved and ignored. Consumers must not fail on them.

### Helpers in `scripts/audit_schema.py`

| Function | Purpose |
|---|---|
| `validate_document(doc)` | Every violation, as a list; empty means valid |
| `review_summary(doc, mode)` | Splits the inventory into reviewed / not reviewed / excluded / unaccounted |
| `diff_inventory(before, after)` | Items added, removed, unchanged between two audits |
| `compare_audits(prev, cur, reviewed_locations, previously_fixed=None)` | Classifies findings as `FIXED` / `DISAPPEARED` / `STILL_OPEN` / `REGRESSED` / `NEW` |
| `decay_confidence(finding, current_commits)` | Lowers stale `CONFIRMED` to `PROBABLE`; returns a new object |
| `is_known_finding(finding, known_fingerprints)` | Matches on fingerprint or `supersedes` |
| `to_fix_plan_issues(doc)` / `to_fix_plan_md(doc)` | Projection for `quality-loop` |

`compare_audits` needs `reviewed_locations` precisely because `FIXED` and
`DISAPPEARED` are indistinguishable without it.

---

## Validation rules

A document violating any of these is invalid output, not a stylistic problem.

**Identity**
1. `id` present and matching `ISSUE-\d{3,}`.
2. `id` unique within the document.
3. `fingerprint` present and non-empty.
4. One fingerprint never maps to two different `(category, location, rule)`
   triples — a collision means two distinct problems share an identity.
5. No `F-\d+` in any `id`. Legacy input is converted on read, never emitted.

**Evidence**
6. Any finding whose `status` is not `OK` has at least one evidence record.
6a. `status: OK` cannot carry a severity of `CRITICAL`, `HIGH`, or `MEDIUM`.
    `severity` is defined as the harm of a **defect**; `OK` asserts there is no
    defect, so the combination is incoherent by definition — `LOW` is the only
    coherent severity for an `OK` finding. It also closes a bypass of *NO OK
    WITHOUT EVIDENCE*, since `OK` waives the evidence requirement.
    *Counter-argument considered:* "a fixed CRITICAL bug should be markable OK."
    It should not — a fixed defect is either absent from the report or carried
    with its real status; `OK` + CRITICAL is not how history is expressed.
7. Every evidence record has `kind`, `location`, and `proves`.
8. `confidence: CONFIRMED` requires evidence of kind `code-read`, `test-run`, or
   `runtime-observation`. `static-reasoning` alone caps confidence at `INFERRED`.
9. `status: PARTIAL` or `BROKEN` requires a `location` containing a line number.

**Enums**
10. `severity`, `likelihood`, `priority`, `status`, `confidence`, and `category`
    each hold a listed value. Unknown enum values are rejected, not coerced.
11. `priority` is consistent with the severity/likelihood matrix in
    `finding-model.md`, unless `priority_override_reason` is present and
    non-empty.

**Cannot-verify**
12. `status: CANNOT VERIFY` requires non-empty `blocked_by` and `resolves_when`.

**References**
13. Every `depends_on` entry names an `id` present in the same document.
13a. `supersedes`, when present, differs from the finding's own `fingerprint`.
     A rename changes the fingerprint by design; `supersedes` is what carries
     continuity across it, so superseding itself asserts a move that did not
     happen. See "What a fingerprint does not survive" in `finding-model.md`.

**Coverage**
14. `reviewed <= discovered - excluded` for each mode.
15. `mode: FULL` requires `reviewed == discovered - excluded` for that mode.
16. `mode: SAMPLED` requires a stated selection method.
17. `excluded` count matches the length of the document's `excluded` list.

**Inventory** — applied only when `inventory` is present
18. `discovered` equals the number of enumerated `items`.
19. Every `reviewed_items` entry appears in the inventory.
20. `reviewed` equals the length of `reviewed_items`.
21. Every `excluded` item appears in the inventory.
22. Each item is in exactly one state — reviewed, excluded, or `not_reviewed`.
    An item in none of them is `ITEM_UNACCOUNTED`; in two, `ITEM_CONTRADICTORY_STATE`.
23. `mode: FULL` requires every non-excluded inventory item to be reviewed **by
    name**, not merely by count.
24. `items` contains no duplicates, and the inventory states its `method`, so a
    later audit can reproduce the enumeration and diff it.
24a. Every mode declaring coverage is enumerated. A mode may reuse another's
     enumeration with `{ "same_as": "static" }` rather than repeating it, but it
     may not simply omit one — an un-enumerated mode would skip every check above
     while still asserting a denominator.

**Authorized scope** — applied only when `authorized_scope` is present
25. Every finding `location` falls inside the authorized scope.
26. Every evidence `location` falls inside it too — citing a file proves it was
    read, so an out-of-scope citation is a disclosure regardless of the finding.

**Security**
18. A finding with `category: security` and `priority` of `P0`/`P1` states an
    `impact`. Severity is never lowered to match a scheduling decision; use
    `priority_override_reason` instead.

---

## Relationship to FIX_PLAN.json

`AUDIT.json` is a superset. `FIX_PLAN.json` — consumed by `quality-loop` via
`scripts/fix_plan_parser.py` — keeps its existing shape:

```json
{ "id": "...", "severity": "...", "title": "...",
  "file": "...", "problem": "...", "fix": "...", "status": "open" }
```

Conversion, implemented by `audit_schema.to_fix_plan_issues`:

| FIX_PLAN field | From AUDIT.json |
|---|---|
| `id` | `id` unchanged — both use `ISSUE-NNN` |
| `severity` | `severity` unchanged |
| `title` | `title` |
| `file` | `location` |
| `problem` | `impact`, else `title` |
| `fix` | `proposed_fix` |
| `status` | `open` — this is *workflow* state, not audit `status` |

Two distinct meanings of the word `status` meet here and must not be conflated:

| | Values | Meaning |
|---|---|---|
| Audit `status` | `OK` `PARTIAL` `BROKEN` `MISSING` `CANNOT VERIFY` | What the audit found |
| FIX_PLAN `status` | `open` `resolved` `blocked` | Where the fix stands |

Findings that are not actionable — `status: OK`, or `CANNOT VERIFY`, which has no
fix to apply — are excluded from the FIX_PLAN projection. A `CANNOT VERIFY` item
handed to `quality-loop` would be an instruction to fix something nobody
established was broken.

The existing `FIX_PLAN.md` heading format is unchanged, so the existing parser
and `quality-loop` continue to work against both old and new plans.

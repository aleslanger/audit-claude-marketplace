# Canonical finding model

One definition of a finding, used by every phase, both output formats, and every
consumer. If a term below is described differently anywhere else in the
repository, this file wins.

---

## 1. Identity

Two separate concepts. Never collapse them into one.

| Concept | What it is | Stable across audits? |
|---|---|---|
| `id` | Position in **this** report — `ISSUE-001`, `ISSUE-002`, … | No |
| `fingerprint` | Identity of the **problem itself** | Yes |

`id` is assigned sequentially after prioritization, so it renumbers whenever the
finding set changes. It is a label for humans reading one report, nothing more.
Never use it to decide whether two audits found the same problem.

`fingerprint` answers "is this the same problem I saw last time". It is what
lets a second audit recognize a finding as already-known rather than new.

### Computing a fingerprint

```
fingerprint = sha1(category + "|" + normalized_location + "|" + rule)[:12]
```

- `category` — the finding's category value (§4).
- `normalized_location` — repository-relative path, **without** the line number.
  Line numbers move when unrelated code above them changes; including them would
  give the same problem a new fingerprint after any edit.
- `rule` — a short stable slug for the *kind* of defect, not its prose title:
  `missing-server-authz`, `idor-object-access`, `dead-control-unrouted`,
  `non-idempotent-mutation`. Titles get reworded between audits; slugs must not.

Two properties this must satisfy, both of which are testable:

- **Stable** — the same defect, audited twice **with the file in the same place**,
  yields the same fingerprint. This is why the prose title and the line number
  are excluded.
- **Distinguishing** — two different defects never collide. Two problems in one
  file are distinguished by their `rule`; the same rule genuinely occurring in
  two files is distinguished by `normalized_location`.

If one file legitimately has two instances of the same rule (two unprotected
endpoints in one router file), append a discriminator to `rule` —
`missing-server-authz#deleteUser`. Do not fall back to the line number.

### What a fingerprint does not survive

**A rename or move changes the fingerprint.** This is a consequence of the two
properties above, not an oversight: `normalized_location` is in the hash because
without it every `missing-server-authz` in the repository would collide, and a
hash of the current location cannot also encode a location it no longer has.

The tradeoff is deliberate — collisions silently merge two real defects into one,
whereas a rename produces a *visible* new fingerprint that a human can reconcile.
Prefer the failure that is noticeable.

Do not try to solve this by weakening the hash. When continuity across a move
matters, record it explicitly:

```
- **supersedes:** <previous fingerprint>
```

`supersedes` is how a finding claims to be the same problem as one from an
earlier audit whose file has since moved. Tooling comparing two audits treats a
finding as already-known if its fingerprint matches **or** it supersedes a known
one. This keeps history correct without pretending the hash can do something it
cannot.

A large refactor will therefore surface findings as new. That is the correct
report — the audit genuinely re-examined relocated code — and `supersedes` links
them back where the continuity is worth recording.

### Legacy `F-01`

`F-01`/`F-xx` was the previous format. It is **legacy** and must not be produced
by new audits. Conversion is positional: the finding at position *n* in the
priority-ordered list becomes `ISSUE-<n zero-padded to 3>`. `F-01` → `ISSUE-001`.

Reading a legacy document is allowed. Writing one is not.

---

## 2. Evidence

A finding does not exist without evidence. Every non-`OK` claim carries at least
one evidence record, and every evidence record states what it actually proves —
which is usually narrower than the claim it is cited for.

```
- **kind:** code-read | test-run | caller-trace | static-reasoning | runtime-observation
- **location:** path/to/file.ts:123
- **quote:** the decisive lines
- **proves:** the specific proposition this establishes
```

Strength, strongest first:

| Kind | Establishes | Does not establish |
|---|---|---|
| `runtime-observation` | The behavior occurred in a running system | That it occurs in every case |
| `code-read` | What the code on that path does | That the path is reachable |
| `test-run` | The asserted property holds | Anything the test does not assert |
| `caller-trace` | The code is reachable | That it behaves correctly |
| `static-reasoning` | A shape or pattern | Actual behavior — weakest, label it |

Rules that follow from the table:

- **Documentation is never evidence of behavior.** A README, a comment, a ticket,
  or a changelog describes intent. `CONFIRMED` requires code or runtime, never
  prose. Documentation may only support a finding *about documentation*.
- **A passing scenario is not proof of completeness.** A runtime test showing one
  tenant cannot read another's record proves that case. It does not prove tenant
  isolation holds generally. State the scenario, not the generalization.
- **A delegated finding is `static-reasoning` until re-verified.** A subagent's
  `file:line` is only as good as the files it chose to search.

---

## 3. Status and confidence

`status` — what the audit concluded:

| Value | Meaning |
|---|---|
| `OK` | Traced end to end and works |
| `PARTIAL` | Works for some cases, not all — requires `file:line` |
| `BROKEN` | Does not work — requires `file:line` |
| `MISSING` | Capability absent entirely |
| `CANNOT VERIFY` | Not determinable in this environment |

`confidence` — how well the status is evidenced: `CONFIRMED` (evidence kinds
`code-read`, `test-run`, or `runtime-observation`), `PROBABLE` (`caller-trace`),
`INFERRED` (`static-reasoning` only, or delegated and not re-verified).

`CONFIRMED` requires at least one evidence record of a qualifying kind. A finding
whose only evidence is `static-reasoning` cannot be `CONFIRMED`, regardless of
how obvious it looks.

### `CANNOT VERIFY`

Never a soft "probably fine". It is an explicit, permanent marker that something
was **not** established, and it must carry a resolution condition:

```
- **blocked_by:** no runtime environment | no database access | external service | needs product decision
- **resolves_when:** the concrete step that would settle it
```

A `CANNOT VERIFY` without `resolves_when` is invalid output. Unavailable runtime
or infrastructure keeps `CANNOT VERIFY` — it never degrades to `OK`, and an
unknown state is never reported as a vulnerability either (§6).

---

## 4. Classification

`category` — what kind of problem: `security`, `bug`, `missing-feature`,
`architecture`, `ux`, `data-integrity`, `performance`, `consistency`.

`severity` — how bad the outcome is **if it happens**. A property of the defect
alone; never adjusted for business convenience:

| Value | Meaning |
|---|---|
| `CRITICAL` | Data loss, data breach, or authorization bypass |
| `HIGH` | Core capability broken, or integrity violated |
| `MEDIUM` | Significant degradation with a workaround |
| `LOW` | Cosmetic or minor quality-of-life |

`likelihood` — how often it is actually reached: `CERTAIN`, `LIKELY`,
`OCCASIONAL`, `RARE`.

`priority` — scheduling decision, `P0`–`P3`, derived from severity and likelihood:

| | CERTAIN | LIKELY | OCCASIONAL | RARE |
|---|---|---|---|---|
| **CRITICAL** | P0 | P0 | P0 | P1 |
| **HIGH** | P0 | P1 | P1 | P2 |
| **MEDIUM** | P1 | P2 | P2 | P3 |
| **LOW** | P2 | P3 | P3 | P3 |

**Severity and priority are distinct and both are required.** Severity describes
the defect; priority describes the schedule. Business pressure may move
`priority`; it may never rewrite `severity`. A `CRITICAL` finding deprioritized
to `P2` stays `CRITICAL` in the record, and the reason for the deviation is
stated explicitly.

A security finding reaches P0/P1 only with a demonstrated impact path — which
data, reachable by whom. "Uses an old library" with no reachable impact is not
P0. Absence of evidence of impact is not evidence of impact.

---

## 5. Coverage

Coverage is computed from the Phase 1 inventory, never estimated.

```
coverage = reviewed / (discovered - excluded)
```

- `discovered` — items enumerated from the filesystem and router config.
- `excluded` — deliberately out of scope, each with a stated reason. Counted and
  listed, never silently dropped.
- `reviewed` — items actually examined and carrying a status.

### The inventory manifest

Record the **items themselves**, not only their count, along with how they were
enumerated:

```
- **items:** /admin/users, /admin/orders, /admin/reports
- **method:** next router config + glob app/**/page.tsx
- **command:** rg -l 'export default' app --glob '*/page.tsx'
```

A bare count is a claim the auditor makes about their own thoroughness; a list is
checkable. With the manifest, `discovered` must equal the number of enumerated
items, and every reviewed item must be one of them — an audit that found forty
routes can no longer report `FULL` coverage of ten.

Recording `method` and `command` also lets a later audit re-run the same
enumeration and **diff the inventory**, so a route added or deleted since the
last audit is visible rather than inferred.

Static and runtime usually enumerate the same surface; the second may reuse the
first rather than repeating it. What it may not do is omit its inventory —
an un-enumerated mode skips every check while still reporting a denominator.

### Every item lands in exactly one state

```
reviewed  |  excluded  |  not_reviewed
```

There is no fourth state. An item present in the inventory but in none of the
three is unaccounted for, and unaccounted reads as fine to every later reader —
which is the failure this rule exists to prevent. List items as `not_reviewed`
explicitly; that is an honest report, whereas omission is not.

An item may not be in two states at once.

Static and runtime coverage are tracked **separately** and never summed. Having
read every route says nothing about having run any of them.

| Mode | Claim permitted when |
|---|---|
| `FULL` | `reviewed == discovered - excluded`, for that mode |
| `PARTIAL` | Anything less — must list what was not reviewed |
| `SAMPLED` | A subset chosen deliberately — must state selection method and size |

`FULL` is a factual claim about the denominator, not a judgement. If one of ten
discovered items is unreviewed, coverage is `PARTIAL` at 9/10, whatever the
importance of the tenth. `SAMPLED` never implies anything about unsampled items,
and a sampled audit may not report an area as clean on the strength of the
sample.

---

## 5a. Comparing two audits

When a previous audit exists, every earlier finding is classified — never
silently dropped:

| Outcome | Meaning |
|---|---|
| `STILL_OPEN` | Present again |
| `REGRESSED` | Was fixed, is back |
| `FIXED` | Gone, **and** its location was re-reviewed |
| `DISAPPEARED` | Gone, but its location was not re-reviewed |
| `NEW` | Not in the previous audit |

`FIXED` and `DISAPPEARED` look identical if you only compare finding lists, and
conflating them is how an audit gradually overstates progress: problems appear
solved because nobody looked at them again. `DISAPPEARED` therefore resolves to
`CANNOT VERIFY`, not to success, and says which location needs re-review.

A renamed file changes the fingerprint, so `supersedes` (§1) is what keeps a
moved finding from being reported as one problem fixed and another discovered.

## 5b. Evidence ages

Evidence is a statement about a **specific revision**. Record it:

```
- **commit:** abc123def456
```

Once the cited file has moved on, `CONFIRMED` no longer holds — the finding
describes code that may no longer exist. Confidence drops to `PROBABLE` and the
finding is flagged for re-verification. This matters because a fix plan is worked
over days or weeks, and a finding confirmed against a since-rewritten file is a
historical note, not a current claim.

Evidence with no recorded commit makes no freshness claim and is left alone, so
an audit run without git context behaves exactly as before. Confidence only ever
decays; re-verification is what raises it again.

## 6. Threat model activation

Security checks are activated by **trust boundaries that exist in this
application**, not by a generic list.

- A finding requires a reachable impact path. The absence of a technology is not
  itself a finding: no rate limiter is only a finding where an endpoint is both
  expensive or sensitive **and** externally reachable.
- Unknown state is `CANNOT VERIFY`, not a vulnerability. "I could not determine
  whether this endpoint checks authorization" is not "this endpoint is
  unprotected".
- Absence of a mechanism the system does not need is not a gap. Single-tenant
  systems do not owe tenant isolation findings. Say why the control does not
  apply rather than reporting it missing.
- Retry and idempotency are judged **together** wherever a duplicate side effect
  is possible. A retry with no idempotency key is a finding; either alone may be
  fine.

---

## 6a. The audit's own authorization

An audit reads code and sometimes data. In a monorepo, a multi-tenant system, or
a client engagement, *what the audit itself may read* is a real boundary — and
the audit is the one process nobody is auditing.

Record what was authorized:

```
- **authorized_scope:** apps/admin/
```

Every finding location **and every evidence location** must fall inside it.
Evidence is checked because citing a file proves it was opened: an out-of-scope
citation is a disclosure regardless of whether the finding is valid.

Where the boundary is unclear, ask before reading rather than after. A finding
obtained by reading outside the engagement is not usable, however real it is, and
reporting it discloses what should not have been read. When something out of
scope looks genuinely dangerous, report *that the boundary should be extended*
and why — do not quietly widen it.

## 7. Serialization

Both outputs are generated from one canonical model:

```
canonical findings
      ├── AUDIT.md    (human)
      └── AUDIT.json  (machine)
```

Never two independent implementations of the same logic — they drift.

Required fields on every finding: `id`, `fingerprint`, `title`, `category`,
`severity`, `likelihood`, `priority`, `status`, `confidence`, `location`,
`evidence`. Optional: `depends_on`, `blocked_by`, `resolves_when`, `impact`,
`proposed_fix`, `size`.

Consumers must ignore unknown fields rather than failing, so the schema can grow.
Every required field must survive `serialize → parse → compare` unchanged; see
`audit-schema.md` for the validation rules and `scripts/audit_schema.py` for the
implementation.

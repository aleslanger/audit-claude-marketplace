# Post-implementation review

Applies when work produced a diff — fixes the user asked for after an audit, or
changes to the audit tooling itself. A plain audit changes nothing (Rule 1) and
does not need this.

**Finishing the implementation is not finishing the work.** Review is a separate
pass over the **final diff**, not a memory of decisions made while writing it.
The two find different things: reviewing as you go finds local mistakes, and
reviewing the diff finds what the changes did to each other.

Where an independent reviewer agent exists, prefer one that did not write the
code. Treat its output as claims, not verdicts — a confident `file:line` from an
agent that searched the wrong workspace is wrong with full conviction. Verify
every significant finding against the real diff before acting on it.

---

## 1. Diff review

Read the complete final diff before anything else. Check:

- changes match the requested scope
- no unrelated files touched
- no refactor nobody asked for
- no existing skill's behavior changed without reason
- no existing hard rule removed or weakened
- no generated artifacts, temp files, or debug output committed
- no fixture edited such that it stops testing the original problem

Explain or revert every unexpected change. "It seemed better" is a reason to
raise it separately, not to include it.

## 2. Cross-file consistency

Every normative concept used in more than one place must mean the same thing
everywhere. Grep the repository for each concept and each of its old and new
spellings:

```
ISSUE-NNN   fingerprint   severity   likelihood   priority
evidence    confidence    CANNOT VERIFY   ASSUMPTION
coverage modes    audit manifest    finding status
```

Search explicitly for stale identifier formats:

```
F-01    F-xx    ISSUE-001    ISSUE-NNN
```

After a migration, two conflicting canonical formats must not coexist. A format
kept for backward compatibility is **explicitly labelled legacy** and has one
unambiguous conversion path. Two live canonical formats is a bug, not a
transition.

## 3. Invariant re-check

These are the skill's reason for existing. Re-verify each still holds — a new
instruction that lets any of them be bypassed makes the implementation wrong,
and it gets fixed before the work is called done.

```
AUDIT DOES NOT MODIFY APPLICATION CODE
INVENTORY BEFORE VERDICT
NO OK WITHOUT EVIDENCE
NO FEATURE VERIFIED ONLY FROM UI EXISTENCE
END-TO-END FLOW TRACING
SERVER-SIDE AUTHORIZATION REQUIRED
CANNOT VERIFY IS EXPLICIT
ASSUMPTIONS ARE EXPLICIT
NO INVENTED TOOLING
DELEGATED P0/P1 MUST BE RE-VERIFIED
PARTIAL COVERAGE MUST NOT CLAIM FULL COVERAGE
```

## 4. Adversarial pass

Second pass, this time trying to break the design. Work these questions
concretely against the implementation, not from memory of intent.

**Finding model**
- Can one problem get two different fingerprints across two audits?
- Can two different problems collide onto one fingerprint?
- Can a finding exist with no evidence?
- Can a security finding reach high priority with no demonstrated impact?
- Can severity and priority be confused for each other?

**Evidence**
- Can something be `CONFIRMED` from documentation alone?
- Is it clear what each individual evidence record proves?
- Does a runtime test's single scenario get read as proof of completeness?
- Is `CANNOT VERIFY` preserved where runtime or infrastructure is unavailable?

**Coverage**
- Can an audit claim `FULL` while discovered items went unreviewed?
- Is the denominator genuinely derived from the inventory?
- Are exclusions counted transparently?
- Is runtime coverage separated from static?
- Can sampling create a false impression of completeness?

**Threat model**
- Does absence of a technology alone generate findings?
- Are security controls activated by real trust boundaries?
- Is an unknown state ever reported as a vulnerability?

**Reliability**
- Does a checklist demand mechanisms this system does not need?
- Is "no need for it" distinguished from "protection missing"?
- Are retry and idempotency judged together where duplicate side effects are
  possible?

**Machine-readable output**
- Does every finding serialize losslessly?
- Does parsing it back preserve meaning?
- Are `id` and `fingerprint` separate?
- Do two schemas represent the same concept?
- Does the change break an existing parser or `quality-loop`?

Fix each real problem, then repeat the pass — fixes introduce their own defects.

## 4a. Do not churn settled decisions

A review that removes what the previous review added, and the one after that puts
it back, costs more than either decision was worth. The output stops converging
and the reader stops trusting it.

Oscillation has one cause: **a constraint whose reason was never written down**.
A later reviewer sees only the rule, cannot reconstruct what it prevents,
reasonably judges it arbitrary, and deletes it. The next reviewer rediscovers the
original problem and re-adds it. Both are acting correctly on the information
they have.

So the fix is not "review less". It is that every non-obvious constraint carries
its own justification at the point where someone would remove it:

- The **reason** — what breaks without it, concretely.
- The **counter-argument it already survived** — the plausible case for removing
  it, and why that case loses. This is what stops the next reviewer from
  re-litigating it from scratch.
- A **test named after the thing it prevents**, so deleting the rule fails
  something legible rather than silently widening what is accepted.

Prefer a definitional justification over an anti-abuse one. "Nobody would do
that" defeats "this stops someone doing X", but it cannot defeat "these two
fields mean contradictory things".

Before changing a rule an earlier pass deliberately established, state which of
these applies:

| Situation | Action |
|---|---|
| New evidence the rule is wrong | Change it, and record the evidence |
| The rule's reason no longer holds | Change it, and say what changed |
| Rule looks arbitrary, no reason recorded | Find the reason first — check tests and history before touching it |
| Personal preference, rule still sound | Leave it |

When a tradeoff is genuinely two-sided, record the decision and the losing
alternative rather than the winning side alone. A documented tradeoff gets
respected; an undocumented one gets flipped. The same applies to a limitation
that cannot be designed away — write down that it is inherent and which failure
mode was chosen deliberately, so it is not repeatedly "fixed".

## 5. Backward compatibility

Verify the existing workflow still runs:

```
audit-to-plan → FIX_PLAN.md / FIX_PLAN.json → quality-loop
```

and the new one:

```
app-audit-plan → canonical findings → AUDIT.md / AUDIT.json
```

and, where canonical output feeds the fixer:

```
app-audit-plan → canonical findings → quality-loop
```

Matching field *names* is not compatibility. Verify the consumer contract:
required fields, optional fields, status values, severity values, ID formats,
ordering assumptions, unknown-field handling, missing-optional handling. Add a
regression fixture for any new format that a parser must read.

## 6. Round-trip validation

For any machine-readable output:

```
canonical object → serialize → parse → canonical object
```

Meaning must survive for `id`, `fingerprint`, `status`, `category`, `severity`,
`priority`, `location`, evidence references, and dependencies.

Where Markdown and JSON are both produced, generate both from one model:

```
canonical data model
      ├── AUDIT.md
      └── AUDIT.json
```

Two independent implementations of the same logic drift apart; one of them is
then silently wrong.

## 7. Golden fixtures

Keep fixtures small enough that a change to the expected result is reviewable.
Cover at least:

```
known IDOR                     known dead control
known cross-tenant leak        known duplicate mutation
known CANNOT VERIFY            known partial coverage
known external dependency failure    known monorepo scope trap
```

Assert structural invariants — finding exists, correct category, correct evidence
location, correct severity class, correct `CANNOT VERIFY` behavior, correct
coverage denominator. Never assert exact prose, and never snapshot cosmetic
Markdown formatting; such tests fail on rewording and get disabled.

## 8. Negative validation

Invalid output must be rejected, not quietly accepted. At minimum:

```
finding without ID                  finding without fingerprint
non-OK finding without evidence     duplicate finding ID
duplicate conflicting fingerprint   unknown severity
invalid priority                    evidence reference to nonexistent evidence
coverage reviewed > discovered      FULL audit with incomplete static coverage
CANNOT VERIFY without resolution condition
```

Without a runtime schema validator, implement these invariants in whatever
validation mechanism exists.

## 9. Mutation mindset

Ask: **if I introduced this bug deliberately, which test would catch it?**

```
ISSUE-NNN reverted to F-01        finding without fingerprint
evidence removed                  FULL coverage at 9/10 reviewed
broken JSON field                 severity enum changed
quality-loop expecting the old contract
```

A severe regression with no detection mechanism means the validation is
incomplete — add it. Never leave a deliberate defect in the final commit.

## 10. Documentation review

- README matches the real workflow
- examples match the canonical schema
- no documented command or capability that does not exist
- no broken cross-references between `.md` files
- one normative definition is not described differently in two places
- new profiles are genuinely discoverable from `SKILL.md`
- no old example uses an invalid finding format

Grep the whole repository for removed or renamed terms.

## 11. Security review of the change itself

This skill governs security audits of other projects, so a weakening here
propagates. Verify the change cannot:

- weaken authorization checks in the audit methodology
- let a client-side guard be accepted as server-side authorization
- mark an unverified state as safe
- ignore tenant isolation
- hide a high-impact finding behind coverage or sampling
- rewrite security severity to match business priority
- accept a delegated security finding without re-verification
- put sensitive data into machine-readable artifacts or logs without cause

## 12. Final gate

```
1. repository validation          7. full diff review
2. relevant unit tests            8. cross-file consistency review
3. integration/parser tests       9. invariant review
4. fixture/golden tests          10. adversarial review
5. backward compatibility tests  11. documentation review
6. canonical schema validation   12. security review
```

Any step not performed is reported as `CANNOT VERIFY`, stating what could not be
verified, why, the impact, and the exact step or environment needed. Do not call
the work fully validated while a blocking gate is unrun.

## 13. Review findings must be closed

Track findings as `RV-001`, `RV-002`, … each with:

```
Problem   Severity   Evidence   Resolution   Validation   Status
```

Every one ends as `RESOLVED`, `ACCEPTED_WITH_REASON`, or `CANNOT_VERIFY`.
`ACCEPTED_WITH_REASON` is never a way to make tests pass, and a Critical or High
finding cannot hold that status without an explicit technical justification.

**`RV-NNN` is a review-local counter, not a canonical finding ID.** It lives in
the review write-up for the duration of one review pass; it is deliberately
absent from `finding-model.md`, from the `AUDIT.json` schema, and from
`validate_document`, and there is no validator for it.

*Counter-argument considered:* "an ID format with no validation is an
oversight — give `RV` a schema like `ISSUE-NNN` has." It is not. `ISSUE-NNN`
identifies a defect **in the audited application**, which outlives the audit and
therefore needs a fingerprint, evidence, and a wire format. `RV-NNN` identifies a
comment **about a diff**, and is closed within the same pass that opened it —
nothing consumes it afterwards. Giving it a schema would create a second
finding-identity space for consumers to reconcile, which §2 exists to prevent.

A review finding that *does* outlive the review — a real defect the diff
introduced and nobody fixed — does not stay an `RV`. Promote it to a canonical
`ISSUE-NNN` finding with a fingerprint and evidence, and say in the review
write-up which `RV` became which `ISSUE`.

## 14. Definition of Done

In addition to the normal criteria:

- the final diff passed a separate review
- no unexplained out-of-scope changes
- canonical concepts are consistent repository-wide
- backward compatibility was actually tested
- machine-readable schema passed round-trip validation
- negative schema/invariant tests pass
- no `FULL` audit can pass with incomplete required coverage
- all P0/P1 review findings resolved
- documentation review found no stale examples or broken references
- declared tests were **run**, and their real results reported
- no test called passing that was not run
- every unverified area is explicitly `CANNOT VERIFY`

The final response carries a `Post-implementation review` section with: review
scope, review findings, fixes made after review, tests rerun after those fixes,
remaining `CANNOT VERIFY` items, and the verdict — exactly one of:

```
VALIDATED
VALIDATED WITH KNOWN LIMITATIONS
NOT FULLY VALIDATED
```

`VALIDATED` requires that every relevant blocking gate actually passed.

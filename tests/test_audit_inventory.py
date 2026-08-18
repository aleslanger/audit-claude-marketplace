"""Inventory manifest, review completeness, cross-audit comparison, evidence age.

These close gaps the finding schema alone cannot: a coverage denominator that is
merely asserted, an item silently neither reviewed nor excluded, a finding that
vanishes without being fixed, and evidence that has outlived the code it cites.
"""

import pytest

import scripts.audit_schema as schema


def make_inventory(items=None, **overrides):
    inventory = {
        "static": {
            "items": items if items is not None else [
                "/admin/users", "/admin/orders", "/admin/reports",
            ],
            "method": "next router config + glob app/**/page.tsx",
            "command": "rg -l 'export default' app --glob '*/page.tsx'",
        }
    }
    inventory["static"].update(overrides)
    return inventory


def make_reviewed(*names):
    return list(names)


def error_codes(doc):
    return {e.code for e in schema.validate_document(doc)}


def make_doc(inventory=None, coverage=None, findings=None, excluded=None, **extra):
    doc = {
        "schema_version": schema.SCHEMA_VERSION,
        "generated": "2026-08-13T10:00:00",
        "scope": "admin area",
        "excluded": excluded if excluded is not None else [],
        "findings": findings if findings is not None else [],
        "coverage": coverage if coverage is not None else {
            "static": {"mode": "FULL", "discovered": 3, "excluded": 0, "reviewed": 3,
                       "reviewed_items": ["/admin/users", "/admin/orders", "/admin/reports"]}
        },
    }
    if inventory is not None:
        doc["inventory"] = inventory
    doc.update(extra)
    return doc


# ---------------------------------------------------------------------------
# 1. inventory manifest — the denominator must be derived, not asserted
# ---------------------------------------------------------------------------

class TestInventoryManifest:
    def test_document_with_consistent_inventory_is_valid(self):
        assert schema.validate_document(make_doc(make_inventory())) == []

    def test_discovered_must_match_inventory_length(self):
        """A denominator that disagrees with the enumerated items is a false claim."""
        doc = make_doc(make_inventory(["/a", "/b", "/c", "/d", "/e"]))
        assert "DISCOVERED_MISMATCH" in error_codes(doc)

    def test_inventory_requires_a_method(self):
        """Without the method, a later audit cannot reproduce the enumeration."""
        inventory = make_inventory()
        del inventory["static"]["method"]
        assert "INVENTORY_METHOD_MISSING" in error_codes(make_doc(inventory))

    def test_inventory_items_must_be_unique(self):
        doc = make_doc(make_inventory(["/admin/users", "/admin/users", "/admin/orders"]))
        assert "INVENTORY_DUPLICATE" in error_codes(doc)

    def test_reviewed_items_must_come_from_inventory(self):
        """Reviewing something never discovered means the inventory is wrong."""
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "PARTIAL", "discovered": 3, "excluded": 0,
                                 "reviewed": 1, "reviewed_items": ["/admin/ghost"]}},
        )
        assert "REVIEWED_NOT_IN_INVENTORY" in error_codes(doc)

    def test_reviewed_count_must_match_reviewed_items(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "FULL", "discovered": 3, "excluded": 0,
                                 "reviewed": 3, "reviewed_items": ["/admin/users"]}},
        )
        assert "REVIEWED_COUNT_MISMATCH" in error_codes(doc)

    def test_full_coverage_requires_every_inventory_item_reviewed(self):
        """The invariant this whole mechanism exists to enforce."""
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "FULL", "discovered": 3, "excluded": 0,
                                 "reviewed": 2,
                                 "reviewed_items": ["/admin/users", "/admin/orders"]}},
        )
        codes = error_codes(doc)
        assert "FULL_COVERAGE_INCOMPLETE" in codes

    def test_excluded_items_leave_the_denominator(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "FULL", "discovered": 3, "excluded": 1,
                                 "reviewed": 2,
                                 "reviewed_items": ["/admin/users", "/admin/orders"]}},
            excluded=[{"item": "/admin/reports", "reason": "removal scheduled"}],
        )
        assert schema.validate_document(doc) == []

    def test_excluded_item_must_exist_in_inventory(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "FULL", "discovered": 3, "excluded": 1,
                                 "reviewed": 2,
                                 "reviewed_items": ["/admin/users", "/admin/orders"]}},
            excluded=[{"item": "/admin/nonexistent", "reason": "typo"}],
        )
        assert "EXCLUDED_NOT_IN_INVENTORY" in error_codes(doc)

    def test_a_mode_cannot_evade_checks_by_omitting_its_inventory(self):
        """Partial inventories must not create a silent hole.

        If any mode has an inventory, a mode that declares coverage without one
        would otherwise skip every cross-check while still claiming a denominator.
        """
        doc = make_doc(
            make_inventory(),  # static only
            coverage={
                "static": {"mode": "FULL", "discovered": 3, "excluded": 0, "reviewed": 3,
                           "reviewed_items": ["/admin/users", "/admin/orders", "/admin/reports"]},
                "runtime": {"mode": "FULL", "discovered": 3, "excluded": 0, "reviewed": 3,
                            "reviewed_items": ["/admin/users", "/admin/orders", "/admin/reports"]},
            },
        )
        assert "INVENTORY_MODE_MISSING" in error_codes(doc)

    def test_shared_inventory_can_be_declared_once(self):
        """A mode may point at another mode's enumeration instead of repeating it."""
        inventory = make_inventory()
        inventory["runtime"] = {"same_as": "static"}
        doc = make_doc(
            inventory,
            coverage={
                "static": {"mode": "FULL", "discovered": 3, "excluded": 0, "reviewed": 3,
                           "reviewed_items": ["/admin/users", "/admin/orders", "/admin/reports"]},
                "runtime": {"mode": "PARTIAL", "discovered": 3, "excluded": 0, "reviewed": 1,
                            "reviewed_items": ["/admin/users"],
                            "not_reviewed": ["/admin/orders", "/admin/reports"]},
            },
        )
        assert schema.validate_document(doc) == []
        assert schema.review_summary(doc, "runtime")["reviewed"] == ["/admin/users"]

    def test_shared_inventory_must_point_at_a_real_mode(self):
        inventory = make_inventory()
        inventory["runtime"] = {"same_as": "nonexistent"}
        doc = make_doc(inventory)
        assert "INVENTORY_BAD_REFERENCE" in error_codes(doc)

    def test_inventory_is_optional_for_backward_compatibility(self):
        """Existing documents without an inventory still validate."""
        doc = make_doc(
            coverage={"static": {"mode": "FULL", "discovered": 3, "excluded": 0, "reviewed": 3}}
        )
        assert schema.validate_document(doc) == []

    def test_inventory_diff_detects_added_and_removed_items(self):
        before = ["/admin/users", "/admin/orders"]
        after = ["/admin/users", "/admin/billing"]
        diff = schema.diff_inventory(before, after)
        assert diff["added"] == ["/admin/billing"]
        assert diff["removed"] == ["/admin/orders"]
        assert diff["unchanged"] == ["/admin/users"]


# ---------------------------------------------------------------------------
# 2. review completeness — silence must not read as "fine"
# ---------------------------------------------------------------------------

class TestReviewCompleteness:
    def test_every_item_is_reviewed_excluded_or_explicitly_not_reviewed(self):
        """Three states, no fourth. An unaccounted item is the bug this catches."""
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "PARTIAL", "discovered": 3, "excluded": 0,
                                 "reviewed": 1, "reviewed_items": ["/admin/users"]}},
        )
        assert "ITEM_UNACCOUNTED" in error_codes(doc)

    def test_declaring_not_reviewed_accounts_for_the_item(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "PARTIAL", "discovered": 3, "excluded": 0,
                                 "reviewed": 1, "reviewed_items": ["/admin/users"],
                                 "not_reviewed": ["/admin/orders", "/admin/reports"]}},
        )
        assert schema.validate_document(doc) == []

    def test_item_cannot_be_both_reviewed_and_not_reviewed(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "PARTIAL", "discovered": 3, "excluded": 0,
                                 "reviewed": 2,
                                 "reviewed_items": ["/admin/users", "/admin/orders"],
                                 "not_reviewed": ["/admin/orders", "/admin/reports"]}},
        )
        assert "ITEM_CONTRADICTORY_STATE" in error_codes(doc)

    def test_unaccounted_items_are_reported_by_name(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "PARTIAL", "discovered": 3, "excluded": 0,
                                 "reviewed": 1, "reviewed_items": ["/admin/users"]}},
        )
        message = " ".join(e.message for e in schema.validate_document(doc))
        assert "/admin/orders" in message and "/admin/reports" in message

    def test_review_summary_separates_the_three_states(self):
        doc = make_doc(
            make_inventory(),
            coverage={"static": {"mode": "PARTIAL", "discovered": 3, "excluded": 1,
                                 "reviewed": 1, "reviewed_items": ["/admin/users"],
                                 "not_reviewed": ["/admin/orders"]}},
            excluded=[{"item": "/admin/reports", "reason": "scheduled for removal"}],
        )
        summary = schema.review_summary(doc, "static")
        assert summary["reviewed"] == ["/admin/users"]
        assert summary["not_reviewed"] == ["/admin/orders"]
        assert summary["excluded"] == ["/admin/reports"]
        assert summary["unaccounted"] == []


# ---------------------------------------------------------------------------
# 3. cross-audit comparison — a vanished finding is not a fixed finding
# ---------------------------------------------------------------------------

class TestCrossAuditComparison:
    def build(self, fingerprint, location, status="BROKEN"):
        return {"fingerprint": fingerprint, "location": location, "status": status,
                "id": "ISSUE-001", "title": "t"}

    def test_finding_gone_from_reviewed_location_is_fixed(self):
        previous = [self.build("aaa", "src/api/orders.ts:18")]
        result = schema.compare_audits(previous, [], reviewed_locations={"src/api/orders.ts"})
        assert result["FIXED"] == ["aaa"]

    def test_finding_gone_from_unreviewed_location_is_not_fixed(self):
        """The single most common way an audit quietly starts lying."""
        previous = [self.build("aaa", "src/api/orders.ts:18")]
        result = schema.compare_audits(previous, [], reviewed_locations=set())
        assert result["DISAPPEARED"] == ["aaa"]
        assert result["FIXED"] == []

    def test_disappeared_findings_are_reported_as_cannot_verify(self):
        previous = [self.build("aaa", "src/api/orders.ts:18")]
        result = schema.compare_audits(previous, [], reviewed_locations=set())
        assert result["cannot_verify"] == ["aaa"]

    def test_finding_still_present_is_open(self):
        previous = [self.build("aaa", "src/api/orders.ts:18")]
        current = [self.build("aaa", "src/api/orders.ts:18")]
        result = schema.compare_audits(previous, current, reviewed_locations={"src/api/orders.ts"})
        assert result["STILL_OPEN"] == ["aaa"]

    def test_finding_returning_after_being_fixed_is_a_regression(self):
        previous = [self.build("aaa", "src/api/orders.ts:18")]
        current = [self.build("aaa", "src/api/orders.ts:18")]
        result = schema.compare_audits(
            previous, current, reviewed_locations={"src/api/orders.ts"},
            previously_fixed={"aaa"},
        )
        assert result["REGRESSED"] == ["aaa"]
        assert result["STILL_OPEN"] == []

    def test_renamed_finding_is_tracked_via_supersedes_not_reported_new(self):
        previous = [self.build("aaa", "src/api/export.ts:44")]
        current = [{"fingerprint": "bbb", "supersedes": "aaa", "id": "ISSUE-001",
                    "title": "t", "location": "src/routes/export.ts:84", "status": "BROKEN"}]
        result = schema.compare_audits(
            previous, current, reviewed_locations={"src/routes/export.ts", "src/api/export.ts"})
        assert result["STILL_OPEN"] == ["aaa"]
        assert result["NEW"] == []
        assert result["DISAPPEARED"] == []

    def test_genuinely_new_finding_is_new(self):
        current = [self.build("ccc", "src/api/billing.ts:9")]
        result = schema.compare_audits([], current, reviewed_locations={"src/api/billing.ts"})
        assert result["NEW"] == ["ccc"]

    def test_every_previous_finding_lands_in_exactly_one_bucket(self):
        previous = [
            self.build("aaa", "src/a.ts:1"),
            self.build("bbb", "src/b.ts:1"),
            self.build("ccc", "src/c.ts:1"),
        ]
        current = [self.build("aaa", "src/a.ts:1")]
        result = schema.compare_audits(previous, current, reviewed_locations={"src/a.ts", "src/b.ts"})
        buckets = result["FIXED"] + result["DISAPPEARED"] + result["STILL_OPEN"] + result["REGRESSED"]
        assert sorted(buckets) == ["aaa", "bbb", "ccc"]


# ---------------------------------------------------------------------------
# 4. evidence age — CONFIRMED is not permanent
# ---------------------------------------------------------------------------

class TestEvidenceAge:
    def make_finding_with_commit(self, commit=None):
        record = {"kind": "code-read", "location": "src/api/route.ts:42",
                  "proves": "handler deletes without checking role",
                  "quote": "export async function DELETE(req) { await db.user.delete(...) }"}
        if commit:
            record["commit"] = commit
        return {"id": "ISSUE-001", "fingerprint": "a" * 12, "title": "t",
                "category": "bug", "severity": "HIGH", "likelihood": "LIKELY",
                "priority": "P1", "status": "BROKEN", "confidence": "CONFIRMED",
                "location": "src/api/route.ts:42", "evidence": [record]}

    def test_evidence_commit_is_optional(self):
        """Audits without git context must keep working."""
        doc = make_doc(findings=[self.make_finding_with_commit()],
                       coverage={"static": {"mode": "PARTIAL", "discovered": 0,
                                            "excluded": 0, "reviewed": 0}})
        assert schema.validate_document(doc) == []

    def test_evidence_with_commit_is_valid(self):
        doc = make_doc(findings=[self.make_finding_with_commit("abc123def456")],
                       coverage={"static": {"mode": "PARTIAL", "discovered": 0,
                                            "excluded": 0, "reviewed": 0}})
        assert schema.validate_document(doc) == []

    def test_confidence_decays_when_the_cited_file_moved_on(self):
        finding = self.make_finding_with_commit("abc123")
        stale = schema.decay_confidence(finding, {"src/api/route.ts": "def456"})
        assert stale["confidence"] == "PROBABLE"

    def test_confidence_holds_when_the_file_is_unchanged(self):
        finding = self.make_finding_with_commit("abc123")
        fresh = schema.decay_confidence(finding, {"src/api/route.ts": "abc123"})
        assert fresh["confidence"] == "CONFIRMED"

    def test_decay_records_why_it_happened(self):
        finding = self.make_finding_with_commit("abc123")
        stale = schema.decay_confidence(finding, {"src/api/route.ts": "def456"})
        assert "abc123" in stale["confidence_note"]
        assert stale["needs_reverification"] is True

    def test_decay_leaves_uncommitted_evidence_alone(self):
        """No commit recorded means no claim about freshness to invalidate."""
        finding = self.make_finding_with_commit()
        assert schema.decay_confidence(finding, {"src/api/route.ts": "def456"}) == finding

    def test_decay_does_not_mutate_the_input(self):
        finding = self.make_finding_with_commit("abc123")
        schema.decay_confidence(finding, {"src/api/route.ts": "def456"})
        assert finding["confidence"] == "CONFIRMED"

    def test_decay_never_raises_confidence(self):
        finding = self.make_finding_with_commit("abc123")
        finding["confidence"] = "INFERRED"
        assert schema.decay_confidence(finding, {"src/api/route.ts": "def456"})["confidence"] == "INFERRED"


# ---------------------------------------------------------------------------
# 5. audit authorization scope
# ---------------------------------------------------------------------------

class TestAuditAuthorization:
    def test_authorized_scope_is_optional(self):
        doc = make_doc(coverage={"static": {"mode": "PARTIAL", "discovered": 0,
                                            "excluded": 0, "reviewed": 0}})
        assert schema.validate_document(doc) == []

    def test_finding_outside_the_authorized_scope_is_rejected(self):
        """The audit itself must stay inside what it was permitted to read."""
        finding = {"id": "ISSUE-001", "fingerprint": "a" * 12, "title": "t",
                   "category": "security", "severity": "HIGH", "likelihood": "LIKELY",
                   "priority": "P1", "status": "BROKEN", "confidence": "CONFIRMED",
                   "location": "apps/other-tenant/src/api.ts:9",
                   "impact": "x",
                   "evidence": [{"kind": "code-read", "location": "apps/other-tenant/src/api.ts:9",
                                 "proves": "y", "quote": "return db.query(sql)"}]}
        doc = make_doc(findings=[finding],
                       coverage={"static": {"mode": "PARTIAL", "discovered": 0,
                                            "excluded": 0, "reviewed": 0}},
                       authorized_scope=["apps/admin/"])
        assert "OUT_OF_AUTHORIZED_SCOPE" in error_codes(doc)

    def test_finding_inside_the_authorized_scope_is_accepted(self):
        finding = {"id": "ISSUE-001", "fingerprint": "a" * 12, "title": "t",
                   "category": "security", "severity": "HIGH", "likelihood": "LIKELY",
                   "priority": "P1", "status": "BROKEN", "confidence": "CONFIRMED",
                   "location": "apps/admin/src/api.ts:9", "impact": "x",
                   "evidence": [{"kind": "code-read", "location": "apps/admin/src/api.ts:9",
                                 "proves": "y", "quote": "return db.query(sql)"}]}
        doc = make_doc(findings=[finding],
                       coverage={"static": {"mode": "PARTIAL", "discovered": 0,
                                            "excluded": 0, "reviewed": 0}},
                       authorized_scope=["apps/admin/"])
        assert schema.validate_document(doc) == []

    def test_evidence_outside_the_authorized_scope_is_rejected(self):
        """Citing a file proves it was read — the check covers evidence too."""
        finding = {"id": "ISSUE-001", "fingerprint": "a" * 12, "title": "t",
                   "category": "bug", "severity": "HIGH", "likelihood": "LIKELY",
                   "priority": "P1", "status": "BROKEN", "confidence": "CONFIRMED",
                   "location": "apps/admin/src/api.ts:9",
                   "evidence": [{"kind": "code-read",
                                 "location": "apps/other-tenant/secrets.ts:1",
                                 "proves": "y", "quote": "return db.query(sql)"}]}
        doc = make_doc(findings=[finding],
                       coverage={"static": {"mode": "PARTIAL", "discovered": 0,
                                            "excluded": 0, "reviewed": 0}},
                       authorized_scope=["apps/admin/"])
        assert "OUT_OF_AUTHORIZED_SCOPE" in error_codes(doc)


# ---------------------------------------------------------------------------
# mutation sensitivity for the new rules
# ---------------------------------------------------------------------------

class TestNewRuleMutationDetection:
    @pytest.mark.parametrize("mutate,expected", [
        (lambda d: d["coverage"]["static"].update(discovered=99), "DISCOVERED_MISMATCH"),
        (lambda d: d["coverage"]["static"].update(reviewed_items=["/admin/users"]),
         "REVIEWED_COUNT_MISMATCH"),
        (lambda d: d["inventory"]["static"].pop("method"), "INVENTORY_METHOD_MISSING"),
    ])
    def test_mutation_is_detected(self, mutate, expected):
        doc = make_doc(make_inventory())
        assert schema.validate_document(doc) == []
        mutate(doc)
        assert expected in error_codes(doc)

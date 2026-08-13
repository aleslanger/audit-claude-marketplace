"""Canonical audit finding model: validation, round-trip, and compatibility.

Structural invariants only — no assertions on prose wording, so the tests stay
useful when titles and descriptions are reworded.
"""

import copy
import json

import pytest

import scripts.audit_schema as schema


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def make_finding(**overrides):
    """A minimal valid finding; override single fields per test."""
    finding = {
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
                "quote": "export async function DELETE(req) { await db.user.delete() }",
                "proves": "handler deletes without checking session or role",
            }
        ],
        "impact": "any authenticated user can delete any account",
        "proposed_fix": "assert caller role server-side before delete",
        "size": "S",
    }
    finding.update(overrides)
    return finding


def make_document(findings=None, coverage=None, excluded=None):
    return {
        "schema_version": schema.SCHEMA_VERSION,
        "generated": "2026-08-13T10:00:00",
        "scope": "admin area",
        "coverage": coverage
        if coverage is not None
        else {"static": {"mode": "FULL", "discovered": 3, "excluded": 1, "reviewed": 2}},
        "excluded": excluded if excluded is not None else [
            {"item": "legacy/", "reason": "scheduled for removal"}
        ],
        "findings": findings if findings is not None else [make_finding()],
    }


def error_codes(doc):
    return {e.code for e in schema.validate_document(doc)}


# --------------------------------------------------------------------------
# fingerprint
# --------------------------------------------------------------------------

class TestFingerprint:
    def test_same_defect_yields_same_fingerprint(self):
        a = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz")
        b = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz")
        assert a == b

    def test_line_number_does_not_change_fingerprint(self):
        """Unrelated edits above a defect must not re-identify it."""
        a = schema.compute_fingerprint("security", "src/api/route.ts:42", "missing-server-authz")
        b = schema.compute_fingerprint("security", "src/api/route.ts:87", "missing-server-authz")
        assert a == b

    def test_title_rewording_does_not_change_fingerprint(self):
        """Fingerprint derives from the rule slug, never the prose title."""
        a = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz")
        b = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz")
        assert a == b

    def test_different_rules_in_same_file_differ(self):
        a = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz")
        b = schema.compute_fingerprint("security", "src/api/route.ts", "idor-object-access")
        assert a != b

    def test_same_rule_in_different_files_differs(self):
        a = schema.compute_fingerprint("security", "src/api/users.ts", "missing-server-authz")
        b = schema.compute_fingerprint("security", "src/api/orders.ts", "missing-server-authz")
        assert a != b

    def test_different_categories_differ(self):
        a = schema.compute_fingerprint("security", "src/api/route.ts", "dead-control")
        b = schema.compute_fingerprint("ux", "src/api/route.ts", "dead-control")
        assert a != b

    def test_discriminator_separates_two_instances_of_one_rule(self):
        """Two unprotected endpoints in one file are two findings, not one."""
        a = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz#deleteUser")
        b = schema.compute_fingerprint("security", "src/api/route.ts", "missing-server-authz#deleteOrder")
        assert a != b

    def test_path_normalization_is_stable(self):
        a = schema.compute_fingerprint("security", "./src/api/route.ts:42", "r")
        b = schema.compute_fingerprint("security", "src/api/route.ts", "r")
        assert a == b

    def test_rename_changes_fingerprint_by_design(self):
        """Documented consequence, not a defect.

        Location is in the hash so that the same rule in two files does not
        collide. A hash of the current location cannot also encode a location the
        file no longer has, so a move produces a new fingerprint. `supersedes`
        carries continuity instead — see test_supersedes_links_across_a_rename.
        Removing location from the hash to "fix" this would silently merge
        distinct defects, which is the worse failure.
        """
        before = schema.compute_fingerprint("security", "src/api/orders.ts", "missing-server-authz")
        after = schema.compute_fingerprint("security", "src/routes/orders.ts", "missing-server-authz")
        assert before != after

    def test_supersedes_links_across_a_rename(self):
        """Continuity across a move is explicit, never inferred from the hash."""
        old_fp = schema.compute_fingerprint("security", "src/api/orders.ts", "missing-server-authz")
        new_fp = schema.compute_fingerprint("security", "src/routes/orders.ts", "missing-server-authz")
        finding = make_finding(fingerprint=new_fp, supersedes=old_fp)
        assert schema.validate_document(make_document([finding])) == []
        assert schema.is_known_finding(finding, {old_fp}) is True

    def test_finding_without_supersedes_is_new_after_a_move(self):
        new_fp = schema.compute_fingerprint("security", "src/routes/orders.ts", "missing-server-authz")
        old_fp = schema.compute_fingerprint("security", "src/api/orders.ts", "missing-server-authz")
        assert schema.is_known_finding(make_finding(fingerprint=new_fp), {old_fp}) is False

    def test_matching_fingerprint_is_known_without_supersedes(self):
        fp = schema.compute_fingerprint("security", "src/api/orders.ts", "missing-server-authz")
        assert schema.is_known_finding(make_finding(fingerprint=fp), {fp}) is True

    def test_two_successive_audits_recognize_unmoved_findings(self):
        """End-to-end continuity, not just the hash property in isolation.

        Second audit of the same tree after unrelated edits pushed each defect
        ~40 lines down, and one file was moved. Unmoved defects must be
        recognized with no bookkeeping; the moved one only via `supersedes`.
        """
        first = {
            "idor": schema.compute_fingerprint("security", "src/api/orders.ts:18", "idor-object-access"),
            "tenant": schema.compute_fingerprint("security", "src/api/export.ts:44", "missing-tenant-filter"),
            "refund": schema.compute_fingerprint("data-integrity", "src/api/refunds.ts:27", "non-idempotent-mutation"),
        }
        second = {
            "idor": schema.compute_fingerprint("security", "src/api/orders.ts:58", "idor-object-access"),
            "tenant": schema.compute_fingerprint("security", "src/routes/export.ts:84", "missing-tenant-filter"),
            "refund": schema.compute_fingerprint("data-integrity", "src/api/refunds.ts:67", "non-idempotent-mutation"),
        }
        known = set(first.values())

        assert schema.is_known_finding({"fingerprint": second["idor"]}, known) is True
        assert schema.is_known_finding({"fingerprint": second["refund"]}, known) is True

        # The moved file is genuinely a new fingerprint until continuity is declared.
        assert schema.is_known_finding({"fingerprint": second["tenant"]}, known) is False
        assert schema.is_known_finding(
            {"fingerprint": second["tenant"], "supersedes": first["tenant"]}, known
        ) is True

    def test_supersedes_cannot_point_at_itself(self):
        f = make_finding(fingerprint="a" * 12, supersedes="a" * 12)
        assert "SELF_SUPERSEDE" in error_codes(make_document([f]))


# --------------------------------------------------------------------------
# valid documents
# --------------------------------------------------------------------------

class TestValidDocument:
    def test_minimal_valid_document_passes(self):
        assert schema.validate_document(make_document()) == []

    def test_ok_finding_needs_no_evidence(self):
        """Nothing is asserted broken, so there is nothing to evidence."""
        ok = make_finding(
            status="OK", severity="LOW", likelihood="RARE", priority="P3",
            confidence="PROBABLE", evidence=[],
        )
        assert schema.validate_document(make_document([ok])) == []

    def test_ok_finding_cannot_claim_confirmed_without_evidence(self):
        """CONFIRMED is a claim about evidence, so it still needs some."""
        ok = make_finding(
            status="OK", severity="LOW", likelihood="RARE", priority="P3",
            confidence="CONFIRMED", evidence=[],
        )
        assert "UNSUPPORTED_CONFIRMED" in error_codes(make_document([ok]))

    def test_unknown_fields_are_accepted(self):
        """Schema must be able to grow without breaking existing consumers."""
        doc = make_document([make_finding(future_field="whatever")])
        doc["future_top_level"] = {"anything": True}
        assert schema.validate_document(doc) == []


# --------------------------------------------------------------------------
# negative validation
# --------------------------------------------------------------------------

class TestIdentityValidation:
    def test_finding_without_id_rejected(self):
        f = make_finding()
        del f["id"]
        assert "MISSING_ID" in error_codes(make_document([f]))

    def test_finding_without_fingerprint_rejected(self):
        f = make_finding()
        del f["fingerprint"]
        assert "MISSING_FINGERPRINT" in error_codes(make_document([f]))

    def test_duplicate_id_rejected(self):
        a = make_finding(id="ISSUE-001", fingerprint="aaaaaaaaaaaa")
        b = make_finding(id="ISSUE-001", fingerprint="bbbbbbbbbbbb")
        assert "DUPLICATE_ID" in error_codes(make_document([a, b]))

    def test_conflicting_fingerprint_rejected(self):
        """One fingerprint must not describe two different problems."""
        a = make_finding(id="ISSUE-001", fingerprint="aaaaaaaaaaaa",
                         location="src/a.ts:1", category="security")
        b = make_finding(id="ISSUE-002", fingerprint="aaaaaaaaaaaa",
                         location="src/b.ts:9", category="ux")
        assert "FINGERPRINT_COLLISION" in error_codes(make_document([a, b]))

    def test_same_fingerprint_at_same_location_is_not_a_collision(self):
        """Re-reporting one problem is a duplicate ID issue, not a collision."""
        a = make_finding(id="ISSUE-001", fingerprint="aaaaaaaaaaaa", location="src/a.ts:1")
        b = make_finding(id="ISSUE-002", fingerprint="aaaaaaaaaaaa", location="src/a.ts:1")
        assert "FINGERPRINT_COLLISION" not in error_codes(make_document([a, b]))

    def test_legacy_f01_id_rejected(self):
        """The old format must not be emitted after migration."""
        assert "LEGACY_ID_FORMAT" in error_codes(make_document([make_finding(id="F-01")]))


class TestEvidenceValidation:
    def test_non_ok_finding_without_evidence_rejected(self):
        assert "MISSING_EVIDENCE" in error_codes(
            make_document([make_finding(status="BROKEN", evidence=[])])
        )

    def test_evidence_without_proves_rejected(self):
        f = make_finding(evidence=[{"kind": "code-read", "location": "a.ts:1"}])
        assert "EVIDENCE_MISSING_PROVES" in error_codes(make_document([f]))

    def test_evidence_with_unknown_kind_rejected(self):
        f = make_finding(evidence=[
            {"kind": "vibes", "location": "a.ts:1", "proves": "x"}
        ])
        assert "INVALID_EVIDENCE_KIND" in error_codes(make_document([f]))

    def test_confirmed_from_static_reasoning_alone_rejected(self):
        """Code shape is not proof of behavior."""
        f = make_finding(confidence="CONFIRMED", evidence=[
            {"kind": "static-reasoning", "location": "a.ts:1", "proves": "looks unguarded"}
        ])
        assert "UNSUPPORTED_CONFIRMED" in error_codes(make_document([f]))

    def test_inferred_from_static_reasoning_accepted(self):
        f = make_finding(confidence="INFERRED", evidence=[
            {"kind": "static-reasoning", "location": "a.ts:1", "proves": "looks unguarded"}
        ])
        assert "UNSUPPORTED_CONFIRMED" not in error_codes(make_document([f]))

    def test_ok_status_cannot_carry_defect_severity(self):
        """`severity` is defined as the harm *of a defect*; `OK` asserts no defect.

        The combination is therefore incoherent by definition, not merely
        discouraged. Two consequences follow, and either alone justifies the rule:
        `OK` waives the evidence requirement, so `OK` + CRITICAL would record a
        severe finding with no evidence; and a reader scanning severities would
        see a CRITICAL that the matrix simultaneously calls fine.

        Before relaxing this, note that a *fixed* defect is not `OK` with high
        severity either — it is simply absent from the report, or carried with its
        real status. Do not reintroduce the combination to express "was bad, now
        fine"; that is what a previous audit's record is for.
        """
        f = make_finding(status="OK", severity="CRITICAL", likelihood="CERTAIN",
                         priority="P0", confidence="PROBABLE", evidence=[])
        assert "OK_WITH_DEFECT_SEVERITY" in error_codes(make_document([f]))

    def test_ok_status_with_low_severity_accepted(self):
        """LOW is the only coherent severity for a finding asserting nothing broken."""
        f = make_finding(status="OK", severity="LOW", likelihood="RARE",
                         priority="P3", confidence="PROBABLE", evidence=[])
        assert schema.validate_document(make_document([f])) == []

    def test_ok_status_rejects_medium_severity(self):
        """Guards the boundary: the rule is definitional, so MEDIUM is out too."""
        f = make_finding(status="OK", severity="MEDIUM", likelihood="RARE",
                         priority="P3", confidence="PROBABLE", evidence=[])
        assert "OK_WITH_DEFECT_SEVERITY" in error_codes(make_document([f]))

    def test_broken_without_line_number_rejected(self):
        f = make_finding(status="BROKEN", location="src/api/route.ts")
        assert "LOCATION_NEEDS_LINE" in error_codes(make_document([f]))

    def test_missing_status_allows_location_placeholder(self):
        """An absent capability has no line to point at."""
        f = make_finding(status="MISSING", location="-", confidence="INFERRED",
                         evidence=[{"kind": "static-reasoning", "location": "-",
                                    "proves": "no handler exists for this operation"}])
        assert "LOCATION_NEEDS_LINE" not in error_codes(make_document([f]))


class TestEnumValidation:
    @pytest.mark.parametrize("field,bad", [
        ("severity", "SEVERE"),
        ("likelihood", "SOMETIMES"),
        ("priority", "P9"),
        ("status", "FINE"),
        ("confidence", "SURE"),
        ("category", "misc"),
    ])
    def test_unknown_enum_value_rejected(self, field, bad):
        codes = error_codes(make_document([make_finding(**{field: bad})]))
        assert f"INVALID_{field.upper()}" in codes

    def test_priority_inconsistent_with_severity_rejected(self):
        """CRITICAL + CERTAIN is P0; P3 must not pass silently."""
        f = make_finding(severity="CRITICAL", likelihood="CERTAIN", priority="P3")
        assert "PRIORITY_MISMATCH" in error_codes(make_document([f]))

    def test_priority_override_requires_reason(self):
        f = make_finding(severity="CRITICAL", likelihood="CERTAIN", priority="P2",
                         priority_override_reason="accepted for the 2026-08 release")
        assert "PRIORITY_MISMATCH" not in error_codes(make_document([f]))

    def test_severity_is_not_rewritten_by_override(self):
        """Deprioritizing must not launder severity."""
        f = make_finding(severity="CRITICAL", likelihood="CERTAIN", priority="P2",
                         priority_override_reason="deferred")
        doc = make_document([f])
        assert schema.validate_document(doc) == []
        assert doc["findings"][0]["severity"] == "CRITICAL"


class TestCannotVerify:
    def test_cannot_verify_without_resolution_rejected(self):
        f = make_finding(status="CANNOT VERIFY", confidence="INFERRED",
                         evidence=[{"kind": "static-reasoning", "location": "a.ts:1",
                                    "proves": "handler not traceable statically"}])
        assert "CANNOT_VERIFY_NEEDS_RESOLUTION" in error_codes(make_document([f]))

    def test_cannot_verify_with_resolution_accepted(self):
        f = make_finding(
            status="CANNOT VERIFY", confidence="INFERRED", location="src/api/route.ts",
            evidence=[{"kind": "static-reasoning", "location": "src/api/route.ts:1",
                       "proves": "authorization is delegated to runtime middleware"}],
            blocked_by="no runtime environment",
            resolves_when="run the app and issue an unauthenticated DELETE",
        )
        assert schema.validate_document(make_document([f])) == []


class TestReferences:
    def test_dangling_depends_on_rejected(self):
        f = make_finding(depends_on=["ISSUE-999"])
        assert "DANGLING_DEPENDENCY" in error_codes(make_document([f]))

    def test_resolvable_depends_on_accepted(self):
        a = make_finding(id="ISSUE-001", fingerprint="aaaaaaaaaaaa", location="src/a.ts:1")
        b = make_finding(id="ISSUE-002", fingerprint="bbbbbbbbbbbb", location="src/b.ts:2",
                         depends_on=["ISSUE-001"])
        assert schema.validate_document(make_document([a, b])) == []


class TestCoverage:
    def test_reviewed_exceeding_discovered_rejected(self):
        doc = make_document(coverage={
            "static": {"mode": "PARTIAL", "discovered": 5, "excluded": 0, "reviewed": 7}
        })
        assert "COVERAGE_OVERCOUNT" in error_codes(doc)

    def test_full_with_incomplete_coverage_rejected(self):
        """9 of 10 reviewed is PARTIAL, however important the tenth is."""
        doc = make_document(
            coverage={"static": {"mode": "FULL", "discovered": 10, "excluded": 0, "reviewed": 9}},
            excluded=[],
        )
        assert "FULL_COVERAGE_INCOMPLETE" in error_codes(doc)

    def test_full_with_complete_coverage_accepted(self):
        doc = make_document(
            coverage={"static": {"mode": "FULL", "discovered": 10, "excluded": 0, "reviewed": 10}},
            excluded=[],
        )
        assert schema.validate_document(doc) == []

    def test_excluded_count_must_match_excluded_list(self):
        """Exclusions are counted transparently, never silently dropped."""
        doc = make_document(
            coverage={"static": {"mode": "FULL", "discovered": 10, "excluded": 3, "reviewed": 7}},
            excluded=[{"item": "legacy/", "reason": "removal scheduled"}],
        )
        assert "EXCLUSION_COUNT_MISMATCH" in error_codes(doc)

    def test_sampled_requires_selection_method(self):
        doc = make_document(coverage={
            "static": {"mode": "SAMPLED", "discovered": 100, "excluded": 0, "reviewed": 10}
        }, excluded=[])
        assert "SAMPLING_METHOD_MISSING" in error_codes(doc)

    def test_sampled_with_method_accepted(self):
        doc = make_document(coverage={
            "static": {"mode": "SAMPLED", "discovered": 100, "excluded": 0, "reviewed": 10,
                       "selection_method": "10 highest-traffic routes"}
        }, excluded=[])
        assert schema.validate_document(doc) == []

    def test_runtime_and_static_coverage_are_independent(self):
        """Reading every route is not running any of them."""
        doc = make_document(coverage={
            "static": {"mode": "FULL", "discovered": 10, "excluded": 0, "reviewed": 10},
            "runtime": {"mode": "PARTIAL", "discovered": 10, "excluded": 0, "reviewed": 0},
        }, excluded=[])
        assert schema.validate_document(doc) == []
        assert schema.is_full_coverage(doc, "static") is True
        assert schema.is_full_coverage(doc, "runtime") is False


class TestSecurityInvariants:
    def test_security_p0_without_impact_rejected(self):
        f = make_finding(category="security", priority="P0", impact="")
        assert "SECURITY_IMPACT_REQUIRED" in error_codes(make_document([f]))

    def test_security_p0_with_impact_accepted(self):
        f = make_finding(category="security", priority="P0",
                         impact="unauthenticated caller can delete any account")
        assert "SECURITY_IMPACT_REQUIRED" not in error_codes(make_document([f]))


# --------------------------------------------------------------------------
# round-trip
# --------------------------------------------------------------------------

class TestRoundTrip:
    def test_document_survives_serialize_parse(self):
        doc = make_document()
        assert schema.parse_document(schema.serialize_document(doc)) == doc

    def test_meaning_preserved_for_every_required_field(self):
        doc = make_document()
        restored = schema.parse_document(schema.serialize_document(doc))
        original, back = doc["findings"][0], restored["findings"][0]
        for field in ("id", "fingerprint", "status", "category", "severity",
                      "priority", "location", "evidence", "confidence", "likelihood"):
            assert back[field] == original[field], f"{field} changed across round-trip"

    def test_dependencies_survive_round_trip(self):
        a = make_finding(id="ISSUE-001", fingerprint="aaaaaaaaaaaa", location="src/a.ts:1")
        b = make_finding(id="ISSUE-002", fingerprint="bbbbbbbbbbbb", location="src/b.ts:2",
                         depends_on=["ISSUE-001"])
        restored = schema.parse_document(schema.serialize_document(make_document([a, b])))
        assert restored["findings"][1]["depends_on"] == ["ISSUE-001"]

    def test_cannot_verify_survives_round_trip(self):
        f = make_finding(
            status="CANNOT VERIFY", confidence="INFERRED", location="src/api/route.ts",
            evidence=[{"kind": "static-reasoning", "location": "src/api/route.ts:1",
                       "proves": "not statically traceable"}],
            blocked_by="no runtime environment",
            resolves_when="run the app and issue an unauthenticated DELETE",
        )
        back = schema.parse_document(schema.serialize_document(make_document([f])))["findings"][0]
        assert back["status"] == "CANNOT VERIFY"
        assert back["resolves_when"]

    def test_supersedes_survives_round_trip(self):
        """Cross-audit continuity must not be lost in serialization."""
        f = make_finding(fingerprint="b" * 12, supersedes="a" * 12)
        back = schema.parse_document(schema.serialize_document(make_document([f])))
        assert back["findings"][0]["supersedes"] == "a" * 12

    def test_unknown_fields_survive_round_trip(self):
        doc = make_document([make_finding(custom="keep me")])
        back = schema.parse_document(schema.serialize_document(doc))
        assert back["findings"][0]["custom"] == "keep me"

    def test_round_trip_is_idempotent(self):
        doc = make_document()
        once = schema.parse_document(schema.serialize_document(doc))
        twice = schema.parse_document(schema.serialize_document(once))
        assert once == twice

    def test_serialized_form_is_valid_json(self):
        json.loads(schema.serialize_document(make_document()))


# --------------------------------------------------------------------------
# legacy conversion
# --------------------------------------------------------------------------

class TestLegacyConversion:
    def test_f01_converts_to_issue_001(self):
        assert schema.legacy_id_to_canonical("F-01") == "ISSUE-001"

    def test_f_ids_convert_positionally(self):
        assert schema.legacy_id_to_canonical("F-12") == "ISSUE-012"

    def test_canonical_id_passes_through_unchanged(self):
        assert schema.legacy_id_to_canonical("ISSUE-007") == "ISSUE-007"

    def test_conversion_is_deterministic(self):
        assert schema.legacy_id_to_canonical("F-03") == schema.legacy_id_to_canonical("F-03")


# --------------------------------------------------------------------------
# FIX_PLAN compatibility
# --------------------------------------------------------------------------

class TestFixPlanCompatibility:
    def test_projection_produces_parser_contract_fields(self):
        issues = schema.to_fix_plan_issues(make_document())
        assert issues
        for issue in issues:
            assert set(issue) >= {"id", "severity", "title", "file", "problem", "fix", "status"}

    def test_projected_ids_are_unchanged(self):
        assert schema.to_fix_plan_issues(make_document())[0]["id"] == "ISSUE-001"

    def test_workflow_status_is_open_not_audit_status(self):
        """FIX_PLAN status is workflow state; BROKEN is an audit finding."""
        assert schema.to_fix_plan_issues(make_document())[0]["status"] == "open"

    def test_severity_values_match_fix_plan_vocabulary(self):
        for issue in schema.to_fix_plan_issues(make_document()):
            assert issue["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    def test_ok_findings_are_not_actionable(self):
        ok = make_finding(id="ISSUE-002", fingerprint="cccccccccccc",
                          status="OK", evidence=[])
        ids = [i["id"] for i in schema.to_fix_plan_issues(make_document([make_finding(), ok]))]
        assert "ISSUE-002" not in ids

    def test_cannot_verify_findings_are_not_actionable(self):
        """quality-loop must never be told to fix an unverified item."""
        cv = make_finding(
            id="ISSUE-002", fingerprint="dddddddddddd", status="CANNOT VERIFY",
            confidence="INFERRED", location="src/b.ts",
            evidence=[{"kind": "static-reasoning", "location": "src/b.ts:1",
                       "proves": "not traceable"}],
            blocked_by="no runtime", resolves_when="run the app",
        )
        ids = [i["id"] for i in schema.to_fix_plan_issues(make_document([make_finding(), cv]))]
        assert "ISSUE-002" not in ids

    def test_generated_fix_plan_md_parses_with_existing_parser(self, tmp_path):
        """End-to-end: AUDIT.json -> FIX_PLAN.md -> existing quality-loop parser."""
        import scripts.fix_plan_parser as fix_plan_parser

        md_path = tmp_path / "FIX_PLAN.md"
        md_path.write_text(schema.to_fix_plan_md(make_document()), encoding="utf-8")

        issues = fix_plan_parser.parse_fix_plan_md(str(md_path))
        assert len(issues) == 1
        assert issues[0]["id"] == "ISSUE-001"
        assert issues[0]["severity"] == "CRITICAL"
        assert issues[0]["status"] == "open"
        assert issues[0]["file"] == "src/api/users/route.ts:42"

    def test_severity_ordering_is_preserved_for_quality_loop(self):
        """quality-loop processes CRITICAL -> HIGH -> MEDIUM -> LOW."""
        high = make_finding(id="ISSUE-002", fingerprint="eeeeeeeeeeee",
                            severity="HIGH", likelihood="LIKELY", priority="P1",
                            location="src/b.ts:2")
        crit = make_finding(id="ISSUE-001", fingerprint="ffffffffffff",
                            severity="CRITICAL", location="src/a.ts:1")
        issues = schema.to_fix_plan_issues(make_document([high, crit]))
        assert [i["severity"] for i in issues] == ["CRITICAL", "HIGH"]


# --------------------------------------------------------------------------
# regression fixtures
# --------------------------------------------------------------------------

class TestFixtures:
    def test_canonical_fixture_is_valid(self):
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        assert schema.validate_document(doc) == []

    def test_canonical_fixture_round_trips(self):
        raw = open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        doc = schema.parse_document(raw)
        assert schema.parse_document(schema.serialize_document(doc)) == doc

    def test_fixture_covers_the_scenarios_the_skill_claims_to_detect(self):
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        rules = {f["title"].lower() for f in doc["findings"]}
        blob = " ".join(rules)
        for scenario in ("idor", "dead", "tenant", "duplicate"):
            assert scenario in blob, f"fixture lost coverage of {scenario}"

    def test_fixture_contains_a_cannot_verify_finding(self):
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        cv = [f for f in doc["findings"] if f["status"] == "CANNOT VERIFY"]
        assert cv and all(f.get("resolves_when") for f in cv)

    def test_fixture_inventory_backs_the_coverage_denominator(self):
        """The denominator is derived from enumerated items, not asserted."""
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        items = doc["inventory"]["static"]["items"]
        assert doc["coverage"]["static"]["discovered"] == len(items)
        assert doc["inventory"]["static"]["method"]

    def test_fixture_accounts_for_every_discovered_item(self):
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        for mode in ("static", "runtime"):
            assert schema.review_summary(doc, mode)["unaccounted"] == []

    def test_fixture_stays_within_its_authorized_scope(self):
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        assert doc["authorized_scope"]
        assert "OUT_OF_AUTHORIZED_SCOPE" not in {
            e.code for e in schema.validate_document(doc)
        }

    def test_fixture_declares_partial_coverage_honestly(self):
        doc = schema.parse_document(
            open("tests/fixtures/sample_AUDIT.json", encoding="utf-8").read()
        )
        assert doc["coverage"]["runtime"]["mode"] != "FULL"


# --------------------------------------------------------------------------
# mutation sensitivity — each mutation must be caught by validation
# --------------------------------------------------------------------------

class TestMutationDetection:
    """If a deliberate defect were introduced, some check must fail."""

    @pytest.mark.parametrize("mutate,expected", [
        (lambda d: d["findings"][0].update(id="F-01"), "LEGACY_ID_FORMAT"),
        (lambda d: d["findings"][0].pop("fingerprint"), "MISSING_FINGERPRINT"),
        (lambda d: d["findings"][0].update(evidence=[]), "MISSING_EVIDENCE"),
        (lambda d: d["findings"][0].update(severity="BAD"), "INVALID_SEVERITY"),
        (lambda d: d["findings"][0].update(priority="P3"), "PRIORITY_MISMATCH"),
        (lambda d: d["findings"][0].update(depends_on=["ISSUE-404"]), "DANGLING_DEPENDENCY"),
    ])
    def test_mutation_is_detected(self, mutate, expected):
        doc = make_document()
        mutate(doc)
        assert expected in error_codes(doc)

    def test_full_coverage_mutation_is_detected(self):
        doc = make_document(
            coverage={"static": {"mode": "FULL", "discovered": 10, "excluded": 0, "reviewed": 10}},
            excluded=[],
        )
        assert schema.validate_document(doc) == []
        doc["coverage"]["static"]["reviewed"] = 9
        assert "FULL_COVERAGE_INCOMPLETE" in error_codes(doc)

    def test_broken_json_field_is_detected(self):
        doc = make_document()
        doc["findings"] = "not a list"
        assert error_codes(doc)

    def test_validation_does_not_mutate_input(self):
        doc = make_document()
        before = copy.deepcopy(doc)
        schema.validate_document(doc)
        assert doc == before

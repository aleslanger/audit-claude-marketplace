"""Rules tightened in schema 1.1, and the crashes that preceded them.

Every test here corresponds to a document that validated clean before, verified
by running it. They are grouped by what an auditor could have claimed with the
looser reading, because that — not the rule number — is what a later reviewer
needs to know before deciding the rule is arbitrary.

`schema.SCHEMA_VERSION` is 1.1, so `make_doc` opts into the tightened rules;
`TestOnePointZeroStaysValid` pins the other side of that gate.
"""

import copy

import pytest

import scripts.audit_schema as schema
import scripts.fix_plan_parser as fix_plan_parser


def make_evidence(**overrides):
    record = {
        "kind": "code-read",
        "location": "src/api/users/route.ts:42",
        "proves": "handler deletes without reading the session",
        "quote": "export async function DELETE(req) { await db.user.delete(...) }",
    }
    record.update(overrides)
    return record


def make_finding(**overrides):
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
        "impact": "any authenticated user can delete any account",
        "evidence": [make_evidence()],
    }
    finding.update(overrides)
    return finding


def make_doc(findings=None, version=None, **extra):
    doc = {
        "schema_version": version or schema.SCHEMA_VERSION,
        "scope": "admin area",
        "findings": [make_finding()] if findings is None else findings,
    }
    doc.update(extra)
    return doc


def error_codes(doc):
    return {e.code for e in schema.validate_document(doc)}


# ---------------------------------------------------------------------------
# malformed input is reported, never raised
# ---------------------------------------------------------------------------

class TestMalformedInputDoesNotCrash:
    """A traceback is never the correct answer to a bad document.

    Each of these raised TypeError before, which aborted validation entirely —
    so one malformed field hid every other error in the document.
    """

    @pytest.mark.parametrize("field,value,expected", [
        ("depends_on", 5, "INVALID_DEPENDS_ON"),
        ("depends_on", "ISSUE-001", "INVALID_DEPENDS_ON"),
        ("confidence", [], "INVALID_CONFIDENCE"),
        ("category", {}, "INVALID_CATEGORY"),
        ("severity", [], "INVALID_SEVERITY"),
    ])
    def test_unhashable_or_wrong_typed_field_is_reported(self, field, value, expected):
        doc = make_doc([make_finding(**{field: value})])
        assert expected in error_codes(doc)

    def test_unhashable_evidence_kind_is_reported(self):
        doc = make_doc([make_finding(evidence=[make_evidence(kind={})])])
        assert "INVALID_EVIDENCE_KIND" in error_codes(doc)

    def test_unhashable_inventory_item_is_reported(self):
        doc = make_doc(
            findings=[],
            inventory={"static": {"items": [["nested"]], "method": "glob"}},
            coverage={"static": {"mode": "PARTIAL", "discovered": 1,
                                 "excluded": 0, "reviewed": 0, "reviewed_items": []}},
        )
        assert "INVALID_INVENTORY_ITEM" in error_codes(doc)

    def test_depends_on_string_is_not_walked_character_by_character(self):
        """Iterating a string reported a dangling dependency on 'I'."""
        doc = make_doc([make_finding(depends_on="ISSUE-001")])
        assert "DANGLING_DEPENDENCY" not in error_codes(doc)


# ---------------------------------------------------------------------------
# "non-empty" means content
# ---------------------------------------------------------------------------

class TestWhitespaceIsNotContent:
    """`"  "` and `True` are truthy, so both satisfied every "non-empty" rule.

    `priority_override_reason=True` was the sharpest case: a single token
    silenced the priority matrix without stating any reason at all.
    """

    def test_whitespace_cannot_verify_reason_is_rejected(self):
        doc = make_doc([make_finding(
            status="CANNOT VERIFY", location="-", severity="LOW",
            likelihood="RARE", priority="P3",
            blocked_by="   ", resolves_when="  ")])
        assert "CANNOT_VERIFY_NEEDS_RESOLUTION" in error_codes(doc)

    def test_true_as_priority_override_reason_does_not_silence_the_matrix(self):
        doc = make_doc([make_finding(priority="P3", priority_override_reason=True)])
        assert "PRIORITY_MISMATCH" in error_codes(doc)

    def test_whitespace_priority_override_reason_does_not_silence_the_matrix(self):
        doc = make_doc([make_finding(priority="P3", priority_override_reason="  ")])
        assert "PRIORITY_MISMATCH" in error_codes(doc)

    def test_whitespace_impact_does_not_satisfy_a_security_p0(self):
        doc = make_doc([make_finding(impact="   ")])
        assert "SECURITY_IMPACT_REQUIRED" in error_codes(doc)

    def test_whitespace_proves_is_rejected(self):
        doc = make_doc([make_finding(evidence=[make_evidence(proves="   ")])])
        assert "EVIDENCE_MISSING_PROVES" in error_codes(doc)

    def test_whitespace_title_is_rejected(self):
        doc = make_doc([make_finding(title="   ")])
        assert "EMPTY_TITLE" in error_codes(doc)

    def test_whitespace_selection_method_does_not_satisfy_sampled(self):
        doc = make_doc(
            findings=[],
            coverage={"static": {"mode": "SAMPLED", "discovered": 4, "excluded": 0,
                                 "reviewed": 2, "reviewed_items": ["/a", "/b"],
                                 "selection_method": "   "}},
        )
        assert "SAMPLING_METHOD_MISSING" in error_codes(doc)


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

class TestFingerprintShape:
    """The spec always said 12 hex characters; only truthiness was checked.

    `True` was the worst accepted value: `True == 1`, so it aliased with any
    integer fingerprint in the collision map and merged two distinct defects.
    """

    @pytest.mark.parametrize("value", [True, 1, "ZZZZZZZZZZZZ", "ab", "a" * 40, " " * 12])
    def test_non_hex_fingerprint_is_rejected(self, value):
        doc = make_doc([make_finding(fingerprint=value)])
        assert "INVALID_FINGERPRINT" in error_codes(doc)

    def test_a_computed_fingerprint_is_accepted(self):
        computed = schema.compute_fingerprint(
            "security", "src/api/users/route.ts:42", "missing-server-authz")
        assert schema.validate_document(make_doc([make_finding(fingerprint=computed)])) == []

    def test_rule_distinguishes_two_defects_in_one_file(self):
        """Identity is (category, location, rule); dropping `rule` merged these.

        Both findings sit in one file with one category, so without `rule` the
        collision check saw a single identity and accepted a shared fingerprint.
        """
        shared = "ffffffffffff"
        first = make_finding(id="ISSUE-001", fingerprint=shared,
                             rule="missing-server-authz")
        second = make_finding(id="ISSUE-002", fingerprint=shared,
                              rule="idor-object-access")
        assert "FINGERPRINT_COLLISION" in error_codes(make_doc([first, second]))


# ---------------------------------------------------------------------------
# location and the audit's own boundary
# ---------------------------------------------------------------------------

class TestLocationShape:
    def test_bare_line_number_is_not_a_location(self):
        """`LINE_SUFFIX_RE` was unanchored, so ":42" satisfied it.

        It also normalized to "", which then prefix-matched every
        authorized_scope entry — a finding with no path at all was in scope.
        """
        doc = make_doc([make_finding(location=":42")])
        assert "LOCATION_NEEDS_LINE" in error_codes(doc)


class TestAuthorizedScopeIsABoundary:
    """Citing a file proves it was read, so this is a confidentiality control.

    It is also the one control nobody else audits, which is why a malformed
    boundary must fail loudly rather than disable itself.
    """

    def test_sibling_directory_sharing_a_prefix_is_out_of_scope(self):
        finding = make_finding(
            location="apps/admin-secrets/db.ts:1",
            evidence=[make_evidence(location="apps/admin-secrets/db.ts:1")])
        doc = make_doc([finding], authorized_scope=["apps/admin"])
        assert "OUT_OF_AUTHORIZED_SCOPE" in error_codes(doc)

    def test_traversal_cannot_escape_the_scope(self):
        finding = make_finding(
            location="apps/admin/../../etc/passwd:1",
            evidence=[make_evidence(location="apps/admin/../../etc/passwd:1")])
        doc = make_doc([finding], authorized_scope=["apps/admin/"])
        assert "OUT_OF_AUTHORIZED_SCOPE" in error_codes(doc)

    def test_a_string_scope_does_not_silently_disable_the_check(self):
        """A bare string is not a list, so both scope rules returned early."""
        finding = make_finding(
            location="apps/other/db.ts:1",
            evidence=[make_evidence(location="apps/other/db.ts:1")])
        doc = make_doc([finding], authorized_scope="apps/admin/")
        assert "INVALID_AUTHORIZED_SCOPE" in error_codes(doc)

    def test_nested_path_inside_the_scope_is_accepted(self):
        finding = make_finding(
            location="apps/admin/users/route.ts:9",
            evidence=[make_evidence(location="apps/admin/users/route.ts:9")])
        doc = make_doc([finding], authorized_scope=["apps/admin"])
        assert schema.validate_document(doc) == []


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------

class TestQuoteIsRequiredWhereItIsThePoint:
    """`quote` was the one field the schema never required.

    Reading code and asserting what it does is checkable only against the lines
    themselves, so the strongest claim in the model — CONFIRMED + code-read —
    could be made with no quoted line at all.
    """

    @pytest.mark.parametrize("kind", ["code-read", "test-run"])
    def test_content_asserting_kinds_require_a_quote(self, kind):
        finding = make_finding(
            confidence="CONFIRMED",
            evidence=[make_evidence(kind=kind, quote=None)])
        assert "EVIDENCE_MISSING_QUOTE" in error_codes(make_doc([finding]))

    @pytest.mark.parametrize("kind", ["caller-trace", "static-reasoning",
                                      "runtime-observation"])
    def test_kinds_with_nothing_to_quote_are_exempt(self, kind):
        """These establish reachability, shape, or observed behavior.

        None of them is an assertion about the text of a specific line, so
        demanding a quote would be a rule with no artifact behind it.
        """
        finding = make_finding(
            confidence="PROBABLE",
            evidence=[make_evidence(kind=kind, quote=None)])
        assert "EVIDENCE_MISSING_QUOTE" not in error_codes(make_doc([finding]))

    def test_whitespace_quote_is_not_a_quote(self):
        finding = make_finding(evidence=[make_evidence(quote="   ")])
        assert "EVIDENCE_MISSING_QUOTE" in error_codes(make_doc([finding]))


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------

def coverage_doc(block, items=("/admin/users", "/admin/orders"), **extra):
    doc = make_doc(
        findings=[],
        inventory={"static": {"items": list(items), "method": "glob app/**/page.tsx"}},
        coverage={"static": block},
    )
    doc.update(extra)
    return doc


class TestCoverageCannotBeClaimedWithoutNames:
    def test_omitting_reviewed_items_is_rejected(self):
        """Omitting the names skipped every name-level rule at once.

        The early return disabled the by-name FULL check, the unaccounted-item
        check, and the contradictory-state check — leaving exactly the count
        that rule 23 says is not enough.
        """
        doc = coverage_doc({"mode": "FULL", "discovered": 2, "excluded": 0, "reviewed": 2})
        assert "REVIEWED_ITEMS_MISSING" in error_codes(doc)

    def test_full_by_count_alone_does_not_hide_unreviewed_items(self):
        doc = coverage_doc({"mode": "FULL", "discovered": 2, "excluded": 0, "reviewed": 2})
        codes = error_codes(doc)
        assert "FULL_COVERAGE_INCOMPLETE" in codes
        assert "ITEM_UNACCOUNTED" in codes

    def test_duplicate_reviewed_items_do_not_inflate_the_numerator(self):
        """Repeating one name satisfied `reviewed == len(reviewed_items)`."""
        doc = coverage_doc({"mode": "PARTIAL", "discovered": 2, "excluded": 0,
                            "reviewed": 2,
                            "reviewed_items": ["/admin/users", "/admin/users"],
                            "not_reviewed": ["/admin/orders"]})
        assert "REVIEWED_ITEMS_DUPLICATE" in error_codes(doc)

    def test_not_reviewed_must_name_real_inventory_items(self):
        doc = coverage_doc({"mode": "PARTIAL", "discovered": 2, "excluded": 0,
                            "reviewed": 1, "reviewed_items": ["/admin/users"],
                            "not_reviewed": ["/admin/ghost"]})
        assert "NOT_REVIEWED_NOT_IN_INVENTORY" in error_codes(doc)

    def test_not_reviewed_as_a_string_is_rejected(self):
        """`set("/b")` becomes {'/', 'b'} — accounting for nothing, silently."""
        doc = coverage_doc({"mode": "PARTIAL", "discovered": 2, "excluded": 0,
                            "reviewed": 1, "reviewed_items": ["/admin/users"],
                            "not_reviewed": "/admin/orders"})
        assert "INVALID_NOT_REVIEWED" in error_codes(doc)


class TestFullNeedsSomethingToBeFullOf:
    def test_full_over_an_empty_denominator_is_rejected(self):
        """`0 == 0 - 0` is true and says nothing.

        Excluding every discovered item, then claiming FULL, was arithmetically
        valid and substantively empty — a clean bill of health for an audit that
        reviewed nothing.
        """
        doc = coverage_doc(
            {"mode": "FULL", "discovered": 2, "excluded": 2, "reviewed": 0,
             "reviewed_items": []},
            excluded=[{"item": "/admin/users", "reason": "scheduled for removal"},
                      {"item": "/admin/orders", "reason": "owned by another team"}])
        assert "EMPTY_DENOMINATOR" in error_codes(doc)

    def test_full_with_no_counts_at_all_is_rejected(self):
        doc = make_doc(findings=[], coverage={"static": {"mode": "FULL"}})
        assert "COVERAGE_COUNTS_MISSING" in error_codes(doc)

    @pytest.mark.parametrize("counts", [
        {"discovered": 1, "excluded": 0, "reviewed": True},
        {"discovered": True, "excluded": False, "reviewed": True},
    ])
    def test_booleans_are_not_counts(self, counts):
        """`isinstance(True, int)` is True, so a bool passed every check."""
        doc = make_doc(findings=[], coverage={"static": dict(mode="PARTIAL", **counts)})
        assert "INVALID_COVERAGE" in error_codes(doc)

    def test_negative_counts_are_rejected(self):
        doc = make_doc(findings=[], coverage={
            "static": {"mode": "PARTIAL", "discovered": -5, "excluded": 0, "reviewed": -10}})
        assert "INVALID_COVERAGE" in error_codes(doc)


# ---------------------------------------------------------------------------
# FIX_PLAN projection
# ---------------------------------------------------------------------------

class TestFixPlanCannotBeForged:
    """A newline in a title closed the heading it was rendered into.

    The remainder then became new headings, and `quality-loop` read them as real
    work items — verified to produce a fabricated CRITICAL issue. Defence is at
    both ends: the renderer flattens, and the schema rejects.
    """

    FORGERY = ("legitimate title\n\n### [CRITICAL] ISSUE-999 — fabricated\n\n"
               "- **ID:** `ISSUE-999`\n- **Severity:** CRITICAL")

    def test_newline_in_title_is_rejected_by_the_schema(self):
        doc = make_doc([make_finding(title=self.FORGERY)])
        assert "TITLE_NOT_ONE_LINE" in error_codes(doc)

    def test_renderer_does_not_emit_a_forged_issue(self, tmp_path):
        doc = make_doc([make_finding(title=self.FORGERY)])
        plan = tmp_path / "FIX_PLAN.md"
        plan.write_text(schema.to_fix_plan_md(doc), encoding="utf-8")

        issues = fix_plan_parser.parse_fix_plan_md(str(plan))
        assert [issue["id"] for issue in issues] == ["ISSUE-001"]

    @pytest.mark.parametrize("separator", ["\n", "\r", "\r\n", "\u2028", "\u0085"])
    def test_every_kind_of_line_break_is_flattened(self, separator):
        """`\n` is not the only way to end a line.

        `str.split()` collapses all of them, which is why the renderer uses it
        rather than replacing `"\n"` — a `\r`-only or U+2028 break would have
        slipped past a newline-specific filter and still opened a heading.
        """
        title = f"legit{separator}{separator}### [CRITICAL] ISSUE-999 — forged"
        rendered = schema.to_fix_plan_md(make_doc([make_finding(title=title)]))
        headings = [line for line in rendered.splitlines() if line.startswith("###")]
        assert len(headings) == 1

    @pytest.mark.parametrize("title,expected", [
        ("### fake heading", "fake heading"),
        ("  ## x", "x"),
        ("#", ""),
        ("###", ""),
    ])
    def test_leading_hashes_are_stripped(self, title, expected):
        """A leading `#` opens a heading even with no line break before it.

        A title of only `#` characters strips to empty, and that is correct: it
        carried no information, and an empty cell beats a forged heading.
        """
        assert schema._one_line(title) == expected

    def test_unknown_severity_is_rendered_rather_than_dropped(self):
        """It was counted in the header and rendered in no group — data loss."""
        finding = make_finding(severity="WEIRD")
        rendered = schema.to_fix_plan_md(make_doc([finding]))
        assert "ISSUE-001" in rendered


# ---------------------------------------------------------------------------
# immutability
# ---------------------------------------------------------------------------

class TestDecayConfidenceDoesNotTouchItsInput:
    """A shallow `dict()` shared the nested `evidence` list with the caller.

    The docstring promised the opposite, and the existing test only compared the
    top-level `confidence` key, so the sharing was invisible.
    """

    def make_finding_with_commit(self, commit="abc123"):
        return {
            "confidence": "CONFIRMED",
            "impact": "unchanged",
            "evidence": [{"kind": "code-read", "location": "src/api/route.ts:42",
                          "proves": "deletes without checking role",
                          "quote": "db.user.delete()", "commit": commit}],
        }

    def test_mutating_the_result_does_not_mutate_the_input(self):
        finding = self.make_finding_with_commit()
        before = copy.deepcopy(finding)

        decayed = schema.decay_confidence(finding, {"src/api/route.ts": "def456"})
        decayed["evidence"].append({"injected": True})
        decayed["evidence"][0]["proves"] = "rewritten"

        assert finding == before

    def test_every_stale_record_is_named_not_only_the_first(self):
        finding = self.make_finding_with_commit()
        finding["evidence"].append(
            {"kind": "code-read", "location": "src/api/other.ts:7",
             "proves": "second stale citation", "quote": "x", "commit": "old2"})

        decayed = schema.decay_confidence(
            finding, {"src/api/route.ts": "new1", "src/api/other.ts": "new2"})

        assert "src/api/route.ts" in decayed["confidence_note"]
        assert "src/api/other.ts" in decayed["confidence_note"]

    def test_no_git_context_is_not_an_error(self):
        """An audit run without git must behave exactly as before."""
        finding = self.make_finding_with_commit()
        assert schema.decay_confidence(finding, None)["confidence"] == "CONFIRMED"
        assert schema.decay_confidence(finding, {})["confidence"] == "CONFIRMED"


# ---------------------------------------------------------------------------
# the version gate itself
# ---------------------------------------------------------------------------

class TestOnePointZeroStaysValid:
    """The gate is the reason a stricter rule could ship at all.

    A 1.0 document is an audit someone already delivered; retroactively
    invalidating it would make the report unreproducible rather than better.
    """

    def test_evidence_without_a_quote_still_validates(self):
        finding = make_finding(evidence=[make_evidence(quote=None)])
        assert schema.validate_document(make_doc([finding], version="1.0")) == []

    def test_coverage_without_reviewed_items_is_not_flagged_as_missing(self):
        doc = coverage_doc({"mode": "PARTIAL", "discovered": 2, "excluded": 0,
                            "reviewed": 0})
        doc["schema_version"] = "1.0"
        assert "REVIEWED_ITEMS_MISSING" not in error_codes(doc)

    @pytest.mark.parametrize("version,tightened", [
        ("1.0", False), ("1.1", True), ("1.2", True),
        ("1.9", True), ("1.10", True), ("2.0", True), ("10.0", True),
        ("0.9", False), ("", False), (None, False), ("abc", False),
    ])
    def test_the_gate_compares_versions_numerically(self, version, tightened):
        """`"1.10" >= "1.9"` is False as text.

        Compared as strings, a future 1.10 would silently drop to the permissive
        1.0 reading — a gate that fails toward accepting less is worse than no
        gate, because nothing announces it.
        """
        assert schema.is_tightened({"schema_version": version}) is tightened

    def test_a_crash_fix_applies_to_every_version(self):
        """Version-gating tightened rules, not correctness.

        A traceback is wrong under 1.0 too, so the type guards are unconditional.
        """
        doc = make_doc([make_finding(depends_on=5)], version="1.0")
        assert "INVALID_DEPENDS_ON" in error_codes(doc)

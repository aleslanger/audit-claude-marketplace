#!/usr/bin/env python3
"""Canonical audit finding model — validation, round-trip, FIX_PLAN projection.

Reference implementation of `skills/app-audit-plan/references/audit-schema.md`.
Both AUDIT.md and AUDIT.json are produced from the objects handled here, so the
two outputs cannot drift apart.

Validation returns a list of errors rather than raising, so a caller can report
every problem in one pass instead of one per run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "1.0"

CATEGORIES = frozenset({
    "security", "bug", "missing-feature", "architecture",
    "ux", "data-integrity", "performance", "consistency",
})
SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
LIKELIHOODS = frozenset({"CERTAIN", "LIKELY", "OCCASIONAL", "RARE"})
PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
STATUSES = frozenset({"OK", "PARTIAL", "BROKEN", "MISSING", "CANNOT VERIFY"})
CONFIDENCES = frozenset({"CONFIRMED", "PROBABLE", "INFERRED"})
EVIDENCE_KINDS = frozenset({
    "code-read", "test-run", "caller-trace", "static-reasoning", "runtime-observation",
})
COVERAGE_MODES = frozenset({"FULL", "PARTIAL", "SAMPLED"})

# Only these establish behavior; static reasoning describes code shape.
CONFIRMING_EVIDENCE_KINDS = frozenset({"code-read", "test-run", "runtime-observation"})

# Findings requiring a line number — an absent capability has no line to cite.
LOCATION_LINE_REQUIRED = frozenset({"PARTIAL", "BROKEN"})

# Not actionable by quality-loop: nothing is broken, or nothing was established.
NON_ACTIONABLE_STATUSES = frozenset({"OK", "CANNOT VERIFY"})

# Severities that assert a real defect, and so are incompatible with `OK`.
DEFECT_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM"})

REQUIRED_FIELDS = (
    "id", "fingerprint", "title", "category", "severity",
    "likelihood", "priority", "status", "confidence", "location", "evidence",
)

CANONICAL_ID_RE = re.compile(r"^ISSUE-\d{3,}$")
LEGACY_ID_RE = re.compile(r"^F-(\d+)$", re.IGNORECASE)
LINE_SUFFIX_RE = re.compile(r":\d+$")

PRIORITY_MATRIX = {
    ("CRITICAL", "CERTAIN"): "P0", ("CRITICAL", "LIKELY"): "P0",
    ("CRITICAL", "OCCASIONAL"): "P0", ("CRITICAL", "RARE"): "P1",
    ("HIGH", "CERTAIN"): "P0", ("HIGH", "LIKELY"): "P1",
    ("HIGH", "OCCASIONAL"): "P1", ("HIGH", "RARE"): "P2",
    ("MEDIUM", "CERTAIN"): "P1", ("MEDIUM", "LIKELY"): "P2",
    ("MEDIUM", "OCCASIONAL"): "P2", ("MEDIUM", "RARE"): "P3",
    ("LOW", "CERTAIN"): "P2", ("LOW", "LIKELY"): "P3",
    ("LOW", "OCCASIONAL"): "P3", ("LOW", "RARE"): "P3",
}

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass(frozen=True)
class ValidationError:
    """A single schema violation. `code` is stable; `message` is for humans."""

    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.code} — {self.message}"


# ---------------------------------------------------------------------------
# fingerprint
# ---------------------------------------------------------------------------

def normalize_location(location: str) -> str:
    """Strip the line number and leading `./` so edits above a defect don't
    re-identify it."""
    normalized = (location or "").strip()
    normalized = LINE_SUFFIX_RE.sub("", normalized)
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def compute_fingerprint(category: str, location: str, rule: str) -> str:
    """Stable identity of a problem across audits.

    Excludes the prose title and the line number — both change without the
    underlying defect changing. Two instances of one rule in a single file are
    separated by a `#discriminator` on `rule`.
    """
    payload = f"{category}|{normalize_location(location)}|{rule}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def is_known_finding(finding: Dict[str, Any], known_fingerprints: Iterable[str]) -> bool:
    """True when a previous audit already recorded this problem.

    Matches on fingerprint, or on `supersedes` when the file has moved since —
    a rename necessarily changes the fingerprint (see `finding-model.md`), so
    continuity across a move is stated explicitly rather than inferred.
    """
    known = set(known_fingerprints)
    if finding.get("fingerprint") in known:
        return True
    return finding.get("supersedes") in known if finding.get("supersedes") else False


def compare_audits(
    previous: Iterable[Dict[str, Any]],
    current: Iterable[Dict[str, Any]],
    reviewed_locations: Iterable[str],
    previously_fixed: Optional[Iterable[str]] = None,
) -> Dict[str, List[str]]:
    """Classify each finding across two audits.

    The distinction that matters: a finding absent from the current audit was
    either **fixed** (its location was re-reviewed and the problem is gone) or it
    merely **disappeared** (nobody looked). These are indistinguishable without
    knowing what was reviewed, and treating the second as the first is how an
    audit quietly starts overstating progress. `DISAPPEARED` therefore resolves to
    `CANNOT VERIFY` rather than to success.

    `reviewed_locations` holds normalized paths (no line numbers).
    """
    reviewed = {normalize_location(location) for location in reviewed_locations}
    already_fixed = set(previously_fixed or ())

    previous_list = [f for f in previous if isinstance(f, dict)]
    current_list = [f for f in current if isinstance(f, dict)]

    previous_by_fingerprint = {
        f.get("fingerprint"): f for f in previous_list if f.get("fingerprint")
    }

    # A rename changes the fingerprint, so `supersedes` maps a current finding
    # back onto the earlier identity it continues.
    current_identities: set = set()
    for finding in current_list:
        if finding.get("fingerprint"):
            current_identities.add(finding["fingerprint"])
        if finding.get("supersedes"):
            current_identities.add(finding["supersedes"])

    result: Dict[str, List[str]] = {
        "FIXED": [], "DISAPPEARED": [], "STILL_OPEN": [], "REGRESSED": [], "NEW": [],
        "cannot_verify": [],
    }

    for fingerprint, finding in previous_by_fingerprint.items():
        if fingerprint in current_identities:
            bucket = "REGRESSED" if fingerprint in already_fixed else "STILL_OPEN"
            result[bucket].append(fingerprint)
            continue
        if normalize_location(str(finding.get("location", ""))) in reviewed:
            result["FIXED"].append(fingerprint)
        else:
            result["DISAPPEARED"].append(fingerprint)
            result["cannot_verify"].append(fingerprint)

    for finding in current_list:
        fingerprint = finding.get("fingerprint")
        if not fingerprint:
            continue
        known = fingerprint in previous_by_fingerprint or (
            finding.get("supersedes") in previous_by_fingerprint
        )
        if not known:
            result["NEW"].append(fingerprint)

    return {key: sorted(value) for key, value in result.items()}


def decay_confidence(
    finding: Dict[str, Any], current_commits: Dict[str, str]
) -> Dict[str, Any]:
    """Lower `CONFIRMED` to `PROBABLE` when the cited code has changed since.

    Evidence is a statement about a specific revision. Once that file moves on,
    the finding is a historical note until someone re-checks it. Returns a new
    object; never mutates the input.

    Evidence without a recorded `commit` makes no freshness claim, so nothing is
    decayed — audits with no git context keep working unchanged.
    """
    if finding.get("confidence") != "CONFIRMED":
        return finding

    stale_records = []
    for record in finding.get("evidence") or []:
        if not isinstance(record, dict):
            continue
        recorded = record.get("commit")
        if not recorded:
            continue
        path = normalize_location(str(record.get("location", "")))
        current = current_commits.get(path)
        if current and current != recorded:
            stale_records.append((path, recorded, current))

    if not stale_records:
        return finding

    path, recorded, current = stale_records[0]
    decayed = dict(finding)
    decayed["confidence"] = "PROBABLE"
    decayed["needs_reverification"] = True
    decayed["confidence_note"] = (
        f"evidence recorded at {recorded} but {path} is now at {current}; "
        "re-verify before relying on this finding"
    )
    return decayed


def legacy_id_to_canonical(identifier: str) -> str:
    """Convert a legacy `F-NN` id to canonical `ISSUE-NNN`, positionally."""
    match = LEGACY_ID_RE.match((identifier or "").strip())
    if not match:
        return identifier
    return f"ISSUE-{int(match.group(1)):03d}"


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------

def serialize_document(document: Dict[str, Any]) -> str:
    """Serialize without reordering or dropping keys, so round-trip is lossless."""
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False)


def parse_document(raw: str) -> Dict[str, Any]:
    return json.loads(raw)


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def _validate_enums(finding: Dict[str, Any], path: str) -> List[ValidationError]:
    checks = (
        ("category", CATEGORIES, "INVALID_CATEGORY"),
        ("severity", SEVERITIES, "INVALID_SEVERITY"),
        ("likelihood", LIKELIHOODS, "INVALID_LIKELIHOOD"),
        ("priority", PRIORITIES, "INVALID_PRIORITY"),
        ("status", STATUSES, "INVALID_STATUS"),
        ("confidence", CONFIDENCES, "INVALID_CONFIDENCE"),
    )
    errors = []
    for field, allowed, code in checks:
        value = finding.get(field)
        if value is not None and value not in allowed:
            errors.append(ValidationError(
                code, path, f"{field} has unknown value {value!r}"))
    return errors


def _validate_evidence(finding: Dict[str, Any], path: str) -> List[ValidationError]:
    errors: List[ValidationError] = []
    status = finding.get("status")
    evidence = finding.get("evidence")

    if not isinstance(evidence, list):
        return [ValidationError("INVALID_EVIDENCE", path, "evidence must be a list")]

    # An OK finding asserts nothing broken, so it needs no evidence record.
    if status != "OK" and not evidence:
        errors.append(ValidationError(
            "MISSING_EVIDENCE", path,
            f"status {status!r} requires at least one evidence record"))

    for index, record in enumerate(evidence):
        record_path = f"{path}.evidence[{index}]"
        if not isinstance(record, dict):
            errors.append(ValidationError(
                "INVALID_EVIDENCE", record_path, "evidence record must be an object"))
            continue
        kind = record.get("kind")
        if kind not in EVIDENCE_KINDS:
            errors.append(ValidationError(
                "INVALID_EVIDENCE_KIND", record_path, f"unknown evidence kind {kind!r}"))
        if not record.get("location"):
            errors.append(ValidationError(
                "EVIDENCE_MISSING_LOCATION", record_path, "evidence needs a location"))
        if not record.get("proves"):
            errors.append(ValidationError(
                "EVIDENCE_MISSING_PROVES", record_path,
                "evidence must state what it proves"))

    # Documentation and code shape never establish behavior.
    if finding.get("confidence") == "CONFIRMED":
        kinds = {r.get("kind") for r in evidence if isinstance(r, dict)}
        if not (kinds & CONFIRMING_EVIDENCE_KINDS):
            errors.append(ValidationError(
                "UNSUPPORTED_CONFIRMED", path,
                "CONFIRMED requires code-read, test-run, or runtime-observation evidence"))

    return errors


def _validate_finding(finding: Dict[str, Any], path: str) -> List[ValidationError]:
    if not isinstance(finding, dict):
        return [ValidationError("INVALID_FINDING", path, "finding must be an object")]

    errors: List[ValidationError] = []

    identifier = finding.get("id")
    if not identifier:
        errors.append(ValidationError("MISSING_ID", path, "finding has no id"))
    elif LEGACY_ID_RE.match(str(identifier)):
        errors.append(ValidationError(
            "LEGACY_ID_FORMAT", path,
            f"{identifier!r} is the legacy format; emit ISSUE-NNN"))
    elif not CANONICAL_ID_RE.match(str(identifier)):
        errors.append(ValidationError(
            "INVALID_ID_FORMAT", path, f"{identifier!r} is not ISSUE-NNN"))

    fingerprint = finding.get("fingerprint")
    if not fingerprint:
        errors.append(ValidationError(
            "MISSING_FINGERPRINT", path, "finding has no fingerprint"))

    # `supersedes` carries identity across a rename, which the hash cannot do.
    # Superseding itself would assert the file both moved and did not.
    if finding.get("supersedes") and finding.get("supersedes") == fingerprint:
        errors.append(ValidationError(
            "SELF_SUPERSEDE", path,
            "supersedes must name a different (earlier) fingerprint"))

    for field in REQUIRED_FIELDS:
        if field in ("id", "fingerprint"):
            continue
        if finding.get(field) in (None, ""):
            errors.append(ValidationError(
                "MISSING_FIELD", path, f"required field {field!r} is missing"))

    errors.extend(_validate_enums(finding, path))
    errors.extend(_validate_evidence(finding, path))

    status = finding.get("status")

    # `OK` waives the evidence requirement because it asserts nothing broken.
    # A finding claiming real severity is therefore not `OK` — otherwise the
    # status becomes a way to record a defect while dodging NO OK WITHOUT EVIDENCE.
    if status == "OK" and finding.get("severity") in DEFECT_SEVERITIES:
        errors.append(ValidationError(
            "OK_WITH_DEFECT_SEVERITY", path,
            f"status OK cannot carry severity {finding.get('severity')}; "
            "use the real status, or lower the severity"))

    # A defect that exists in code can be pointed at precisely.
    if status in LOCATION_LINE_REQUIRED:
        if not LINE_SUFFIX_RE.search(str(finding.get("location", ""))):
            errors.append(ValidationError(
                "LOCATION_NEEDS_LINE", path,
                f"status {status} requires a file:line location"))

    # CANNOT VERIFY is permanent until someone does the named step.
    if status == "CANNOT VERIFY":
        if not finding.get("blocked_by") or not finding.get("resolves_when"):
            errors.append(ValidationError(
                "CANNOT_VERIFY_NEEDS_RESOLUTION", path,
                "CANNOT VERIFY requires blocked_by and resolves_when"))

    # Priority is derived; deviating from it is a decision that must be stated.
    severity, likelihood = finding.get("severity"), finding.get("likelihood")
    expected = PRIORITY_MATRIX.get((severity, likelihood))
    if expected and finding.get("priority") != expected:
        if not finding.get("priority_override_reason"):
            errors.append(ValidationError(
                "PRIORITY_MISMATCH", path,
                f"{severity}/{likelihood} implies {expected}, got "
                f"{finding.get('priority')!r}; set priority_override_reason to deviate"))

    # High-priority security claims need a demonstrated impact path.
    if finding.get("category") == "security" and finding.get("priority") in ("P0", "P1"):
        if not finding.get("impact"):
            errors.append(ValidationError(
                "SECURITY_IMPACT_REQUIRED", path,
                "security P0/P1 must state the impact path"))

    return errors


def _inventory_items(document: Dict[str, Any], mode_name: str) -> Optional[List[str]]:
    """Enumerated items for a coverage mode, or None when no inventory is given.

    A mode may declare `same_as` to reuse another mode's enumeration rather than
    duplicating it — static and runtime usually cover the same surface.
    """
    inventory = document.get("inventory") or {}
    block = inventory.get(mode_name)
    if not isinstance(block, dict):
        return None

    seen: set = set()
    while isinstance(block, dict) and block.get("same_as"):
        target = block["same_as"]
        if target in seen:  # cycle
            return None
        seen.add(target)
        block = inventory.get(target)

    if not isinstance(block, dict):
        return None
    items = block.get("items")
    return items if isinstance(items, list) else None


def _validate_inventory(document: Dict[str, Any]) -> List[ValidationError]:
    """The coverage denominator must be derived from enumerated items.

    Without this, `discovered` is a number the auditor asserts, and an audit that
    found forty routes can claim FULL coverage of ten.
    """
    errors: List[ValidationError] = []
    inventory = document.get("inventory")
    if inventory is None:
        return errors  # optional — documents predating the manifest still validate
    if not isinstance(inventory, dict):
        return [ValidationError("INVALID_INVENTORY", "inventory", "inventory must be an object")]

    # Once any mode is inventoried, a mode that declares coverage without one
    # would skip every cross-check while still asserting a denominator.
    for mode_name in (document.get("coverage") or {}):
        if _inventory_items(document, mode_name) is None:
            errors.append(ValidationError(
                "INVENTORY_MODE_MISSING", f"inventory.{mode_name}",
                f"coverage declares mode {mode_name!r} but no inventory enumerates it; "
                "add its items or point at another mode with same_as"))

    for mode_name, block in inventory.items():
        path = f"inventory.{mode_name}"
        if not isinstance(block, dict):
            errors.append(ValidationError("INVALID_INVENTORY", path, "must be an object"))
            continue

        if block.get("same_as"):
            if not isinstance(inventory.get(block["same_as"]), dict):
                errors.append(ValidationError(
                    "INVENTORY_BAD_REFERENCE", path,
                    f"same_as points at {block['same_as']!r}, which is not an inventory mode"))
            continue

        items = block.get("items")
        if not isinstance(items, list):
            errors.append(ValidationError(
                "INVENTORY_ITEMS_MISSING", path, "inventory needs an items list"))
            continue

        # A later audit must be able to reproduce the same enumeration.
        if not block.get("method"):
            errors.append(ValidationError(
                "INVENTORY_METHOD_MISSING", path,
                "inventory must state the method used to enumerate items"))

        duplicates = sorted({item for item in items if items.count(item) > 1})
        if duplicates:
            errors.append(ValidationError(
                "INVENTORY_DUPLICATE", path,
                f"inventory lists duplicate items: {', '.join(duplicates)}"))

    return errors


def _validate_coverage_against_inventory(
    document: Dict[str, Any], mode_name: str, block: Dict[str, Any]
) -> List[ValidationError]:
    """Cross-check a coverage block against the enumerated inventory.

    Enforces the three-state rule: every discovered item is reviewed, excluded, or
    explicitly not reviewed. There is no fourth state, because an unaccounted item
    silently reads as fine.
    """
    errors: List[ValidationError] = []
    items = _inventory_items(document, mode_name)
    if items is None:
        return errors

    path = f"coverage.{mode_name}"
    inventory_set = set(items)

    discovered = block.get("discovered")
    if isinstance(discovered, int) and discovered != len(items):
        errors.append(ValidationError(
            "DISCOVERED_MISMATCH", path,
            f"discovered {discovered} does not match {len(items)} enumerated items"))

    reviewed_items = block.get("reviewed_items")
    if not isinstance(reviewed_items, list):
        return errors

    reviewed_set = set(reviewed_items)
    unknown = sorted(reviewed_set - inventory_set)
    if unknown:
        errors.append(ValidationError(
            "REVIEWED_NOT_IN_INVENTORY", path,
            f"reviewed items absent from the inventory: {', '.join(unknown)}"))

    reviewed_count = block.get("reviewed")
    if isinstance(reviewed_count, int) and reviewed_count != len(reviewed_items):
        errors.append(ValidationError(
            "REVIEWED_COUNT_MISMATCH", path,
            f"reviewed {reviewed_count} does not match {len(reviewed_items)} reviewed items"))

    excluded_items = {
        entry.get("item") for entry in document.get("excluded") or []
        if isinstance(entry, dict)
    }
    unknown_excluded = sorted(item for item in excluded_items if item not in inventory_set)
    if unknown_excluded:
        errors.append(ValidationError(
            "EXCLUDED_NOT_IN_INVENTORY", f"excluded",
            f"excluded items absent from the inventory: {', '.join(unknown_excluded)}"))

    not_reviewed = set(block.get("not_reviewed") or [])

    contradictory = sorted((reviewed_set & not_reviewed) | (reviewed_set & excluded_items))
    if contradictory:
        errors.append(ValidationError(
            "ITEM_CONTRADICTORY_STATE", path,
            f"items in more than one state: {', '.join(contradictory)}"))

    unaccounted = sorted(inventory_set - reviewed_set - not_reviewed - excluded_items)
    if unaccounted:
        errors.append(ValidationError(
            "ITEM_UNACCOUNTED", path,
            "discovered items neither reviewed, excluded, nor declared not reviewed: "
            + ", ".join(unaccounted)))

    # FULL is a claim about the enumerated items, not only about the arithmetic.
    if block.get("mode") == "FULL":
        missing = sorted(inventory_set - reviewed_set - excluded_items)
        if missing:
            errors.append(ValidationError(
                "FULL_COVERAGE_INCOMPLETE", path,
                f"FULL claimed while these were not reviewed: {', '.join(missing)}"))

    return errors


def _validate_authorized_scope(document: Dict[str, Any]) -> List[ValidationError]:
    """The audit must stay within the scope it was permitted to read.

    Citing a file proves it was read, so evidence locations are checked too — in a
    monorepo or multi-tenant tree, reading outside the engagement is itself a
    problem, independent of what was found.
    """
    scope = document.get("authorized_scope")
    if not isinstance(scope, list) or not scope:
        return []

    def in_scope(location: str) -> bool:
        normalized = normalize_location(str(location or ""))
        return any(normalized.startswith(normalize_location(prefix)) for prefix in scope)

    errors: List[ValidationError] = []
    for index, finding in enumerate(document.get("findings") or []):
        if not isinstance(finding, dict):
            continue
        path = f"findings[{index}]"
        location = finding.get("location")
        if location and location != "-" and not in_scope(location):
            errors.append(ValidationError(
                "OUT_OF_AUTHORIZED_SCOPE", path,
                f"location {location!r} lies outside the authorized scope"))
        for evidence_index, record in enumerate(finding.get("evidence") or []):
            if not isinstance(record, dict):
                continue
            evidence_location = record.get("location")
            if evidence_location and evidence_location != "-" and not in_scope(evidence_location):
                errors.append(ValidationError(
                    "OUT_OF_AUTHORIZED_SCOPE", f"{path}.evidence[{evidence_index}]",
                    f"evidence location {evidence_location!r} lies outside the authorized scope"))
    return errors


def review_summary(document: Dict[str, Any], mode_name: str) -> Dict[str, List[str]]:
    """Split the inventory into reviewed / not reviewed / excluded / unaccounted.

    `unaccounted` should always be empty in a valid document; it is surfaced so a
    report can show what silence would otherwise hide.
    """
    items = _inventory_items(document, mode_name) or []
    block = (document.get("coverage") or {}).get(mode_name) or {}
    reviewed = set(block.get("reviewed_items") or [])
    not_reviewed = set(block.get("not_reviewed") or [])
    excluded = {
        entry.get("item") for entry in document.get("excluded") or []
        if isinstance(entry, dict)
    }
    return {
        "reviewed": [i for i in items if i in reviewed],
        "not_reviewed": [i for i in items if i in not_reviewed],
        "excluded": [i for i in items if i in excluded],
        "unaccounted": [
            i for i in items
            if i not in reviewed and i not in not_reviewed and i not in excluded
        ],
    }


def diff_inventory(before: Iterable[str], after: Iterable[str]) -> Dict[str, List[str]]:
    """Compare two audits' enumerations, so scope drift is visible."""
    before_set, after_set = set(before), set(after)
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "unchanged": sorted(before_set & after_set),
    }


def _validate_coverage(document: Dict[str, Any]) -> List[ValidationError]:
    errors: List[ValidationError] = []
    coverage = document.get("coverage")
    if coverage is None:
        return errors
    if not isinstance(coverage, dict):
        return [ValidationError("INVALID_COVERAGE", "coverage", "coverage must be an object")]

    declared_exclusions = document.get("excluded")
    exclusion_count = len(declared_exclusions) if isinstance(declared_exclusions, list) else 0

    for mode_name, block in coverage.items():
        path = f"coverage.{mode_name}"
        if not isinstance(block, dict):
            errors.append(ValidationError("INVALID_COVERAGE", path, "must be an object"))
            continue

        mode = block.get("mode")
        if mode not in COVERAGE_MODES:
            errors.append(ValidationError(
                "INVALID_COVERAGE_MODE", path, f"unknown coverage mode {mode!r}"))

        discovered = block.get("discovered", 0)
        excluded = block.get("excluded", 0)
        reviewed = block.get("reviewed", 0)
        if not all(isinstance(v, int) for v in (discovered, excluded, reviewed)):
            errors.append(ValidationError(
                "INVALID_COVERAGE", path, "discovered/excluded/reviewed must be integers"))
            continue

        denominator = discovered - excluded

        if reviewed > denominator:
            errors.append(ValidationError(
                "COVERAGE_OVERCOUNT", path,
                f"reviewed {reviewed} exceeds denominator {denominator}"))

        # FULL is a statement about the denominator, not a judgement call.
        if mode == "FULL" and reviewed != denominator:
            errors.append(ValidationError(
                "FULL_COVERAGE_INCOMPLETE", path,
                f"FULL requires reviewed == {denominator}, got {reviewed}"))

        if mode == "SAMPLED" and not block.get("selection_method"):
            errors.append(ValidationError(
                "SAMPLING_METHOD_MISSING", path,
                "SAMPLED requires a stated selection_method"))

        # Exclusions are counted transparently, never silently dropped.
        if excluded != exclusion_count:
            errors.append(ValidationError(
                "EXCLUSION_COUNT_MISMATCH", path,
                f"excluded {excluded} does not match {exclusion_count} listed exclusions"))

        errors.extend(_validate_coverage_against_inventory(document, mode_name, block))

    return errors


def validate_document(document: Dict[str, Any]) -> List[ValidationError]:
    """Return every schema violation. An empty list means valid.

    Never mutates the input.
    """
    if not isinstance(document, dict):
        return [ValidationError("INVALID_DOCUMENT", "", "document must be an object")]

    errors: List[ValidationError] = []
    findings = document.get("findings")

    if not isinstance(findings, list):
        return [ValidationError("INVALID_FINDINGS", "findings", "findings must be a list")]

    seen_ids: set = set()
    fingerprint_identities: Dict[str, tuple] = {}

    for index, finding in enumerate(findings):
        path = f"findings[{index}]"
        errors.extend(_validate_finding(finding, path))
        if not isinstance(finding, dict):
            continue

        identifier = finding.get("id")
        if identifier:
            if identifier in seen_ids:
                errors.append(ValidationError(
                    "DUPLICATE_ID", path, f"id {identifier!r} appears more than once"))
            seen_ids.add(identifier)

        # One fingerprint must never describe two different problems.
        fingerprint = finding.get("fingerprint")
        if fingerprint:
            identity = (finding.get("category"),
                        normalize_location(str(finding.get("location", ""))))
            previous = fingerprint_identities.get(fingerprint)
            if previous is not None and previous != identity:
                errors.append(ValidationError(
                    "FINGERPRINT_COLLISION", path,
                    f"fingerprint {fingerprint!r} maps to {previous} and {identity}"))
            else:
                fingerprint_identities[fingerprint] = identity

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        for dependency in finding.get("depends_on") or []:
            if dependency not in seen_ids:
                errors.append(ValidationError(
                    "DANGLING_DEPENDENCY", f"findings[{index}]",
                    f"depends_on references unknown id {dependency!r}"))

    errors.extend(_validate_inventory(document))
    errors.extend(_validate_coverage(document))
    errors.extend(_validate_authorized_scope(document))

    # The arithmetic and item-name checks can flag one problem twice; report once.
    deduplicated: List[ValidationError] = []
    seen: set = set()
    for error in errors:
        key = (error.code, error.path)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(error)
    return deduplicated


def is_valid(document: Dict[str, Any]) -> bool:
    return not validate_document(document)


def is_full_coverage(document: Dict[str, Any], mode_name: str) -> bool:
    """True only when that mode genuinely reviewed everything discovered.

    Static and runtime coverage are independent; neither implies the other.
    """
    block = (document.get("coverage") or {}).get(mode_name)
    if not isinstance(block, dict) or block.get("mode") != "FULL":
        return False
    return block.get("reviewed", 0) == block.get("discovered", 0) - block.get("excluded", 0)


# ---------------------------------------------------------------------------
# FIX_PLAN projection
# ---------------------------------------------------------------------------

def to_fix_plan_issues(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Project canonical findings onto the FIX_PLAN contract quality-loop reads.

    Only actionable findings are projected: an OK finding has nothing to fix, and
    a CANNOT VERIFY finding was never established as broken — handing either to
    an automated fixer would be an instruction to change working code.
    """
    issues = []
    for finding in document.get("findings", []):
        if not isinstance(finding, dict):
            continue
        if finding.get("status") in NON_ACTIONABLE_STATUSES:
            continue
        issues.append({
            "id": finding.get("id"),
            "severity": finding.get("severity"),
            "title": finding.get("title"),
            "file": finding.get("location"),
            "problem": finding.get("impact") or finding.get("title"),
            "fix": finding.get("proposed_fix", ""),
            # Workflow state, not audit status — quality-loop advances this.
            "status": "open",
        })

    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i["severity"], 99), str(i["id"])))
    return issues


def to_fix_plan_md(document: Dict[str, Any], project: Optional[str] = None) -> str:
    """Render FIX_PLAN.md in the format the existing parser already reads."""
    issues = to_fix_plan_issues(document)
    counts = {severity: 0 for severity in SEVERITIES}
    for issue in issues:
        if issue["severity"] in counts:
            counts[issue["severity"]] += 1

    lines = [
        f"# Fix Plan — {project or document.get('scope', 'audit')}",
        f"Generated: {document.get('generated', '')}",
        f"Scope: {document.get('scope', '')}",
        f"Total issues: {len(issues)} (CRITICAL: {counts['CRITICAL']} · "
        f"HIGH: {counts['HIGH']} · MEDIUM: {counts['MEDIUM']} · LOW: {counts['LOW']})",
        "",
    ]

    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        group = [i for i in issues if i["severity"] == severity]
        if not group:
            continue
        lines += ["---", "", f"## {severity.capitalize()}", ""]
        for issue in group:
            lines += [
                f"### [{severity}] {issue['id']} — {issue['title']}",
                f"- **ID:** `{issue['id']}`",
                f"- **File:** `{issue['file']}`",
                f"- **Problem:** {issue['problem']}",
                f"- **Fix:** {issue['fix']}",
                f"- **Status:** `{issue['status']}`",
                "",
            ]

    return "\n".join(lines)


def write_audit_json(document: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(serialize_document(document))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate an AUDIT.json document")
    parser.add_argument("path", help="Path to AUDIT.json")
    parser.add_argument("--fix-plan", help="Also write a FIX_PLAN.md projection here")
    args = parser.parse_args()

    with open(args.path, encoding="utf-8") as handle:
        document = parse_document(handle.read())

    errors = validate_document(document)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"\n{len(errors)} validation error(s)")
        return 1

    print(f"OK: {len(document.get('findings', []))} finding(s) validated")

    if args.fix_plan:
        with open(args.fix_plan, "w", encoding="utf-8") as handle:
            handle.write(to_fix_plan_md(document))
        print(f"Wrote {args.fix_plan}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

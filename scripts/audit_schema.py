#!/usr/bin/env python3
"""Canonical audit finding model — validation, round-trip, FIX_PLAN projection.

Reference implementation of `skills/app-audit-plan/references/audit-schema.md`.
Both AUDIT.md and AUDIT.json are produced from the objects handled here, so the
two outputs cannot drift apart.

Validation returns a list of errors rather than raising, so a caller can report
every problem in one pass instead of one per run.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "1.1"

# Rules tightened in 1.1. A 1.0 document keeps the looser reading so existing
# audits stay valid; crashes and immutability bugs are fixed for every version,
# because a traceback is never the correct answer to bad input.
TIGHTENED_SCHEMA_VERSION = "1.1"

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

# Kinds asserting what the code says, and so answerable only by quoting it.
QUOTE_REQUIRED_KINDS = frozenset({"code-read", "test-run"})

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
# Anchored on a non-empty path: ":42" is not a location, and it used to
# normalize to "" — which prefix-matched every authorized_scope entry.
LINE_SUFFIX_RE = re.compile(r":\d+$")
LOCATED_LINE_RE = re.compile(r"^.+:\d+$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{12}$")

# A location standing in for "nowhere" — permitted only where there is no code
# to point at.
NO_LOCATION = "-"

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


def _version_tuple(version: Any) -> tuple:
    """Parse a dotted version into comparable integers.

    Compared numerically, not as strings: `"1.10" >= "1.9"` is False as text, so a
    future 1.10 would silently fall back to the looser 1.0 reading. A gate whose
    failure mode is "accept less" has to be the one thing that cannot drift.

    An unparseable version sorts lowest, so garbage gets the permissive reading
    rather than a crash — the enum and field rules still apply to the document.
    """
    parts = str(version or "").split(".")
    numbers = []
    for part in parts:
        digits = "".join(c for c in part if c.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers)


def is_tightened(document: Dict[str, Any]) -> bool:
    """True when this document opts into the 1.1 rules.

    The tightened rules reject output that 1.0 accepted, so an existing audit
    must keep validating unchanged. Version-gating is what lets a stricter rule
    ship without retroactively invalidating a report someone already delivered.
    """
    if not isinstance(document, dict):
        return False
    return _version_tuple(document.get("schema_version")) >= _version_tuple(
        TIGHTENED_SCHEMA_VERSION)


def _non_empty_str(value: Any) -> bool:
    """True for a string carrying actual content.

    Truthiness is not enough: `"  "` and `True` are both truthy, and both were
    accepted where the spec says "non-empty". `True` in particular was a
    one-token bypass of the priority-override rule.
    """
    return isinstance(value, str) and bool(value.strip())


def _is_count(value: Any) -> bool:
    """True for a non-negative integer that is not a bool.

    `isinstance(True, int)` is True in Python, so a bool satisfied every
    coverage arithmetic check; a negative count satisfied them too.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _path_segments(path: str) -> List[str]:
    """Split a normalized path, resolving `..` so traversal cannot escape.

    Without this, `apps/admin/../../etc/passwd` compared as a string starting
    with `apps/admin/` and counted as inside that scope.
    """
    resolved: List[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if resolved:
                resolved.pop()
            continue
        resolved.append(segment)
    return resolved


def location_within(location: str, prefix: str) -> bool:
    """True when `location` is the prefix itself or sits beneath it.

    Compared segment by segment, because a raw `startswith` puts
    `apps/admin-secrets/` inside a scope of `apps/admin`. An out-of-scope
    citation is a disclosure whether or not the finding is real, so this is a
    confidentiality check, not a formatting one.
    """
    location_parts = _path_segments(normalize_location(location))
    prefix_parts = _path_segments(normalize_location(prefix))
    if not prefix_parts:
        return False
    return location_parts[:len(prefix_parts)] == prefix_parts


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
    finding: Dict[str, Any], current_commits: Optional[Dict[str, str]] = None
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

    # No git context is the common case, not an error: nothing can be stale
    # relative to an unknown revision.
    if not current_commits:
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

    # A deep copy, because a shallow `dict()` shares the nested `evidence` list
    # with the caller — mutating the result then mutated the input, which is
    # exactly what "never mutates the input" promises it will not do.
    decayed = copy.deepcopy(finding)
    decayed["confidence"] = "PROBABLE"
    decayed["needs_reverification"] = True
    decayed["confidence_note"] = "; ".join(
        f"evidence recorded at {recorded} but {path} is now at {current}"
        for path, recorded, current in stale_records
    ) + "; re-verify before relying on this finding"
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
        if value is None:
            continue
        # `value not in allowed` raises TypeError on a list or dict, which took
        # the whole validator down instead of reporting one bad field.
        if not isinstance(value, str) or value not in allowed:
            errors.append(ValidationError(
                code, path, f"{field} has unknown value {value!r}"))
    return errors


def _validate_evidence(
    finding: Dict[str, Any], path: str, tightened: bool = False
) -> List[ValidationError]:
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
        # Membership on an unhashable value raises, so the type is checked first.
        if not isinstance(kind, str) or kind not in EVIDENCE_KINDS:
            errors.append(ValidationError(
                "INVALID_EVIDENCE_KIND", record_path, f"unknown evidence kind {kind!r}"))
        if not record.get("location"):
            errors.append(ValidationError(
                "EVIDENCE_MISSING_LOCATION", record_path, "evidence needs a location"))

        proves = record.get("proves")
        if not (_non_empty_str(proves) if tightened else bool(proves)):
            errors.append(ValidationError(
                "EVIDENCE_MISSING_PROVES", record_path,
                "evidence must state what it proves"))

        # A quote is the artifact the whole evidence standard rests on: reading
        # code and asserting what it does is checkable only against the lines
        # themselves. Kinds that describe reachability or shape rather than
        # content have nothing to quote, so they are exempt.
        if (tightened and isinstance(kind, str) and kind in QUOTE_REQUIRED_KINDS
                and not _non_empty_str(record.get("quote"))):
            errors.append(ValidationError(
                "EVIDENCE_MISSING_QUOTE", record_path,
                f"evidence of kind {kind!r} must quote the decisive lines"))

    # Documentation and code shape never establish behavior.
    if finding.get("confidence") == "CONFIRMED":
        kinds = {r.get("kind") for r in evidence
                 if isinstance(r, dict) and isinstance(r.get("kind"), str)}
        if not (kinds & CONFIRMING_EVIDENCE_KINDS):
            errors.append(ValidationError(
                "UNSUPPORTED_CONFIRMED", path,
                "CONFIRMED requires code-read, test-run, or runtime-observation evidence"))

    return errors


def _validate_finding(
    finding: Dict[str, Any], path: str, tightened: bool = False
) -> List[ValidationError]:
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
    elif tightened and not FINGERPRINT_RE.match(str(fingerprint)):
        # The spec has always said 12 hex chars. Only truthiness was checked, so
        # `True` was a valid fingerprint — and `True == 1`, which silently
        # aliased it with any integer fingerprint in the collision map.
        errors.append(ValidationError(
            "INVALID_FINGERPRINT", path,
            f"fingerprint {fingerprint!r} must be 12 lowercase hex characters"))

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

    if tightened:
        title = finding.get("title")
        if title is not None and not _non_empty_str(title):
            errors.append(ValidationError(
                "EMPTY_TITLE", path, "title must be a non-empty string"))
        # A newline in a title closed the FIX_PLAN heading it was rendered into
        # and let the remainder become fabricated issues. The renderer flattens
        # it too; this rejects it at the source rather than relying on that.
        elif isinstance(title, str) and "\n" in title:
            errors.append(ValidationError(
                "TITLE_NOT_ONE_LINE", path,
                "title must be a single line: a newline forges FIX_PLAN headings"))

    errors.extend(_validate_enums(finding, path))
    errors.extend(_validate_evidence(finding, path, tightened))

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
        location = str(finding.get("location", ""))
        # `LINE_SUFFIX_RE` is unanchored, so ":42" satisfied it — and ":42"
        # normalizes to "", which prefix-matched every authorized_scope entry.
        pattern = LOCATED_LINE_RE if tightened else LINE_SUFFIX_RE
        if not pattern.search(location):
            errors.append(ValidationError(
                "LOCATION_NEEDS_LINE", path,
                f"status {status} requires a file:line location"))

    # CANNOT VERIFY is permanent until someone does the named step.
    if status == "CANNOT VERIFY":
        has_reason = (
            (_non_empty_str(finding.get("blocked_by"))
             and _non_empty_str(finding.get("resolves_when")))
            if tightened else
            bool(finding.get("blocked_by")) and bool(finding.get("resolves_when"))
        )
        if not has_reason:
            errors.append(ValidationError(
                "CANNOT_VERIFY_NEEDS_RESOLUTION", path,
                "CANNOT VERIFY requires blocked_by and resolves_when"))

    # Priority is derived; deviating from it is a decision that must be stated.
    severity, likelihood = finding.get("severity"), finding.get("likelihood")
    # A dict key lookup raises on an unhashable value; the enum rules have
    # already reported it, so the matrix simply has nothing to say here.
    expected = (PRIORITY_MATRIX.get((severity, likelihood))
                if isinstance(severity, str) and isinstance(likelihood, str) else None)
    if expected and finding.get("priority") != expected:
        reason = finding.get("priority_override_reason")
        stated = _non_empty_str(reason) if tightened else bool(reason)
        if not stated:
            errors.append(ValidationError(
                "PRIORITY_MISMATCH", path,
                f"{severity}/{likelihood} implies {expected}, got "
                f"{finding.get('priority')!r}; set priority_override_reason to deviate"))

    # High-priority security claims need a demonstrated impact path.
    if finding.get("category") == "security" and finding.get("priority") in ("P0", "P1"):
        impact = finding.get("impact")
        if not (_non_empty_str(impact) if tightened else bool(impact)):
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
    document: Dict[str, Any], mode_name: str, block: Dict[str, Any],
    tightened: bool = False,
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
    # An unhashable item would raise here; report it instead of crashing.
    unhashable = [i for i in items if not isinstance(i, (str, int, float, bool, tuple))]
    if unhashable:
        errors.append(ValidationError(
            "INVALID_INVENTORY_ITEM", path,
            f"inventory items must be scalars, got {len(unhashable)} that are not"))
        items = [i for i in items if isinstance(i, (str, int, float, bool, tuple))]
    inventory_set = set(items)

    discovered = block.get("discovered")
    if isinstance(discovered, int) and discovered != len(items):
        errors.append(ValidationError(
            "DISCOVERED_MISMATCH", path,
            f"discovered {discovered} does not match {len(items)} enumerated items"))

    reviewed_items = block.get("reviewed_items")
    if reviewed_items is None:
        # Omitting the names used to return early and skip every name-level rule
        # below — including "FULL by name", the unaccounted-item check, and the
        # contradictory-state check. Counting is exactly what rule 23 says is
        # not enough, so the omission was a way to be graded on the count alone.
        if tightened:
            errors.append(ValidationError(
                "REVIEWED_ITEMS_MISSING", path,
                "an enumerated mode must name its reviewed items, not only count them"))
        reviewed_items = []
    elif not isinstance(reviewed_items, list):
        errors.append(ValidationError(
            "INVALID_REVIEWED_ITEMS", path, "reviewed_items must be a list"))
        reviewed_items = []

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

    raw_not_reviewed = block.get("not_reviewed")
    if raw_not_reviewed is not None and not isinstance(raw_not_reviewed, list):
        # `set("/b")` becomes {'/', 'b'}, which accounts for nothing while
        # looking like it accounted for something.
        errors.append(ValidationError(
            "INVALID_NOT_REVIEWED", path, "not_reviewed must be a list"))
        raw_not_reviewed = []
    not_reviewed = set(raw_not_reviewed or [])

    unknown_not_reviewed = sorted(i for i in not_reviewed if i not in inventory_set)
    if unknown_not_reviewed:
        errors.append(ValidationError(
            "NOT_REVIEWED_NOT_IN_INVENTORY", path,
            "not_reviewed names items absent from the inventory: "
            + ", ".join(unknown_not_reviewed)))

    duplicate_reviewed = sorted({i for i in reviewed_items if reviewed_items.count(i) > 1})
    if duplicate_reviewed:
        # `reviewed` matching len(reviewed_items) is satisfied by repeating one
        # name, which inflates the numerator the manifest exists to make checkable.
        errors.append(ValidationError(
            "REVIEWED_ITEMS_DUPLICATE", path,
            f"reviewed_items repeats: {', '.join(duplicate_reviewed)}"))

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
    if scope is None:
        return []
    # A bare string used to silently disable both scope rules: it is not a list,
    # so the check returned early with no error at all. A malformed boundary must
    # fail loudly — this is the one control nobody else is auditing.
    if not isinstance(scope, list) or not scope:
        return [ValidationError(
            "INVALID_AUTHORIZED_SCOPE", "authorized_scope",
            "authorized_scope must be a non-empty list of directory paths")]

    def in_scope(location: str) -> bool:
        return any(location_within(str(location or ""), str(prefix)) for prefix in scope)

    errors: List[ValidationError] = []
    for index, finding in enumerate(document.get("findings") or []):
        if not isinstance(finding, dict):
            continue
        path = f"findings[{index}]"
        location = finding.get("location")
        if location and location != NO_LOCATION and not in_scope(location):
            errors.append(ValidationError(
                "OUT_OF_AUTHORIZED_SCOPE", path,
                f"location {location!r} lies outside the authorized scope"))
        for evidence_index, record in enumerate(finding.get("evidence") or []):
            if not isinstance(record, dict):
                continue
            evidence_location = record.get("location")
            if evidence_location and evidence_location != NO_LOCATION and not in_scope(evidence_location):
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


def _validate_coverage(
    document: Dict[str, Any], tightened: bool = False
) -> List[ValidationError]:
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

        # Defaulting an absent count to 0 made `{"mode": "FULL"}` valid, because
        # 0 == 0 - 0: FULL coverage asserted with no denominator whatsoever.
        missing_counts = [k for k in ("discovered", "excluded", "reviewed")
                         if block.get(k) is None]
        if missing_counts and tightened:
            errors.append(ValidationError(
                "COVERAGE_COUNTS_MISSING", path,
                "coverage must state " + ", ".join(missing_counts)))
            continue

        discovered = block.get("discovered", 0)
        excluded = block.get("excluded", 0)
        reviewed = block.get("reviewed", 0)
        # `isinstance(True, int)` is True, so a bool satisfied every check below,
        # and a negative count satisfied them too.
        if not all(_is_count(v) for v in (discovered, excluded, reviewed)):
            errors.append(ValidationError(
                "INVALID_COVERAGE", path,
                "discovered/excluded/reviewed must be non-negative integers"))
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

        # FULL over nothing is arithmetically true and substantively empty: a mode
        # that reviewed no items may not report complete coverage of them.
        if mode == "FULL" and denominator == 0:
            errors.append(ValidationError(
                "EMPTY_DENOMINATOR", path,
                "FULL requires at least one non-excluded item; nothing was reviewed"))

        selection = block.get("selection_method")
        if mode == "SAMPLED" and not (
            _non_empty_str(selection) if tightened else bool(selection)
        ):
            errors.append(ValidationError(
                "SAMPLING_METHOD_MISSING", path,
                "SAMPLED requires a stated selection_method"))

        # Exclusions are counted transparently, never silently dropped.
        if excluded != exclusion_count:
            errors.append(ValidationError(
                "EXCLUSION_COUNT_MISMATCH", path,
                f"excluded {excluded} does not match {exclusion_count} listed exclusions"))

        errors.extend(_validate_coverage_against_inventory(
            document, mode_name, block, tightened))

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

    tightened = is_tightened(document)
    seen_ids: set = set()
    fingerprint_identities: Dict[str, tuple] = {}

    for index, finding in enumerate(findings):
        path = f"findings[{index}]"
        errors.extend(_validate_finding(finding, path, tightened))
        if not isinstance(finding, dict):
            continue

        identifier = finding.get("id")
        # An unhashable id would raise on `in`/`add`; the format rule has already
        # reported it, so it is simply not tracked for uniqueness here.
        if identifier and isinstance(identifier, (str, int)):
            if identifier in seen_ids:
                errors.append(ValidationError(
                    "DUPLICATE_ID", path, f"id {identifier!r} appears more than once"))
            seen_ids.add(identifier)

        # One fingerprint must never describe two different problems.
        fingerprint = finding.get("fingerprint")
        if fingerprint and isinstance(fingerprint, (str, int)):
            # `rule` completes the triple the spec defines. It is optional, so a
            # document omitting it keeps the older two-part identity — but two
            # defects in one file can only be told apart when it is present.
            identity = (finding.get("category"),
                        normalize_location(str(finding.get("location", ""))),
                        finding.get("rule"))
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
        depends_on = finding.get("depends_on")
        if depends_on is None:
            continue
        # Iterating a non-list crashed on an int and walked characters on a
        # string, reporting a dangling dependency on 'I'.
        if not isinstance(depends_on, list):
            errors.append(ValidationError(
                "INVALID_DEPENDS_ON", f"findings[{index}]",
                f"depends_on must be a list of ids, got {type(depends_on).__name__}"))
            continue
        for dependency in depends_on:
            if dependency not in seen_ids:
                errors.append(ValidationError(
                    "DANGLING_DEPENDENCY", f"findings[{index}]",
                    f"depends_on references unknown id {dependency!r}"))

    errors.extend(_validate_inventory(document))
    errors.extend(_validate_coverage(document, tightened))
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

def _one_line(value: Any) -> str:
    """Flatten a value to a single line safe to interpolate into Markdown.

    `to_fix_plan_md` writes `### [SEVERITY] ID — title` headings, so a newline
    inside a title used to close the heading and let the rest of the string
    become new headings — a verified injection that produced a fabricated
    CRITICAL issue in the plan quality-loop then treated as real work. Leading
    `#` is neutralised for the same reason.
    """
    if value is None:
        return ""
    # `split()` collapses every kind of whitespace, `\r` and U+2028 included, so a
    # line break in any encoding cannot survive into the rendered heading.
    text = " ".join(str(value).split())
    # A leading `#` would open a heading of its own. Stripping to empty is fine:
    # a title of only `#` characters carries no information to preserve, and an
    # empty cell is more honest than a forged heading. (1.1 rejects such a title
    # at the source anyway; this keeps the renderer safe for 1.0 documents.)
    return text.lstrip("#").strip()


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
    # An unrecognised severity still has to appear somewhere: it used to be
    # counted in the total but rendered in no group, so the issue vanished from
    # the plan while the header claimed it was there.
    unknown = [i for i in issues if i["severity"] not in counts]
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

    groups = [(s_, [i for i in issues if i["severity"] == s_])
              for s_ in ("CRITICAL", "HIGH", "MEDIUM", "LOW")]
    if unknown:
        groups.append(("UNKNOWN", unknown))

    for severity, group in groups:
        if not group:
            continue
        lines += ["---", "", f"## {severity.capitalize()}", ""]
        for issue in group:
            lines += [
                f"### [{severity}] {_one_line(issue['id'])} — {_one_line(issue['title'])}",
                f"- **ID:** `{_one_line(issue['id'])}`",
                f"- **File:** `{_one_line(issue['file'])}`",
                f"- **Problem:** {_one_line(issue['problem'])}",
                f"- **Fix:** {_one_line(issue['fix'])}",
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

    try:
        with open(args.path, encoding="utf-8") as handle:
            document = parse_document(handle.read())
    except OSError as exc:
        print(f"FAIL: cannot read {args.path}: {exc}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: {args.path} is not valid JSON: {exc}")
        return 1
    if not isinstance(document, dict):
        print(f"FAIL: {args.path} must contain a JSON object")
        return 1

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

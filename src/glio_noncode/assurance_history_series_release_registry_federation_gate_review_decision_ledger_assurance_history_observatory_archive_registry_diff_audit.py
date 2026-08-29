"""Independent audit of observatory archive registry diff documents.

The typed diff model is intentionally strict and fail-fast. This companion
boundary is operator-facing: it accepts a public mapping, evaluates a fixed
set of structural and integrity checks, and returns a complete or incomplete
report instead of losing all diagnostic detail at the first malformed field.
It never treats a diff as a new evidence source and never includes the input
path or private attribution metadata in its public report.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "source-addresses",
    "item-identities",
    "action-sides",
    "field-conservation",
    "count-conservation",
    "registry-change-fields",
    "aggregate-state",
    "item-addresses",
    "content-address",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = (
    "diff_id",
    "version",
    "boundary",
    "baseline_address",
    "candidate_address",
    "baseline_registry_id",
    "candidate_registry_id",
    "baseline_state",
    "candidate_state",
    "baseline_accepted",
    "candidate_accepted",
    "baseline_release_ready",
    "candidate_release_ready",
    "baseline_metrics",
    "candidate_metrics",
    "baseline_verification_address",
    "candidate_verification_address",
    "registry_changed_fields",
    "item_count",
    "added_count",
    "removed_count",
    "changed_count",
    "unchanged_count",
    "state",
    "items",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "evidence address", prefix)
    except ValidationError:
        return fallback


def _typed(value: Mapping[str, Any]) -> diff_model.RegistryDiff | None:
    try:
        return diff_model.diff_from_mapping(value)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


class RegistryDiffAuditCheck:
    """One independently addressed assertion over a diff document."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "registry diff audit check ID", 128)
        self.passed = _bool(passed, "registry diff audit check passed")
        self.detail = _text(detail, "registry diff audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "registry diff audit evidence address", 2048)
        self.content_address = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=AUDIT_CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryDiffAuditCheck:
        value = _mapping(value, "registry diff audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "registry diff audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("registry diff audit check content address mismatch")
        return result


class RegistryDiffAudit:
    """Public complete or incomplete report for a registry diff mapping."""

    def __init__(self, diff_address: str, baseline_address: str, candidate_address: str, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryDiffAuditCheck], content_address: str) -> None:
        self.diff_address = diff_address
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.state = state
        self.complete = complete
        self.accepted = accepted
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "registry diff audit diff address", diff_model.DIFF_PREFIX)
        _address(self.baseline_address, "registry diff audit baseline address", registry_model.REGISTRY_PREFIX)
        _address(self.candidate_address, "registry diff audit candidate address", registry_model.REGISTRY_PREFIX)
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("registry diff audit state does not match completion")
        _bool(self.complete, "registry diff audit complete")
        _bool(self.accepted, "registry diff audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("registry diff audit check set is invalid")
        _count(self.passed_count, "registry diff audit passed count", MAX_CHECKS)
        _count(self.failed_count, "registry diff audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("registry diff audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("registry diff audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry diff audit content address")
        else:
            _address(self.content_address, "registry diff audit content address", AUDIT_PREFIX)
        if not diff_model._public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("registry diff audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_address", "baseline_address", "candidate_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: RegistryDiffAudit) -> str:
    if not isinstance(value, RegistryDiffAudit):
        raise ValidationError("registry diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryDiffAuditCheck:
    return RegistryDiffAuditCheck(check_id, passed, detail, evidence)


def _registry_projection(value: diff_model.RegistryDiff, *, baseline: bool) -> dict[str, Any]:
    prefix = "baseline_" if baseline else "candidate_"
    metrics = value.baseline_metrics if baseline else value.candidate_metrics
    return {
        "registry_id": value.baseline_registry_id if baseline else value.candidate_registry_id,
        "version": registry_model.VERSION,
        "boundary": registry_model.BOUNDARY,
        "entry_count": metrics["entry_count"],
        "state": value.baseline_state if baseline else value.candidate_state,
        "accepted": value.baseline_accepted if baseline else value.candidate_accepted,
        "release_ready": value.baseline_release_ready if baseline else value.candidate_release_ready,
        "metrics": metrics,
        "verification_address": getattr(value, prefix + "verification_address"),
    }


def _audit_mapping(document: Mapping[str, Any]) -> RegistryDiffAudit:
    fallback_diff = diff_model.DIFF_PREFIX + ":unresolved"
    fallback_registry = registry_model.REGISTRY_PREFIX + ":unresolved"
    diff_address = _safe_address(document.get("content_address"), diff_model.DIFF_PREFIX, fallback_diff)
    baseline_address = _safe_address(document.get("baseline_address"), registry_model.REGISTRY_PREFIX, fallback_registry)
    candidate_address = _safe_address(document.get("candidate_address"), registry_model.REGISTRY_PREFIX, fallback_registry)
    typed = _typed(document)
    if typed is not None:
        diff_address = typed.content_address
        baseline_address = typed.baseline_address
        candidate_address = typed.candidate_address

    exact_fields = set(document) == set(EXPECTED_FIELDS)
    public_boundary = diff_model._public(document)
    source_addresses = False
    try:
        _address(document.get("baseline_address"), "baseline address", registry_model.REGISTRY_PREFIX)
        _address(document.get("candidate_address"), "candidate address", registry_model.REGISTRY_PREFIX)
        _address(document.get("baseline_verification_address"), "baseline verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
        _address(document.get("candidate_verification_address"), "candidate verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
        source_addresses = True
    except ValidationError:
        source_addresses = False

    item_identities = False
    action_sides = False
    field_conservation = False
    count_conservation = False
    registry_change_fields = False
    aggregate_state = False
    item_addresses = False
    content_address = False
    mapping_round_trip = False
    if typed is not None:
        item_identities = (
            tuple(item.ordinal for item in typed.items) == tuple(range(1, typed.item_count + 1))
            and tuple(item.entry_id for item in typed.items) == tuple(sorted(item.entry_id for item in typed.items))
            and len({item.entry_id for item in typed.items}) == typed.item_count
            and len({item.content_address for item in typed.items}) == typed.item_count
        )
        action_sides = all(
            (item.action == diff_model.RegistryDiffAction.ADDED.value and item.baseline is None and item.candidate is not None)
            or (item.action == diff_model.RegistryDiffAction.REMOVED.value and item.baseline is not None and item.candidate is None)
            or (item.action in {diff_model.RegistryDiffAction.CHANGED.value, diff_model.RegistryDiffAction.UNCHANGED.value} and item.baseline is not None and item.candidate is not None)
            for item in typed.items
        )
        field_conservation = all(
            (item.baseline is None or item.candidate is None or tuple(item.changed_fields) == diff_model._changed_entry_fields(item.baseline, item.candidate))
            and (item.baseline is not None and item.candidate is not None or tuple(item.changed_fields) == tuple(diff_model.ENTRY_FIELDS))
            for item in typed.items
        )
        count_conservation = (
            typed.item_count == len(typed.items)
            and typed.added_count + typed.removed_count + typed.changed_count + typed.unchanged_count == typed.item_count
            and typed.added_count == sum(item.action == "added" for item in typed.items)
            and typed.removed_count == sum(item.action == "removed" for item in typed.items)
            and typed.changed_count == sum(item.action == "changed" for item in typed.items)
            and typed.unchanged_count == sum(item.action == "unchanged" for item in typed.items)
        )
        before = _registry_projection(typed, baseline=True)
        after = _registry_projection(typed, baseline=False)
        registry_change_fields = tuple(field for field in diff_model.REGISTRY_FIELDS if before[field] != after[field]) == tuple(typed.registry_changed_fields)
        aggregate_state = typed.state == diff_model._aggregate_diff_state(typed.baseline_state, typed.candidate_state, typed.baseline_accepted, typed.candidate_accepted, typed.baseline_release_ready, typed.candidate_release_ready, any(item.action != "unchanged" for item in typed.items) or bool(typed.registry_changed_fields))
        item_addresses = all(diff_model.address_diff_item(item) == item.content_address for item in typed.items)
        content_address = diff_model.address_diff(typed) == typed.content_address
        try:
            mapping_round_trip = diff_model.diff_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip = False

    checks = (
        _check("exact-fields", exact_fields, "diff document contains exactly the declared public fields", diff_address),
        _check("public-boundary", public_boundary, "diff document contains no private, path, or attribution metadata", diff_address),
        _check("source-addresses", source_addresses, "baseline, candidate, and source verification addresses use public namespaces", diff_address),
        _check("item-identities", item_identities, "diff item ordinals, keys, and addresses are ordered and unique", diff_address),
        _check("action-sides", action_sides, "each action has the correct baseline and candidate sides", diff_address),
        _check("field-conservation", field_conservation, "changed fields are derived from the two entry projections", diff_address),
        _check("count-conservation", count_conservation, "action counts conserve the item set", diff_address),
        _check("registry-change-fields", registry_change_fields, "aggregate changed fields are derived from registry projections", diff_address),
        _check("aggregate-state", aggregate_state, "aggregate diff state is derived from source posture and changes", diff_address),
        _check("item-addresses", item_addresses, "every nested diff item address reproduces", diff_address),
        _check("content-address", content_address, "diff content address reproduces from its public projection", diff_address),
        _check("mapping-round-trip", mapping_round_trip, "typed public mapping rehydrates without projection drift", diff_address),
    )
    complete = all(check.passed for check in checks)
    body = {"diff_address": diff_address, "baseline_address": baseline_address, "candidate_address": candidate_address, "state": "complete" if complete else "incomplete", "complete": complete, "accepted": complete, "checks": checks}
    provisional = RegistryDiffAudit(**body, content_address="pending:audit")
    return RegistryDiffAudit(**body, content_address=address_audit(provisional))


def audit_diff(value: diff_model.RegistryDiff) -> RegistryDiffAudit:
    if not isinstance(value, diff_model.RegistryDiff):
        raise ValidationError("registry diff audit requires a typed diff")
    diff_model.verify_diff(value)
    return _audit_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryDiffAudit:
    value = _mapping(value, "registry diff audit input")
    if "diff_address" in value and "checks" in value:
        _strict(value, {"diff_address", "baseline_address", "candidate_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address"}, "registry diff audit")
        checks = tuple(RegistryDiffAuditCheck.from_mapping(item) for item in _mapping(value["checks"], "registry diff audit checks").values()) if isinstance(value["checks"], Mapping) else tuple(RegistryDiffAuditCheck.from_mapping(item) for item in value["checks"])
        return RegistryDiffAudit(value["diff_address"], value["baseline_address"], value["candidate_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
    return _audit_mapping(value)


def audit_json(value: RegistryDiffAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def verify_audit(value: RegistryDiffAudit) -> RegistryDiffAudit:
    if not isinstance(value, RegistryDiffAudit):
        raise ValidationError("registry diff audit verification requires a typed audit")
    value._validate()
    return value


def render_audit_markdown(value: RegistryDiffAudit) -> str:
    verify_audit(value)
    lines = ["# Assurance History Observatory Archive Registry Diff Audit", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Diff: `{value.diff_address}`", f"- Baseline: `{value.baseline_address}`", f"- Candidate: `{value.candidate_address}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"diff_address": {"type": "string"}, "baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_diff_items": diff_model.MAX_DIFF_ITEMS}, "features": ("public mapping audit", "fixed structural check set", "entry action and field conservation", "aggregate registry transition audit", "nested item address replay", "content-address replay", "incomplete tamper diagnostics", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "EXPECTED_FIELDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryDiffAudit",
    "RegistryDiffAuditCheck",
    "address_audit",
    "audit_diff",
    "audit_from_mapping",
    "audit_json",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]

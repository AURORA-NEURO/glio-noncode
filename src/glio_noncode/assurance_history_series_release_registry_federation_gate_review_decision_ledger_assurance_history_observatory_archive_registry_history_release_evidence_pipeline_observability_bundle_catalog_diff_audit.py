"""Independent assurance for observability-bundle catalog diffs.

The diff model rejects malformed typed construction.  This companion keeps a
reviewable result even when a copied public mapping is damaged: every audit
always contains the same fixed checks, and a failed check carries the diff
address as its evidence anchor.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "catalog-addresses",
    "label-union",
    "status-conservation",
    "entry-field-conservation",
    "denominator-conservation",
    "delta-conservation",
    "entry-addresses",
    "aggregate-state",
    "content-address",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff.FIELDS


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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must contain at most {maximum} items")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "observability bundle catalog diff audit evidence address", prefix)
    except ValidationError:
        return fallback


def _typed(value: Mapping[str, Any]) -> diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff | None:
    try:
        return diff_model.diff_from_mapping(value)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck:
    """One fixed, independently addressed catalog-diff assertion."""

    FIELDS = ("check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str | None = None) -> None:
        self.check_id = _text(check_id, "observability bundle catalog diff audit check ID", 128)
        self.passed = _bool(passed, "observability bundle catalog diff audit check passed")
        self.detail = _text(detail, "observability bundle catalog diff audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "observability bundle catalog diff audit evidence address", 2048)
        expected = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=CHECK_PREFIX)
        if content_address is not None and content_address != expected:
            raise ValidationError("observability bundle catalog diff audit check content address does not replay")
        self.content_address = expected

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck:
        value = _mapping(value, "observability bundle catalog diff audit check")
        _strict(value, set(cls.FIELDS), "observability bundle catalog diff audit check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog diff audit check is missing fields: {missing}")
        return cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"], value["content_address"])


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit:
    """Complete or incomplete public audit of a catalog diff."""

    FIELDS = ("diff_address", "left_catalog_address", "right_catalog_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address")

    def __init__(self, diff_address: str, left_catalog_address: str, right_catalog_address: str, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck], content_address: str) -> None:
        self.diff_address = diff_address
        self.left_catalog_address = left_catalog_address
        self.right_catalog_address = right_catalog_address
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
        _address(self.diff_address, "observability bundle catalog diff audit diff address", diff_model.DIFF_PREFIX)
        _address(self.left_catalog_address, "observability bundle catalog diff audit left catalog address", diff_model.catalog_model.CATALOG_PREFIX)
        _address(self.right_catalog_address, "observability bundle catalog diff audit right catalog address", diff_model.catalog_model.CATALOG_PREFIX)
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("observability bundle catalog diff audit state does not match completion")
        _bool(self.complete, "observability bundle catalog diff audit complete")
        _bool(self.accepted, "observability bundle catalog diff audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("observability bundle catalog diff audit check set is invalid")
        _count(self.passed_count, "observability bundle catalog diff audit passed count", MAX_CHECKS)
        _count(self.failed_count, "observability bundle catalog diff audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != MAX_CHECKS or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("observability bundle catalog diff audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("observability bundle catalog diff audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog diff audit content address")
        else:
            _address(self.content_address, "observability bundle catalog diff audit content address", AUDIT_PREFIX)
        if not diff_model._public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("observability bundle catalog diff audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "left_catalog_address": self.left_catalog_address, "right_catalog_address": self.right_catalog_address, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_address", "left_catalog_address", "right_catalog_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit):
        raise ValidationError("observability bundle catalog diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck(check_id, passed, detail, evidence)


def _field_changes(item: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff) -> tuple[str, ...]:
    if item.left_entry is None or item.right_entry is None:
        return ()
    left = diff_model._projection(item.left_entry)
    right = diff_model._projection(item.right_entry)
    return tuple(sorted(field for field in diff_model.COMPARABLE_FIELDS if left[field] != right[field]))


def _audit_mapping(document: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit:
    fallback_diff = diff_model.DIFF_PREFIX + ":unresolved"
    fallback_catalog = diff_model.catalog_model.CATALOG_PREFIX + ":unresolved"
    diff_address = _safe_address(document.get("content_address"), diff_model.DIFF_PREFIX, fallback_diff)
    left_catalog_address = _safe_address(document.get("left_catalog_address"), diff_model.catalog_model.CATALOG_PREFIX, fallback_catalog)
    right_catalog_address = _safe_address(document.get("right_catalog_address"), diff_model.catalog_model.CATALOG_PREFIX, fallback_catalog)
    typed = _typed(document)
    if typed is not None:
        diff_address = typed.content_address
        left_catalog_address = typed.left_catalog_address
        right_catalog_address = typed.right_catalog_address

    exact_fields = set(document) == set(EXPECTED_FIELDS)
    public_boundary = diff_model._public(document)
    catalog_addresses = False
    try:
        _address(document.get("left_catalog_address"), "left catalog address", diff_model.catalog_model.CATALOG_PREFIX)
        _address(document.get("right_catalog_address"), "right catalog address", diff_model.catalog_model.CATALOG_PREFIX)
        catalog_addresses = True
    except (ValidationError, KeyError, TypeError, ValueError):
        catalog_addresses = False

    label_union = status_conservation = entry_field_conservation = denominator_conservation = delta_conservation = entry_addresses = aggregate_state = content_address = mapping_round_trip = False
    if typed is not None:
        left_labels = {item.left_entry.label for item in typed.items if item.left_entry is not None}
        right_labels = {item.right_entry.label for item in typed.items if item.right_entry is not None}
        item_labels = {item.label for item in typed.items}
        label_union = item_labels == left_labels | right_labels and all(item.label == (item.left_entry.label if item.left_entry is not None else item.right_entry.label) for item in typed.items)
        status_conservation = all(item.status in diff_model.STATUSES and item.status == ("added" if item.left_entry is None else "removed" if item.right_entry is None else "changed" if item.changed_fields else "unchanged") for item in typed.items)
        entry_field_conservation = all(tuple(item.changed_fields) == _field_changes(item) for item in typed.items)
        denominator_conservation = typed.left_entry_count == typed.left_accepted_count + typed.left_rejected_count and typed.right_entry_count == typed.right_accepted_count + typed.right_rejected_count and typed.left_artifact_count == typed.left_entry_count * len(diff_model.catalog_model.bundle_model.ARTIFACT_FILES) and typed.right_artifact_count == typed.right_entry_count * len(diff_model.catalog_model.bundle_model.ARTIFACT_FILES)
        delta_conservation = typed.entry_count_delta == typed.right_entry_count - typed.left_entry_count and typed.accepted_count_delta == sum(item.accepted_delta for item in typed.items) and typed.ready_count_delta == sum(item.ready_delta for item in typed.items) and typed.artifact_count_delta == sum(item.artifact_count_delta for item in typed.items) and typed.rejected_count_delta == typed.right_rejected_count - typed.left_rejected_count
        entry_addresses = all(diff_model.address_entry_diff(item) == item.content_address for item in typed.items)
        aggregate_state = typed.state == diff_model._state(typed.added_count, typed.removed_count, typed.changed_count)
        content_address = diff_model.address_diff(typed) == typed.content_address
        try:
            mapping_round_trip = diff_model.diff_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip = False

    checks = (
        _check("exact-fields", exact_fields, "diff document contains exactly the declared public fields", diff_address),
        _check("public-boundary", public_boundary, "diff document contains no private, path, or attribution metadata", diff_address),
        _check("catalog-addresses", catalog_addresses, "both source catalog addresses use the catalog namespace", diff_address),
        _check("label-union", label_union, "entry labels conserve the union of left and right snapshot labels", diff_address),
        _check("status-conservation", status_conservation, "each entry status is derived from left and right presence", diff_address),
        _check("entry-field-conservation", entry_field_conservation, "paired entry changed fields derive from public receipt fields", diff_address),
        _check("denominator-conservation", denominator_conservation, "catalog entry, acceptance, rejection, and artifact totals reconcile", diff_address),
        _check("delta-conservation", delta_conservation, "aggregate deltas equal the sum of entry transitions", diff_address),
        _check("entry-addresses", entry_addresses, "every nested entry diff content address reproduces", diff_address),
        _check("aggregate-state", aggregate_state, "aggregate diff state derives from status counts", diff_address),
        _check("content-address", content_address, "diff content address reproduces from its public projection", diff_address),
        _check("mapping-round-trip", mapping_round_trip, "typed public mapping rehydrates without projection drift", diff_address),
    )
    complete = all(check.passed for check in checks)
    body = {"diff_address": diff_address, "left_catalog_address": left_catalog_address, "right_catalog_address": right_catalog_address, "state": "complete" if complete else "incomplete", "complete": complete, "accepted": complete, "checks": checks}
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit(**body, content_address="pending:observability-bundle-catalog-diff-audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit(**body, content_address=address_audit(provisional))


def audit_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit:
    if not isinstance(value, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff):
        raise ValidationError("observability bundle catalog diff audit requires a typed diff")
    diff_model.verify_diff(value)
    return _audit_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit:
    value = _mapping(value, "observability bundle catalog diff audit input")
    if "diff_address" in value and "checks" in value:
        _strict(value, set(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit.FIELDS), "observability bundle catalog diff audit")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle catalog diff audit checks", MAX_CHECKS))
        result = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit(value["diff_address"], value["left_catalog_address"], value["right_catalog_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("observability bundle catalog diff audit counts do not reconcile")
        return result
    return _audit_mapping(value)


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit):
        raise ValidationError("observability bundle catalog diff audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("observability bundle catalog diff audit content address does not replay")
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Diff Audit", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Diff: `{value.diff_address}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "left_catalog_address": {"type": "string", "pattern": "^" + diff_model.catalog_model.CATALOG_PREFIX + ":"}, "right_catalog_address": {"type": "string", "pattern": "^" + diff_model.catalog_model.CATALOG_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_items": diff_model.MAX_ITEMS}, "features": ("fixed catalog-diff assurance checks", "public namespace validation", "label-union and status conservation", "semantic field conservation", "acceptance readiness rejection and artifact delta conservation", "nested address replay", "aggregate-state replay", "incomplete tamper diagnostics", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "EXPECTED_FIELDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditCheck",
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

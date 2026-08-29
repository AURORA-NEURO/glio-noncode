"""Independent audit of release-evidence observability-bundle diffs.

The diff boundary is fail-fast for typed callers.  This companion boundary
also accepts a public mapping and returns a fixed, independently addressed
diagnostic report, preserving useful check failures when a copied diff is
malformed or relinked.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle as bundle_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff as diff_model
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
    "action-conservation",
    "field-conservation",
    "count-conservation",
    "bundle-field-conservation",
    "aggregate-state",
    "item-addresses",
    "content-address",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff.FIELDS


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
        return _address(value, "evidence address", prefix)
    except ValidationError:
        return fallback


def _typed(value: Mapping[str, Any]) -> diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff | None:
    try:
        return diff_model.diff_from_mapping(value)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck:
    """One independently addressed assertion over a handoff diff."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "release evidence observability bundle diff audit check ID", 128)
        self.passed = _bool(passed, "release evidence observability bundle diff audit check passed")
        self.detail = _text(detail, "release evidence observability bundle diff audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "release evidence observability bundle diff audit evidence address", 2048)
        self.content_address = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=AUDIT_CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck:
        value = _mapping(value, "release evidence observability bundle diff audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "release evidence observability bundle diff audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("release evidence observability bundle diff audit check content address mismatch")
        return result


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit:
    """Complete or incomplete public audit of an observability-bundle diff."""

    def __init__(self, diff_address: str, baseline_address: str, candidate_address: str, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck], content_address: str) -> None:
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
        _address(self.diff_address, "release evidence observability bundle diff audit diff address", diff_model.DIFF_PREFIX)
        _address(self.baseline_address, "release evidence observability bundle diff audit baseline address", bundle_model.BUNDLE_PREFIX)
        _address(self.candidate_address, "release evidence observability bundle diff audit candidate address", bundle_model.BUNDLE_PREFIX)
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("release evidence observability bundle diff audit state does not match completion")
        _bool(self.complete, "release evidence observability bundle diff audit complete")
        _bool(self.accepted, "release evidence observability bundle diff audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("release evidence observability bundle diff audit check set is invalid")
        _count(self.passed_count, "release evidence observability bundle diff audit passed count", MAX_CHECKS)
        _count(self.failed_count, "release evidence observability bundle diff audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("release evidence observability bundle diff audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("release evidence observability bundle diff audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability bundle diff audit content address")
        else:
            _address(self.content_address, "release evidence observability bundle diff audit content address", AUDIT_PREFIX)
        if not diff_model._public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("release evidence observability bundle diff audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("diff_address", "baseline_address", "candidate_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit):
        raise ValidationError("release evidence observability bundle diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck(check_id, passed, detail, evidence)


def _projection(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff, *, baseline: bool) -> dict[str, Any]:
    return value._projection(baseline)


def _audit_mapping(document: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit:
    fallback_diff = diff_model.DIFF_PREFIX + ":unresolved"
    fallback_bundle = bundle_model.BUNDLE_PREFIX + ":unresolved"
    diff_address = _safe_address(document.get("content_address"), diff_model.DIFF_PREFIX, fallback_diff)
    baseline_address = _safe_address(document.get("baseline_address"), bundle_model.BUNDLE_PREFIX, fallback_bundle)
    candidate_address = _safe_address(document.get("candidate_address"), bundle_model.BUNDLE_PREFIX, fallback_bundle)
    typed = _typed(document)
    if typed is not None:
        diff_address = typed.content_address
        baseline_address = typed.baseline_address
        candidate_address = typed.candidate_address

    exact_fields = set(document) == set(EXPECTED_FIELDS)
    public_boundary = diff_model._public(document)
    source_addresses = False
    try:
        for field, prefix in (("baseline_address", bundle_model.BUNDLE_PREFIX), ("candidate_address", bundle_model.BUNDLE_PREFIX), ("baseline_manifest_address", bundle_model.MANIFEST_PREFIX), ("candidate_manifest_address", bundle_model.MANIFEST_PREFIX), ("baseline_pipeline_address", bundle_model.pipeline_model.PIPELINE_PREFIX), ("candidate_pipeline_address", bundle_model.pipeline_model.PIPELINE_PREFIX), ("baseline_observability_address", bundle_model.observability_model.OBSERVABILITY_PREFIX), ("candidate_observability_address", bundle_model.observability_model.OBSERVABILITY_PREFIX), ("baseline_audit_address", bundle_model.audit_model.AUDIT_PREFIX), ("candidate_audit_address", bundle_model.audit_model.AUDIT_PREFIX)):
            _address(document.get(field), field, prefix)
        for field in ("baseline_query_addresses", "candidate_query_addresses"):
            values = _sequence(document.get(field), field, len(bundle_model.QUERY_ARTIFACTS))
            if len(values) != len(bundle_model.QUERY_ARTIFACTS):
                raise ValidationError("query address count is invalid")
            for value, prefix in zip(values, diff_model.QUERY_PREFIXES, strict=True):
                _address(value, field, prefix)
        source_addresses = True
    except (ValidationError, KeyError, TypeError, ValueError):
        source_addresses = False

    item_identities = action_conservation = field_conservation = count_conservation = bundle_field_conservation = aggregate_state = item_addresses = content_address = mapping_round_trip = False
    if typed is not None:
        item_identities = tuple(item.ordinal for item in typed.items) == tuple(range(1, typed.item_count + 1)) and tuple(item.name for item in typed.items) == bundle_model.FILES and len({item.name for item in typed.items}) == typed.item_count and len({item.content_address for item in typed.items}) == typed.item_count
        action_conservation = all(item.action in diff_model.ACTIONS and item.action == ("changed" if item.changed_fields else "unchanged") for item in typed.items)
        before = _projection(typed, baseline=True)
        after = _projection(typed, baseline=False)
        field_conservation = tuple(field for field in diff_model.BUNDLE_FIELDS if before[field] != after[field]) == tuple(typed.changed_fields)
        count_conservation = typed.item_count == len(typed.items) and typed.changed_count + typed.unchanged_count == typed.item_count and typed.changed_count == sum(item.action == "changed" for item in typed.items) and typed.unchanged_count == sum(item.action == "unchanged" for item in typed.items)
        bundle_field_conservation = typed.baseline_artifact_count == len(bundle_model.ARTIFACT_FILES) and typed.candidate_artifact_count == len(bundle_model.ARTIFACT_FILES) and len(typed.baseline_query_addresses) == len(bundle_model.QUERY_ARTIFACTS) and len(typed.candidate_query_addresses) == len(bundle_model.QUERY_ARTIFACTS)
        aggregate_state = typed.state == diff_model._aggregate_state(before, after, bool(typed.changed_fields) or typed.changed_count > 0)
        item_addresses = all(diff_model.address_diff_item(item) == item.content_address for item in typed.items)
        content_address = diff_model.address_diff(typed) == typed.content_address
        try:
            mapping_round_trip = diff_model.diff_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip = False

    checks = (
        _check("exact-fields", exact_fields, "diff document contains exactly the declared public fields", diff_address),
        _check("public-boundary", public_boundary, "diff document contains no private, path, or attribution metadata", diff_address),
        _check("source-addresses", source_addresses, "bundle, manifest, pipeline, observability, audit, and query addresses use public namespaces", diff_address),
        _check("item-identities", item_identities, "file ordinals, names, and nested addresses are ordered and unique", diff_address),
        _check("action-conservation", action_conservation, "each file action conserves its changed-field evidence", diff_address),
        _check("field-conservation", field_conservation, "semantic changed fields derive from baseline and candidate receipts", diff_address),
        _check("count-conservation", count_conservation, "changed and unchanged counts conserve the nine-file set", diff_address),
        _check("bundle-field-conservation", bundle_field_conservation, "artifact and query counts preserve the observability handoff contract", diff_address),
        _check("aggregate-state", aggregate_state, "aggregate diff state derives from all source posture fields", diff_address),
        _check("item-addresses", item_addresses, "every nested file diff address reproduces", diff_address),
        _check("content-address", content_address, "diff content address reproduces from its public projection", diff_address),
        _check("mapping-round-trip", mapping_round_trip, "typed public mapping rehydrates without projection drift", diff_address),
    )
    complete = all(check.passed for check in checks)
    body = {"diff_address": diff_address, "baseline_address": baseline_address, "candidate_address": candidate_address, "state": "complete" if complete else "incomplete", "complete": complete, "accepted": complete, "checks": checks}
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit(**body, content_address="pending:audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit(**body, content_address=address_audit(provisional))


def audit_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit:
    if not isinstance(value, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff):
        raise ValidationError("release evidence observability bundle diff audit requires a typed diff")
    diff_model.verify_diff(value)
    return _audit_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit:
    value = _mapping(value, "release evidence observability bundle diff audit input")
    audit_fields = {"diff_address", "baseline_address", "candidate_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address"}
    if "diff_address" in value and "checks" in value:
        _strict(value, audit_fields, "release evidence observability bundle diff audit")
        raw_checks = value["checks"]
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck.from_mapping(item) for item in (raw_checks.values() if isinstance(raw_checks, Mapping) else _sequence(raw_checks, "release evidence observability bundle diff audit checks", MAX_CHECKS)))
        return RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit(value["diff_address"], value["baseline_address"], value["candidate_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
    return _audit_mapping(value)


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit):
        raise ValidationError("release evidence observability bundle diff audit verification requires a typed audit")
    value._validate()
    return value


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit) -> str:
    verify_audit(value)
    lines = ["# Assurance History Observatory Release Evidence Observability Bundle Diff Audit", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Diff: `{value.diff_address}`", f"- Baseline: `{value.baseline_address}`", f"- Candidate: `{value.candidate_address}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "baseline_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "candidate_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_items": diff_model.MAX_ITEMS, "max_artifact_bytes": bundle_model.MAX_ARTIFACT_BYTES}, "features": ("public observability-bundle diff mapping audit", "fixed structural check set", "bundle and nested namespace validation", "semantic receipt field conservation", "file action and byte conservation", "pipeline observability and audit aggregate-state replay", "nested item address replay", "content-address replay", "incomplete tamper diagnostics", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "EXPECTED_FIELDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck",
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

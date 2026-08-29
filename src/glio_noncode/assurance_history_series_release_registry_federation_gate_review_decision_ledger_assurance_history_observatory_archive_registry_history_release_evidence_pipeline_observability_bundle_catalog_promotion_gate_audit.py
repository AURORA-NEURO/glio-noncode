"""Independent assurance checks for catalog-promotion decisions.

The promotion gate is a composed decision document.  This module replays the
decision from its public projection and checks that the policy, input
addresses, fifteen gate assertions, counters, and ready/held/blocked state
remain internally consistent.  It deliberately treats malformed gate
documents as evidence: an incomplete audit is returned instead of allowing a
serialization error to hide the failing boundary.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-audit-v1"
BOUNDARY = gate_model.BOUNDARY + "_audit"
AUDIT_PREFIX = gate_model.GATE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "policy-address",
    "input-addresses",
    "check-set",
    "severity-conservation",
    "decision-conservation",
    "budget-observations",
    "count-conservation",
    "check-addresses",
    "content-address",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate.FIELDS


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} has an invalid public namespace")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return gate_model._public(value)


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "promotion gate audit evidence address", prefix)
    except (ValidationError, TypeError, ValueError):
        return fallback


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck:
    """One fixed promotion-gate invariant with addressed evidence."""

    FIELDS = ("check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "observability bundle catalog promotion gate audit check ID", 64)
        self.passed = _bool(passed, "observability bundle catalog promotion gate audit check passed")
        self.detail = _text(detail, "observability bundle catalog promotion gate audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "observability bundle catalog promotion gate audit evidence address", 2048)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observability bundle catalog promotion gate audit check ID is unsupported")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion gate audit check content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion gate audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion gate audit check address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck:
        value = _mapping(value, "observability bundle catalog promotion gate audit check")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion gate audit check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion gate audit check is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck):
        raise ValidationError("observability bundle catalog promotion gate audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit:
    """Addressed, independent assurance for a promotion gate."""

    FIELDS = ("gate_address", "diff_address", "report_address", "policy_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address")

    def __init__(self, gate_address: str, diff_address: str, report_address: str, policy_address: str, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck], content_address: str) -> None:
        self.gate_address = _address(gate_address, "observability bundle catalog promotion gate audit gate address", gate_model.GATE_PREFIX)
        self.diff_address = _address(diff_address, "observability bundle catalog promotion gate audit diff address", gate_model.diff_model.DIFF_PREFIX)
        self.report_address = _address(report_address, "observability bundle catalog promotion gate audit report address", gate_model.report_model.REPORT_PREFIX)
        self.policy_address = _address(policy_address, "observability bundle catalog promotion gate audit policy address", gate_model.POLICY_PREFIX)
        self.state = _text(state, "observability bundle catalog promotion gate audit state", 32)
        self.complete = _bool(complete, "observability bundle catalog promotion gate audit complete")
        self.accepted = _bool(accepted, "observability bundle catalog promotion gate audit accepted")
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck) for check in self.checks):
            raise ValidationError("observability bundle catalog promotion gate audit checks are not canonical")
        if self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != MAX_CHECKS:
            raise ValidationError("observability bundle catalog promotion gate audit check counts are not conserved")
        if self.state not in STATES or self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("observability bundle catalog promotion gate audit state is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion gate audit content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion gate audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion gate audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "diff_address": self.diff_address, "report_address": self.report_address, "policy_address": self.policy_address, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit:
        value = _mapping(value, "observability bundle catalog promotion gate audit")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion gate audit")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion gate audit is missing fields: {missing}")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle catalog promotion gate audit checks", MAX_CHECKS))
        result = cls(value["gate_address"], value["diff_address"], value["report_address"], value["policy_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("observability bundle catalog promotion gate audit counts do not reconcile")
        return result


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit):
        raise ValidationError("observability bundle catalog promotion gate audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck(check_id, passed, detail, evidence_address, "pending:observability-bundle-catalog-promotion-gate-audit-check")


def _typed(document: Mapping[str, Any]) -> gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate | None:
    try:
        return gate_model.gate_from_mapping(document)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def _audit_mapping(document: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit:
    fallback_gate = gate_model.GATE_PREFIX + ":unresolved"
    fallback_diff = gate_model.diff_model.DIFF_PREFIX + ":unresolved"
    fallback_report = gate_model.report_model.REPORT_PREFIX + ":unresolved"
    fallback_policy = gate_model.POLICY_PREFIX + ":unresolved"
    gate_address = _safe_address(document.get("content_address"), gate_model.GATE_PREFIX, fallback_gate)
    diff_address = _safe_address(document.get("diff_address"), gate_model.diff_model.DIFF_PREFIX, fallback_diff)
    report_address = _safe_address(document.get("report_address"), gate_model.report_model.REPORT_PREFIX, fallback_report)
    policy_address = _safe_address(document.get("policy_address"), gate_model.POLICY_PREFIX, fallback_policy)
    typed = _typed(document)
    if typed is not None:
        gate_address, diff_address, report_address, policy_address = typed.content_address, typed.diff_address, typed.report_address, typed.policy_address
    exact_fields = set(document) == set(EXPECTED_FIELDS)
    public_boundary = _public(document)
    policy_replays = input_addresses = check_set = severity_conservation = decision_conservation = budget_observations = count_conservation = check_addresses = content_address = mapping_round_trip = False
    if typed is not None:
        policy_replays = gate_model.address_policy(typed.policy) == typed.policy_address
        input_addresses = all(
            (
                gate_model._address(typed.diff_address, "diff address", gate_model.diff_model.DIFF_PREFIX),
                gate_model._address(typed.diff_audit_address, "diff audit address", gate_model.diff_audit_model.AUDIT_PREFIX),
                gate_model._address(typed.report_address, "report address", gate_model.report_model.REPORT_PREFIX),
                gate_model._address(typed.report_audit_address, "report audit address", gate_model.report_audit_model.AUDIT_PREFIX),
                gate_model._address(typed.policy_address, "policy address", gate_model.POLICY_PREFIX),
            )
        )
        check_set = tuple(check.check_id for check in typed.checks) == gate_model.CHECK_IDS and len(typed.checks) == gate_model.MAX_CHECKS
        severity_conservation = typed.passed_count + typed.failed_count == typed.check_count and typed.blocking_failure_count + typed.hold_failure_count == typed.failed_count
        expected_state = "blocked" if typed.blocking_failure_count else "held" if typed.hold_failure_count else "ready"
        decision_conservation = typed.state == expected_state and typed.accepted == (typed.state != "blocked") and typed.release_ready == (typed.state == "ready")
        budget_observations = (
            typed.added_count <= gate_model.diff_model.MAX_ITEMS
            and typed.removed_count <= gate_model.diff_model.MAX_ITEMS
            and typed.changed_count <= gate_model.diff_model.MAX_ITEMS
            and abs(typed.accepted_delta) <= gate_model.report_model.MAX_ROWS
            and abs(typed.ready_delta) <= gate_model.report_model.MAX_ROWS
        )
        count_conservation = (
            typed.candidate_accepted_count + typed.candidate_rejected_count == typed.candidate_entry_count
            and typed.candidate_ready_count <= typed.candidate_accepted_count
            and typed.check_count == gate_model.MAX_CHECKS
        )
        check_addresses = all(gate_model.address_check(check) == check.content_address for check in typed.checks)
        content_address = gate_model.address_gate(typed) == typed.content_address
        try:
            mapping_round_trip = gate_model.gate_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            pass
    checks = (
        _check("exact-fields", exact_fields, "gate document contains exactly the declared public fields", gate_address),
        _check("public-boundary", public_boundary, "gate document contains no private, path, or attribution metadata", gate_address),
        _check("policy-address", policy_replays, "embedded promotion policy address reproduces", policy_address),
        _check("input-addresses", input_addresses, "all composed input addresses use their declared public namespaces", gate_address),
        _check("check-set", check_set, "gate contains the canonical fifteen-check assertion set", gate_address),
        _check("severity-conservation", severity_conservation, "passed, failed, blocking, and hold counts reconcile", gate_address),
        _check("decision-conservation", decision_conservation, "ready, held, blocked, accepted, and release-ready state derive from failures", gate_address),
        _check("budget-observations", budget_observations, "transition counts and regression deltas remain bounded", gate_address),
        _check("count-conservation", count_conservation, "candidate and check counters reconcile", gate_address),
        _check("check-addresses", check_addresses, "every nested gate check address reproduces", gate_address),
        _check("content-address", content_address, "gate content address reproduces from its public projection", gate_address),
        _check("mapping-round-trip", mapping_round_trip, "typed gate mapping rehydrates without drift", gate_address),
    )
    complete = all(check.passed for check in checks)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit(gate_address, diff_address, report_address, policy_address, "complete" if complete else "incomplete", complete, complete, checks, "pending:observability-bundle-catalog-promotion-gate-audit")
    addressed_checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck(check.check_id, check.passed, check.detail, check.evidence_address, address_check(check)) for check in provisional.checks)
    final = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit(gate_address, diff_address, report_address, policy_address, provisional.state, provisional.complete, provisional.accepted, addressed_checks, "pending:observability-bundle-catalog-promotion-gate-audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit(final.gate_address, final.diff_address, final.report_address, final.policy_address, final.state, final.complete, final.accepted, final.checks, address_audit(final))


def audit_gate(value: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit:
    if not isinstance(value, gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate):
        raise ValidationError("observability bundle catalog promotion gate audit requires a typed gate")
    gate_model.verify_gate(value)
    return _audit_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit:
    value = _mapping(value, "observability bundle catalog promotion gate audit input")
    if "gate_address" in value and "checks" in value:
        return verify_audit(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit.from_mapping(value))
    return _audit_mapping(value)


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit):
        raise ValidationError("observability bundle catalog promotion gate audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion gate audit content address does not replay")
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit) -> str:
    value = verify_audit(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Promotion Gate Audit", "", f"- State: `{value.state}`", f"- Complete: `{value.complete}`", f"- Passed: `{value.passed_count}`", f"- Failed: `{value.failed_count}`", f"- Gate: `{value.gate_address}`", f"- Content address: `{value.content_address}`", "", "| check | passed | detail | evidence |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{check.passed}` | {check.detail} | `{check.evidence_address}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit.FIELDS), "properties": {"gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "diff_address": {"type": "string", "pattern": "^" + gate_model.diff_model.DIFF_PREFIX + ":"}, "report_address": {"type": "string", "pattern": "^" + gate_model.report_model.REPORT_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + gate_model.POLICY_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS}, "features": ("fixed composed-gate assurance checks", "policy and input address replay", "decision and severity conservation", "bounded transition and regression observations", "nested check address replay", "failure-visible tamper diagnostics", "content-address replay", "mapping round-trip", "path-free JSON and Markdown output"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "EXPECTED_FIELDS", "MAX_CHECKS", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAuditCheck",
    "address_audit", "address_check", "audit_from_mapping", "audit_gate", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit",
]

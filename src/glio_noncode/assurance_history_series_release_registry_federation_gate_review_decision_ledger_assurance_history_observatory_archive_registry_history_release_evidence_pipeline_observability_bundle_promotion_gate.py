"""Policy-governed promotion decisions for observability handoff revisions.

The persisted observability bundle diff answers what changed.  This boundary
answers whether the candidate may be promoted under an explicit public policy.
It reloads the typed diff audit, evaluates every policy assertion, and emits a
path-free addressed decision with distinct ``ready``, ``held``, and ``blocked``
states.  Policy failures are holds; integrity, acceptance, or address failures
are blocking failures.  No decision mutates either handoff.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff as diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_audit as diff_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_audit_model.VERSION + "-promotion-gate-v1"
BOUNDARY = diff_audit_model.BOUNDARY + "_promotion_gate"
GATE_PREFIX = diff_model.DIFF_PREFIX + "-promotion-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
CHECK_PREFIX = GATE_PREFIX + "-check"
DEFAULT_POLICY_ID = "glio-noncode-observability-bundle-promotion-policy"
DEFAULT_ALLOWED_DIFF_STATES = ("unchanged", "improved")
DEFAULT_MAX_CHANGED_ITEMS = diff_model.MAX_ITEMS
DEFAULT_MAX_CHANGED_FIELDS = len(diff_model.BUNDLE_FIELDS)
STATES = ("ready", "held", "blocked")
SEVERITIES = ("hold", "blocking")
CHECK_IDS = (
    "baseline-accepted",
    "candidate-accepted",
    "candidate-audit-complete",
    "candidate-ready",
    "diff-audit-complete",
    "transition-state",
    "changed-artifact-budget",
    "semantic-field-budget",
    "byte-receipt-conservation",
    "public-boundary",
    "content-address",
)
MAX_CHECKS = len(CHECK_IDS)
BLOCKING_CHECK_IDS = frozenset(
    {
        "baseline-accepted",
        "candidate-accepted",
        "candidate-audit-complete",
        "candidate-ready",
        "diff-audit-complete",
        "byte-receipt-conservation",
        "public-boundary",
        "content-address",
    }
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


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} has an invalid public namespace")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
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
    return diff_model._public(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _states(value: Any) -> tuple[str, ...]:
    values = _sequence(value, "observability bundle promotion policy allowed diff states", len(diff_model.STATES))
    if not values:
        raise ValidationError("observability bundle promotion policy allowed diff states cannot be empty")
    normalized = tuple(_text(item, "observability bundle promotion policy diff state", 32) for item in values)
    if any(item not in diff_model.STATES for item in normalized):
        raise ValidationError("observability bundle promotion policy diff state is unsupported")
    if len(set(normalized)) != len(normalized) or tuple(item for item in diff_model.STATES if item in normalized) != normalized:
        raise ValidationError("observability bundle promotion policy diff states must use canonical order")
    return normalized


class RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy:
    """Public requirements and budgets for promoting a candidate handoff."""

    FIELDS = (
        "policy_id",
        "require_baseline_accepted",
        "require_candidate_accepted",
        "require_candidate_audit_complete",
        "require_candidate_ready",
        "require_diff_audit_complete",
        "allowed_diff_states",
        "max_changed_items",
        "max_changed_fields",
    )

    def __init__(
        self,
        policy_id: str = DEFAULT_POLICY_ID,
        require_baseline_accepted: bool = True,
        require_candidate_accepted: bool = True,
        require_candidate_audit_complete: bool = True,
        require_candidate_ready: bool = True,
        require_diff_audit_complete: bool = True,
        allowed_diff_states: Sequence[str] = DEFAULT_ALLOWED_DIFF_STATES,
        max_changed_items: int = DEFAULT_MAX_CHANGED_ITEMS,
        max_changed_fields: int = DEFAULT_MAX_CHANGED_FIELDS,
    ) -> None:
        self.policy_id = _text(policy_id, "observability bundle promotion policy ID", 128)
        self.require_baseline_accepted = _bool(require_baseline_accepted, "observability bundle promotion baseline requirement")
        self.require_candidate_accepted = _bool(require_candidate_accepted, "observability bundle promotion candidate requirement")
        self.require_candidate_audit_complete = _bool(require_candidate_audit_complete, "observability bundle promotion candidate audit requirement")
        self.require_candidate_ready = _bool(require_candidate_ready, "observability bundle promotion candidate readiness requirement")
        self.require_diff_audit_complete = _bool(require_diff_audit_complete, "observability bundle promotion diff audit requirement")
        self.allowed_diff_states = _states(allowed_diff_states)
        self.max_changed_items = _count(max_changed_items, "observability bundle promotion changed-item budget", diff_model.MAX_ITEMS)
        self.max_changed_fields = _count(max_changed_fields, "observability bundle promotion changed-field budget", len(diff_model.BUNDLE_FIELDS))
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle promotion policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "require_baseline_accepted": self.require_baseline_accepted,
            "require_candidate_accepted": self.require_candidate_accepted,
            "require_candidate_audit_complete": self.require_candidate_audit_complete,
            "require_candidate_ready": self.require_candidate_ready,
            "require_diff_audit_complete": self.require_diff_audit_complete,
            "allowed_diff_states": self.allowed_diff_states,
            "max_changed_items": self.max_changed_items,
            "max_changed_fields": self.max_changed_fields,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy:
        value = _mapping(value, "observability bundle promotion policy")
        _strict(value, set(cls().to_dict()), "observability bundle promotion policy")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle promotion policy is missing fields: {missing}")
        return cls(**value)


def address_policy(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy):
        raise ValidationError("observability bundle promotion policy address requires a typed policy")
    return content_hash(value.to_dict(), prefix=POLICY_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck:
    """One policy assertion and its addressed evidence."""

    FIELDS = ("check_id", "passed", "severity", "detail", "observed", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, severity: str, detail: str, observed: Mapping[str, Any], evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "observability bundle promotion check ID", 128)
        self.passed = _bool(passed, "observability bundle promotion check passed")
        self.severity = _text(severity, "observability bundle promotion check severity", 32)
        if self.severity not in SEVERITIES:
            raise ValidationError("observability bundle promotion check severity is invalid")
        self.detail = _text(detail, "observability bundle promotion check detail", 1024)
        self.observed = _json_value(dict(_mapping(observed, "observability bundle promotion observed values")))
        self.evidence_address = _address(evidence_address, "observability bundle promotion check evidence address")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle promotion check content address")
        else:
            _address(self.content_address, "observability bundle promotion check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("observability bundle promotion check address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "severity": self.severity, "detail": self.detail, "observed": self.observed, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck:
        value = _mapping(value, "observability bundle promotion check")
        _strict(value, set(cls.FIELDS), "observability bundle promotion check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle promotion check is missing fields: {missing}")
        return cls(value["check_id"], value["passed"], value["severity"], value["detail"], value["observed"], value["evidence_address"], value["content_address"])


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck):
        raise ValidationError("observability bundle promotion check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
    """An addressed ready, held, or blocked promotion decision."""

    FIELDS = (
        "gate_id",
        "baseline_address",
        "candidate_address",
        "diff_address",
        "diff_audit_address",
        "policy_address",
        "policy",
        "state",
        "accepted",
        "release_ready",
        "check_count",
        "passed_count",
        "failed_count",
        "blocking_failure_count",
        "hold_failure_count",
        "checks",
        "content_address",
    )

    def __init__(self, gate_id: str, baseline_address: str, candidate_address: str, diff_address: str, diff_audit_address: str, policy_address: str, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy, state: str, accepted: bool, release_ready: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck], content_address: str) -> None:
        self.gate_id = _text(gate_id, "observability bundle promotion gate ID", 128)
        self.baseline_address = _address(baseline_address, "observability bundle promotion baseline address", diff_model.bundle_model.BUNDLE_PREFIX)
        self.candidate_address = _address(candidate_address, "observability bundle promotion candidate address", diff_model.bundle_model.BUNDLE_PREFIX)
        self.diff_address = _address(diff_address, "observability bundle promotion diff address", diff_model.DIFF_PREFIX)
        self.diff_audit_address = _address(diff_audit_address, "observability bundle promotion diff audit address", diff_audit_model.AUDIT_PREFIX)
        self.policy_address = _address(policy_address, "observability bundle promotion policy address", POLICY_PREFIX)
        self.policy = policy
        self.state = _text(state, "observability bundle promotion state", 32)
        self.accepted = _bool(accepted, "observability bundle promotion accepted")
        self.release_ready = _bool(release_ready, "observability bundle promotion release-ready")
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.blocking_failure_count = sum(not check.passed and check.severity == "blocking" for check in self.checks)
        self.hold_failure_count = sum(not check.passed and check.severity == "hold" for check in self.checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.policy, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy):
            raise ValidationError("observability bundle promotion policy must be typed")
        if address_policy(self.policy) != self.policy_address:
            raise ValidationError("observability bundle promotion policy address does not reproduce")
        if self.state not in STATES:
            raise ValidationError("observability bundle promotion state is invalid")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("observability bundle promotion check set is invalid")
        if any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck) for check in self.checks):
            raise ValidationError("observability bundle promotion checks must be typed")
        _count(self.passed_count, "observability bundle promotion passed count", MAX_CHECKS)
        _count(self.failed_count, "observability bundle promotion failed count", MAX_CHECKS)
        _count(self.blocking_failure_count, "observability bundle promotion blocking failure count", MAX_CHECKS)
        _count(self.hold_failure_count, "observability bundle promotion hold failure count", MAX_CHECKS)
        if self.passed_count + self.failed_count != MAX_CHECKS or self.blocking_failure_count + self.hold_failure_count != self.failed_count:
            raise ValidationError("observability bundle promotion check counts are not conserved")
        expected_state = "blocked" if self.blocking_failure_count else "held" if self.hold_failure_count else "ready"
        if self.state != expected_state or self.accepted != (self.state != "blocked") or self.release_ready != (self.state == "ready"):
            raise ValidationError("observability bundle promotion decision is not derived from checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle promotion content address")
        else:
            _address(self.content_address, "observability bundle promotion content address", GATE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_gate(self) != self.content_address):
            raise ValidationError("observability bundle promotion gate address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "diff_address": self.diff_address, "diff_audit_address": self.diff_audit_address, "policy_address": self.policy_address, "policy": self.policy.to_dict(), "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "blocking_failure_count": self.blocking_failure_count, "hold_failure_count": self.hold_failure_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("gate_id", "baseline_address", "candidate_address", "diff_address", "diff_audit_address", "policy_address", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "blocking_failure_count", "hold_failure_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
        value = _mapping(value, "observability bundle promotion gate")
        _strict(value, set(cls.FIELDS), "observability bundle promotion gate")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle promotion gate is missing fields: {missing}")
        policy = RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy.from_mapping(value["policy"] if "policy" in value else {})
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle promotion checks", MAX_CHECKS))
        return cls(value["gate_id"], value["baseline_address"], value["candidate_address"], value["diff_address"], value["diff_audit_address"], value["policy_address"], policy, value["state"], value["accepted"], value["release_ready"], checks, value["content_address"])


DEFAULT_GATE_ID = "glio-noncode-observability-bundle-promotion-gate"


def address_gate(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate):
        raise ValidationError("observability bundle promotion gate address requires a typed gate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def _check(detail: str, check_id: str, passed: bool, observed: Mapping[str, Any], evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck:
    severity = "blocking" if check_id in BLOCKING_CHECK_IDS else "hold"
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck(check_id, passed, severity, detail, observed, evidence_address, "pending:observability-bundle-promotion-check")


def _audit_passed(audit: diff_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit, check_id: str) -> bool:
    return next(check.passed for check in audit.checks if check.check_id == check_id)


def _build_gate(diff: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff, audit: diff_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy, gate_id: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
    checks = (
        _check("baseline pipeline and audit acceptance satisfy the promotion prerequisite" if diff.baseline_pipeline_accepted and diff.baseline_audit_accepted else "baseline pipeline or audit acceptance is missing", "baseline-accepted", (not policy.require_baseline_accepted) or (diff.baseline_pipeline_accepted and diff.baseline_audit_accepted), {"required": policy.require_baseline_accepted, "pipeline_accepted": diff.baseline_pipeline_accepted, "audit_accepted": diff.baseline_audit_accepted}, diff.baseline_address),
        _check("candidate pipeline and audit acceptance satisfy the promotion prerequisite" if diff.candidate_pipeline_accepted and diff.candidate_audit_accepted else "candidate pipeline or audit acceptance is missing", "candidate-accepted", (not policy.require_candidate_accepted) or (diff.candidate_pipeline_accepted and diff.candidate_audit_accepted), {"required": policy.require_candidate_accepted, "pipeline_accepted": diff.candidate_pipeline_accepted, "audit_accepted": diff.candidate_audit_accepted}, diff.candidate_address),
        _check("candidate audit is complete and accepted" if diff.candidate_audit_state == "complete" and diff.candidate_audit_accepted else "candidate audit is incomplete or rejected", "candidate-audit-complete", (not policy.require_candidate_audit_complete) or (diff.candidate_audit_state == "complete" and diff.candidate_audit_accepted), {"required": policy.require_candidate_audit_complete, "state": diff.candidate_audit_state, "accepted": diff.candidate_audit_accepted}, diff.candidate_address),
        _check("candidate pipeline and observability projection are ready" if diff.candidate_pipeline_state == "ready" and diff.candidate_observability_state == "ready" else "candidate pipeline or observability projection is not ready", "candidate-ready", (not policy.require_candidate_ready) or (diff.candidate_pipeline_state == "ready" and diff.candidate_observability_state == "ready"), {"required": policy.require_candidate_ready, "pipeline_state": diff.candidate_pipeline_state, "observability_state": diff.candidate_observability_state}, diff.candidate_address),
        _check("independent diff audit is complete and accepted" if audit.state == "complete" and audit.accepted else "independent diff audit is incomplete or rejected", "diff-audit-complete", (not policy.require_diff_audit_complete) or (audit.state == "complete" and audit.accepted), {"required": policy.require_diff_audit_complete, "state": audit.state, "accepted": audit.accepted}, audit.content_address),
        _check("diff state is allowed by policy" if diff.state in policy.allowed_diff_states else "diff state is not allowed by policy", "transition-state", diff.state in policy.allowed_diff_states, {"observed": diff.state, "allowed": policy.allowed_diff_states}, diff.content_address),
        _check("changed artifact count is within policy budget" if diff.changed_count <= policy.max_changed_items else "changed artifact count exceeds policy budget", "changed-artifact-budget", diff.changed_count <= policy.max_changed_items, {"changed_count": diff.changed_count, "maximum": policy.max_changed_items}, diff.content_address),
        _check("semantic field count is within policy budget" if len(diff.changed_fields) <= policy.max_changed_fields else "semantic field count exceeds policy budget", "semantic-field-budget", len(diff.changed_fields) <= policy.max_changed_fields, {"changed_fields": diff.changed_fields, "count": len(diff.changed_fields), "maximum": policy.max_changed_fields}, diff.content_address),
        _check("diff audit conserves byte actions, fields, counts, and item identities" if all(_audit_passed(audit, check_id) for check_id in ("item-identities", "action-conservation", "field-conservation", "count-conservation")) else "diff audit does not conserve byte receipts", "byte-receipt-conservation", all(_audit_passed(audit, check_id) for check_id in ("item-identities", "action-conservation", "field-conservation", "count-conservation")), {"required_checks": ("item-identities", "action-conservation", "field-conservation", "count-conservation")}, audit.content_address),
        _check("diff, audit, and policy documents remain public and path-free" if _public(diff.to_dict()) and _public(audit.to_dict()) and _public(policy.to_dict()) else "one promotion input crosses the public boundary", "public-boundary", _public(diff.to_dict()) and _public(audit.to_dict()) and _public(policy.to_dict()), {"diff_public": _public(diff.to_dict()), "audit_public": _public(audit.to_dict()), "policy_public": _public(policy.to_dict())}, diff.content_address),
        _check("diff and audit content addresses replay" if diff_model.address_diff(diff) == diff.content_address and diff_audit_model.address_audit(audit) == audit.content_address else "diff or audit content address does not replay", "content-address", diff_model.address_diff(diff) == diff.content_address and diff_audit_model.address_audit(audit) == audit.content_address, {"diff_replays": diff_model.address_diff(diff) == diff.content_address, "audit_replays": diff_audit_model.address_audit(audit) == audit.content_address}, diff.content_address),
    )
    blocking_failure_count = sum(not check.passed and check.severity == "blocking" for check in checks)
    hold_failure_count = sum(not check.passed and check.severity == "hold" for check in checks)
    state = "blocked" if blocking_failure_count else "held" if hold_failure_count else "ready"
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate(gate_id, diff.baseline_address, diff.candidate_address, diff.content_address, audit.content_address, address_policy(policy), policy, state, state != "blocked", state == "ready", checks, "pending:observability-bundle-promotion-gate")
    materialized_checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck(check.check_id, check.passed, check.severity, check.detail, check.observed, check.evidence_address, address_check(check)) for check in provisional.checks)
    final = RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate(gate_id, diff.baseline_address, diff.candidate_address, diff.content_address, audit.content_address, address_policy(policy), policy, state, state != "blocked", state == "ready", materialized_checks, "pending:observability-bundle-promotion-gate")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate(final.gate_id, final.baseline_address, final.candidate_address, final.diff_address, final.diff_audit_address, final.policy_address, final.policy, final.state, final.accepted, final.release_ready, final.checks, address_gate(final))


def build_promotion_gate(diff: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff, *, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy | None = None, gate_id: str = DEFAULT_GATE_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
    if not isinstance(diff, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff):
        raise ValidationError("observability bundle promotion gate requires a typed diff")
    policy = RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy() if policy is None else policy
    if not isinstance(policy, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy):
        raise ValidationError("observability bundle promotion gate requires a typed policy")
    return _build_gate(diff, diff_audit_model.audit_diff(diff), policy, _text(gate_id, "observability bundle promotion gate ID", 128))


def build_promotion_gate_from_directories(baseline_source: str, candidate_source: str, *, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy | None = None, gate_id: str = DEFAULT_GATE_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
    return build_promotion_gate(diff_model.diff_bundle_directories(baseline_source, candidate_source), policy=policy, gate_id=gate_id)


def gate_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
    value = _mapping(value, "observability bundle promotion gate")
    if "policy" not in value:
        raise ValidationError("observability bundle promotion gate mapping must include policy")
    typed = RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate.from_mapping(value)
    return verify_gate(typed)


def verify_gate(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate):
        raise ValidationError("observability bundle promotion gate verification requires a typed gate")
    if address_gate(value) != value.content_address:
        raise ValidationError("observability bundle promotion gate content address does not replay")
    return value


def gate_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate) -> str:
    return canonical_json(verify_gate(value).to_dict())


def gate_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate) -> str:
    value = verify_gate(value)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=("check_id", "passed", "severity", "detail", "evidence_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: check.to_dict()[key] for key in writer.fieldnames} for check in value.checks)
    return output.getvalue()


def render_gate_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate) -> str:
    value = verify_gate(value)
    lines = ["# Assurance History Observatory Observability Bundle Promotion Gate", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Blocking failures: `{value.blocking_failure_count}`", f"- Hold failures: `{value.hold_failure_count}`", f"- Content address: `{value.content_address}`", "", "| check_id | passed | severity | detail | evidence_address |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {check.check_id} | {check.passed} | {check.severity} | {check.detail} | {check.evidence_address} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    fields = {"policy_id": {"type": "string", "maxLength": 128}, "require_baseline_accepted": {"type": "boolean"}, "require_candidate_accepted": {"type": "boolean"}, "require_candidate_audit_complete": {"type": "boolean"}, "require_candidate_ready": {"type": "boolean"}, "require_diff_audit_complete": {"type": "boolean"}, "allowed_diff_states": {"type": "array", "minItems": 1, "maxItems": len(diff_model.STATES), "items": {"type": "string", "enum": list(diff_model.STATES)}}, "max_changed_items": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_ITEMS}, "max_changed_fields": {"type": "integer", "minimum": 0, "maximum": len(diff_model.BUNDLE_FIELDS)}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy.FIELDS), "properties": fields}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string", "maxLength": 1024}, "observed": {"type": "object", "additionalProperties": True}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate.FIELDS), "properties": {"gate_id": {"type": "string"}, "baseline_address": {"type": "string", "pattern": "^" + diff_model.bundle_model.BUNDLE_PREFIX + ":"}, "candidate_address": {"type": "string", "pattern": "^" + diff_model.bundle_model.BUNDLE_PREFIX + ":"}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "diff_audit_address": {"type": "string", "pattern": "^" + diff_audit_model.AUDIT_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + POLICY_PREFIX + ":"}, "policy": policy_schema(), "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "blocking_failure_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "hold_failure_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + GATE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "states": STATES, "severities": SEVERITIES, "check_ids": CHECK_IDS, "blocking_check_ids": tuple(sorted(BLOCKING_CHECK_IDS)), "limits": {"max_checks": MAX_CHECKS, "max_changed_items": diff_model.MAX_ITEMS, "max_changed_fields": len(diff_model.BUNDLE_FIELDS)}, "features": ("strict typed observability-bundle diff input", "independent diff-audit evaluation", "explicit promotion policy", "ready held and blocked decisions", "blocking versus hold severity", "changed artifact and semantic field budgets", "addressed check evidence", "content-addressed policy checks and gate", "path-free JSON CSV and Markdown exports"), "schemas": ("policy", "check", "gate")}


__all__ = [
    "BLOCKING_CHECK_IDS",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "DEFAULT_ALLOWED_DIFF_STATES",
    "DEFAULT_GATE_ID",
    "DEFAULT_MAX_CHANGED_FIELDS",
    "DEFAULT_MAX_CHANGED_ITEMS",
    "DEFAULT_POLICY_ID",
    "GATE_PREFIX",
    "MAX_CHECKS",
    "POLICY_PREFIX",
    "SEVERITIES",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGate",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionGateCheck",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy",
    "address_check",
    "address_gate",
    "address_policy",
    "build_promotion_gate",
    "build_promotion_gate_from_directories",
    "capabilities",
    "check_schema",
    "gate_csv",
    "gate_from_mapping",
    "gate_json",
    "gate_schema",
    "policy_schema",
    "render_gate_markdown",
    "verify_gate",
]

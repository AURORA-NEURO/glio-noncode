"""Policy-governed promotion decisions for catalog revisions.

This boundary combines a catalog evolution diff with the candidate catalog's
aggregate report.  It makes the release decision explicit, deterministic, and
replayable: integrity failures block, policy budget failures hold, and only a
fully verified candidate can become ready.  Inputs are typed public documents;
the gate never reopens source directories and never emits filesystem paths.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_audit as diff_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report as report_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_audit as report_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = report_audit_model.VERSION + "-promotion-gate-v1"
BOUNDARY = report_audit_model.BOUNDARY + "_promotion_gate"
GATE_PREFIX = diff_model.DIFF_PREFIX + "-promotion-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
CHECK_PREFIX = GATE_PREFIX + "-check"
DEFAULT_GATE_ID = "glio-noncode-observability-bundle-catalog-promotion-gate"
DEFAULT_POLICY_ID = "glio-noncode-observability-bundle-catalog-promotion-policy"
DEFAULT_ALLOWED_DIFF_STATES = ("unchanged", "added", "changed", "mixed")
DEFAULT_MAX_ADDED = diff_model.MAX_ITEMS
DEFAULT_MAX_REMOVED = 0
DEFAULT_MAX_CHANGED = diff_model.MAX_ITEMS
DEFAULT_MAX_ACCEPTED_REGRESSION = 0
DEFAULT_MAX_READY_REGRESSION = 0
DEFAULT_MAX_REJECTED = 0
STATES = ("ready", "held", "blocked")
SEVERITIES = ("hold", "blocking")
CHECK_IDS = (
    "baseline-nonempty",
    "candidate-nonempty",
    "diff-audit-complete",
    "candidate-report-audit-complete",
    "candidate-all-accepted",
    "candidate-all-ready",
    "transition-state",
    "added-budget",
    "removed-budget",
    "changed-budget",
    "accepted-regression",
    "ready-regression",
    "rejected-budget",
    "public-boundary",
    "content-address",
)
MAX_CHECKS = len(CHECK_IDS)
BLOCKING_CHECK_IDS = frozenset(
    {
        "baseline-nonempty",
        "candidate-nonempty",
        "diff-audit-complete",
        "candidate-report-audit-complete",
        "candidate-all-accepted",
        "candidate-all-ready",
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


def _delta(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < -maximum or value > maximum:
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
    return report_model._public(value)


def _states(value: Any) -> tuple[str, ...]:
    values = _sequence(value, "observability bundle catalog promotion allowed diff states", len(diff_model.STATES))
    if not values:
        raise ValidationError("observability bundle catalog promotion allowed diff states cannot be empty")
    normalized = tuple(_text(item, "observability bundle catalog promotion diff state", 32) for item in values)
    if any(item not in diff_model.STATES for item in normalized):
        raise ValidationError("observability bundle catalog promotion diff state is unsupported")
    if len(set(normalized)) != len(normalized) or tuple(item for item in diff_model.STATES if item in normalized) != normalized:
        raise ValidationError("observability bundle catalog promotion diff states must use canonical order")
    return normalized


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy:
    """Public requirements and bounded budgets for catalog promotion."""

    FIELDS = (
        "policy_id",
        "require_baseline_nonempty",
        "require_candidate_nonempty",
        "require_diff_audit_complete",
        "require_candidate_report_audit_complete",
        "require_candidate_all_accepted",
        "require_candidate_all_ready",
        "allowed_diff_states",
        "max_added",
        "max_removed",
        "max_changed",
        "max_accepted_regression",
        "max_ready_regression",
        "max_rejected",
    )

    def __init__(
        self,
        policy_id: str = DEFAULT_POLICY_ID,
        require_baseline_nonempty: bool = True,
        require_candidate_nonempty: bool = True,
        require_diff_audit_complete: bool = True,
        require_candidate_report_audit_complete: bool = True,
        require_candidate_all_accepted: bool = True,
        require_candidate_all_ready: bool = True,
        allowed_diff_states: Sequence[str] = DEFAULT_ALLOWED_DIFF_STATES,
        max_added: int = DEFAULT_MAX_ADDED,
        max_removed: int = DEFAULT_MAX_REMOVED,
        max_changed: int = DEFAULT_MAX_CHANGED,
        max_accepted_regression: int = DEFAULT_MAX_ACCEPTED_REGRESSION,
        max_ready_regression: int = DEFAULT_MAX_READY_REGRESSION,
        max_rejected: int = DEFAULT_MAX_REJECTED,
    ) -> None:
        self.policy_id = _text(policy_id, "observability bundle catalog promotion policy ID", 128)
        self.require_baseline_nonempty = _bool(require_baseline_nonempty, "observability bundle catalog promotion baseline requirement")
        self.require_candidate_nonempty = _bool(require_candidate_nonempty, "observability bundle catalog promotion candidate requirement")
        self.require_diff_audit_complete = _bool(require_diff_audit_complete, "observability bundle catalog promotion diff audit requirement")
        self.require_candidate_report_audit_complete = _bool(require_candidate_report_audit_complete, "observability bundle catalog promotion report audit requirement")
        self.require_candidate_all_accepted = _bool(require_candidate_all_accepted, "observability bundle catalog promotion acceptance requirement")
        self.require_candidate_all_ready = _bool(require_candidate_all_ready, "observability bundle catalog promotion readiness requirement")
        self.allowed_diff_states = _states(allowed_diff_states)
        self.max_added = _count(max_added, "observability bundle catalog promotion added budget", diff_model.MAX_ITEMS)
        self.max_removed = _count(max_removed, "observability bundle catalog promotion removed budget", diff_model.MAX_ITEMS)
        self.max_changed = _count(max_changed, "observability bundle catalog promotion changed budget", diff_model.MAX_ITEMS)
        self.max_accepted_regression = _count(max_accepted_regression, "observability bundle catalog promotion accepted regression budget", report_model.MAX_ROWS)
        self.max_ready_regression = _count(max_ready_regression, "observability bundle catalog promotion ready regression budget", report_model.MAX_ROWS)
        self.max_rejected = _count(max_rejected, "observability bundle catalog promotion rejected budget", report_model.MAX_ROWS)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog promotion policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "require_baseline_nonempty": self.require_baseline_nonempty,
            "require_candidate_nonempty": self.require_candidate_nonempty,
            "require_diff_audit_complete": self.require_diff_audit_complete,
            "require_candidate_report_audit_complete": self.require_candidate_report_audit_complete,
            "require_candidate_all_accepted": self.require_candidate_all_accepted,
            "require_candidate_all_ready": self.require_candidate_all_ready,
            "allowed_diff_states": self.allowed_diff_states,
            "max_added": self.max_added,
            "max_removed": self.max_removed,
            "max_changed": self.max_changed,
            "max_accepted_regression": self.max_accepted_regression,
            "max_ready_regression": self.max_ready_regression,
            "max_rejected": self.max_rejected,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy:
        value = _mapping(value, "observability bundle catalog promotion policy")
        _strict(value, set(cls().to_dict()), "observability bundle catalog promotion policy")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion policy is missing fields: {missing}")
        return cls(**value)


def address_policy(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy):
        raise ValidationError("observability bundle catalog promotion policy address requires a typed policy")
    return content_hash(value.to_dict(), prefix=POLICY_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck:
    """One gate assertion with public observed values and evidence."""

    FIELDS = ("check_id", "passed", "severity", "detail", "observed", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, severity: str, detail: str, observed: Mapping[str, Any], evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "observability bundle catalog promotion check ID", 128)
        self.passed = _bool(passed, "observability bundle catalog promotion check passed")
        self.severity = _text(severity, "observability bundle catalog promotion check severity", 32)
        if self.severity not in SEVERITIES:
            raise ValidationError("observability bundle catalog promotion check severity is invalid")
        self.detail = _text(detail, "observability bundle catalog promotion check detail", 1024)
        self.observed = _json_value(dict(_mapping(observed, "observability bundle catalog promotion observed values")))
        self.evidence_address = _address(evidence_address, "observability bundle catalog promotion check evidence address")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion check content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion check address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "severity": self.severity, "detail": self.detail, "observed": self.observed, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck:
        value = _mapping(value, "observability bundle catalog promotion check")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion check is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck):
        raise ValidationError("observability bundle catalog promotion check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate:
    """A path-free ready, held, or blocked catalog promotion decision."""

    FIELDS = (
        "gate_id",
        "diff_address",
        "diff_audit_address",
        "report_address",
        "report_audit_address",
        "policy_address",
        "policy",
        "state",
        "accepted",
        "release_ready",
        "baseline_entry_count",
        "candidate_entry_count",
        "candidate_accepted_count",
        "candidate_ready_count",
        "candidate_rejected_count",
        "added_count",
        "removed_count",
        "changed_count",
        "accepted_delta",
        "ready_delta",
        "check_count",
        "passed_count",
        "failed_count",
        "blocking_failure_count",
        "hold_failure_count",
        "checks",
        "content_address",
    )

    def __init__(self, gate_id: str, diff_address: str, diff_audit_address: str, report_address: str, report_audit_address: str, policy_address: str, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy, state: str, accepted: bool, release_ready: bool, baseline_entry_count: int, candidate_entry_count: int, candidate_accepted_count: int, candidate_ready_count: int, candidate_rejected_count: int, added_count: int, removed_count: int, changed_count: int, accepted_delta: int, ready_delta: int, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck], content_address: str) -> None:
        self.gate_id = _text(gate_id, "observability bundle catalog promotion gate ID", 128)
        self.diff_address = _address(diff_address, "observability bundle catalog promotion diff address", diff_model.DIFF_PREFIX)
        self.diff_audit_address = _address(diff_audit_address, "observability bundle catalog promotion diff audit address", diff_audit_model.AUDIT_PREFIX)
        self.report_address = _address(report_address, "observability bundle catalog promotion report address", report_model.REPORT_PREFIX)
        self.report_audit_address = _address(report_audit_address, "observability bundle catalog promotion report audit address", report_audit_model.AUDIT_PREFIX)
        self.policy_address = _address(policy_address, "observability bundle catalog promotion policy address", POLICY_PREFIX)
        self.policy = policy
        self.state = _text(state, "observability bundle catalog promotion state", 32)
        self.accepted = _bool(accepted, "observability bundle catalog promotion accepted")
        self.release_ready = _bool(release_ready, "observability bundle catalog promotion release-ready")
        self.baseline_entry_count = _count(baseline_entry_count, "observability bundle catalog promotion baseline entry count", report_model.MAX_ROWS)
        self.candidate_entry_count = _count(candidate_entry_count, "observability bundle catalog promotion candidate entry count", report_model.MAX_ROWS)
        self.candidate_accepted_count = _count(candidate_accepted_count, "observability bundle catalog promotion candidate accepted count", report_model.MAX_ROWS)
        self.candidate_ready_count = _count(candidate_ready_count, "observability bundle catalog promotion candidate ready count", report_model.MAX_ROWS)
        self.candidate_rejected_count = _count(candidate_rejected_count, "observability bundle catalog promotion candidate rejected count", report_model.MAX_ROWS)
        self.added_count = _count(added_count, "observability bundle catalog promotion added count", diff_model.MAX_ITEMS)
        self.removed_count = _count(removed_count, "observability bundle catalog promotion removed count", diff_model.MAX_ITEMS)
        self.changed_count = _count(changed_count, "observability bundle catalog promotion changed count", diff_model.MAX_ITEMS)
        self.accepted_delta = _delta(accepted_delta, "observability bundle catalog promotion accepted delta", report_model.MAX_ROWS)
        self.ready_delta = _delta(ready_delta, "observability bundle catalog promotion ready delta", report_model.MAX_ROWS)
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.blocking_failure_count = sum(not check.passed and check.severity == "blocking" for check in self.checks)
        self.hold_failure_count = sum(not check.passed and check.severity == "hold" for check in self.checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.policy, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy) or address_policy(self.policy) != self.policy_address:
            raise ValidationError("observability bundle catalog promotion policy is not typed or does not reproduce")
        if self.state not in STATES:
            raise ValidationError("observability bundle catalog promotion state is invalid")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck) for check in self.checks):
            raise ValidationError("observability bundle catalog promotion check set is invalid")
        if self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != MAX_CHECKS or self.blocking_failure_count + self.hold_failure_count != self.failed_count:
            raise ValidationError("observability bundle catalog promotion check counts are not conserved")
        if self.candidate_accepted_count + self.candidate_rejected_count != self.candidate_entry_count or self.candidate_ready_count > self.candidate_accepted_count:
            raise ValidationError("observability bundle catalog promotion candidate counts are not conserved")
        expected_state = "blocked" if self.blocking_failure_count else "held" if self.hold_failure_count else "ready"
        if self.state != expected_state or self.accepted != (self.state != "blocked") or self.release_ready != (self.state == "ready"):
            raise ValidationError("observability bundle catalog promotion decision is not derived from checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion content address", GATE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_gate(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion gate address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field not in {"policy", "checks"} else (self.policy.to_dict() if field == "policy" else tuple(check.to_dict() for check in self.checks)) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "checks" and key != "policy"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate:
        value = _mapping(value, "observability bundle catalog promotion gate")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion gate")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion gate is missing fields: {missing}")
        policy = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy.from_mapping(value["policy"])
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle catalog promotion checks", MAX_CHECKS))
        result = cls(value["gate_id"], value["diff_address"], value["diff_audit_address"], value["report_address"], value["report_audit_address"], value["policy_address"], policy, value["state"], value["accepted"], value["release_ready"], value["baseline_entry_count"], value["candidate_entry_count"], value["candidate_accepted_count"], value["candidate_ready_count"], value["candidate_rejected_count"], value["added_count"], value["removed_count"], value["changed_count"], value["accepted_delta"], value["ready_delta"], checks, value["content_address"])
        for field in ("check_count", "passed_count", "failed_count", "blocking_failure_count", "hold_failure_count"):
            if getattr(result, field) != value[field]:
                raise ValidationError(f"observability bundle catalog promotion {field} does not reconcile")
        return result


def address_gate(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate):
        raise ValidationError("observability bundle catalog promotion gate address requires a typed gate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def _check(check_id: str, passed: bool, detail: str, observed: Mapping[str, Any], evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck:
    severity = "blocking" if check_id in BLOCKING_CHECK_IDS else "hold"
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck(check_id, passed, severity, detail, observed, evidence_address, "pending:observability-bundle-catalog-promotion-check")


def _audit_passed(audit: Any, check_id: str) -> bool:
    return next((check.passed for check in audit.checks if check.check_id == check_id), False)


def _build_gate(diff: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff, diff_audit: diff_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAudit, report: report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport, report_audit: report_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy, gate_id: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate:
    baseline_nonempty = diff.left_entry_count > 0
    candidate_nonempty = report.entry_count > 0
    accepted_regression = max(0, -diff.accepted_count_delta)
    ready_regression = max(0, -diff.ready_count_delta)
    checks = (
        _check("baseline-nonempty", (not policy.require_baseline_nonempty) or baseline_nonempty, "baseline catalog satisfies the non-empty prerequisite" if baseline_nonempty else "baseline catalog is empty", {"required": policy.require_baseline_nonempty, "entry_count": diff.left_entry_count}, diff.left_catalog_address),
        _check("candidate-nonempty", (not policy.require_candidate_nonempty) or candidate_nonempty, "candidate catalog satisfies the non-empty prerequisite" if candidate_nonempty else "candidate catalog is empty", {"required": policy.require_candidate_nonempty, "entry_count": report.entry_count}, report.content_address),
        _check("diff-audit-complete", (not policy.require_diff_audit_complete) or (diff_audit.state == "complete" and diff_audit.accepted), "catalog diff audit is complete and accepted" if diff_audit.state == "complete" and diff_audit.accepted else "catalog diff audit is incomplete or rejected", {"required": policy.require_diff_audit_complete, "state": diff_audit.state, "accepted": diff_audit.accepted}, diff_audit.content_address),
        _check("candidate-report-audit-complete", (not policy.require_candidate_report_audit_complete) or (report_audit.state == "complete" and report_audit.accepted), "candidate catalog report audit is complete and accepted" if report_audit.state == "complete" and report_audit.accepted else "candidate catalog report audit is incomplete or rejected", {"required": policy.require_candidate_report_audit_complete, "state": report_audit.state, "accepted": report_audit.accepted}, report_audit.content_address),
        _check("candidate-all-accepted", (not policy.require_candidate_all_accepted) or report.rejected_count == 0, "all candidate entries are accepted" if report.rejected_count == 0 else "candidate contains rejected entries", {"required": policy.require_candidate_all_accepted, "accepted_count": report.accepted_count, "rejected_count": report.rejected_count}, report.content_address),
        _check("candidate-all-ready", (not policy.require_candidate_all_ready) or report.ready_count == report.entry_count, "all candidate entries are ready" if report.ready_count == report.entry_count else "candidate contains held or blocked entries", {"required": policy.require_candidate_all_ready, "ready_count": report.ready_count, "entry_count": report.entry_count}, report.content_address),
        _check("transition-state", diff.state in policy.allowed_diff_states, "catalog transition state is allowed by policy" if diff.state in policy.allowed_diff_states else "catalog transition state is not allowed by policy", {"observed": diff.state, "allowed": policy.allowed_diff_states}, diff.content_address),
        _check("added-budget", diff.added_count <= policy.max_added, "added entry count is within policy budget" if diff.added_count <= policy.max_added else "added entry count exceeds policy budget", {"observed": diff.added_count, "maximum": policy.max_added}, diff.content_address),
        _check("removed-budget", diff.removed_count <= policy.max_removed, "removed entry count is within policy budget" if diff.removed_count <= policy.max_removed else "removed entry count exceeds policy budget", {"observed": diff.removed_count, "maximum": policy.max_removed}, diff.content_address),
        _check("changed-budget", diff.changed_count <= policy.max_changed, "changed entry count is within policy budget" if diff.changed_count <= policy.max_changed else "changed entry count exceeds policy budget", {"observed": diff.changed_count, "maximum": policy.max_changed}, diff.content_address),
        _check("accepted-regression", accepted_regression <= policy.max_accepted_regression, "accepted-count regression is within policy budget" if accepted_regression <= policy.max_accepted_regression else "accepted-count regression exceeds policy budget", {"delta": diff.accepted_count_delta, "regression": accepted_regression, "maximum": policy.max_accepted_regression}, diff.content_address),
        _check("ready-regression", ready_regression <= policy.max_ready_regression, "ready-count regression is within policy budget" if ready_regression <= policy.max_ready_regression else "ready-count regression exceeds policy budget", {"delta": diff.ready_count_delta, "regression": ready_regression, "maximum": policy.max_ready_regression}, diff.content_address),
        _check("rejected-budget", report.rejected_count <= policy.max_rejected, "candidate rejected count is within policy budget" if report.rejected_count <= policy.max_rejected else "candidate rejected count exceeds policy budget", {"observed": report.rejected_count, "maximum": policy.max_rejected}, report.content_address),
        _check("public-boundary", all(_public(value.to_dict()) for value in (diff, diff_audit, report, report_audit, policy)), "all promotion inputs remain public and path-free", {"diff": _public(diff.to_dict()), "diff_audit": _public(diff_audit.to_dict()), "report": _public(report.to_dict()), "report_audit": _public(report_audit.to_dict()), "policy": _public(policy.to_dict())}, diff.content_address),
        _check("content-address", diff_model.address_diff(diff) == diff.content_address and diff_audit_model.address_audit(diff_audit) == diff_audit.content_address and report_model.address_report(report) == report.content_address and report_audit_model.address_audit(report_audit) == report_audit.content_address, "all promotion input addresses replay" if diff_model.address_diff(diff) == diff.content_address and diff_audit_model.address_audit(diff_audit) == diff_audit.content_address and report_model.address_report(report) == report.content_address and report_audit_model.address_audit(report_audit) == report_audit.content_address else "one or more promotion input addresses do not replay", {"diff": diff_model.address_diff(diff) == diff.content_address, "diff_audit": diff_audit_model.address_audit(diff_audit) == diff_audit.content_address, "report": report_model.address_report(report) == report.content_address, "report_audit": report_audit_model.address_audit(report_audit) == report_audit.content_address}, diff.content_address),
    )
    blocking_failure_count = sum(not check.passed and check.severity == "blocking" for check in checks)
    hold_failure_count = sum(not check.passed and check.severity == "hold" for check in checks)
    state = "blocked" if blocking_failure_count else "held" if hold_failure_count else "ready"
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate(gate_id, diff.content_address, diff_audit.content_address, report.content_address, report_audit.content_address, address_policy(policy), policy, state, state != "blocked", state == "ready", diff.left_entry_count, report.entry_count, report.accepted_count, report.ready_count, report.rejected_count, diff.added_count, diff.removed_count, diff.changed_count, diff.accepted_count_delta, diff.ready_count_delta, checks, "pending:observability-bundle-catalog-promotion-gate")
    addressed_checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck(check.check_id, check.passed, check.severity, check.detail, check.observed, check.evidence_address, address_check(check)) for check in provisional.checks)
    final = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate(gate_id, diff.content_address, diff_audit.content_address, report.content_address, report_audit.content_address, address_policy(policy), policy, state, state != "blocked", state == "ready", diff.left_entry_count, report.entry_count, report.accepted_count, report.ready_count, report.rejected_count, diff.added_count, diff.removed_count, diff.changed_count, diff.accepted_count_delta, diff.ready_count_delta, addressed_checks, "pending:observability-bundle-catalog-promotion-gate")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate(final.gate_id, final.diff_address, final.diff_audit_address, final.report_address, final.report_audit_address, final.policy_address, final.policy, final.state, final.accepted, final.release_ready, final.baseline_entry_count, final.candidate_entry_count, final.candidate_accepted_count, final.candidate_ready_count, final.candidate_rejected_count, final.added_count, final.removed_count, final.changed_count, final.accepted_delta, final.ready_delta, final.checks, address_gate(final))


def build_promotion_gate(diff: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff, report: report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport, *, policy: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy | None = None, gate_id: str = DEFAULT_GATE_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate:
    if not isinstance(diff, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) or not isinstance(report, report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport):
        raise ValidationError("observability bundle catalog promotion gate requires typed diff and report")
    diff_model.verify_diff(diff)
    report_model.verify_report(report)
    policy = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy() if policy is None else policy
    if not isinstance(policy, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy):
        raise ValidationError("observability bundle catalog promotion gate requires a typed policy")
    if report.catalog_address != diff.right_catalog_address:
        raise ValidationError("observability bundle catalog promotion report must describe the diff candidate catalog")
    return _build_gate(diff, diff_audit_model.audit_diff(diff), report, report_audit_model.audit_report(report), policy, _text(gate_id, "observability bundle catalog promotion gate ID", 128))


def gate_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate:
    return verify_gate(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate.from_mapping(_mapping(value, "observability bundle catalog promotion gate")))


def verify_gate(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate):
        raise ValidationError("observability bundle catalog promotion gate verification requires a typed gate")
    if address_gate(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion gate content address does not replay")
    return value


def gate_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) -> str:
    return canonical_json(verify_gate(value).to_dict())


def gate_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) -> str:
    value = verify_gate(value)
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "severity", "detail", "evidence_address", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow({field: check.to_dict()[field] for field in fields})
    return output.getvalue()


def render_gate_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) -> str:
    value = verify_gate(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Promotion Gate", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Release ready: `{value.release_ready}`", f"- Candidate: `{value.candidate_entry_count}` entries, `{value.candidate_ready_count}` ready, `{value.candidate_rejected_count}` rejected", f"- Transition: `+{value.added_count}` added, `-{value.removed_count}` removed, `{value.changed_count}` changed", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Blocking failures: `{value.blocking_failure_count}`", f"- Hold failures: `{value.hold_failure_count}`", f"- Content address: `{value.content_address}`", "", "| check_id | passed | severity | detail | evidence_address |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {check.check_id} | {check.passed} | {check.severity} | {check.detail} | {check.evidence_address} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    fields = {"policy_id": {"type": "string", "maxLength": 128}, **{field: {"type": "boolean"} for field in ("require_baseline_nonempty", "require_candidate_nonempty", "require_diff_audit_complete", "require_candidate_report_audit_complete", "require_candidate_all_accepted", "require_candidate_all_ready")}, "allowed_diff_states": {"type": "array", "minItems": 1, "maxItems": len(diff_model.STATES), "items": {"type": "string", "enum": list(diff_model.STATES)}}, **{field: {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_ITEMS} for field in ("max_added", "max_removed", "max_changed")}, **{field: {"type": "integer", "minimum": 0, "maximum": report_model.MAX_ROWS} for field in ("max_accepted_regression", "max_ready_regression", "max_rejected")}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy.FIELDS), "properties": fields}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "observed": {"type": "object", "additionalProperties": True}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def gate_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {"gate_id": {"type": "string", "maxLength": 128}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "diff_audit_address": {"type": "string", "pattern": "^" + diff_audit_model.AUDIT_PREFIX + ":"}, "report_address": {"type": "string", "pattern": "^" + report_model.REPORT_PREFIX + ":"}, "report_audit_address": {"type": "string", "pattern": "^" + report_audit_model.AUDIT_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + POLICY_PREFIX + ":"}, "policy": policy_schema(), "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + GATE_PREFIX + ":"}}
    properties.update({field: {"type": "integer", "minimum": 0, "maximum": report_model.MAX_ROWS} for field in ("baseline_entry_count", "candidate_entry_count", "candidate_accepted_count", "candidate_ready_count", "candidate_rejected_count")})
    properties.update({field: {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_ITEMS} for field in ("added_count", "removed_count", "changed_count", "check_count", "passed_count", "failed_count", "blocking_failure_count", "hold_failure_count")})
    properties.update({field: {"type": "integer", "minimum": -report_model.MAX_ROWS, "maximum": report_model.MAX_ROWS} for field in ("accepted_delta", "ready_delta")})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate.FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "gate_prefix": GATE_PREFIX, "policy_prefix": POLICY_PREFIX, "check_prefix": CHECK_PREFIX, "states": STATES, "severities": SEVERITIES, "check_ids": CHECK_IDS, "blocking_check_ids": tuple(sorted(BLOCKING_CHECK_IDS)), "limits": {"max_checks": MAX_CHECKS, "max_catalog_entries": report_model.MAX_ROWS, "max_items": diff_model.MAX_ITEMS}, "features": ("catalog diff and candidate report composition", "independent diff and report assurance", "explicit public promotion policy", "ready held and blocked decisions", "transition and regression budgets", "acceptance and readiness prerequisites", "path-free observed evidence", "content-addressed checks and gates", "JSON CSV and Markdown exports"), "schemas": ("policy", "check", "gate")}


__all__ = [
    "BLOCKING_CHECK_IDS", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "DEFAULT_ALLOWED_DIFF_STATES", "DEFAULT_GATE_ID", "DEFAULT_POLICY_ID", "GATE_PREFIX", "MAX_CHECKS", "POLICY_PREFIX", "SEVERITIES", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy",
    "address_check", "address_gate", "address_policy", "build_promotion_gate", "capabilities", "check_schema", "gate_csv", "gate_from_mapping", "gate_json", "gate_schema", "policy_schema", "render_gate_markdown", "verify_gate",
]

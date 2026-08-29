"""Policy evaluation for ordered observatory registry histories.

The history model records what changed and the history audit proves that the
record is structurally reproducible.  This boundary answers the next
operational question: may this timeline be used as a release input under a
declared public policy?  A gate never mutates the history or invents source
metadata.  It emits an addressed decision with explicit checks, observed
values, and a stable distinction between a policy hold and an integrity block.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = audit_model.VERSION + "-release-gate-v1"
BOUNDARY = audit_model.BOUNDARY + "_release_gate"
GATE_PREFIX = history_model.HISTORY_PREFIX + "-release-gate"
POLICY_PREFIX = GATE_PREFIX + "-policy"
CHECK_PREFIX = GATE_PREFIX + "-check"
DEFAULT_POLICY_ID = "glio-noncode-registry-history-release-policy"
DEFAULT_MINIMUM_SNAPSHOTS = 2
DEFAULT_ALLOWED_TRANSITION_STATES = ("unchanged", "improved")
DEFAULT_MAX_REMOVED_ITEMS = 0
DEFAULT_MAX_CHANGED_ITEMS = diff_model.MAX_DIFF_ITEMS
DEFAULT_MAX_REGRESSED_TRANSITIONS = 0
DEFAULT_MAX_MIXED_TRANSITIONS = 0
STATES = ("ready", "held", "blocked")
SEVERITIES = ("hold", "blocking")
CHECK_IDS = (
    "minimum-snapshots",
    "audit-complete",
    "snapshots-accepted",
    "final-release-ready",
    "transition-states",
    "removed-items-budget",
    "changed-items-budget",
    "regression-budget",
    "mixed-budget",
    "public-boundary",
    "content-address",
)
MAX_CHECKS = len(CHECK_IDS)
MAX_ALLOWED_TRANSITION_STATES = len(history_model.STATES)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return history_model._public(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _states(value: Any) -> tuple[str, ...]:
    values = _sequence(value, "registry history release policy transition states", MAX_ALLOWED_TRANSITION_STATES)
    if not values:
        raise ValidationError("registry history release policy transition states cannot be empty")
    normalized = tuple(_text(item, "registry history release policy transition state", 32) for item in values)
    if any(item not in history_model.STATES for item in normalized):
        raise ValidationError("registry history release policy transition state is unsupported")
    if len(set(normalized)) != len(normalized):
        raise ValidationError("registry history release policy transition states must be unique")
    if tuple(item for item in history_model.STATES if item in normalized) != normalized:
        raise ValidationError("registry history release policy transition states must use canonical order")
    return normalized


class RegistryHistoryReleasePolicy:
    """Public limits and requirements used by the history release gate."""

    def __init__(
        self,
        policy_id: str = DEFAULT_POLICY_ID,
        minimum_snapshots: int = DEFAULT_MINIMUM_SNAPSHOTS,
        require_audit_complete: bool = True,
        require_all_snapshots_accepted: bool = True,
        require_final_release_ready: bool = True,
        allowed_transition_states: Sequence[str] = DEFAULT_ALLOWED_TRANSITION_STATES,
        max_removed_items_per_transition: int = DEFAULT_MAX_REMOVED_ITEMS,
        max_changed_items_per_transition: int = DEFAULT_MAX_CHANGED_ITEMS,
        max_regressed_transitions: int = DEFAULT_MAX_REGRESSED_TRANSITIONS,
        max_mixed_transitions: int = DEFAULT_MAX_MIXED_TRANSITIONS,
    ) -> None:
        self.policy_id = _text(policy_id, "registry history release policy ID", 128)
        self.minimum_snapshots = _count(minimum_snapshots, "registry history release policy minimum snapshots", history_model.MAX_SNAPSHOTS, positive=True)
        self.require_audit_complete = _bool(require_audit_complete, "registry history release policy audit requirement")
        self.require_all_snapshots_accepted = _bool(require_all_snapshots_accepted, "registry history release policy acceptance requirement")
        self.require_final_release_ready = _bool(require_final_release_ready, "registry history release policy final readiness requirement")
        self.allowed_transition_states = _states(allowed_transition_states)
        self.max_removed_items_per_transition = _count(max_removed_items_per_transition, "registry history release policy removed-item budget", diff_model.MAX_DIFF_ITEMS)
        self.max_changed_items_per_transition = _count(max_changed_items_per_transition, "registry history release policy changed-item budget", diff_model.MAX_DIFF_ITEMS)
        self.max_regressed_transitions = _count(max_regressed_transitions, "registry history release policy regression budget", history_model.MAX_TRANSITIONS)
        self.max_mixed_transitions = _count(max_mixed_transitions, "registry history release policy mixed-state budget", history_model.MAX_TRANSITIONS)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("registry history release policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "minimum_snapshots": self.minimum_snapshots,
            "require_audit_complete": self.require_audit_complete,
            "require_all_snapshots_accepted": self.require_all_snapshots_accepted,
            "require_final_release_ready": self.require_final_release_ready,
            "allowed_transition_states": self.allowed_transition_states,
            "max_removed_items_per_transition": self.max_removed_items_per_transition,
            "max_changed_items_per_transition": self.max_changed_items_per_transition,
            "max_regressed_transitions": self.max_regressed_transitions,
            "max_mixed_transitions": self.max_mixed_transitions,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleasePolicy:
        value = _mapping(value, "registry history release policy")
        _strict(value, set(cls(DEFAULT_POLICY_ID).to_dict()), "registry history release policy")
        return cls(**value)


def address_policy(value: RegistryHistoryReleasePolicy) -> str:
    if not isinstance(value, RegistryHistoryReleasePolicy):
        raise ValidationError("registry history release policy address requires a typed policy")
    return content_hash(value.to_dict(), prefix=POLICY_PREFIX)


class RegistryHistoryReleaseGateCheck:
    """One policy assertion with an explicit hold or blocking severity."""

    def __init__(self, check_id: str, passed: bool, severity: str, detail: str, observed: Mapping[str, Any], evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "registry history release gate check ID", 128)
        self.passed = _bool(passed, "registry history release gate check passed")
        self.severity = _text(severity, "registry history release gate check severity", 32)
        if self.severity not in SEVERITIES:
            raise ValidationError("registry history release gate check severity is invalid")
        self.detail = _text(detail, "registry history release gate check detail", 1024)
        self.observed = _json_value(dict(_mapping(observed, "registry history release gate observed values")))
        if not _public(self.observed):
            raise ValidationError("registry history release gate observed values cross the public boundary")
        self.evidence_address = _text(evidence_address, "registry history release gate evidence address", 2048)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry history release gate check content address")
        else:
            _address(self.content_address, "registry history release gate check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("registry history release gate check address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "severity": self.severity, "detail": self.detail, "observed": self.observed, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGateCheck:
        value = _mapping(value, "registry history release gate check")
        _strict(value, {"check_id", "passed", "severity", "detail", "observed", "evidence_address", "content_address"}, "registry history release gate check")
        return cls(**value)


def address_check(value: RegistryHistoryReleaseGateCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseGateCheck):
        raise ValidationError("registry history release gate check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseGate:
    """A deterministic ready, held, or blocked decision over one history."""

    def __init__(self, history_id: str, history_address: str, audit_address: str, policy_address: str, policy: RegistryHistoryReleasePolicy, state: str, accepted: bool, release_ready: bool, checks: Sequence[RegistryHistoryReleaseGateCheck], content_address: str) -> None:
        self.history_id = _text(history_id, "registry history release gate history ID")
        self.history_address = _address(history_address, "registry history release gate history address", history_model.HISTORY_PREFIX)
        self.audit_address = _address(audit_address, "registry history release gate audit address", audit_model.AUDIT_PREFIX)
        self.policy_address = _address(policy_address, "registry history release gate policy address", POLICY_PREFIX)
        self.policy = policy
        self.state = _text(state, "registry history release gate state", 32)
        self.accepted = _bool(accepted, "registry history release gate accepted")
        self.release_ready = _bool(release_ready, "registry history release gate release-ready")
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.policy, RegistryHistoryReleasePolicy):
            raise ValidationError("registry history release gate policy must be typed")
        if address_policy(self.policy) != self.policy_address:
            raise ValidationError("registry history release gate policy address does not reproduce")
        if self.state not in STATES:
            raise ValidationError("registry history release gate state is invalid")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("registry history release gate check set is invalid")
        if any(not isinstance(check, RegistryHistoryReleaseGateCheck) for check in self.checks):
            raise ValidationError("registry history release gate checks must be typed")
        _count(self.passed_count, "registry history release gate passed count", MAX_CHECKS)
        _count(self.failed_count, "registry history release gate failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("registry history release gate counts are not conserved")
        expected_accepted = self.failed_count == 0
        blocking_failed = any(not check.passed and check.severity == "blocking" for check in self.checks)
        expected_state = "ready" if expected_accepted else ("blocked" if blocking_failed else "held")
        if self.accepted != expected_accepted or self.release_ready != expected_accepted or self.state != expected_state:
            raise ValidationError("registry history release gate decision is not derived from checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry history release gate content address")
        else:
            _address(self.content_address, "registry history release gate content address", GATE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_gate(self) != self.content_address):
            raise ValidationError("registry history release gate address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "history_address": self.history_address,
            "audit_address": self.audit_address,
            "policy_address": self.policy_address,
            "policy": self.policy.to_dict(),
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": tuple(check.to_dict() for check in self.checks),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("history_id", "history_address", "audit_address", "policy_address", "policy", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGate:
        value = _mapping(value, "registry history release gate")
        _strict(value, {"history_id", "history_address", "audit_address", "policy_address", "policy", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "checks", "content_address"}, "registry history release gate")
        checks = tuple(RegistryHistoryReleaseGateCheck.from_mapping(item) for item in _sequence(value["checks"], "registry history release gate checks", MAX_CHECKS))
        result = cls(value["history_id"], value["history_address"], value["audit_address"], value["policy_address"], RegistryHistoryReleasePolicy.from_mapping(_mapping(value["policy"], "registry history release policy")), value["state"], value["accepted"], value["release_ready"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("registry history release gate derived counts are not conserved")
        return result


def address_gate(value: RegistryHistoryReleaseGate) -> str:
    if not isinstance(value, RegistryHistoryReleaseGate):
        raise ValidationError("registry history release gate address requires a typed gate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


def _check(check_id: str, passed: bool, severity: str, detail: str, observed: Mapping[str, Any], evidence: str) -> RegistryHistoryReleaseGateCheck:
    provisional = RegistryHistoryReleaseGateCheck(check_id, passed, severity, detail, observed, evidence, "pending:check")
    return RegistryHistoryReleaseGateCheck(check_id, passed, severity, detail, observed, evidence, address_check(provisional))


def _evaluate_checks(value: history_model.RegistryHistory, audit: audit_model.RegistryHistoryAudit, policy: RegistryHistoryReleasePolicy, policy_address: str) -> tuple[RegistryHistoryReleaseGateCheck, ...]:
    transition_states = tuple(item.state for item in value.transitions)
    removed_items = tuple(item.removed_count for item in value.transitions)
    changed_items = tuple(item.changed_count for item in value.transitions)
    regressed = sum(item == "regressed" for item in transition_states)
    mixed = sum(item == "mixed" for item in transition_states)
    history_address = value.content_address
    audit_address = audit.content_address
    return (
        _check("minimum-snapshots", value.snapshot_count >= policy.minimum_snapshots, "hold", "history contains the minimum required number of snapshots", {"actual": value.snapshot_count, "minimum": policy.minimum_snapshots}, history_address),
        _check("audit-complete", not policy.require_audit_complete or (audit.complete and audit.accepted), "blocking", "independent history audit satisfies the completeness requirement", {"required": policy.require_audit_complete, "audit_complete": audit.complete, "audit_accepted": audit.accepted}, audit_address),
        _check("snapshots-accepted", not policy.require_all_snapshots_accepted or all(item.accepted for item in value.snapshots), "hold", "every snapshot satisfies the acceptance requirement", {"required": policy.require_all_snapshots_accepted, "accepted_count": sum(item.accepted for item in value.snapshots), "snapshot_count": value.snapshot_count}, history_address),
        _check("final-release-ready", not policy.require_final_release_ready or value.snapshots[-1].release_ready, "hold", "the final snapshot satisfies the release-readiness requirement", {"required": policy.require_final_release_ready, "final_release_ready": value.snapshots[-1].release_ready}, history_address),
        _check("transition-states", all(item in policy.allowed_transition_states for item in transition_states), "hold", "all transition states are permitted by policy", {"allowed": policy.allowed_transition_states, "observed": transition_states}, history_address),
        _check("removed-items-budget", all(item <= policy.max_removed_items_per_transition for item in removed_items), "hold", "every transition remains within the removed-item budget", {"maximum_observed": max(removed_items, default=0), "budget": policy.max_removed_items_per_transition}, history_address),
        _check("changed-items-budget", all(item <= policy.max_changed_items_per_transition for item in changed_items), "hold", "every transition remains within the changed-item budget", {"maximum_observed": max(changed_items, default=0), "budget": policy.max_changed_items_per_transition}, history_address),
        _check("regression-budget", regressed <= policy.max_regressed_transitions, "hold", "the history remains within the regression budget", {"observed": regressed, "budget": policy.max_regressed_transitions}, history_address),
        _check("mixed-budget", mixed <= policy.max_mixed_transitions, "hold", "the history remains within the mixed-transition budget", {"observed": mixed, "budget": policy.max_mixed_transitions}, history_address),
        _check("public-boundary", _public(value.to_dict()) and _public(audit.to_dict()) and _public(policy.to_dict()), "blocking", "history, audit, and policy projections contain only public fields", {"history_public": _public(value.to_dict()), "audit_public": _public(audit.to_dict()), "policy_public": _public(policy.to_dict())}, history_address),
        _check("content-address", history_model.address_history(value) == value.content_address and audit_model.address_audit(audit) == audit.content_address and address_policy(policy) == policy_address, "blocking", "history, audit, and policy addresses reproduce from their public projections", {"history_address_reproduces": history_model.address_history(value) == value.content_address, "audit_address_reproduces": audit_model.address_audit(audit) == audit.content_address, "policy_address_reproduces": address_policy(policy) == policy_address}, history_address),
    )


def evaluate_history(value: history_model.RegistryHistory, policy: RegistryHistoryReleasePolicy | None = None, *, audit: audit_model.RegistryHistoryAudit | None = None) -> RegistryHistoryReleaseGate:
    """Evaluate one verified history under a typed public policy."""

    history_model.verify_history(value)
    selected_policy = policy or RegistryHistoryReleasePolicy()
    if not isinstance(selected_policy, RegistryHistoryReleasePolicy):
        raise ValidationError("registry history release gate requires a typed policy")
    selected_audit = audit or audit_model.audit_history(value)
    if not isinstance(selected_audit, audit_model.RegistryHistoryAudit):
        raise ValidationError("registry history release gate requires a typed history audit")
    audit_model.verify_audit(selected_audit)
    if selected_audit.history_address != value.content_address:
        raise ValidationError("registry history release gate audit does not reference the history")
    policy_address = address_policy(selected_policy)
    checks = _evaluate_checks(value, selected_audit, selected_policy, policy_address)
    accepted = all(check.passed for check in checks)
    blocking_failed = any(not check.passed and check.severity == "blocking" for check in checks)
    state = "ready" if accepted else ("blocked" if blocking_failed else "held")
    body = {"history_id": value.history_id, "history_address": value.content_address, "audit_address": selected_audit.content_address, "policy_address": policy_address, "policy": selected_policy, "state": state, "accepted": accepted, "release_ready": accepted, "checks": checks}
    provisional = RegistryHistoryReleaseGate(**body, content_address="pending:gate")
    return RegistryHistoryReleaseGate(**body, content_address=address_gate(provisional))


def evaluate_history_from_directory(source: str | Path, policy: RegistryHistoryReleasePolicy | None = None) -> RegistryHistoryReleaseGate:
    """Load an exact history package and evaluate it without exposing its path."""

    return evaluate_history(history_model.load_history(source), policy)


def gate_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseGate:
    return RegistryHistoryReleaseGate.from_mapping(value)


def verify_gate(value: RegistryHistoryReleaseGate) -> RegistryHistoryReleaseGate:
    if not isinstance(value, RegistryHistoryReleaseGate):
        raise ValidationError("registry history release gate verification requires a typed gate")
    value._validate()
    return value


def gate_json(value: RegistryHistoryReleaseGate) -> str:
    verify_gate(value)
    return canonical_json(value.to_dict())


def gate_csv(value: RegistryHistoryReleaseGate) -> str:
    verify_gate(value)
    fields = ("check_id", "passed", "severity", "detail", "observed", "evidence_address", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        row["observed"] = canonical_json(row["observed"])
        writer.writerow({field: row[field] for field in fields})
    return output.getvalue()


def render_gate_markdown(value: RegistryHistoryReleaseGate) -> str:
    verify_gate(value)
    lines = ["# Assurance History Observatory Archive Registry History Release Gate", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Release ready: `{str(value.release_ready).lower()}`", f"- History: `{value.history_address}`", f"- Audit: `{value.audit_address}`", f"- Policy: `{value.policy.policy_id}`", f"- Policy address: `{value.policy_address}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Severity | Detail |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | `{check.severity}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    fields = {
        "policy_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "minimum_snapshots": {"type": "integer", "minimum": 1, "maximum": history_model.MAX_SNAPSHOTS},
        "require_audit_complete": {"type": "boolean"},
        "require_all_snapshots_accepted": {"type": "boolean"},
        "require_final_release_ready": {"type": "boolean"},
        "allowed_transition_states": {"type": "array", "minItems": 1, "maxItems": MAX_ALLOWED_TRANSITION_STATES, "items": {"type": "string", "enum": list(history_model.STATES)}},
        "max_removed_items_per_transition": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS},
        "max_changed_items_per_transition": {"type": "integer", "minimum": 0, "maximum": diff_model.MAX_DIFF_ITEMS},
        "max_regressed_transitions": {"type": "integer", "minimum": 0, "maximum": history_model.MAX_TRANSITIONS},
        "max_mixed_transitions": {"type": "integer", "minimum": 0, "maximum": history_model.MAX_TRANSITIONS},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "observed": {"type": "object", "additionalProperties": True}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def gate_schema() -> dict[str, Any]:
    fields = {"history_id": {"type": "string"}, "history_address": {"type": "string", "pattern": "^" + history_model.HISTORY_PREFIX + ":"}, "audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + POLICY_PREFIX + ":"}, "policy": policy_schema(), "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + GATE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "states": STATES, "severities": SEVERITIES, "checks": CHECK_IDS, "limits": {"max_checks": MAX_CHECKS, "max_snapshots": history_model.MAX_SNAPSHOTS, "max_transitions": history_model.MAX_TRANSITIONS, "max_diff_items": diff_model.MAX_DIFF_ITEMS}, "defaults": {"minimum_snapshots": DEFAULT_MINIMUM_SNAPSHOTS, "allowed_transition_states": DEFAULT_ALLOWED_TRANSITION_STATES, "max_removed_items_per_transition": DEFAULT_MAX_REMOVED_ITEMS, "max_changed_items_per_transition": DEFAULT_MAX_CHANGED_ITEMS, "max_regressed_transitions": DEFAULT_MAX_REGRESSED_TRANSITIONS, "max_mixed_transitions": DEFAULT_MAX_MIXED_TRANSITIONS}, "features": ("typed public release policy", "independent history-audit dependency", "ready held and blocked decision states", "explicit policy budgets", "addressed check observations", "public-boundary enforcement", "content-address replay", "JSON CSV and Markdown exports", "path-free directory evaluation"), "schemas": ("policy", "check", "gate")}


__all__ = [
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "DEFAULT_ALLOWED_TRANSITION_STATES",
    "DEFAULT_MAX_CHANGED_ITEMS",
    "DEFAULT_MAX_MIXED_TRANSITIONS",
    "DEFAULT_MAX_REGRESSED_TRANSITIONS",
    "DEFAULT_MAX_REMOVED_ITEMS",
    "DEFAULT_MINIMUM_SNAPSHOTS",
    "DEFAULT_POLICY_ID",
    "GATE_PREFIX",
    "MAX_CHECKS",
    "POLICY_PREFIX",
    "SEVERITIES",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseGate",
    "RegistryHistoryReleaseGateCheck",
    "RegistryHistoryReleasePolicy",
    "address_check",
    "address_gate",
    "address_policy",
    "capabilities",
    "check_schema",
    "evaluate_history",
    "evaluate_history_from_directory",
    "gate_csv",
    "gate_from_mapping",
    "gate_json",
    "gate_schema",
    "policy_schema",
    "render_gate_markdown",
    "verify_gate",
]

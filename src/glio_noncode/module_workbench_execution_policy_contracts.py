"""Typed policy contracts for module execution readiness and progress."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_POLICY_VERSION = "module-workbench-execution-policy-v1"
MODULE_WORKBENCH_EXECUTION_POLICY_BOUNDARY = "public_aggregate_module_workbench_execution_policy"
MODULE_WORKBENCH_EXECUTION_POLICY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_POLICY_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_POLICY_MAX_CHECKS = 32


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _percent(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 100.0:
        raise ValidationError(f"{field} must be between zero and one hundred")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPolicy:
    """Thresholds for deciding whether an execution ledger is admissible."""

    policy_id: str
    minimum_completion_percent: float
    minimum_evidence_coverage_percent: float
    maximum_blocked_count: int
    maximum_superseded_count: int
    maximum_event_count: int
    require_audit_acceptance: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_id, "policy_id", 256)
        _percent(self.minimum_completion_percent, "minimum_completion_percent")
        _percent(self.minimum_evidence_coverage_percent, "minimum_evidence_coverage_percent")
        _count(self.maximum_blocked_count, "maximum_blocked_count")
        _count(self.maximum_superseded_count, "maximum_superseded_count")
        _count(self.maximum_event_count, "maximum_event_count")
        if not isinstance(self.require_audit_acceptance, bool):
            raise ValidationError("require_audit_acceptance must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_policy(value: ModuleWorkbenchExecutionPolicy) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-policy")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPolicyCheck:
    """One policy threshold result."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_policy_check(
    value: ModuleWorkbenchExecutionPolicyCheck,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-policy-check")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPolicyGate:
    """Aggregate policy decision over a ledger and its independent audit."""

    ledger_address: str
    audit_address: str
    policy_address: str
    checks: tuple[ModuleWorkbenchExecutionPolicyCheck, ...]
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.ledger_address, "ledger_address")
        _text(self.audit_address, "audit_address")
        _text(self.policy_address, "policy_address")
        if len(self.checks) > MODULE_WORKBENCH_EXECUTION_POLICY_MAX_CHECKS:
            raise ValidationError("execution policy check limit exceeded")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("execution policy checks must be sorted and unique")
        _count(self.check_count, "check_count")
        _count(self.passed_count, "passed_count")
        _count(self.failed_count, "failed_count")
        if self.check_count != len(self.checks):
            raise ValidationError("policy check count does not conserve rows")
        if self.passed_count + self.failed_count != self.check_count:
            raise ValidationError("policy pass/fail counts do not conserve rows")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("policy passed count is inconsistent")
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_POLICY_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_POLICY_BOUNDARY,
            "ledger_address": self.ledger_address,
            "audit_address": self.audit_address,
            "policy_address": self.policy_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_policy_gate(
    value: ModuleWorkbenchExecutionPolicyGate,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-policy-gate")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_POLICY_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_POLICY_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_POLICY_MAX_CHECKS",
    "MODULE_WORKBENCH_EXECUTION_POLICY_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_POLICY_VERSION",
    "ModuleWorkbenchExecutionPolicy",
    "ModuleWorkbenchExecutionPolicyCheck",
    "ModuleWorkbenchExecutionPolicyGate",
    "address_module_workbench_execution_policy",
    "address_module_workbench_execution_policy_check",
    "address_module_workbench_execution_policy_gate",
]

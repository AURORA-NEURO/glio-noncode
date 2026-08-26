"""Typed policy and gate contracts for the module implementation workbench."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_POLICY_VERSION = "module-workbench-policy-v1"
MODULE_WORKBENCH_POLICY_BOUNDARY = "public_aggregate_module_workbench_policy"
MODULE_WORKBENCH_POLICY_MAX_CHECKS = 128
MODULE_WORKBENCH_POLICY_MAX_LIMIT = 512
MODULE_WORKBENCH_POLICY_DEFAULT_LIMIT = 50


def _text(value: Any, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _non_negative(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


def _score(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be between zero and one")
    return float(value)


def _percent(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 100.0:
        raise ValidationError(f"{field} must be between zero and one hundred")
    return float(value)


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError(f"{field} contains an empty value")
    if tuple(sorted(set(values))) != values:
        raise ValidationError(f"{field} must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchPolicy:
    """Immutable thresholds for deciding whether depth work is releasable."""

    policy_id: str
    minimum_overall_score: float
    minimum_depth_percent: float
    maximum_blocked_count: int
    maximum_high_risk_count: int
    minimum_family_score: float
    required_dimensions: tuple[str, ...]
    minimum_test_references: int
    minimum_evidence_count: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_id, "policy_id")
        _score(self.minimum_overall_score, "minimum_overall_score")
        _percent(self.minimum_depth_percent, "minimum_depth_percent")
        _non_negative(self.maximum_blocked_count, "maximum_blocked_count")
        _non_negative(self.maximum_high_risk_count, "maximum_high_risk_count")
        _score(self.minimum_family_score, "minimum_family_score")
        _sorted_unique(self.required_dimensions, "required_dimensions")
        _non_negative(self.minimum_test_references, "minimum_test_references")
        _non_negative(self.minimum_evidence_count, "minimum_evidence_count")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchPolicyCheck:
    """One independently inspectable workbench threshold result."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("policy check passed must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchGate:
    """Aggregate policy decision with a conserved independent check list."""

    report_address: str
    policy_address: str
    checks: tuple[ModuleWorkbenchPolicyCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.report_address, "report_address")
        _text(self.policy_address, "policy_address")
        _text(self.content_address, "content_address")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_POLICY_MAX_CHECKS:
            raise ValidationError("workbench gate checks are missing or exceed the limit")
        check_ids = tuple(item.check_id for item in self.checks)
        if check_ids != tuple(sorted(check_ids)) or len(set(check_ids)) != len(check_ids):
            raise ValidationError("workbench gate checks must be sorted and unique")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("workbench gate acceptance does not conserve checks")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_POLICY_VERSION,
            "boundary": MODULE_WORKBENCH_POLICY_BOUNDARY,
            "report_address": self.report_address,
            "policy_address": self.policy_address,
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_policy(value: ModuleWorkbenchPolicy) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-policy")


def address_module_workbench_policy_check(value: ModuleWorkbenchPolicyCheck) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-policy-check")


__all__ = [
    "MODULE_WORKBENCH_POLICY_BOUNDARY",
    "MODULE_WORKBENCH_POLICY_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_POLICY_MAX_CHECKS",
    "MODULE_WORKBENCH_POLICY_MAX_LIMIT",
    "MODULE_WORKBENCH_POLICY_VERSION",
    "ModuleWorkbenchGate",
    "ModuleWorkbenchPolicy",
    "ModuleWorkbenchPolicyCheck",
    "address_module_workbench_policy",
    "address_module_workbench_policy_check",
]

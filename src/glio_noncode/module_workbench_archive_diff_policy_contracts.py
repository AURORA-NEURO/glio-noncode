"""Typed policy and gate contracts for portable workbench comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_VERSION = "module-workbench-archive-diff-policy-v1"
MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_BOUNDARY = "public_aggregate_module_workbench_archive_diff_policy"
MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_CHECKS = 32
MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_LIMIT = 512
MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_DEFAULT_LIMIT = 50


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _delta(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -1.0 <= value <= 1.0:
        raise ValidationError(f"{field} must be between -1 and one")
    return float(value)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveDiffPolicy:
    """Immutable thresholds for admitting a candidate archive comparison."""

    policy_id: str
    maximum_added_count: int
    maximum_changed_count: int
    maximum_removed_count: int
    maximum_regression_count: int
    maximum_task_delta: int
    minimum_score_delta: float
    require_accepted_inputs: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_id, "policy_id")
        for field in (
            "maximum_added_count",
            "maximum_changed_count",
            "maximum_removed_count",
            "maximum_regression_count",
            "maximum_task_delta",
        ):
            _count(getattr(self, field), field)
        _delta(self.minimum_score_delta, "minimum_score_delta")
        if not isinstance(self.require_accepted_inputs, bool):
            raise ValidationError("require_accepted_inputs must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchArchiveDiffPolicyCheck:
    """One independently inspectable archive-diff policy result."""

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
class ModuleWorkbenchArchiveDiffPolicyGate:
    """A conserved policy decision over one portable archive comparison."""

    diff_address: str
    policy: ModuleWorkbenchArchiveDiffPolicy
    checks: tuple[ModuleWorkbenchArchiveDiffPolicyCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_address, "diff_address")
        if not isinstance(self.policy, ModuleWorkbenchArchiveDiffPolicy):
            raise ValidationError("archive-diff gate policy must be typed")
        _text(self.content_address, "content_address")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_CHECKS:
            raise ValidationError("archive-diff gate checks are missing or exceed the limit")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("archive-diff gate checks must be sorted and unique")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("archive-diff gate acceptance does not conserve checks")

    @property
    def policy_address(self) -> str:
        return self.policy.content_address

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_VERSION,
            "boundary": MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_BOUNDARY,
            "diff_address": self.diff_address,
            "policy": self.policy.to_dict(),
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


def address_module_workbench_archive_diff_policy(
    value: ModuleWorkbenchArchiveDiffPolicy,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-archive-diff-policy")


def address_module_workbench_archive_diff_policy_check(
    value: ModuleWorkbenchArchiveDiffPolicyCheck,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-archive-diff-policy-check")


def address_module_workbench_archive_diff_policy_gate(
    value: ModuleWorkbenchArchiveDiffPolicyGate,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix="module-workbench-archive-diff-policy-gate")


__all__ = [
    "MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_BOUNDARY",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_CHECKS",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_LIMIT",
    "MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_VERSION",
    "ModuleWorkbenchArchiveDiffPolicy",
    "ModuleWorkbenchArchiveDiffPolicyCheck",
    "ModuleWorkbenchArchiveDiffPolicyGate",
    "address_module_workbench_archive_diff_policy",
    "address_module_workbench_archive_diff_policy_check",
    "address_module_workbench_archive_diff_policy_gate",
]

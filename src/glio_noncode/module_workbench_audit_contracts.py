"""Contracts for independent audits of module workbench reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_AUDIT_VERSION = "module-workbench-audit-v1"
MODULE_WORKBENCH_AUDIT_BOUNDARY = "public_aggregate_module_workbench_audit"
MODULE_WORKBENCH_AUDIT_MAX_CHECKS = 128
MODULE_WORKBENCH_AUDIT_MAX_LIMIT = 512
MODULE_WORKBENCH_AUDIT_DEFAULT_LIMIT = 50


class ModuleWorkbenchAuditPlane(StrEnum):
    """Independent audit dimensions for a workbench report."""

    IDENTITY = "identity"
    CONSERVATION = "conservation"
    COVERAGE = "coverage"
    SORTING = "sorting"
    TASKS = "tasks"
    FAMILIES = "families"
    BOUNDARY = "boundary"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchAuditCheck:
    """One independently recomputable workbench invariant."""

    check_id: str
    plane: ModuleWorkbenchAuditPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("audit check passed must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchAudit:
    """Independent audit result for a typed module workbench report."""

    report_address: str
    checks: tuple[ModuleWorkbenchAuditCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.report_address, "report_address")
        _text(self.content_address, "content_address")
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_AUDIT_MAX_CHECKS:
            raise ValidationError("workbench audit checks are missing or exceed the limit")
        keys = tuple(item.check_id for item in self.checks)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValidationError("workbench audit checks must be sorted and unique")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("workbench audit acceptance does not conserve checks")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_AUDIT_VERSION,
            "boundary": MODULE_WORKBENCH_AUDIT_BOUNDARY,
            "report_address": self.report_address,
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_audit_check(value: ModuleWorkbenchAuditCheck) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-audit-check")


__all__ = [
    "MODULE_WORKBENCH_AUDIT_BOUNDARY",
    "MODULE_WORKBENCH_AUDIT_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_AUDIT_MAX_CHECKS",
    "MODULE_WORKBENCH_AUDIT_MAX_LIMIT",
    "MODULE_WORKBENCH_AUDIT_VERSION",
    "ModuleWorkbenchAudit",
    "ModuleWorkbenchAuditCheck",
    "ModuleWorkbenchAuditPlane",
    "address_module_workbench_audit_check",
]

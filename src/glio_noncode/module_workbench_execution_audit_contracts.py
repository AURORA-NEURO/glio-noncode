"""Typed contracts for independent execution-ledger audits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_AUDIT_VERSION = "module-workbench-execution-audit-v1"
MODULE_WORKBENCH_EXECUTION_AUDIT_BOUNDARY = "public_aggregate_module_workbench_execution_audit"
MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_CHECKS = 32
MODULE_WORKBENCH_EXECUTION_AUDIT_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_LIMIT = 512


class ModuleWorkbenchExecutionAuditPlane(StrEnum):
    """Independent invariant families evaluated by the audit."""

    ADDRESSES = "addresses"
    EVENT_SEQUENCE = "event_sequence"
    TRANSITION_GRAPH = "transition_graph"
    PREREQUISITES = "prerequisites"
    EVIDENCE = "evidence"
    STATE_COUNTS = "state_counts"
    CONSERVATION = "conservation"
    BOUNDARY_KEYS = "boundary_keys"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionAuditCheck:
    """One independently computed execution invariant."""

    check_id: str
    plane: ModuleWorkbenchExecutionAuditPlane
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchExecutionAuditPlane):
            raise ValidationError("plane must be a supported execution audit plane")
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_audit_check(
    value: ModuleWorkbenchExecutionAuditCheck,
) -> str:
    """Return the exact address for an audit check."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-audit-check")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionAudit:
    """Conserved independent audit over an execution ledger."""

    ledger_address: str
    checks: tuple[ModuleWorkbenchExecutionAuditCheck, ...]
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.ledger_address, "ledger_address")
        if len(self.checks) > MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_CHECKS:
            raise ValidationError("execution audit check limit exceeded")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("execution audit checks must be sorted and unique")
        _count(self.check_count, "check_count")
        _count(self.passed_count, "passed_count")
        _count(self.failed_count, "failed_count")
        if self.check_count != len(self.checks):
            raise ValidationError("execution audit check count does not conserve rows")
        if self.passed_count + self.failed_count != self.check_count:
            raise ValidationError("execution audit pass/fail counts do not conserve rows")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("execution audit passed count is inconsistent")
        if not isinstance(self.accepted, bool):
            raise ValidationError("accepted must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_AUDIT_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_AUDIT_BOUNDARY,
            "ledger_address": self.ledger_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_audit(
    value: ModuleWorkbenchExecutionAudit,
) -> str:
    """Return the exact address for the complete audit."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-audit")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_AUDIT_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_AUDIT_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_CHECKS",
    "MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_AUDIT_VERSION",
    "ModuleWorkbenchExecutionAudit",
    "ModuleWorkbenchExecutionAuditCheck",
    "ModuleWorkbenchExecutionAuditPlane",
    "address_module_workbench_execution_audit",
    "address_module_workbench_execution_audit_check",
]

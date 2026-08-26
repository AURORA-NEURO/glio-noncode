"""Typed contracts for independent lineage graph audits."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION = "module-certification-lineage-audit-v1"
MODULE_CERTIFICATION_LINEAGE_AUDIT_BOUNDARY = "public_aggregate_module_certification_lineage_audit"
MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_CHECKS = 32
MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_LIMIT = 512


class CertificationLineageAuditPlane(StrEnum):
    """Independent audit plane for a lineage assertion."""

    IDENTITY = "identity"
    GRAPH = "graph"
    COVERAGE = "coverage"
    PUBLIC = "public"
    LIMITS = "limits"


def _text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ModuleCertificationLineageAuditCheck:
    """One deterministic assertion over a lineage graph."""

    check_id: str
    plane: CertificationLineageAuditPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("check_id", "detail", "content_address"):
            _text(getattr(self, field), field)
        if not isinstance(self.passed, bool):
            raise ValidationError("lineage audit passed must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleCertificationLineageAudit:
    """Complete independent audit result for one lineage graph."""

    lineage_address: str
    checks: tuple[ModuleCertificationLineageAuditCheck, ...]
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.lineage_address, "lineage_address")
        _text(self.content_address, "content_address")
        if self.passed_count < 0 or self.failed_count < 0:
            raise ValidationError("lineage audit counts cannot be negative")
        if self.passed_count + self.failed_count != len(self.checks):
            raise ValidationError("lineage audit counts do not conserve checks")
        if not self.checks:
            raise ValidationError("lineage audit requires checks")
        if tuple(item.check_id for item in self.checks) != tuple(
            sorted(item.check_id for item in self.checks)
        ):
            raise ValidationError("lineage audit checks must be sorted")
        if len(self.checks) > MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_CHECKS:
            raise ValidationError("lineage audit check limit exceeded")

    @property
    def check_count(self) -> int:
        return len(self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION,
            "boundary": MODULE_CERTIFICATION_LINEAGE_AUDIT_BOUNDARY,
            "lineage_address": self.lineage_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            result["checks"] = [item.to_dict() for item in self.checks]
        return result


def address_module_certification_lineage_audit_check(
    value: ModuleCertificationLineageAuditCheck,
) -> str:
    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return _address(body, "module-certification-lineage-audit-check")


__all__ = [
    "CertificationLineageAuditPlane",
    "MODULE_CERTIFICATION_LINEAGE_AUDIT_BOUNDARY",
    "MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_CHECKS",
    "MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_LIMIT",
    "MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION",
    "ModuleCertificationLineageAudit",
    "ModuleCertificationLineageAuditCheck",
    "address_module_certification_lineage_audit_check",
]

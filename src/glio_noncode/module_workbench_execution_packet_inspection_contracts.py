"""Contracts for reviewing packet verification and release findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_VERSION = (
    "module-workbench-execution-packet-inspection-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_inspection"
)
MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_FINDINGS = 128


class ModuleWorkbenchExecutionPacketInspectionSeverity(StrEnum):
    """Review severity assigned to one normalized finding."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ModuleWorkbenchExecutionPacketInspectionPlane(StrEnum):
    """Source plane retained in the review projection."""

    MANIFEST = "manifest"
    PATH = "path"
    BYTES = "bytes"
    LINKAGE = "linkage"
    SEMANTIC = "semantic"
    PUBLIC = "public"
    REPLAY = "replay"
    STORAGE = "storage"
    RELEASE = "release"


class ModuleWorkbenchExecutionPacketInspectionState(StrEnum):
    """Aggregate state of the normalized review."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketInspectionFinding:
    """One stable review finding copied from a packet check."""

    finding_id: str
    plane: ModuleWorkbenchExecutionPacketInspectionPlane
    severity: ModuleWorkbenchExecutionPacketInspectionSeverity
    code: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.finding_id, "finding_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchExecutionPacketInspectionPlane):
            raise ValidationError("inspection plane is invalid")
        if not isinstance(self.severity, ModuleWorkbenchExecutionPacketInspectionSeverity):
            raise ValidationError("inspection severity is invalid")
        _text(self.code, "code", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("inspection finding result must be boolean")
        _text(self.detail, "detail", 4096)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_execution_packet_inspection_finding(
    value: ModuleWorkbenchExecutionPacketInspectionFinding,
) -> str:
    """Address one finding without a filesystem path or clock value."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-inspection-finding")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketInspection:
    """Addressed, bounded review projection for one execution packet."""

    packet_id: str
    packet_address: str
    verification_address: str
    replay_address: str
    release_address: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    findings: tuple[ModuleWorkbenchExecutionPacketInspectionFinding, ...]
    state: ModuleWorkbenchExecutionPacketInspectionState
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "packet_id",
            "packet_address",
            "verification_address",
            "replay_address",
            "release_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        _count(self.artifact_count, "artifact_count")
        _count(self.check_count, "check_count")
        _count(self.passed_check_count, "passed_check_count")
        _count(self.failed_check_count, "failed_check_count")
        if self.passed_check_count + self.failed_check_count != self.check_count:
            raise ValidationError("inspection check counts do not conserve")
        if (
            not self.findings
            or len(self.findings) > MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_FINDINGS
        ):
            raise ValidationError("inspection findings are incomplete or excessive")
        ids = tuple(item.finding_id for item in self.findings)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("inspection findings must be sorted and unique")
        if not isinstance(self.state, ModuleWorkbenchExecutionPacketInspectionState):
            raise ValidationError("inspection state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("inspection acceptance must be boolean")
        if self.accepted != (self.state is ModuleWorkbenchExecutionPacketInspectionState.ACCEPTED):
            raise ValidationError("inspection state and acceptance do not agree")
        if self.accepted != all(item.passed for item in self.findings):
            raise ValidationError("inspection acceptance does not conserve findings")

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def passed_finding_count(self) -> int:
        return sum(item.passed for item in self.findings)

    @property
    def failed_finding_count(self) -> int:
        return sum(not item.passed for item in self.findings)

    @property
    def critical_count(self) -> int:
        return sum(
            item.severity is ModuleWorkbenchExecutionPacketInspectionSeverity.CRITICAL
            and not item.passed
            for item in self.findings
        )

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_VERSION,
            "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY,
            "packet_id": self.packet_id,
            "packet_address": self.packet_address,
            "verification_address": self.verification_address,
            "replay_address": self.replay_address,
            "release_address": self.release_address,
            "artifact_count": self.artifact_count,
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "finding_count": self.finding_count,
            "passed_finding_count": self.passed_finding_count,
            "failed_finding_count": self.failed_finding_count,
            "critical_count": self.critical_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def address_module_workbench_execution_packet_inspection(
    value: ModuleWorkbenchExecutionPacketInspection,
) -> str:
    """Address the inspection projection and all of its findings."""

    body = {key: item for key, item in value.to_dict().items() if key != "content_address"}
    return content_hash(body, prefix="module-workbench-execution-packet-inspection")


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_FINDINGS",
    "MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_MAX_LIMIT",
    "MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_VERSION",
    "ModuleWorkbenchExecutionPacketInspection",
    "ModuleWorkbenchExecutionPacketInspectionFinding",
    "ModuleWorkbenchExecutionPacketInspectionPlane",
    "ModuleWorkbenchExecutionPacketInspectionSeverity",
    "ModuleWorkbenchExecutionPacketInspectionState",
    "address_module_workbench_execution_packet_inspection",
    "address_module_workbench_execution_packet_inspection_finding",
]

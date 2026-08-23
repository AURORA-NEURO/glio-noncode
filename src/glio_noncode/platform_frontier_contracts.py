"""Contracts for the Domain 16 C01-C04 platform-control frontier.

This module defines a bounded, aggregate-only execution surface for mission
planning, workflow compilation, typed tool contracts, and isolated execution.
The contracts keep intended use, role scope, resource boundaries, provenance,
and failure state explicit. They do not produce scientific measurements or
clinical decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


PLATFORM_FRONTIER_CONTEXT_KEY = "public_platform|research|aggregate|local|v1"
PLATFORM_FRONTIER_BOUNDARY = "public_aggregate_platform_runtime"
PLATFORM_FRONTIER_VERSION = "2026.08.d16-c01-c04.v1"


class PlatformFrontierOperation(StrEnum):
    """The four W1 platform-control operations."""

    MISSION_PLANNER = "mission_planner"
    WORKFLOW_COMPILER = "workflow_compiler"
    TYPED_TOOL_REGISTRY = "typed_tool_registry"
    EXECUTION_SANDBOX = "execution_sandbox"


class PlatformFrontierRole(StrEnum):
    """Fixture role used to keep positive and control paths separate."""

    POSITIVE = "positive"
    CONTROL = "control"


class PlatformFrontierState(StrEnum):
    """Shared state vocabulary for planning and execution receipts."""

    COMPLETED = "completed"
    READY = "ready"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    ADMITTED = "admitted"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class PlatformFrontierSourceReceipt:
    """Public aggregate source receipt for one operational fixture family."""

    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("platform source URI must use HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("platform source address must use SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierRecord:
    """One typed operation request with an expected operational boundary."""

    record_id: str
    operation: PlatformFrontierOperation
    role: PlatformFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: PlatformFrontierState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("platform record requires source receipts")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("platform record address must use SHA-256")
        if len(self.expected_issue_codes) != len(set(self.expected_issue_codes)):
            raise ValidationError("platform issue codes must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierFixture:
    """Complete four-row-per-operation aggregate platform fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[PlatformFrontierSourceReceipt, ...]
    records: tuple[PlatformFrontierRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[PlatformFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is PlatformFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[PlatformFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is PlatformFrontierRole.CONTROL)

    def by_operation(self, operation: PlatformFrontierOperation | str) -> tuple[PlatformFrontierRecord, ...]:
        value = operation.value if isinstance(operation, PlatformFrontierOperation) else str(operation)
        return tuple(item for item in self.records if item.operation.value == value)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierExecution:
    """Observed operation receipt projected without raw request internals."""

    record_id: str
    operation: PlatformFrontierOperation
    role: PlatformFrontierRole
    state: PlatformFrontierState
    accepted: bool
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierCheck:
    """One retained assertion over an observed platform receipt."""

    check_id: str
    record_id: str | None
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierEvaluation:
    """All row executions and assertions for the four operations."""

    fixture_id: str
    executions: tuple[PlatformFrontierExecution, ...]
    checks: tuple[PlatformFrontierCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def addressed_platform_check(
    check_id: str,
    record_id: str | None,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> PlatformFrontierCheck:
    """Build a deterministically addressed check."""

    body = {
        "check_id": check_id,
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return PlatformFrontierCheck(**body, content_address=content_hash(body))


__all__ = [
    "PLATFORM_FRONTIER_BOUNDARY",
    "PLATFORM_FRONTIER_CONTEXT_KEY",
    "PLATFORM_FRONTIER_VERSION",
    "PlatformFrontierCheck",
    "PlatformFrontierEvaluation",
    "PlatformFrontierExecution",
    "PlatformFrontierFixture",
    "PlatformFrontierOperation",
    "PlatformFrontierRecord",
    "PlatformFrontierRole",
    "PlatformFrontierSourceReceipt",
    "PlatformFrontierState",
    "addressed_platform_check",
]

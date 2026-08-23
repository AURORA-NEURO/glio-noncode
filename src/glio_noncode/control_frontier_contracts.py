"""Contracts for the Domain 16 C05-C12 control/runtime frontier.

The package is an aggregate-only execution surface.  Every row carries an
exact context, declared source receipts, an expected boundary, and a content
address.  Positive rows exercise the accepted path for one capability while
controls deliberately exercise missing, incompatible, foreign, or blocked
inputs.  The contracts never infer a scientific or clinical conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


CONTROL_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|untreated"
CONTROL_FRONTIER_BOUNDARY = "public_aggregate_control_runtime"
CONTROL_FRONTIER_VERSION = "2026.08.d16-c05-c12.v1"


class ControlFrontierOperation(StrEnum):
    """The eight capability surfaces in this frontier package."""

    POLICY_CLAIM_GATE = "policy_claim_gate"
    BUDGET_RESOURCE_SCHEDULER = "budget_resource_scheduler"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    HUMAN_REVIEW_ROUTER = "human_review_router"
    EXECUTION_LEDGER = "execution_ledger"
    MODEL_REGISTRY = "model_registry"
    DATA_REFERENCE_REGISTRY = "data_reference_registry"
    DRIFT_OOD_MONITOR = "drift_ood_monitor"


class ControlFrontierRole(StrEnum):
    """Fixture role retained in every evaluation projection."""

    POSITIVE = "positive"
    CONTROL = "control"


class ControlFrontierState(StrEnum):
    """Shared state vocabulary for operation receipts."""

    SUPPORTED = "supported"
    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    SELECTED = "selected"
    ABSTAINED = "abstained"
    EMPTY = "empty"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    COMPATIBLE = "compatible"
    REVIEW_REQUIRED = "review_required"
    OUT_OF_DOMAIN = "out_of_domain"
    WATCH = "watch"
    DRIFT = "drift"


@dataclass(frozen=True, slots=True)
class ControlFrontierSourceReceipt:
    """One public source receipt bound to aggregate operational data."""

    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("control frontier source URI must use HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("control frontier source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierRecord:
    """One operation payload with a declared expected boundary."""

    record_id: str
    operation: ControlFrontierOperation
    role: ControlFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: ControlFrontierState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("control frontier record requires source receipts")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("control frontier record address must be SHA-256")
        if len(self.expected_issue_codes) != len(set(self.expected_issue_codes)):
            raise ValidationError("control frontier issue codes must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierFixture:
    """Complete four-row-per-operation public aggregate."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ControlFrontierSourceReceipt, ...]
    records: tuple[ControlFrontierRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[ControlFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ControlFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[ControlFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ControlFrontierRole.CONTROL)

    def by_operation(self, operation: ControlFrontierOperation | str) -> tuple[ControlFrontierRecord, ...]:
        selected = operation.value if isinstance(operation, ControlFrontierOperation) else str(operation)
        return tuple(item for item in self.records if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierExecution:
    """One functional operation result with issue and acceptance accounting."""

    record_id: str
    operation: ControlFrontierOperation
    role: ControlFrontierRole
    state: ControlFrontierState
    accepted: bool
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierCheck:
    """One retained assertion over an observed operation receipt."""

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
class ControlFrontierEvaluation:
    """All executions and checks for the eight-operation aggregate."""

    fixture_id: str
    executions: tuple[ControlFrontierExecution, ...]
    checks: tuple[ControlFrontierCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def by_operation(self, operation: ControlFrontierOperation | str) -> tuple[ControlFrontierExecution, ...]:
        selected = operation.value if isinstance(operation, ControlFrontierOperation) else str(operation)
        return tuple(item for item in self.executions if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_checks": self.passed_checks, "failed_check_ids": list(self.failed_check_ids)}


def addressed_control_frontier_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    record_id: str | None = None,
) -> ControlFrontierCheck:
    """Create an addressed check without dropping the observed value."""

    body = {
        "check_id": check_id,
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ControlFrontierCheck(**body, content_address=content_hash(body))


__all__ = [
    "CONTROL_FRONTIER_BOUNDARY",
    "CONTROL_FRONTIER_CONTEXT_KEY",
    "CONTROL_FRONTIER_VERSION",
    "ControlFrontierCheck",
    "ControlFrontierExecution",
    "ControlFrontierFixture",
    "ControlFrontierOperation",
    "ControlFrontierRecord",
    "ControlFrontierRole",
    "ControlFrontierSourceReceipt",
    "ControlFrontierState",
    "ControlFrontierEvaluation",
    "addressed_control_frontier_check",
]

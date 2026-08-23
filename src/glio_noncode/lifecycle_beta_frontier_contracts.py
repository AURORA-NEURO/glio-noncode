"""Contracts for the Domain 14 C05-C12 lifecycle depth tranche.

The contracts keep eight review surfaces in one bounded aggregate package.  A
record contains the operation payload, expected state, explicit controls, and
the source receipts needed to reproduce the result.  Nothing in this module
promotes a scientific claim or hides an unresolved review condition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|core|untreated"
LIFECYCLE_BETA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
LIFECYCLE_BETA_FRONTIER_VERSION = "2026.08.d14-c05-c12.v1"


class LifecycleBetaFrontierOperation(StrEnum):
    """The eight operational capabilities covered by this tranche."""

    TIER_ADJUDICATION = "tier_adjudication"
    PROVENANCE_LINEAGE = "provenance_lineage"
    UNCERTAINTY_LEDGER = "uncertainty_ledger"
    REVIEW_ROUTING = "review_routing"
    BLINDED_ADJUDICATION = "blinded_adjudication"
    COMMENT_CHANGE_LOG = "comment_change_log"
    RELEASE_DECISION = "release_decision"
    EVIDENCE_DELTA = "evidence_delta"


class LifecycleBetaFrontierRole(StrEnum):
    """Fixture role; only the positive row is eligible for acceptance."""

    POSITIVE = "positive"
    CONTROL = "control"


class LifecycleBetaFrontierState(StrEnum):
    """State vocabulary retained by every execution receipt."""

    SUPPORTED = "supported"
    REVIEW_REQUIRED = "review_required"
    PARTIAL = "partial"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    READY_FOR_REVIEW = "ready_for_review"
    ADJUDICATED = "adjudicated"
    SPLIT_DECISION = "split_decision"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierSourceReceipt:
    """One public source receipt bound to an aggregate fixture."""

    source_id: str
    title: str
    uri: str
    access_note: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "access_note", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("lifecycle frontier source URI must use HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("lifecycle frontier source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRecord:
    """One operation payload and its expected deterministic boundary."""

    record_id: str
    operation: LifecycleBetaFrontierOperation
    role: LifecycleBetaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: LifecycleBetaFrontierState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("lifecycle frontier record requires source receipts")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("lifecycle frontier record address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierFixture:
    """The complete four-row-per-operation public aggregate."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[LifecycleBetaFrontierSourceReceipt, ...]
    records: tuple[LifecycleBetaFrontierRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[LifecycleBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LifecycleBetaFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[LifecycleBetaFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is LifecycleBetaFrontierRole.CONTROL)

    def by_operation(self, operation: LifecycleBetaFrontierOperation | str) -> tuple[LifecycleBetaFrontierRecord, ...]:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.records if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierExecution:
    """One replayable operation output with issue and acceptance accounting."""

    record_id: str
    operation: LifecycleBetaFrontierOperation
    role: LifecycleBetaFrontierRole
    state: LifecycleBetaFrontierState
    accepted: bool
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierCheck:
    """A named fixture assertion retained in the evaluation receipt."""

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
class LifecycleBetaFrontierEvaluation:
    """All executions and checks for the C05-C12 fixture."""

    fixture_id: str
    executions: tuple[LifecycleBetaFrontierExecution, ...]
    checks: tuple[LifecycleBetaFrontierCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def by_operation(self, operation: LifecycleBetaFrontierOperation | str) -> tuple[LifecycleBetaFrontierExecution, ...]:
        selected = operation.value if isinstance(operation, LifecycleBetaFrontierOperation) else str(operation)
        return tuple(item for item in self.executions if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_checks": self.passed_checks, "failed_check_ids": list(self.failed_check_ids)}


def addressed_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    record_id: str | None = None,
) -> LifecycleBetaFrontierCheck:
    """Create a content-addressed check without dropping the observed value."""

    body = {
        "check_id": check_id,
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return LifecycleBetaFrontierCheck(**body, content_address=content_hash(body))


__all__ = [
    "LIFECYCLE_BETA_FRONTIER_BOUNDARY",
    "LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY",
    "LIFECYCLE_BETA_FRONTIER_VERSION",
    "LifecycleBetaFrontierCheck",
    "LifecycleBetaFrontierEvaluation",
    "LifecycleBetaFrontierExecution",
    "LifecycleBetaFrontierFixture",
    "LifecycleBetaFrontierOperation",
    "LifecycleBetaFrontierRecord",
    "LifecycleBetaFrontierRole",
    "LifecycleBetaFrontierSourceReceipt",
    "LifecycleBetaFrontierState",
    "addressed_check",
]

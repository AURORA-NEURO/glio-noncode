"""Typed contracts for the D13 C09-C12 planning frontier.

The frontier is intentionally explicit about what is being planned.  A model
system can satisfy a declared context gate without proving fidelity.  A guide
row can be adapted without proving activity.  A control plan can be
reproducible without guaranteeing balance.  A power estimate can expose
assumptions without becoming a statistical or clinical claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty


PLANNING_FRONTIER_VERSION = "2026.08.d13-c09-c12.v1"
PLANNING_FRONTIER_CONTEXT_KEY = (
    "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
)
PLANNING_FRONTIER_FOREIGN_CONTEXT = (
    "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
)
PLANNING_FRONTIER_BOUNDARY = "public_aggregate_planning_evidence"


class PlanningOperation(StrEnum):
    MODEL_ELIGIBILITY = "model_system_eligibility"
    GUIDE_OLIGO = "guide_oligo_adaptation"
    CONTROLS_RANDOMIZATION = "controls_randomization"
    POWER_REPLICATION = "power_replication"


class PlanningRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class PlanningState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    REVIEW = "review"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class PlanningSourceReceipt:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "scope", "version", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("planning source receipts require HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("planning source receipts require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningRecord:
    record_id: str
    capability: str
    operation: PlanningOperation
    role: PlanningRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: PlanningState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "capability", "context_key", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValueError("planning records require public source joins")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("planning records require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[PlanningSourceReceipt, ...]
    records: tuple[PlanningRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[PlanningRecord, ...]:
        return tuple(item for item in self.records if item.role is PlanningRole.POSITIVE)

    @property
    def control_records(self) -> tuple[PlanningRecord, ...]:
        return tuple(item for item in self.records if item.role is PlanningRole.CONTROL)

    @property
    def operations(self) -> tuple[PlanningOperation, ...]:
        return tuple(dict.fromkeys(item.operation for item in self.records))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningOperationResult:
    operation: PlanningOperation
    state: PlanningState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningExecution:
    record_id: str
    capability: str
    operation: PlanningOperation
    role: PlanningRole
    expected_state: PlanningState
    observed_state: PlanningState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningCheck:
    check_id: str
    record_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningEvaluation:
    fixture_id: str
    executions: tuple[PlanningExecution, ...]
    checks: tuple[PlanningCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def make_planning_check(
    check_id: str,
    record_id: str,
    plane: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> PlanningCheck:
    body = {
        "check_id": check_id,
        "record_id": record_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return PlanningCheck(**body, content_address=content_hash(body))


__all__ = [
    "PLANNING_FRONTIER_BOUNDARY",
    "PLANNING_FRONTIER_CONTEXT_KEY",
    "PLANNING_FRONTIER_FOREIGN_CONTEXT",
    "PLANNING_FRONTIER_VERSION",
    "PlanningCheck",
    "PlanningExecution",
    "PlanningFixture",
    "PlanningOperation",
    "PlanningOperationResult",
    "PlanningRecord",
    "PlanningRole",
    "PlanningSourceReceipt",
    "PlanningState",
    "PlanningEvaluation",
    "make_planning_check",
]

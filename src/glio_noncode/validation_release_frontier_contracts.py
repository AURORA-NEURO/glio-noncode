"""Contracts for the D13 C13-C16 validation-release frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty

VALIDATION_RELEASE_FRONTIER_VERSION = "2026.08.d13-c13-c16.v1"
VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
VALIDATION_RELEASE_FRONTIER_BOUNDARY = "public_aggregate_validation_release_planning"


class ValidationReleaseOperation(StrEnum):
    OFF_TARGET_RISK = "off_target_risk"
    VALUE_OF_INFORMATION = "value_of_information"
    EXPERIMENT_PACKAGE = "experiment_package"
    CLAIM_UPDATE = "claim_update"


class ValidationReleaseRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class ValidationReleaseState(StrEnum):
    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"
    PACKAGED = "packaged"
    UPDATED = "updated"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class ValidationReleaseSourceReceipt:
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
            raise ValueError("validation-release sources must use HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation-release source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseRecord:
    record_id: str
    operation: ValidationReleaseOperation
    role: ValidationReleaseRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: ValidationReleaseState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ValidationReleaseSourceReceipt, ...]
    records: tuple[ValidationReleaseRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[ValidationReleaseRecord, ...]:
        return tuple(item for item in self.records if item.role == ValidationReleaseRole.POSITIVE)

    @property
    def control_records(self) -> tuple[ValidationReleaseRecord, ...]:
        return tuple(item for item in self.records if item.role == ValidationReleaseRole.CONTROL)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseOperationResult:
    operation: ValidationReleaseOperation
    state: ValidationReleaseState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseExecution:
    record_id: str
    operation: ValidationReleaseOperation
    role: ValidationReleaseRole
    expected_state: ValidationReleaseState
    observed_state: ValidationReleaseState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseCheck:
    check_id: str
    record_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseEvaluation:
    fixture_id: str
    executions: tuple[ValidationReleaseExecution, ...]
    checks: tuple[ValidationReleaseCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def make_validation_release_check(check_id: str, record_id: str, passed: bool, observed: Any, required: Any, detail: str) -> ValidationReleaseCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return ValidationReleaseCheck(**body, content_address=content_hash(body))


__all__ = [
    "VALIDATION_RELEASE_FRONTIER_BOUNDARY",
    "VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY",
    "VALIDATION_RELEASE_FRONTIER_FOREIGN_CONTEXT",
    "VALIDATION_RELEASE_FRONTIER_VERSION",
    "ValidationReleaseCheck",
    "ValidationReleaseExecution",
    "ValidationReleaseFixture",
    "ValidationReleaseOperation",
    "ValidationReleaseOperationResult",
    "ValidationReleaseRecord",
    "ValidationReleaseRole",
    "ValidationReleaseSourceReceipt",
    "ValidationReleaseState",
    "ValidationReleaseEvaluation",
    "make_validation_release_check",
]

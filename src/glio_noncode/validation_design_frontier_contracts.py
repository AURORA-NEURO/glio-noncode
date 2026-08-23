"""Contracts for the D13 C01-C04 validation-design frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty

VALIDATION_DESIGN_FRONTIER_VERSION = "2026.08.d13-c01-c04.v1"
VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
VALIDATION_DESIGN_FRONTIER_BOUNDARY = "public_aggregate_validation_design_planning"


class ValidationDesignOperation(StrEnum):
    GAP_ANALYSIS = "gap_analysis"
    ASSAY_ELIGIBILITY = "assay_eligibility"
    MPRA_PACKAGE = "mpra_package"
    STARRSEQ_PACKAGE = "starrseq_package"


class ValidationDesignRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class ValidationDesignState(StrEnum):
    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"
    ROUTED = "routed"
    PACKAGED = "packaged"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class ValidationDesignSourceReceipt:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("source_id", "title", "uri", "scope", "version", "content_address"):
            require_non_empty(str(getattr(self, field)), field)
        if not self.uri.startswith("https://"):
            raise ValueError("validation-design receipts require HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation-design receipts require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignRecord:
    record_id: str
    capability: str
    operation: ValidationDesignOperation
    role: ValidationDesignRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: ValidationDesignState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.capability, "capability")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.notes, "notes")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("validation-design records require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ValidationDesignSourceReceipt, ...]
    records: tuple[ValidationDesignRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[ValidationDesignRecord, ...]:
        return tuple(row for row in self.records if row.role == ValidationDesignRole.POSITIVE)

    @property
    def control_records(self) -> tuple[ValidationDesignRecord, ...]:
        return tuple(row for row in self.records if row.role == ValidationDesignRole.CONTROL)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignOperationResult:
    operation: ValidationDesignOperation
    state: ValidationDesignState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignExecution:
    record_id: str
    capability: str
    operation: ValidationDesignOperation
    role: ValidationDesignRole
    expected_state: ValidationDesignState
    observed_state: ValidationDesignState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignCheck:
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
class ValidationDesignEvaluation:
    fixture_id: str
    executions: tuple[ValidationDesignExecution, ...]
    checks: tuple[ValidationDesignCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def make_validation_design_check(check_id: str, record_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> ValidationDesignCheck:
    body = {"check_id": check_id, "record_id": record_id, "plane": plane, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return ValidationDesignCheck(**body, content_address=content_hash(body))


__all__ = ["VALIDATION_DESIGN_FRONTIER_BOUNDARY", "VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY", "VALIDATION_DESIGN_FRONTIER_FOREIGN_CONTEXT", "VALIDATION_DESIGN_FRONTIER_VERSION", "ValidationDesignCheck", "ValidationDesignExecution", "ValidationDesignFixture", "ValidationDesignOperation", "ValidationDesignOperationResult", "ValidationDesignRecord", "ValidationDesignRole", "ValidationDesignSourceReceipt", "ValidationDesignState", "ValidationDesignEvaluation", "make_validation_design_check"]

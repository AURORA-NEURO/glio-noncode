"""Contracts for the D13 validation-design closure layer.

The core validation-design bundle is intentionally kept stable.  These
contracts add independent, addressable projections over that bundle so a
reviewer can inspect boundary, indexes, joins, summaries, certification, and
runtime telemetry without changing the original 27-artifact handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

VALIDATION_DESIGN_CLOSURE_VERSION = "validation-design-closure-v1"
VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION = "validation-design-closure-schema-v1"
VALIDATION_DESIGN_CLOSURE_RUNTIME_VERSION = "validation-design-closure-runtime-v1"
VALIDATION_DESIGN_CLOSURE_RECONCILIATION_VERSION = "validation-design-closure-reconciliation-v1"
VALIDATION_DESIGN_CLOSURE_CERTIFICATION_VERSION = "validation-design-closure-certification-v1"
VALIDATION_DESIGN_CLOSURE_BOUNDARY = "public_aggregate_validation_design_closure_handoff"
VALIDATION_DESIGN_CLOSURE_CHECK_PREFIX = "validation-design-closure-check"
VALIDATION_DESIGN_CLOSURE_DEFAULT_LIMIT = 50
VALIDATION_DESIGN_CLOSURE_MAX_LIMIT = 500

VALIDATION_DESIGN_CLOSURE_ARTIFACT_COUNT = 27
VALIDATION_DESIGN_CLOSURE_SOURCE_COUNT = 5
VALIDATION_DESIGN_CLOSURE_RECORD_COUNT = 16
VALIDATION_DESIGN_CLOSURE_OPERATION_COUNT = 4
VALIDATION_DESIGN_CLOSURE_EXECUTION_COUNT = 16
VALIDATION_DESIGN_CLOSURE_EVALUATION_CHECK_COUNT = 80
VALIDATION_DESIGN_CLOSURE_STAGE_COUNT = 79
VALIDATION_DESIGN_CLOSURE_PLANE_COUNT = 57
VALIDATION_DESIGN_CLOSURE_CERTIFICATION_DOMAIN_COUNT = 8
VALIDATION_DESIGN_CLOSURE_CERTIFICATION_CHECK_COUNT = 48
VALIDATION_DESIGN_CLOSURE_EVENT_COUNT = 158
VALIDATION_DESIGN_CLOSURE_METRIC_COUNT = 18
VALIDATION_DESIGN_CLOSURE_RUNTIME_STAGE_COUNT = 12


class ValidationDesignClosureState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class ValidationDesignClosurePlane(StrEnum):
    MANIFEST = "manifest"
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    RUNTIME = "runtime"
    PLANE = "plane"
    INDEX = "index"
    JOIN = "join"
    PUBLIC_BOUNDARY = "public_boundary"
    QUERY = "query"
    SUMMARY = "summary"
    CERTIFICATION = "certification"
    OBSERVABILITY = "observability"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureCheck:
    check_id: str
    plane: ValidationDesignClosurePlane | str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{VALIDATION_DESIGN_CLOSURE_CHECK_PREFIX}:"):
            raise ValueError("D13 closure checks require addressed receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureBoundaryReport:
    bundle_id: str
    forbidden_keys: tuple[str, ...]
    discovered_keys: tuple[str, ...]
    path_checks: dict[str, bool]
    artifact_checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureIndexEntry:
    key: str
    address: str
    resource: str
    ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureIndexes:
    bundle_id: str
    by_artifact_id: tuple[ValidationDesignClosureIndexEntry, ...]
    by_path: tuple[ValidationDesignClosureIndexEntry, ...]
    by_record_id: tuple[ValidationDesignClosureIndexEntry, ...]
    by_operation: tuple[ValidationDesignClosureIndexEntry, ...]
    by_check_id: tuple[ValidationDesignClosureIndexEntry, ...]
    by_stage_id: tuple[ValidationDesignClosureIndexEntry, ...]
    by_plane_id: tuple[ValidationDesignClosureIndexEntry, ...]
    by_issue_code: tuple[ValidationDesignClosureIndexEntry, ...]
    by_state: tuple[ValidationDesignClosureIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureIndexAudit:
    bundle_id: str
    checks: tuple[ValidationDesignClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureQueryResult:
    bundle_id: str
    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureReconciliationCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[ValidationDesignClosureReconciliationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureReconciliationDelta:
    left_bundle_id: str
    right_bundle_id: str
    left_address: str
    right_address: str
    changed_artifacts: tuple[str, ...]
    changed_counts: dict[str, tuple[int, int]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureDomainSummary:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    passed_check_count: int
    failed_check_count: int
    accepted_count: int
    blocked_count: int
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    operations: tuple[ValidationDesignClosureDomainSummary, ...]
    states: tuple[dict[str, Any], ...]
    planes: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureSummaryAudit:
    bundle_id: str
    checks: tuple[ValidationDesignClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureCertificationCheck:
    check_id: str
    domain: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureCertificationDomain:
    domain_id: str
    title: str
    check_ids: tuple[str, ...]
    passed_count: int
    check_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureCertificationReport:
    version: str
    bundle_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[ValidationDesignClosureCertificationDomain, ...]
    checks: tuple[ValidationDesignClosureCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def accepted_domain_count(self) -> int:
        return sum(item.accepted for item in self.domains)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted_domain_count": self.accepted_domain_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureEvent:
    sequence: int
    event_type: str
    stage_id: str
    state: str
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureMetric:
    metric_id: str
    plane: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureObservability:
    bundle_id: str
    events: tuple[ValidationDesignClosureEvent, ...]
    metrics: tuple[ValidationDesignClosureMetric, ...]
    accepted: bool
    content_address: str

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def metric_count(self) -> int:
        return len(self.metrics)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": self.event_count,
            "metric_count": self.metric_count,
        }


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureRuntimeStage:
    stage_id: str
    ordinal: int
    state: ValidationDesignClosureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureRuntimeReport:
    run_id: str
    state: ValidationDesignClosureState
    stages: tuple[ValidationDesignClosureRuntimeStage, ...]
    bundle: Any
    boundary: ValidationDesignClosureBoundaryReport
    indexes: ValidationDesignClosureIndexes
    index_audit: ValidationDesignClosureIndexAudit
    reconciliation: ValidationDesignClosureReconciliationReport
    summary: ValidationDesignClosureSummary
    summary_audit: ValidationDesignClosureSummaryAudit
    certification: ValidationDesignClosureCertificationReport
    observability: ValidationDesignClosureObservability
    replay: ValidationDesignClosureReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VALIDATION_DESIGN_CLOSURE_RUNTIME_VERSION,
            "run_id": self.run_id,
            "state": self.state,
            "stages": [item.to_dict() for item in self.stages],
            "bundle": self.bundle.to_dict(include_payloads=False),
            "boundary": self.boundary.to_dict(),
            "indexes": self.indexes.to_dict(),
            "index_audit": self.index_audit.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "summary": self.summary.to_dict(),
            "summary_audit": self.summary_audit.to_dict(),
            "certification": self.certification.to_dict(),
            "observability": self.observability.to_dict(),
            "replay": self.replay.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def validation_design_closure_check(
    check_id: str,
    plane: ValidationDesignClosurePlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ValidationDesignClosureCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ValidationDesignClosureCheck(
        **body,
        content_address=content_hash(body, prefix=VALIDATION_DESIGN_CLOSURE_CHECK_PREFIX),
    )


__all__ = [
    "VALIDATION_DESIGN_CLOSURE_ARTIFACT_COUNT",
    "VALIDATION_DESIGN_CLOSURE_BOUNDARY",
    "VALIDATION_DESIGN_CLOSURE_CERTIFICATION_CHECK_COUNT",
    "VALIDATION_DESIGN_CLOSURE_CERTIFICATION_DOMAIN_COUNT",
    "VALIDATION_DESIGN_CLOSURE_CERTIFICATION_VERSION",
    "VALIDATION_DESIGN_CLOSURE_CHECK_PREFIX",
    "VALIDATION_DESIGN_CLOSURE_DEFAULT_LIMIT",
    "VALIDATION_DESIGN_CLOSURE_EVALUATION_CHECK_COUNT",
    "VALIDATION_DESIGN_CLOSURE_EVENT_COUNT",
    "VALIDATION_DESIGN_CLOSURE_MAX_LIMIT",
    "VALIDATION_DESIGN_CLOSURE_METRIC_COUNT",
    "VALIDATION_DESIGN_CLOSURE_OPERATION_COUNT",
    "VALIDATION_DESIGN_CLOSURE_PLANE_COUNT",
    "VALIDATION_DESIGN_CLOSURE_RECORD_COUNT",
    "VALIDATION_DESIGN_CLOSURE_RECONCILIATION_VERSION",
    "VALIDATION_DESIGN_CLOSURE_RUNTIME_STAGE_COUNT",
    "VALIDATION_DESIGN_CLOSURE_RUNTIME_VERSION",
    "VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION",
    "VALIDATION_DESIGN_CLOSURE_SOURCE_COUNT",
    "VALIDATION_DESIGN_CLOSURE_STAGE_COUNT",
    "VALIDATION_DESIGN_CLOSURE_VERSION",
    "ValidationDesignClosureBoundaryReport",
    "ValidationDesignClosureCertificationCheck",
    "ValidationDesignClosureCertificationDomain",
    "ValidationDesignClosureCertificationReport",
    "ValidationDesignClosureCheck",
    "ValidationDesignClosureDomainSummary",
    "ValidationDesignClosureEvent",
    "ValidationDesignClosureIndexAudit",
    "ValidationDesignClosureIndexEntry",
    "ValidationDesignClosureIndexes",
    "ValidationDesignClosureMetric",
    "ValidationDesignClosureObservability",
    "ValidationDesignClosurePlane",
    "ValidationDesignClosureQueryResult",
    "ValidationDesignClosureReconciliationCheck",
    "ValidationDesignClosureReconciliationDelta",
    "ValidationDesignClosureReconciliationReport",
    "ValidationDesignClosureReplay",
    "ValidationDesignClosureRuntimeReport",
    "ValidationDesignClosureRuntimeStage",
    "ValidationDesignClosureState",
    "ValidationDesignClosureSummary",
    "ValidationDesignClosureSummaryAudit",
    "validation_design_closure_check",
]

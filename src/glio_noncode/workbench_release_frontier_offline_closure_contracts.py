"""Contracts for the independent D15 workbench-release closure handoff."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

WORKBENCH_RELEASE_CLOSURE_VERSION = "workbench-release-closure-v1"
WORKBENCH_RELEASE_CLOSURE_SCHEMA_VERSION = "workbench-release-closure-schema-v1"
WORKBENCH_RELEASE_CLOSURE_RUNTIME_VERSION = "workbench-release-closure-runtime-v1"
WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_VERSION = "workbench-release-closure-certification-v1"
WORKBENCH_RELEASE_CLOSURE_BOUNDARY = "public_aggregate_workbench_release_closure_handoff"
WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX = "workbench-release-closure-check"
WORKBENCH_RELEASE_CLOSURE_DEFAULT_LIMIT = 50
WORKBENCH_RELEASE_CLOSURE_MAX_LIMIT = 500

WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT = 56
WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT = 5
WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT = 16
WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT = 4
WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT = 16
WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT = 80
WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT = 80
WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT = 16
WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT = 52
WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT = 16
WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT = 12
WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT = 16
WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT = 49
WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT = 184
WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT = 10
WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT = 60
WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL = 14


class WorkbenchReleaseClosureState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class WorkbenchReleaseClosurePlane(StrEnum):
    MANIFEST = "manifest"
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    VALIDATION = "validation"
    EVIDENCE = "evidence"
    LINEAGE = "lineage"
    REVIEW = "review"
    RUNTIME = "runtime"
    INDEX = "index"
    PUBLIC = "public"
    GRAPH = "graph"
    RELEASE = "release"
    OBSERVABILITY = "observability"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureCheck:
    check_id: str
    plane: WorkbenchReleaseClosurePlane | str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX}:"):
            raise ValueError("D15 closure checks require addressed receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureBoundaryReport:
    bundle_id: str
    source_boundary: str
    forbidden_keys: tuple[str, ...]
    discovered_key_count: int
    artifact_checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureIndexEntry:
    key: str
    resource: str
    target_id: str
    artifact_id: str
    ordinal: int
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureIndexes:
    bundle_id: str
    by_artifact_id: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_record_id: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_operation: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_check_id: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_source_id: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_stage_id: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_edge_id: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_queue_priority: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_capability: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    by_diagnostic_severity: tuple[WorkbenchReleaseClosureIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureIndexAudit:
    bundle_id: str
    checks: tuple[WorkbenchReleaseClosureCheck, ...]
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
class WorkbenchReleaseClosureQueryResult:
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
class WorkbenchReleaseClosureReconciliationCheck:
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
class WorkbenchReleaseClosureReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[WorkbenchReleaseClosureReconciliationCheck, ...]
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
class WorkbenchReleaseClosureReconciliationDelta:
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
class WorkbenchReleaseClosureOperationSummary:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    held_count: int
    issue_count: int
    check_count: int
    validation_count: int
    evidence_count: int
    states: tuple[tuple[str, int], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    operations: tuple[WorkbenchReleaseClosureOperationSummary, ...]
    states: tuple[dict[str, Any], ...]
    severities: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureSummaryAudit:
    bundle_id: str
    checks: tuple[WorkbenchReleaseClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureCertificationCheck:
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
class WorkbenchReleaseClosureCertificationDomain:
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
class WorkbenchReleaseClosureCertificationReport:
    version: str
    bundle_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[WorkbenchReleaseClosureCertificationDomain, ...]
    checks: tuple[WorkbenchReleaseClosureCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureEvent:
    sequence: int
    event_type: str
    resource: str
    resource_id: str
    state: str
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureMetric:
    metric_id: str
    plane: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureObservability:
    bundle_id: str
    events: tuple[WorkbenchReleaseClosureEvent, ...]
    metrics: tuple[WorkbenchReleaseClosureMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"event_count": len(self.events), "metric_count": len(self.metrics)}


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureGraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureGraphReport:
    bundle_id: str
    nodes: tuple[str, ...]
    edges: tuple[WorkbenchReleaseClosureGraphEdge, ...]
    connected_component_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_count": len(self.nodes), "edge_count": len(self.edges)}


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureRuntimeStage:
    stage_id: str
    ordinal: int
    state: WorkbenchReleaseClosureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureRuntimeReport:
    run_id: str
    state: WorkbenchReleaseClosureState
    stages: tuple[WorkbenchReleaseClosureRuntimeStage, ...]
    bundle: Any
    boundary: WorkbenchReleaseClosureBoundaryReport
    indexes: WorkbenchReleaseClosureIndexes
    index_audit: WorkbenchReleaseClosureIndexAudit
    reconciliation: WorkbenchReleaseClosureReconciliationReport
    summary: WorkbenchReleaseClosureSummary
    summary_audit: WorkbenchReleaseClosureSummaryAudit
    certification: WorkbenchReleaseClosureCertificationReport
    observability: WorkbenchReleaseClosureObservability
    graph: WorkbenchReleaseClosureGraphReport
    replay: WorkbenchReleaseClosureReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKBENCH_RELEASE_CLOSURE_RUNTIME_VERSION,
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
            "graph": self.graph.to_dict(),
            "replay": self.replay.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def workbench_release_closure_check(
    check_id: str,
    plane: WorkbenchReleaseClosurePlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> WorkbenchReleaseClosureCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseClosureCheck(
        **body,
        content_address=content_hash(body, prefix=WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX),
    )


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_BOUNDARY",
    "WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_VERSION",
    "WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX",
    "WORKBENCH_RELEASE_CLOSURE_DEFAULT_LIMIT",
    "WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_EVENT_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_MAX_LIMIT",
    "WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL",
    "WORKBENCH_RELEASE_CLOSURE_RUNTIME_VERSION",
    "WORKBENCH_RELEASE_CLOSURE_SCHEMA_VERSION",
    "WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_VERSION",
    "WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT",
    "WorkbenchReleaseClosureBoundaryReport",
    "WorkbenchReleaseClosureCertificationCheck",
    "WorkbenchReleaseClosureCertificationDomain",
    "WorkbenchReleaseClosureCertificationReport",
    "WorkbenchReleaseClosureCheck",
    "WorkbenchReleaseClosureEvent",
    "WorkbenchReleaseClosureGraphEdge",
    "WorkbenchReleaseClosureGraphReport",
    "WorkbenchReleaseClosureIndexAudit",
    "WorkbenchReleaseClosureIndexEntry",
    "WorkbenchReleaseClosureIndexes",
    "WorkbenchReleaseClosureMetric",
    "WorkbenchReleaseClosureObservability",
    "WorkbenchReleaseClosureOperationSummary",
    "WorkbenchReleaseClosureQueryResult",
    "WorkbenchReleaseClosureReconciliationCheck",
    "WorkbenchReleaseClosureReconciliationDelta",
    "WorkbenchReleaseClosureReconciliationReport",
    "WorkbenchReleaseClosureReplay",
    "WorkbenchReleaseClosureRuntimeReport",
    "WorkbenchReleaseClosureRuntimeStage",
    "WorkbenchReleaseClosureState",
    "WorkbenchReleaseClosureSummary",
    "WorkbenchReleaseClosureSummaryAudit",
    "workbench_release_closure_check",
]

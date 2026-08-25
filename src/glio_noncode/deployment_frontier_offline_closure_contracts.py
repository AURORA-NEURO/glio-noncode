"""Contracts for the independent D16 deployment-governance closure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

DEPLOYMENT_FRONTIER_CLOSURE_VERSION = "deployment-frontier-closure-v1"
DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_VERSION = "deployment-frontier-closure-schema-v1"
DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_VERSION = "deployment-frontier-closure-runtime-v1"
DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_VERSION = "deployment-frontier-closure-certification-v1"
DEPLOYMENT_FRONTIER_CLOSURE_BOUNDARY = "public_aggregate_deployment_closure_handoff"
DEPLOYMENT_FRONTIER_CLOSURE_CHECK_PREFIX = "deployment-frontier-closure-check"
DEPLOYMENT_FRONTIER_CLOSURE_DEFAULT_LIMIT = 50
DEPLOYMENT_FRONTIER_CLOSURE_MAX_LIMIT = 500

DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT = 51
DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT = 5
DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT = 16
DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT = 4
DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT = 16
DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT = 80
DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT = 64
DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT = 16
DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT = 52
DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT = 16
DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT = 12
DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT = 13
DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT = 38
DEPLOYMENT_FRONTIER_CLOSURE_AUDIT_EVENT_COUNT = 32
DEPLOYMENT_FRONTIER_CLOSURE_TRANSCRIPT_EVENT_COUNT = 33
DEPLOYMENT_FRONTIER_CLOSURE_TRACE_OBSERVATION_COUNT = 37
DEPLOYMENT_FRONTIER_CLOSURE_EVENT_COUNT = 151
DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_DOMAIN_COUNT = 10
DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_CHECK_COUNT = 60
DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_TOTAL = 14


class DeploymentFrontierClosureState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class DeploymentFrontierClosurePlane(StrEnum):
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
class DeploymentFrontierClosureCheck:
    check_id: str
    plane: DeploymentFrontierClosurePlane | str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{DEPLOYMENT_FRONTIER_CLOSURE_CHECK_PREFIX}:"):
            raise ValueError("D16 closure checks require addressed receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureBoundaryReport:
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
class DeploymentFrontierClosureIndexEntry:
    key: str
    resource: str
    target_id: str
    artifact_id: str
    ordinal: int
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureIndexes:
    bundle_id: str
    by_artifact_id: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_record_id: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_operation: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_check_id: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_source_id: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_stage_id: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_edge_id: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_queue_priority: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_issue_code: tuple[DeploymentFrontierClosureIndexEntry, ...]
    by_state: tuple[DeploymentFrontierClosureIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureIndexAudit:
    bundle_id: str
    checks: tuple[DeploymentFrontierClosureCheck, ...]
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
class DeploymentFrontierClosureQueryResult:
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
class DeploymentFrontierClosureReconciliationCheck:
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
class DeploymentFrontierClosureReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[DeploymentFrontierClosureReconciliationCheck, ...]
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
class DeploymentFrontierClosureReconciliationDelta:
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
class DeploymentFrontierClosureOperationSummary:
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
class DeploymentFrontierClosureSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    operations: tuple[DeploymentFrontierClosureOperationSummary, ...]
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
class DeploymentFrontierClosureSummaryAudit:
    bundle_id: str
    checks: tuple[DeploymentFrontierClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureCertificationCheck:
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
class DeploymentFrontierClosureCertificationDomain:
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
class DeploymentFrontierClosureCertificationReport:
    version: str
    bundle_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[DeploymentFrontierClosureCertificationDomain, ...]
    checks: tuple[DeploymentFrontierClosureCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureEvent:
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
class DeploymentFrontierClosureMetric:
    metric_id: str
    plane: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureObservability:
    bundle_id: str
    events: tuple[DeploymentFrontierClosureEvent, ...]
    metrics: tuple[DeploymentFrontierClosureMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"event_count": len(self.events), "metric_count": len(self.metrics)}


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureGraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureGraphReport:
    bundle_id: str
    nodes: tuple[str, ...]
    edges: tuple[DeploymentFrontierClosureGraphEdge, ...]
    connected_component_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_count": len(self.nodes), "edge_count": len(self.edges)}


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureRuntimeStage:
    stage_id: str
    ordinal: int
    state: DeploymentFrontierClosureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureRuntimeReport:
    run_id: str
    state: DeploymentFrontierClosureState
    stages: tuple[DeploymentFrontierClosureRuntimeStage, ...]
    bundle: Any
    boundary: DeploymentFrontierClosureBoundaryReport
    indexes: DeploymentFrontierClosureIndexes
    index_audit: DeploymentFrontierClosureIndexAudit
    reconciliation: DeploymentFrontierClosureReconciliationReport
    summary: DeploymentFrontierClosureSummary
    summary_audit: DeploymentFrontierClosureSummaryAudit
    certification: DeploymentFrontierClosureCertificationReport
    observability: DeploymentFrontierClosureObservability
    graph: DeploymentFrontierClosureGraphReport
    replay: DeploymentFrontierClosureReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_VERSION,
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


def deployment_frontier_closure_check(
    check_id: str,
    plane: DeploymentFrontierClosurePlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> DeploymentFrontierClosureCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierClosureCheck(
        **body,
        content_address=content_hash(body, prefix=DEPLOYMENT_FRONTIER_CLOSURE_CHECK_PREFIX),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("DEPLOYMENT_FRONTIER_CLOSURE")
    or name.startswith("DeploymentFrontierClosure")
    or name == "deployment_frontier_closure_check"
]

"""Contracts for the D14 evidence-lifecycle closure layer.

The source D14 offline bundle remains the byte-level handoff.  These contracts
add independent addressable projections over its public aggregate artifacts:
indexes, joins, summaries, certification, telemetry, failure rehearsal, graph
lineage, and an export-ready runtime report.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

EVIDENCE_LIFECYCLE_CLOSURE_VERSION = "evidence-lifecycle-closure-v1"
EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION = "evidence-lifecycle-closure-schema-v1"
EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_VERSION = "evidence-lifecycle-closure-runtime-v1"
EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_VERSION = "evidence-lifecycle-closure-certification-v1"
EVIDENCE_LIFECYCLE_CLOSURE_BOUNDARY = "public_aggregate_evidence_lifecycle_closure_handoff"
EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX = "evidence-lifecycle-closure-check"
EVIDENCE_LIFECYCLE_CLOSURE_DEFAULT_LIMIT = 50
EVIDENCE_LIFECYCLE_CLOSURE_MAX_LIMIT = 500

EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT = 21
EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT = 5
EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT = 16
EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT = 4
EVIDENCE_LIFECYCLE_CLOSURE_EXECUTION_COUNT = 16
EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT = 120
EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT = 62
EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT = 10
EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT = 36
EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT = 16
EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT = 16
EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT = 31
EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_DOMAIN_COUNT = 8
EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_CHECK_COUNT = 48
EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_STAGE_COUNT = 12


class EvidenceLifecycleClosureState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class EvidenceLifecycleClosurePlane(StrEnum):
    MANIFEST = "manifest"
    BOUNDARY = "boundary"
    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    LINEAGE = "lineage"
    QUEUE = "queue"
    REVIEW = "review"
    RUNTIME = "runtime"
    INDEX = "index"
    JOIN = "join"
    SUMMARY = "summary"
    CERTIFICATION = "certification"
    OBSERVABILITY = "observability"
    GRAPH = "graph"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureCheck:
    check_id: str
    plane: EvidenceLifecycleClosurePlane | str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX}:"):
            raise ValueError("D14 closure checks require addressed receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureBoundaryReport:
    bundle_id: str
    source_boundary: str
    forbidden_keys: tuple[str, ...]
    discovered_key_count: int
    artifact_checks: tuple[dict[str, Any], ...]
    filesystem_accepted: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureIndexEntry:
    key: str
    resource: str
    target_id: str
    artifact_id: str
    ordinal: int
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureIndexes:
    bundle_id: str
    by_artifact_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_record_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_operation: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_check_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_source_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_event_type: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_stage_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_edge_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_queue_disposition: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    by_scenario_id: tuple[EvidenceLifecycleClosureIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureIndexAudit:
    bundle_id: str
    checks: tuple[EvidenceLifecycleClosureCheck, ...]
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
class EvidenceLifecycleClosureQueryResult:
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
class EvidenceLifecycleClosureReconciliationCheck:
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
class EvidenceLifecycleClosureReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[EvidenceLifecycleClosureReconciliationCheck, ...]
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
class EvidenceLifecycleClosureReconciliationDelta:
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
class EvidenceLifecycleClosureOperationSummary:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    held_count: int
    issue_count: int
    check_count: int
    passed_check_count: int
    states: tuple[tuple[str, int], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    operations: tuple[EvidenceLifecycleClosureOperationSummary, ...]
    queue: tuple[dict[str, Any], ...]
    states: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureSummaryAudit:
    bundle_id: str
    checks: tuple[EvidenceLifecycleClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureCertificationCheck:
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
class EvidenceLifecycleClosureCertificationDomain:
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
class EvidenceLifecycleClosureCertificationReport:
    version: str
    bundle_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[EvidenceLifecycleClosureCertificationDomain, ...]
    checks: tuple[EvidenceLifecycleClosureCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureEvent:
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
class EvidenceLifecycleClosureMetric:
    metric_id: str
    plane: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureObservability:
    bundle_id: str
    events: tuple[EvidenceLifecycleClosureEvent, ...]
    metrics: tuple[EvidenceLifecycleClosureMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"event_count": len(self.events), "metric_count": len(self.metrics)}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureGraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureGraphReport:
    bundle_id: str
    nodes: tuple[str, ...]
    edges: tuple[EvidenceLifecycleClosureGraphEdge, ...]
    connected_component_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_count": len(self.nodes), "edge_count": len(self.edges)}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureRuntimeStage:
    stage_id: str
    ordinal: int
    state: EvidenceLifecycleClosureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureRuntimeReport:
    run_id: str
    state: EvidenceLifecycleClosureState
    stages: tuple[EvidenceLifecycleClosureRuntimeStage, ...]
    bundle: Any
    boundary: EvidenceLifecycleClosureBoundaryReport
    indexes: EvidenceLifecycleClosureIndexes
    index_audit: EvidenceLifecycleClosureIndexAudit
    reconciliation: EvidenceLifecycleClosureReconciliationReport
    summary: EvidenceLifecycleClosureSummary
    summary_audit: EvidenceLifecycleClosureSummaryAudit
    certification: EvidenceLifecycleClosureCertificationReport
    observability: EvidenceLifecycleClosureObservability
    graph: EvidenceLifecycleClosureGraphReport
    replay: EvidenceLifecycleClosureReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_VERSION,
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


def evidence_lifecycle_closure_check(
    check_id: str,
    plane: EvidenceLifecycleClosurePlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> EvidenceLifecycleClosureCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return EvidenceLifecycleClosureCheck(
        **body,
        content_address=content_hash(body, prefix=EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX),
    )


__all__ = [
    "EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_BOUNDARY",
    "EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_CHECK_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_DOMAIN_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_VERSION",
    "EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX",
    "EVIDENCE_LIFECYCLE_CLOSURE_DEFAULT_LIMIT",
    "EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_EVENT_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_MAX_LIMIT",
    "EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_STAGE_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_RUNTIME_VERSION",
    "EVIDENCE_LIFECYCLE_CLOSURE_SCHEMA_VERSION",
    "EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_VERSION",
    "EvidenceLifecycleClosureBoundaryReport",
    "EvidenceLifecycleClosureCertificationCheck",
    "EvidenceLifecycleClosureCertificationDomain",
    "EvidenceLifecycleClosureCertificationReport",
    "EvidenceLifecycleClosureCheck",
    "EvidenceLifecycleClosureEvent",
    "EvidenceLifecycleClosureGraphEdge",
    "EvidenceLifecycleClosureGraphReport",
    "EvidenceLifecycleClosureIndexAudit",
    "EvidenceLifecycleClosureIndexEntry",
    "EvidenceLifecycleClosureIndexes",
    "EvidenceLifecycleClosureMetric",
    "EvidenceLifecycleClosureObservability",
    "EvidenceLifecycleClosureOperationSummary",
    "EvidenceLifecycleClosurePlane",
    "EvidenceLifecycleClosureQueryResult",
    "EvidenceLifecycleClosureReconciliationCheck",
    "EvidenceLifecycleClosureReconciliationDelta",
    "EvidenceLifecycleClosureReconciliationReport",
    "EvidenceLifecycleClosureReplay",
    "EvidenceLifecycleClosureRuntimeReport",
    "EvidenceLifecycleClosureRuntimeStage",
    "EvidenceLifecycleClosureState",
    "EvidenceLifecycleClosureSummary",
    "EvidenceLifecycleClosureSummaryAudit",
    "evidence_lifecycle_closure_check",
]

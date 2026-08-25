"""Typed contracts for the D01-D16 program release closure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable

PROGRAM_RELEASE_CLOSURE_VERSION = "program-release-closure-v1"
PROGRAM_RELEASE_CLOSURE_SCHEMA_VERSION = "program-release-closure-schema-v1"
PROGRAM_RELEASE_CLOSURE_RUNTIME_VERSION = "program-release-closure-runtime-v1"
PROGRAM_RELEASE_CLOSURE_CERTIFICATION_VERSION = "program-release-closure-certification-v1"
PROGRAM_RELEASE_CLOSURE_EXPORT_VERSION = "program-release-closure-export-v1"
PROGRAM_RELEASE_CLOSURE_BOUNDARY = "public_aggregate_program_release_closure_handoff"
PROGRAM_RELEASE_CLOSURE_CHECK_PREFIX = "program-release-closure-check"
PROGRAM_RELEASE_CLOSURE_ARTIFACT_PREFIX = "program-release-closure-artifact"
PROGRAM_RELEASE_CLOSURE_DEFAULT_LIMIT = 50
PROGRAM_RELEASE_CLOSURE_MAX_LIMIT = 500
PROGRAM_RELEASE_CLOSURE_DOMAIN_IDS = tuple(f"D{index:02d}" for index in range(1, 17))
PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT = 16
PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT = 18
PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT = 120
PROGRAM_RELEASE_CLOSURE_GATE_TYPES = (
    "bundle_accepted",
    "runtime_address",
    "runtime_depth",
    "evaluation_checks",
    "artifact_contribution",
    "public_projection",
)
PROGRAM_RELEASE_CLOSURE_GATES_PER_DOMAIN = len(PROGRAM_RELEASE_CLOSURE_GATE_TYPES)
PROGRAM_RELEASE_CLOSURE_GATE_COUNT = (
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT * PROGRAM_RELEASE_CLOSURE_GATES_PER_DOMAIN
)
PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECKS_PER_DOMAIN = 6
PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT = (
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT * PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECKS_PER_DOMAIN
)
PROGRAM_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL = 14
PROGRAM_RELEASE_CLOSURE_PLAN_STEP_COUNT = 23
PROGRAM_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT = 15
PROGRAM_RELEASE_CLOSURE_RESOURCE_COUNT = 5
PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT = 266
PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT = 96


class ProgramReleaseClosureState(StrEnum):
    """Lifecycle state of the public program release closure."""

    READY = "ready"
    BLOCKED = "blocked"


class ProgramReleaseClosurePlane(StrEnum):
    """Assurance planes used by the aggregate release."""

    BOUNDARY = "boundary"
    SOURCE = "source"
    ARTIFACT = "artifact"
    DEPENDENCY = "dependency"
    GATE = "gate"
    RECONCILIATION = "reconciliation"
    CERTIFICATION = "certification"
    OBSERVABILITY = "observability"
    GRAPH = "graph"
    FAILURE = "failure"
    PLAN = "plan"
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class ProgramReleaseClosureCheck:
    check_id: str
    plane: ProgramReleaseClosurePlane | str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseDomain:
    domain_id: str
    domain: str
    dependency_order: int
    source_bundle_id: str
    source_runtime_address: str
    source_receipt_address: str
    runtime_state: str
    stage_count: int
    evaluation_check_count: int
    source_artifact_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseArtifact:
    artifact_ref: str
    artifact_id: str
    domain_id: str
    relative_path: str
    media_type: str
    source_address: str
    content_address: str
    byte_count: int
    line_count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseDependency:
    dependency_id: str
    source_domain_id: str
    target_domain_id: str
    relation: str
    source_order: int
    target_order: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseGate:
    gate_id: str
    domain_id: str
    gate_type: str
    passed: bool
    observed: Any
    expected: Any
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseIndexEntry:
    index_name: str
    key: str
    resource: str
    reference: str
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseIndexes:
    bundle_id: str
    by_domain_id: tuple[ProgramReleaseIndexEntry, ...]
    by_artifact_ref: tuple[ProgramReleaseIndexEntry, ...]
    by_dependency_id: tuple[ProgramReleaseIndexEntry, ...]
    by_gate_id: tuple[ProgramReleaseIndexEntry, ...]
    by_content_address: tuple[ProgramReleaseIndexEntry, ...]
    by_source_address: tuple[ProgramReleaseIndexEntry, ...]
    by_state: tuple[ProgramReleaseIndexEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseIndexAudit:
    bundle_id: str
    checks: tuple[ProgramReleaseClosureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseQueryResult:
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
class ProgramReleaseReconciliation:
    bundle_id: str
    checks: tuple[ProgramReleaseClosureCheck, ...]
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
            "failed_check_ids": self.failed_check_ids,
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    domains: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"counter_map": self.counter_map}


@dataclass(frozen=True, slots=True)
class ProgramReleaseSummaryAudit:
    bundle_id: str
    checks: tuple[ProgramReleaseClosureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": sum(item.passed for item in self.checks)}


@dataclass(frozen=True, slots=True)
class ProgramReleaseCertificationCheck:
    certification_id: str
    domain_id: str
    plane: str
    passed: bool
    observed: Any
    expected: Any
    references: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseCertification:
    bundle_id: str
    version: str
    checks: tuple[ProgramReleaseCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def coverage_percent(self) -> float:
        return round(100.0 * self.passed_check_count / max(1, self.check_count), 2)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "coverage_percent": self.coverage_percent,
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseEvent:
    sequence: int
    event_id: str
    event_type: str
    domain_id: str
    input_address: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseMetric:
    metric_id: str
    domain_id: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseObservability:
    bundle_id: str
    events: tuple[ProgramReleaseEvent, ...]
    metrics: tuple[ProgramReleaseMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": len(self.events),
            "metric_count": len(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseGraphNode:
    node_id: str
    node_type: str
    reference: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseGraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseGraph:
    bundle_id: str
    nodes: tuple[ProgramReleaseGraphNode, ...]
    edges: tuple[ProgramReleaseGraphEdge, ...]
    connected_component_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseFailureCase:
    case_id: str
    target: str
    mutation: str
    expected_rejection: bool
    observed_rejection: bool
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseFailureReport:
    bundle_id: str
    cases: tuple[ProgramReleaseFailureCase, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"case_count": len(self.cases)}


@dataclass(frozen=True, slots=True)
class ProgramReleasePlanStep:
    step_id: str
    ordinal: int
    domain_id: str
    action: str
    prerequisite_ids: tuple[str, ...]
    input_address: str
    output_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleasePlan:
    bundle_id: str
    steps: tuple[ProgramReleasePlanStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"step_count": len(self.steps)}


@dataclass(frozen=True, slots=True)
class ProgramReleaseOperation:
    """One executable operation in the closure control plane."""

    operation_id: str
    resource: str
    phase: str
    prerequisite_ids: tuple[str, ...]
    input_address: str
    output_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseOperationalMatrix:
    """The ordered operation inventory used to assemble a closure."""

    bundle_id: str
    operations: tuple[ProgramReleaseOperation, ...]
    resources: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "operation_count": len(self.operations),
            "resource_count": len(self.resources),
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseOperationalAudit:
    """Independent checks over the operation matrix."""

    bundle_id: str
    checks: tuple[ProgramReleaseClosureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseDomainView:
    """Reviewer-facing joined view for one domain."""

    domain_id: str
    domain: str
    dependency_order: int
    incoming_dependency_count: int
    outgoing_dependency_count: int
    gate_count: int
    passed_gate_count: int
    stage_count: int
    evaluation_check_count: int
    source_artifact_count: int
    ready: bool
    source_runtime_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseReviewViews:
    """Stable collection of joined domain views."""

    bundle_id: str
    views: tuple[ProgramReleaseDomainView, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"view_count": len(self.views)}


@dataclass(frozen=True, slots=True)
class ProgramReleaseRuntimeStage:
    ordinal: int
    stage_id: str
    state: ProgramReleaseClosureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseSnapshot:
    bundle_id: str
    run_id: str
    source_bundle_id: str
    source_bundle_address: str
    domains: tuple[ProgramReleaseDomain, ...]
    artifacts: tuple[ProgramReleaseArtifact, ...]
    dependencies: tuple[ProgramReleaseDependency, ...]
    gates: tuple[ProgramReleaseGate, ...]
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return PROGRAM_RELEASE_CLOSURE_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"boundary": self.boundary}

    @property
    def domain_map(self) -> dict[str, ProgramReleaseDomain]:
        return {item.domain_id: item for item in self.domains}


@dataclass(frozen=True, slots=True)
class ProgramReleaseRuntimeReport:
    run_id: str
    state: ProgramReleaseClosureState
    stages: tuple[ProgramReleaseRuntimeStage, ...]
    snapshot: ProgramReleaseSnapshot
    indexes: ProgramReleaseIndexes
    index_audit: ProgramReleaseIndexAudit
    reconciliation: ProgramReleaseReconciliation
    summary: ProgramReleaseSummary
    summary_audit: ProgramReleaseSummaryAudit
    certification: ProgramReleaseCertification
    observability: ProgramReleaseObservability
    graph: ProgramReleaseGraph
    failures: ProgramReleaseFailureReport
    plan: ProgramReleasePlan
    plan_audit: tuple[ProgramReleaseClosureCheck, ...]
    operational: ProgramReleaseOperationalMatrix
    operational_audit: ProgramReleaseOperationalAudit
    views: ProgramReleaseReviewViews
    views_audit: tuple[ProgramReleaseClosureCheck, ...]
    replay: ProgramReleaseReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "stage_count": len(self.stages),
            "failed_stage_ids": tuple(
                item.stage_id
                for item in self.stages
                if item.state is ProgramReleaseClosureState.BLOCKED
            ),
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseExportArtifact:
    relative_path: str
    media_type: str
    byte_count: int
    content_address: str
    content: bytes

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body = {
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "content_address": self.content_address,
        }
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class ProgramReleaseExportManifest:
    version: str
    bundle_id: str
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseExportPacket:
    bundle_id: str
    artifacts: tuple[ProgramReleaseExportArtifact, ...]
    manifest: ProgramReleaseExportManifest
    accepted: bool
    content_address: str

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "artifacts": [item.to_dict(include_content=include_content) for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseExportVerification:
    bundle_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def program_release_closure_check(
    check_id: str,
    plane: ProgramReleaseClosurePlane | str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> ProgramReleaseClosureCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": jsonable(observed),
        "expected": jsonable(expected),
        "detail": detail,
    }
    return ProgramReleaseClosureCheck(
        **body,
        content_address=content_hash(body, prefix=PROGRAM_RELEASE_CLOSURE_CHECK_PREFIX),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE_CLOSURE")
    or name.startswith("ProgramRelease")
    or name == "program_release_closure_check"
]

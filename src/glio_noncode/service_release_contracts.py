"""Typed contracts for the repository service-release registry.

The service surface is useful for health and query clients, while a release
registry is useful for archival, promotion, and independent verification.
These contracts keep that registry public, deterministic, and addressable.
They intentionally describe only aggregate service projections; source case
records, personal identifiers, runtime authorship, and model metadata are not
part of this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable

SERVICE_RELEASE_VERSION = "service-release-v1"
SERVICE_RELEASE_SCHEMA_VERSION = "service-release-schema-v1"
SERVICE_RELEASE_RUNTIME_VERSION = "service-release-runtime-v1"
SERVICE_RELEASE_EXPORT_VERSION = "service-release-export-v1"
SERVICE_RELEASE_BOUNDARY = "public_service_release_registry_handoff"
SERVICE_RELEASE_DEFAULT_LIMIT = 50
SERVICE_RELEASE_MAX_LIMIT = 500
SERVICE_RELEASE_SURFACE_IDS = (
    "capability-certification",
    "architecture-program",
    "operational",
    "program-release",
    "service-status",
    "public-boundary",
)
SERVICE_RELEASE_SURFACE_COUNT = len(SERVICE_RELEASE_SURFACE_IDS)
SERVICE_RELEASE_ARTIFACT_COUNT = 13
SERVICE_RELEASE_DEPENDENCY_COUNT = SERVICE_RELEASE_SURFACE_COUNT * (SERVICE_RELEASE_SURFACE_COUNT - 1) // 2
SERVICE_RELEASE_GATE_TYPES = (
    "source_accepted",
    "address_present",
    "row_denominator",
    "public_projection",
)
SERVICE_RELEASE_GATES_PER_SURFACE = len(SERVICE_RELEASE_GATE_TYPES)
SERVICE_RELEASE_GATE_COUNT = SERVICE_RELEASE_SURFACE_COUNT * SERVICE_RELEASE_GATES_PER_SURFACE
SERVICE_RELEASE_RUNTIME_STAGE_TOTAL = 14
SERVICE_RELEASE_PLAN_STEP_COUNT = 23
SERVICE_RELEASE_OBSERVABILITY_EVENT_COUNT = 78
SERVICE_RELEASE_OBSERVABILITY_METRIC_COUNT = 24
SERVICE_RELEASE_RESOURCE_NAMES = (
    "surfaces",
    "artifacts",
    "dependencies",
    "gates",
    "stages",
    "checks",
    "events",
    "metrics",
    "views",
)


class ServiceReleaseState(StrEnum):
    """Lifecycle state of a public service release registry."""

    READY = "ready"
    BLOCKED = "blocked"


class ServiceReleasePlane(StrEnum):
    """Independent verification planes used by the registry."""

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


def _address(body: Any, prefix: str) -> str:
    return content_hash(body, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ServiceReleaseCheck:
    check_id: str
    plane: ServiceReleasePlane | str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseSurface:
    surface_id: str
    category: str
    dependency_order: int
    source_address: str
    service_address: str
    row_count: int
    artifact_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseArtifact:
    artifact_ref: str
    artifact_id: str
    surface_id: str
    relative_path: str
    media_type: str
    source_address: str
    byte_count: int
    line_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseDependency:
    dependency_id: str
    source_surface_id: str
    target_surface_id: str
    relation: str
    source_order: int
    target_order: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseGate:
    gate_id: str
    surface_id: str
    gate_type: str
    passed: bool
    observed: Any
    expected: Any
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseIndexEntry:
    index_name: str
    key: str
    resource: str
    reference: str
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseIndexes:
    bundle_id: str
    by_surface_id: tuple[ServiceReleaseIndexEntry, ...]
    by_artifact_ref: tuple[ServiceReleaseIndexEntry, ...]
    by_dependency_id: tuple[ServiceReleaseIndexEntry, ...]
    by_gate_id: tuple[ServiceReleaseIndexEntry, ...]
    by_content_address: tuple[ServiceReleaseIndexEntry, ...]
    by_state: tuple[ServiceReleaseIndexEntry, ...]
    accepted: bool
    content_address: str

    @property
    def entries(self) -> tuple[ServiceReleaseIndexEntry, ...]:
        return (
            *self.by_surface_id,
            *self.by_artifact_ref,
            *self.by_dependency_id,
            *self.by_gate_id,
            *self.by_content_address,
            *self.by_state,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"entry_count": len(self.entries)}


@dataclass(frozen=True, slots=True)
class ServiceReleaseIndexAudit:
    bundle_id: str
    checks: tuple[ServiceReleaseCheck, ...]
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
class ServiceReleaseQueryResult:
    bundle_id: str
    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"has_more": self.has_more}


@dataclass(frozen=True, slots=True)
class ServiceReleaseReconciliation:
    bundle_id: str
    checks: tuple[ServiceReleaseCheck, ...]
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
class ServiceReleaseSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    surfaces: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"counter_map": self.counter_map}


@dataclass(frozen=True, slots=True)
class ServiceReleaseSummaryAudit:
    bundle_id: str
    checks: tuple[ServiceReleaseCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": sum(item.passed for item in self.checks)}


@dataclass(frozen=True, slots=True)
class ServiceReleaseCertification:
    bundle_id: str
    checks: tuple[ServiceReleaseCheck, ...]
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
class ServiceReleaseEvent:
    sequence: int
    event_id: str
    event_type: str
    surface_id: str
    input_address: str
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseMetric:
    metric_id: str
    surface_id: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseObservability:
    bundle_id: str
    events: tuple[ServiceReleaseEvent, ...]
    metrics: tuple[ServiceReleaseMetric, ...]
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
class ServiceReleaseGraphNode:
    node_id: str
    node_type: str
    reference: str
    surface_id: str | None
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseGraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseGraph:
    bundle_id: str
    nodes: tuple[ServiceReleaseGraphNode, ...]
    edges: tuple[ServiceReleaseGraphEdge, ...]
    connected: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass(frozen=True, slots=True)
class ServiceReleaseFailureCase:
    case_id: str
    mutation: str
    expected_failure: str
    observed_failure: str
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseFailureReport:
    bundle_id: str
    cases: tuple[ServiceReleaseFailureCase, ...]
    accepted: bool
    content_address: str

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def passed_case_count(self) -> int:
        return sum(item.passed for item in self.cases)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "case_count": self.case_count,
            "passed_case_count": self.passed_case_count,
        }


@dataclass(frozen=True, slots=True)
class ServiceReleasePlanStep:
    ordinal: int
    step_id: str
    phase: str
    action: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    gate_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleasePlan:
    bundle_id: str
    steps: tuple[ServiceReleasePlanStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"step_count": len(self.steps)}


@dataclass(frozen=True, slots=True)
class ServiceReleaseView:
    view_id: str
    title: str
    surface_ids: tuple[str, ...]
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"row_count": len(self.rows)}


@dataclass(frozen=True, slots=True)
class ServiceReleaseViews:
    bundle_id: str
    views: tuple[ServiceReleaseView, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"view_count": len(self.views)}


@dataclass(frozen=True, slots=True)
class ServiceReleaseRuntimeStage:
    ordinal: int
    stage_id: str
    state: ServiceReleaseState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseSnapshot:
    bundle_id: str
    service_address: str
    source_surface_address: str
    surfaces: tuple[ServiceReleaseSurface, ...]
    artifacts: tuple[ServiceReleaseArtifact, ...]
    dependencies: tuple[ServiceReleaseDependency, ...]
    gates: tuple[ServiceReleaseGate, ...]
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return SERVICE_RELEASE_BOUNDARY

    @property
    def surface_map(self) -> dict[str, ServiceReleaseSurface]:
        return {item.surface_id: item for item in self.surfaces}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"boundary": self.boundary}


@dataclass(frozen=True, slots=True)
class ServiceReleaseRuntimeReport:
    run_id: str
    state: ServiceReleaseState
    stages: tuple[ServiceReleaseRuntimeStage, ...]
    snapshot: ServiceReleaseSnapshot
    indexes: ServiceReleaseIndexes
    index_audit: ServiceReleaseIndexAudit
    reconciliation: ServiceReleaseReconciliation
    summary: ServiceReleaseSummary
    summary_audit: ServiceReleaseSummaryAudit
    certification: ServiceReleaseCertification
    observability: ServiceReleaseObservability
    graph: ServiceReleaseGraph
    failures: ServiceReleaseFailureReport
    plan: ServiceReleasePlan
    plan_audit: tuple[ServiceReleaseCheck, ...]
    views: ServiceReleaseViews
    views_audit: tuple[ServiceReleaseCheck, ...]
    replay: ServiceReleaseReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "stage_count": len(self.stages),
            "failed_stage_ids": [
                item.stage_id for item in self.stages if item.state is ServiceReleaseState.BLOCKED
            ],
        }


@dataclass(frozen=True, slots=True)
class ServiceReleaseExportArtifact:
    relative_path: str
    media_type: str
    byte_count: int
    content_address: str
    content: bytes

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "content_address": self.content_address,
        }
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class ServiceReleaseExportManifest:
    version: str
    bundle_id: str
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ServiceReleaseExportPacket:
    bundle_id: str
    artifacts: tuple[ServiceReleaseExportArtifact, ...]
    manifest: ServiceReleaseExportManifest
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
class ServiceReleaseExportVerification:
    bundle_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    duplicate_paths: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    tampered_paths: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def check(
    check_id: str,
    plane: ServiceReleasePlane | str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> ServiceReleaseCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return ServiceReleaseCheck(**body, content_address=_address(body, "service-release-check"))


__all__ = [name for name in globals() if name.startswith("SERVICE_RELEASE") or name.startswith("ServiceRelease") or name == "check"]

"""Contracts for the cross-domain D13-D16 release closure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable

FRONTIER_RELEASE_CLOSURE_VERSION = "frontier-release-closure-v1"
FRONTIER_RELEASE_CLOSURE_SCHEMA_VERSION = "frontier-release-closure-schema-v1"
FRONTIER_RELEASE_CLOSURE_RUNTIME_VERSION = "frontier-release-closure-runtime-v1"
FRONTIER_RELEASE_CLOSURE_CERTIFICATION_VERSION = "frontier-release-closure-certification-v1"
FRONTIER_RELEASE_CLOSURE_BOUNDARY = "public_aggregate_frontier_release_closure_handoff"
FRONTIER_RELEASE_CLOSURE_CHECK_PREFIX = "frontier-release-closure-check"
FRONTIER_RELEASE_CLOSURE_DEFAULT_LIMIT = 50
FRONTIER_RELEASE_CLOSURE_MAX_LIMIT = 500
FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT = 4
FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT = 155
FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT = 6
FRONTIER_RELEASE_CLOSURE_GATE_COUNT = 24
FRONTIER_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT = 8
FRONTIER_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT = 48
FRONTIER_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL = 12
FRONTIER_RELEASE_CLOSURE_FAILURE_COUNT = 12
FRONTIER_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT = 13
FRONTIER_RELEASE_CLOSURE_EVENT_COUNT = 193
FRONTIER_RELEASE_CLOSURE_METRIC_COUNT = 24
FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS = ("D13", "D14", "D15", "D16")
FRONTIER_RELEASE_CLOSURE_DOMAIN_NAMES = (
    "validation_design",
    "evidence_lifecycle",
    "workbench_release",
    "deployment_frontier",
)


class FrontierReleaseClosureState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class FrontierReleaseClosurePlane(StrEnum):
    MANIFEST = "manifest"
    DOMAIN = "domain"
    ARTIFACT = "artifact"
    DEPENDENCY = "dependency"
    GATE = "gate"
    PUBLIC = "public"
    RECONCILIATION = "reconciliation"
    SUMMARY = "summary"
    CERTIFICATION = "certification"
    OBSERVABILITY = "observability"
    GRAPH = "graph"
    RUNTIME = "runtime"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class FrontierReleaseClosureCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseBoundaryReport:
    bundle_id: str
    source_boundary: str
    forbidden_keys: tuple[str, ...]
    discovered_key_count: int
    checks: tuple[FrontierReleaseClosureCheck, ...]
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
class FrontierReleaseDomain:
    domain_id: str
    name: str
    bundle_id: str
    bundle_version: str
    boundary: str
    bundle_content_address: str
    runtime_content_address: str
    artifact_count: int
    source_count: int
    record_count: int
    evaluation_check_count: int
    source_stage_count: int
    closure_stage_count: int
    certification_check_count: int
    certification_passed_count: int
    certification_coverage_percent: float
    reconciliation_check_count: int
    reconciliation_passed_count: int
    graph_node_count: int
    graph_edge_count: int
    graph_component_count: int
    deterministic_replay: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseArtifact:
    artifact_ref: str
    domain_id: str
    artifact_id: str
    relative_path: str
    media_type: str
    content_address: str
    source_content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseDependency:
    dependency_id: str
    source_domain_id: str
    target_domain_id: str
    relation: str
    ordinal: int
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseGate:
    gate_id: str
    domain_id: str
    gate_type: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseIndexEntry:
    index_name: str
    key: str
    resource: str
    reference: str
    domain_id: str
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseIndexes:
    by_domain_id: tuple[FrontierReleaseIndexEntry, ...]
    by_artifact_ref: tuple[FrontierReleaseIndexEntry, ...]
    by_gate_id: tuple[FrontierReleaseIndexEntry, ...]
    by_dependency_id: tuple[FrontierReleaseIndexEntry, ...]
    by_bundle_id: tuple[FrontierReleaseIndexEntry, ...]
    by_state: tuple[FrontierReleaseIndexEntry, ...]
    by_content_address: tuple[FrontierReleaseIndexEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def index_count(self) -> int:
        return 7


@dataclass(frozen=True, slots=True)
class FrontierReleaseIndexAudit:
    bundle_id: str
    checks: tuple[FrontierReleaseClosureCheck, ...]
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
class FrontierReleaseQueryResult:
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
class FrontierReleaseReconciliationReport:
    bundle_id: str
    checks: tuple[FrontierReleaseClosureCheck, ...]
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
class FrontierReleaseDelta:
    left_bundle_id: str
    right_bundle_id: str
    left_address: str
    right_address: str
    changed_domains: tuple[str, ...]
    changed_artifacts: tuple[str, ...]
    changed_gates: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    domains: tuple[dict[str, Any], ...]
    gates: tuple[dict[str, Any], ...]
    dependencies: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseSummaryAudit:
    bundle_id: str
    checks: tuple[FrontierReleaseClosureCheck, ...]
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
class FrontierReleaseCertificationCheck:
    check_id: str
    domain: str
    plane: str
    passed: bool
    observed: Any
    expected: Any
    evidence_refs: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseCertificationDomain:
    domain_id: str
    name: str
    check_count: int
    passed_check_count: int
    coverage_percent: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseCertificationReport:
    version: str
    bundle_id: str
    check_count: int
    passed_check_count: int
    coverage_percent: float
    domains: tuple[FrontierReleaseCertificationDomain, ...]
    checks: tuple[FrontierReleaseCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_count(self) -> int:
        return self.check_count - self.passed_check_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_count": self.failed_check_count,
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed],
        }


@dataclass(frozen=True, slots=True)
class FrontierReleaseEvent:
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
class FrontierReleaseMetric:
    metric_id: str
    plane: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseObservability:
    bundle_id: str
    events: tuple[FrontierReleaseEvent, ...]
    metrics: tuple[FrontierReleaseMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseGraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseGraphReport:
    bundle_id: str
    nodes: tuple[str, ...]
    edges: tuple[FrontierReleaseGraphEdge, ...]
    connected_component_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass(frozen=True, slots=True)
class FrontierReleaseFailureCase:
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
class FrontierReleaseFailureReport:
    bundle_id: str
    cases: tuple[FrontierReleaseFailureCase, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"case_count": len(self.cases)}


@dataclass(frozen=True, slots=True)
class FrontierReleasePlanStep:
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
class FrontierReleasePlan:
    bundle_id: str
    steps: tuple[FrontierReleasePlanStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"step_count": len(self.steps)}


@dataclass(frozen=True, slots=True)
class FrontierReleaseRuntimeStage:
    ordinal: int
    stage_id: str
    state: FrontierReleaseClosureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseRuntimeReport:
    run_id: str
    state: FrontierReleaseClosureState
    stages: tuple[FrontierReleaseRuntimeStage, ...]
    snapshot: Any
    boundary: Any
    indexes: FrontierReleaseIndexes
    index_audit: FrontierReleaseIndexAudit
    reconciliation: FrontierReleaseReconciliationReport
    summary: FrontierReleaseSummary
    summary_audit: FrontierReleaseSummaryAudit
    certification: FrontierReleaseCertificationReport
    observability: FrontierReleaseObservability
    graph: FrontierReleaseGraphReport
    failures: FrontierReleaseFailureReport
    plan: FrontierReleasePlan
    plan_audit: tuple[dict[str, Any], ...]
    replay: FrontierReleaseReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "stage_count": len(self.stages),
            "failed_stage_ids": [
                item.stage_id
                for item in self.stages
                if item.state is FrontierReleaseClosureState.BLOCKED
            ],
        }


@dataclass(frozen=True, slots=True)
class FrontierReleaseExportArtifact:
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
class FrontierReleaseExportManifest:
    version: str
    bundle_id: str
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierReleaseExportPacket:
    bundle_id: str
    artifacts: tuple[FrontierReleaseExportArtifact, ...]
    manifest: FrontierReleaseExportManifest
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
class FrontierReleaseExportVerification:
    bundle_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def frontier_release_closure_check(
    check_id: str,
    plane: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> FrontierReleaseClosureCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": jsonable(observed),
        "expected": jsonable(expected),
        "detail": detail,
    }
    return FrontierReleaseClosureCheck(
        **body,
        content_address=content_hash(body, prefix=FRONTIER_RELEASE_CLOSURE_CHECK_PREFIX),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("FRONTIER_RELEASE_CLOSURE")
    or name.startswith("FrontierRelease")
    or name == "frontier_release_closure_check"
]

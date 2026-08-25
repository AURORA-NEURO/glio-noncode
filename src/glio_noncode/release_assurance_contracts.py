"""Typed contracts for the whole-product release-assurance gate.

Release assurance is the final aggregate boundary above the individual
capability, architecture, service, and public-surface certifications.  It
does not replace those systems.  It preserves their addresses and acceptance
states, then adds an independently addressed cross-plane decision that can be
replayed, queried, exported, and audited without exposing source records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable

RELEASE_ASSURANCE_VERSION = "release-assurance-v1"
RELEASE_ASSURANCE_SCHEMA_VERSION = "release-assurance-schema-v1"
RELEASE_ASSURANCE_RUNTIME_VERSION = "release-assurance-runtime-v1"
RELEASE_ASSURANCE_EXPORT_VERSION = "release-assurance-export-v1"
RELEASE_ASSURANCE_BOUNDARY = "public_whole_product_release_assurance"
RELEASE_ASSURANCE_DOMAIN_IDS = (
    "capability-catalog",
    "architecture-program",
    "service-release",
    "public-surface",
)
RELEASE_ASSURANCE_DOMAIN_COUNT = len(RELEASE_ASSURANCE_DOMAIN_IDS)
RELEASE_ASSURANCE_CHECKS_PER_DOMAIN = 5
RELEASE_ASSURANCE_CROSS_CHECK_COUNT = 8
RELEASE_ASSURANCE_CHECK_COUNT = (
    RELEASE_ASSURANCE_DOMAIN_COUNT * RELEASE_ASSURANCE_CHECKS_PER_DOMAIN
    + RELEASE_ASSURANCE_CROSS_CHECK_COUNT
)
RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN = 5
RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT = (
    RELEASE_ASSURANCE_DOMAIN_COUNT * RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN
)
RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL = 12
RELEASE_ASSURANCE_PLAN_STEP_COUNT = 20
RELEASE_ASSURANCE_EVENT_COUNT = 48
RELEASE_ASSURANCE_METRIC_COUNT = 16
RELEASE_ASSURANCE_VIEW_COUNT = 4
RELEASE_ASSURANCE_FAILURE_CASE_COUNT = 8
RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT = 10
RELEASE_ASSURANCE_HANDOFF_VERSION = "release-assurance-handoff-v1"
RELEASE_ASSURANCE_HANDOFF_SCHEMA_VERSION = "release-assurance-handoff-schema-v1"
RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT = 19
RELEASE_ASSURANCE_HANDOFF_MAX_ARTIFACTS = 64
RELEASE_ASSURANCE_HANDOFF_RESOURCE_NAMES = (
    "artifacts",
    "manifest",
    "status",
)
RELEASE_ASSURANCE_RESOURCE_NAMES = (
    "domains",
    "checks",
    "evidence",
    "stages",
    "events",
    "metrics",
    "views",
)
RELEASE_ASSURANCE_DEFAULT_LIMIT = 50
RELEASE_ASSURANCE_MAX_LIMIT = 500


class ReleaseAssuranceState(StrEnum):
    """Final state of the whole-product assurance decision."""

    READY = "ready"
    BLOCKED = "blocked"


class ReleaseAssuranceHandoffState(StrEnum):
    """Filesystem state of a durable release-assurance handoff."""

    READY = "ready"
    BLOCKED = "blocked"
    MISSING = "missing"
    INSPECTED = "inspected"


class ReleaseAssurancePlane(StrEnum):
    """Planes that contribute evidence to the final decision."""

    CAPABILITY = "capability"
    ARCHITECTURE = "architecture"
    SERVICE = "service"
    PUBLIC_BOUNDARY = "public-boundary"
    CROSS_PLANE = "cross-plane"
    RUNTIME = "runtime"
    EXPORT = "export"


def _address(value: Any, prefix: str) -> str:
    return content_hash(value, prefix=prefix)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceEvidenceLink:
    link_id: str
    domain_id: str
    evidence_type: str
    source_address: str
    role: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceCheck:
    check_id: str
    domain_id: str
    plane: ReleaseAssurancePlane | str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    evidence_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceDomain:
    domain_id: str
    title: str
    denominator: int
    accepted_count: int
    readiness_percent: float
    source_address: str
    evidence_count: int
    accepted: bool
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceSummary:
    bundle_id: str
    counters: tuple[tuple[str, int | float], ...]
    domain_rows: tuple[dict[str, Any], ...]
    overall_percent: float
    accepted: bool
    content_address: str

    @property
    def counter_map(self) -> dict[str, int | float]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"counter_map": self.counter_map}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceSummaryAudit:
    bundle_id: str
    checks: tuple[ReleaseAssuranceCheck, ...]
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
class ReleaseAssuranceQueryResult:
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
class ReleaseAssuranceSnapshot:
    bundle_id: str
    run_id: str
    service_snapshot_address: str
    public_audit_address: str
    domains: tuple[ReleaseAssuranceDomain, ...]
    evidence: tuple[ReleaseAssuranceEvidenceLink, ...]
    checks: tuple[ReleaseAssuranceCheck, ...]
    overall_percent: float
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return RELEASE_ASSURANCE_BOUNDARY

    @property
    def domain_map(self) -> dict[str, ReleaseAssuranceDomain]:
        return {item.domain_id: item for item in self.domains}

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "boundary": self.boundary,
            "domain_count": len(self.domains),
            "evidence_count": len(self.evidence),
            "check_count": len(self.checks),
            "passed_check_count": self.passed_check_count,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceRuntimeStage:
    ordinal: int
    stage_id: str
    state: ReleaseAssuranceState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceRuntimeReport:
    run_id: str
    state: ReleaseAssuranceState
    stages: tuple[ReleaseAssuranceRuntimeStage, ...]
    snapshot: ReleaseAssuranceSnapshot
    indexes: ReleaseAssuranceIndexes
    index_audit: ReleaseAssuranceIndexAudit
    summary: ReleaseAssuranceSummary
    summary_audit: ReleaseAssuranceSummaryAudit
    observability: ReleaseAssuranceObservability
    graph: ReleaseAssuranceGraph
    failures: ReleaseAssuranceFailureReport
    plan: ReleaseAssurancePlan
    plan_audit: tuple[ReleaseAssuranceCheck, ...]
    views: ReleaseAssuranceViews
    views_audit: tuple[ReleaseAssuranceCheck, ...]
    replay: ReleaseAssuranceReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "stage_count": len(self.stages),
            "failed_stage_ids": [
                item.stage_id for item in self.stages if item.state is ReleaseAssuranceState.BLOCKED
            ],
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceEvent:
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
class ReleaseAssuranceMetric:
    metric_id: str
    domain_id: str
    name: str
    value: int | float
    unit: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceObservability:
    bundle_id: str
    events: tuple[ReleaseAssuranceEvent, ...]
    metrics: tuple[ReleaseAssuranceMetric, ...]
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
class ReleaseAssuranceView:
    view_id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    source_domain_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"row_count": len(self.rows)}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceViews:
    bundle_id: str
    views: tuple[ReleaseAssuranceView, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"view_count": len(self.views)}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceGraphNode:
    node_id: str
    node_type: str
    reference: str
    domain_id: str | None
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceGraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceGraph:
    bundle_id: str
    nodes: tuple[ReleaseAssuranceGraphNode, ...]
    edges: tuple[ReleaseAssuranceGraphEdge, ...]
    connected: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceIndexEntry:
    index_name: str
    key: str
    resource: str
    reference: str
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceIndexes:
    bundle_id: str
    by_domain_id: tuple[ReleaseAssuranceIndexEntry, ...]
    by_check_id: tuple[ReleaseAssuranceIndexEntry, ...]
    by_evidence_id: tuple[ReleaseAssuranceIndexEntry, ...]
    by_content_address: tuple[ReleaseAssuranceIndexEntry, ...]
    by_state: tuple[ReleaseAssuranceIndexEntry, ...]
    accepted: bool
    content_address: str

    @property
    def entries(self) -> tuple[ReleaseAssuranceIndexEntry, ...]:
        return (*self.by_domain_id, *self.by_check_id, *self.by_evidence_id,
                *self.by_content_address, *self.by_state)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"entry_count": len(self.entries)}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceIndexAudit:
    bundle_id: str
    checks: tuple[ReleaseAssuranceCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count,
                                 "failed_count": len(self.checks) - self.passed_count}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceFailureCase:
    case_id: str
    mutation: str
    expected_failure: str
    observed_failure: str
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceFailureReport:
    bundle_id: str
    cases: tuple[ReleaseAssuranceFailureCase, ...]
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
class ReleaseAssurancePlanStep:
    ordinal: int
    step_id: str
    phase: str
    action: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    check_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssurancePlan:
    bundle_id: str
    steps: tuple[ReleaseAssurancePlanStep, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"step_count": len(self.steps)}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceExportArtifact:
    relative_path: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    content: bytes

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceExportManifest:
    version: str
    bundle_id: str
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceExportPacket:
    bundle_id: str
    artifacts: tuple[ReleaseAssuranceExportArtifact, ...]
    manifest: ReleaseAssuranceExportManifest
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
class ReleaseAssuranceExportVerification:
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


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceReconciliationRow:
    """One independently computed conservation comparison."""

    row_id: str
    plane: ReleaseAssurancePlane
    metric: str
    expected: Any
    observed: Any
    passed: bool
    detail: str
    evidence_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceReconciliation:
    """Independent denominator, address, and partition reconciliation."""

    bundle_id: str
    rows: tuple[ReleaseAssuranceReconciliationRow, ...]
    accepted: bool
    content_address: str

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def failed_row_ids(self) -> tuple[str, ...]:
        return tuple(item.row_id for item in self.rows if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "row_count": self.row_count,
            "failed_row_ids": self.failed_row_ids,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceDiff:
    """Address-only difference between two assurance snapshots."""

    left_bundle_id: str
    right_bundle_id: str
    left_address: str
    right_address: str
    added_domain_ids: tuple[str, ...]
    removed_domain_ids: tuple[str, ...]
    changed_domain_ids: tuple[str, ...]
    added_check_ids: tuple[str, ...]
    removed_check_ids: tuple[str, ...]
    changed_check_ids: tuple[str, ...]
    changed_addresses: tuple[str, ...]
    identical: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceCatalogEntry:
    """Public catalog metadata for one bounded assurance resource."""

    resource: str
    title: str
    key_field: str
    source_plane: ReleaseAssurancePlane
    row_count: int
    address: str
    public: bool
    queryable: bool
    exportable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceCatalog:
    """Versioned resource catalog used by clients and offline tooling."""

    bundle_id: str
    entries: tuple[ReleaseAssuranceCatalogEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"entry_count": len(self.entries)}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceComplianceItem:
    """One public-boundary compliance result."""

    item_id: str
    scope: str
    rule: str
    observed: Any
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceComplianceReport:
    """Boundary, path, address, and metadata compliance report."""

    bundle_id: str
    items: tuple[ReleaseAssuranceComplianceItem, ...]
    accepted: bool
    content_address: str

    @property
    def failed_item_ids(self) -> tuple[str, ...]:
        return tuple(item.item_id for item in self.items if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "item_count": len(self.items),
            "failed_item_ids": self.failed_item_ids,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssurancePerformanceBudget:
    """Structural ceiling for one release-assurance build."""

    name: str
    maximum: int
    observed: int
    unit: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssurancePerformanceReport:
    """Bounded count budget report for large public projections."""

    bundle_id: str
    budgets: tuple[ReleaseAssurancePerformanceBudget, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "budget_count": len(self.budgets),
            "failed_budget_names": tuple(item.name for item in self.budgets if not item.passed),
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceOperation:
    """One actionable release-assurance operator row."""

    operation_id: str
    operation_type: str
    priority: int
    state: ReleaseAssuranceState
    topic: str
    source_address: str
    action: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceOperations:
    """Deterministic operator queue over checks, stages, and controls."""

    bundle_id: str
    operations: tuple[ReleaseAssuranceOperation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "operation_count": len(self.operations),
            "blocked_count": sum(item.state is ReleaseAssuranceState.BLOCKED for item in self.operations),
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceCheckpoint:
    """Portable checkpoint joining every deep assurance projection."""

    bundle_id: str
    run_id: str
    snapshot_address: str
    component_addresses: tuple[tuple[str, str, bool], ...]
    accepted: bool
    content_address: str

    @property
    def component_count(self) -> int:
        return len(self.component_addresses)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"component_count": self.component_count}


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceReviewItem:
    """One bounded reviewer assignment generated from release evidence."""

    review_id: str
    priority: int
    state: ReleaseAssuranceState
    topic: str
    reason: str
    action: str
    evidence_addresses: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceReviewQueue:
    """Deterministic review queue for release decisions and failed controls."""

    bundle_id: str
    run_id: str
    items: tuple[ReleaseAssuranceReviewItem, ...]
    accepted: bool
    content_address: str

    @property
    def review_count(self) -> int:
        return len(self.items)

    @property
    def blocked_count(self) -> int:
        return sum(item.state is ReleaseAssuranceState.BLOCKED for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHistoryEvent:
    """Append-only event connecting runtime and reviewer projections."""

    sequence: int
    event_id: str
    event_type: str
    topic: str
    state: ReleaseAssuranceState
    input_address: str
    output_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHistory:
    """Addressed append-only history for one release-assurance run."""

    bundle_id: str
    run_id: str
    events: tuple[ReleaseAssuranceHistoryEvent, ...]
    accepted: bool
    content_address: str

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def failed_event_ids(self) -> tuple[str, ...]:
        return tuple(item.event_id for item in self.events if not item.accepted)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "event_count": self.event_count,
            "failed_event_ids": self.failed_event_ids,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceThresholdResult:
    """One explicit release threshold evaluation."""

    threshold_id: str
    name: str
    expected: Any
    observed: Any
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceThresholdReport:
    """Fail-closed threshold decision over snapshot and runtime state."""

    bundle_id: str
    results: tuple[ReleaseAssuranceThresholdResult, ...]
    accepted: bool
    content_address: str

    @property
    def failed_threshold_ids(self) -> tuple[str, ...]:
        return tuple(item.threshold_id for item in self.results if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "threshold_count": len(self.results),
            "failed_threshold_ids": self.failed_threshold_ids,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHandoffArtifact:
    """One exact-byte artifact in a durable release handoff."""

    artifact_id: str
    relative_path: str
    media_type: str
    role: str
    source_address: str
    byte_count: int
    line_count: int
    content_address: str
    required: bool
    content: bytes

    def metadata_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content": None}

    def to_dict(self) -> dict[str, Any]:
        return self.metadata_dict()


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHandoffManifest:
    """Public manifest that can be inspected without loading source planes."""

    version: str
    schema_version: str
    bundle_id: str
    run_id: str
    artifact_count: int
    required_artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    source_addresses: tuple[tuple[str, str], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHandoffPacket:
    """In-memory handoff packet ready for exact-byte persistence."""

    bundle_id: str
    run_id: str
    artifacts: tuple[ReleaseAssuranceHandoffArtifact, ...]
    manifest: ReleaseAssuranceHandoffManifest
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "artifacts": [item.metadata_dict() for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHandoffVerification:
    """Detailed filesystem verification result for a durable handoff."""

    directory: str
    state: ReleaseAssuranceHandoffState
    bundle_id: str
    run_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    duplicate_paths: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    tampered_paths: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    manifest_drift: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHandoffInspection:
    """Manifest-only inspection result for offline tooling."""

    directory: str
    state: ReleaseAssuranceHandoffState
    bundle_id: str
    run_id: str
    artifact_count: int
    required_artifact_count: int
    artifact_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceHandoffQueryResult:
    """Bounded manifest catalog query result."""

    directory: str
    resource: str
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
class ReleaseAssuranceHandoffDiff:
    """Address-only comparison between two persisted handoff manifests."""

    left_directory: str
    right_directory: str
    left_manifest_address: str
    right_manifest_address: str
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    unchanged_artifact_ids: tuple[str, ...]
    identical: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def check(
    check_id: str,
    domain_id: str,
    plane: ReleaseAssurancePlane | str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    evidence_addresses: tuple[str, ...] = (),
) -> ReleaseAssuranceCheck:
    """Construct one independently addressed assurance check."""

    body = {
        "check_id": check_id,
        "domain_id": domain_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "detail": detail,
        "evidence_addresses": evidence_addresses,
    }
    return ReleaseAssuranceCheck(
        **body,
        content_address=_address(body, "release-assurance-check"),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE")
    or name.startswith("ReleaseAssurance")
    or name == "check"
]

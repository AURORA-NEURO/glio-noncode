"""Closed contracts for the D16 coordination architecture.

This module defines the stable public projections used by the coordination
runtime.  The contracts describe planning and execution control, not model
attribution or clinical interpretation.  Payloads are aggregate-only and each
material receipt is content addressed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty


COORDINATION_VERSION = "2026.08.coordination-architecture.v1"
COORDINATION_BOUNDARY = "public_aggregate_platform_coordination"
COORDINATION_CONTEXT = "GRCh38|glioma|adult|stem_like|aggregate|pre_treatment"
COORDINATION_FOREIGN_CONTEXT = "GRCh38|glioma|adult|stem_like|aggregate|post_treatment"
COORDINATION_OPERATION_COUNT = 16
COORDINATION_CASES_PER_OPERATION = 4
COORDINATION_CASE_COUNT = COORDINATION_OPERATION_COUNT * COORDINATION_CASES_PER_OPERATION


class CoordinationState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


class CoordinationRole(StrEnum):
    PLANNER = "planner"
    COMPILER = "compiler"
    TOOL_REGISTRY = "tool_registry"
    SANDBOX = "sandbox"
    POLICY = "policy"
    SCHEDULER = "scheduler"
    FALLBACK = "fallback"
    REVIEW = "review"
    LEDGER = "ledger"
    COMPUTE_REGISTRY = "compute_registry"
    REFERENCE_REGISTRY = "reference_registry"
    MONITORING = "monitoring"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    FEDERATION = "federation"
    RELEASE = "release"


class CoordinationScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    BUDGET_EXCEEDED = "budget_exceeded"
    CONTRACT_MISMATCH = "contract_mismatch"


class CoordinationPlane(StrEnum):
    IDENTITY = "identity"
    CONTRACT = "contract"
    POLICY = "policy"
    RESOURCE = "resource"
    REVIEW = "review"
    INTEGRITY = "integrity"
    RELEASE = "release"


class CoordinationOperation(StrEnum):
    MISSION_PLAN = "mission_plan"
    WORKFLOW_COMPILE = "workflow_compile"
    TYPED_TOOL_REGISTRY = "typed_tool_registry"
    EXECUTION_SANDBOX = "execution_sandbox"
    CLAIM_GATE = "claim_gate"
    RESOURCE_SCHEDULE = "resource_schedule"
    FALLBACK_ROUTE = "fallback_route"
    HUMAN_REVIEW = "human_review"
    EVENT_LEDGER = "event_ledger"
    COMPUTE_REGISTRY = "compute_registry"
    REFERENCE_REGISTRY = "reference_registry"
    DRIFT_MONITOR = "drift_monitor"
    SECURITY_POLICY = "security_policy"
    DEPLOYMENT_BUNDLE = "deployment_bundle"
    FEDERATED_COORDINATION = "federated_coordination"
    RELEASE_ROLLBACK = "release_rollback"


class CoordinationCheckKind(StrEnum):
    FIXTURE = "fixture"
    OPERATION = "operation"
    PLAN = "plan"
    TOOL = "tool"
    SANDBOX = "sandbox"
    POLICY = "policy"
    RESOURCE = "resource"
    REVIEW = "review"
    LEDGER = "ledger"
    REGISTRY = "registry"
    MONITORING = "monitoring"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    RELEASE = "release"
    INTEGRITY = "integrity"


def _address(value: Any, prefix: str) -> str:
    return content_hash(value, prefix=prefix)


@dataclass(frozen=True, slots=True)
class CoordinationSource:
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
            raise ValueError("coordination sources require HTTPS")
        if self.scope != "public_aggregate":
            raise ValueError("coordination sources are public aggregate only")
        if ":" not in self.content_address:
            raise ValueError("coordination sources require content addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: CoordinationOperation
    role: CoordinationRole
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    budget_units: int
    requires_review: bool
    source_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "operation_id",
            "capability_id",
            "input_contract",
            "output_contract",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.ordinal < 1 or self.budget_units < 1:
            raise ValueError("operation ordinals and budgets must be positive")
        if not self.source_ids:
            raise ValueError("operation specs require public source joins")
        if ":" not in self.content_address:
            raise ValueError("operation specs require content addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationCase:
    case_id: str
    operation_id: str
    capability_id: str
    role: CoordinationRole
    scenario: CoordinationScenario
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CoordinationState
    expected_issue_codes: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "case_id",
            "operation_id",
            "capability_id",
            "context_key",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not self.payload:
            raise ValueError("coordination cases require sources and public payload fields")
        if ":" not in self.content_address:
            raise ValueError("coordination cases require content addresses")
        if self.scenario is CoordinationScenario.POSITIVE and self.expected_state is not CoordinationState.ACCEPTED:
            raise ValueError("positive coordination cases must expect acceptance")
        if self.scenario is not CoordinationScenario.POSITIVE and self.expected_state is CoordinationState.ACCEPTED:
            raise ValueError("coordination controls must not expect acceptance")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[CoordinationSource, ...]
    operations: tuple[CoordinationOperationSpec, ...]
    cases: tuple[CoordinationCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "boundary", "context_key", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != COORDINATION_VERSION:
            raise ValueError("unsupported coordination fixture version")
        if self.boundary != COORDINATION_BOUNDARY:
            raise ValueError("coordination boundary is closed")
        if len(self.operations) != COORDINATION_OPERATION_COUNT:
            raise ValueError("coordination fixture requires sixteen operation specs")
        if len(self.cases) != COORDINATION_CASE_COUNT:
            raise ValueError("coordination fixture requires four cases per operation")
        if not self.sources or ":" not in self.content_address:
            raise ValueError("coordination fixture requires public sources and an address")

    @property
    def positive_cases(self) -> tuple[CoordinationCase, ...]:
        return tuple(item for item in self.cases if item.scenario is CoordinationScenario.POSITIVE)

    @property
    def control_cases(self) -> tuple[CoordinationCase, ...]:
        return tuple(item for item in self.cases if item.scenario is not CoordinationScenario.POSITIVE)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationPlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    budget_units: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationPlan:
    plan_id: str
    nodes: tuple[CoordinationPlanNode, ...]
    total_budget_units: int
    accepted: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationToolSpec:
    tool_id: str
    operation_id: str
    input_contract: str
    output_contract: str
    deterministic: bool
    network_allowed: bool
    public_aggregate_only: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("tool_id", "operation_id", "input_contract", "output_contract", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.public_aggregate_only:
            raise ValueError("coordination tools must be aggregate-only")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationToolRegistry:
    registry_id: str
    tools: tuple[CoordinationToolSpec, ...]
    accepted: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationExecution:
    case_id: str
    operation_id: str
    capability_id: str
    scenario: CoordinationScenario
    expected_state: CoordinationState
    observed_state: CoordinationState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    tool_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationEvaluation:
    fixture_id: str
    executions: tuple[CoordinationExecution, ...]
    passed_cases: int
    failed_cases: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationCheck:
    check_id: str
    kind: CoordinationCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationPolicyDecision:
    decision_id: str
    state: CoordinationState
    allowed: bool
    reasons: tuple[str, ...]
    claim_boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationSchedule:
    schedule_id: str
    order: tuple[str, ...]
    capacity_units: int
    used_units: int
    accepted: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationReviewItem:
    review_id: str
    case_id: str
    operation_id: str
    priority: int
    issue_codes: tuple[str, ...]
    sla_band: str
    state: CoordinationState
    content_address: str

    def __post_init__(self) -> None:
        if self.state is CoordinationState.ACCEPTED or self.priority < 1:
            raise ValueError("review items must be prioritized held work")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationLedgerEvent:
    event_id: str
    ordinal: int
    event_type: str
    case_id: str
    state: CoordinationState
    previous_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationLedger:
    ledger_id: str
    events: tuple[CoordinationLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationRegistryEntry:
    entry_id: str
    kind: str
    title: str
    version: str
    digest: str
    contract: str
    public_scope: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationRegistry:
    registry_id: str
    kind: str
    entries: tuple[CoordinationRegistryEntry, ...]
    accepted: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationObservation:
    observation_id: str
    operation_id: str
    observed_context: str
    reference_rate: float
    drift_score: float
    out_of_domain: bool
    state: CoordinationState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationSecurityDecision:
    decision_id: str
    path_class: str
    network_requested: bool
    private_key_detected: bool
    state: CoordinationState
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationDeploymentArtifact:
    artifact_id: str
    artifact_kind: str
    digest: str
    offline_capable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationAssignment:
    assignment_id: str
    site_id: str
    operation_id: str
    context_key: str
    eligible: bool
    privacy_cost: int
    state: CoordinationState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationRelease:
    release_id: str
    version: str
    state: CoordinationState
    artifact_addresses: tuple[str, ...]
    blockers: tuple[str, ...]
    rollback_version: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationRuntimeStage:
    stage_id: str
    ordinal: int
    state: CoordinationState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationRuntime:
    run_id: str
    stages: tuple[CoordinationRuntimeStage, ...]
    state: CoordinationState
    fixture_id: str
    evaluation: CoordinationEvaluation
    plan: CoordinationPlan
    tools: CoordinationToolRegistry
    schedule: CoordinationSchedule
    ledger: CoordinationLedger
    compute_registry: CoordinationRegistry
    reference_registry: CoordinationRegistry
    observations: tuple[CoordinationObservation, ...]
    security: tuple[CoordinationSecurityDecision, ...]
    deployment_artifacts: tuple[CoordinationDeploymentArtifact, ...]
    assignments: tuple[CoordinationAssignment, ...]
    release: CoordinationRelease
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationQualityReport:
    fixture_id: str
    checks: tuple[CoordinationCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationFailureProbe:
    probe_id: str
    expected_state: CoordinationState
    observed_state: CoordinationState
    passed: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoordinationFailureReport:
    probes: tuple[CoordinationFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def addressed(value: Any, prefix: str = "coordination") -> str:
    return _address(value, prefix)


__all__ = [
    "COORDINATION_VERSION",
    "COORDINATION_BOUNDARY",
    "COORDINATION_CONTEXT",
    "COORDINATION_FOREIGN_CONTEXT",
    "COORDINATION_OPERATION_COUNT",
    "COORDINATION_CASES_PER_OPERATION",
    "COORDINATION_CASE_COUNT",
    "CoordinationState",
    "CoordinationRole",
    "CoordinationScenario",
    "CoordinationPlane",
    "CoordinationOperation",
    "CoordinationCheckKind",
    "CoordinationSource",
    "CoordinationOperationSpec",
    "CoordinationCase",
    "CoordinationFixture",
    "CoordinationPlanNode",
    "CoordinationPlan",
    "CoordinationToolSpec",
    "CoordinationToolRegistry",
    "CoordinationExecution",
    "CoordinationEvaluation",
    "CoordinationCheck",
    "CoordinationPolicyDecision",
    "CoordinationSchedule",
    "CoordinationReviewItem",
    "CoordinationLedgerEvent",
    "CoordinationLedger",
    "CoordinationRegistryEntry",
    "CoordinationRegistry",
    "CoordinationObservation",
    "CoordinationSecurityDecision",
    "CoordinationDeploymentArtifact",
    "CoordinationAssignment",
    "CoordinationRelease",
    "CoordinationRuntimeStage",
    "CoordinationRuntime",
    "CoordinationQualityReport",
    "CoordinationFailureProbe",
    "CoordinationFailureReport",
    "addressed",
]

"""Typed D16 contracts for platform execution and deployment architecture."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

PLATFORM_EXECUTION_ARCHITECTURE_VERSION = "2026.08.d16-platform-execution.v1"
PLATFORM_EXECUTION_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
PLATFORM_EXECUTION_ARCHITECTURE_CONTEXT = "multi_context_public_aggregate"
PLATFORM_EXECUTION_ARCHITECTURE_FOREIGN_CONTEXT = "foreign_context_control"
PLATFORM_EXECUTION_ARCHITECTURE_SOURCE_COUNT = 19
PLATFORM_EXECUTION_ARCHITECTURE_OPERATION_COUNT = 16
PLATFORM_EXECUTION_ARCHITECTURE_CASE_COUNT = 64
PLATFORM_EXECUTION_ARCHITECTURE_CASES_PER_OPERATION = 4
PLATFORM_EXECUTION_ARCHITECTURE_ARTIFACT_COUNT = 6


class PlatformExecutionState(StrEnum):
    READY = "ready"
    ABSTAINED = "abstained"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    PARTIAL = "partial"
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    ADMITTED = "admitted"
    DENIED = "denied"
    SUPPORTED = "supported"
    SELECTED = "selected"
    EMPTY = "empty"
    COMPLETED = "completed"
    OUT_OF_DOMAIN = "out_of_domain"
    WATCH = "watch"
    DRIFT = "drift"
    HOLD = "hold"
    RELEASED = "released"
    REVIEW = "review"
    PUBLISHED = "published"


class PlatformExecutionScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class PlatformExecutionFamily(StrEnum):
    PLATFORM = "platform_frontier"
    CONTROL = "control_frontier"
    DEPLOYMENT = "deployment_frontier"


class PlatformExecutionPlane(StrEnum):
    PLATFORM_CONTROL = "platform_control"
    QUALITY_CONTROL = "quality_control"
    DEPLOYMENT = "deployment"


class PlatformExecutionOperation(StrEnum):
    MISSION_PLANNER = "mission_planner"
    WORKFLOW_COMPILER = "workflow_compiler"
    TYPED_TOOL_REGISTRY = "typed_tool_registry"
    EXECUTION_SANDBOX = "execution_sandbox"
    POLICY_CLAIM_GATE = "policy_claim_gate"
    BUDGET_RESOURCE_SCHEDULER = "budget_resource_scheduler"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    HUMAN_REVIEW_ROUTER = "human_review_router"
    EXECUTION_LEDGER = "execution_ledger"
    MODEL_REGISTRY = "model_registry"
    DATA_REFERENCE_REGISTRY = "data_reference_registry"
    DRIFT_OOD_MONITOR = "drift_ood_monitor"
    PRIVACY_SECURITY_POLICY = "privacy_security_policy"
    LOCAL_DEPLOYMENT_BUNDLE = "local_deployment_bundle"
    FEDERATED_EXECUTION = "federated_execution"
    RELEASE_ROLLBACK = "release_rollback"


class PlatformExecutionCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CASE = "case"
    RESULT = "result"
    CONTROL = "control"
    SAFETY = "safety"
    REPLAY = "replay"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "platform-execution-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class PlatformExecutionSource:
    source_id: str
    family: PlatformExecutionFamily
    source_kind: str
    source_version: str
    uri: str
    source_context_key: str
    delegate_source_id: str
    delegate_fixture_id: str
    public_aggregate: bool
    delegate_content_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: PlatformExecutionOperation
    delegate_operation: str
    family: PlatformExecutionFamily
    plane: PlatformExecutionPlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionCase:
    case_id: str
    operation_id: str
    operation: PlatformExecutionOperation
    family: PlatformExecutionFamily
    plane: PlatformExecutionPlane
    scenario: PlatformExecutionScenario
    aggregate_context_key: str
    delegate_context_key: str
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_class: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: PlatformExecutionState
    expected_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    description: str
    content_address: str

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        value = jsonable(self)
        if not include_payload:
            value["payload"] = {}
        return value


@dataclass(frozen=True, slots=True)
class PlatformExecutionFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    family_contexts: Mapping[str, str]
    sources: tuple[PlatformExecutionSource, ...]
    operations: tuple[PlatformExecutionOperationSpec, ...]
    cases: tuple[PlatformExecutionCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[PlatformExecutionCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is PlatformExecutionScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[PlatformExecutionCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is not PlatformExecutionScenario.POSITIVE
        )

    @property
    def family_set(self) -> tuple[PlatformExecutionFamily, ...]:
        return tuple(PlatformExecutionFamily)

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "boundary": self.boundary,
            "context_key": self.context_key,
            "foreign_context_key": self.foreign_context_key,
            "family_contexts": jsonable(self.family_contexts),
            "sources": [item.to_dict() for item in self.sources],
            "operations": [item.to_dict() for item in self.operations],
            "cases": [item.to_dict(include_payload=include_payload) for item in self.cases],
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> PlatformExecutionFixture:
        try:
            sources = tuple(
                PlatformExecutionSource(
                    str(item["source_id"]),
                    PlatformExecutionFamily(item["family"]),
                    str(item["source_kind"]),
                    str(item["source_version"]),
                    str(item["uri"]),
                    str(item["source_context_key"]),
                    str(item["delegate_source_id"]),
                    str(item["delegate_fixture_id"]),
                    bool(item["public_aggregate"]),
                    str(item["delegate_content_address"]),
                    str(item["content_address"]),
                )
                for item in raw["sources"]
            )
            operations = tuple(
                PlatformExecutionOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    PlatformExecutionOperation(item["operation"]),
                    str(item["delegate_operation"]),
                    PlatformExecutionFamily(item["family"]),
                    PlatformExecutionPlane(item["plane"]),
                    str(item["input_contract"]),
                    str(item["output_contract"]),
                    tuple(str(value) for value in item["dependencies"]),
                    tuple(str(value) for value in item["source_ids"]),
                    str(item["control_policy"]),
                    str(item["content_address"]),
                )
                for item in raw["operations"]
            )
            cases = tuple(
                PlatformExecutionCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    PlatformExecutionOperation(item["operation"]),
                    PlatformExecutionFamily(item["family"]),
                    PlatformExecutionPlane(item["plane"]),
                    PlatformExecutionScenario(item["scenario"]),
                    str(item["aggregate_context_key"]),
                    str(item["delegate_context_key"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_class"]),
                    tuple(str(value) for value in item["source_ids"]),
                    dict(item["payload"]),
                    PlatformExecutionState(item["expected_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D16 fixture mapping is invalid: {exc}") from exc
        return cls(
            str(raw["fixture_id"]),
            str(raw["version"]),
            str(raw["boundary"]),
            str(raw["context_key"]),
            str(raw["foreign_context_key"]),
            {str(key): str(value) for key, value in dict(raw["family_contexts"]).items()},
            sources,
            operations,
            cases,
            str(raw["content_address"]),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> PlatformExecutionFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D16 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class PlatformExecutionCheck:
    check_id: str
    kind: PlatformExecutionCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionDataAudit:
    fixture_id: str
    checks: tuple[PlatformExecutionCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class PlatformExecutionExecution:
    case_id: str
    operation: PlatformExecutionOperation
    family: PlatformExecutionFamily
    scenario: PlatformExecutionScenario
    observed_state: PlatformExecutionState
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionReceipt:
    case_id: str
    operation_id: str
    expected_state: PlatformExecutionState
    observed_state: PlatformExecutionState
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    observed_counts: Mapping[str, int]
    passed: bool
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionEvaluation:
    fixture_id: str
    context_key: str
    state: str
    executions: tuple[PlatformExecutionExecution, ...]
    receipts: tuple[PlatformExecutionReceipt, ...]
    checks: tuple[PlatformExecutionCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == "accepted" and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class PlatformExecutionPlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: PlatformExecutionFamily
    plane: PlatformExecutionPlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionPlan:
    fixture_id: str
    nodes: tuple[PlatformExecutionPlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionReviewItem:
    case_id: str
    operation_id: str
    family: PlatformExecutionFamily
    scenario: PlatformExecutionScenario
    observed_state: PlatformExecutionState
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionReviewQueue:
    fixture_id: str
    items: tuple[PlatformExecutionReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionArtifact:
    artifact_id: str
    artifact_type: str
    visibility: str
    content_address: str
    source_addresses: tuple[str, ...]
    record_count: int
    review_safe: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionRelease:
    release_id: str
    fixture_id: str
    state: PlatformExecutionState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionDepthReport:
    fixture_id: str
    source_count: int
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    family_count: int
    check_count: int
    addressed_count: int
    state_count: int
    issue_code_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionQualityGate:
    fixture_id: str
    checks: tuple[PlatformExecutionCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionRuntimeStage:
    stage_id: str
    ordinal: int
    state: str
    input_addresses: tuple[str, ...]
    output_address: str
    check_ids: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformExecutionRuntime:
    fixture: PlatformExecutionFixture
    audit: PlatformExecutionDataAudit
    plan: PlatformExecutionPlan
    evaluation: PlatformExecutionEvaluation
    review_queue: PlatformExecutionReviewQueue
    ledger: PlatformExecutionLedger
    artifacts: tuple[PlatformExecutionArtifact, ...]
    release: PlatformExecutionRelease
    depth: PlatformExecutionDepthReport
    quality: PlatformExecutionQualityGate
    stages: tuple[PlatformExecutionRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("PlatformExecution")
    or name.startswith("PLATFORM_EXECUTION")
    or name == "addressed"
]

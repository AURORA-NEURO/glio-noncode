"""Typed D15 contracts for research workbench and collaboration architecture."""

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

WORKBENCH_ARCHITECTURE_VERSION = "2026.08.d15-workbench-architecture.v1"
WORKBENCH_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
WORKBENCH_ARCHITECTURE_CONTEXT = "multi_context_public_aggregate"
WORKBENCH_ARCHITECTURE_FOREIGN_CONTEXT = "foreign_context_control"
WORKBENCH_ARCHITECTURE_SOURCE_COUNT = 20
WORKBENCH_ARCHITECTURE_OPERATION_COUNT = 16
WORKBENCH_ARCHITECTURE_CASE_COUNT = 64
WORKBENCH_ARCHITECTURE_CASES_PER_OPERATION = 4
WORKBENCH_ARCHITECTURE_ARTIFACT_COUNT = 6


class WorkbenchArchitectureState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSENT = "absent"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    COMPLETE = "complete"
    CONTRADICTORY = "contradictory"
    INCOMPLETE = "incomplete"
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    DENIED = "denied"
    EXPIRED = "expired"
    READY_FOR_REVIEW = "ready_for_review"
    VERIFIED = "verified"
    REVIEWED = "reviewed"
    EXPORTED = "exported"
    SEARCHED = "searched"
    PASSED = "passed"
    PUBLISHED = "published"
    REJECTED = "rejected"
    REVIEW = "review"


class WorkbenchArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class WorkbenchArchitectureFamily(StrEnum):
    WORKSPACE_FOUNDATION = "workspace_frontier"
    WORKSPACE_BETA = "workspace_beta_frontier"
    WORKSPACE_GAMMA = "workspace_gamma_frontier"
    WORKBENCH_RELEASE = "workbench_release_frontier"


class WorkbenchArchitecturePlane(StrEnum):
    WORKSPACE_FOUNDATION = "workspace_foundation"
    WORKSPACE_BETA = "workspace_beta"
    WORKSPACE_COLLABORATION = "workspace_collaboration"
    WORKBENCH_RELEASE = "workbench_release"


class WorkbenchArchitectureOperation(StrEnum):
    CASE_WORKSPACE = "case_workspace"
    COHORT_WORKSPACE = "cohort_workspace"
    VARIANT_EXPLORER = "variant_explorer"
    REGULATORY_TRACK_BROWSER = "regulatory_track_browser"
    TOPOLOGY_VIEWER = "topology_viewer"
    CAUSAL_CHAIN_EXPLORER = "causal_chain_explorer"
    POSTERIOR_DECOMPOSITION = "posterior_decomposition"
    EVIDENCE_TABLE = "evidence_table"
    VALIDATION_EXPERIMENT_BOARD = "validation_experiment_board"
    NOTEBOOK_SDK_LAUNCHER = "notebook_sdk_launcher"
    SIGNED_SNAPSHOT = "signed_snapshot"
    ROLE_COLLABORATION = "role_collaboration"
    STRUCTURED_REVIEW = "structured_review"
    REPORT_EXPORT = "report_export"
    SEARCH_PALETTE = "search_palette"
    ACCESSIBILITY_HUMAN_FACTORS = "accessibility_human_factors"


class WorkbenchArchitectureCheckKind(StrEnum):
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


def addressed(value: Any, prefix: str = "workbench-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureSource:
    source_id: str
    family: WorkbenchArchitectureFamily
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
class WorkbenchArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: WorkbenchArchitectureOperation
    delegate_operation: str
    family: WorkbenchArchitectureFamily
    plane: WorkbenchArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureCase:
    case_id: str
    operation_id: str
    operation: WorkbenchArchitectureOperation
    family: WorkbenchArchitectureFamily
    plane: WorkbenchArchitecturePlane
    scenario: WorkbenchArchitectureScenario
    aggregate_context_key: str
    delegate_context_key: str
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_class: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: WorkbenchArchitectureState
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
class WorkbenchArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    family_contexts: Mapping[str, str]
    sources: tuple[WorkbenchArchitectureSource, ...]
    operations: tuple[WorkbenchArchitectureOperationSpec, ...]
    cases: tuple[WorkbenchArchitectureCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[WorkbenchArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is WorkbenchArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[WorkbenchArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not WorkbenchArchitectureScenario.POSITIVE
        )

    @property
    def family_set(self) -> tuple[WorkbenchArchitectureFamily, ...]:
        return tuple(WorkbenchArchitectureFamily)

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
    def from_mapping(cls, raw: Mapping[str, Any]) -> WorkbenchArchitectureFixture:
        try:
            sources = tuple(
                WorkbenchArchitectureSource(
                    str(item["source_id"]),
                    WorkbenchArchitectureFamily(item["family"]),
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
                WorkbenchArchitectureOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    WorkbenchArchitectureOperation(item["operation"]),
                    str(item["delegate_operation"]),
                    WorkbenchArchitectureFamily(item["family"]),
                    WorkbenchArchitecturePlane(item["plane"]),
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
                WorkbenchArchitectureCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    WorkbenchArchitectureOperation(item["operation"]),
                    WorkbenchArchitectureFamily(item["family"]),
                    WorkbenchArchitecturePlane(item["plane"]),
                    WorkbenchArchitectureScenario(item["scenario"]),
                    str(item["aggregate_context_key"]),
                    str(item["delegate_context_key"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_class"]),
                    tuple(str(value) for value in item["source_ids"]),
                    dict(item["payload"]),
                    WorkbenchArchitectureState(item["expected_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D15 fixture mapping is invalid: {exc}") from exc
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
    def from_file(cls, path: str | Path) -> WorkbenchArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D15 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureCheck:
    check_id: str
    kind: WorkbenchArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureDataAudit:
    fixture_id: str
    checks: tuple[WorkbenchArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureExecution:
    case_id: str
    operation: WorkbenchArchitectureOperation
    family: WorkbenchArchitectureFamily
    scenario: WorkbenchArchitectureScenario
    observed_state: WorkbenchArchitectureState
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: WorkbenchArchitectureState
    observed_state: WorkbenchArchitectureState
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
class WorkbenchArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: str
    executions: tuple[WorkbenchArchitectureExecution, ...]
    receipts: tuple[WorkbenchArchitectureCaseReceipt, ...]
    checks: tuple[WorkbenchArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == "accepted" and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class WorkbenchArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: WorkbenchArchitectureFamily
    plane: WorkbenchArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitecturePlan:
    fixture_id: str
    nodes: tuple[WorkbenchArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureReviewItem:
    case_id: str
    operation_id: str
    family: WorkbenchArchitectureFamily
    scenario: WorkbenchArchitectureScenario
    observed_state: WorkbenchArchitectureState
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureReviewQueue:
    fixture_id: str
    items: tuple[WorkbenchArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureArtifact:
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
class WorkbenchArchitectureRelease:
    release_id: str
    fixture_id: str
    state: WorkbenchArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureRuntimeStage:
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
class WorkbenchArchitectureDepthReport:
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
class WorkbenchArchitectureQualityGate:
    fixture_id: str
    checks: tuple[WorkbenchArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureRuntime:
    fixture: WorkbenchArchitectureFixture
    audit: WorkbenchArchitectureDataAudit
    plan: WorkbenchArchitecturePlan
    evaluation: WorkbenchArchitectureEvaluation
    review_queue: WorkbenchArchitectureReviewQueue
    ledger: WorkbenchArchitectureLedger
    artifacts: tuple[WorkbenchArchitectureArtifact, ...]
    release: WorkbenchArchitectureRelease
    depth: WorkbenchArchitectureDepthReport
    quality: WorkbenchArchitectureQualityGate
    stages: tuple[WorkbenchArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("WorkbenchArchitecture")
    or name.startswith("WORKBENCH_ARCHITECTURE")
    or name == "addressed"
]

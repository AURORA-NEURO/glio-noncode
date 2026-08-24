"""Typed D13 contracts for research planning and validation architecture."""

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

PLANNING_ARCHITECTURE_VERSION = "2026.08.d13-planning-architecture.v1"
PLANNING_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
PLANNING_ARCHITECTURE_CONTEXT = "multi_context_public_aggregate"
PLANNING_ARCHITECTURE_FOREIGN_CONTEXT = "foreign_context_control"
PLANNING_ARCHITECTURE_SOURCE_COUNT = 20
PLANNING_ARCHITECTURE_OPERATION_COUNT = 16
PLANNING_ARCHITECTURE_CASE_COUNT = 64
PLANNING_ARCHITECTURE_CASES_PER_OPERATION = 4
PLANNING_ARCHITECTURE_ARTIFACT_COUNT = 6


class PlanningArchitectureState(StrEnum):
    READY = "ready"
    ROUTED = "routed"
    PACKAGED = "packaged"
    DESIGNED = "designed"
    READY_FOR_REVIEW = "ready_for_review"
    UPDATED = "updated"
    BLOCKED = "blocked"
    REVIEW = "review"
    REJECTED = "rejected"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    PUBLISHED = "published"


class PlanningArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class PlanningArchitectureFamily(StrEnum):
    VALIDATION_DESIGN = "validation_design_frontier"
    EDITING_DESIGN = "editing_design_frontier"
    PLANNING = "planning_frontier"
    VALIDATION_RELEASE = "validation_release_frontier"


class PlanningArchitecturePlane(StrEnum):
    VALIDATION_DESIGN = "validation_design"
    EDITING_DESIGN = "editing_design"
    PLANNING = "planning"
    VALIDATION_RELEASE = "validation_release"


class PlanningArchitectureOperation(StrEnum):
    EVIDENCE_GAP = "evidence_gap"
    ASSAY_ELIGIBILITY = "assay_eligibility"
    MPRA_CONSTRUCT = "mpra_construct"
    STARRSEQ_CONSTRUCT = "starrseq_construct"
    CRISPR_DESIGN = "crispr_design"
    BASE_EDITING = "base_editing"
    PRIME_EDITING = "prime_editing"
    ALLELE_REPORTER = "allele_reporter"
    MODEL_ELIGIBILITY = "model_eligibility"
    GUIDE_ADAPTATION = "guide_adaptation"
    CONTROLS_RANDOMIZATION = "controls_randomization"
    POWER_REPLICATION = "power_replication"
    OFF_TARGET_RISK = "off_target_risk"
    VALUE_OF_INFORMATION = "value_of_information"
    EXPERIMENT_PACKAGE = "experiment_package"
    CLAIM_UPDATE = "claim_update"


class PlanningArchitectureCheckKind(StrEnum):
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


def addressed(value: Any, prefix: str = "planning-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class PlanningArchitectureSource:
    source_id: str
    family: PlanningArchitectureFamily
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
class PlanningArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: PlanningArchitectureOperation
    delegate_operation: str
    family: PlanningArchitectureFamily
    plane: PlanningArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureCase:
    case_id: str
    operation_id: str
    operation: PlanningArchitectureOperation
    family: PlanningArchitectureFamily
    plane: PlanningArchitecturePlane
    scenario: PlanningArchitectureScenario
    aggregate_context_key: str
    delegate_context_key: str
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_class: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: PlanningArchitectureState
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
class PlanningArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    family_contexts: Mapping[str, str]
    sources: tuple[PlanningArchitectureSource, ...]
    operations: tuple[PlanningArchitectureOperationSpec, ...]
    cases: tuple[PlanningArchitectureCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[PlanningArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is PlanningArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[PlanningArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not PlanningArchitectureScenario.POSITIVE
        )

    @property
    def family_set(self) -> tuple[PlanningArchitectureFamily, ...]:
        return tuple(PlanningArchitectureFamily)

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
    def from_mapping(cls, raw: Mapping[str, Any]) -> PlanningArchitectureFixture:
        try:
            sources = tuple(
                PlanningArchitectureSource(
                    str(item["source_id"]),
                    PlanningArchitectureFamily(item["family"]),
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
                PlanningArchitectureOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    PlanningArchitectureOperation(item["operation"]),
                    str(item["delegate_operation"]),
                    PlanningArchitectureFamily(item["family"]),
                    PlanningArchitecturePlane(item["plane"]),
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
                PlanningArchitectureCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    PlanningArchitectureOperation(item["operation"]),
                    PlanningArchitectureFamily(item["family"]),
                    PlanningArchitecturePlane(item["plane"]),
                    PlanningArchitectureScenario(item["scenario"]),
                    str(item["aggregate_context_key"]),
                    str(item["delegate_context_key"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_class"]),
                    tuple(str(value) for value in item["source_ids"]),
                    dict(item["payload"]),
                    PlanningArchitectureState(item["expected_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D13 fixture mapping is invalid: {exc}") from exc
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
    def from_file(cls, path: str | Path) -> PlanningArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D13 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureCheck:
    check_id: str
    kind: PlanningArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureDataAudit:
    fixture_id: str
    checks: tuple[PlanningArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class PlanningArchitectureExecution:
    case_id: str
    operation: PlanningArchitectureOperation
    family: PlanningArchitectureFamily
    scenario: PlanningArchitectureScenario
    observed_state: PlanningArchitectureState
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: PlanningArchitectureState
    observed_state: PlanningArchitectureState
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
class PlanningArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: str
    executions: tuple[PlanningArchitectureExecution, ...]
    receipts: tuple[PlanningArchitectureCaseReceipt, ...]
    checks: tuple[PlanningArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == "accepted" and all(item.passed for item in self.checks)

    def execution_map(self) -> dict[str, PlanningArchitectureExecution]:
        return {item.case_id: item for item in self.executions}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class PlanningArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: PlanningArchitectureFamily
    plane: PlanningArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitecturePlan:
    fixture_id: str
    nodes: tuple[PlanningArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureReviewItem:
    case_id: str
    operation_id: str
    family: PlanningArchitectureFamily
    scenario: PlanningArchitectureScenario
    observed_state: PlanningArchitectureState
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureReviewQueue:
    fixture_id: str
    items: tuple[PlanningArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureArtifact:
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
class PlanningArchitectureRelease:
    release_id: str
    fixture_id: str
    state: PlanningArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureRuntimeStage:
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
class PlanningArchitectureRuntime:
    fixture: PlanningArchitectureFixture
    audit: PlanningArchitectureDataAudit
    plan: PlanningArchitecturePlan
    evaluation: PlanningArchitectureEvaluation
    review_queue: PlanningArchitectureReviewQueue
    ledger: PlanningArchitectureLedger
    artifacts: tuple[PlanningArchitectureArtifact, ...]
    release: PlanningArchitectureRelease
    depth: PlanningArchitectureDepthReport
    quality: PlanningArchitectureQualityGate
    stages: tuple[PlanningArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningArchitectureDepthReport:
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
class PlanningArchitectureQualityGate:
    fixture_id: str
    checks: tuple[PlanningArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("PlanningArchitecture")
    or name.startswith("PLANNING_ARCHITECTURE")
    or name == "addressed"
]

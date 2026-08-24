"""Typed D12 contracts for cohort discovery and longitudinal aggregates."""

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

COHORT_ARCHITECTURE_VERSION = "2026.08.d12-cohort-architecture.v1"
COHORT_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
COHORT_ARCHITECTURE_CONTEXT = "multi_context_public_aggregate"
COHORT_ARCHITECTURE_FOREIGN_CONTEXT = "foreign_context_control"
COHORT_ARCHITECTURE_SOURCE_COUNT = 22
COHORT_ARCHITECTURE_OPERATION_COUNT = 16
COHORT_ARCHITECTURE_CASE_COUNT = 64
COHORT_ARCHITECTURE_CASES_PER_OPERATION = 4
COHORT_ARCHITECTURE_ARTIFACT_COUNT = 6


class CohortArchitectureState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSENT = "absent"
    ABSTAINED = "abstained"
    CONTRADICTORY = "contradictory"
    AMBIGUOUS = "ambiguous"
    REVIEW = "review"
    INVALID = "invalid"
    PUBLISHED = "published"


class CohortArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class CohortArchitectureFamily(StrEnum):
    FOUNDATION = "cohort_foundation_frontier"
    BETA = "cohort_beta_frontier"
    ALPHA = "cohort_alpha_frontier"
    FRONTIER = "cohort_frontier"


class CohortArchitecturePlane(StrEnum):
    FOUNDATION = "cohort_foundation"
    BETA = "cohort_convergence"
    ALPHA = "cohort_longitudinal"
    FRONTIER = "cohort_release"


class CohortArchitectureOperation(StrEnum):
    COHORT_QUERY = "cohort_query"
    BACKGROUND_RATE = "background_rate"
    SEQUENCE_CONTROL = "sequence_control"
    CHROMATIN_CONTROL = "chromatin_control"
    REGULATORY_RECURRENCE = "regulatory_recurrence"
    REGIONAL_BURDEN = "regional_burden"
    FUNCTIONAL_CONVERGENCE = "functional_convergence"
    PATHWAY_REGULON_CONVERGENCE = "pathway_regulon_convergence"
    CLONALITY_TIMING = "clonality_timing"
    PRIMARY_RECURRENCE = "primary_recurrence"
    TREATMENT_SELECTION = "treatment_selection"
    CROSS_COHORT_REPLICATION = "cross_cohort_replication"
    SUBGROUP_FAIRNESS = "subgroup_fairness"
    TRANSPORTABILITY = "transportability"
    FEDERATED_SUMMARY = "federated_summary"
    COHORT_DISCOVERY = "cohort_discovery"


class CohortArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CASE = "case"
    RESULT = "result"
    CONTROL = "control"
    REPLAY = "replay"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "cohort-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class CohortArchitectureSource:
    source_id: str
    family: CohortArchitectureFamily
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
class CohortArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: CohortArchitectureOperation
    delegate_operation: str
    family: CohortArchitectureFamily
    plane: CohortArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureCase:
    case_id: str
    operation_id: str
    operation: CohortArchitectureOperation
    family: CohortArchitectureFamily
    plane: CohortArchitecturePlane
    scenario: CohortArchitectureScenario
    aggregate_context_key: str
    delegate_context_key: str
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_class: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: CohortArchitectureState
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
class CohortArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    family_contexts: Mapping[str, str]
    sources: tuple[CohortArchitectureSource, ...]
    operations: tuple[CohortArchitectureOperationSpec, ...]
    cases: tuple[CohortArchitectureCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[CohortArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is CohortArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[CohortArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is not CohortArchitectureScenario.POSITIVE
        )

    @property
    def family_set(self) -> tuple[CohortArchitectureFamily, ...]:
        return tuple(CohortArchitectureFamily)

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
    def from_mapping(cls, raw: Mapping[str, Any]) -> CohortArchitectureFixture:
        try:
            sources = tuple(
                CohortArchitectureSource(
                    str(item["source_id"]),
                    CohortArchitectureFamily(item["family"]),
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
                CohortArchitectureOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    CohortArchitectureOperation(item["operation"]),
                    str(item["delegate_operation"]),
                    CohortArchitectureFamily(item["family"]),
                    CohortArchitecturePlane(item["plane"]),
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
                CohortArchitectureCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    CohortArchitectureOperation(item["operation"]),
                    CohortArchitectureFamily(item["family"]),
                    CohortArchitecturePlane(item["plane"]),
                    CohortArchitectureScenario(item["scenario"]),
                    str(item["aggregate_context_key"]),
                    str(item["delegate_context_key"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_class"]),
                    tuple(str(value) for value in item["source_ids"]),
                    dict(item["payload"]),
                    CohortArchitectureState(item["expected_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D12 fixture mapping is invalid: {exc}") from exc
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
    def from_file(cls, path: str | Path) -> CohortArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D12 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class CohortArchitectureCheck:
    check_id: str
    kind: CohortArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureDataAudit:
    fixture_id: str
    checks: tuple[CohortArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class CohortArchitectureExecution:
    case_id: str
    operation: CohortArchitectureOperation
    family: CohortArchitectureFamily
    scenario: CohortArchitectureScenario
    observed_state: CohortArchitectureState
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: CohortArchitectureState
    observed_state: CohortArchitectureState
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
class CohortArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: str
    executions: tuple[CohortArchitectureExecution, ...]
    receipts: tuple[CohortArchitectureCaseReceipt, ...]
    checks: tuple[CohortArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == "accepted" and all(item.passed for item in self.checks)

    def execution_map(self) -> dict[str, CohortArchitectureExecution]:
        return {item.case_id: item for item in self.executions}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class CohortArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: CohortArchitectureFamily
    plane: CohortArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitecturePlan:
    fixture_id: str
    nodes: tuple[CohortArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureReviewItem:
    case_id: str
    operation_id: str
    family: CohortArchitectureFamily
    scenario: CohortArchitectureScenario
    observed_state: CohortArchitectureState
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureReviewQueue:
    fixture_id: str
    items: tuple[CohortArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureArtifact:
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
class CohortArchitectureRelease:
    release_id: str
    fixture_id: str
    state: CohortArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureRuntimeStage:
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
class CohortArchitectureRuntime:
    fixture: CohortArchitectureFixture
    audit: CohortArchitectureDataAudit
    plan: CohortArchitecturePlan
    evaluation: CohortArchitectureEvaluation
    review_queue: CohortArchitectureReviewQueue
    ledger: CohortArchitectureLedger
    artifacts: tuple[CohortArchitectureArtifact, ...]
    release: CohortArchitectureRelease
    depth: CohortArchitectureDepthReport
    quality: CohortArchitectureQualityGate
    stages: tuple[CohortArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortArchitectureDepthReport:
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
class CohortArchitectureQualityGate:
    fixture_id: str
    checks: tuple[CohortArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("CohortArchitecture")
    or name.startswith("COHORT_ARCHITECTURE")
    or name == "addressed"
]

"""Typed D11 contracts for causal evidence research aggregates."""

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

CAUSAL_ARCHITECTURE_VERSION = "2026.08.d11-causal-architecture.v1"
CAUSAL_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
CAUSAL_ARCHITECTURE_CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
CAUSAL_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"
CAUSAL_ARCHITECTURE_SOURCE_COUNT = 20
CAUSAL_ARCHITECTURE_OPERATION_COUNT = 16
CAUSAL_ARCHITECTURE_CASE_COUNT = 64
CAUSAL_ARCHITECTURE_CASES_PER_OPERATION = 4
CAUSAL_ARCHITECTURE_ARTIFACT_COUNT = 6


class CausalArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"


class CausalArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class CausalArchitecturePlane(StrEnum):
    FOUNDATION = "causal_foundation"
    BETA = "causal_mediator"
    ALPHA = "causal_sensitivity"
    FRONTIER = "causal_release"


class CausalArchitectureFamily(StrEnum):
    FOUNDATION = "causal_foundation_frontier"
    BETA = "causal_beta_frontier"
    ALPHA = "causal_alpha_frontier"
    FRONTIER = "causal_frontier"


class CausalArchitectureOperation(StrEnum):
    TYPED_HYPOTHESIS = "typed_hypothesis_object"
    FACTOR_GRAPH = "factor_graph_constructor"
    CONTEXT_PRIOR = "context_conditioned_prior"
    MEASUREMENT_LIKELIHOOD = "measurement_likelihood"
    SEQUENCE_ELEMENT_MEDIATOR = "sequence_to_element"
    ELEMENT_GENE_MEDIATOR = "element_to_gene"
    GENE_STATE_MEDIATOR = "gene_to_state"
    COUNTERFACTUAL_ALLELE = "counterfactual_allele_state"
    MEDIATION_SENSITIVITY = "mediation_sensitivity"
    CONFOUNDING_CHECKLIST = "confounding_checklist"
    DEPENDENCE_CORRECTION = "dependence_correction"
    NEGATIVE_EVIDENCE = "negative_evidence"
    POSTERIOR_DECOMPOSITION = "posterior_decomposition"
    DRIVER_POSTERIOR = "regulatory_driver_posterior"
    SELECTIVE_ABSTENTION = "selective_prediction_abstention"
    CAUSAL_DOSSIER = "causal_dossier_publication"


class CausalArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CASE = "case"
    RESULT = "result"
    CONTROL = "control"
    REPLAY = "replay"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "causal-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class CausalArchitectureSource:
    source_id: str
    family: CausalArchitectureFamily
    source_kind: str
    source_version: str
    uri: str
    context_key: str
    public_aggregate: bool
    delegate_source_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: CausalArchitectureOperation
    family: CausalArchitectureFamily
    plane: CausalArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureCase:
    case_id: str
    operation_id: str
    family: CausalArchitectureFamily
    plane: CausalArchitecturePlane
    scenario: CausalArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_context_key: str
    payload: Mapping[str, Any]
    expected_state: CausalArchitectureState
    expected_result_state: str
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
class CausalArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    sources: tuple[CausalArchitectureSource, ...]
    operations: tuple[CausalArchitectureOperationSpec, ...]
    cases: tuple[CausalArchitectureCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[CausalArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is CausalArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[CausalArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is not CausalArchitectureScenario.POSITIVE
        )

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "boundary": self.boundary,
            "context_key": self.context_key,
            "foreign_context_key": self.foreign_context_key,
            "sources": [item.to_dict() for item in self.sources],
            "operations": [item.to_dict() for item in self.operations],
            "cases": [item.to_dict(include_payload=include_payload) for item in self.cases],
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> CausalArchitectureFixture:
        try:
            sources = tuple(
                CausalArchitectureSource(
                    str(item["source_id"]),
                    CausalArchitectureFamily(item["family"]),
                    str(item["source_kind"]),
                    str(item["source_version"]),
                    str(item["uri"]),
                    str(item["context_key"]),
                    bool(item["public_aggregate"]),
                    str(item["delegate_source_id"]),
                    str(item["content_address"]),
                )
                for item in raw["sources"]
            )
            operations = tuple(
                CausalArchitectureOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    CausalArchitectureOperation(item["operation"]),
                    CausalArchitectureFamily(item["family"]),
                    CausalArchitecturePlane(item["plane"]),
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
                CausalArchitectureCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    CausalArchitectureFamily(item["family"]),
                    CausalArchitecturePlane(item["plane"]),
                    CausalArchitectureScenario(item["scenario"]),
                    str(item["context_key"]),
                    tuple(str(value) for value in item["source_ids"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_context_key"]),
                    dict(item["payload"]),
                    CausalArchitectureState(item["expected_state"]),
                    str(item["expected_result_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D11 fixture mapping is invalid: {exc}") from exc
        return cls(
            str(raw["fixture_id"]),
            str(raw["version"]),
            str(raw["boundary"]),
            str(raw["context_key"]),
            str(raw["foreign_context_key"]),
            sources,
            operations,
            cases,
            str(raw["content_address"]),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> CausalArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D11 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class CausalArchitectureCheck:
    check_id: str
    kind: CausalArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureDataAudit:
    fixture_id: str
    checks: tuple[CausalArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class CausalArchitectureExecution:
    case_id: str
    operation: CausalArchitectureOperation
    family: CausalArchitectureFamily
    scenario: CausalArchitectureScenario
    observed_state: CausalArchitectureState
    observed_result_state: str
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: CausalArchitectureState
    observed_state: CausalArchitectureState
    expected_result_state: str
    observed_result_state: str
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
class CausalArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: CausalArchitectureState
    executions: tuple[CausalArchitectureExecution, ...]
    receipts: tuple[CausalArchitectureCaseReceipt, ...]
    checks: tuple[CausalArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is CausalArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": sum(
                item.expected_state is CausalArchitectureState.ACCEPTED for item in self.receipts
            ),
            "control_count": sum(
                item.expected_state is CausalArchitectureState.REVIEW for item in self.receipts
            ),
        }


@dataclass(frozen=True, slots=True)
class CausalArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: CausalArchitectureFamily
    plane: CausalArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitecturePlan:
    fixture_id: str
    nodes: tuple[CausalArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureReviewItem:
    case_id: str
    operation_id: str
    scenario: CausalArchitectureScenario
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureReviewQueue:
    fixture_id: str
    items: tuple[CausalArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureArtifact:
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
class CausalArchitectureRelease:
    release_id: str
    fixture_id: str
    state: CausalArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureRuntimeStage:
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
class CausalArchitectureRuntime:
    fixture: CausalArchitectureFixture
    audit: CausalArchitectureDataAudit
    plan: CausalArchitecturePlan
    evaluation: CausalArchitectureEvaluation
    review_queue: CausalArchitectureReviewQueue
    ledger: CausalArchitectureLedger
    artifacts: tuple[CausalArchitectureArtifact, ...]
    release: CausalArchitectureRelease
    stages: tuple[CausalArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture.to_dict(include_payload=False),
            "audit": self.audit.to_dict(),
            "plan": self.plan.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "review_queue": self.review_queue.to_dict(),
            "ledger": self.ledger.to_dict(),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "release": self.release.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CausalArchitectureDepthReport:
    fixture_id: str
    source_count: int
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    check_count: int
    addressed_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalArchitectureQualityGate:
    fixture_id: str
    checks: tuple[CausalArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("CausalArchitecture")
    or name.startswith("CAUSAL_ARCHITECTURE")
    or name == "addressed"
]

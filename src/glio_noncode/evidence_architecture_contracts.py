"""Typed D14 contracts for evidence lifecycle and release architecture."""

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

EVIDENCE_ARCHITECTURE_VERSION = "2026.08.d14-evidence-architecture.v1"
EVIDENCE_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
EVIDENCE_ARCHITECTURE_CONTEXT = "multi_context_public_aggregate"
EVIDENCE_ARCHITECTURE_FOREIGN_CONTEXT = "foreign_context_control"
EVIDENCE_ARCHITECTURE_SOURCE_COUNT = 19
EVIDENCE_ARCHITECTURE_OPERATION_COUNT = 16
EVIDENCE_ARCHITECTURE_CASE_COUNT = 64
EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION = 4
EVIDENCE_ARCHITECTURE_ARTIFACT_COUNT = 6


class EvidenceArchitectureState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"
    CLEAR = "clear"
    INCOMPLETE = "incomplete"
    REVIEW_REQUIRED = "review_required"
    ADJUDICATED = "adjudicated"
    SPLIT_DECISION = "split_decision"
    APPROVED = "approved"
    REJECTED = "rejected"
    READY_FOR_REVIEW = "ready_for_review"
    RECLASSIFIED = "reclassified"
    SUPERSEDED = "superseded"
    BUNDLED = "bundled"
    SIGNED = "signed"
    BLOCKED = "blocked"
    REVIEW = "review"
    PUBLISHED = "published"


class EvidenceArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class EvidenceArchitectureFamily(StrEnum):
    LIFECYCLE_FOUNDATION = "evidence_lifecycle_frontier"
    LIFECYCLE_BETA = "lifecycle_beta_frontier"
    EVIDENCE_RELEASE = "evidence_release_frontier"


class EvidenceArchitecturePlane(StrEnum):
    LIFECYCLE_FOUNDATION = "lifecycle_foundation"
    LIFECYCLE_ADJUDICATION = "lifecycle_adjudication"
    EVIDENCE_RELEASE = "evidence_release"


class EvidenceArchitectureOperation(StrEnum):
    CITATION_RESOLUTION = "citation_resolution"
    GRAPH_CONSTRUCTION = "graph_construction"
    EDGE_VALIDATION = "edge_validation"
    DISAGREEMENT_TRACKING = "disagreement_tracking"
    TIER_ADJUDICATION = "tier_adjudication"
    PROVENANCE_LINEAGE = "provenance_lineage"
    UNCERTAINTY_LEDGER = "uncertainty_ledger"
    REVIEW_ROUTING = "review_routing"
    BLINDED_ADJUDICATION = "blinded_adjudication"
    COMMENT_CHANGE_LOG = "comment_change_log"
    RELEASE_DECISION = "release_decision"
    EVIDENCE_DELTA = "evidence_delta"
    RECLASSIFICATION = "reclassification"
    SUPERSESSION = "supersession"
    REPRODUCIBILITY_BUNDLE = "reproducibility_bundle"
    SIGNED_DOSSIER = "signed_dossier"


class EvidenceArchitectureCheckKind(StrEnum):
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


def addressed(value: Any, prefix: str = "evidence-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureSource:
    source_id: str
    family: EvidenceArchitectureFamily
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
class EvidenceArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: EvidenceArchitectureOperation
    delegate_operation: str
    family: EvidenceArchitectureFamily
    plane: EvidenceArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureCase:
    case_id: str
    operation_id: str
    operation: EvidenceArchitectureOperation
    family: EvidenceArchitectureFamily
    plane: EvidenceArchitecturePlane
    scenario: EvidenceArchitectureScenario
    aggregate_context_key: str
    delegate_context_key: str
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_class: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: EvidenceArchitectureState
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
class EvidenceArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    family_contexts: Mapping[str, str]
    sources: tuple[EvidenceArchitectureSource, ...]
    operations: tuple[EvidenceArchitectureOperationSpec, ...]
    cases: tuple[EvidenceArchitectureCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[EvidenceArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is EvidenceArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[EvidenceArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not EvidenceArchitectureScenario.POSITIVE
        )

    @property
    def family_set(self) -> tuple[EvidenceArchitectureFamily, ...]:
        return tuple(EvidenceArchitectureFamily)

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
    def from_mapping(cls, raw: Mapping[str, Any]) -> EvidenceArchitectureFixture:
        try:
            sources = tuple(
                EvidenceArchitectureSource(
                    str(item["source_id"]),
                    EvidenceArchitectureFamily(item["family"]),
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
                EvidenceArchitectureOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    EvidenceArchitectureOperation(item["operation"]),
                    str(item["delegate_operation"]),
                    EvidenceArchitectureFamily(item["family"]),
                    EvidenceArchitecturePlane(item["plane"]),
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
                EvidenceArchitectureCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    EvidenceArchitectureOperation(item["operation"]),
                    EvidenceArchitectureFamily(item["family"]),
                    EvidenceArchitecturePlane(item["plane"]),
                    EvidenceArchitectureScenario(item["scenario"]),
                    str(item["aggregate_context_key"]),
                    str(item["delegate_context_key"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_class"]),
                    tuple(str(value) for value in item["source_ids"]),
                    dict(item["payload"]),
                    EvidenceArchitectureState(item["expected_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D14 fixture mapping is invalid: {exc}") from exc
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
    def from_file(cls, path: str | Path) -> EvidenceArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D14 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureCheck:
    check_id: str
    kind: EvidenceArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureDataAudit:
    fixture_id: str
    checks: tuple[EvidenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureExecution:
    case_id: str
    operation: EvidenceArchitectureOperation
    family: EvidenceArchitectureFamily
    scenario: EvidenceArchitectureScenario
    observed_state: EvidenceArchitectureState
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: EvidenceArchitectureState
    observed_state: EvidenceArchitectureState
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
class EvidenceArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: str
    executions: tuple[EvidenceArchitectureExecution, ...]
    receipts: tuple[EvidenceArchitectureCaseReceipt, ...]
    checks: tuple[EvidenceArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == "accepted" and all(item.passed for item in self.checks)

    def execution_map(self) -> dict[str, EvidenceArchitectureExecution]:
        return {item.case_id: item for item in self.executions}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class EvidenceArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: EvidenceArchitectureFamily
    plane: EvidenceArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitecturePlan:
    fixture_id: str
    nodes: tuple[EvidenceArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureReviewItem:
    case_id: str
    operation_id: str
    family: EvidenceArchitectureFamily
    scenario: EvidenceArchitectureScenario
    observed_state: EvidenceArchitectureState
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureReviewQueue:
    fixture_id: str
    items: tuple[EvidenceArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureArtifact:
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
class EvidenceArchitectureRelease:
    release_id: str
    fixture_id: str
    state: EvidenceArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureRuntimeStage:
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
class EvidenceArchitectureRuntime:
    fixture: EvidenceArchitectureFixture
    audit: EvidenceArchitectureDataAudit
    plan: EvidenceArchitecturePlan
    evaluation: EvidenceArchitectureEvaluation
    review_queue: EvidenceArchitectureReviewQueue
    ledger: EvidenceArchitectureLedger
    artifacts: tuple[EvidenceArchitectureArtifact, ...]
    release: EvidenceArchitectureRelease
    depth: EvidenceArchitectureDepthReport
    quality: EvidenceArchitectureQualityGate
    stages: tuple[EvidenceArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureDepthReport:
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
class EvidenceArchitectureQualityGate:
    fixture_id: str
    checks: tuple[EvidenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("EvidenceArchitecture")
    or name.startswith("EVIDENCE_ARCHITECTURE")
    or name == "addressed"
]

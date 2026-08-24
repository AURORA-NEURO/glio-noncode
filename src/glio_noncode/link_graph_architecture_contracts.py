"""Typed D10 contracts for a public regulatory link-graph aggregate."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import jsonable

LINK_GRAPH_ARCHITECTURE_VERSION = "2026.08.d10-link-graph-architecture.v1"
LINK_GRAPH_ARCHITECTURE_BOUNDARY = "public_aggregate_non_patient"
LINK_GRAPH_ARCHITECTURE_CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
LINK_GRAPH_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"
LINK_GRAPH_ARCHITECTURE_SOURCE_COUNT = 19
LINK_GRAPH_ARCHITECTURE_OPERATION_COUNT = 16
LINK_GRAPH_ARCHITECTURE_CASE_COUNT = 64
LINK_GRAPH_ARCHITECTURE_CASES_PER_OPERATION = 4
LINK_GRAPH_ARCHITECTURE_ARTIFACT_COUNT = 6


class LinkGraphArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"


class LinkGraphArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    CONTROL_A = "control_a"
    CONTROL_B = "control_b"
    CONTROL_C = "control_c"


class LinkGraphArchitecturePlane(StrEnum):
    FOUNDATION = "foundation_baseline"
    BETA = "beta_regulatory_evidence"
    ALPHA = "alpha_link_inference"
    FRONTIER = "frontier_release"


class LinkGraphArchitectureFamily(StrEnum):
    FOUNDATION = "link_graph_foundation_frontier"
    BETA = "link_graph_beta_frontier"
    ALPHA = "link_graph_alpha_frontier"
    FRONTIER = "link_frontier"


class LinkGraphArchitectureOperation(StrEnum):
    COORDINATE_OVERLAP = "coordinate_overlap"
    NEAREST_GENE = "nearest_gene"
    CCRE_ASSIGNMENT = "ccre_assignment"
    ENHANCER_GENE_CONSENSUS = "enhancer_gene_consensus"
    ACTIVITY_BY_CONTACT = "activity_by_contact"
    COACCESSIBILITY = "coaccessibility"
    MOLECULAR_QTL = "molecular_qtl"
    ALLELE_SPECIFIC = "allele_specific"
    CRISPR_PERTURBATION = "crispr_perturbation"
    CONTACT_3D = "contact_3d"
    PROMOTER_TETHERING = "promoter_tethering"
    MULTI_GENE_GRAPH = "multi_gene_graph"
    DEPENDENCE_CORRECTION = "link_dependence_correction"
    TARGET_GENE_RANKING = "target_gene_ranking"
    CALIBRATION_ABSTENTION = "link_calibration_abstention"
    EVIDENCE_PUBLICATION = "link_evidence_publication"


class LinkGraphArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CASE = "case"
    RESULT = "result"
    CONTROL = "control"
    REPLAY = "replay"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "link-graph-architecture") -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    import hashlib

    return f"sha256:{hashlib.sha256(f'{prefix}|{payload}'.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureSource:
    source_id: str
    family: LinkGraphArchitectureFamily
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
class LinkGraphArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: LinkGraphArchitectureOperation
    family: LinkGraphArchitectureFamily
    plane: LinkGraphArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureCase:
    case_id: str
    operation_id: str
    family: LinkGraphArchitectureFamily
    plane: LinkGraphArchitecturePlane
    scenario: LinkGraphArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    delegate_fixture_id: str
    delegate_record_id: str
    delegate_context_key: str
    payload: Mapping[str, Any]
    expected_state: LinkGraphArchitectureState
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
class LinkGraphArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    sources: tuple[LinkGraphArchitectureSource, ...]
    operations: tuple[LinkGraphArchitectureOperationSpec, ...]
    cases: tuple[LinkGraphArchitectureCase, ...]
    content_address: str

    @property
    def positive_cases(self) -> tuple[LinkGraphArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is LinkGraphArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[LinkGraphArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not LinkGraphArchitectureScenario.POSITIVE
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
    def from_mapping(cls, raw: Mapping[str, Any]) -> LinkGraphArchitectureFixture:
        try:
            sources = tuple(
                LinkGraphArchitectureSource(
                    str(item["source_id"]),
                    LinkGraphArchitectureFamily(item["family"]),
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
                LinkGraphArchitectureOperationSpec(
                    str(item["operation_id"]),
                    str(item["capability_id"]),
                    int(item["ordinal"]),
                    LinkGraphArchitectureOperation(item["operation"]),
                    LinkGraphArchitectureFamily(item["family"]),
                    LinkGraphArchitecturePlane(item["plane"]),
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
                LinkGraphArchitectureCase(
                    str(item["case_id"]),
                    str(item["operation_id"]),
                    LinkGraphArchitectureFamily(item["family"]),
                    LinkGraphArchitecturePlane(item["plane"]),
                    LinkGraphArchitectureScenario(item["scenario"]),
                    str(item["context_key"]),
                    tuple(str(value) for value in item["source_ids"]),
                    str(item["delegate_fixture_id"]),
                    str(item["delegate_record_id"]),
                    str(item["delegate_context_key"]),
                    dict(item["payload"]),
                    LinkGraphArchitectureState(item["expected_state"]),
                    str(item["expected_result_state"]),
                    tuple(str(value) for value in item["expected_issue_codes"]),
                    {str(key): int(value) for key, value in item["expected_counts"].items()},
                    str(item["description"]),
                    str(item["content_address"]),
                )
                for item in raw["cases"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"D10 fixture mapping is invalid: {exc}") from exc
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
    def from_file(cls, path: str | Path) -> LinkGraphArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D10 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureCheck:
    check_id: str
    kind: LinkGraphArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureDataAudit:
    fixture_id: str
    checks: tuple[LinkGraphArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureExecution:
    case_id: str
    operation: LinkGraphArchitectureOperation
    family: LinkGraphArchitectureFamily
    scenario: LinkGraphArchitectureScenario
    observed_state: LinkGraphArchitectureState
    observed_result_state: str
    observed_issue_codes: tuple[str, ...]
    observed_counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: LinkGraphArchitectureState
    observed_state: LinkGraphArchitectureState
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
class LinkGraphArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: LinkGraphArchitectureState
    executions: tuple[LinkGraphArchitectureExecution, ...]
    receipts: tuple[LinkGraphArchitectureCaseReceipt, ...]
    checks: tuple[LinkGraphArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is LinkGraphArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": sum(
                item.expected_state is LinkGraphArchitectureState.ACCEPTED for item in self.receipts
            ),
            "control_count": sum(
                item.expected_state is LinkGraphArchitectureState.REVIEW for item in self.receipts
            ),
        }


@dataclass(frozen=True, slots=True)
class LinkGraphArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: LinkGraphArchitectureFamily
    plane: LinkGraphArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitecturePlan:
    fixture_id: str
    nodes: tuple[LinkGraphArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureReviewItem:
    case_id: str
    operation_id: str
    scenario: LinkGraphArchitectureScenario
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureReviewQueue:
    fixture_id: str
    items: tuple[LinkGraphArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureLedger:
    fixture_id: str
    events: tuple[dict[str, Any], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureArtifact:
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
class LinkGraphArchitectureRelease:
    release_id: str
    fixture_id: str
    state: LinkGraphArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureRuntimeStage:
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
class LinkGraphArchitectureRuntime:
    fixture: LinkGraphArchitectureFixture
    audit: LinkGraphArchitectureDataAudit
    plan: LinkGraphArchitecturePlan
    evaluation: LinkGraphArchitectureEvaluation
    review_queue: LinkGraphArchitectureReviewQueue
    ledger: LinkGraphArchitectureLedger
    artifacts: tuple[LinkGraphArchitectureArtifact, ...]
    release: LinkGraphArchitectureRelease
    depth: LinkGraphArchitectureDepthReport
    quality: LinkGraphArchitectureQualityGate
    stages: tuple[LinkGraphArchitectureRuntimeStage, ...]
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
            "depth": self.depth.to_dict(),
            "quality": self.quality.to_dict(),
            "stages": [item.to_dict() for item in self.stages],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class LinkGraphArchitectureDepthReport:
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
class LinkGraphArchitectureQualityGate:
    fixture_id: str
    checks: tuple[LinkGraphArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("LinkGraphArchitecture")
    or name.startswith("LINK_GRAPH_ARCHITECTURE")
    or name == "addressed"
]

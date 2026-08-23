"""Typed D08 aggregate contracts for cell-state and disease context evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CELL_STATE_ARCHITECTURE_VERSION = "2026.08.d08-cell-state-architecture.v1"
CELL_STATE_ARCHITECTURE_BOUNDARY = "public_aggregate_cell_state_disease_territory"
CELL_STATE_ARCHITECTURE_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CELL_STATE_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|glioma|pediatric|stem_like|tumor|unknown"
CELL_STATE_ARCHITECTURE_OPERATION_COUNT = 16
CELL_STATE_ARCHITECTURE_CASES_PER_OPERATION = 4
CELL_STATE_ARCHITECTURE_CASE_COUNT = 64
CELL_STATE_ARCHITECTURE_SOURCE_COUNT = 18
CELL_STATE_ARCHITECTURE_ARTIFACT_COUNT = 6


class CellStateArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class CellStateArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class CellStateArchitecturePlane(StrEnum):
    TAXONOMY = "taxonomy"
    PRIOR = "prior"
    TERRITORY = "territory"
    CELL_STATE = "cell_state"
    RELEASE = "release"


class CellStateArchitectureFamily(StrEnum):
    CONTEXT = "cell_context_frontier"
    BETA = "cell_context_beta_frontier"
    ALPHA = "cell_context_alpha_frontier"
    STATE = "cell_state_frontier"


class CellStateArchitectureOperation(StrEnum):
    DISEASE_ONTOLOGY = "disease_ontology_context"
    AGE_ROUTE = "adult_pediatric_route"
    MOLECULAR_STATE = "molecular_class_state"
    TERRITORY_ASSEMBLY = "territory_context_assembly"
    DEVELOPMENTAL_LINEAGE = "developmental_lineage_prior"
    GBM_MALIGNANT_STATE = "glioblastoma_malignant_state_prior"
    IDH_MUTANT_LINEAGE = "idh_mutant_lineage_state_prior"
    H3K27_DEVELOPMENTAL_STATE = "h3k27_altered_developmental_state_prior"
    SPATIAL_NICHE = "spatial_niche_prior"
    CORE_MARGIN = "core_margin_territory_prior"
    RECURRENCE_STATE = "recurrence_state_prior"
    TREATMENT_INDUCED = "treatment_induced_state_prior"
    ABUNDANCE_INTERVAL = "cell_state_abundance_interval"
    REFERENCE_MAPPING = "single_cell_reference_mapping"
    OOD_DETECTION = "cell_state_ood_detection"
    CONTEXT_PUBLICATION = "cell_state_context_publication"


class CellStateArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    LINEAGE = "lineage"
    REVIEW = "review"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "cell-state-architecture") -> str:
    return content_hash({"prefix": prefix, "value": value})


def _text_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{name} must be a sequence")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{name} cannot contain blank values")
    return result


@dataclass(frozen=True, slots=True)
class CellStateArchitectureSource:
    source_id: str
    family: CellStateArchitectureFamily
    title: str
    uri: str
    version: str
    scope: str
    license: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "version", "scope", "license", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith(("https://", "http://")):
            raise ValidationError("D08 source URI must be HTTP(S)")
        if self.scope != "public_aggregate":
            raise ValidationError("D08 sources must be public aggregate receipts")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D08 source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: CellStateArchitectureOperation
    family: CellStateArchitectureFamily
    plane: CellStateArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "operation_id",
            "capability_id",
            "input_contract",
            "output_contract",
            "control_policy",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.ordinal < 1 or not self.source_ids:
            raise ValidationError("D08 operations require order and source joins")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: CellStateArchitectureOperation
    family: CellStateArchitectureFamily
    plane: CellStateArchitecturePlane
    scenario: CellStateArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: CellStateArchitectureState
    expected_result_state: str
    expected_issue_codes: tuple[str, ...]
    expected_counts: dict[str, int]
    description: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "case_id",
            "operation_id",
            "capability_id",
            "context_key",
            "expected_result_state",
            "description",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not isinstance(self.payload, dict):
            raise ValidationError("D08 cases require source joins and object payloads")
        if any(int(value) < 0 for value in self.expected_counts.values()):
            raise ValidationError("D08 expected counts cannot be negative")
        if (
            self.scenario is CellStateArchitectureScenario.POSITIVE
            and self.expected_state is not CellStateArchitectureState.ACCEPTED
        ):
            raise ValidationError("D08 positive cases must be accepted")
        if (
            self.scenario is not CellStateArchitectureScenario.POSITIVE
            and self.expected_state is not CellStateArchitectureState.REVIEW
        ):
            raise ValidationError("D08 controls must remain review-held")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[CellStateArchitectureSource, ...]
    operations: tuple[CellStateArchitectureOperationSpec, ...]
    cases: tuple[CellStateArchitectureCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.version != CELL_STATE_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported D08 cell-state architecture version")
        if self.boundary != CELL_STATE_ARCHITECTURE_BOUNDARY:
            raise ValidationError("D08 boundary does not match the public aggregate contract")
        if self.context_key != CELL_STATE_ARCHITECTURE_CONTEXT:
            raise ValidationError("D08 context does not match the aggregate contract")
        if len(self.sources) != CELL_STATE_ARCHITECTURE_SOURCE_COUNT:
            raise ValidationError("D08 fixture requires eighteen source receipts")
        if len(self.operations) != CELL_STATE_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("D08 fixture requires sixteen operation specifications")
        if len(self.cases) != CELL_STATE_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("D08 fixture requires sixty-four cases")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValidationError("D08 source identifiers must be unique")
        if len({item.operation_id for item in self.operations}) != len(self.operations):
            raise ValidationError("D08 operation identifiers must be unique")
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValidationError("D08 case identifiers must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D08 fixture requires a content address")

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(item.operation_id for item in self.operations)

    @property
    def positive_cases(self) -> tuple[CellStateArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is CellStateArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[CellStateArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not CellStateArchitectureScenario.POSITIVE
        )

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "version": self.version,
            "boundary": self.boundary,
            "context_key": self.context_key,
            "sources": [item.to_dict() for item in self.sources],
            "operations": [item.to_dict() for item in self.operations],
            "cases": [
                item.to_dict() if include_payload else {**item.to_dict(), "payload": {}}
                for item in self.cases
            ],
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> CellStateArchitectureFixture:
        sources = tuple(_source(item) for item in raw.get("sources", ()))
        operations = tuple(_operation(item) for item in raw.get("operations", ()))
        cases = tuple(_case(item) for item in raw.get("cases", ()))
        body = {
            "fixture_id": str(raw.get("fixture_id", "")),
            "version": str(raw.get("version", "")),
            "boundary": str(raw.get("boundary", "")),
            "context_key": str(raw.get("context_key", "")),
            "sources": sources,
            "operations": operations,
            "cases": cases,
        }
        expected = addressed(body, "cell-state-fixture")
        supplied = str(raw.get("content_address", expected))
        if supplied != expected:
            raise ValidationError("D08 fixture content address does not match mapping")
        return cls(**body, content_address=supplied)

    @classmethod
    def from_file(cls, path: str | Path) -> CellStateArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D08 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureCheck:
    check_id: str
    kind: CellStateArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureDataAudit:
    fixture_id: str
    checks: tuple[CellStateArchitectureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class CellStateArchitectureExecution:
    case_id: str
    operation: CellStateArchitectureOperation
    family: CellStateArchitectureFamily
    scenario: CellStateArchitectureScenario
    observed_state: CellStateArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: dict[str, int]
    output_address: str
    summary: dict[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    family: CellStateArchitectureFamily
    expected_state: CellStateArchitectureState
    observed_state: CellStateArchitectureState
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    expected_counts: dict[str, int]
    observed_counts: dict[str, int]
    passed: bool
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: CellStateArchitectureState
    executions: tuple[CellStateArchitectureExecution, ...]
    receipts: tuple[CellStateArchitectureCaseReceipt, ...]
    checks: tuple[CellStateArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is CellStateArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    @property
    def positive_count(self) -> int:
        return sum(
            item.expected_state is CellStateArchitectureState.ACCEPTED for item in self.receipts
        )

    @property
    def control_count(self) -> int:
        return sum(
            item.expected_state is CellStateArchitectureState.REVIEW for item in self.receipts
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


@dataclass(frozen=True, slots=True)
class CellStateArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: CellStateArchitectureFamily
    plane: CellStateArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitecturePlan:
    fixture_id: str
    nodes: tuple[CellStateArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureReviewItem:
    case_id: str
    operation_id: str
    scenario: CellStateArchitectureScenario
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureReviewQueue:
    fixture_id: str
    items: tuple[CellStateArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureLedgerEvent:
    event_id: str
    case_id: str
    operation_id: str
    state: str
    disposition: str
    reason_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    output_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureLedger:
    fixture_id: str
    events: tuple[CellStateArchitectureLedgerEvent, ...]
    state_counts: Mapping[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureArtifact:
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
class CellStateArchitectureRelease:
    release_id: str
    fixture_id: str
    state: CellStateArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureRuntimeStage:
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
class CellStateArchitectureRuntime:
    fixture: CellStateArchitectureFixture
    audit: CellStateArchitectureDataAudit
    plan: CellStateArchitecturePlan
    evaluation: CellStateArchitectureEvaluation
    review_queue: CellStateArchitectureReviewQueue
    ledger: CellStateArchitectureLedger
    artifacts: tuple[CellStateArchitectureArtifact, ...]
    release: CellStateArchitectureRelease
    stages: tuple[CellStateArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class CellStateArchitectureDepthReport:
    fixture_id: str
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    source_count: int
    addressed_count: int
    family_counts: Mapping[str, int]
    plane_counts: Mapping[str, int]
    check_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateArchitectureQualityGate:
    fixture_id: str
    checks: tuple[CellStateArchitectureCheck, ...]
    release: CellStateArchitectureRelease
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


def _source(raw: Mapping[str, Any]) -> CellStateArchitectureSource:
    body = {
        "source_id": str(raw.get("source_id", "")),
        "family": CellStateArchitectureFamily(str(raw.get("family", ""))),
        "title": str(raw.get("title", raw.get("source_id", ""))),
        "uri": str(raw.get("uri", "")),
        "version": str(raw.get("version", "public")),
        "scope": str(raw.get("scope", "")),
        "license": str(raw.get("license", "public source receipt")),
    }
    return CellStateArchitectureSource(**body, content_address=addressed(body, "cell-state-source"))


def _operation(raw: Mapping[str, Any]) -> CellStateArchitectureOperationSpec:
    body = {
        "operation_id": str(raw.get("operation_id", "")),
        "capability_id": str(raw.get("capability_id", "")),
        "ordinal": int(raw.get("ordinal", 0)),
        "operation": CellStateArchitectureOperation(str(raw.get("operation", ""))),
        "family": CellStateArchitectureFamily(str(raw.get("family", ""))),
        "plane": CellStateArchitecturePlane(str(raw.get("plane", ""))),
        "input_contract": str(raw.get("input_contract", "")),
        "output_contract": str(raw.get("output_contract", "")),
        "dependencies": _text_tuple(raw.get("dependencies", ()), "dependencies")
        if raw.get("dependencies", ())
        else (),
        "source_ids": _text_tuple(raw.get("source_ids", ()), "source_ids"),
        "control_policy": str(raw.get("control_policy", "")),
    }
    return CellStateArchitectureOperationSpec(
        **body, content_address=addressed(body, "cell-state-operation")
    )


def _case(raw: Mapping[str, Any]) -> CellStateArchitectureCase:
    body = {
        "case_id": str(raw.get("case_id", "")),
        "operation_id": str(raw.get("operation_id", "")),
        "capability_id": str(raw.get("capability_id", "")),
        "operation": CellStateArchitectureOperation(str(raw.get("operation", ""))),
        "family": CellStateArchitectureFamily(str(raw.get("family", ""))),
        "plane": CellStateArchitecturePlane(str(raw.get("plane", ""))),
        "scenario": CellStateArchitectureScenario(str(raw.get("scenario", ""))),
        "context_key": str(raw.get("context_key", "")),
        "source_ids": _text_tuple(raw.get("source_ids", ()), "source_ids"),
        "payload": dict(raw.get("payload", {})),
        "expected_state": CellStateArchitectureState(str(raw.get("expected_state", ""))),
        "expected_result_state": str(raw.get("expected_result_state", "")),
        "expected_issue_codes": _text_tuple(
            raw.get("expected_issue_codes", ()), "expected_issue_codes"
        )
        if raw.get("expected_issue_codes", ())
        else (),
        "expected_counts": {
            str(key): int(value) for key, value in dict(raw.get("expected_counts", {})).items()
        },
        "description": str(raw.get("description", "")),
    }
    return CellStateArchitectureCase(**body, content_address=addressed(body, "cell-state-case"))


__all__ = [
    "CELL_STATE_ARCHITECTURE_ARTIFACT_COUNT",
    "CELL_STATE_ARCHITECTURE_BOUNDARY",
    "CELL_STATE_ARCHITECTURE_CASE_COUNT",
    "CELL_STATE_ARCHITECTURE_CASES_PER_OPERATION",
    "CELL_STATE_ARCHITECTURE_CONTEXT",
    "CELL_STATE_ARCHITECTURE_FOREIGN_CONTEXT",
    "CELL_STATE_ARCHITECTURE_OPERATION_COUNT",
    "CELL_STATE_ARCHITECTURE_SOURCE_COUNT",
    "CELL_STATE_ARCHITECTURE_VERSION",
    "CellStateArchitectureArtifact",
    "CellStateArchitectureCase",
    "CellStateArchitectureCaseReceipt",
    "CellStateArchitectureCheck",
    "CellStateArchitectureCheckKind",
    "CellStateArchitectureDataAudit",
    "CellStateArchitectureDepthReport",
    "CellStateArchitectureEvaluation",
    "CellStateArchitectureExecution",
    "CellStateArchitectureFamily",
    "CellStateArchitectureFixture",
    "CellStateArchitectureLedger",
    "CellStateArchitectureLedgerEvent",
    "CellStateArchitectureOperation",
    "CellStateArchitectureOperationSpec",
    "CellStateArchitecturePlane",
    "CellStateArchitecturePlan",
    "CellStateArchitecturePlanNode",
    "CellStateArchitectureQualityGate",
    "CellStateArchitectureRelease",
    "CellStateArchitectureReviewItem",
    "CellStateArchitectureReviewQueue",
    "CellStateArchitectureRuntime",
    "CellStateArchitectureRuntimeStage",
    "CellStateArchitectureScenario",
    "CellStateArchitectureSource",
    "CellStateArchitectureState",
    "addressed",
]

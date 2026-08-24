"""Typed D06 aggregate contracts for sequence grammar and variant effect."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

SEQUENCE_ARCHITECTURE_VERSION = "2026.08.d06-sequence-architecture.v1"
SEQUENCE_ARCHITECTURE_BOUNDARY = "public_aggregate_sequence_grammar_variant_effect"
SEQUENCE_ARCHITECTURE_CONTEXT = "GRCh38|diffuse_glioma|adult|bulk_tumor|sequence|baseline"
SEQUENCE_ARCHITECTURE_FOREIGN_CONTEXT = (
    "GRCh38|diffuse_glioma|pediatric|bulk_tumor|sequence|baseline"
)
SEQUENCE_ARCHITECTURE_OPERATION_COUNT = 16
SEQUENCE_ARCHITECTURE_CASES_PER_OPERATION = 4
SEQUENCE_ARCHITECTURE_CASE_COUNT = 64
SEQUENCE_ARCHITECTURE_SOURCE_COUNT = 17
SEQUENCE_ARCHITECTURE_FAMILY_COUNT = 4
SEQUENCE_ARCHITECTURE_ARTIFACT_COUNT = 6


class SequenceArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class SequenceArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class SequenceArchitecturePlane(StrEnum):
    INGESTION = "ingestion"
    EFFECT = "effect"
    GRAMMAR = "grammar"
    REGULATION = "regulation"
    FRONTIER = "frontier"


class SequenceArchitectureFamily(StrEnum):
    EFFECT = "sequence_effect_frontier"
    GRAMMAR = "sequence_grammar_frontier"
    REGULATION = "sequence_regulation_frontier"
    FRONTIER = "sequence_frontier"


class SequenceArchitectureOperation(StrEnum):
    CONTEXT_ENCODING = "context_encoding"
    FOUNDATION_MODEL = "foundation_model_adapter"
    LONG_CONTEXT = "long_context_variant_effect"
    REGULATORY_ENSEMBLE = "regulatory_track_delta_ensemble"
    MOTIF_DISRUPTION = "motif_disruption"
    MOTIF_CREATION = "motif_creation"
    MOTIF_SPACING = "motif_spacing_grammar"
    COOPERATIVE_GRAMMAR = "cooperative_tf_grammar"
    NUCLEOSOME_PROPENSITY = "nucleosome_propensity"
    SPLICE_REGULATION = "splice_regulation"
    UTR_REGULATION = "utr_regulation"
    PROMOTER_GRAMMAR = "promoter_grammar"
    ENHANCER_GRAMMAR = "enhancer_grammar"
    ALLELE_SATURATION = "allele_saturation"
    ENSEMBLE_DISAGREEMENT = "ensemble_disagreement"
    SEQUENCE_PUBLISH = "sequence_evidence_publish"


class SequenceArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    LINEAGE = "lineage"
    REVIEW = "review"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "sequence-architecture") -> str:
    return content_hash({"prefix": prefix, "value": value})


def _text_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{name} must be a sequence")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{name} cannot contain blank values")
    return result


@dataclass(frozen=True, slots=True)
class SequenceArchitectureSource:
    source_id: str
    family: SequenceArchitectureFamily
    title: str
    uri: str
    version: str
    scope: str
    license: str
    public_aggregate: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "version", "scope", "license", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith(("https://", "http://")):
            raise ValidationError("sequence source URI must be HTTP(S)")
        if self.scope != "public_aggregate":
            raise ValidationError("D06 sources must be public aggregate receipts")
        if not self.public_aggregate:
            raise ValidationError("D06 sources must be marked public aggregate")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("sequence source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: SequenceArchitectureOperation
    family: SequenceArchitectureFamily
    plane: SequenceArchitecturePlane
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
            raise ValidationError("D06 operations require positive order and source joins")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: SequenceArchitectureOperation
    family: SequenceArchitectureFamily
    plane: SequenceArchitecturePlane
    scenario: SequenceArchitectureScenario
    context_key: str
    delegate_context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: SequenceArchitectureState
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
            "delegate_context_key",
            "expected_result_state",
            "description",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not isinstance(self.payload, dict):
            raise ValidationError("D06 cases require source joins and object payloads")
        if any(int(value) < 0 for value in self.expected_counts.values()):
            raise ValidationError("D06 expected counts cannot be negative")
        if self.scenario is SequenceArchitectureScenario.POSITIVE:
            if self.expected_state is not SequenceArchitectureState.ACCEPTED:
                raise ValidationError("D06 positive cases must be accepted")
        elif self.expected_state is not SequenceArchitectureState.REVIEW:
            raise ValidationError("D06 controls must remain in review")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[SequenceArchitectureSource, ...]
    operations: tuple[SequenceArchitectureOperationSpec, ...]
    cases: tuple[SequenceArchitectureCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.version != SEQUENCE_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported D06 sequence architecture version")
        if self.boundary != SEQUENCE_ARCHITECTURE_BOUNDARY:
            raise ValidationError("D06 boundary does not match the public aggregate contract")
        if self.context_key != SEQUENCE_ARCHITECTURE_CONTEXT:
            raise ValidationError("D06 context does not match the aggregate contract")
        if len(self.sources) != SEQUENCE_ARCHITECTURE_SOURCE_COUNT:
            raise ValidationError("D06 fixture requires seventeen source receipts")
        if len(self.operations) != SEQUENCE_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("D06 fixture requires sixteen operation specifications")
        if len(self.cases) != SEQUENCE_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("D06 fixture requires sixty-four cases")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValidationError("D06 source identifiers must be unique")
        if len({item.operation_id for item in self.operations}) != len(self.operations):
            raise ValidationError("D06 operation identifiers must be unique")
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValidationError("D06 case identifiers must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D06 fixture requires a content address")

    @property
    def fixture_id_key(self) -> str:
        return self.fixture_id

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(item.operation_id for item in self.operations)

    @property
    def positive_cases(self) -> tuple[SequenceArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is SequenceArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[SequenceArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not SequenceArchitectureScenario.POSITIVE
        )

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        body = {
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
        return body

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SequenceArchitectureFixture:
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
        expected = addressed(body, "sequence-fixture")
        supplied = str(raw.get("content_address", expected))
        if supplied != expected:
            raise ValidationError("D06 fixture content address does not match its mapping")
        return cls(**body, content_address=supplied)

    @classmethod
    def from_file(cls, path: str | Path) -> SequenceArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D06 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureCheck:
    check_id: str
    kind: SequenceArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureDataAudit:
    fixture_id: str
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureExecution:
    case_id: str
    operation: SequenceArchitectureOperation
    family: SequenceArchitectureFamily
    scenario: SequenceArchitectureScenario
    observed_state: SequenceArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: dict[str, int]
    output_address: str
    summary: dict[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    family: SequenceArchitectureFamily
    expected_state: SequenceArchitectureState
    observed_state: SequenceArchitectureState
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
class SequenceArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: SequenceArchitectureState
    receipts: tuple[SequenceArchitectureCaseReceipt, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is SequenceArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    @property
    def positive_count(self) -> int:
        return sum(
            item.expected_state is SequenceArchitectureState.ACCEPTED for item in self.receipts
        )

    @property
    def control_count(self) -> int:
        return len(self.receipts) - self.positive_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


@dataclass(frozen=True, slots=True)
class SequenceArchitecturePlanNode:
    operation_id: str
    capability_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    ready: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitecturePlan:
    fixture_id: str
    nodes: tuple[SequenceArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureReviewItem:
    review_id: str
    case_id: str
    operation_id: str
    scenario: SequenceArchitectureScenario
    reason_codes: tuple[str, ...]
    priority: int
    disposition: str
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureReviewQueue:
    fixture_id: str
    items: tuple[SequenceArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureLedgerEvent:
    sequence: int
    case_id: str
    operation_id: str
    input_address: str
    output_address: str
    previous_address: str
    state: SequenceArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureLedger:
    fixture_id: str
    events: tuple[SequenceArchitectureLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureArtifact:
    artifact_id: str
    artifact_type: str
    media_type: str
    row_count: int
    source_addresses: tuple[str, ...]
    content_address: str
    retention: str

    def __post_init__(self) -> None:
        if self.row_count < 0 or not self.content_address.startswith("sha256:"):
            raise ValidationError("D06 artifacts require non-negative rows and addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureRelease:
    fixture_id: str
    state: SequenceArchitectureState
    artifact_ids: tuple[str, ...]
    artifact_addresses: tuple[str, ...]
    review_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureRuntimeStage:
    ordinal: int
    stage_id: str
    state: SequenceArchitectureState
    input_addresses: tuple[str, ...]
    output_addresses: tuple[str, ...]
    check_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureRuntime:
    fixture_id: str
    run_id: str
    state: SequenceArchitectureState
    stages: tuple[SequenceArchitectureRuntimeStage, ...]
    audit: SequenceArchitectureDataAudit
    plan: SequenceArchitecturePlan
    evaluation: SequenceArchitectureEvaluation
    review_queue: SequenceArchitectureReviewQueue
    ledger: SequenceArchitectureLedger
    metrics: Any
    validation: tuple[SequenceArchitectureCheck, ...]
    artifacts: tuple[SequenceArchitectureArtifact, ...]
    release: SequenceArchitectureRelease
    depth: SequenceArchitectureDepthReport
    quality: SequenceArchitectureQualityGate
    compliance: Any
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is SequenceArchitectureState.PUBLISHED and all(
            item.state is not SequenceArchitectureState.BLOCKED for item in self.stages
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "stage_count": len(self.stages)}


@dataclass(frozen=True, slots=True)
class SequenceArchitectureDepthReport:
    fixture_id: str
    source_count: int
    operation_count: int
    case_count: int
    receipt_count: int
    ledger_count: int
    stage_count: int
    artifact_count: int
    family_count: int
    check_count: int
    state_count: int
    issue_code_count: int
    addressed_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureQualityGate:
    fixture_id: str
    checks: tuple[SequenceArchitectureCheck, ...]
    passed: bool
    release_state: SequenceArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source(raw: Any) -> SequenceArchitectureSource:
    data = dict(raw)
    data["family"] = SequenceArchitectureFamily(str(data["family"]))
    data["public_aggregate"] = bool(data.get("public_aggregate", True))
    return SequenceArchitectureSource(**data)


def _operation(raw: Any) -> SequenceArchitectureOperationSpec:
    data = dict(raw)
    data["operation"] = SequenceArchitectureOperation(str(data["operation"]))
    data["family"] = SequenceArchitectureFamily(str(data["family"]))
    data["plane"] = SequenceArchitecturePlane(str(data["plane"]))
    data["dependencies"] = _text_tuple(data.get("dependencies", ()), "operation.dependencies")
    data["source_ids"] = _text_tuple(data.get("source_ids", ()), "operation.source_ids")
    return SequenceArchitectureOperationSpec(**data)


def _case(raw: Any) -> SequenceArchitectureCase:
    data = dict(raw)
    data["operation"] = SequenceArchitectureOperation(str(data["operation"]))
    data["family"] = SequenceArchitectureFamily(str(data["family"]))
    data["plane"] = SequenceArchitecturePlane(str(data["plane"]))
    data["scenario"] = SequenceArchitectureScenario(str(data["scenario"]))
    data["delegate_context_key"] = str(data.get("delegate_context_key", data["context_key"]))
    data["expected_state"] = SequenceArchitectureState(str(data["expected_state"]))
    data["source_ids"] = _text_tuple(data.get("source_ids", ()), "case.source_ids")
    data["expected_issue_codes"] = _text_tuple(
        data.get("expected_issue_codes", ()), "case.expected_issue_codes"
    )
    data["expected_counts"] = {
        str(key): int(value) for key, value in dict(data.get("expected_counts", {})).items()
    }
    data["payload"] = dict(data.get("payload", {}))
    return SequenceArchitectureCase(**data)


__all__ = [
    name
    for name in globals()
    if name.startswith("SEQUENCE_ARCHITECTURE_")
    or name.startswith("SequenceArchitecture")
    or name == "addressed"
]

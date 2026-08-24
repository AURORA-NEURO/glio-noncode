"""Typed D07 aggregate contracts for chromatin and methylation evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CHROMATIN_ARCHITECTURE_VERSION = "2026.08.d07-chromatin-architecture.v1"
CHROMATIN_ARCHITECTURE_BOUNDARY = "public_aggregate_chromatin_accessibility_methylation"
CHROMATIN_ARCHITECTURE_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CHROMATIN_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|glioma|adult|differentiated|tumor|unknown"
CHROMATIN_ARCHITECTURE_OPERATION_COUNT = 16
CHROMATIN_ARCHITECTURE_CASES_PER_OPERATION = 4
CHROMATIN_ARCHITECTURE_CASE_COUNT = 64
CHROMATIN_ARCHITECTURE_SOURCE_COUNT = 19
CHROMATIN_ARCHITECTURE_FAMILY_COUNT = 4
CHROMATIN_ARCHITECTURE_ARTIFACT_COUNT = 6


class ChromatinArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class ChromatinArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class ChromatinArchitecturePlane(StrEnum):
    ACCESSIBILITY = "accessibility"
    METHYLATION = "methylation"
    CHROMATIN_STATE = "chromatin_state"
    CROSS_ASSAY = "cross_assay"
    RELEASE = "release"


class ChromatinArchitectureFamily(StrEnum):
    CONTEXT = "chromatin_context_frontier"
    METHYLATION = "methylation_frontier"
    ALPHA = "chromatin_alpha_frontier"
    FRONTIER = "chromatin_frontier"


class ChromatinArchitectureOperation(StrEnum):
    TRACK_RETRIEVAL = "chromatin_track_retrieval"
    ACCESSIBILITY_DELTA = "accessibility_delta"
    HISTONE_CONTEXT = "histone_context"
    H3K27AC_ACTIVITY = "h3k27ac_activity"
    METHYLATION_CONTEXT = "methylation_context_retrieval"
    CPG_CHANGE = "cpg_creation_loss"
    SENSITIVE_MOTIF = "methylation_sensitive_motif"
    IDH_CONTEXT = "idh_hypermethylation_context"
    STATE_SEGMENTATION = "chromatin_state_segmentation"
    ALLELE_SPECIFIC = "allele_specific_chromatin"
    PURITY = "epigenomic_purity"
    COMPOSITION_CORRECTION = "batch_composition_correction"
    CONTEXT_IMPUTATION = "context_imputation_confidence"
    ASSAY_COVERAGE = "assay_support_coverage"
    ASSAY_CONCORDANCE = "cross_assay_concordance"
    EVIDENCE_PUBLISH = "chromatin_evidence_publish"


class ChromatinArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    LINEAGE = "lineage"
    REVIEW = "review"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "chromatin-architecture") -> str:
    """Return the deterministic address used by every D07 aggregate object."""

    return content_hash({"prefix": prefix, "value": value})


def _text_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{name} must be a sequence")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{name} cannot contain blank values")
    return result


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureSource:
    source_id: str
    family: ChromatinArchitectureFamily
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
            raise ValidationError("D07 source URI must be HTTP(S)")
        if self.scope != "public_aggregate":
            raise ValidationError("D07 sources must be public aggregate receipts")
        if not self.public_aggregate:
            raise ValidationError("D07 sources must be marked public aggregate")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D07 source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: ChromatinArchitectureOperation
    family: ChromatinArchitectureFamily
    plane: ChromatinArchitecturePlane
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
            raise ValidationError("D07 operations require positive order and source joins")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D07 operation address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: ChromatinArchitectureOperation
    family: ChromatinArchitectureFamily
    plane: ChromatinArchitecturePlane
    scenario: ChromatinArchitectureScenario
    context_key: str
    delegate_context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: ChromatinArchitectureState
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
            raise ValidationError("D07 cases require source joins and object payloads")
        if any(int(value) < 0 for value in self.expected_counts.values()):
            raise ValidationError("D07 expected counts cannot be negative")
        if self.scenario is ChromatinArchitectureScenario.POSITIVE:
            if self.expected_state is not ChromatinArchitectureState.ACCEPTED:
                raise ValidationError("D07 positive cases must be accepted")
        elif self.expected_state is not ChromatinArchitectureState.REVIEW:
            raise ValidationError("D07 controls must remain in review")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D07 case address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[ChromatinArchitectureSource, ...]
    operations: tuple[ChromatinArchitectureOperationSpec, ...]
    cases: tuple[ChromatinArchitectureCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.version != CHROMATIN_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported D07 chromatin architecture version")
        if self.boundary != CHROMATIN_ARCHITECTURE_BOUNDARY:
            raise ValidationError("D07 boundary does not match the public aggregate contract")
        if self.context_key != CHROMATIN_ARCHITECTURE_CONTEXT:
            raise ValidationError("D07 context does not match the aggregate contract")
        if len(self.sources) != CHROMATIN_ARCHITECTURE_SOURCE_COUNT:
            raise ValidationError("D07 fixture requires nineteen source receipts")
        if len(self.operations) != CHROMATIN_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("D07 fixture requires sixteen operation specifications")
        if len(self.cases) != CHROMATIN_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("D07 fixture requires sixty-four cases")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValidationError("D07 source identifiers must be unique")
        if len({item.operation_id for item in self.operations}) != len(self.operations):
            raise ValidationError("D07 operation identifiers must be unique")
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValidationError("D07 case identifiers must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D07 fixture requires a content address")

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(item.operation_id for item in self.operations)

    @property
    def positive_cases(self) -> tuple[ChromatinArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is ChromatinArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[ChromatinArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not ChromatinArchitectureScenario.POSITIVE
        )

    def operation(self, operation_id: str) -> ChromatinArchitectureOperationSpec:
        for item in self.operations:
            if item.operation_id == operation_id:
                return item
        raise KeyError(operation_id)

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
    def from_mapping(cls, raw: Mapping[str, Any]) -> ChromatinArchitectureFixture:
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
        expected = addressed(body, "chromatin-fixture")
        supplied = str(raw.get("content_address", expected))
        if supplied != expected:
            raise ValidationError("D07 fixture content address does not match its mapping")
        return cls(**body, content_address=supplied)

    @classmethod
    def from_file(cls, path: str | Path) -> ChromatinArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D07 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureCheck:
    check_id: str
    kind: ChromatinArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureDataAudit:
    fixture_id: str
    checks: tuple[ChromatinArchitectureCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureExecution:
    case_id: str
    operation: ChromatinArchitectureOperation
    family: ChromatinArchitectureFamily
    scenario: ChromatinArchitectureScenario
    observed_state: ChromatinArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: dict[str, int]
    output_address: str
    summary: dict[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    family: ChromatinArchitectureFamily
    expected_state: ChromatinArchitectureState
    observed_state: ChromatinArchitectureState
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
class ChromatinArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: ChromatinArchitectureState
    executions: tuple[ChromatinArchitectureExecution, ...]
    receipts: tuple[ChromatinArchitectureCaseReceipt, ...]
    checks: tuple[ChromatinArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is ChromatinArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    @property
    def positive_count(self) -> int:
        return sum(
            item.expected_state is ChromatinArchitectureState.ACCEPTED for item in self.receipts
        )

    @property
    def control_count(self) -> int:
        return sum(
            item.expected_state is ChromatinArchitectureState.REVIEW for item in self.receipts
        )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class ChromatinArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: ChromatinArchitectureFamily
    plane: ChromatinArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitecturePlan:
    fixture_id: str
    nodes: tuple[ChromatinArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureReviewItem:
    case_id: str
    operation_id: str
    scenario: ChromatinArchitectureScenario
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureReviewQueue:
    fixture_id: str
    items: tuple[ChromatinArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureLedgerEvent:
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
class ChromatinArchitectureLedger:
    fixture_id: str
    events: tuple[ChromatinArchitectureLedgerEvent, ...]
    state_counts: Mapping[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureArtifact:
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
class ChromatinArchitectureRelease:
    release_id: str
    fixture_id: str
    state: ChromatinArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureRuntimeStage:
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
class ChromatinArchitectureRuntime:
    fixture: ChromatinArchitectureFixture
    audit: ChromatinArchitectureDataAudit
    plan: ChromatinArchitecturePlan
    evaluation: ChromatinArchitectureEvaluation
    review_queue: ChromatinArchitectureReviewQueue
    ledger: ChromatinArchitectureLedger
    artifacts: tuple[ChromatinArchitectureArtifact, ...]
    release: ChromatinArchitectureRelease
    depth: ChromatinArchitectureDepthReport
    quality: ChromatinArchitectureQualityGate
    compliance: Any
    stages: tuple[ChromatinArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureDepthReport:
    fixture_id: str
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    source_count: int
    family_count: int
    addressed_count: int
    family_counts: Mapping[str, int]
    plane_counts: Mapping[str, int]
    check_count: int
    state_count: int
    issue_code_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureQualityGate:
    fixture_id: str
    checks: tuple[ChromatinArchitectureCheck, ...]
    release: ChromatinArchitectureRelease
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _source(raw: Mapping[str, Any]) -> ChromatinArchitectureSource:
    body = {
        "source_id": str(raw.get("source_id", "")),
        "family": ChromatinArchitectureFamily(str(raw.get("family", ""))),
        "title": str(raw.get("title", raw.get("source_id", ""))),
        "uri": str(raw.get("uri", "")),
        "version": str(raw.get("version", "public")),
        "scope": str(raw.get("scope", "")),
        "license": str(raw.get("license", "public source receipt")),
        "public_aggregate": bool(raw.get("public_aggregate", True)),
    }
    return ChromatinArchitectureSource(**body, content_address=addressed(body, "chromatin-source"))


def _operation(raw: Mapping[str, Any]) -> ChromatinArchitectureOperationSpec:
    body = {
        "operation_id": str(raw.get("operation_id", "")),
        "capability_id": str(raw.get("capability_id", "")),
        "ordinal": int(raw.get("ordinal", 0)),
        "operation": ChromatinArchitectureOperation(str(raw.get("operation", ""))),
        "family": ChromatinArchitectureFamily(str(raw.get("family", ""))),
        "plane": ChromatinArchitecturePlane(str(raw.get("plane", ""))),
        "input_contract": str(raw.get("input_contract", "")),
        "output_contract": str(raw.get("output_contract", "")),
        "dependencies": _text_tuple(raw.get("dependencies", ()), "dependencies")
        if raw.get("dependencies", ())
        else (),
        "source_ids": _text_tuple(raw.get("source_ids", ()), "source_ids"),
        "control_policy": str(raw.get("control_policy", "")),
    }
    return ChromatinArchitectureOperationSpec(
        **body, content_address=addressed(body, "chromatin-operation")
    )


def _case(raw: Mapping[str, Any]) -> ChromatinArchitectureCase:
    body = {
        "case_id": str(raw.get("case_id", "")),
        "operation_id": str(raw.get("operation_id", "")),
        "capability_id": str(raw.get("capability_id", "")),
        "operation": ChromatinArchitectureOperation(str(raw.get("operation", ""))),
        "family": ChromatinArchitectureFamily(str(raw.get("family", ""))),
        "plane": ChromatinArchitecturePlane(str(raw.get("plane", ""))),
        "scenario": ChromatinArchitectureScenario(str(raw.get("scenario", ""))),
        "context_key": str(raw.get("context_key", "")),
        "delegate_context_key": str(
            raw.get("delegate_context_key", raw.get("context_key", ""))
        ),
        "source_ids": _text_tuple(raw.get("source_ids", ()), "source_ids"),
        "payload": dict(raw.get("payload", {})),
        "expected_state": ChromatinArchitectureState(str(raw.get("expected_state", ""))),
        "expected_result_state": str(raw.get("expected_result_state", "")),
        "expected_issue_codes": _text_tuple(
            raw.get("expected_issue_codes", ()), "expected_issue_codes"
        )
        if raw.get("expected_issue_codes", ())
        else (),
        "expected_counts": {
            str(k): int(v) for k, v in dict(raw.get("expected_counts", {})).items()
        },
        "description": str(raw.get("description", "")),
    }
    return ChromatinArchitectureCase(**body, content_address=addressed(body, "chromatin-case"))


__all__ = [
    "CHROMATIN_ARCHITECTURE_ARTIFACT_COUNT",
    "CHROMATIN_ARCHITECTURE_BOUNDARY",
    "CHROMATIN_ARCHITECTURE_CASE_COUNT",
    "CHROMATIN_ARCHITECTURE_CASES_PER_OPERATION",
    "CHROMATIN_ARCHITECTURE_CONTEXT",
    "CHROMATIN_ARCHITECTURE_FOREIGN_CONTEXT",
    "CHROMATIN_ARCHITECTURE_FAMILY_COUNT",
    "CHROMATIN_ARCHITECTURE_OPERATION_COUNT",
    "CHROMATIN_ARCHITECTURE_SOURCE_COUNT",
    "CHROMATIN_ARCHITECTURE_VERSION",
    "ChromatinArchitectureArtifact",
    "ChromatinArchitectureCase",
    "ChromatinArchitectureCaseReceipt",
    "ChromatinArchitectureCheck",
    "ChromatinArchitectureCheckKind",
    "ChromatinArchitectureDataAudit",
    "ChromatinArchitectureDepthReport",
    "ChromatinArchitectureEvaluation",
    "ChromatinArchitectureExecution",
    "ChromatinArchitectureFamily",
    "ChromatinArchitectureFixture",
    "ChromatinArchitectureLedger",
    "ChromatinArchitectureLedgerEvent",
    "ChromatinArchitectureOperation",
    "ChromatinArchitectureOperationSpec",
    "ChromatinArchitecturePlane",
    "ChromatinArchitecturePlan",
    "ChromatinArchitecturePlanNode",
    "ChromatinArchitectureQualityGate",
    "ChromatinArchitectureRelease",
    "ChromatinArchitectureReviewItem",
    "ChromatinArchitectureReviewQueue",
    "ChromatinArchitectureRuntime",
    "ChromatinArchitectureRuntimeStage",
    "ChromatinArchitectureScenario",
    "ChromatinArchitectureSource",
    "ChromatinArchitectureState",
    "addressed",
]

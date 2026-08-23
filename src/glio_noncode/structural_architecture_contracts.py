"""Closed contracts for the composed Domain 02 structural architecture.

The existing structural families are deliberately kept as the scientific
adapters.  This module defines the boundary around them: operation identity,
source scope, public aggregate cases, execution receipts, review routing,
hash-linked lineage, and release accounting.  The boundary is deterministic
and stores only bounded summaries and public identifiers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

STRUCTURAL_ARCHITECTURE_VERSION = "2026.08.structural-architecture.v1"
STRUCTURAL_ARCHITECTURE_BOUNDARY = "public_aggregate_structural_evidence_and_reconstruction"
STRUCTURAL_ARCHITECTURE_CONTEXT = (
    "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
)
STRUCTURAL_ARCHITECTURE_FOREIGN_CONTEXT = (
    "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
)
STRUCTURAL_ARCHITECTURE_OPERATION_COUNT = 16
STRUCTURAL_ARCHITECTURE_CASES_PER_OPERATION = 4
STRUCTURAL_ARCHITECTURE_CASE_COUNT = (
    STRUCTURAL_ARCHITECTURE_OPERATION_COUNT * STRUCTURAL_ARCHITECTURE_CASES_PER_OPERATION
)
STRUCTURAL_ARCHITECTURE_ARTIFACT_COUNT = 6


class StructuralArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"


class StructuralArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    DUPLICATE_IDENTITY = "duplicate_identity"


class StructuralArchitecturePlane(StrEnum):
    INGESTION = "ingestion"
    RECONSTRUCTION = "reconstruction"
    HAPLOTYPE = "haplotype"
    CONTEXT = "context"
    PROVENANCE = "provenance"
    REVIEW = "review"
    RELEASE = "release"


class StructuralArchitectureOperation(StrEnum):
    RECONSTRUCTION = "reconstruction"
    CONSENSUS = "consensus"
    COMPLEX_RESOLUTION = "complex_resolution"
    COPY_NUMBER = "copy_number"
    FOCAL_AMPLIFICATION = "focal_amplification"
    CHROMOTHRIPSIS = "chromothripsis"
    ECDNA = "ecdna"
    ENHANCER_HIJACKING = "enhancer_hijacking"
    PHASED_HAPLOTYPE = "phased_haplotype"
    ALLELE_AWARE_SV = "allele_aware_sv"
    PANGENOME_PROJECTION = "pangenome_projection"
    REPEAT_MOBILE_ANNOTATION = "repeat_mobile_annotation"
    TANDEM_REPEAT = "tandem_repeat"
    COMPOUND_HAPLOTYPE = "compound_haplotype"
    BREAKPOINT_UNCERTAINTY = "breakpoint_uncertainty"
    STRUCTURAL_EVIDENCE_EXPORT = "structural_evidence_export"


class StructuralArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    POLICY = "policy"
    LINEAGE = "lineage"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "structural-architecture") -> str:
    """Return a stable content address for a bounded architecture object."""

    return content_hash(value, prefix=prefix)


def _tuple_text(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{field_name} must be an array")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{field_name} must contain non-empty values")
    return result


@dataclass(frozen=True, slots=True)
class StructuralArchitectureSource:
    source_id: str
    title: str
    uri: str
    version: str
    scope: str
    license: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "version", "scope", "license", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("structural architecture sources require HTTPS")
        if self.scope != "public_aggregate":
            raise ValidationError("structural architecture sources must be public aggregate")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("structural architecture sources require a content address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: StructuralArchitectureOperation
    family: str
    plane: StructuralArchitecturePlane
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
            "family",
            "input_contract",
            "output_contract",
            "control_policy",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.ordinal < 1 or not self.source_ids:
            raise ValidationError("operation ordinals and source joins are required")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("operation specs require a content address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: StructuralArchitectureOperation
    scenario: StructuralArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    public_identifier: str
    payload: Mapping[str, Any]
    expected_state: StructuralArchitectureState
    expected_result_state: str
    expected_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    content_address: str
    description: str = ""

    def __post_init__(self) -> None:
        for name in (
            "case_id",
            "operation_id",
            "capability_id",
            "context_key",
            "public_identifier",
            "expected_result_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not self.payload:
            raise ValidationError("architecture cases require sources and payloads")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("architecture cases require a content address")
        if len(self.expected_issue_codes) != len(set(self.expected_issue_codes)):
            raise ValidationError("case issue codes must be unique")
        for key, value in self.expected_counts.items():
            if not str(key).strip() or int(value) < 0:
                raise ValidationError("case counts must be named and non-negative")
        if self.scenario is StructuralArchitectureScenario.POSITIVE:
            if self.expected_state is not StructuralArchitectureState.ACCEPTED:
                raise ValidationError("positive cases must expect acceptance")
            if self.expected_issue_codes:
                raise ValidationError("positive cases cannot require issue codes")
        elif self.expected_state is StructuralArchitectureState.ACCEPTED:
            raise ValidationError("control cases cannot expect architecture acceptance")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[StructuralArchitectureSource, ...]
    operations: tuple[StructuralArchitectureOperationSpec, ...]
    cases: tuple[StructuralArchitectureCase, ...]
    content_address: str
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "boundary", "context_key", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != STRUCTURAL_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported structural architecture version")
        if self.boundary != STRUCTURAL_ARCHITECTURE_BOUNDARY:
            raise ValidationError("structural architecture boundary is closed")
        if len(self.operations) != STRUCTURAL_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("structural architecture requires sixteen operation specs")
        if len(self.cases) != STRUCTURAL_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("structural architecture requires four cases per operation")
        if not self.sources or not self.content_address.startswith("sha256:"):
            raise ValidationError("structural architecture requires sources and an address")
        if len({source.source_id for source in self.sources}) != len(self.sources):
            raise ValidationError("structural architecture source IDs must be unique")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValidationError("structural architecture case IDs must be unique")

    @property
    def positive_cases(self) -> tuple[StructuralArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is StructuralArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[StructuralArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not StructuralArchitectureScenario.POSITIVE
        )

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(item.operation.value for item in self.operations)

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(item.source_id for item in self.sources))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralArchitectureFixture:
        if not isinstance(raw, Mapping):
            raise ValidationError("structural architecture fixture must be an object")
        sources = tuple(_source(item) for item in raw.get("sources", ()))
        operations = tuple(_operation(item) for item in raw.get("operations", ()))
        cases = tuple(_case(item) for item in raw.get("cases", ()))
        return cls(
            fixture_id=str(raw.get("fixture_id", "")),
            version=str(raw.get("version", "")),
            boundary=str(raw.get("boundary", "")),
            context_key=str(raw.get("context_key", "")),
            sources=sources,
            operations=operations,
            cases=cases,
            content_address=str(raw.get("content_address", "")),
            notes=_tuple_text(raw.get("notes", ()), "notes") if raw.get("notes", ()) else (),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> StructuralArchitectureFixture:
        file_path = Path(path)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"architecture fixture not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid architecture fixture JSON: {exc}") from exc
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureCheck:
    check_id: str
    kind: StructuralArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureDataAudit:
    fixture_id: str
    checks: tuple[StructuralArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureExecution:
    case_id: str
    operation: StructuralArchitectureOperation
    scenario: StructuralArchitectureScenario
    observed_state: StructuralArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: StructuralArchitectureState
    observed_state: StructuralArchitectureState
    expected_result_state: str
    observed_result_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    observed_counts: Mapping[str, int]
    passed: bool
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: StructuralArchitectureState
    receipts: tuple[StructuralArchitectureCaseReceipt, ...]
    checks: tuple[StructuralArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is StructuralArchitectureState.ACCEPTED and all(
            item.passed for item in self.receipts
        )

    @property
    def positive_count(self) -> int:
        return sum(
            item.expected_state is StructuralArchitectureState.ACCEPTED for item in self.receipts
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
class StructuralArchitecturePlanNode:
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
class StructuralArchitecturePlan:
    fixture_id: str
    nodes: tuple[StructuralArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureReviewItem:
    review_id: str
    case_id: str
    operation_id: str
    reason_codes: tuple[str, ...]
    priority: int
    disposition: str
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureReviewQueue:
    fixture_id: str
    items: tuple[StructuralArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureLedgerEvent:
    sequence: int
    case_id: str
    operation_id: str
    input_address: str
    output_address: str
    previous_address: str
    state: StructuralArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureLedger:
    fixture_id: str
    events: tuple[StructuralArchitectureLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureArtifact:
    artifact_id: str
    artifact_type: str
    media_type: str
    row_count: int
    source_addresses: tuple[str, ...]
    content_address: str
    retention: str

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise ValidationError("artifact row count cannot be negative")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("artifacts require content addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureRelease:
    fixture_id: str
    state: StructuralArchitectureState
    artifacts: tuple[StructuralArchitectureArtifact, ...]
    rollback_key: str
    checks: tuple[StructuralArchitectureCheck, ...]
    content_address: str

    @property
    def published(self) -> bool:
        return self.state is StructuralArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"published": self.published}


@dataclass(frozen=True, slots=True)
class StructuralArchitectureRuntimeStage:
    stage_id: str
    ordinal: int
    state: StructuralArchitectureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureRuntime:
    run_id: str
    fixture_id: str
    state: StructuralArchitectureState
    stages: tuple[StructuralArchitectureRuntimeStage, ...]
    evaluation: StructuralArchitectureEvaluation
    plan: StructuralArchitecturePlan
    review_queue: StructuralArchitectureReviewQueue
    ledger: StructuralArchitectureLedger
    artifacts: tuple[StructuralArchitectureArtifact, ...]
    release: StructuralArchitectureRelease
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is StructuralArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "stage_count": len(self.stages)}


@dataclass(frozen=True, slots=True)
class StructuralArchitectureDepthReport:
    fixture_id: str
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    stage_count: int
    artifact_count: int
    addressed_count: int
    accepted: bool
    checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralArchitectureQualityGate:
    fixture_id: str
    state: StructuralArchitectureState
    checks: tuple[StructuralArchitectureCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state is StructuralArchitectureState.PUBLISHED and all(
            item.passed for item in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def _source(raw: Any) -> StructuralArchitectureSource:
    if not isinstance(raw, Mapping):
        raise ValidationError("architecture source must be an object")
    return StructuralArchitectureSource(
        source_id=str(raw.get("source_id", "")),
        title=str(raw.get("title", "")),
        uri=str(raw.get("uri", "")),
        version=str(raw.get("version", "")),
        scope=str(raw.get("scope", "")),
        license=str(raw.get("license", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _operation(raw: Any) -> StructuralArchitectureOperationSpec:
    if not isinstance(raw, Mapping):
        raise ValidationError("architecture operation must be an object")
    return StructuralArchitectureOperationSpec(
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        ordinal=int(raw.get("ordinal", 0)),
        operation=StructuralArchitectureOperation(str(raw.get("operation", ""))),
        family=str(raw.get("family", "")),
        plane=StructuralArchitecturePlane(str(raw.get("plane", ""))),
        input_contract=str(raw.get("input_contract", "")),
        output_contract=str(raw.get("output_contract", "")),
        dependencies=_tuple_text(raw.get("dependencies", ()), "dependencies"),
        source_ids=_tuple_text(raw.get("source_ids", ()), "source_ids"),
        control_policy=str(raw.get("control_policy", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _case(raw: Any) -> StructuralArchitectureCase:
    if not isinstance(raw, Mapping):
        raise ValidationError("architecture case must be an object")
    counts = raw.get("expected_counts", {})
    if not isinstance(counts, Mapping):
        raise ValidationError("architecture expected_counts must be an object")
    payload = raw.get("payload", {})
    if not isinstance(payload, Mapping):
        raise ValidationError("architecture case payload must be an object")
    return StructuralArchitectureCase(
        case_id=str(raw.get("case_id", "")),
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        operation=StructuralArchitectureOperation(str(raw.get("operation", ""))),
        scenario=StructuralArchitectureScenario(str(raw.get("scenario", ""))),
        context_key=str(raw.get("context_key", "")),
        source_ids=_tuple_text(raw.get("source_ids", ()), "source_ids"),
        public_identifier=str(raw.get("public_identifier", "")),
        payload=dict(payload),
        expected_state=StructuralArchitectureState(str(raw.get("expected_state", ""))),
        expected_result_state=str(raw.get("expected_result_state", "")),
        expected_issue_codes=_tuple_text(
            raw.get("expected_issue_codes", ()), "expected_issue_codes"
        )
        if raw.get("expected_issue_codes", ())
        else (),
        expected_counts={str(key): int(value) for key, value in counts.items()},
        content_address=str(raw.get("content_address", "")),
        description=str(raw.get("description", "")),
    )


__all__ = [
    "STRUCTURAL_ARCHITECTURE_ARTIFACT_COUNT",
    "STRUCTURAL_ARCHITECTURE_BOUNDARY",
    "STRUCTURAL_ARCHITECTURE_CASE_COUNT",
    "STRUCTURAL_ARCHITECTURE_CASES_PER_OPERATION",
    "STRUCTURAL_ARCHITECTURE_CONTEXT",
    "STRUCTURAL_ARCHITECTURE_FOREIGN_CONTEXT",
    "STRUCTURAL_ARCHITECTURE_OPERATION_COUNT",
    "STRUCTURAL_ARCHITECTURE_VERSION",
    "StructuralArchitectureArtifact",
    "StructuralArchitectureCase",
    "StructuralArchitectureCaseReceipt",
    "StructuralArchitectureCheck",
    "StructuralArchitectureCheckKind",
    "StructuralArchitectureDataAudit",
    "StructuralArchitectureDepthReport",
    "StructuralArchitectureEvaluation",
    "StructuralArchitectureExecution",
    "StructuralArchitectureFixture",
    "StructuralArchitectureLedger",
    "StructuralArchitectureLedgerEvent",
    "StructuralArchitectureOperation",
    "StructuralArchitectureOperationSpec",
    "StructuralArchitecturePlan",
    "StructuralArchitecturePlanNode",
    "StructuralArchitecturePlane",
    "StructuralArchitectureQualityGate",
    "StructuralArchitectureRelease",
    "StructuralArchitectureReviewItem",
    "StructuralArchitectureReviewQueue",
    "StructuralArchitectureRuntime",
    "StructuralArchitectureRuntimeStage",
    "StructuralArchitectureScenario",
    "StructuralArchitectureSource",
    "StructuralArchitectureState",
    "addressed",
]

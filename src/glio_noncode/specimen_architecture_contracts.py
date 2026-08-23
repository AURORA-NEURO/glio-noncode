"""Closed contracts for the composed Domain 03 specimen architecture.

The four existing specimen planes remain the typed scientific adapters. This
module defines the common public-aggregate boundary around them: source
receipts, operation identity, case declarations, sanitized execution
receipts, review routing, lineage, release artifacts, and runtime stages.
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

SPECIMEN_ARCHITECTURE_VERSION = "2026.08.specimen-architecture.v1"
SPECIMEN_ARCHITECTURE_BOUNDARY = "public_aggregate_specimen_context_and_release"
SPECIMEN_ARCHITECTURE_CONTEXT = (
    "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
)
SPECIMEN_ARCHITECTURE_FOREIGN_CONTEXT = (
    "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
)
SPECIMEN_ARCHITECTURE_OPERATION_COUNT = 16
SPECIMEN_ARCHITECTURE_CASES_PER_OPERATION = 4
SPECIMEN_ARCHITECTURE_CASE_COUNT = (
    SPECIMEN_ARCHITECTURE_OPERATION_COUNT * SPECIMEN_ARCHITECTURE_CASES_PER_OPERATION
)
SPECIMEN_ARCHITECTURE_ARTIFACT_COUNT = 6


class SpecimenArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class SpecimenArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class SpecimenArchitecturePlane(StrEnum):
    INGESTION = "ingestion"
    ONTOLOGY = "ontology"
    PURITY_INTEGRITY = "purity_integrity"
    ORIGIN_CLONALITY = "origin_clonality"
    LINEAGE = "lineage"
    PREANALYTIC = "preanalytic"
    RELEASE = "release"


class SpecimenArchitectureOperation(StrEnum):
    ONTOLOGY_MAPPING = "ontology_mapping"
    MATCHED_NORMAL = "matched_normal"
    PURITY_PLOIDY = "purity_ploidy"
    SAMPLE_INTEGRITY = "sample_integrity"
    ORIGIN = "origin"
    MOSAICISM = "mosaicism"
    CANCER_CELL_FRACTION = "cancer_cell_fraction"
    SUBCLONE = "subclone"
    REGION_LINEAGE = "region_lineage"
    LONGITUDINAL_LINKING = "longitudinal_linking"
    PHASE_MAPPING = "phase_mapping"
    TREATMENT_CONTEXT = "treatment_context"
    PREANALYTIC_QUALITY = "preanalytic_quality"
    ASSAY_LINEAGE = "assay_lineage"
    IDENTITY_ADJUDICATION = "identity_adjudication"
    CONTEXT_ENVELOPE = "context_envelope"


class SpecimenArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    LINEAGE = "lineage"
    REVIEW = "review"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "specimen-architecture") -> str:
    return content_hash(value, prefix=prefix)


def _text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{field_name} must be an array")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{field_name} must contain non-empty values")
    return result


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureSource:
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
            raise ValidationError("specimen architecture sources require HTTPS")
        if self.scope != "public_aggregate":
            raise ValidationError("specimen architecture sources must be public aggregate")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen architecture sources require an address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: SpecimenArchitectureOperation
    family: str
    plane: SpecimenArchitecturePlane
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
            raise ValidationError("specimen operation ordinals and source joins are required")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen operation specs require an address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: SpecimenArchitectureOperation
    scenario: SpecimenArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    aggregate_identifier: str
    payload: Mapping[str, Any]
    parameters: Mapping[str, Any]
    expected_state: SpecimenArchitectureState
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
            "aggregate_identifier",
            "expected_result_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not self.payload:
            raise ValidationError("specimen cases require sources and payloads")
        if len(self.expected_issue_codes) != len(set(self.expected_issue_codes)):
            raise ValidationError("specimen issue codes must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen cases require an address")
        for key, value in self.expected_counts.items():
            if not str(key).strip() or int(value) < 0:
                raise ValidationError("specimen case counts must be named and non-negative")
        if self.scenario is SpecimenArchitectureScenario.POSITIVE:
            if self.expected_state is not SpecimenArchitectureState.ACCEPTED:
                raise ValidationError("specimen positive cases must expect acceptance")
            if self.expected_issue_codes:
                raise ValidationError("specimen positive cases cannot require issues")
        elif self.expected_state is SpecimenArchitectureState.ACCEPTED:
            raise ValidationError("specimen controls cannot expect acceptance")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[SpecimenArchitectureSource, ...]
    operations: tuple[SpecimenArchitectureOperationSpec, ...]
    cases: tuple[SpecimenArchitectureCase, ...]
    content_address: str
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "boundary", "context_key", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != SPECIMEN_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported specimen architecture version")
        if self.boundary != SPECIMEN_ARCHITECTURE_BOUNDARY:
            raise ValidationError("specimen architecture boundary is closed")
        if len(self.operations) != SPECIMEN_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("specimen architecture requires sixteen operation specs")
        if len(self.cases) != SPECIMEN_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("specimen architecture requires four cases per operation")
        if not self.sources or not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen architecture requires sources and an address")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValidationError("specimen architecture source IDs must be unique")
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValidationError("specimen architecture case IDs must be unique")

    @property
    def positive_cases(self) -> tuple[SpecimenArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is SpecimenArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[SpecimenArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not SpecimenArchitectureScenario.POSITIVE
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
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenArchitectureFixture:
        if not isinstance(raw, Mapping):
            raise ValidationError("specimen architecture fixture must be an object")
        sources = tuple(_source(item) for item in raw.get("sources", ()))
        operations = tuple(_operation(item) for item in raw.get("operations", ()))
        cases = tuple(_case(item) for item in raw.get("cases", ()))
        notes = raw.get("notes", ())
        return cls(
            fixture_id=str(raw.get("fixture_id", "")),
            version=str(raw.get("version", "")),
            boundary=str(raw.get("boundary", "")),
            context_key=str(raw.get("context_key", "")),
            sources=sources,
            operations=operations,
            cases=cases,
            content_address=str(raw.get("content_address", "")),
            notes=_text_tuple(notes, "notes") if notes else (),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> SpecimenArchitectureFixture:
        file_path = Path(path)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"specimen architecture fixture not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid specimen architecture JSON: {exc}") from exc
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureCheck:
    check_id: str
    kind: SpecimenArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureDataAudit:
    fixture_id: str
    checks: tuple[SpecimenArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureExecution:
    case_id: str
    operation: SpecimenArchitectureOperation
    scenario: SpecimenArchitectureScenario
    observed_state: SpecimenArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: SpecimenArchitectureState
    observed_state: SpecimenArchitectureState
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
class SpecimenArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: SpecimenArchitectureState
    receipts: tuple[SpecimenArchitectureCaseReceipt, ...]
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is SpecimenArchitectureState.ACCEPTED and all(
            item.passed for item in self.receipts
        )

    @property
    def positive_count(self) -> int:
        return sum(
            item.expected_state is SpecimenArchitectureState.ACCEPTED for item in self.receipts
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
class SpecimenArchitecturePlanNode:
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
class SpecimenArchitecturePlan:
    fixture_id: str
    nodes: tuple[SpecimenArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureReviewItem:
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
class SpecimenArchitectureReviewQueue:
    fixture_id: str
    items: tuple[SpecimenArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureLedgerEvent:
    sequence: int
    case_id: str
    operation_id: str
    input_address: str
    output_address: str
    previous_address: str
    state: SpecimenArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureLedger:
    fixture_id: str
    events: tuple[SpecimenArchitectureLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureArtifact:
    artifact_id: str
    artifact_type: str
    media_type: str
    row_count: int
    source_addresses: tuple[str, ...]
    content_address: str
    retention: str

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise ValidationError("specimen artifact row count cannot be negative")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("specimen artifacts require addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureRelease:
    fixture_id: str
    state: SpecimenArchitectureState
    artifacts: tuple[SpecimenArchitectureArtifact, ...]
    rollback_key: str
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str

    @property
    def published(self) -> bool:
        return self.state is SpecimenArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"published": self.published}


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureRuntimeStage:
    stage_id: str
    ordinal: int
    state: SpecimenArchitectureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureRuntime:
    run_id: str
    fixture_id: str
    state: SpecimenArchitectureState
    stages: tuple[SpecimenArchitectureRuntimeStage, ...]
    evaluation: SpecimenArchitectureEvaluation
    plan: SpecimenArchitecturePlan
    review_queue: SpecimenArchitectureReviewQueue
    ledger: SpecimenArchitectureLedger
    artifacts: tuple[SpecimenArchitectureArtifact, ...]
    release: SpecimenArchitectureRelease
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is SpecimenArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        value = jsonable(self)
        value["release"] = self.release.to_dict()
        value["review_queue"] = self.review_queue.to_dict()
        value["ledger"] = self.ledger.to_dict()
        value["plan"] = self.plan.to_dict()
        value["evaluation"] = self.evaluation.to_dict()
        return value | {"accepted": self.accepted, "stage_count": len(self.stages)}


@dataclass(frozen=True, slots=True)
class SpecimenArchitectureDepthReport:
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
class SpecimenArchitectureQualityGate:
    fixture_id: str
    state: SpecimenArchitectureState
    checks: tuple[SpecimenArchitectureCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state is SpecimenArchitectureState.PUBLISHED and all(
            item.passed for item in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def _source(raw: Any) -> SpecimenArchitectureSource:
    if not isinstance(raw, Mapping):
        raise ValidationError("specimen source must be an object")
    return SpecimenArchitectureSource(
        source_id=str(raw.get("source_id", "")),
        title=str(raw.get("title", "")),
        uri=str(raw.get("uri", "")),
        version=str(raw.get("version", "")),
        scope=str(raw.get("scope", "")),
        license=str(raw.get("license", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _operation(raw: Any) -> SpecimenArchitectureOperationSpec:
    if not isinstance(raw, Mapping):
        raise ValidationError("specimen operation must be an object")
    return SpecimenArchitectureOperationSpec(
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        ordinal=int(raw.get("ordinal", 0)),
        operation=SpecimenArchitectureOperation(str(raw.get("operation", ""))),
        family=str(raw.get("family", "")),
        plane=SpecimenArchitecturePlane(str(raw.get("plane", ""))),
        input_contract=str(raw.get("input_contract", "")),
        output_contract=str(raw.get("output_contract", "")),
        dependencies=_text_tuple(raw.get("dependencies", ()), "dependencies"),
        source_ids=_text_tuple(raw.get("source_ids", ()), "source_ids"),
        control_policy=str(raw.get("control_policy", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _case(raw: Any) -> SpecimenArchitectureCase:
    if not isinstance(raw, Mapping):
        raise ValidationError("specimen case must be an object")
    payload = raw.get("payload", {})
    parameters = raw.get("parameters", {})
    counts = raw.get("expected_counts", {})
    if (
        not isinstance(payload, Mapping)
        or not isinstance(parameters, Mapping)
        or not isinstance(counts, Mapping)
    ):
        raise ValidationError("specimen case payload, parameters, and counts must be objects")
    issue_codes = raw.get("expected_issue_codes", ())
    if (
        isinstance(issue_codes, Sequence)
        and issue_codes
        and all(isinstance(item, (list, tuple)) for item in issue_codes)
    ):
        issue_codes = [subitem for group in issue_codes for subitem in group]
    return SpecimenArchitectureCase(
        case_id=str(raw.get("case_id", "")),
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        operation=SpecimenArchitectureOperation(str(raw.get("operation", ""))),
        scenario=SpecimenArchitectureScenario(str(raw.get("scenario", ""))),
        context_key=str(raw.get("context_key", "")),
        source_ids=_text_tuple(raw.get("source_ids", ()), "source_ids"),
        aggregate_identifier=str(raw.get("aggregate_identifier", "")),
        payload=dict(payload),
        parameters=dict(parameters),
        expected_state=SpecimenArchitectureState(str(raw.get("expected_state", ""))),
        expected_result_state=str(raw.get("expected_result_state", "")),
        expected_issue_codes=_text_tuple(issue_codes, "expected_issue_codes")
        if issue_codes
        else (),
        expected_counts={str(key): int(value) for key, value in counts.items()},
        content_address=str(raw.get("content_address", "")),
        description=str(raw.get("description", "")),
    )


__all__ = [
    "SPECIMEN_ARCHITECTURE_ARTIFACT_COUNT",
    "SPECIMEN_ARCHITECTURE_BOUNDARY",
    "SPECIMEN_ARCHITECTURE_CASE_COUNT",
    "SPECIMEN_ARCHITECTURE_CASES_PER_OPERATION",
    "SPECIMEN_ARCHITECTURE_CONTEXT",
    "SPECIMEN_ARCHITECTURE_FOREIGN_CONTEXT",
    "SPECIMEN_ARCHITECTURE_OPERATION_COUNT",
    "SPECIMEN_ARCHITECTURE_VERSION",
    "SpecimenArchitectureArtifact",
    "SpecimenArchitectureCase",
    "SpecimenArchitectureCaseReceipt",
    "SpecimenArchitectureCheck",
    "SpecimenArchitectureCheckKind",
    "SpecimenArchitectureDataAudit",
    "SpecimenArchitectureDepthReport",
    "SpecimenArchitectureEvaluation",
    "SpecimenArchitectureExecution",
    "SpecimenArchitectureFixture",
    "SpecimenArchitectureLedger",
    "SpecimenArchitectureLedgerEvent",
    "SpecimenArchitectureOperation",
    "SpecimenArchitectureOperationSpec",
    "SpecimenArchitecturePlan",
    "SpecimenArchitecturePlanNode",
    "SpecimenArchitecturePlane",
    "SpecimenArchitectureQualityGate",
    "SpecimenArchitectureRelease",
    "SpecimenArchitectureReviewItem",
    "SpecimenArchitectureReviewQueue",
    "SpecimenArchitectureRuntime",
    "SpecimenArchitectureRuntimeStage",
    "SpecimenArchitectureScenario",
    "SpecimenArchitectureSource",
    "SpecimenArchitectureState",
    "addressed",
]

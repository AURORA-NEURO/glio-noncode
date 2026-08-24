"""Closed contracts for the composed Domain 04 reference architecture.

The coordinate, annotation, governance, and release planes remain the typed
execution authorities.  This module defines the shared public-aggregate
boundary around them: source identity, operation joins, scenario policy,
sanitized receipts, review, lineage, artifacts, and runtime stages.
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

REFERENCE_ARCHITECTURE_VERSION = "2026.08.reference-architecture.v1"
REFERENCE_ARCHITECTURE_BOUNDARY = "public_aggregate_reference_context_and_release"
REFERENCE_ARCHITECTURE_CONTEXT = "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
REFERENCE_ARCHITECTURE_FOREIGN_CONTEXT = (
    "GRCh37|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
)
REFERENCE_ARCHITECTURE_OPERATION_COUNT = 16
REFERENCE_ARCHITECTURE_CASES_PER_OPERATION = 4
REFERENCE_ARCHITECTURE_CASE_COUNT = (
    REFERENCE_ARCHITECTURE_OPERATION_COUNT * REFERENCE_ARCHITECTURE_CASES_PER_OPERATION
)
REFERENCE_ARCHITECTURE_SOURCE_COUNT = 20
REFERENCE_ARCHITECTURE_FAMILY_COUNT = 4
REFERENCE_ARCHITECTURE_ARTIFACT_COUNT = 6


class ReferenceArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class ReferenceArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class ReferenceArchitecturePlane(StrEnum):
    INGESTION = "ingestion"
    COORDINATE = "coordinate"
    ANNOTATION = "annotation"
    GOVERNANCE = "governance"
    RELEASE = "release"


class ReferenceArchitectureOperation(StrEnum):
    REFERENCE_REGISTRY = "reference_registry"
    LIFTOVER_CHAIN = "liftover_chain"
    LIFTOVER_AMBIGUITY = "liftover_ambiguity"
    PANGENOME_COORDINATE = "pangenome_coordinate"
    GENCODE_TRANSCRIPT = "gencode_transcript_catalog"
    MANE_TRANSCRIPT = "mane_transcript_catalog"
    REGULATORY_ONTOLOGY = "regulatory_ontology_catalog"
    DISEASE_ONTOLOGY = "disease_ontology_mapping"
    GENE_ALIAS = "gene_alias_version_resolution"
    POPULATION_FREQUENCY = "population_frequency_adaptation"
    REFERENCE_SNAPSHOT = "reference_snapshot_manifest"
    LICENSE_RESTRICTION = "license_use_restriction"
    PROVENANCE_CHECK = "source_provenance_check"
    ANNOTATION_DRIFT = "annotation_drift_detection"
    REFERENCE_BUNDLE = "reproducible_reference_bundle"
    RELEASE_GATE = "reference_release_gate"


class ReferenceArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    LINEAGE = "lineage"
    REVIEW = "review"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "reference-architecture") -> str:
    return content_hash(value, prefix=prefix)


def _text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"{field_name} must be an array")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{field_name} must contain non-empty values")
    return result


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureSource:
    source_id: str
    title: str
    uri: str
    version: str
    scope: str
    license: str
    public_aggregate: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "source_id",
            "title",
            "uri",
            "version",
            "scope",
            "license",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field)), field)
        if not self.uri.startswith("https://") or self.scope != "public_aggregate":
            raise ValidationError(
                "reference architecture sources must be HTTPS public aggregate receipts"
            )
        if not self.public_aggregate:
            raise ValidationError("reference sources require an explicit public marker")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("reference architecture sources require SHA addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: ReferenceArchitectureOperation
    family: str
    plane: ReferenceArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "operation_id",
            "capability_id",
            "family",
            "input_contract",
            "output_contract",
            "control_policy",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field)), field)
        if self.ordinal < 1 or not self.source_ids:
            raise ValidationError("reference operation ordinals and source joins are required")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("reference operation specs require SHA addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: ReferenceArchitectureOperation
    scenario: ReferenceArchitectureScenario
    context_key: str
    delegate_context_key: str
    source_ids: tuple[str, ...]
    aggregate_identifier: str
    payload: Mapping[str, Any]
    parameters: Mapping[str, Any]
    expected_state: ReferenceArchitectureState
    expected_result_state: str
    expected_issue_codes: tuple[str, ...]
    expected_counts: Mapping[str, int]
    content_address: str
    description: str = ""

    def __post_init__(self) -> None:
        for field in (
            "case_id",
            "operation_id",
            "capability_id",
            "context_key",
            "delegate_context_key",
            "aggregate_identifier",
            "expected_result_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field)), field)
        if not self.source_ids or not self.payload:
            raise ValidationError("reference cases require source IDs and payloads")
        if len(self.expected_issue_codes) != len(set(self.expected_issue_codes)):
            raise ValidationError("reference issue codes must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("reference cases require SHA addresses")
        if any(int(value) < 0 for value in self.expected_counts.values()):
            raise ValidationError("reference case counts cannot be negative")
        if self.scenario is ReferenceArchitectureScenario.POSITIVE:
            if self.expected_state is not ReferenceArchitectureState.ACCEPTED:
                raise ValidationError("reference positives must expect acceptance")
        elif self.expected_state is ReferenceArchitectureState.ACCEPTED:
            raise ValidationError("reference controls cannot expect acceptance")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[ReferenceArchitectureSource, ...]
    operations: tuple[ReferenceArchitectureOperationSpec, ...]
    cases: tuple[ReferenceArchitectureCase, ...]
    content_address: str
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("fixture_id", "version", "boundary", "context_key", "content_address"):
            require_non_empty(str(getattr(self, field)), field)
        if (
            self.version != REFERENCE_ARCHITECTURE_VERSION
            or self.boundary != REFERENCE_ARCHITECTURE_BOUNDARY
        ):
            raise ValidationError("unsupported reference architecture boundary")
        if self.context_key != REFERENCE_ARCHITECTURE_CONTEXT:
            raise ValidationError("reference architecture context is closed")
        if (
            len(self.operations) != REFERENCE_ARCHITECTURE_OPERATION_COUNT
            or len(self.cases) != REFERENCE_ARCHITECTURE_CASE_COUNT
        ):
            raise ValidationError("reference architecture requires 16 operations and 64 cases")
        if not self.sources or not self.content_address.startswith("sha256:"):
            raise ValidationError("reference architecture requires addressed sources and fixture")
        if len({item.source_id for item in self.sources}) != len(self.sources) or len(
            {item.case_id for item in self.cases}
        ) != len(self.cases):
            raise ValidationError("reference architecture IDs must be unique")

    @property
    def positive_cases(self) -> tuple[ReferenceArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is ReferenceArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[ReferenceArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not ReferenceArchitectureScenario.POSITIVE
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
    def from_mapping(cls, raw: Mapping[str, Any]) -> ReferenceArchitectureFixture:
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
            notes=_text_tuple(raw.get("notes", ()), "notes") if raw.get("notes") else (),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> ReferenceArchitectureFixture:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"reference architecture fixture not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid reference architecture JSON: {exc}") from exc
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureCheck:
    check_id: str
    kind: ReferenceArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureDataAudit:
    fixture_id: str
    checks: tuple[ReferenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureExecution:
    case_id: str
    operation: ReferenceArchitectureOperation
    scenario: ReferenceArchitectureScenario
    observed_state: ReferenceArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: Mapping[str, int]
    output_address: str
    summary: Mapping[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    expected_state: ReferenceArchitectureState
    observed_state: ReferenceArchitectureState
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
class ReferenceArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: ReferenceArchitectureState
    receipts: tuple[ReferenceArchitectureCaseReceipt, ...]
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return (
            self.state is ReferenceArchitectureState.ACCEPTED
            and all(item.passed for item in self.receipts)
            and all(item.passed for item in self.checks)
        )

    @property
    def positive_count(self) -> int:
        return sum(
            item.expected_state is ReferenceArchitectureState.ACCEPTED for item in self.receipts
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
class ReferenceArchitecturePlanNode:
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
class ReferenceArchitecturePlan:
    fixture_id: str
    nodes: tuple[ReferenceArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureReviewItem:
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
class ReferenceArchitectureReviewQueue:
    fixture_id: str
    items: tuple[ReferenceArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureLedgerEvent:
    sequence: int
    case_id: str
    operation_id: str
    input_address: str
    output_address: str
    previous_address: str
    state: ReferenceArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureLedger:
    fixture_id: str
    events: tuple[ReferenceArchitectureLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureArtifact:
    artifact_id: str
    artifact_type: str
    media_type: str
    row_count: int
    source_addresses: tuple[str, ...]
    content_address: str
    retention: str

    def __post_init__(self) -> None:
        if self.row_count < 0 or not self.content_address.startswith("sha256:"):
            raise ValidationError("reference artifacts require non-negative rows and SHA addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureRelease:
    fixture_id: str
    state: ReferenceArchitectureState
    artifacts: tuple[ReferenceArchitectureArtifact, ...]
    rollback_key: str
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str

    @property
    def published(self) -> bool:
        return self.state is ReferenceArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"published": self.published}


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureRuntimeStage:
    stage_id: str
    ordinal: int
    state: ReferenceArchitectureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureRuntime:
    run_id: str
    fixture_id: str
    state: ReferenceArchitectureState
    stages: tuple[ReferenceArchitectureRuntimeStage, ...]
    evaluation: ReferenceArchitectureEvaluation
    plan: ReferenceArchitecturePlan
    review_queue: ReferenceArchitectureReviewQueue
    ledger: ReferenceArchitectureLedger
    artifacts: tuple[ReferenceArchitectureArtifact, ...]
    release: ReferenceArchitectureRelease
    depth: ReferenceArchitectureDepthReport
    quality: ReferenceArchitectureQualityGate
    compliance: Any
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is ReferenceArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        value = jsonable(self)
        value["evaluation"] = self.evaluation.to_dict()
        value["plan"] = self.plan.to_dict()
        value["review_queue"] = self.review_queue.to_dict()
        value["ledger"] = self.ledger.to_dict()
        value["release"] = self.release.to_dict()
        value["depth"] = self.depth.to_dict()
        value["quality"] = self.quality.to_dict()
        value["compliance"] = self.compliance.to_dict()
        return value | {"accepted": self.accepted, "stage_count": len(self.stages)}


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureDepthReport:
    fixture_id: str
    source_count: int
    operation_count: int
    case_count: int
    positive_count: int
    control_count: int
    stage_count: int
    artifact_count: int
    family_count: int
    check_count: int
    state_count: int
    issue_code_count: int
    addressed_count: int
    accepted: bool
    checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceArchitectureQualityGate:
    fixture_id: str
    state: ReferenceArchitectureState
    checks: tuple[ReferenceArchitectureCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state is ReferenceArchitectureState.PUBLISHED and all(
            item.passed for item in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def _source(raw: Any) -> ReferenceArchitectureSource:
    if not isinstance(raw, Mapping):
        raise ValidationError("reference source must be an object")
    return ReferenceArchitectureSource(
        source_id=str(raw.get("source_id", "")),
        title=str(raw.get("title", "")),
        uri=str(raw.get("uri", "")),
        version=str(raw.get("version", "")),
        scope=str(raw.get("scope", "")),
        license=str(raw.get("license", "")),
        public_aggregate=bool(raw.get("public_aggregate", True)),
        content_address=str(raw.get("content_address", "")),
    )


def _operation(raw: Any) -> ReferenceArchitectureOperationSpec:
    if not isinstance(raw, Mapping):
        raise ValidationError("reference operation must be an object")
    return ReferenceArchitectureOperationSpec(
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        ordinal=int(raw.get("ordinal", 0)),
        operation=ReferenceArchitectureOperation(str(raw.get("operation", ""))),
        family=str(raw.get("family", "")),
        plane=ReferenceArchitecturePlane(str(raw.get("plane", ""))),
        input_contract=str(raw.get("input_contract", "")),
        output_contract=str(raw.get("output_contract", "")),
        dependencies=_text_tuple(raw.get("dependencies", ()), "dependencies"),
        source_ids=_text_tuple(raw.get("source_ids", ()), "source_ids"),
        control_policy=str(raw.get("control_policy", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _case(raw: Any) -> ReferenceArchitectureCase:
    if not isinstance(raw, Mapping):
        raise ValidationError("reference case must be an object")
    issue_codes = raw.get("expected_issue_codes", ())
    if (
        isinstance(issue_codes, Sequence)
        and issue_codes
        and all(isinstance(item, (list, tuple)) for item in issue_codes)
    ):
        issue_codes = [subitem for group in issue_codes for subitem in group]
    counts = raw.get("expected_counts", {})
    if (
        not isinstance(raw.get("payload", {}), Mapping)
        or not isinstance(raw.get("parameters", {}), Mapping)
        or not isinstance(counts, Mapping)
    ):
        raise ValidationError("reference case payload, parameters, and counts must be objects")
    scenario = ReferenceArchitectureScenario(str(raw.get("scenario", "")))
    context_key = str(raw.get("context_key", ""))
    delegate_context_value = raw.get("delegate_context_key")
    if delegate_context_value is None:
        delegate_context_value = (
            REFERENCE_ARCHITECTURE_CONTEXT
            if scenario is ReferenceArchitectureScenario.FOREIGN_CONTEXT
            else context_key
        )
    return ReferenceArchitectureCase(
        case_id=str(raw.get("case_id", "")),
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        operation=ReferenceArchitectureOperation(str(raw.get("operation", ""))),
        scenario=scenario,
        context_key=context_key,
        delegate_context_key=str(delegate_context_value),
        source_ids=_text_tuple(raw.get("source_ids", ()), "source_ids"),
        aggregate_identifier=str(raw.get("aggregate_identifier", "")),
        payload=dict(raw["payload"]),
        parameters=dict(raw.get("parameters", {})),
        expected_state=ReferenceArchitectureState(str(raw.get("expected_state", ""))),
        expected_result_state=str(raw.get("expected_result_state", "")),
        expected_issue_codes=_text_tuple(issue_codes, "expected_issue_codes")
        if issue_codes
        else (),
        expected_counts={str(key): int(value) for key, value in counts.items()},
        content_address=str(raw.get("content_address", "")),
        description=str(raw.get("description", "")),
    )


__all__ = [
    "REFERENCE_ARCHITECTURE_ARTIFACT_COUNT",
    "REFERENCE_ARCHITECTURE_FAMILY_COUNT",
    "REFERENCE_ARCHITECTURE_BOUNDARY",
    "REFERENCE_ARCHITECTURE_CASE_COUNT",
    "REFERENCE_ARCHITECTURE_CASES_PER_OPERATION",
    "REFERENCE_ARCHITECTURE_CONTEXT",
    "REFERENCE_ARCHITECTURE_FOREIGN_CONTEXT",
    "REFERENCE_ARCHITECTURE_OPERATION_COUNT",
    "REFERENCE_ARCHITECTURE_SOURCE_COUNT",
    "REFERENCE_ARCHITECTURE_VERSION",
    "ReferenceArchitectureArtifact",
    "ReferenceArchitectureCase",
    "ReferenceArchitectureCaseReceipt",
    "ReferenceArchitectureCheck",
    "ReferenceArchitectureCheckKind",
    "ReferenceArchitectureDataAudit",
    "ReferenceArchitectureDepthReport",
    "ReferenceArchitectureEvaluation",
    "ReferenceArchitectureExecution",
    "ReferenceArchitectureFixture",
    "ReferenceArchitectureLedger",
    "ReferenceArchitectureLedgerEvent",
    "ReferenceArchitectureOperation",
    "ReferenceArchitectureOperationSpec",
    "ReferenceArchitecturePlan",
    "ReferenceArchitecturePlanNode",
    "ReferenceArchitecturePlane",
    "ReferenceArchitectureQualityGate",
    "ReferenceArchitectureRelease",
    "ReferenceArchitectureReviewItem",
    "ReferenceArchitectureReviewQueue",
    "ReferenceArchitectureRuntime",
    "ReferenceArchitectureRuntimeStage",
    "ReferenceArchitectureScenario",
    "ReferenceArchitectureSource",
    "ReferenceArchitectureState",
    "addressed",
]

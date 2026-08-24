"""Closed contracts for the composed D05 glioma regulatory atlas.

The four existing D05 atlas families remain the typed execution authorities.
This module supplies the shared public aggregate boundary around them: source
receipts, operation joins, context policy, sanitized outcomes, review, lineage,
replay, and release artifacts.
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

ATLAS_ARCHITECTURE_VERSION = "2026.08.d05-atlas-architecture.v1"
ATLAS_ARCHITECTURE_BOUNDARY = "public_aggregate_glioma_regulatory_atlas"
ATLAS_ARCHITECTURE_CONTEXT = "GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown"
ATLAS_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown"
ATLAS_ARCHITECTURE_OPERATION_COUNT = 16
ATLAS_ARCHITECTURE_CASES_PER_OPERATION = 4
ATLAS_ARCHITECTURE_CASE_COUNT = (
    ATLAS_ARCHITECTURE_OPERATION_COUNT * ATLAS_ARCHITECTURE_CASES_PER_OPERATION
)
ATLAS_ARCHITECTURE_SOURCE_COUNT = 20
ATLAS_ARCHITECTURE_FAMILY_COUNT = 4
ATLAS_ARCHITECTURE_ARTIFACT_COUNT = 6


class AtlasArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class AtlasArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class AtlasArchitecturePlane(StrEnum):
    INGESTION = "ingestion"
    REGULATORY = "regulatory"
    MOLECULAR = "molecular"
    EVIDENCE = "evidence"
    FRONTIER = "frontier"


class AtlasArchitectureFamily(StrEnum):
    REGULATORY = "regulatory_atlas"
    MOLECULAR = "molecular_atlas"
    ALPHA_EVIDENCE = "atlas_alpha_evidence"
    FRONTIER = "frontier_atlas"


class AtlasArchitectureOperation(StrEnum):
    CCRE_TRACK_PARSE = "ccre_track_parse"
    BRAIN_CELL_PROFILE = "brain_cell_type_profile"
    ADULT_GLIO_PROFILE = "adult_glioma_profile"
    PEDIATRIC_GLIO_PROFILE = "pediatric_glioma_profile"
    IDH_MUTANT_PROFILE = "idh_mutant_state_profile"
    IDH_WILDTYPE_PROFILE = "idh_wildtype_state_profile"
    H3K27_PROFILE = "h3k27_altered_state_profile"
    HISTONE_HARMONIZATION = "histone_mark_harmonization"
    OPEN_CHROMATIN_HARMONIZATION = "open_chromatin_harmonization"
    METHYLATION_HARMONIZATION = "methylation_harmonization"
    REGULATORY_ROLE_CLASSIFICATION = "regulatory_role_classification"
    SUPER_ENHANCER_ATLAS = "super_enhancer_candidate_atlas"
    BOUNDARY_ATLAS = "insulator_boundary_atlas"
    HOTSPOT_ATLAS = "regulatory_hotspot_atlas"
    EVIDENCE_TIER = "atlas_evidence_tier_adjudication"
    SNAPSHOT_PUBLISH = "atlas_snapshot_publish"


class AtlasArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    LINEAGE = "lineage"
    REVIEW = "review"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "atlas-architecture") -> str:
    return content_hash({"prefix": prefix, "value": value})


def _text_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{name} must be a sequence")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{name} cannot contain blank values")
    return result


@dataclass(frozen=True, slots=True)
class AtlasArchitectureSource:
    source_id: str
    family: AtlasArchitectureFamily
    title: str
    uri: str
    version: str
    scope: str
    license: str
    public_aggregate: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "version",
            "scope",
            "license",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith(("https://", "http://")):
            raise ValidationError("atlas source URI must be HTTP(S)")
        if self.scope != "public_aggregate":
            raise ValidationError("atlas architecture sources must be public aggregate receipts")
        if not self.public_aggregate:
            raise ValidationError("atlas sources must carry the public aggregate marker")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("atlas source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: AtlasArchitectureOperation
    family: AtlasArchitectureFamily
    plane: AtlasArchitecturePlane
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
        if self.ordinal < 1:
            raise ValidationError("atlas operation ordinal must be positive")
        if not self.source_ids:
            raise ValidationError("atlas operation requires source joins")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: AtlasArchitectureOperation
    family: AtlasArchitectureFamily
    scenario: AtlasArchitectureScenario
    context_key: str
    delegate_context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: AtlasArchitectureState
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
        if not self.source_ids:
            raise ValidationError("atlas case requires source joins")
        if not isinstance(self.payload, dict):
            raise ValidationError("atlas case payload must be an object")
        if any(int(value) < 0 for value in self.expected_counts.values()):
            raise ValidationError("atlas expected counts cannot be negative")
        if self.scenario is AtlasArchitectureScenario.POSITIVE:
            if self.expected_state is not AtlasArchitectureState.ACCEPTED:
                raise ValidationError("positive atlas cases must be accepted at the boundary")
        elif self.expected_state is not AtlasArchitectureState.REVIEW:
            raise ValidationError("atlas controls must remain review cases")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[AtlasArchitectureSource, ...]
    operations: tuple[AtlasArchitectureOperationSpec, ...]
    cases: tuple[AtlasArchitectureCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "boundary", "context_key", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != ATLAS_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported atlas architecture version")
        if self.boundary != ATLAS_ARCHITECTURE_BOUNDARY:
            raise ValidationError("unsupported atlas architecture boundary")
        if len(self.operations) != ATLAS_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("atlas architecture requires sixteen operations")
        if len(self.cases) != ATLAS_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("atlas architecture requires sixty-four cases")
        operation_ids = {item.operation_id for item in self.operations}
        if len(operation_ids) != len(self.operations):
            raise ValidationError("atlas operation IDs must be unique")
        case_ids = {item.case_id for item in self.cases}
        if len(case_ids) != len(self.cases):
            raise ValidationError("atlas case IDs must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("atlas fixture address must be SHA-256")

    @property
    def positive_cases(self) -> tuple[AtlasArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is AtlasArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[AtlasArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is not AtlasArchitectureScenario.POSITIVE
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
    def from_mapping(cls, raw: Mapping[str, Any]) -> AtlasArchitectureFixture:
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
        expected = addressed(body, "atlas-fixture")
        supplied = str(raw.get("content_address", expected))
        if supplied != expected:
            raise ValidationError("atlas fixture content address does not verify")
        return cls(**body, content_address=supplied)

    @classmethod
    def from_file(cls, path: str | Path) -> AtlasArchitectureFixture:
        with Path(path).open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, Mapping):
            raise ValidationError("atlas architecture fixture must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureCheck:
    check_id: str
    kind: AtlasArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureDataAudit:
    fixture_id: str
    checks: tuple[AtlasArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureExecution:
    case_id: str
    operation: AtlasArchitectureOperation
    family: AtlasArchitectureFamily
    scenario: AtlasArchitectureScenario
    observed_state: AtlasArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: dict[str, int]
    output_address: str
    summary: dict[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    family: AtlasArchitectureFamily
    expected_state: AtlasArchitectureState
    observed_state: AtlasArchitectureState
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
class AtlasArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: AtlasArchitectureState
    receipts: tuple[AtlasArchitectureCaseReceipt, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is AtlasArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    @property
    def positive_count(self) -> int:
        return sum(item.expected_state is AtlasArchitectureState.ACCEPTED for item in self.receipts)

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
class AtlasArchitecturePlanNode:
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
class AtlasArchitecturePlan:
    fixture_id: str
    nodes: tuple[AtlasArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureReviewItem:
    review_id: str
    case_id: str
    operation_id: str
    scenario: AtlasArchitectureScenario
    reason_codes: tuple[str, ...]
    priority: int
    disposition: str
    next_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureReviewQueue:
    fixture_id: str
    items: tuple[AtlasArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureLedgerEvent:
    sequence: int
    case_id: str
    operation_id: str
    input_address: str
    output_address: str
    previous_address: str
    state: AtlasArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureLedger:
    fixture_id: str
    events: tuple[AtlasArchitectureLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureArtifact:
    artifact_id: str
    artifact_type: str
    media_type: str
    row_count: int
    source_addresses: tuple[str, ...]
    content_address: str
    retention: str

    def __post_init__(self) -> None:
        if self.row_count < 0 or not self.content_address.startswith("sha256:"):
            raise ValidationError("atlas artifacts require non-negative rows and SHA addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureRelease:
    fixture_id: str
    state: AtlasArchitectureState
    artifacts: tuple[AtlasArchitectureArtifact, ...]
    rollback_key: str
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    @property
    def published(self) -> bool:
        return self.state is AtlasArchitectureState.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"published": self.published}


@dataclass(frozen=True, slots=True)
class AtlasArchitectureRuntimeStage:
    stage_id: str
    ordinal: int
    state: AtlasArchitectureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureRuntime:
    run_id: str
    fixture_id: str
    state: AtlasArchitectureState
    stages: tuple[AtlasArchitectureRuntimeStage, ...]
    evaluation: AtlasArchitectureEvaluation
    plan: AtlasArchitecturePlan
    review_queue: AtlasArchitectureReviewQueue
    ledger: AtlasArchitectureLedger
    artifacts: tuple[AtlasArchitectureArtifact, ...]
    release: AtlasArchitectureRelease
    depth: AtlasArchitectureDepthReport
    quality: AtlasArchitectureQualityGate
    compliance: Any
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is AtlasArchitectureState.PUBLISHED

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
class AtlasArchitectureDepthReport:
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
class AtlasArchitectureQualityGate:
    fixture_id: str
    state: AtlasArchitectureState
    checks: tuple[AtlasArchitectureCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state is AtlasArchitectureState.PUBLISHED and all(
            item.passed for item in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


def _source(raw: Any) -> AtlasArchitectureSource:
    if not isinstance(raw, Mapping):
        raise ValidationError("atlas source must be an object")
    return AtlasArchitectureSource(
        source_id=str(raw.get("source_id", "")),
        family=AtlasArchitectureFamily(str(raw.get("family", ""))),
        title=str(raw.get("title", "")),
        uri=str(raw.get("uri", "")),
        version=str(raw.get("version", "")),
        scope=str(raw.get("scope", "")),
        license=str(raw.get("license", "")),
        public_aggregate=bool(raw.get("public_aggregate", True)),
        content_address=str(raw.get("content_address", "")),
    )


def _operation(raw: Any) -> AtlasArchitectureOperationSpec:
    if not isinstance(raw, Mapping):
        raise ValidationError("atlas operation must be an object")
    return AtlasArchitectureOperationSpec(
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        ordinal=int(raw.get("ordinal", 0)),
        operation=AtlasArchitectureOperation(str(raw.get("operation", ""))),
        family=AtlasArchitectureFamily(str(raw.get("family", ""))),
        plane=AtlasArchitecturePlane(str(raw.get("plane", ""))),
        input_contract=str(raw.get("input_contract", "")),
        output_contract=str(raw.get("output_contract", "")),
        dependencies=_text_tuple(raw.get("dependencies", ()), "dependencies"),
        source_ids=_text_tuple(raw.get("source_ids", ()), "source_ids"),
        control_policy=str(raw.get("control_policy", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _case(raw: Any) -> AtlasArchitectureCase:
    if not isinstance(raw, Mapping):
        raise ValidationError("atlas case must be an object")
    counts = raw.get("expected_counts", {})
    if not isinstance(counts, Mapping):
        raise ValidationError("atlas expected counts must be an object")
    return AtlasArchitectureCase(
        case_id=str(raw.get("case_id", "")),
        operation_id=str(raw.get("operation_id", "")),
        capability_id=str(raw.get("capability_id", "")),
        operation=AtlasArchitectureOperation(str(raw.get("operation", ""))),
        family=AtlasArchitectureFamily(str(raw.get("family", ""))),
        scenario=AtlasArchitectureScenario(str(raw.get("scenario", ""))),
        context_key=str(raw.get("context_key", "")),
        delegate_context_key=str(
            raw.get("delegate_context_key", raw.get("context_key", ""))
        ),
        source_ids=_text_tuple(raw.get("source_ids", ()), "source_ids"),
        payload=dict(raw.get("payload", {})),
        expected_state=AtlasArchitectureState(str(raw.get("expected_state", ""))),
        expected_result_state=str(raw.get("expected_result_state", "")),
        expected_issue_codes=_text_tuple(
            raw.get("expected_issue_codes", ()), "expected_issue_codes"
        ),
        expected_counts={str(key): int(value) for key, value in counts.items()},
        description=str(raw.get("description", "")),
        content_address=str(raw.get("content_address", "")),
    )


__all__ = [
    "ATLAS_ARCHITECTURE_ARTIFACT_COUNT",
    "ATLAS_ARCHITECTURE_FAMILY_COUNT",
    "ATLAS_ARCHITECTURE_BOUNDARY",
    "ATLAS_ARCHITECTURE_CASE_COUNT",
    "ATLAS_ARCHITECTURE_CASES_PER_OPERATION",
    "ATLAS_ARCHITECTURE_CONTEXT",
    "ATLAS_ARCHITECTURE_FOREIGN_CONTEXT",
    "ATLAS_ARCHITECTURE_OPERATION_COUNT",
    "ATLAS_ARCHITECTURE_SOURCE_COUNT",
    "ATLAS_ARCHITECTURE_VERSION",
    "AtlasArchitectureArtifact",
    "AtlasArchitectureCase",
    "AtlasArchitectureCaseReceipt",
    "AtlasArchitectureCheck",
    "AtlasArchitectureCheckKind",
    "AtlasArchitectureDataAudit",
    "AtlasArchitectureDepthReport",
    "AtlasArchitectureEvaluation",
    "AtlasArchitectureExecution",
    "AtlasArchitectureFamily",
    "AtlasArchitectureFixture",
    "AtlasArchitectureLedger",
    "AtlasArchitectureLedgerEvent",
    "AtlasArchitectureOperation",
    "AtlasArchitectureOperationSpec",
    "AtlasArchitecturePlane",
    "AtlasArchitecturePlan",
    "AtlasArchitecturePlanNode",
    "AtlasArchitectureQualityGate",
    "AtlasArchitectureRelease",
    "AtlasArchitectureReviewItem",
    "AtlasArchitectureReviewQueue",
    "AtlasArchitectureRuntime",
    "AtlasArchitectureRuntimeStage",
    "AtlasArchitectureScenario",
    "AtlasArchitectureSource",
    "AtlasArchitectureState",
    "addressed",
]

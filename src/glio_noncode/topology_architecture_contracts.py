"""Typed D09 aggregate contracts for three-dimensional genome topology."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

TOPOLOGY_ARCHITECTURE_VERSION = "2026.08.d09-topology-architecture.v1"
TOPOLOGY_ARCHITECTURE_BOUNDARY = "public_aggregate_3d_genome_regulatory_topology"
TOPOLOGY_ARCHITECTURE_CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"
TOPOLOGY_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|glioma|pediatric|stem_like|tumor|unknown"
TOPOLOGY_ARCHITECTURE_SOURCE_COUNT = 17
TOPOLOGY_ARCHITECTURE_OPERATION_COUNT = 16
TOPOLOGY_ARCHITECTURE_CASES_PER_OPERATION = 4
TOPOLOGY_ARCHITECTURE_CASE_COUNT = 64
TOPOLOGY_ARCHITECTURE_ARTIFACT_COUNT = 6


class TopologyArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    PUBLISHED = "published"


class TopologyArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    IDENTITY_CONFLICT = "identity_conflict"


class TopologyArchitecturePlane(StrEnum):
    CONTEXT_QC = "context_qc"
    CONTACT_INFERENCE = "contact_inference"
    TOPOLOGY_ALPHA = "topology_alpha"
    FRONTIER_RELEASE = "frontier_release"


class TopologyArchitectureFamily(StrEnum):
    CONTEXT = "topology_context_frontier"
    BETA = "topology_beta_frontier"
    ALPHA = "topology_alpha_frontier"
    FRONTIER = "topology_frontier"


class TopologyArchitectureOperation(StrEnum):
    CONTACT_IMPORT = "contact_import"
    MATRIX_QC = "matrix_qc"
    BOUNDARY_ENSEMBLE = "boundary_ensemble"
    INSULATION_DELTA = "insulation_delta"
    LOOP_STRIPE = "loop_stripe"
    PROMOTER_CAPTURE = "promoter_capture"
    ENHANCER_PROMOTER_CONTACT = "enhancer_promoter_contact"
    ACTIVITY_BY_CONTACT = "activity_by_contact"
    BOUNDARY_MOTIF = "boundary_motif"
    CTCF_COHESIN = "ctcf_cohesin"
    IDH_INSULATOR = "idh_insulator"
    SV_REWIRE = "sv_rewire"
    ECDNA_CONTACT = "ecdna_contact"
    COMPARTMENT_SWITCH = "compartment_switch"
    TOPOLOGY_TRANSPORT = "topology_transport"
    EVIDENCE_PUBLICATION = "evidence_publication"


class TopologyArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    CONTEXT = "context"
    IDENTITY = "identity"
    CONTROL = "control"
    REPLAY = "replay"
    RELEASE = "release"
    INVARIANT = "invariant"


def addressed(value: Any, prefix: str = "topology-architecture") -> str:
    return content_hash({"prefix": prefix, "value": value})


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{name} must be a sequence")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise ValidationError(f"{name} cannot contain blank values")
    return result


@dataclass(frozen=True, slots=True)
class TopologyArchitectureSource:
    source_id: str
    family: TopologyArchitectureFamily
    title: str
    uri: str
    version: str
    scope: str
    license: str
    content_address: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "title",
            "uri",
            "version",
            "scope",
            "license",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.uri.startswith(("https://", "http://")):
            raise ValidationError("D09 source URI must be HTTP(S)")
        if self.scope != "public_aggregate":
            raise ValidationError("D09 sources must be public aggregate receipts")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D09 source address must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: TopologyArchitectureOperation
    family: TopologyArchitectureFamily
    plane: TopologyArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    control_policy: str
    content_address: str

    def __post_init__(self) -> None:
        for field_name in (
            "operation_id",
            "capability_id",
            "input_contract",
            "output_contract",
            "control_policy",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.ordinal < 1 or not self.source_ids:
            raise ValidationError("D09 operations require an ordinal and source joins")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    operation: TopologyArchitectureOperation
    family: TopologyArchitectureFamily
    plane: TopologyArchitecturePlane
    scenario: TopologyArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: TopologyArchitectureState
    expected_result_state: str
    expected_issue_codes: tuple[str, ...]
    expected_counts: dict[str, int]
    description: str
    content_address: str

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "operation_id",
            "capability_id",
            "context_key",
            "expected_result_state",
            "description",
            "content_address",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.source_ids or not isinstance(self.payload, dict):
            raise ValidationError("D09 cases require source joins and object payloads")
        if any(int(value) < 0 for value in self.expected_counts.values()):
            raise ValidationError("D09 expected counts cannot be negative")
        if (
            self.scenario is TopologyArchitectureScenario.POSITIVE
            and self.expected_state is not TopologyArchitectureState.ACCEPTED
        ):
            raise ValidationError("D09 positive cases must be accepted")
        if (
            self.scenario is not TopologyArchitectureScenario.POSITIVE
            and self.expected_state is not TopologyArchitectureState.REVIEW
        ):
            raise ValidationError("D09 controls must be review-held")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[TopologyArchitectureSource, ...]
    operations: tuple[TopologyArchitectureOperationSpec, ...]
    cases: tuple[TopologyArchitectureCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.version != TOPOLOGY_ARCHITECTURE_VERSION:
            raise ValidationError("unsupported D09 topology architecture version")
        if self.boundary != TOPOLOGY_ARCHITECTURE_BOUNDARY:
            raise ValidationError("D09 boundary does not match the public aggregate contract")
        if self.context_key != TOPOLOGY_ARCHITECTURE_CONTEXT:
            raise ValidationError("D09 context does not match the aggregate contract")
        if len(self.sources) != TOPOLOGY_ARCHITECTURE_SOURCE_COUNT:
            raise ValidationError("D09 fixture requires seventeen source receipts")
        if len(self.operations) != TOPOLOGY_ARCHITECTURE_OPERATION_COUNT:
            raise ValidationError("D09 fixture requires sixteen operation specifications")
        if len(self.cases) != TOPOLOGY_ARCHITECTURE_CASE_COUNT:
            raise ValidationError("D09 fixture requires sixty-four cases")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValidationError("D09 source IDs must be unique")
        if len({item.operation_id for item in self.operations}) != len(self.operations):
            raise ValidationError("D09 operation IDs must be unique")
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValidationError("D09 case IDs must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("D09 fixture requires a content address")

    @property
    def positive_cases(self) -> tuple[TopologyArchitectureCase, ...]:
        return tuple(
            item for item in self.cases if item.scenario is TopologyArchitectureScenario.POSITIVE
        )

    @property
    def control_cases(self) -> tuple[TopologyArchitectureCase, ...]:
        return tuple(
            item
            for item in self.cases
            if item.scenario is not TopologyArchitectureScenario.POSITIVE
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
    def from_mapping(cls, raw: Mapping[str, Any]) -> TopologyArchitectureFixture:
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
        expected = addressed(body, "topology-fixture")
        supplied = str(raw.get("content_address", expected))
        if supplied != expected:
            raise ValidationError("D09 fixture content address does not match mapping")
        return cls(**body, content_address=supplied)

    @classmethod
    def from_file(cls, path: str | Path) -> TopologyArchitectureFixture:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValidationError("D09 fixture JSON must be an object")
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureCheck:
    check_id: str
    kind: TopologyArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureDataAudit:
    fixture_id: str
    checks: tuple[TopologyArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


@dataclass(frozen=True, slots=True)
class TopologyArchitectureExecution:
    case_id: str
    operation: TopologyArchitectureOperation
    family: TopologyArchitectureFamily
    scenario: TopologyArchitectureScenario
    observed_state: TopologyArchitectureState
    observed_result_state: str
    issue_codes: tuple[str, ...]
    counts: dict[str, int]
    output_address: str
    summary: dict[str, Any]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureCaseReceipt:
    case_id: str
    operation_id: str
    family: TopologyArchitectureFamily
    expected_state: TopologyArchitectureState
    observed_state: TopologyArchitectureState
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
class TopologyArchitectureEvaluation:
    fixture_id: str
    context_key: str
    state: TopologyArchitectureState
    executions: tuple[TopologyArchitectureExecution, ...]
    receipts: tuple[TopologyArchitectureCaseReceipt, ...]
    checks: tuple[TopologyArchitectureCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is TopologyArchitectureState.ACCEPTED and all(
            item.passed for item in (*self.receipts, *self.checks)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": sum(
                item.expected_state is TopologyArchitectureState.ACCEPTED for item in self.receipts
            ),
            "control_count": sum(
                item.expected_state is TopologyArchitectureState.REVIEW for item in self.receipts
            ),
        }


@dataclass(frozen=True, slots=True)
class TopologyArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    family: TopologyArchitectureFamily
    plane: TopologyArchitecturePlane
    ready: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitecturePlan:
    fixture_id: str
    nodes: tuple[TopologyArchitecturePlanNode, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureReviewItem:
    case_id: str
    operation_id: str
    scenario: TopologyArchitectureScenario
    priority: str
    blocking: bool
    reason: str
    required_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureReviewQueue:
    fixture_id: str
    items: tuple[TopologyArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureLedgerEvent:
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
class TopologyArchitectureLedger:
    fixture_id: str
    events: tuple[TopologyArchitectureLedgerEvent, ...]
    state_counts: Mapping[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureArtifact:
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
class TopologyArchitectureRelease:
    release_id: str
    fixture_id: str
    state: TopologyArchitectureState
    artifact_ids: tuple[str, ...]
    provenance_address: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyArchitectureRuntimeStage:
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
class TopologyArchitectureRuntime:
    fixture: TopologyArchitectureFixture
    audit: TopologyArchitectureDataAudit
    plan: TopologyArchitecturePlan
    evaluation: TopologyArchitectureEvaluation
    review_queue: TopologyArchitectureReviewQueue
    ledger: TopologyArchitectureLedger
    artifacts: tuple[TopologyArchitectureArtifact, ...]
    release: TopologyArchitectureRelease
    stages: tuple[TopologyArchitectureRuntimeStage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class TopologyArchitectureDepthReport:
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
class TopologyArchitectureQualityGate:
    fixture_id: str
    checks: tuple[TopologyArchitectureCheck, ...]
    release: TopologyArchitectureRelease
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": [item.check_id for item in self.checks if not item.passed]
        }


def _source(raw: Mapping[str, Any]) -> TopologyArchitectureSource:
    body = {
        "source_id": str(raw.get("source_id", "")),
        "family": TopologyArchitectureFamily(str(raw.get("family", ""))),
        "title": str(raw.get("title", raw.get("source_id", ""))),
        "uri": str(raw.get("uri", "")),
        "version": str(raw.get("version", raw.get("release", "public"))),
        "scope": str(raw.get("scope", "public_aggregate")),
        "license": "public source receipt",
    }
    return TopologyArchitectureSource(**body, content_address=addressed(body, "topology-source"))


def _operation(raw: Mapping[str, Any]) -> TopologyArchitectureOperationSpec:
    body = {
        "operation_id": str(raw.get("operation_id", "")),
        "capability_id": str(raw.get("capability_id", "")),
        "ordinal": int(raw.get("ordinal", 0)),
        "operation": TopologyArchitectureOperation(str(raw.get("operation", ""))),
        "family": TopologyArchitectureFamily(str(raw.get("family", ""))),
        "plane": TopologyArchitecturePlane(str(raw.get("plane", ""))),
        "input_contract": str(raw.get("input_contract", "")),
        "output_contract": str(raw.get("output_contract", "")),
        "dependencies": _strings(raw.get("dependencies", ()), "dependencies")
        if raw.get("dependencies", ())
        else (),
        "source_ids": _strings(raw.get("source_ids", ()), "source_ids"),
        "control_policy": str(raw.get("control_policy", "")),
    }
    return TopologyArchitectureOperationSpec(
        **body, content_address=addressed(body, "topology-operation")
    )


def _case(raw: Mapping[str, Any]) -> TopologyArchitectureCase:
    body = {
        "case_id": str(raw.get("case_id", "")),
        "operation_id": str(raw.get("operation_id", "")),
        "capability_id": str(raw.get("capability_id", "")),
        "operation": TopologyArchitectureOperation(str(raw.get("operation", ""))),
        "family": TopologyArchitectureFamily(str(raw.get("family", ""))),
        "plane": TopologyArchitecturePlane(str(raw.get("plane", ""))),
        "scenario": TopologyArchitectureScenario(str(raw.get("scenario", ""))),
        "context_key": str(raw.get("context_key", "")),
        "source_ids": _strings(raw.get("source_ids", ()), "source_ids"),
        "payload": dict(raw.get("payload", {})),
        "expected_state": TopologyArchitectureState(str(raw.get("expected_state", ""))),
        "expected_result_state": str(raw.get("expected_result_state", "")),
        "expected_issue_codes": _strings(
            raw.get("expected_issue_codes", ()), "expected_issue_codes"
        )
        if raw.get("expected_issue_codes", ())
        else (),
        "expected_counts": {
            str(key): int(value) for key, value in dict(raw.get("expected_counts", {})).items()
        },
        "description": str(raw.get("description", "")),
    }
    return TopologyArchitectureCase(**body, content_address=addressed(body, "topology-case"))


__all__ = [
    "TOPOLOGY_ARCHITECTURE_ARTIFACT_COUNT",
    "TOPOLOGY_ARCHITECTURE_BOUNDARY",
    "TOPOLOGY_ARCHITECTURE_CASE_COUNT",
    "TOPOLOGY_ARCHITECTURE_CASES_PER_OPERATION",
    "TOPOLOGY_ARCHITECTURE_CONTEXT",
    "TOPOLOGY_ARCHITECTURE_FOREIGN_CONTEXT",
    "TOPOLOGY_ARCHITECTURE_OPERATION_COUNT",
    "TOPOLOGY_ARCHITECTURE_SOURCE_COUNT",
    "TOPOLOGY_ARCHITECTURE_VERSION",
    "TopologyArchitectureArtifact",
    "TopologyArchitectureCase",
    "TopologyArchitectureCaseReceipt",
    "TopologyArchitectureCheck",
    "TopologyArchitectureCheckKind",
    "TopologyArchitectureDataAudit",
    "TopologyArchitectureDepthReport",
    "TopologyArchitectureEvaluation",
    "TopologyArchitectureExecution",
    "TopologyArchitectureFamily",
    "TopologyArchitectureFixture",
    "TopologyArchitectureLedger",
    "TopologyArchitectureLedgerEvent",
    "TopologyArchitectureOperation",
    "TopologyArchitectureOperationSpec",
    "TopologyArchitecturePlane",
    "TopologyArchitecturePlan",
    "TopologyArchitecturePlanNode",
    "TopologyArchitectureQualityGate",
    "TopologyArchitectureRelease",
    "TopologyArchitectureReviewItem",
    "TopologyArchitectureReviewQueue",
    "TopologyArchitectureRuntime",
    "TopologyArchitectureRuntimeStage",
    "TopologyArchitectureScenario",
    "TopologyArchitectureSource",
    "TopologyArchitectureState",
    "addressed",
]

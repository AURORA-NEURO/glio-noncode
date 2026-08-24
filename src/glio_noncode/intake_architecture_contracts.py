"""Closed contracts for the D01 variant identity and intake architecture.

The architecture is a deterministic public-aggregate boundary around the
existing intake, normalization, and identity primitives.  It records source
scope, parsing decisions, unresolved states, and release receipts without
storing subject-level material or making biological or clinical claims.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


INTAKE_ARCHITECTURE_VERSION = "2026.08.intake-architecture.v1"
INTAKE_ARCHITECTURE_BOUNDARY = "public_aggregate_variant_identity_and_intake"
INTAKE_ARCHITECTURE_CONTEXT = "GRCh38|glioma|adult|aggregate|public_reference|pre_treatment"
INTAKE_ARCHITECTURE_FOREIGN_CONTEXT = "GRCh38|glioma|adult|aggregate|public_reference|post_treatment"
INTAKE_ARCHITECTURE_OPERATION_COUNT = 16
INTAKE_ARCHITECTURE_CASES_PER_OPERATION = 4
INTAKE_ARCHITECTURE_CASE_COUNT = (
    INTAKE_ARCHITECTURE_OPERATION_COUNT * INTAKE_ARCHITECTURE_CASES_PER_OPERATION
)
INTAKE_ARCHITECTURE_PLANE_COUNT = 7
INTAKE_ARCHITECTURE_STAGE_COUNT = 24
INTAKE_ARCHITECTURE_QUALITY_CHECK_COUNT = 24
INTAKE_ARCHITECTURE_EVALUATION_CHECKS_PER_CASE = 7
INTAKE_ARCHITECTURE_EVALUATION_GLOBAL_CHECK_COUNT = 10
INTAKE_ARCHITECTURE_EVALUATION_CHECK_COUNT = (
    INTAKE_ARCHITECTURE_CASE_COUNT * INTAKE_ARCHITECTURE_EVALUATION_CHECKS_PER_CASE
    + INTAKE_ARCHITECTURE_EVALUATION_GLOBAL_CHECK_COUNT
)


class IntakeArchitectureState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    ABSTAINED = "abstained"


class IntakeArchitectureScenario(StrEnum):
    POSITIVE = "positive"
    FOREIGN_CONTEXT = "foreign_context"
    MALFORMED_INPUT = "malformed_input"
    DUPLICATE_IDENTITY = "duplicate_identity"


class IntakeArchitecturePlane(StrEnum):
    INGESTION = "ingestion"
    PARSING = "parsing"
    NORMALIZATION = "normalization"
    IDENTITY = "identity"
    POLICY = "policy"
    PROVENANCE = "provenance"
    RELEASE = "release"


class IntakeArchitectureOperation(StrEnum):
    CASE_MANIFEST_INGESTION = "case_manifest_ingestion"
    VCF_BCF_GVCF_PARSING = "vcf_bcf_gvcf_parsing"
    REGULATORY_TRACK_PARSING = "regulatory_track_parsing"
    VRS_NORMALIZATION = "vrs_normalization"
    CAT_VRS_NORMALIZATION = "cat_vrs_normalization"
    VA_SPEC_ENVELOPE = "va_spec_envelope"
    MULTIALLELIC_DECOMPOSITION = "multiallelic_decomposition"
    REPEAT_AWARE_NORMALIZATION = "repeat_aware_normalization"
    VARIANT_EQUIVALENCE = "variant_equivalence"
    DUPLICATE_ALIAS_RECONCILIATION = "duplicate_alias_reconciliation"
    BATCH_SAMPLE_IDENTITY = "batch_sample_identity"
    CHAIN_OF_CUSTODY = "chain_of_custody"
    CONSENT_POLICY = "consent_policy"
    INPUT_QUARANTINE = "input_quarantine"
    COMPLETENESS_SCORING = "completeness_scoring"
    REPRODUCIBLE_BUNDLE = "reproducible_bundle"


class IntakeArchitectureCheckKind(StrEnum):
    FIXTURE = "fixture"
    SOURCE = "source"
    OPERATION = "operation"
    PARSING = "parsing"
    NORMALIZATION = "normalization"
    IDENTITY = "identity"
    POLICY = "policy"
    PROVENANCE = "provenance"
    RELEASE = "release"
    INTEGRITY = "integrity"


def addressed(value: Any, prefix: str = "intake-architecture") -> str:
    return content_hash(value, prefix=prefix)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureSource:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "scope", "version", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValueError("intake sources require HTTPS")
        if self.scope != "public_aggregate":
            raise ValueError("intake sources are public aggregate only")
        if ":" not in self.content_address:
            raise ValueError("intake sources require content addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureOperationSpec:
    operation_id: str
    capability_id: str
    ordinal: int
    operation: IntakeArchitectureOperation
    plane: IntakeArchitecturePlane
    input_contract: str
    output_contract: str
    dependencies: tuple[str, ...]
    source_ids: tuple[str, ...]
    review_on_control: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "operation_id",
            "capability_id",
            "input_contract",
            "output_contract",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.ordinal < 1 or not self.source_ids:
            raise ValueError("intake operation ordinals and source joins are required")
        if ":" not in self.content_address:
            raise ValueError("intake operation specs require content addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureCase:
    case_id: str
    operation_id: str
    capability_id: str
    scenario: IntakeArchitectureScenario
    context_key: str
    source_ids: tuple[str, ...]
    public_identifier: str
    payload: Mapping[str, Any]
    expected_state: IntakeArchitectureState
    expected_issue_codes: tuple[str, ...]
    content_address: str
    delegate_context_key: str = INTAKE_ARCHITECTURE_CONTEXT

    def __post_init__(self) -> None:
        for name in (
            "case_id",
            "operation_id",
            "capability_id",
            "context_key",
            "public_identifier",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids or not self.payload:
            raise ValueError("intake cases require source joins and public payloads")
        if self.scenario is IntakeArchitectureScenario.POSITIVE:
            if self.expected_state is not IntakeArchitectureState.ACCEPTED:
                raise ValueError("positive intake cases must expect acceptance")
            if self.expected_issue_codes:
                raise ValueError("positive intake cases cannot carry issue codes")
        elif self.expected_state is IntakeArchitectureState.ACCEPTED:
            raise ValueError("intake controls must not expect acceptance")
        if ":" not in self.content_address:
            raise ValueError("intake cases require content addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureFixture:
    fixture_id: str
    version: str
    boundary: str
    context_key: str
    sources: tuple[IntakeArchitectureSource, ...]
    operations: tuple[IntakeArchitectureOperationSpec, ...]
    cases: tuple[IntakeArchitectureCase, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("fixture_id", "version", "boundary", "context_key", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != INTAKE_ARCHITECTURE_VERSION:
            raise ValueError("unsupported intake architecture fixture version")
        if self.boundary != INTAKE_ARCHITECTURE_BOUNDARY:
            raise ValueError("intake architecture boundary is closed")
        if len(self.operations) != INTAKE_ARCHITECTURE_OPERATION_COUNT:
            raise ValueError("intake fixture requires sixteen operation specs")
        if len(self.cases) != INTAKE_ARCHITECTURE_CASE_COUNT:
            raise ValueError("intake fixture requires four cases per operation")
        if not self.sources or ":" not in self.content_address:
            raise ValueError("intake fixture requires public sources and an address")

    @property
    def positive_cases(self) -> tuple[IntakeArchitectureCase, ...]:
        return tuple(item for item in self.cases if item.scenario is IntakeArchitectureScenario.POSITIVE)

    @property
    def control_cases(self) -> tuple[IntakeArchitectureCase, ...]:
        return tuple(item for item in self.cases if item.scenario is not IntakeArchitectureScenario.POSITIVE)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureDataCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureDataAudit:
    fixture_id: str
    checks: tuple[IntakeArchitectureDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureParseReceipt:
    case_id: str
    input_format: str
    input_address: str
    record_count: int
    accepted_count: int
    deferred_count: int
    issue_codes: tuple[str, ...]
    state: IntakeArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureNormalizationReceipt:
    case_id: str
    normalizer: str
    input_address: str
    candidate_count: int
    selected_identifier: str | None
    state: IntakeArchitectureState
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureIdentityReceipt:
    case_id: str
    resolver: str
    record_count: int
    matched_record_count: int
    equivalence_key: str | None
    aliases: tuple[str, ...]
    state: IntakeArchitectureState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureOperationResult:
    case_id: str
    operation_id: str
    capability_id: str
    scenario: IntakeArchitectureScenario
    expected_state: IntakeArchitectureState
    observed_state: IntakeArchitectureState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    receipt_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureEvaluationCheck:
    """One independently addressable check on an evaluated intake case."""

    check_id: str
    case_id: str
    kind: IntakeArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureEvaluation:
    fixture_id: str
    results: tuple[IntakeArchitectureOperationResult, ...]
    passed_cases: int
    failed_cases: int
    accepted: bool
    content_address: str
    checks: tuple[IntakeArchitectureEvaluationCheck, ...] = ()

    @property
    def check_count(self) -> int:
        return len(self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitecturePlanNode:
    operation_id: str
    ordinal: int
    dependencies: tuple[str, ...]
    contract: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitecturePlan:
    plan_id: str
    nodes: tuple[IntakeArchitecturePlanNode, ...]
    accepted: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureReviewItem:
    review_id: str
    case_id: str
    operation_id: str
    priority: int
    issue_codes: tuple[str, ...]
    route: str
    state: IntakeArchitectureState
    content_address: str

    def __post_init__(self) -> None:
        if self.priority < 1 or self.state is IntakeArchitectureState.ACCEPTED:
            raise ValueError("intake review items must be prioritized held work")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureReviewQueue:
    queue_id: str
    items: tuple[IntakeArchitectureReviewItem, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureLedgerEvent:
    event_id: str
    ordinal: int
    case_id: str
    event_type: str
    state: IntakeArchitectureState
    previous_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureLedger:
    ledger_id: str
    events: tuple[IntakeArchitectureLedgerEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureBundleArtifact:
    artifact_id: str
    artifact_kind: str
    digest: str
    offline_capable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureRelease:
    release_id: str
    version: str
    state: IntakeArchitectureState
    artifact_addresses: tuple[str, ...]
    blockers: tuple[str, ...]
    rollback_version: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureRuntimeStage:
    stage_id: str
    ordinal: int
    state: IntakeArchitectureState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureRuntime:
    run_id: str
    fixture_id: str
    stages: tuple[IntakeArchitectureRuntimeStage, ...]
    state: IntakeArchitectureState
    evaluation: IntakeArchitectureEvaluation
    plan: IntakeArchitecturePlan
    review_queue: IntakeArchitectureReviewQueue
    ledger: IntakeArchitectureLedger
    artifacts: tuple[IntakeArchitectureBundleArtifact, ...]
    release: IntakeArchitectureRelease
    content_address: str
    compliance: Any = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureQualityCheck:
    check_id: str
    kind: IntakeArchitectureCheckKind
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureQualityReport:
    fixture_id: str
    checks: tuple[IntakeArchitectureQualityCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureFailureProbe:
    probe_id: str
    expected_state: IntakeArchitectureState
    observed_state: IntakeArchitectureState
    passed: bool
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureFailureReport:
    probes: tuple[IntakeArchitectureFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureValidationCell:
    cell_id: str
    plane: IntakeArchitecturePlane
    operation_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureValidationMatrix:
    matrix_id: str
    cells: tuple[IntakeArchitectureValidationCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureSchemaField:
    field_id: str
    type_name: str
    required: bool
    privacy_scope: str
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureSchemaManifest:
    schema_id: str
    version: str
    fields: tuple[IntakeArchitectureSchemaField, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeArchitectureDepthReport:
    fixture_id: str
    operation_count: int
    case_count: int
    source_count: int
    stage_count: int
    receipt_count: int
    addressed_output_count: int
    accepted: bool
    checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [name for name in globals() if name.startswith("INTAKE_ARCHITECTURE_")] + [
    "IntakeArchitectureState",
    "IntakeArchitectureScenario",
    "IntakeArchitecturePlane",
    "IntakeArchitectureOperation",
    "IntakeArchitectureCheckKind",
    "IntakeArchitectureSource",
    "IntakeArchitectureOperationSpec",
    "IntakeArchitectureCase",
    "IntakeArchitectureFixture",
    "IntakeArchitectureDataCheck",
    "IntakeArchitectureDataAudit",
    "IntakeArchitectureParseReceipt",
    "IntakeArchitectureNormalizationReceipt",
    "IntakeArchitectureIdentityReceipt",
    "IntakeArchitectureOperationResult",
    "IntakeArchitectureEvaluationCheck",
    "IntakeArchitectureEvaluation",
    "IntakeArchitecturePlanNode",
    "IntakeArchitecturePlan",
    "IntakeArchitectureReviewItem",
    "IntakeArchitectureReviewQueue",
    "IntakeArchitectureLedgerEvent",
    "IntakeArchitectureLedger",
    "IntakeArchitectureBundleArtifact",
    "IntakeArchitectureRelease",
    "IntakeArchitectureRuntimeStage",
    "IntakeArchitectureRuntime",
    "IntakeArchitectureQualityCheck",
    "IntakeArchitectureQualityReport",
    "IntakeArchitectureFailureProbe",
    "IntakeArchitectureFailureReport",
    "IntakeArchitectureValidationCell",
    "IntakeArchitectureValidationMatrix",
    "IntakeArchitectureSchemaField",
    "IntakeArchitectureSchemaManifest",
    "IntakeArchitectureDepthReport",
    "addressed",
]

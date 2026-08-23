"""Typed contracts for the repository-wide module fabric.

The module fabric is a release-time integration boundary.  It does not infer
scientific results and it does not replace a domain frontier.  It answers a
narrow, testable question: can every capability declared by the product
ledger be resolved to the implementation and test surfaces that the ledger
claims, while keeping public aggregate controls visible?

The contracts deliberately omit private subject fields and execution
payloads.  A fixture records public aggregate module evidence, exact domain
identity, expected control state, and content addresses.  Every derived
receipt is therefore replayable without copying a raw domain payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty


MODULE_FABRIC_VERSION = "2026.08.module-fabric.v1"
MODULE_FABRIC_BOUNDARY = "public_aggregate_module_integration"
MODULE_FABRIC_CONTEXT_KEY = (
    "GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment"
)
MODULE_FABRIC_FOREIGN_CONTEXT = (
    "GRCh38|glioma|adult|stem_like|tumor_margin|post_treatment"
)
FABRIC_CONTEXT_KEY = MODULE_FABRIC_CONTEXT_KEY
FABRIC_FOREIGN_CONTEXT = MODULE_FABRIC_FOREIGN_CONTEXT
MODULE_FABRIC_DOMAIN_IDS = tuple(f"D{index:02d}" for index in range(1, 17))
MODULE_FABRIC_DOMAIN_NAMES = {
    "D01": "Variant Identity & Intake",
    "D02": "Structural Variation, Copy Number & Haplotype",
    "D03": "Specimen, Origin & Lineage",
    "D04": "Reference & Annotation Governance",
    "D05": "Glioma Regulatory Atlas",
    "D06": "Sequence Grammar & Variant Effect",
    "D07": "Chromatin, Accessibility & Methylation",
    "D08": "Cell State, Disease Class & Territory",
    "D09": "3D Genome & Regulatory Topology",
    "D10": "Variant-Element-Gene Linking",
    "D11": "Causal Chain & Regulatory Driver Inference",
    "D12": "Cohort, Clonal & Longitudinal Discovery",
    "D13": "Functional Validation & Experiment Design",
    "D14": "Evidence Graph, Review & Reclassification",
    "D15": "Research Workbench & Collaboration",
    "D16": "Agentic Platform, Quality & Deployment",
}


class FabricRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class FabricState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    ABSTAINED = "abstained"
    REJECTED = "rejected"


class FabricReferenceState(StrEnum):
    RESOLVED = "resolved"
    FAILED = "failed"


class FabricReferenceKind(StrEnum):
    IMPLEMENTATION = "implementation"
    TEST = "test"


class FabricCheckPlane(StrEnum):
    IDENTITY = "identity"
    PUBLIC_BOUNDARY = "public_boundary"
    REFERENCE_RESOLUTION = "reference_resolution"
    TEST_SURFACE = "test_surface"
    DOMAIN_CLOSURE = "domain_closure"
    CONTROL = "control"
    INTEGRITY = "integrity"
    REPLAY = "replay"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class FabricSourceReceipt:
    """A public HTTPS source receipt used to bind aggregate fixture rows."""

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
            raise ValueError("module fabric source receipts require HTTPS")
        if self.scope != "public_aggregate":
            raise ValueError("module fabric sources must be public aggregate receipts")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("module fabric source receipts require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricRecord:
    """One positive or control row in the module-fabric fixture."""

    record_id: str
    domain_id: str
    capability_id: str
    role: FabricRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: FabricState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "domain_id",
            "capability_id",
            "context_key",
            "notes",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.domain_id not in MODULE_FABRIC_DOMAIN_IDS:
            raise ValueError(f"unknown module-fabric domain: {self.domain_id}")
        if not self.capability_id.startswith(f"GNC-{self.domain_id}-C"):
            raise ValueError("capability_id does not belong to record domain")
        if not self.source_ids:
            raise ValueError("module-fabric records require source joins")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("module-fabric records require SHA-256 addresses")
        if self.role is FabricRole.POSITIVE and self.expected_state is not FabricState.ACCEPTED:
            raise ValueError("positive module-fabric rows must expect accepted state")
        if self.role is FabricRole.CONTROL and self.expected_state is FabricState.ACCEPTED:
            raise ValueError("control module-fabric rows must retain a non-accepted state")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricFixture:
    """Content-addressed public aggregate module-fabric fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[FabricSourceReceipt, ...]
    records: tuple[FabricRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[FabricRecord, ...]:
        return tuple(item for item in self.records if item.role is FabricRole.POSITIVE)

    @property
    def control_records(self) -> tuple[FabricRecord, ...]:
        return tuple(item for item in self.records if item.role is FabricRole.CONTROL)

    @property
    def domain_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.domain_id for item in self.records))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReferenceReceipt:
    """Resolution receipt for one declared implementation or test reference."""

    reference: str
    kind: FabricReferenceKind
    module_name: str
    symbol_name: str | None
    state: FabricReferenceState
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.reference, "reference")
        require_non_empty(self.module_name, "module_name")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith("sha256:"):
            raise ValueError("reference receipts require SHA-256 addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricOperationResult:
    """Sanitized result of resolving one capability record."""

    state: FabricState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    implementation_receipts: tuple[FabricReferenceReceipt, ...]
    test_receipts: tuple[FabricReferenceReceipt, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricExecution:
    """Expected-versus-observed receipt for one fixture row."""

    record_id: str
    domain_id: str
    capability_id: str
    role: FabricRole
    expected_state: FabricState
    observed_state: FabricState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    implementation_receipts: tuple[FabricReferenceReceipt, ...]
    test_receipts: tuple[FabricReferenceReceipt, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricCheck:
    """Named assertion retained in the evaluation report."""

    check_id: str
    record_id: str
    plane: FabricCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricEvaluation:
    """Deterministic evaluation of all fixture records and checks."""

    fixture_id: str
    executions: tuple[FabricExecution, ...]
    checks: tuple[FabricCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricMetrics:
    """Conserved counts for domains, roles, states, and references."""

    fixture_id: str
    record_count: int
    domain_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    review_count: int
    abstained_count: int
    rejected_count: int
    implementation_reference_count: int
    test_reference_count: int
    resolved_reference_count: int
    failed_reference_count: int
    by_domain: Mapping[str, Mapping[str, int]]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricDepthAudit:
    checks: tuple[FabricDepthCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricLineageNode:
    node_id: str
    node_kind: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricLineageEdge:
    source_id: str
    target_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricLineage:
    nodes: tuple[FabricLineageNode, ...]
    edges: tuple[FabricLineageEdge, ...]
    accepted: bool
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReplayCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReplayReport:
    fixture_id: str
    checks: tuple[FabricReplayCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricQualityReport:
    fixture_id: str
    checks: tuple[FabricQualityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReleaseArtifact:
    artifact_id: str
    artifact_kind: str
    content_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricReleaseManifest:
    release_id: str
    fixture_id: str
    state: FabricState
    artifacts: tuple[FabricReleaseArtifact, ...]
    blockers: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricRuntimeStage:
    stage_id: str
    ordinal: int
    state: FabricState
    input_address: str
    output_address: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricRuntimeReport:
    run_id: str
    stages: tuple[FabricRuntimeStage, ...]
    state: FabricState
    evaluation: FabricEvaluation
    metrics: FabricMetrics
    depth: FabricDepthAudit
    lineage: FabricLineage
    replay: FabricReplayReport
    quality: FabricQualityReport
    release: FabricReleaseManifest
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricFailureProbe:
    probe_id: str
    expected_state: FabricState
    observed_state: FabricState
    issue_codes: tuple[str, ...]
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricFailureReport:
    probes: tuple[FabricFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def make_addressed(value: Mapping[str, Any], *, prefix: str = "sha256") -> str:
    """Return the canonical address used by fabric receipts."""

    return content_hash(dict(value), prefix=prefix)


def make_fabric_check(
    check_id: str,
    record_id: str,
    plane: FabricCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricCheck:
    body = {
        "check_id": check_id,
        "record_id": record_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricCheck(**body, content_address=content_hash(body))


def make_depth_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricDepthCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricDepthCheck(**body, content_address=content_hash(body))


def make_quality_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricQualityCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricQualityCheck(**body, content_address=content_hash(body))


def make_replay_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricReplayCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricReplayCheck(**body, content_address=content_hash(body))


__all__ = [
    "FABRIC_CONTEXT_KEY",
    "FABRIC_FOREIGN_CONTEXT",
    "MODULE_FABRIC_BOUNDARY",
    "MODULE_FABRIC_CONTEXT_KEY",
    "MODULE_FABRIC_DOMAIN_IDS",
    "MODULE_FABRIC_DOMAIN_NAMES",
    "MODULE_FABRIC_FOREIGN_CONTEXT",
    "MODULE_FABRIC_VERSION",
    "FabricCheck",
    "FabricCheckPlane",
    "FabricDepthAudit",
    "FabricDepthCheck",
    "FabricEvaluation",
    "FabricExecution",
    "FabricFailureProbe",
    "FabricFailureReport",
    "FabricFixture",
    "FabricLineage",
    "FabricLineageEdge",
    "FabricLineageNode",
    "FabricMetrics",
    "FabricOperationResult",
    "FabricQualityCheck",
    "FabricQualityReport",
    "FabricRecord",
    "FabricReferenceKind",
    "FabricReferenceReceipt",
    "FabricReferenceState",
    "FabricReleaseArtifact",
    "FabricReleaseManifest",
    "FabricReplayCheck",
    "FabricReplayReport",
    "FabricRole",
    "FabricRuntimeReport",
    "FabricRuntimeStage",
    "FabricSourceReceipt",
    "FabricState",
    "make_addressed",
    "make_depth_check",
    "make_fabric_check",
    "make_quality_check",
    "make_replay_check",
]

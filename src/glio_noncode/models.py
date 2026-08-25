"""Typed domain objects for cases, evidence, hypotheses, review, and release."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty, utc_now


class ValueEnum(str, Enum):
    """Enum base whose values are stable strings in serialized contracts."""


class VariantKind(ValueEnum):
    SNV = "snv"
    INDEL = "indel"
    CNV = "cnv"
    BREAKEND = "breakend"
    HAPLOTYPE = "haplotype"


class VariantOrigin(ValueEnum):
    GERMLINE = "germline"
    SOMATIC = "somatic"
    MOSAIC = "mosaic"
    CLONAL = "clonal"
    UNCERTAIN = "uncertain"


class EvidenceState(ValueEnum):
    SUPPORTED = "supported"
    ABSENT = "absent"
    CONTRADICTORY = "contradictory"
    MEASURED_NEGATIVE = "measured_negative"
    UNSUPPORTED = "unsupported"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class EvidenceTier(ValueEnum):
    REFERENCE = "reference"
    COMPUTED = "computed"
    EXPERIMENTAL = "experimental"
    COHORT = "cohort"
    REVIEWED = "reviewed"


class SupportLevel(ValueEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNKNOWN = "unknown"


class ResearchStatus(ValueEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    REVIEWED = "reviewed"
    RELEASED_RESEARCH = "released_research"
    SUPERSEDED = "superseded"


class ReviewState(ValueEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RETURNED = "returned"


class EdgeType(ValueEnum):
    VARIANT_TO_ELEMENT = "variant_to_element"
    ELEMENT_TO_GENE = "element_to_gene"
    GENE_TO_STATE = "gene_to_state"
    CAUSAL_PATH = "causal_path"


class AssayType(ValueEnum):
    MPRA = "mpra"
    CRISPR_INTERFERENCE = "crispri"
    CRISPR_ACTIVATION = "crispra"
    BASE_EDITING = "base_editing"
    REPORTER = "reporter"
    PERTURBATION = "perturbation"
    CONTACT_ASSAY = "contact_assay"
    RNA_MEASUREMENT = "rna_measurement"


@dataclass(frozen=True, slots=True)
class ReferenceContext:
    """The context in which evidence is applicable."""

    genome_build: str
    disease_class: str
    age_group: str
    cell_state: str
    territory: str = "unknown"
    treatment_phase: str = "unknown"
    assay_support: tuple[str, ...] = ()
    source_version: str = "unspecified"

    def __post_init__(self) -> None:
        for name in ("genome_build", "disease_class", "age_group", "cell_state"):
            require_non_empty(getattr(self, name), name)

    @property
    def key(self) -> str:
        parts = (
            self.genome_build,
            self.disease_class,
            self.age_group,
            self.cell_state,
            self.territory,
            self.treatment_phase,
        )
        return "|".join(parts)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ReferenceContext":
        return cls(
            genome_build=str(raw.get("genome_build", "")),
            disease_class=str(raw.get("disease_class", "")),
            age_group=str(raw.get("age_group", "")),
            cell_state=str(raw.get("cell_state", "")),
            territory=str(raw.get("territory", "unknown")),
            treatment_phase=str(raw.get("treatment_phase", "unknown")),
            assay_support=tuple(str(item) for item in raw.get("assay_support", ())),
            source_version=str(raw.get("source_version", "unspecified")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariantIdentity:
    """Canonical variation identity with explicit origin and provenance."""

    variant_id: str
    kind: VariantKind
    chromosome: str
    start: int
    end: int
    reference: str
    alternate: str
    genome_build: str
    origin: VariantOrigin = VariantOrigin.UNCERTAIN
    clonality: str = "unknown"
    sample_id: str = "unspecified"
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.variant_id, "variant_id")
        require_non_empty(self.chromosome, "chromosome")
        require_non_empty(self.genome_build, "genome_build")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("variant coordinates must satisfy 1 <= start <= end")
        if not self.reference or not self.alternate:
            raise ValidationError("reference and alternate alleles must not be empty")

    @property
    def canonical_key(self) -> str:
        return ":".join(
            (
                self.genome_build,
                self.chromosome,
                str(self.start),
                str(self.end),
                self.reference,
                self.alternate,
            )
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "VariantIdentity":
        kind = VariantKind(str(raw.get("kind", VariantKind.SNV.value)))
        origin = VariantOrigin(str(raw.get("origin", VariantOrigin.UNCERTAIN.value)))
        return cls(
            variant_id=str(raw.get("variant_id", "")),
            kind=kind,
            chromosome=str(raw.get("chromosome", "")),
            start=int(raw.get("start", 0)),
            end=int(raw.get("end", raw.get("start", 0))),
            reference=str(raw.get("reference", "")),
            alternate=str(raw.get("alternate", "")),
            genome_build=str(raw.get("genome_build", "")),
            origin=origin,
            clonality=str(raw.get("clonality", "unknown")),
            sample_id=str(raw.get("sample_id", "unspecified")),
            annotations=dict(raw.get("annotations", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CandidateElement:
    """A context-qualified regulatory element candidate supplied by an adapter."""

    element_id: str
    chromosome: str
    start: int
    end: int
    element_type: str
    context: ReferenceContext
    source_id: str
    target_genes: tuple[str, ...] = ()
    state_ids: tuple[str, ...] = ()
    features: Mapping[str, float] = field(default_factory=dict)
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("element_id", "chromosome", "element_type", "source_id"):
            require_non_empty(getattr(self, name), name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("element coordinates must satisfy 1 <= start <= end")
        if not self.target_genes and not self.state_ids:
            raise ValidationError("an element must expose a candidate gene or state")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], default_context: ReferenceContext) -> "CandidateElement":
        context_raw = raw.get("context")
        context = default_context if not isinstance(context_raw, Mapping) else ReferenceContext.from_dict(context_raw)
        features = {str(key): float(value) for key, value in dict(raw.get("features", {})).items()}
        return cls(
            element_id=str(raw.get("element_id", "")),
            chromosome=str(raw.get("chromosome", "")),
            start=int(raw.get("start", 0)),
            end=int(raw.get("end", raw.get("start", 0))),
            element_type=str(raw.get("element_type", "regulatory_element")),
            context=context,
            source_id=str(raw.get("source_id", "")),
            target_genes=tuple(str(item) for item in raw.get("target_genes", ())),
            state_ids=tuple(str(item) for item in raw.get("state_ids", ())),
            features=features,
            annotations=dict(raw.get("annotations", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CaseManifest:
    """Input contract for a reproducible case evaluation."""

    case_id: str
    subject_id: str
    context: ReferenceContext
    variants: tuple[VariantIdentity, ...]
    candidate_elements: tuple[CandidateElement, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    input_versions: Mapping[str, str] = field(default_factory=dict)
    requested_by: str = "unspecified"

    def __post_init__(self) -> None:
        require_non_empty(self.case_id, "case_id")
        require_non_empty(self.subject_id, "subject_id")
        if not self.variants:
            raise ValidationError("case must contain at least one variant")
        seen = set()
        for variant in self.variants:
            if variant.variant_id in seen:
                raise ValidationError(f"duplicate variant_id: {variant.variant_id}")
            seen.add(variant.variant_id)
        element_ids = [element.element_id for element in self.candidate_elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValidationError("candidate element IDs must be unique")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CaseManifest":
        context = ReferenceContext.from_dict(dict(raw.get("context", {})))
        variants = tuple(VariantIdentity.from_dict(item) for item in raw.get("variants", ()))
        elements = tuple(
            CandidateElement.from_dict(item, context) for item in raw.get("candidate_elements", ())
        )
        return cls(
            case_id=str(raw.get("case_id", "")),
            subject_id=str(raw.get("subject_id", "")),
            context=context,
            variants=variants,
            candidate_elements=elements,
            metadata=dict(raw.get("metadata", {})),
            input_versions={str(key): str(value) for key, value in dict(raw.get("input_versions", {})).items()},
            requested_by=str(raw.get("requested_by", "unspecified")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    """An append-only claim about exactly one typed edge."""

    evidence_id: str
    edge_id: str
    source_id: str
    channel: str
    state: EvidenceState
    tier: EvidenceTier
    score: float | None
    confidence: float
    context: ReferenceContext
    summary: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    produced_by: str = "deterministic_runtime"
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    supersedes: str | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "edge_id", "source_id", "channel", "summary"):
            require_non_empty(getattr(self, name), name)
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValidationError("evidence score must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("evidence confidence must be between 0 and 1")
        if self.supersedes == self.evidence_id:
            raise ValidationError("an evidence claim cannot supersede itself")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HypothesisEdge:
    """One decomposed edge in a candidate causal path."""

    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    support: float
    uncertainty: float
    context_fit: float
    claim_ids: tuple[str, ...]
    support_level: SupportLevel
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("edge_id", "source_id", "target_id"):
            require_non_empty(getattr(self, name), name)
        for name in ("support", "uncertainty", "context_fit"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
        if not self.claim_ids:
            raise ValidationError("each edge must reference at least one claim or abstention")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A research hypothesis with factorized links and a transparent summary."""

    hypothesis_id: str
    variant_id: str
    element_id: str
    gene_id: str
    state_id: str
    mechanism: str
    context: ReferenceContext
    edges: tuple[HypothesisEdge, ...]
    support: float
    uncertainty: float
    status: ResearchStatus = ResearchStatus.DRAFT
    missing_evidence: tuple[str, ...] = ()
    negative_evidence: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "variant_id", "element_id", "gene_id", "state_id", "mechanism"):
            require_non_empty(getattr(self, name), name)
        if not self.edges:
            raise ValidationError("a hypothesis must have at least one edge")
        for name in ("support", "uncertainty"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExperimentOption:
    """A bounded validation option with explicit readouts and constraints."""

    option_id: str
    assay: AssayType
    tests_edges: tuple[str, ...]
    expected_information_gain: float
    feasibility: float
    cost_class: str
    required_context: tuple[str, ...]
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.option_id, "option_id")
        if not self.tests_edges:
            raise ValidationError("an experiment option must test at least one edge")
        for name in ("expected_information_gain", "feasibility"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")

    @property
    def priority(self) -> float:
        return round(self.expected_information_gain * self.feasibility, 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"priority": self.priority}


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """Human review record attached to a releaseable dossier."""

    review_id: str
    case_id: str
    reviewer: str
    state: ReviewState
    reviewed_hypothesis_ids: tuple[str, ...]
    rationale: str
    checked_claim_ids: tuple[str, ...]
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def __post_init__(self) -> None:
        for name in ("review_id", "case_id", "reviewer", "rationale"):
            require_non_empty(getattr(self, name), name)
        if not self.reviewed_hypothesis_ids:
            raise ValidationError("review must name at least one hypothesis")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ReviewDecision":
        """Rehydrate a review request from the public JSON contract."""

        return cls(
            review_id=str(raw.get("review_id", "")),
            case_id=str(raw.get("case_id", "")),
            reviewer=str(raw.get("reviewer", "")),
            state=ReviewState(str(raw.get("state", ReviewState.PENDING.value))),
            reviewed_hypothesis_ids=tuple(str(item) for item in raw.get("reviewed_hypothesis_ids", ())),
            rationale=str(raw.get("rationale", "")),
            checked_claim_ids=tuple(str(item) for item in raw.get("checked_claim_ids", ())),
            created_at=str(raw.get("created_at", utc_now().isoformat())),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class Dossier:
    """Replayable case snapshot suitable for local review and research release."""

    dossier_id: str
    case_id: str
    run_id: str
    created_at: str
    input_address: str
    hypotheses: tuple[Hypothesis, ...]
    evidence: tuple[EvidenceClaim, ...]
    experiments: tuple[ExperimentOption, ...]
    review: ReviewDecision | None
    research_use_only: bool
    policy_version: str
    event_head: str
    content_address: str
    status: ResearchStatus
    warnings: tuple[str, ...] = ()
    source_receipts: tuple[Mapping[str, Any], ...] = ()
    source_bundle_addresses: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Dossier":
        """Rehydrate an immutable stored dossier for a follow-up review."""

        hypotheses: list[Hypothesis] = []
        for hypothesis_raw in raw.get("hypotheses", ()):
            context = ReferenceContext.from_dict(hypothesis_raw.get("context", {}))
            edges = tuple(
                HypothesisEdge(
                    edge_id=str(edge_raw.get("edge_id", "")),
                    edge_type=EdgeType(str(edge_raw.get("edge_type", EdgeType.CAUSAL_PATH.value))),
                    source_id=str(edge_raw.get("source_id", "")),
                    target_id=str(edge_raw.get("target_id", "")),
                    support=float(edge_raw.get("support", 0.0)),
                    uncertainty=float(edge_raw.get("uncertainty", 0.0)),
                    context_fit=float(edge_raw.get("context_fit", 0.0)),
                    claim_ids=tuple(str(item) for item in edge_raw.get("claim_ids", ())),
                    support_level=SupportLevel(str(edge_raw.get("support_level", SupportLevel.UNKNOWN.value))),
                    alternatives=tuple(str(item) for item in edge_raw.get("alternatives", ())),
                )
                for edge_raw in hypothesis_raw.get("edges", ())
            )
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=str(hypothesis_raw.get("hypothesis_id", "")),
                    variant_id=str(hypothesis_raw.get("variant_id", "")),
                    element_id=str(hypothesis_raw.get("element_id", "")),
                    gene_id=str(hypothesis_raw.get("gene_id", "")),
                    state_id=str(hypothesis_raw.get("state_id", "")),
                    mechanism=str(hypothesis_raw.get("mechanism", "")),
                    context=context,
                    edges=edges,
                    support=float(hypothesis_raw.get("support", 0.0)),
                    uncertainty=float(hypothesis_raw.get("uncertainty", 0.0)),
                    status=ResearchStatus(str(hypothesis_raw.get("status", ResearchStatus.DRAFT.value))),
                    missing_evidence=tuple(str(item) for item in hypothesis_raw.get("missing_evidence", ())),
                    negative_evidence=tuple(str(item) for item in hypothesis_raw.get("negative_evidence", ())),
                    alternatives=tuple(str(item) for item in hypothesis_raw.get("alternatives", ())),
                    provenance=tuple(str(item) for item in hypothesis_raw.get("provenance", ())),
                )
            )
        evidence = tuple(
            EvidenceClaim(
                evidence_id=str(item.get("evidence_id", "")),
                edge_id=str(item.get("edge_id", "")),
                source_id=str(item.get("source_id", "")),
                channel=str(item.get("channel", "")),
                state=EvidenceState(str(item.get("state", EvidenceState.ABSTAINED.value))),
                tier=EvidenceTier(str(item.get("tier", EvidenceTier.COMPUTED.value))),
                score=None if item.get("score") is None else float(item.get("score")),
                confidence=float(item.get("confidence", 0.0)),
                context=ReferenceContext.from_dict(item.get("context", {})),
                summary=str(item.get("summary", "")),
                payload=dict(item.get("payload", {})),
                depends_on=tuple(str(value) for value in item.get("depends_on", ())),
                produced_by=str(item.get("produced_by", "deterministic_runtime")),
                created_at=str(item.get("created_at", utc_now().isoformat())),
                supersedes=item.get("supersedes"),
            )
            for item in raw.get("evidence", ())
        )
        experiments = tuple(
            ExperimentOption(
                option_id=str(item.get("option_id", "")),
                assay=AssayType(str(item.get("assay", AssayType.PERTURBATION.value))),
                tests_edges=tuple(str(value) for value in item.get("tests_edges", ())),
                expected_information_gain=float(item.get("expected_information_gain", 0.0)),
                feasibility=float(item.get("feasibility", 0.0)),
                cost_class=str(item.get("cost_class", "unspecified")),
                required_context=tuple(str(value) for value in item.get("required_context", ())),
                controls=tuple(str(value) for value in item.get("controls", ())),
                readouts=tuple(str(value) for value in item.get("readouts", ())),
                limitations=tuple(str(value) for value in item.get("limitations", ())),
            )
            for item in raw.get("experiments", ())
        )
        review_raw = raw.get("review")
        review = ReviewDecision.from_dict(review_raw) if isinstance(review_raw, Mapping) else None
        return cls(
            dossier_id=str(raw.get("dossier_id", "")),
            case_id=str(raw.get("case_id", "")),
            run_id=str(raw.get("run_id", "")),
            created_at=str(raw.get("created_at", "")),
            input_address=str(raw.get("input_address", "")),
            hypotheses=tuple(hypotheses),
            evidence=evidence,
            experiments=experiments,
            review=review,
            research_use_only=bool(raw.get("research_use_only", False)),
            policy_version=str(raw.get("policy_version", "")),
            event_head=str(raw.get("event_head", "")),
            content_address=str(raw.get("content_address", "")),
            status=ResearchStatus(str(raw.get("status", ResearchStatus.DRAFT.value))),
            warnings=tuple(str(item) for item in raw.get("warnings", ())),
            source_receipts=tuple(dict(item) for item in raw.get("source_receipts", ())),
            source_bundle_addresses=tuple(str(item) for item in raw.get("source_bundle_addresses", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def is_releasable(self) -> bool:
        return self.research_use_only and self.review is not None and self.review.state == ReviewState.ACCEPTED


def enum_values(enum_type: type[ValueEnum]) -> list[str]:
    """Expose allowed values for schema and client generation."""

    return [item.value for item in enum_type]


def ensure_unique(values: Iterable[str], label: str) -> None:
    """Validate uniqueness in a collection while preserving caller ordering."""

    values_list = list(values)
    if len(values_list) != len(set(values_list)):
        raise ValidationError(f"{label} values must be unique")

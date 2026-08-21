"""External-alpha adapters and graph models for regulatory link evidence.

Domain 10 external-alpha contracts extend the candidate-link plane with four
explicit evidence paths:

* CRISPR perturbation rows preserve perturbation mode, direction, effect size,
  replicate identity, and exact variant-element-gene context.
* 3D contact rows preserve the assay kind, signal scale, resolution, and raw
  contact measurement before a candidate edge is created.
* Promoter tethering computes a bounded, component-level baseline from declared
  distance, contact, promoter, and activity observations. It is a tethering
  hypothesis, not a regulatory mechanism.
* The multi-gene/multi-element graph builder retains every candidate edge,
  alternatives, evidence lineage, connected-component structure, and graph
  state without selecting a single target gene by convenience.

All models are research-use evidence structures. They do not infer causality,
clinical relevance, pathogenicity, prognosis, or actionability. Context
mismatch is an explicit transport failure, while missing channels produce
partial or abstained states rather than silent defaults.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import exp, isfinite
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .link_graph import (
    CandidateLinkGraph,
    EnhancerGeneConsensusLinker,
    LinkEvidence,
    LinkState,
    LinkType,
)
from .models import ReferenceContext
from .serialization import content_hash, jsonable, require_non_empty


class LinkGraphAlphaState(StrEnum):
    """State for parser/model reports in the external-alpha link plane."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    INVALID = "invalid"


class PerturbationDirection(StrEnum):
    """Declared direction of a perturbation effect."""

    ACTIVATING = "activating"
    REPRESSING = "repressing"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ContactAssayKind(StrEnum):
    """Contact assay labels retained as evidence metadata."""

    HIC = "hic"
    MICRO_C = "micro_c"
    CAPTURE_C = "capture_c"
    PROMOTER_CAPTURE = "promoter_capture"
    CHIA_PET = "chia_pet"
    GAM = "gam"
    OTHER = "other"


class TetheringTier(StrEnum):
    """Interpretive tier for the declared promoter-tethering baseline."""

    PROMOTER_OVERLAP = "promoter_overlap"
    PROXIMAL = "proximal"
    DISTAL_CONTACT = "distal_contact"
    LOW_SUPPORT = "low_support"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaIssue:
    """A quarantined alpha row with a stable receipt and remediation hint."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    remediation: str = "Inspect the row, source version, and declared context before retrying."
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "link graph alpha issue code")
        require_non_empty(self.message, "link graph alpha issue message")
        require_non_empty(self.raw_hash, "link graph alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("link graph alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CRISPRPerturbationLinkObservation:
    """One CRISPR perturbation path from a variant or element to a gene."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    perturbation_mode: str
    direction: PerturbationDirection
    effect_size: float
    effect_scale: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    confidence: float = 1.0
    p_value: float | None = None
    q_value: float | None = None
    replicate_id: str | None = None
    guide_id: str | None = None
    state: LinkState = LinkState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "variant_id",
            "element_id",
            "gene_id",
            "perturbation_mode",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not isfinite(self.effect_size):
            raise ValidationError("CRISPR effect_size must be finite")
        if not isfinite(self.effect_scale) or self.effect_scale <= 0:
            raise ValidationError("CRISPR effect_scale must be finite and positive")
        if not 0 <= self.confidence <= 1:
            raise ValidationError("CRISPR confidence must be between zero and one")
        for name in ("p_value", "q_value"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValidationError(f"CRISPR {name} must be between zero and one")

    @property
    def bounded_support(self) -> float:
        """Return an effect-scale-bounded support value, retaining raw effect."""

        return min(1.0, abs(self.effect_size) / self.effect_scale) * self.confidence

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["bounded_support"] = self.bounded_support
        return payload


@dataclass(frozen=True, slots=True)
class CRISPRPerturbationLinkBatch:
    """Parsed CRISPR observations plus malformed-row accounting."""

    source_id: str
    input_hash: str
    observations: tuple[CRISPRPerturbationLinkObservation, ...]
    issues: tuple[LinkGraphAlphaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["observations"] = tuple(observation.to_dict() for observation in self.observations)
        return payload


class CRISPRPerturbationLinkAdapter:
    """Parse CRISPR perturbation-link rows with loss-accounted receipts."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        effect_scale: float = 1.0,
    ) -> CRISPRPerturbationLinkBatch:
        rows, json_mode = _rows(text, input_format, "observations")
        if not source_id.strip():
            raise ValidationError("CRISPR source_id is required")
        if effect_scale <= 0 or not isfinite(effect_scale):
            raise ValidationError("CRISPR effect_scale must be finite and positive")
        observations: list[CRISPRPerturbationLinkObservation] = []
        issues: list[LinkGraphAlphaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    LinkGraphAlphaIssue(
                        "invalid_crispr_perturbation_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                observations.append(
                    CRISPRPerturbationLinkObservation(
                        evidence_id=str(
                            _value(row, "evidence_id", "link_id", default=f"{source_id}:{index}")
                        ),
                        variant_id=str(_value(row, "variant_id", "variant")),
                        element_id=str(
                            _value(row, "element_id", "enhancer_id", "regulatory_element_id")
                        ),
                        gene_id=str(_value(row, "gene_id", "gene", "promoter_id")),
                        perturbation_mode=str(
                            _value(row, "perturbation_mode", "mode", "assay", default="unknown")
                        ),
                        direction=_direction(
                            _value(row, "direction", "effect_direction", default="unknown")
                        ),
                        effect_size=float(_value(row, "effect_size", "effect", "delta")),
                        effect_scale=float(_value(row, "effect_scale", default=effect_scale)),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        confidence=float(_value(row, "confidence", default=1.0)),
                        p_value=_optional_float(row, "p_value", "pvalue"),
                        q_value=_optional_float(row, "q_value", "qvalue", "fdr"),
                        replicate_id=_optional_text(row, "replicate_id", "replicate"),
                        guide_id=_optional_text(row, "guide_id", "guide"),
                        state=_link_state(row.get("state", LinkState.SUPPORTED.value)),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LinkGraphAlphaIssue(
                        "invalid_crispr_perturbation_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return CRISPRPerturbationLinkBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


class CRISPRPerturbationLinker:
    """Convert exact-context CRISPR observations into candidate link edges."""

    def link(
        self,
        observations: Iterable[CRISPRPerturbationLinkObservation | Mapping[str, Any]],
        context: ReferenceContext,
        *,
        variant_id: str | None = None,
    ) -> CandidateLinkGraph:
        values = tuple(_coerce_crispr(value) for value in observations)
        directions: dict[tuple[str, str, str], set[PerturbationDirection]] = defaultdict(set)
        for value in values:
            if value.context_key == context.key:
                directions[(value.variant_id, value.element_id, value.gene_id)].add(value.direction)
        evidence: list[LinkEvidence] = []
        for value in values:
            key = (value.variant_id, value.element_id, value.gene_id)
            direction_set = directions.get(key, set())
            opposing = (
                PerturbationDirection.ACTIVATING in direction_set
                and PerturbationDirection.REPRESSING in direction_set
            )
            evidence.append(
                LinkEvidence(
                    evidence_id=value.evidence_id,
                    variant_id=value.variant_id,
                    element_id=value.element_id,
                    gene_id=value.gene_id,
                    link_type=LinkType.PERTURBATION,
                    context_key=value.context_key,
                    source_id=value.source_id,
                    source_version=value.source_version,
                    raw_hash=value.raw_hash,
                    support=value.bounded_support,
                    confidence=value.confidence,
                    state=LinkState.CONTRADICTORY if opposing else value.state,
                    attributes={
                        **dict(value.attributes),
                        "perturbation_mode": value.perturbation_mode,
                        "effect_direction": value.direction.value,
                        "effect_size": value.effect_size,
                        "p_value": value.p_value,
                        "q_value": value.q_value,
                        "replicate_id": value.replicate_id,
                        "guide_id": value.guide_id,
                    },
                )
            )
        return EnhancerGeneConsensusLinker().link(
            evidence,
            context,
            variant_id=variant_id,
        )


@dataclass(frozen=True, slots=True)
class ThreeDContactLinkObservation:
    """One normalized or raw 3D contact path to a promoter/gene."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    contact_signal: float
    contact_scale: float
    resolution_bp: int
    assay_kind: ContactAssayKind
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    confidence: float = 1.0
    replicate_id: str | None = None
    state: LinkState = LinkState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "variant_id",
            "element_id",
            "gene_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not isfinite(self.contact_signal) or self.contact_signal < 0:
            raise ValidationError("3D contact_signal must be finite and non-negative")
        if not isfinite(self.contact_scale) or self.contact_scale <= 0:
            raise ValidationError("3D contact_scale must be finite and positive")
        if self.resolution_bp < 1:
            raise ValidationError("3D contact resolution_bp must be positive")
        if not 0 <= self.confidence <= 1:
            raise ValidationError("3D contact confidence must be between zero and one")

    @property
    def normalized_contact(self) -> float:
        return min(1.0, self.contact_signal / self.contact_scale)

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["normalized_contact"] = self.normalized_contact
        return payload


@dataclass(frozen=True, slots=True)
class ThreeDContactLinkBatch:
    """Parsed 3D contact paths and row-level issues."""

    source_id: str
    input_hash: str
    observations: tuple[ThreeDContactLinkObservation, ...]
    issues: tuple[LinkGraphAlphaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["observations"] = tuple(observation.to_dict() for observation in self.observations)
        return payload


class ThreeDContactLinkAdapter:
    """Parse contact-link rows while retaining assay scale and resolution."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        contact_scale: float = 1.0,
        resolution_bp: int = 5000,
        assay_kind: ContactAssayKind = ContactAssayKind.HIC,
    ) -> ThreeDContactLinkBatch:
        rows, json_mode = _rows(text, input_format, "observations")
        if contact_scale <= 0 or not isfinite(contact_scale):
            raise ValidationError("3D contact_scale must be finite and positive")
        if resolution_bp < 1:
            raise ValidationError("3D resolution_bp must be positive")
        observations: list[ThreeDContactLinkObservation] = []
        issues: list[LinkGraphAlphaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    LinkGraphAlphaIssue(
                        "invalid_3d_contact_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                observations.append(
                    ThreeDContactLinkObservation(
                        evidence_id=str(
                            _value(row, "evidence_id", "link_id", default=f"{source_id}:{index}")
                        ),
                        variant_id=str(_value(row, "variant_id", "variant")),
                        element_id=str(
                            _value(row, "element_id", "enhancer_id", "regulatory_element_id")
                        ),
                        gene_id=str(_value(row, "gene_id", "gene", "promoter_id")),
                        contact_signal=float(
                            _value(row, "contact_signal", "contact", "score", "contact_score")
                        ),
                        contact_scale=float(_value(row, "contact_scale", default=contact_scale)),
                        resolution_bp=int(
                            _value(row, "resolution_bp", "resolution", default=resolution_bp)
                        ),
                        assay_kind=_assay_kind(
                            _value(row, "assay_kind", "assay", default=assay_kind.value)
                        ),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        confidence=float(_value(row, "confidence", default=1.0)),
                        replicate_id=_optional_text(row, "replicate_id", "replicate"),
                        state=_link_state(row.get("state", LinkState.SUPPORTED.value)),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LinkGraphAlphaIssue(
                        "invalid_3d_contact_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return ThreeDContactLinkBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


class ThreeDContactLinker:
    """Convert exact-context contact paths into candidate graph edges."""

    def link(
        self,
        observations: Iterable[ThreeDContactLinkObservation | Mapping[str, Any]],
        context: ReferenceContext,
        *,
        variant_id: str | None = None,
    ) -> CandidateLinkGraph:
        values = tuple(_coerce_contact(value) for value in observations)
        evidence = tuple(
            LinkEvidence(
                evidence_id=value.evidence_id,
                variant_id=value.variant_id,
                element_id=value.element_id,
                gene_id=value.gene_id,
                link_type=LinkType.CONTACT,
                context_key=value.context_key,
                source_id=value.source_id,
                source_version=value.source_version,
                raw_hash=value.raw_hash,
                support=value.normalized_contact * value.confidence,
                confidence=value.confidence,
                state=value.state,
                attributes={
                    **dict(value.attributes),
                    "contact_signal": value.contact_signal,
                    "contact_scale": value.contact_scale,
                    "normalized_contact": value.normalized_contact,
                    "resolution_bp": value.resolution_bp,
                    "assay_kind": value.assay_kind.value,
                    "replicate_id": value.replicate_id,
                },
            )
            for value in values
        )
        return EnhancerGeneConsensusLinker().link(
            evidence,
            context,
            variant_id=variant_id,
        )


@dataclass(frozen=True, slots=True)
class PromoterTetheringObservation:
    """Declared inputs used by the promoter-tethering baseline."""

    observation_id: str
    variant_id: str
    element_id: str
    gene_id: str
    distance_bp: int
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    contact_support: float | None = None
    promoter_activity: float | None = None
    element_activity: float | None = None
    promoter_overlap: bool = False
    promoter_id: str | None = None
    decay_distance_bp: int = 100000
    confidence: float = 1.0
    state: LinkState = LinkState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "element_id",
            "gene_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.distance_bp < 0:
            raise ValidationError("promoter tethering distance_bp must be non-negative")
        if self.decay_distance_bp < 1:
            raise ValidationError("promoter tethering decay_distance_bp must be positive")
        if not 0 <= self.confidence <= 1:
            raise ValidationError("promoter tethering confidence must be between zero and one")
        for name in ("contact_support", "promoter_activity", "element_activity"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValidationError(f"promoter tethering {name} must be between zero and one")

    @property
    def distance_prior(self) -> float:
        return exp(-self.distance_bp / self.decay_distance_bp)

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["distance_prior"] = self.distance_prior
        return payload


@dataclass(frozen=True, slots=True)
class PromoterTetheringResult:
    """One scored promoter-tethering candidate and its component receipt."""

    variant_id: str
    element_id: str
    gene_id: str
    context_key: str
    tethering_score: float | None
    distance_prior: float | None
    contact_component: float | None
    promoter_component: float | None
    element_component: float | None
    overlap_component: float | None
    available_components: tuple[str, ...]
    tier: TetheringTier
    state: LinkGraphAlphaState
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    alternatives: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PromoterTetheringReport:
    """Promoter-tethering model output with context and input receipts."""

    input_hash: str
    context_key: str | None
    state: LinkGraphAlphaState
    results: tuple[PromoterTetheringResult, ...]
    issues: tuple[LinkGraphAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PromoterTetheringModel:
    """Score declared promoter-tethering components without mechanism claims."""

    def assess(
        self,
        observations: Iterable[PromoterTetheringObservation | Mapping[str, Any]],
        *,
        context_key: str | None = None,
        minimum_score: float = 0.35,
        maximum_distance_bp: int | None = None,
        minimum_components: int = 2,
    ) -> PromoterTetheringReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        issues: list[LinkGraphAlphaIssue] = []
        parsed: list[PromoterTetheringObservation] = []
        context_mismatch = False
        if not 0 <= minimum_score <= 1:
            issue = LinkGraphAlphaIssue(
                "invalid_tethering_parameter",
                "minimum_score must be between zero and one",
                input_hash,
                severity="error",
            )
            return PromoterTetheringReport(
                input_hash,
                context_key,
                LinkGraphAlphaState.INVALID,
                (),
                (issue,),
                (),
                content_hash(issue),
            )
        if minimum_components < 1:
            issue = LinkGraphAlphaIssue(
                "invalid_tethering_parameter",
                "minimum_components must be positive",
                input_hash,
                severity="error",
            )
            return PromoterTetheringReport(
                input_hash,
                context_key,
                LinkGraphAlphaState.INVALID,
                (),
                (issue,),
                (),
                content_hash(issue),
            )
        for row_number, value in enumerate(values, start=1):
            if isinstance(value, PromoterTetheringObservation):
                observation = value
            elif isinstance(value, Mapping):
                try:
                    observation = _coerce_tethering(value)
                except (TypeError, ValueError, ValidationError) as exc:
                    issues.append(
                        LinkGraphAlphaIssue(
                            "invalid_promoter_tethering_row",
                            str(exc),
                            content_hash(value),
                            row_number=row_number,
                            severity="error",
                            raw_record=dict(value),
                        )
                    )
                    continue
            else:
                issues.append(
                    LinkGraphAlphaIssue(
                        "invalid_promoter_tethering_row",
                        "row must be an object",
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if context_key and observation.context_key != context_key:
                context_mismatch = True
                issues.append(
                    LinkGraphAlphaIssue(
                        "context_mismatch",
                        "promoter-tethering observation is outside the requested context",
                        observation.raw_hash,
                        row_number=row_number,
                        source_id=observation.source_id,
                        severity="warning",
                    )
                )
                continue
            if maximum_distance_bp is not None and observation.distance_bp > maximum_distance_bp:
                issues.append(
                    LinkGraphAlphaIssue(
                        "distance_window_exceeded",
                        "promoter-tethering observation exceeds the declared distance window",
                        observation.raw_hash,
                        row_number=row_number,
                        source_id=observation.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(observation)
        grouped: dict[tuple[str, str, str, str], list[PromoterTetheringObservation]] = defaultdict(
            list
        )
        for observation in parsed:
            grouped[
                (
                    observation.variant_id,
                    observation.element_id,
                    observation.gene_id,
                    observation.context_key,
                )
            ].append(observation)
        results: list[PromoterTetheringResult] = []
        for key, group in sorted(grouped.items()):
            variant_id, element_id, gene_id, row_context = key
            distance_prior = fmean(item.distance_prior for item in group)
            components: dict[str, float] = {"distance_prior": distance_prior}
            for field_name, component_name in (
                ("contact_support", "contact"),
                ("promoter_activity", "promoter"),
                ("element_activity", "element"),
            ):
                channel = [getattr(item, field_name) for item in group]
                declared = [float(item) for item in channel if item is not None]
                if declared:
                    components[component_name] = fmean(declared)
            overlap_values = [1.0 if item.promoter_overlap else 0.0 for item in group]
            if any(item.promoter_overlap for item in group):
                components["overlap"] = fmean(overlap_values)
            weights = {
                "distance_prior": 0.25,
                "contact": 0.30,
                "promoter": 0.20,
                "element": 0.15,
                "overlap": 0.10,
            }
            available = tuple(name for name in weights if name in components)
            score = (
                sum(weights[name] * components[name] for name in available)
                / sum(weights[name] for name in available)
                if len(available) >= minimum_components
                else None
            )
            if score is None:
                tier = TetheringTier.ABSTAINED
                row_state = LinkGraphAlphaState.ABSTAINED
                reason = "insufficient declared tethering components"
            elif score < minimum_score:
                tier = TetheringTier.LOW_SUPPORT
                row_state = LinkGraphAlphaState.PARTIAL
                reason = "bounded tethering baseline is below the declared threshold"
            elif any(item.promoter_overlap for item in group):
                tier = TetheringTier.PROMOTER_OVERLAP
                row_state = LinkGraphAlphaState.SUPPORTED
                reason = "declared promoter overlap and component evidence pass the threshold"
            elif max(item.distance_bp for item in group) <= 2000:
                tier = TetheringTier.PROXIMAL
                row_state = LinkGraphAlphaState.SUPPORTED
                reason = "proximal promoter distance and component evidence pass the threshold"
            else:
                tier = TetheringTier.DISTAL_CONTACT
                row_state = LinkGraphAlphaState.SUPPORTED
                reason = "distal contact-supported tethering baseline passes the threshold"
            body = {
                "variant_id": variant_id,
                "element_id": element_id,
                "gene_id": gene_id,
                "context_key": row_context,
                "score": score,
                "components": components,
                "tier": tier,
                "state": row_state,
            }
            results.append(
                PromoterTetheringResult(
                    variant_id=variant_id,
                    element_id=element_id,
                    gene_id=gene_id,
                    context_key=row_context,
                    tethering_score=round(score, 9) if score is not None else None,
                    distance_prior=round(distance_prior, 9),
                    contact_component=_round_optional(components.get("contact")),
                    promoter_component=_round_optional(components.get("promoter")),
                    element_component=_round_optional(components.get("element")),
                    overlap_component=_round_optional(components.get("overlap")),
                    available_components=available,
                    tier=tier,
                    state=row_state,
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    raw_hashes=tuple(sorted(item.raw_hash for item in group)),
                    alternatives=(),
                    reason=reason,
                    limitations=(
                        "Distance and assay components are descriptive inputs, not a validated "
                        "tethering mechanism.",
                        "Threshold and decay parameters require external calibration and "
                        "negative controls.",
                    ),
                    content_address=content_hash(body),
                )
            )
        by_element: dict[tuple[str, str], list[PromoterTetheringResult]] = defaultdict(list)
        for result in results:
            by_element[(result.variant_id, result.element_id)].append(result)
        amended: list[PromoterTetheringResult] = []
        for result in results:
            peers = sorted(
                {
                    item.gene_id
                    for item in by_element[(result.variant_id, result.element_id)]
                    if item.gene_id != result.gene_id
                }
            )
            state = result.state
            if peers and result.tethering_score is not None:
                top_score = max(
                    item.tethering_score or 0.0
                    for item in by_element[(result.variant_id, result.element_id)]
                )
                if (
                    result.tethering_score == top_score
                    and sum(
                        1
                        for item in by_element[(result.variant_id, result.element_id)]
                        if item.tethering_score == top_score
                    )
                    > 1
                ):
                    state = LinkGraphAlphaState.AMBIGUOUS
            amended.append(
                replace(
                    result,
                    state=state,
                    alternatives=tuple(peers),
                    content_address=content_hash(
                        {**result.to_dict(), "state": state, "alternatives": tuple(peers)}
                    ),
                )
            )
        final_state = _alpha_state(
            tuple(item.state for item in amended),
            issues,
            context_mismatch,
        )
        return PromoterTetheringReport(
            input_hash=input_hash,
            context_key=context_key,
            state=final_state,
            results=tuple(amended),
            issues=tuple(issues),
            warnings=(
                "Promoter tethering is a bounded baseline, not a validated regulatory mechanism.",
                "Alternative genes remain visible when the same element has multiple candidates.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": final_state,
                    "results": amended,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class MultiGeneElementGraphEdge:
    """A graph edge retaining aggregate and source-path evidence."""

    link_id: str
    variant_id: str
    element_id: str
    gene_id: str
    link_type: LinkType
    context_key: str
    state: LinkState
    support: float | None
    uncertainty: float
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    alternatives: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("link_id", "variant_id", "element_id", "gene_id", "context_key", "reason"):
            require_non_empty(str(getattr(self, name)), name)
        if self.support is not None and not 0 <= self.support <= 1:
            raise ValidationError("multi-gene graph support must be between zero and one")
        if not 0 <= self.uncertainty <= 1:
            raise ValidationError("multi-gene graph uncertainty must be between zero and one")
        if not self.evidence_ids and self.state in {LinkState.SUPPORTED, LinkState.PARTIAL}:
            raise ValidationError("multi-gene graph supported edges require evidence IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MultiGeneElementGraph:
    """Context-qualified graph slice spanning variants, elements, and genes."""

    graph_id: str
    context_key: str
    state: LinkState
    variant_ids: tuple[str, ...]
    element_ids: tuple[str, ...]
    gene_ids: tuple[str, ...]
    edges: tuple[MultiGeneElementGraphEdge, ...]
    connected_components: tuple[tuple[str, ...], ...]
    degree_by_node: Mapping[str, int]
    warnings: tuple[str, ...]
    issues: tuple[LinkGraphAlphaIssue, ...]
    input_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MultiGeneElementGraphBuilder:
    """Build a lossless multi-gene/multi-element graph from link evidence."""

    def build(
        self,
        evidence: Iterable[LinkEvidence | Mapping[str, Any]],
        context: ReferenceContext,
        *,
        graph_id: str = "multi-gene-element-graph",
        variant_id: str | None = None,
        minimum_support: float = 0.0,
    ) -> MultiGeneElementGraph:
        values = tuple(evidence)
        input_hash = content_hash(values)
        issues: list[LinkGraphAlphaIssue] = []
        if not graph_id.strip():
            raise ValidationError("multi-gene graph_id is required")
        if not 0 <= minimum_support <= 1:
            issue = LinkGraphAlphaIssue(
                "invalid_graph_parameter",
                "minimum_support must be between zero and one",
                input_hash,
                severity="error",
            )
            return MultiGeneElementGraph(
                graph_id,
                context.key,
                LinkState.ABSTAINED,
                (),
                (),
                (),
                (),
                (),
                {},
                (),
                (issue,),
                input_hash,
                content_hash(issue),
            )
        parsed: list[LinkEvidence] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_evidence(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LinkGraphAlphaIssue(
                        "invalid_graph_evidence",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if variant_id and item.variant_id != variant_id:
                continue
            if item.context_key != context.key:
                mismatch = True
                issues.append(
                    LinkGraphAlphaIssue(
                        "context_mismatch",
                        "graph evidence is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            if item.support < minimum_support:
                issues.append(
                    LinkGraphAlphaIssue(
                        "support_threshold_excluded",
                        "evidence support is below the graph threshold",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="info",
                    )
                )
                continue
            parsed.append(item)
        candidate_graph = EnhancerGeneConsensusLinker().link(
            parsed,
            context,
            variant_id=variant_id,
        )
        edges = tuple(
            MultiGeneElementGraphEdge(
                link_id=link.link_id,
                variant_id=link.variant_id,
                element_id=link.element_id,
                gene_id=link.gene_id or "unassigned-gene",
                link_type=link.link_type,
                context_key=link.context_key,
                state=link.state,
                support=link.support,
                uncertainty=link.uncertainty,
                evidence_ids=link.evidence_ids,
                source_ids=link.source_ids,
                alternatives=link.alternatives,
                reason=link.reason,
                limitations=link.limitations
                + (
                    "Graph edges summarize declared evidence paths; they do not establish "
                    "regulation.",
                ),
                content_address=content_hash(link.to_dict()),
            )
            for link in candidate_graph.links
        )
        variants = tuple(sorted({edge.variant_id for edge in edges}))
        elements = tuple(sorted({edge.element_id for edge in edges}))
        genes = tuple(sorted({edge.gene_id for edge in edges}))
        degree: dict[str, int] = defaultdict(int)
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            nodes = (
                f"variant:{edge.variant_id}",
                f"element:{edge.element_id}",
                f"gene:{edge.gene_id}",
            )
            for node in nodes:
                degree[node] += 1
            for left in nodes:
                adjacency[left].update(item for item in nodes if item != left)
        components = _components(adjacency)
        state = candidate_graph.state
        if mismatch and not edges:
            state = LinkState.OUT_OF_DOMAIN
        elif issues and state == LinkState.SUPPORTED:
            state = LinkState.PARTIAL
        warnings = tuple(
            dict.fromkeys(
                candidate_graph.warnings
                + (
                    "Multi-gene and multi-element alternatives are retained; no preferred "
                    "target is selected.",
                    "Connected components describe graph structure, not a causal chain.",
                )
            )
        )
        return MultiGeneElementGraph(
            graph_id=graph_id,
            context_key=context.key,
            state=state,
            variant_ids=variants,
            element_ids=elements,
            gene_ids=genes,
            edges=edges,
            connected_components=components,
            degree_by_node=dict(sorted(degree.items())),
            warnings=warnings,
            issues=tuple(issues),
            input_hash=input_hash,
            content_address=content_hash(
                {
                    "graph_id": graph_id,
                    "context_key": context.key,
                    "state": state,
                    "edges": edges,
                    "components": components,
                    "issues": issues,
                }
            ),
        )


def _rows(
    text: str,
    input_format: str | None,
    collection_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("link graph alpha input must not be empty")
    selected = (input_format or "").lower().strip()
    if not selected:
        selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
    if selected == "json":
        import json

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid link graph alpha JSON: {exc}") from exc
        rows = payload.get(collection_key, payload) if isinstance(payload, Mapping) else payload
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValidationError(f"link graph alpha JSON must contain a {collection_key} list")
        return tuple(rows), True
    if selected == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("link graph alpha TSV requires a header")
        return tuple(reader), False
    raise ValidationError(f"unsupported link graph alpha format: {selected}")


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    if default is not None:
        return default
    raise ValidationError(f"link graph alpha field is required: {names[0]}")


def _optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return None


def _optional_float(row: Mapping[str, Any], *names: str) -> float | None:
    value = _optional_text(row, *names)
    return None if value is None else float(value)


def _direction(value: Any) -> PerturbationDirection:
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "gain": PerturbationDirection.ACTIVATING,
        "loss": PerturbationDirection.REPRESSING,
        "activation": PerturbationDirection.ACTIVATING,
        "repression": PerturbationDirection.REPRESSING,
        "none": PerturbationDirection.NEUTRAL,
    }
    return aliases.get(normalized, PerturbationDirection(normalized))


def _assay_kind(value: Any) -> ContactAssayKind:
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {"capturec": "capture_c", "promotercapture": "promoter_capture", "other": "other"}
    normalized = aliases.get(normalized, normalized)
    try:
        return ContactAssayKind(normalized)
    except ValueError:
        return ContactAssayKind.OTHER


def _link_state(value: Any) -> LinkState:
    try:
        return LinkState(str(value))
    except ValueError as exc:
        raise ValidationError(f"unsupported link state: {value}") from exc


def _coerce_crispr(
    value: CRISPRPerturbationLinkObservation | Mapping[str, Any],
) -> CRISPRPerturbationLinkObservation:
    if isinstance(value, CRISPRPerturbationLinkObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("CRISPR perturbation observation must be a mapping")
    return CRISPRPerturbationLinkObservation(
        evidence_id=str(value.get("evidence_id", value.get("link_id", "crispr-input"))),
        variant_id=str(value.get("variant_id", value.get("variant", ""))),
        element_id=str(value.get("element_id", value.get("enhancer_id", ""))),
        gene_id=str(value.get("gene_id", value.get("gene", value.get("promoter_id", "")))),
        perturbation_mode=str(value.get("perturbation_mode", value.get("mode", "unknown"))),
        direction=_direction(value.get("direction", value.get("effect_direction", "unknown"))),
        effect_size=float(value.get("effect_size", value.get("effect", 0.0))),
        effect_scale=float(value.get("effect_scale", 1.0)),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "crispr-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        confidence=float(value.get("confidence", 1.0)),
        p_value=_mapping_optional_float(value, "p_value", "pvalue"),
        q_value=_mapping_optional_float(value, "q_value", "qvalue", "fdr"),
        replicate_id=_mapping_optional_text(value, "replicate_id", "replicate"),
        guide_id=_mapping_optional_text(value, "guide_id", "guide"),
        state=_link_state(value.get("state", LinkState.SUPPORTED.value)),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_contact(
    value: ThreeDContactLinkObservation | Mapping[str, Any],
) -> ThreeDContactLinkObservation:
    if isinstance(value, ThreeDContactLinkObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("3D contact observation must be a mapping")
    return ThreeDContactLinkObservation(
        evidence_id=str(value.get("evidence_id", value.get("link_id", "contact-input"))),
        variant_id=str(value.get("variant_id", value.get("variant", ""))),
        element_id=str(value.get("element_id", value.get("enhancer_id", ""))),
        gene_id=str(value.get("gene_id", value.get("gene", value.get("promoter_id", "")))),
        contact_signal=float(
            value.get("contact_signal", value.get("contact", value.get("score", 0.0)))
        ),
        contact_scale=float(value.get("contact_scale", 1.0)),
        resolution_bp=int(value.get("resolution_bp", value.get("resolution", 5000))),
        assay_kind=_assay_kind(
            value.get("assay_kind", value.get("assay", ContactAssayKind.HIC.value))
        ),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "contact-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        confidence=float(value.get("confidence", 1.0)),
        replicate_id=_mapping_optional_text(value, "replicate_id", "replicate"),
        state=_link_state(value.get("state", LinkState.SUPPORTED.value)),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_tethering(value: Mapping[str, Any]) -> PromoterTetheringObservation:
    return PromoterTetheringObservation(
        observation_id=str(value.get("observation_id", value.get("id", "tether-input"))),
        variant_id=str(value.get("variant_id", value.get("variant", ""))),
        element_id=str(value.get("element_id", value.get("enhancer_id", ""))),
        gene_id=str(value.get("gene_id", value.get("gene", ""))),
        distance_bp=int(value.get("distance_bp", value.get("distance", 0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "tethering-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        contact_support=_mapping_optional_float(value, "contact_support", "contact"),
        promoter_activity=_mapping_optional_float(value, "promoter_activity", "promoter_score"),
        element_activity=_mapping_optional_float(value, "element_activity", "activity"),
        promoter_overlap=bool(value.get("promoter_overlap", value.get("overlap", False))),
        promoter_id=_mapping_optional_text(value, "promoter_id", "promoter"),
        decay_distance_bp=int(value.get("decay_distance_bp", 100000)),
        confidence=float(value.get("confidence", 1.0)),
        state=_link_state(value.get("state", LinkState.SUPPORTED.value)),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_evidence(value: LinkEvidence | Mapping[str, Any]) -> LinkEvidence:
    if isinstance(value, LinkEvidence):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("multi-gene graph evidence must be a mapping")
    try:
        link_type = LinkType(str(value.get("link_type", LinkType.CONSENSUS.value)))
    except ValueError as exc:
        raise ValidationError(f"unsupported link type: {value.get('link_type')}") from exc
    return LinkEvidence(
        evidence_id=str(value.get("evidence_id", value.get("link_id", "graph-input"))),
        variant_id=str(value.get("variant_id", "")),
        element_id=str(value.get("element_id", "")),
        gene_id=str(value.get("gene_id", value.get("gene", ""))),
        link_type=link_type,
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "graph-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        support=float(value.get("support", 0.0)),
        confidence=float(value.get("confidence", 1.0)),
        state=_link_state(value.get("state", LinkState.SUPPORTED.value)),
        attributes=dict(value.get("attributes", {})),
    )


def _mapping_optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    return _optional_text(row, *names)


def _mapping_optional_float(row: Mapping[str, Any], *names: str) -> float | None:
    value = _mapping_optional_text(row, *names)
    return None if value is None else float(value)


def _round_optional(value: float | None) -> float | None:
    return round(value, 9) if value is not None else None


def _alpha_state(
    states: Iterable[LinkGraphAlphaState],
    issues: Iterable[LinkGraphAlphaIssue],
    context_mismatch: bool,
) -> LinkGraphAlphaState:
    values = tuple(states)
    if values:
        if LinkGraphAlphaState.ABSTAINED in values and all(
            value == LinkGraphAlphaState.ABSTAINED for value in values
        ):
            return LinkGraphAlphaState.ABSTAINED
        if LinkGraphAlphaState.AMBIGUOUS in values:
            return LinkGraphAlphaState.AMBIGUOUS
        if any(value == LinkGraphAlphaState.PARTIAL for value in values):
            return LinkGraphAlphaState.PARTIAL
        if all(value == LinkGraphAlphaState.SUPPORTED for value in values):
            return LinkGraphAlphaState.SUPPORTED
    if context_mismatch:
        return LinkGraphAlphaState.OUT_OF_DOMAIN
    if any(issue.severity == "error" for issue in issues):
        return LinkGraphAlphaState.PARTIAL
    return LinkGraphAlphaState.ABSTAINED


def _components(adjacency: Mapping[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    remaining = set(adjacency)
    components: list[tuple[str, ...]] = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            remaining.discard(node)
            stack.extend(sorted(adjacency.get(node, set()) - component, reverse=True))
        components.append(tuple(sorted(component)))
    return tuple(sorted(components))


__all__ = [
    "CRISPRPerturbationLinkAdapter",
    "CRISPRPerturbationLinkBatch",
    "CRISPRPerturbationLinkObservation",
    "CRISPRPerturbationLinker",
    "ContactAssayKind",
    "LinkGraphAlphaIssue",
    "LinkGraphAlphaState",
    "MultiGeneElementGraph",
    "MultiGeneElementGraphBuilder",
    "MultiGeneElementGraphEdge",
    "PerturbationDirection",
    "PromoterTetheringModel",
    "PromoterTetheringObservation",
    "PromoterTetheringReport",
    "PromoterTetheringResult",
    "TetheringTier",
    "ThreeDContactLinkAdapter",
    "ThreeDContactLinkBatch",
    "ThreeDContactLinkObservation",
    "ThreeDContactLinker",
]

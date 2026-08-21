"""Deterministic, evidence-bounded handlers for the remaining inference roles.

The extension layer deliberately operates on serialized observations rather than
hidden models.  Every result retains the supplied state, context qualification,
source identifiers, and limitations.  A missing measurement is never converted
into a negative measurement, and a weak context match cannot be upgraded by a
downstream calculation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from .errors import ValidationError
from .models import EvidenceState
from .serialization import content_hash, jsonable


class InferenceState(StrEnum):
    """Result state used when an extension combines one or more observations."""

    SUPPORTED = EvidenceState.SUPPORTED.value
    MEASURED_NEGATIVE = EvidenceState.MEASURED_NEGATIVE.value
    CONTRADICTORY = EvidenceState.CONTRADICTORY.value
    UNSUPPORTED = EvidenceState.UNSUPPORTED.value
    OUT_OF_DOMAIN = EvidenceState.OUT_OF_DOMAIN.value
    ABSTAINED = EvidenceState.ABSTAINED.value


@dataclass(frozen=True, slots=True)
class InferenceObservation:
    """Normalized evidence row accepted by an inference extension."""

    observation_id: str
    source_id: str
    channel: str
    state: EvidenceState
    score: float | None
    confidence: float
    context_score: float | None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("observation_id", "source_id", "channel"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"inference {name} is required")
        for name in ("score", "confidence", "context_score"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValidationError(f"inference {name} must be between 0 and 1")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_id: str,
        fallback_channel: str,
    ) -> InferenceObservation:
        if not isinstance(raw, Mapping):
            raise ValidationError("inference observation must be a mapping")
        state_raw = raw.get("state", EvidenceState.SUPPORTED.value)
        try:
            state = EvidenceState(str(state_raw))
        except ValueError as exc:
            raise ValidationError(f"unsupported inference evidence state: {state_raw}") from exc
        score_raw = raw.get("score", raw.get("support"))
        score = _optional_unit(score_raw, "score")
        confidence = _unit(raw.get("confidence", 1.0), "confidence")
        context_score = _optional_unit(
            raw.get("context_score", raw.get("context_match")),
            "context_score",
        )
        payload = raw.get("payload", raw)
        if not isinstance(payload, Mapping):
            raise ValidationError("inference observation payload must be a mapping")
        return cls(
            observation_id=str(raw.get("observation_id", raw.get("evidence_id", fallback_id))),
            source_id=str(raw.get("source_id", "declared_input")),
            channel=str(raw.get("channel", fallback_channel)),
            state=state,
            score=score,
            confidence=confidence,
            context_score=context_score,
            payload=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Common envelope for all extension-specific result payloads."""

    role_id: str
    state: InferenceState
    support: float | None
    uncertainty: float
    summary: str
    source_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    payload: Mapping[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        if not self.role_id.strip() or not self.summary.strip():
            raise ValidationError("inference result role_id and summary are required")
        if self.support is not None and not 0.0 <= self.support <= 1.0:
            raise ValidationError("inference result support must be between 0 and 1")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("inference result uncertainty must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MotifGrammarResult:
    """Sequence motif delta interpreted as an element grammar observation."""

    variant_id: str
    element_id: str
    state: InferenceState
    created_motif_ids: tuple[str, ...]
    disrupted_motif_ids: tuple[str, ...]
    grammar_change_score: float | None
    uncertainty: float
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AccessibilityDeltaResult:
    """Context-qualified accessibility change without a causal claim."""

    variant_id: str
    element_id: str
    state: InferenceState
    delta: float | None
    direction: str
    context_score: float | None
    support: float | None
    uncertainty: float
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyRewiringResult:
    """Contact change result retaining target identity and measurement state."""

    element_id: str
    target_id: str
    state: InferenceState
    contact_delta: float | None
    direction: str
    support: float | None
    uncertainty: float
    contact_observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkEvidenceResult:
    """A bounded link score with its explicit feature decomposition."""

    link_type: str
    source_id: str
    target_id: str
    state: InferenceState
    score: float | None
    features: Mapping[str, float]
    uncertainty: float
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleSpecificResult:
    """Allele comparison that keeps the measured values and effect direction."""

    variant_id: str
    state: InferenceState
    reference_value: float | None
    alternate_value: float | None
    delta: float | None
    direction: str
    support: float | None
    uncertainty: float
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MechanismEdgeResult:
    """Context-specific mechanism edge assembled from link observations."""

    source_id: str
    target_id: str
    state_id: str
    state: InferenceState
    support: float | None
    context_match: float | None
    link_ids: tuple[str, ...]
    uncertainty: float
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LongitudinalResult:
    """Timepoint comparison that distinguishes missing follow-up from stability."""

    variant_id: str
    state: InferenceState
    timepoints: tuple[str, ...]
    values: tuple[tuple[str, float], ...]
    delta: float | None
    direction: str
    support: float | None
    uncertainty: float
    missing_timepoints: tuple[str, ...]
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GermlineContextResult:
    """Origin classification transport with explicit inherited-context evidence."""

    variant_id: str
    origin: str
    state: InferenceState
    inherited_context: bool | None
    cohort_support: float | None
    uncertainty: float
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DriverPosteriorResult:
    """Declared-prior research posterior proxy, never a clinical probability."""

    hypothesis_id: str
    state: InferenceState
    declared_prior: float
    evidence_support: float | None
    posterior_proxy: float | None
    calibration_status: str
    uncertainty: float
    observation_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _unit(value: Any, field_name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc
    if not isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValidationError(f"{field_name} must be between 0 and 1")
    return result


def _optional_unit(value: Any, field_name: str) -> float | None:
    return None if value is None else _unit(value, field_name)


def _optional_number(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc
    if not isfinite(result):
        raise ValidationError(f"{field_name} must be finite")
    return result


def _text(value: Any, field_name: str, default: str = "") -> str:
    result = str(value if value is not None else default).strip()
    if not result:
        raise ValidationError(f"{field_name} is required")
    return result


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field_name} must be a mapping")
    return value


def _rows(value: Any, *, fallback_channel: str) -> tuple[InferenceObservation, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        raw_rows = value.get("observations", value.get("claims"))
        if raw_rows is None:
            raw_rows = (value,)
    elif isinstance(value, (list, tuple)):
        raw_rows = value
    else:
        raise ValidationError("evidence input must be a mapping or sequence")
    if not isinstance(raw_rows, (list, tuple)):
        raise ValidationError("observations must be a sequence")
    return tuple(
        InferenceObservation.from_mapping(
            _mapping(row, "observation"),
            fallback_id=f"observation-{index + 1}",
            fallback_channel=fallback_channel,
        )
        for index, row in enumerate(raw_rows)
    )


def _payload_value(row: InferenceObservation, *keys: str) -> Any:
    for key in keys:
        if key in row.payload:
            return row.payload[key]
    return None


def _number_from(row: InferenceObservation, *keys: str) -> float | None:
    return _optional_number(_payload_value(row, *keys), keys[0])


def _context_floor(rows: Iterable[InferenceObservation]) -> float | None:
    values = [row.context_score for row in rows if row.context_score is not None]
    return min(values) if values else None


def _context_gate(
    rows: Iterable[InferenceObservation], minimum: float = 0.35
) -> InferenceState | None:
    values = [row.context_score for row in rows if row.context_score is not None]
    if values and min(values) < minimum:
        return InferenceState.OUT_OF_DOMAIN
    return None


def _row_support(row: InferenceObservation) -> float | None:
    if row.state == EvidenceState.SUPPORTED:
        return row.score if row.score is not None else row.confidence
    if row.state == EvidenceState.MEASURED_NEGATIVE:
        return 0.0
    return None


def _mean(values: Iterable[float]) -> float | None:
    numbers = tuple(values)
    return None if not numbers else round(sum(numbers) / len(numbers), 6)


def _support_and_uncertainty(rows: Iterable[InferenceObservation]) -> tuple[float | None, float]:
    values = tuple(row for row in rows if _row_support(row) is not None)
    if not values:
        return None, 1.0
    support = _mean(_row_support(row) for row in values)
    confidence = _mean(row.confidence for row in values) or 0.0
    context_values = [row.context_score for row in values if row.context_score is not None]
    context_penalty = 1.0 - (min(context_values) if context_values else 0.5)
    uncertainty = min(
        1.0, round(0.45 * (1.0 - confidence) + 0.35 * context_penalty + 0.20 / len(values), 6)
    )
    return support, uncertainty


def _result_state(rows: Iterable[InferenceObservation], *, minimum: int = 1) -> InferenceState:
    values = tuple(rows)
    if len(values) < minimum:
        return InferenceState.ABSTAINED
    if any(row.state in {EvidenceState.OUT_OF_DOMAIN, EvidenceState.ABSTAINED} for row in values):
        return (
            InferenceState.OUT_OF_DOMAIN
            if any(row.state == EvidenceState.OUT_OF_DOMAIN for row in values)
            else InferenceState.ABSTAINED
        )
    if any(row.state == EvidenceState.CONTRADICTORY for row in values):
        return InferenceState.CONTRADICTORY
    if all(row.state == EvidenceState.MEASURED_NEGATIVE for row in values):
        return InferenceState.MEASURED_NEGATIVE
    if any(row.state == EvidenceState.UNSUPPORTED for row in values):
        return InferenceState.UNSUPPORTED
    return InferenceState.SUPPORTED


def _ids(rows: Iterable[InferenceObservation]) -> tuple[str, ...]:
    return tuple(row.observation_id for row in rows)


def _sources(rows: Iterable[InferenceObservation]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(row.source_id for row in rows))


def _direction(delta: float | None, *, tolerance: float = 1e-9) -> str:
    if delta is None:
        return "not_observed"
    if delta > tolerance:
        return "increased"
    if delta < -tolerance:
        return "decreased"
    return "unchanged_within_declared_precision"


def _address(value: Any) -> str:
    return content_hash(jsonable(value))


class InferenceExtensionSuite:
    """Execute transparent calculations for A24-A35 and A33."""

    def motif_grammar(
        self,
        sequence_evidence: Mapping[str, Any],
        candidate_element: Mapping[str, Any],
    ) -> MotifGrammarResult:
        sequence = _mapping(sequence_evidence, "sequence_evidence")
        element = _mapping(candidate_element, "candidate_element")
        rows = _rows(sequence, fallback_channel="motif_delta")
        if not rows and any(
            key in sequence for key in ("created_hits", "disrupted_hits", "motif_delta_count")
        ):
            rows = (
                InferenceObservation.from_mapping(
                    sequence,
                    fallback_id="sequence-analysis",
                    fallback_channel="motif_delta",
                ),
            )
        created = tuple(
            _text(hit.get("motif_id", hit.get("name", "unknown")), "motif_id")
            for hit in sequence.get("created_hits", ())
            if isinstance(hit, Mapping)
        )
        disrupted = tuple(
            _text(hit.get("motif_id", hit.get("name", "unknown")), "motif_id")
            for hit in sequence.get("disrupted_hits", ())
            if isinstance(hit, Mapping)
        )
        support, uncertainty = _support_and_uncertainty(rows)
        if rows and rows[0].score is None and (created or disrupted):
            support = min(1.0, (len(created) + len(disrupted)) / 4.0)
            uncertainty = min(1.0, 0.65 + 0.1 * (support == 0.0))
        state = _result_state(rows)
        if not rows:
            state = InferenceState.ABSTAINED
        limitations = [
            "Motif grammar is sequence-derived and does not establish occupancy or activity.",
            "A sequence delta is not an effect probability.",
        ]
        if not created and not disrupted:
            limitations.append("No created or disrupted motif hits were supplied.")
        payload = {
            "variant_id": _text(sequence.get("variant_id", "unresolved_variant"), "variant_id"),
            "element_id": _text(element.get("element_id", "unresolved_element"), "element_id"),
            "created_motif_ids": created,
            "disrupted_motif_ids": disrupted,
            "support": support,
            "state": state,
        }
        return MotifGrammarResult(
            variant_id=payload["variant_id"],
            element_id=payload["element_id"],
            state=state,
            created_motif_ids=created,
            disrupted_motif_ids=disrupted,
            grammar_change_score=support,
            uncertainty=uncertainty,
            limitations=tuple(limitations),
            content_address=_address(payload),
        )

    def accessibility_delta(
        self,
        sequence_evidence: Mapping[str, Any],
        chromatin_evidence: Mapping[str, Any],
    ) -> AccessibilityDeltaResult:
        sequence = _mapping(sequence_evidence, "sequence_evidence")
        chromatin = _mapping(chromatin_evidence, "chromatin_evidence")
        rows = _rows(chromatin, fallback_channel="chromatin_accessibility")
        sequence_rows = _rows(sequence, fallback_channel="sequence_delta")
        all_rows = rows + sequence_rows
        gated = _context_gate(all_rows)
        delta = None
        for row in rows:
            delta = _number_from(row, "delta", "accessibility_delta", "effect_size")
            if delta is None:
                reference = _number_from(row, "reference_accessibility", "reference_value")
                alternate = _number_from(row, "alternate_accessibility", "alternate_value")
                if reference is not None and alternate is not None:
                    delta = alternate - reference
            if delta is not None:
                break
        support, uncertainty = _support_and_uncertainty(rows)
        state = gated or _result_state(rows)
        if delta is None and state == InferenceState.SUPPORTED:
            state = InferenceState.UNSUPPORTED
            support = None
            uncertainty = 1.0
        if delta is not None:
            support = max(abs(delta), support or 0.0)
            uncertainty = min(1.0, uncertainty + 0.05 if len(rows) < 2 else uncertainty)
        limitations = [
            "Accessibility delta requires a declared chromatin measurement or effect estimate.",
            "Sequence evidence can motivate this comparison but cannot "
            "substitute for chromatin measurement.",
        ]
        if gated:
            limitations.append(
                "At least one supplied context score is below the transport threshold."
            )
        variant_id = _text(
            sequence.get("variant_id", chromatin.get("variant_id", "unresolved_variant")),
            "variant_id",
        )
        element_id = _text(
            chromatin.get("element_id", sequence.get("element_id", "unresolved_element")),
            "element_id",
        )
        payload = {
            "variant_id": variant_id,
            "element_id": element_id,
            "delta": delta,
            "state": state,
            "rows": _ids(rows),
        }
        return AccessibilityDeltaResult(
            variant_id=variant_id,
            element_id=element_id,
            state=state,
            delta=None if delta is None else round(delta, 6),
            direction=_direction(delta),
            context_score=_context_floor(all_rows),
            support=None if support is None else round(min(1.0, abs(support)), 6),
            uncertainty=round(uncertainty, 6),
            observation_ids=_ids(all_rows),
            limitations=tuple(limitations),
            content_address=_address(payload),
        )

    def topology_rewiring(
        self,
        contact_evidence: Mapping[str, Any],
        candidate_element: Mapping[str, Any],
    ) -> TopologyRewiringResult:
        contact = _mapping(contact_evidence, "contact_evidence")
        element = _mapping(candidate_element, "candidate_element")
        rows = _rows(contact, fallback_channel="contact")
        gated = _context_gate(rows)
        deltas = tuple(
            value
            for row in rows
            for value in (_number_from(row, "contact_delta", "delta", "effect_size"),)
            if value is not None
        )
        delta = _mean(deltas)
        support, uncertainty = _support_and_uncertainty(rows)
        if delta is not None:
            support = max(abs(delta), support or 0.0)
        state = gated or _result_state(rows)
        target_id = _text(
            contact.get(
                "target_id", contact.get("gene_id", element.get("target_gene", "unresolved_target"))
            ),
            "target_id",
        )
        element_id = _text(
            element.get("element_id", contact.get("element_id", "unresolved_element")), "element_id"
        )
        limitations = (
            "Contact rewiring is conditional on the supplied contact assay and mapping context.",
            "A contact change does not by itself establish regulatory direction or gene causality.",
        )
        payload = {
            "element_id": element_id,
            "target_id": target_id,
            "delta": delta,
            "state": state,
            "rows": _ids(rows),
        }
        return TopologyRewiringResult(
            element_id=element_id,
            target_id=target_id,
            state=state,
            contact_delta=delta,
            direction=_direction(delta),
            support=None if support is None else round(min(1.0, abs(support)), 6),
            uncertainty=round(uncertainty, 6),
            contact_observation_ids=_ids(rows),
            limitations=limitations + (("Contact context is out of domain.",) if gated else ()),
            content_address=_address(payload),
        )

    def variant_element_link(
        self,
        canonical_variant: Mapping[str, Any],
        candidate_element: Mapping[str, Any],
    ) -> LinkEvidenceResult:
        variant = _mapping(canonical_variant, "canonical_variant")
        element = _mapping(candidate_element, "candidate_element")
        variant_id = _text(variant.get("variant_id", "variant"), "variant_id")
        element_id = _text(element.get("element_id", "element"), "element_id")
        features: dict[str, float] = {}
        for key in ("link_score", "overlap_score", "distance_score", "context_score"):
            value = _optional_unit(
                element.get(
                    key,
                    element.get("annotations", {}).get(key)
                    if isinstance(element.get("annotations"), Mapping)
                    else None,
                ),
                key,
            )
            if value is not None:
                features[key] = value
        if not features:
            variant_chromosome = variant.get("chromosome")
            element_chromosome = element.get("chromosome")
            start = _optional_number(variant.get("start"), "variant.start")
            end = _optional_number(element.get("end"), "element.end")
            element_start = _optional_number(element.get("start"), "element.start")
            if (
                variant_chromosome
                and element_chromosome
                and variant_chromosome == element_chromosome
                and start is not None
                and end is not None
                and element_start is not None
            ):
                distance = (
                    0.0
                    if element_start <= start <= end
                    else min(abs(start - element_start), abs(start - end))
                )
                features["distance_score"] = round(max(0.0, 1.0 - distance / 1_000_000.0), 6)
        score = _mean(features.values())
        state = InferenceState.SUPPORTED if score is not None else InferenceState.ABSTAINED
        uncertainty = 0.35 if "link_score" in features else 0.65 if score is not None else 1.0
        limitations = (
            "Variant-element linkage is a bounded contextual score, not proof "
            "of allele-dependent regulation.",
            "Distance and overlap features are priors unless supported by a "
            "functional or contact observation.",
        )
        payload = {
            "variant_id": variant_id,
            "element_id": element_id,
            "features": features,
            "score": score,
            "state": state,
        }
        return LinkEvidenceResult(
            link_type="variant_to_element",
            source_id=variant_id,
            target_id=element_id,
            state=state,
            score=score,
            features=features,
            uncertainty=uncertainty,
            observation_ids=(),
            limitations=limitations,
            content_address=_address(payload),
        )

    def element_gene_link(
        self,
        candidate_element: Mapping[str, Any],
        contact_evidence: Mapping[str, Any],
    ) -> LinkEvidenceResult:
        element = _mapping(candidate_element, "candidate_element")
        contact = _mapping(contact_evidence, "contact_evidence")
        element_id = _text(element.get("element_id", "element"), "element_id")
        genes = element.get("target_genes", ())
        if isinstance(genes, str):
            genes = (genes,)
        if not isinstance(genes, (list, tuple)):
            raise ValidationError("candidate_element.target_genes must be a sequence")
        target_id = _text(
            contact.get(
                "target_gene", contact.get("gene_id", genes[0] if genes else "unresolved_gene")
            ),
            "target_gene",
        )
        rows = _rows(contact, fallback_channel="contact")
        matching = tuple(
            row
            for row in rows
            if _payload_value(row, "target_gene", "gene_id") in {None, target_id}
        )
        support, uncertainty = _support_and_uncertainty(matching)
        annotations = element.get("annotations", {})
        if support is None and isinstance(annotations, Mapping):
            support = _optional_unit(annotations.get("link_confidence"), "link_confidence")
            if support is not None:
                uncertainty = 0.65
        gated = _context_gate(matching)
        state = gated or (
            InferenceState.SUPPORTED if support is not None else InferenceState.ABSTAINED
        )
        limitations = (
            "Element-gene linkage retains the nominated target and supporting contact rows.",
            "Nearest-gene proximity alone is not treated as a gene-link measurement.",
        )
        payload = {
            "element_id": element_id,
            "target_id": target_id,
            "support": support,
            "state": state,
            "rows": _ids(matching),
        }
        return LinkEvidenceResult(
            link_type="element_to_gene",
            source_id=element_id,
            target_id=target_id,
            state=state,
            score=None if support is None else round(support, 6),
            features={"contact_observation_count": float(len(matching))},
            uncertainty=round(uncertainty, 6),
            observation_ids=_ids(matching),
            limitations=limitations + (("Contact context is out of domain.",) if gated else ()),
            content_address=_address(payload),
        )

    def allele_specific(
        self,
        canonical_variant: Mapping[str, Any],
        functional_evidence: Mapping[str, Any],
    ) -> AlleleSpecificResult:
        variant = _mapping(canonical_variant, "canonical_variant")
        functional = _mapping(functional_evidence, "functional_evidence")
        rows = _rows(functional, fallback_channel="functional")
        reference_values: list[float] = []
        alternate_values: list[float] = []
        for row in rows:
            allele = str(_payload_value(row, "allele", "haplotype", "allele_label") or "").lower()
            value = _number_from(row, "value", "activity", "expression", "effect_size")
            if value is None:
                continue
            if allele in {"ref", "reference", str(variant.get("reference", "")).lower()}:
                reference_values.append(value)
            elif allele in {"alt", "alternate", str(variant.get("alternate", "")).lower()}:
                alternate_values.append(value)
        reference = _mean(reference_values)
        alternate = _mean(alternate_values)
        delta = None if reference is None or alternate is None else round(alternate - reference, 6)
        support, uncertainty = _support_and_uncertainty(rows)
        if delta is None:
            state = _result_state(rows, minimum=2) if rows else InferenceState.ABSTAINED
            limitations = (
                "Reference and alternate allele measurements are both "
                "required for an allele-specific comparison.",
            )
            support = None
            uncertainty = 1.0
        else:
            state = _result_state(rows, minimum=2)
            support = min(1.0, abs(delta))
            limitations = (
                "Allele-specific delta preserves assay values but does not "
                "establish mechanism or clinical effect.",
            )
        variant_id = _text(variant.get("variant_id", "variant"), "variant_id")
        payload = {
            "variant_id": variant_id,
            "reference": reference,
            "alternate": alternate,
            "delta": delta,
            "state": state,
            "rows": _ids(rows),
        }
        return AlleleSpecificResult(
            variant_id=variant_id,
            state=state,
            reference_value=reference,
            alternate_value=alternate,
            delta=delta,
            direction=_direction(delta),
            support=support,
            uncertainty=uncertainty,
            observation_ids=_ids(rows),
            limitations=limitations,
            content_address=_address(payload),
        )

    def cell_state_mechanism(
        self,
        link_evidence: Mapping[str, Any],
        cell_state_annotation: Mapping[str, Any],
    ) -> MechanismEdgeResult:
        links = _rows(link_evidence, fallback_channel="link")
        annotation = _mapping(cell_state_annotation, "cell_state_annotation")
        state_id = _text(
            annotation.get("state_id", annotation.get("cell_state", "unresolved_state")), "state_id"
        )
        target_id = _text(
            annotation.get("gene_id", annotation.get("target_id", "unresolved_gene")), "target_id"
        )
        source_id = _text(
            annotation.get("element_id", annotation.get("source_id", "unresolved_element")),
            "source_id",
        )
        matching = tuple(
            row
            for row in links
            if _payload_value(row, "state_id", "cell_state") in {None, state_id}
            and _payload_value(row, "target_id", "gene_id") in {None, target_id}
        )
        gated = _context_gate(matching)
        support, uncertainty = _support_and_uncertainty(matching)
        state = gated or (
            InferenceState.SUPPORTED if support is not None else InferenceState.ABSTAINED
        )
        limitations = (
            "Mechanism edges are context-specific assemblies of supplied "
            "links, not mechanistic proof.",
            "Cell-state labels must be defined by the upstream annotation source.",
        )
        payload = {
            "source_id": source_id,
            "target_id": target_id,
            "state_id": state_id,
            "support": support,
            "state": state,
            "rows": _ids(matching),
        }
        return MechanismEdgeResult(
            source_id=source_id,
            target_id=target_id,
            state_id=state_id,
            state=state,
            support=support,
            context_match=_context_floor(matching),
            link_ids=_ids(matching),
            uncertainty=uncertainty,
            limitations=limitations + (("Mechanism context is out of domain.",) if gated else ()),
            content_address=_address(payload),
        )

    def longitudinal(
        self,
        origin_assessment: Mapping[str, Any],
        functional_evidence: Mapping[str, Any],
    ) -> LongitudinalResult:
        origin = _mapping(origin_assessment, "origin_assessment")
        functional = _mapping(functional_evidence, "functional_evidence")
        rows = _rows(functional, fallback_channel="longitudinal_function")
        by_time: dict[str, list[float]] = {}
        for row in rows:
            timepoint = _payload_value(row, "timepoint", "visit", "collection_time")
            value = _number_from(row, "value", "activity", "expression", "effect_size")
            if timepoint is not None and value is not None:
                by_time.setdefault(str(timepoint), []).append(value)
        ordered = tuple(sorted(by_time))
        values = tuple((timepoint, _mean(by_time[timepoint]) or 0.0) for timepoint in ordered)
        delta = None if len(values) < 2 else round(values[-1][1] - values[0][1], 6)
        state = _result_state(rows, minimum=2) if len(values) >= 2 else InferenceState.ABSTAINED
        support, uncertainty = _support_and_uncertainty(rows)
        if delta is not None:
            support = min(1.0, abs(delta))
        variant_id = _text(
            origin.get("variant_id", functional.get("variant_id", "variant")), "variant_id"
        )
        limitations = [
            "Longitudinal comparison requires at least two measured timepoints.",
            "Missing timepoints are not interpreted as negative observations.",
            "Origin and clonality metadata are retained as context, not used "
            "to impute measurements.",
        ]
        if len(values) == 1:
            limitations.append("Only one measured timepoint was supplied.")
        payload = {
            "variant_id": variant_id,
            "values": values,
            "delta": delta,
            "state": state,
            "rows": _ids(rows),
        }
        return LongitudinalResult(
            variant_id=variant_id,
            state=state,
            timepoints=ordered,
            values=values,
            delta=delta,
            direction=_direction(delta),
            support=support if delta is not None else None,
            uncertainty=uncertainty if delta is not None else 1.0,
            missing_timepoints=tuple(
                str(item) for item in functional.get("missing_timepoints", ())
            ),
            observation_ids=_ids(rows),
            limitations=tuple(limitations),
            content_address=_address(payload),
        )

    def germline_context(
        self,
        origin_assessment: Mapping[str, Any],
        cohort_record: Mapping[str, Any],
    ) -> GermlineContextResult:
        origin = _mapping(origin_assessment, "origin_assessment")
        cohort = _mapping(cohort_record, "cohort_record")
        rows = _rows(cohort, fallback_channel="cohort_origin")
        origin_label = str(origin.get("origin", "uncertain")).lower()
        inherited_raw = cohort.get("inherited_context", cohort.get("present_in_normal"))
        inherited = None if inherited_raw is None else bool(inherited_raw)
        support_values = [row.score for row in rows if row.score is not None]
        cohort_support = _mean(support_values)
        if inherited is True or origin_label == "germline":
            state = InferenceState.SUPPORTED
        elif inherited is False or origin_label == "somatic":
            state = (
                InferenceState.MEASURED_NEGATIVE if inherited is False else InferenceState.SUPPORTED
            )
        else:
            state = InferenceState.ABSTAINED
        if rows:
            row_state = _result_state(rows)
            if row_state in {InferenceState.OUT_OF_DOMAIN, InferenceState.CONTRADICTORY}:
                state = row_state
        uncertainty = 0.25 if inherited is not None else 0.75
        if origin_label == "uncertain":
            uncertainty = min(1.0, uncertainty + 0.15)
        variant_id = _text(
            origin.get("variant_id", cohort.get("variant_id", "variant")), "variant_id"
        )
        limitations = (
            "Germline context separates inherited observations from the somatic research path.",
            "Absence of a normal observation is not equivalent to proof of somatic origin.",
        )
        payload = {
            "variant_id": variant_id,
            "origin": origin_label,
            "inherited": inherited,
            "state": state,
            "rows": _ids(rows),
        }
        return GermlineContextResult(
            variant_id=variant_id,
            origin=origin_label,
            state=state,
            inherited_context=inherited,
            cohort_support=cohort_support,
            uncertainty=uncertainty,
            observation_ids=_ids(rows),
            limitations=limitations,
            content_address=_address(payload),
        )

    def driver_posterior(
        self,
        causal_lattice: Mapping[str, Any],
        evidence_envelope: Mapping[str, Any],
    ) -> DriverPosteriorResult:
        lattice = _mapping(causal_lattice, "causal_lattice")
        envelope = _mapping(evidence_envelope, "evidence_envelope")
        prior = _unit(lattice.get("declared_prior", lattice.get("prior")), "declared_prior")
        support = _optional_unit(
            lattice.get("support", envelope.get("support", envelope.get("score"))),
            "evidence_support",
        )
        if support is None:
            state = InferenceState.ABSTAINED
            posterior = None
            uncertainty = 1.0
        else:
            odds_prior = prior / max(1e-9, 1.0 - prior)
            odds_evidence = support / max(1e-9, 1.0 - support)
            posterior = round((odds_prior * odds_evidence) / (1.0 + odds_prior * odds_evidence), 6)
            state = InferenceState.SUPPORTED if support > 0.0 else InferenceState.MEASURED_NEGATIVE
            uncertainty = round(min(1.0, 0.55 + 0.35 * abs(0.5 - support)), 6)
        hypothesis_id = _text(
            lattice.get("hypothesis_id", envelope.get("hypothesis_id", "hypothesis")),
            "hypothesis_id",
        )
        observation_ids = tuple(
            str(value)
            for value in (
                lattice.get("path_id", lattice.get("causal_path_id", "causal-lattice")),
                envelope.get("evidence_id", envelope.get("source_id", "evidence-envelope")),
            )
        )
        limitations = (
            "This posterior is a declared-prior research proxy, not a "
            "calibrated clinical probability.",
            "The supplied support is treated as a bounded likelihood proxy "
            "only because the contract declares it.",
            "Calibration requires held-out evaluation against an explicit reference set.",
        )
        payload = {
            "hypothesis_id": hypothesis_id,
            "prior": prior,
            "support": support,
            "posterior": posterior,
            "state": state,
        }
        return DriverPosteriorResult(
            hypothesis_id=hypothesis_id,
            state=state,
            declared_prior=prior,
            evidence_support=support,
            posterior_proxy=posterior,
            calibration_status="unvalidated_research_proxy",
            uncertainty=uncertainty,
            observation_ids=observation_ids,
            limitations=limitations,
            content_address=_address(payload),
        )


def result_to_envelope_payload(result: Any) -> Mapping[str, Any]:
    """Expose a stable payload for a control-plane envelope without raw inputs."""

    if not hasattr(result, "to_dict"):
        raise ValidationError("inference result must implement to_dict")
    return result.to_dict()

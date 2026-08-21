"""Context-preserving disease, age, molecular, and territory resolution.

Domain 08 is the biological-context boundary.  It converts declared metadata
and source-scoped taxonomy observations into a ``GliomaStateContext`` while
keeping context transport, ambiguity, contradictory evidence, and missingness
visible.  The module deliberately does not diagnose a case or infer a clinical
state from a generic score.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from statistics import mean
from typing import Any

from .errors import ValidationError
from .models import EvidenceState, ReferenceContext
from .serialization import content_hash, jsonable


class ContextDimension(StrEnum):
    """Typed dimensions emitted by the Domain 08 contextualizers."""

    DISEASE_ONTOLOGY = "disease_ontology"
    AGE_ROUTE = "age_route"
    MOLECULAR_CLASS = "molecular_class"
    MOLECULAR_STATE = "molecular_state"
    TERRITORY = "territory"


class ContextResolutionState(StrEnum):
    """Resolution state with no implicit negative-evidence interpretation."""

    SUPPORTED = "supported"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class ContextIssue:
    """A parser issue retained alongside accepted context observations."""

    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = "Inspect the source row and resolve the context contract before reuse."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextObservation:
    """One source-scoped candidate term for a declared reference context."""

    observation_id: str
    subject_id: str
    dimension: ContextDimension
    candidate_id: str
    candidate_label: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    state: EvidenceState = EvidenceState.SUPPORTED
    confidence: float = 1.0
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "subject_id",
            "candidate_id",
            "candidate_label",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"context observation {name} is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("context observation confidence must be between 0 and 1")

    def matches(self, context: ReferenceContext) -> bool:
        """Return true only for an exact context key, never a guessed transport."""

        return self.context_key == context.key

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextObservationBatch:
    """Accepted observations plus quarantined rows and source receipts."""

    source_id: str
    input_hash: str
    observations: tuple[ContextObservation, ...]
    issues: tuple[ContextIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContextObservationParser:
    """Parse context observations from a stable TSV or JSON interchange form."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        input_format: str | None = None,
    ) -> ContextObservationBatch:
        if not source_id.strip():
            raise ValidationError("context source_id is required")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("context input must not be empty")
        first = next(line.strip() for line in text.splitlines() if line.strip())
        selected = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid context JSON: {exc}") from exc
            rows = payload.get("observations", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("context JSON must contain an observations list")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("context TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported context format: {selected}")

        observations: list[ContextObservation] = []
        issues: list[ContextIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(ContextIssue("invalid_context_row", "row must be an object"))
                continue
            raw_hash = content_hash(row)
            try:
                dimension = ContextDimension(
                    str(self._value(row, "dimension", "context_dimension"))
                )
                state = EvidenceState(
                    str(self._value(row, "state", default=EvidenceState.SUPPORTED.value))
                )
                observations.append(
                    ContextObservation(
                        observation_id=str(
                            self._value(
                                row,
                                "observation_id",
                                "evidence_id",
                                default=f"{source_id}:{index}",
                            )
                        ),
                        subject_id=str(
                            self._value(row, "subject_id", "sample_id", default="unspecified")
                        ),
                        dimension=dimension,
                        candidate_id=str(
                            self._value(row, "candidate_id", "term_id", "key")
                        ),
                        candidate_label=str(
                            self._value(row, "candidate_label", "label", default="unspecified")
                        ),
                        context_key=str(self._value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                        raw_hash=raw_hash,
                        state=state,
                        confidence=float(self._value(row, "confidence", "score", default=1.0)),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ContextIssue(
                        "invalid_context_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "observations": tuple(observations),
            "issues": tuple(issues),
        }
        return ContextObservationBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        if default is not None:
            return default
        raise ValidationError(f"context field is required: {names[0]}")


@dataclass(frozen=True, slots=True)
class ContextCandidate:
    """Grouped candidate support used in a resolution result."""

    candidate_id: str
    candidate_label: str
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    mean_confidence: float
    observation_count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextResolution:
    """One context dimension resolved without discarding alternative candidates."""

    dimension: ContextDimension
    context_key: str
    state: ContextResolutionState
    selected_candidate_id: str | None
    selected_candidate_label: str | None
    candidates: tuple[ContextCandidate, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    uncertainty: float
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("context resolution uncertainty must be between 0 and 1")
        if self.selected_candidate_id is not None and self.selected_candidate_id not in {
            candidate.candidate_id for candidate in self.candidates
        }:
            raise ValidationError("selected context candidate must be present in candidates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _resolve_dimension(
    dimension: ContextDimension,
    context: ReferenceContext,
    observations: Iterable[ContextObservation],
    subject_id: str,
) -> ContextResolution:
    if not subject_id.strip():
        raise ValidationError("context subject_id is required")
    rows = tuple(
        row
        for row in observations
        if row.dimension == dimension
        and row.subject_id in {subject_id, "unspecified"}
    )
    matched = tuple(row for row in rows if row.matches(context))
    if not matched:
        state = ContextResolutionState.OUT_OF_DOMAIN if rows else ContextResolutionState.ABSTAINED
        reason = (
            "observations exist, but none match the exact target context"
            if rows
            else "no observations were supplied for this context dimension"
        )
        body = {"dimension": dimension, "context": context, "state": state, "rows": rows}
        return ContextResolution(
            dimension=dimension,
            context_key=context.key,
            state=state,
            selected_candidate_id=None,
            selected_candidate_label=None,
            candidates=(),
            evidence_ids=tuple(row.observation_id for row in rows),
            source_ids=tuple(sorted({row.source_id for row in rows})),
            uncertainty=1.0,
            reason=reason,
            limitations=(
                "Missing or context-mismatched observations are not treated as negative evidence.",
            ),
            content_address=content_hash(body),
        )

    contradictory = tuple(row for row in matched if row.state == EvidenceState.CONTRADICTORY)
    usable = tuple(row for row in matched if row.state == EvidenceState.SUPPORTED)
    grouped: dict[str, list[ContextObservation]] = defaultdict(list)
    for row in usable:
        grouped[row.candidate_id].append(row)
    candidates = tuple(
        ContextCandidate(
            candidate_id=candidate_id,
            candidate_label=values[0].candidate_label,
            evidence_ids=tuple(item.observation_id for item in values),
            source_ids=tuple(sorted({item.source_id for item in values})),
            mean_confidence=round(mean(item.confidence for item in values), 6),
            observation_count=len(values),
        )
        for candidate_id, values in sorted(grouped.items())
    )
    if contradictory:
        state = ContextResolutionState.CONTRADICTORY
        selected_id = None
        selected_label = None
        reason = "contradictory context observations were supplied"
        uncertainty = 1.0
    elif not candidates:
        state = ContextResolutionState.ABSTAINED
        selected_id = None
        selected_label = None
        reason = "matched rows contain no positive context support"
        uncertainty = 1.0
    elif len(candidates) > 1:
        state = ContextResolutionState.AMBIGUOUS
        selected_id = None
        selected_label = None
        reason = "multiple positive context candidates remain after exact context gating"
        uncertainty = min(1.0, 0.75 + 0.05 * len(candidates))
    else:
        state = ContextResolutionState.SUPPORTED
        selected_id = candidates[0].candidate_id
        selected_label = candidates[0].candidate_label
        reason = "one positive context candidate remains after exact context gating"
        uncertainty = 1.0 - candidates[0].mean_confidence
        if len(candidates[0].source_ids) == 1:
            uncertainty = min(1.0, uncertainty + 0.1)
    body = {
        "dimension": dimension,
        "context": context,
        "state": state,
        "selected": selected_id,
        "candidates": candidates,
        "matched": matched,
    }
    return ContextResolution(
        dimension=dimension,
        context_key=context.key,
        state=state,
        selected_candidate_id=selected_id,
        selected_candidate_label=selected_label,
        candidates=candidates,
        evidence_ids=tuple(row.observation_id for row in matched),
        source_ids=tuple(sorted({row.source_id for row in matched})),
        uncertainty=round(uncertainty, 6),
        reason=reason,
        limitations=(
            "Context resolution is a research taxonomy observation, not a diagnosis or prognosis.",
            "External calibration, transport, and out-of-domain evaluation remain required.",
        ),
        content_address=content_hash(body),
    )


class DiseaseOntologyContextualizer:
    """Resolve a disease ontology candidate only within the target context."""

    def resolve(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextObservation],
        *,
        subject_id: str = "unspecified",
    ) -> ContextResolution:
        return _resolve_dimension(
            ContextDimension.DISEASE_ONTOLOGY, context, observations, subject_id
        )


class AdultPediatricRouter:
    """Route declared adult or pediatric context without guessing an age group."""

    _SUPPORTED = {"adult", "pediatric"}

    def route(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextObservation] = (),
        *,
        subject_id: str = "unspecified",
    ) -> ContextResolution:
        declared = context.age_group.strip().lower()
        observed = _resolve_dimension(
            ContextDimension.AGE_ROUTE, context, observations, subject_id
        )
        if declared not in self._SUPPORTED:
            return replace(
                observed,
                dimension=ContextDimension.AGE_ROUTE,
                reason="age group is missing or outside the supported adult/pediatric routes",
                limitations=observed.limitations
                + ("No age route is inferred from disease or molecular metadata.",),
                content_address=content_hash(
                    {"context": context, "declared": declared, "state": "abstained"}
                ),
                state=ContextResolutionState.ABSTAINED,
                selected_candidate_id=None,
                selected_candidate_label=None,
                candidates=(),
                uncertainty=1.0,
            )
        declared_candidate = ContextCandidate(
            candidate_id=declared,
            candidate_label=declared,
            evidence_ids=observed.evidence_ids,
            source_ids=tuple(sorted(set(observed.source_ids) | {"case-context"})),
            mean_confidence=1.0,
            observation_count=max(1, len(observed.evidence_ids)),
        )
        if observed.state == ContextResolutionState.CONTRADICTORY or (
            observed.state == ContextResolutionState.SUPPORTED
            and observed.selected_candidate_id != declared
        ):
            state = ContextResolutionState.CONTRADICTORY
            selected_id = None
            selected_label = None
            reason = "declared age route conflicts with context evidence"
        elif observed.state == ContextResolutionState.AMBIGUOUS:
            state = ContextResolutionState.AMBIGUOUS
            selected_id = None
            selected_label = None
            reason = "context evidence leaves multiple age routes despite a declared route"
        else:
            state = ContextResolutionState.SUPPORTED
            selected_id = declared
            selected_label = declared
            reason = "adult/pediatric route is taken from the declared reference context"
        body = {
            "context": context,
            "declared": declared,
            "observed": observed,
            "state": state,
        }
        return ContextResolution(
            dimension=ContextDimension.AGE_ROUTE,
            context_key=context.key,
            state=state,
            selected_candidate_id=selected_id,
            selected_candidate_label=selected_label,
            candidates=(declared_candidate,) if selected_id else observed.candidates,
            evidence_ids=observed.evidence_ids,
            source_ids=declared_candidate.source_ids,
            uncertainty=0.0 if state == ContextResolutionState.SUPPORTED else 1.0,
            reason=reason,
            limitations=(
                "Adult/pediatric routing is a context partition and not a disease conclusion.",
                "Adolescent, mixed-age, and unknown cohorts require an explicit extension.",
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class MolecularClassStateResolution:
    """Separate molecular class and state resolutions with a combined state."""

    context_key: str
    state: ContextResolutionState
    molecular_class: ContextResolution
    molecular_state: ContextResolution
    uncertainty: float
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MolecularClassStateContextualizer:
    """Resolve molecular class/state observations without manufacturing absence."""

    def resolve(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextObservation],
        *,
        subject_id: str = "unspecified",
    ) -> MolecularClassStateResolution:
        values = tuple(observations)
        molecular_class = _resolve_dimension(
            ContextDimension.MOLECULAR_CLASS, context, values, subject_id
        )
        molecular_state = _resolve_dimension(
            ContextDimension.MOLECULAR_STATE, context, values, subject_id
        )
        components = (molecular_class, molecular_state)
        if any(item.state == ContextResolutionState.CONTRADICTORY for item in components):
            state = ContextResolutionState.CONTRADICTORY
        elif any(item.state == ContextResolutionState.OUT_OF_DOMAIN for item in components):
            state = ContextResolutionState.OUT_OF_DOMAIN
        elif any(item.state == ContextResolutionState.AMBIGUOUS for item in components):
            state = ContextResolutionState.AMBIGUOUS
        elif all(item.state == ContextResolutionState.SUPPORTED for item in components):
            state = ContextResolutionState.SUPPORTED
        else:
            state = ContextResolutionState.ABSTAINED
        body = {
            "context": context,
            "state": state,
            "molecular_class": molecular_class,
            "molecular_state": molecular_state,
        }
        return MolecularClassStateResolution(
            context_key=context.key,
            state=state,
            molecular_class=molecular_class,
            molecular_state=molecular_state,
            uncertainty=round(mean(item.uncertainty for item in components), 6),
            limitations=(
                "Molecular context rows are descriptive and do not assert pathogenicity "
                "or treatment actionability.",
                "Unmeasured molecular class or state remains abstained, not negative.",
            ),
            content_address=content_hash(body),
        )


class MalignantMicroenvironmentTerritoryResolver:
    """Resolve territory candidates while exposing one-to-many identity mappings."""

    def resolve(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextObservation],
        *,
        subject_id: str = "unspecified",
    ) -> ContextResolution:
        return _resolve_dimension(ContextDimension.TERRITORY, context, observations, subject_id)


@dataclass(frozen=True, slots=True)
class GliomaStateContext:
    """Assembled Domain 08 output used by downstream context-gated planes."""

    subject_id: str
    context: ReferenceContext
    state: ContextResolutionState
    disease: ContextResolution
    age_route: ContextResolution
    molecular: MolecularClassStateResolution
    territory: ContextResolution
    uncertainty: float
    source_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not self.subject_id.strip():
            raise ValidationError("glioma state context subject_id is required")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("glioma state context uncertainty must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CellStateContextAssembler:
    """Compose four typed resolutions without hiding the weakest component."""

    def assemble(
        self,
        subject_id: str,
        context: ReferenceContext,
        disease: ContextResolution,
        age_route: ContextResolution,
        molecular: MolecularClassStateResolution,
        territory: ContextResolution,
    ) -> GliomaStateContext:
        if not subject_id.strip():
            raise ValidationError("subject_id is required")
        components = (
            disease,
            age_route,
            molecular.molecular_class,
            molecular.molecular_state,
            territory,
        )
        states = tuple(item.state for item in components) + (molecular.state,)
        if ContextResolutionState.CONTRADICTORY in states:
            state = ContextResolutionState.CONTRADICTORY
        elif ContextResolutionState.OUT_OF_DOMAIN in states:
            state = ContextResolutionState.OUT_OF_DOMAIN
        elif ContextResolutionState.AMBIGUOUS in states:
            state = ContextResolutionState.AMBIGUOUS
        elif all(item == ContextResolutionState.SUPPORTED for item in states):
            state = ContextResolutionState.SUPPORTED
        else:
            state = ContextResolutionState.ABSTAINED
        source_ids = tuple(
            sorted(
                {
                    source_id
                    for resolution in (disease, age_route, territory)
                    for source_id in resolution.source_ids
                }
                | set(molecular.molecular_class.source_ids)
                | set(molecular.molecular_state.source_ids)
            )
        )
        uncertainty = round(
            mean(
                [
                    disease.uncertainty,
                    age_route.uncertainty,
                    molecular.uncertainty,
                    territory.uncertainty,
                ]
            ),
            6,
        )
        limitations = (
            "This context bundle is for research use and is not a clinical diagnosis, "
            "prognosis, or treatment recommendation.",
            "Generic context scores are not proof; external benchmark, calibration, "
            "transport, and OOD evaluation remain required.",
            "No component infers consent, identity, assay support, or negative evidence "
            "when it is missing.",
        )
        body = {
            "subject_id": subject_id,
            "context": context,
            "state": state,
            "disease": disease,
            "age_route": age_route,
            "molecular": molecular,
            "territory": territory,
            "source_ids": source_ids,
        }
        return GliomaStateContext(
            subject_id=subject_id,
            context=context,
            state=state,
            disease=disease,
            age_route=age_route,
            molecular=molecular,
            territory=territory,
            uncertainty=uncertainty,
            source_ids=source_ids,
            limitations=limitations,
            content_address=content_hash(body),
        )


__all__ = [
    "AdultPediatricRouter",
    "CellStateContextAssembler",
    "ContextCandidate",
    "ContextDimension",
    "ContextIssue",
    "ContextObservation",
    "ContextObservationBatch",
    "ContextObservationParser",
    "ContextResolution",
    "ContextResolutionState",
    "DiseaseOntologyContextualizer",
    "GliomaStateContext",
    "MalignantMicroenvironmentTerritoryResolver",
    "MolecularClassStateContextualizer",
    "MolecularClassStateResolution",
]

"""Scientific-beta context priors for lineage and malignant cell-state evidence.

These priors aggregate declared, context-qualified observations into bounded
support scores. They keep evidence candidates, uncertainty, applicability,
and ambiguity visible; a selected candidate is a research prior output, not a
diagnosis, prognosis, treatment recommendation, or calibrated probability.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable, require_non_empty


class CellContextBetaState(StrEnum):
    """State returned by a context-prior operation."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class PriorObservationState(StrEnum):
    """State attached to a source observation before aggregation."""

    SUPPORTED = "supported"
    CONTRADICTORY = "contradictory"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class CellContextBetaIssue:
    """Parser or model issue retained with raw input provenance."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("cell context issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("cell context issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextPriorObservation:
    """One source-qualified candidate signal for a biological-context prior."""

    observation_id: str
    subject_id: str
    candidate_id: str
    candidate_label: str
    context_key: str
    support: float
    uncertainty: float
    source_id: str
    source_version: str
    raw_hash: str
    state: PriorObservationState = PriorObservationState.SUPPORTED
    evidence_tier: str = "declared"
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
            "evidence_tier",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1:
            raise ValidationError("context prior support must be between zero and one")
        if not 0 <= self.uncertainty <= 1:
            raise ValidationError("context prior uncertainty must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextPriorObservationBatch:
    """Accepted context-prior observations and quarantined rows."""

    source_id: str
    input_hash: str
    observations: tuple[ContextPriorObservation, ...]
    issues: tuple[CellContextBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ContextPriorObservationParser:
    """Parse JSON or TSV prior observations with lossless row quarantine."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> ContextPriorObservationBatch:
        require_non_empty(source_id, "source_id")
        require_non_empty(source_version, "source_version")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("context prior input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid context prior JSON: {exc}") from exc
            if isinstance(payload, Mapping):
                rows = payload.get("observations", payload.get("records", payload))
                if isinstance(rows, Mapping) and "candidate_id" in rows:
                    rows = [rows]
            else:
                rows = payload
            if not isinstance(rows, list):
                raise ValidationError("context prior JSON must contain an observations list")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("context prior TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported context prior format: {selected}")

        observations: list[ContextPriorObservation] = []
        issues: list[CellContextBetaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    CellContextBetaIssue(
                        "invalid_context_prior_row",
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
                    ContextPriorObservation(
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
                        candidate_id=str(self._value(row, "candidate_id", "term_id")),
                        candidate_label=str(
                            self._value(row, "candidate_label", "label", default="unspecified")
                        ),
                        context_key=str(self._value(row, "context_key", "context")),
                        support=float(self._value(row, "support", "score", default=1.0)),
                        uncertainty=float(self._value(row, "uncertainty", default=1.0)),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        state=PriorObservationState(
                            str(
                                self._value(
                                    row,
                                    "state",
                                    default=PriorObservationState.SUPPORTED.value,
                                )
                            )
                        ),
                        evidence_tier=str(
                            self._value(row, "evidence_tier", "tier", default="declared")
                        ),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CellContextBetaIssue(
                        "invalid_context_prior_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return ContextPriorObservationBatch(
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

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        if default is not None:
            return default
        raise ValidationError(f"context prior field is required: {names[0]}")


@dataclass(frozen=True, slots=True)
class ContextPriorCandidate:
    """Aggregated bounded support for one candidate lineage or state."""

    candidate_id: str
    candidate_label: str
    support_score: float
    uncertainty: float
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    evidence_count: int
    declared_candidate: bool

    def __post_init__(self) -> None:
        require_non_empty(self.candidate_id, "candidate_id")
        if not 0 <= self.support_score <= 1:
            raise ValidationError("candidate support_score must be between zero and one")
        if not 0 <= self.uncertainty <= 1:
            raise ValidationError("candidate uncertainty must be between zero and one")
        if self.evidence_count < 1:
            raise ValidationError("candidate evidence_count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ContextPriorResult:
    """Replayable context prior result with candidate alternatives retained."""

    prior_kind: str
    subject_id: str
    context_key: str
    model_id: str
    model_version: str
    state: CellContextBetaState
    selected_candidate_id: str | None
    selected_candidate_label: str | None
    candidates: tuple[ContextPriorCandidate, ...]
    uncertainty: float
    applicable: bool
    missing_requirements: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("prior_kind", "subject_id", "context_key", "model_id", "model_version"):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.uncertainty <= 1:
            raise ValidationError("context prior result uncertainty must be between zero and one")
        candidate_ids = {candidate.candidate_id for candidate in self.candidates}
        if (
            self.selected_candidate_id is not None
            and self.selected_candidate_id not in candidate_ids
        ):
            raise ValidationError("selected prior candidate must be retained in candidates")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class _ContextPriorEngine:
    """Shared aggregation and ambiguity logic for four declared prior families."""

    def __init__(
        self,
        *,
        prior_kind: str,
        declared_candidates: Mapping[str, str],
        applicability: Mapping[str, tuple[str, ...]],
    ) -> None:
        self.prior_kind = prior_kind
        self.declared_candidates = dict(declared_candidates)
        self.applicability = dict(applicability)

    def estimate(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextPriorObservation | Mapping[str, Any]],
        *,
        subject_id: str = "unspecified",
        model_id: str,
        model_version: str,
        declared_molecular_state: str | None = None,
        minimum_evidence: int = 1,
        ambiguity_margin: float = 0.15,
    ) -> ContextPriorResult:
        require_non_empty(subject_id, "subject_id")
        require_non_empty(model_id, "model_id")
        require_non_empty(model_version, "model_version")
        if minimum_evidence < 1:
            raise ValidationError("minimum_evidence must be positive")
        if ambiguity_margin < 0 or ambiguity_margin > 1:
            raise ValidationError("ambiguity_margin must be between zero and one")
        values = tuple(_coerce_observation(value) for value in observations)
        relevant = tuple(
            value for value in values if value.subject_id in {subject_id, "unspecified"}
        )
        exact = tuple(value for value in relevant if value.context_key == context.key)
        applicable, requirements = self._is_applicable(context, declared_molecular_state)
        if not applicable:
            return self._result(
                context,
                subject_id,
                model_id,
                model_version,
                CellContextBetaState.OUT_OF_DOMAIN,
                None,
                None,
                (),
                1.0,
                False,
                requirements,
                tuple(value.observation_id for value in exact),
                tuple(sorted({value.source_id for value in exact})),
                tuple(sorted({value.source_version for value in exact})),
                "the requested context does not satisfy this prior family's applicability gate",
            )
        if not exact:
            state = (
                CellContextBetaState.OUT_OF_DOMAIN if relevant else CellContextBetaState.ABSTAINED
            )
            reason = (
                "observations exist but none match the exact target context"
                if relevant
                else "no context-prior observations were supplied"
            )
            return self._result(
                context,
                subject_id,
                model_id,
                model_version,
                state,
                None,
                None,
                (),
                1.0,
                True,
                requirements,
                tuple(value.observation_id for value in relevant),
                tuple(sorted({value.source_id for value in relevant})),
                tuple(sorted({value.source_version for value in relevant})),
                reason,
            )
        contradictory = tuple(
            value for value in exact if value.state == PriorObservationState.CONTRADICTORY
        )
        usable = tuple(value for value in exact if value.state == PriorObservationState.SUPPORTED)
        grouped: dict[str, list[ContextPriorObservation]] = defaultdict(list)
        for value in usable:
            grouped[value.candidate_id].append(value)
        candidates = tuple(
            self._candidate(candidate_id, rows) for candidate_id, rows in sorted(grouped.items())
        )
        if contradictory:
            state = CellContextBetaState.CONTRADICTORY
            selected_id = None
            selected_label = None
            uncertainty = 1.0
            reason = "contradictory context-prior observations were supplied"
        elif not candidates:
            state = CellContextBetaState.ABSTAINED
            selected_id = None
            selected_label = None
            uncertainty = 1.0
            reason = "exact-context rows contain no positive prior support"
        elif any(candidate.evidence_count < minimum_evidence for candidate in candidates):
            state = CellContextBetaState.PARTIAL
            selected_id = None
            selected_label = None
            uncertainty = min(1.0, fmean(candidate.uncertainty for candidate in candidates) + 0.2)
            reason = "one or more candidate priors do not meet the declared evidence minimum"
        else:
            ranked = tuple(
                sorted(
                    candidates,
                    key=lambda candidate: (-candidate.support_score, candidate.candidate_id),
                )
            )
            top = ranked[0]
            second = ranked[1] if len(ranked) > 1 else None
            if second is not None and top.support_score - second.support_score < ambiguity_margin:
                state = CellContextBetaState.AMBIGUOUS
                selected_id = None
                selected_label = None
                uncertainty = min(1.0, fmean(candidate.uncertainty for candidate in ranked) + 0.25)
                reason = "top context-prior candidates remain within the declared ambiguity margin"
            else:
                state = CellContextBetaState.SUPPORTED
                selected_id = top.candidate_id
                selected_label = top.candidate_label
                uncertainty = top.uncertainty
                reason = "one context-prior candidate exceeds the declared ambiguity margin"
        return self._result(
            context,
            subject_id,
            model_id,
            model_version,
            state,
            selected_id,
            selected_label,
            candidates,
            round(uncertainty, 6),
            True,
            requirements,
            tuple(value.observation_id for value in exact),
            tuple(sorted({value.source_id for value in exact})),
            tuple(sorted({value.source_version for value in exact})),
            reason,
        )

    def _candidate(
        self,
        candidate_id: str,
        rows: list[ContextPriorObservation],
    ) -> ContextPriorCandidate:
        support_scores = tuple(row.support * (1 - row.uncertainty) for row in rows)
        return ContextPriorCandidate(
            candidate_id=candidate_id,
            candidate_label=rows[0].candidate_label,
            support_score=round(fmean(support_scores), 6),
            uncertainty=round(fmean(row.uncertainty for row in rows), 6),
            evidence_ids=tuple(row.observation_id for row in rows),
            source_ids=tuple(sorted({row.source_id for row in rows})),
            source_versions=tuple(sorted({row.source_version for row in rows})),
            evidence_count=len(rows),
            declared_candidate=candidate_id in self.declared_candidates,
        )

    def _is_applicable(
        self,
        context: ReferenceContext,
        declared_molecular_state: str | None,
    ) -> tuple[bool, tuple[str, ...]]:
        requirements: list[str] = []
        for field_name, allowed in self.applicability.items():
            if field_name == "molecular_state":
                value = _normalize_molecular_state(declared_molecular_state or "")
            else:
                value = str(getattr(context, field_name)).strip().lower()
            if value not in {_normalize_molecular_state(item) for item in allowed}:
                requirements.append(f"{field_name} must be one of {', '.join(allowed)}")
        return not requirements, tuple(requirements)

    def _result(
        self,
        context: ReferenceContext,
        subject_id: str,
        model_id: str,
        model_version: str,
        state: CellContextBetaState,
        selected_id: str | None,
        selected_label: str | None,
        candidates: tuple[ContextPriorCandidate, ...],
        uncertainty: float,
        applicable: bool,
        requirements: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        source_versions: tuple[str, ...],
        reason: str,
    ) -> ContextPriorResult:
        return ContextPriorResult(
            prior_kind=self.prior_kind,
            subject_id=subject_id,
            context_key=context.key,
            model_id=model_id,
            model_version=model_version,
            state=state,
            selected_candidate_id=selected_id,
            selected_candidate_label=selected_label,
            candidates=candidates,
            uncertainty=uncertainty,
            applicable=applicable,
            missing_requirements=requirements,
            evidence_ids=evidence_ids,
            source_ids=source_ids,
            source_versions=source_versions,
            reason=reason,
            warnings=(
                "Prior support scores are bounded research evidence summaries, not "
                "calibrated probabilities.",
                "Context mismatch, missing observations, and candidate disagreement "
                "are not negative evidence.",
                "External calibration, subgroup transport, and out-of-domain "
                "evaluation remain required.",
            ),
            content_address=content_hash(
                {
                    "prior_kind": self.prior_kind,
                    "subject_id": subject_id,
                    "context": context,
                    "model_id": model_id,
                    "model_version": model_version,
                    "state": state,
                    "selected_id": selected_id,
                    "candidates": candidates,
                    "requirements": requirements,
                    "evidence_ids": evidence_ids,
                }
            ),
        )


class DevelopmentalLineagePrior:
    """Estimate a bounded developmental-lineage prior for adult/pediatric glioma contexts."""

    _ENGINE = _ContextPriorEngine(
        prior_kind="developmental_lineage",
        declared_candidates={
            "radial_glia_like": "radial glia-like",
            "oligodendrocyte_lineage": "oligodendrocyte lineage",
            "astroglial_progenitor": "astroglial progenitor",
            "neural_progenitor": "neural progenitor",
        },
        applicability={
            "disease_class": ("glioma", "glioblastoma"),
            "age_group": ("adult", "pediatric"),
        },
    )

    def estimate(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextPriorObservation | Mapping[str, Any]],
        *,
        subject_id: str = "unspecified",
        model_id: str = "developmental-lineage-prior",
        model_version: str = "beta-1",
        minimum_evidence: int = 1,
        ambiguity_margin: float = 0.15,
    ) -> ContextPriorResult:
        return self._ENGINE.estimate(
            context,
            observations,
            subject_id=subject_id,
            model_id=model_id,
            model_version=model_version,
            minimum_evidence=minimum_evidence,
            ambiguity_margin=ambiguity_margin,
        )


class GlioblastomaMalignantStatePrior:
    """Estimate a bounded malignant-state prior only for explicit glioblastoma context."""

    _ENGINE = _ContextPriorEngine(
        prior_kind="glioblastoma_malignant_state",
        declared_candidates={
            "stem_like": "stem-like",
            "cycling": "cycling",
            "mesenchymal_like": "mesenchymal-like",
            "astrocyte_like": "astrocyte-like",
            "hypoxic": "hypoxic",
            "invasive": "invasive",
        },
        applicability={"disease_class": ("glioblastoma", "gbm")},
    )

    def estimate(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextPriorObservation | Mapping[str, Any]],
        *,
        subject_id: str = "unspecified",
        model_id: str = "glioblastoma-malignant-state-prior",
        model_version: str = "beta-1",
        minimum_evidence: int = 1,
        ambiguity_margin: float = 0.15,
    ) -> ContextPriorResult:
        return self._ENGINE.estimate(
            context,
            observations,
            subject_id=subject_id,
            model_id=model_id,
            model_version=model_version,
            minimum_evidence=minimum_evidence,
            ambiguity_margin=ambiguity_margin,
        )


class IdhMutantLineageStatePrior:
    """Estimate an IDH-mutant lineage/state prior only with declared molecular state."""

    _ENGINE = _ContextPriorEngine(
        prior_kind="idh_mutant_lineage_state",
        declared_candidates={
            "oligodendrocyte_precursor_like": "oligodendrocyte-precursor-like",
            "proneural": "proneural",
            "astrocyte_lineage": "astrocyte lineage",
            "neural_progenitor": "neural progenitor",
        },
        applicability={"molecular_state": ("IDH-mutant",)},
    )

    def estimate(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextPriorObservation | Mapping[str, Any]],
        *,
        declared_molecular_state: str | None,
        subject_id: str = "unspecified",
        model_id: str = "idh-mutant-lineage-state-prior",
        model_version: str = "beta-1",
        minimum_evidence: int = 1,
        ambiguity_margin: float = 0.15,
    ) -> ContextPriorResult:
        return self._ENGINE.estimate(
            context,
            observations,
            subject_id=subject_id,
            model_id=model_id,
            model_version=model_version,
            declared_molecular_state=declared_molecular_state,
            minimum_evidence=minimum_evidence,
            ambiguity_margin=ambiguity_margin,
        )


class H3K27AlteredDevelopmentalStatePrior:
    """Estimate a H3K27-altered developmental-state prior with an explicit state gate."""

    _ENGINE = _ContextPriorEngine(
        prior_kind="h3k27_altered_developmental_state",
        declared_candidates={
            "midline_glial_progenitor": "midline glial progenitor",
            "radial_glia_like": "radial glia-like",
            "oligodendrocyte_lineage": "oligodendrocyte lineage",
            "developmental_stem_like": "developmental stem-like",
        },
        applicability={"molecular_state": ("H3K27-altered",)},
    )

    def estimate(
        self,
        context: ReferenceContext,
        observations: Iterable[ContextPriorObservation | Mapping[str, Any]],
        *,
        declared_molecular_state: str | None,
        subject_id: str = "unspecified",
        model_id: str = "h3k27-altered-developmental-state-prior",
        model_version: str = "beta-1",
        minimum_evidence: int = 1,
        ambiguity_margin: float = 0.15,
    ) -> ContextPriorResult:
        return self._ENGINE.estimate(
            context,
            observations,
            subject_id=subject_id,
            model_id=model_id,
            model_version=model_version,
            declared_molecular_state=declared_molecular_state,
            minimum_evidence=minimum_evidence,
            ambiguity_margin=ambiguity_margin,
        )


def _coerce_observation(
    value: ContextPriorObservation | Mapping[str, Any],
) -> ContextPriorObservation:
    if isinstance(value, ContextPriorObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("context prior observation must be a mapping")
    return ContextPriorObservation(
        observation_id=str(value.get("observation_id", value.get("evidence_id", "prior-input"))),
        subject_id=str(value.get("subject_id", "unspecified")),
        candidate_id=str(value.get("candidate_id", "")),
        candidate_label=str(value.get("candidate_label", value.get("label", "unspecified"))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        support=float(value.get("support", value.get("score", 0.0))),
        uncertainty=float(value.get("uncertainty", 1.0)),
        source_id=str(value.get("source_id", "prior-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        state=PriorObservationState(str(value.get("state", PriorObservationState.SUPPORTED.value))),
        evidence_tier=str(value.get("evidence_tier", value.get("tier", "declared"))),
        attributes=dict(value.get("attributes", {})),
    )


def _normalize_molecular_state(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


__all__ = [
    "CellContextBetaIssue",
    "CellContextBetaState",
    "ContextPriorCandidate",
    "ContextPriorObservation",
    "ContextPriorObservationBatch",
    "ContextPriorObservationParser",
    "ContextPriorResult",
    "DevelopmentalLineagePrior",
    "GlioblastomaMalignantStatePrior",
    "H3K27AlteredDevelopmentalStatePrior",
    "IdhMutantLineageStatePrior",
    "PriorObservationState",
]

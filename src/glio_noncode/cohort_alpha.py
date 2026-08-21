"""External-alpha cohort, clonality, treatment, and replication contracts.

Domain 12 external-alpha summaries extend the exact-context cohort plane with
four explicit comparisons:

* ``ClonalityTimingIntegrator`` aggregates declared cancer-cell-fraction and
  phase observations while retaining sample-level timing receipts.
* ``PrimaryRecurrenceComparator`` compares matching loci across primary and
  recurrence phases without treating recurrence as a treatment outcome.
* ``TreatmentSelectionSignalDetector`` contrasts pre- and post-treatment
  frequencies as a descriptive selection signal with minimum sample gates.
* ``CrossCohortReplicationEngine`` evaluates effect-direction concordance and
  cohort coverage while retaining heterogeneous cohort evidence.

All inputs are pseudonymous evidence records. These outputs are descriptive
research summaries, not clonal evolution proofs, treatment-response claims,
causal effects, statistical significance tests, or clinical recommendations.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class CohortAlphaState(StrEnum):
    """State for Domain 12 external-alpha summaries."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class ClonalityLabel(StrEnum):
    """Bounded label for declared cellular-fraction observations."""

    CLONAL = "clonal"
    SUBCLONAL = "subclonal"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class TimingLabel(StrEnum):
    """Declared timing label derived from phase or timepoint metadata."""

    EARLY = "early"
    LATE = "late"
    INDETERMINATE = "indeterminate"


class PhaseLabel(StrEnum):
    """Primary/recurrence treatment-independent specimen phase."""

    PRIMARY = "primary"
    RECURRENCE = "recurrence"
    PROGRESSION = "progression"
    INTERVAL = "interval"
    UNKNOWN = "unknown"


class SelectionLabel(StrEnum):
    """Descriptive before/after treatment frequency comparison."""

    ENRICHED = "enriched"
    DEPLETED = "depleted"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CohortAlphaIssue:
    """Quarantined alpha record with source receipt."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    remediation: str = "Inspect the record, context, and cohort definition before retrying."
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "cohort alpha issue code")
        require_non_empty(self.message, "cohort alpha issue message")
        require_non_empty(self.raw_hash, "cohort alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("cohort alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ClonalityTimingObservation:
    """One pseudonymous sample-level clonality and timing observation."""

    observation_id: str
    variant_id: str
    sample_id: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    cancer_cell_fraction: float | None = None
    purity: float | None = None
    copy_number: float | None = None
    timepoint: float | None = None
    phase: PhaseLabel = PhaseLabel.UNKNOWN
    region_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "sample_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        for name in ("cancer_cell_fraction", "purity"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValidationError(f"clonality {name} must be between zero and one")
        if self.copy_number is not None and self.copy_number < 0:
            raise ValidationError("clonality copy_number cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ClonalityTimingResult:
    """Integrated clonality label with sample and timing receipts."""

    variant_id: str
    context_key: str
    state: CohortAlphaState
    clonality_label: ClonalityLabel
    timing_label: TimingLabel
    median_cancer_cell_fraction: float | None
    ccf_values: tuple[float, ...]
    sample_ids: tuple[str, ...]
    ordered_sample_ids: tuple[str, ...]
    phase_labels: tuple[str, ...]
    region_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ClonalityTimingReport:
    """Clonality and timing outputs across variants."""

    input_hash: str
    context_key: str
    state: CohortAlphaState
    results: tuple[ClonalityTimingResult, ...]
    issues: tuple[CohortAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ClonalityTimingIntegrator:
    """Integrate declared CCF and specimen timing without evolution claims."""

    def integrate(
        self,
        observations: Iterable[ClonalityTimingObservation | Mapping[str, Any]],
        *,
        context_key: str,
        clonal_threshold: float = 0.85,
        subclonal_threshold: float = 0.25,
    ) -> ClonalityTimingReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if not 0 <= subclonal_threshold < clonal_threshold <= 1:
            raise ValidationError("clonality thresholds must satisfy 0 <= subclonal < clonal <= 1")
        parsed: list[ClonalityTimingObservation] = []
        issues: list[CohortAlphaIssue] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_clonality(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CohortAlphaIssue(
                        "invalid_clonality_row",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if item.context_key != context_key:
                mismatch = True
                issues.append(
                    CohortAlphaIssue(
                        "context_mismatch",
                        "clonality observation is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(item)
        grouped: dict[tuple[str, str], list[ClonalityTimingObservation]] = defaultdict(list)
        for item in parsed:
            grouped[(item.variant_id, item.context_key)].append(item)
        results: list[ClonalityTimingResult] = []
        for (variant_id, row_context), group in sorted(grouped.items()):
            ccf_values = tuple(
                sorted(
                    item.cancer_cell_fraction
                    for item in group
                    if item.cancer_cell_fraction is not None
                )
            )
            if not ccf_values:
                label = ClonalityLabel.UNKNOWN
                state = CohortAlphaState.PARTIAL
                median_ccf = None
                reason = "no cancer-cell-fraction channel was supplied"
            else:
                median_ccf = median(ccf_values)
                if min(ccf_values) >= clonal_threshold:
                    label = ClonalityLabel.CLONAL
                elif max(ccf_values) <= subclonal_threshold:
                    label = ClonalityLabel.SUBCLONAL
                elif len(set(ccf_values)) > 1:
                    label = ClonalityLabel.MIXED
                else:
                    label = ClonalityLabel.UNKNOWN
                state = CohortAlphaState.SUPPORTED
                reason = "declared CCF observations were integrated per variant and exact context"
            phase_labels = tuple(sorted({item.phase.value for item in group}))
            timing = _timing_label(group)
            ordered = tuple(
                item.sample_id
                for item in sorted(
                    group,
                    key=lambda item: (
                        item.timepoint is None,
                        item.timepoint if item.timepoint is not None else float("inf"),
                        item.sample_id,
                    ),
                )
            )
            if (
                any(item.timepoint is None for item in group)
                and timing == TimingLabel.INDETERMINATE
            ):
                state = CohortAlphaState.PARTIAL
            results.append(
                ClonalityTimingResult(
                    variant_id=variant_id,
                    context_key=row_context,
                    state=state,
                    clonality_label=label,
                    timing_label=timing,
                    median_cancer_cell_fraction=None
                    if median_ccf is None
                    else round(median_ccf, 9),
                    ccf_values=ccf_values,
                    sample_ids=tuple(sorted({item.sample_id for item in group})),
                    ordered_sample_ids=ordered,
                    phase_labels=phase_labels,
                    region_ids=tuple(sorted({item.region_id for item in group if item.region_id})),
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    reason=reason,
                    limitations=(
                        "CCF and specimen timepoints are declared observations, not proof of "
                        "clonal evolution.",
                        "Purity, copy number, sampling, and phase assignment require external "
                        "validation.",
                    ),
                    content_address=content_hash(
                        {
                            "variant_id": variant_id,
                            "context_key": row_context,
                            "state": state,
                            "label": label,
                            "timing": timing,
                            "ccf_values": ccf_values,
                            "sample_ids": tuple(sorted({item.sample_id for item in group})),
                        }
                    ),
                )
            )
        state = _aggregate_state(tuple(item.state for item in results), mismatch, issues)
        return ClonalityTimingReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Clonality and timing labels summarize declared sampling and CCF channels.",
                "They do not establish evolutionary order, fitness, or treatment response.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class PrimaryRecurrenceObservation:
    """One locus observation in a primary or recurrence phase."""

    observation_id: str
    variant_id: str
    locus_id: str
    sample_id: str
    phase: PhaseLabel
    frequency: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    treatment_exposed: bool | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "locus_id",
            "sample_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.frequency <= 1:
            raise ValidationError("primary-recurrence frequency must be between zero and one")
        if self.phase not in {PhaseLabel.PRIMARY, PhaseLabel.RECURRENCE, PhaseLabel.PROGRESSION}:
            raise ValidationError(
                "primary-recurrence phase must be primary, recurrence, or progression"
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PrimaryRecurrenceComparison:
    """Primary/recurrence frequency comparison for one locus."""

    variant_id: str
    locus_id: str
    context_key: str
    state: CohortAlphaState
    primary_frequency: float | None
    recurrence_frequency: float | None
    recurrence_minus_primary: float | None
    primary_sample_ids: tuple[str, ...]
    recurrence_sample_ids: tuple[str, ...]
    progression_sample_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    label: SelectionLabel
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PrimaryRecurrenceComparatorReport:
    """Primary/recurrence comparator output."""

    input_hash: str
    context_key: str
    state: CohortAlphaState
    results: tuple[PrimaryRecurrenceComparison, ...]
    issues: tuple[CohortAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PrimaryRecurrenceComparator:
    """Compare phase frequencies without attributing differences to treatment."""

    def compare(
        self,
        observations: Iterable[PrimaryRecurrenceObservation | Mapping[str, Any]],
        *,
        context_key: str,
        change_threshold: float = 0.20,
    ) -> PrimaryRecurrenceComparatorReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if not 0 <= change_threshold <= 1:
            raise ValidationError(
                "primary-recurrence change_threshold must be between zero and one"
            )
        parsed, issues, mismatch = _parse_context_records(
            values, _coerce_primary_recurrence, context_key
        )
        groups: dict[tuple[str, str], list[PrimaryRecurrenceObservation]] = defaultdict(list)
        for item in parsed:
            groups[(item.variant_id, item.locus_id)].append(item)
        results: list[PrimaryRecurrenceComparison] = []
        for (variant_id, locus_id), group in sorted(groups.items()):
            primary = tuple(item for item in group if item.phase == PhaseLabel.PRIMARY)
            recurrence = tuple(item for item in group if item.phase == PhaseLabel.RECURRENCE)
            progression = tuple(item for item in group if item.phase == PhaseLabel.PROGRESSION)
            primary_frequency = median(item.frequency for item in primary) if primary else None
            recurrence_frequency = (
                median(item.frequency for item in recurrence) if recurrence else None
            )
            delta = (
                recurrence_frequency - primary_frequency
                if primary_frequency is not None and recurrence_frequency is not None
                else None
            )
            if delta is None:
                state = CohortAlphaState.PARTIAL
                label = SelectionLabel.UNKNOWN
                reason = "both primary and recurrence phases are required for comparison"
            elif delta >= change_threshold:
                state = CohortAlphaState.SUPPORTED
                label = SelectionLabel.ENRICHED
                reason = "recurrence frequency exceeds primary frequency by the declared threshold"
            elif delta <= -change_threshold:
                state = CohortAlphaState.SUPPORTED
                label = SelectionLabel.DEPLETED
                reason = "recurrence frequency is below primary frequency by the declared threshold"
            else:
                state = CohortAlphaState.SUPPORTED
                label = SelectionLabel.STABLE
                reason = "primary and recurrence frequencies remain within the declared threshold"
            results.append(
                PrimaryRecurrenceComparison(
                    variant_id=variant_id,
                    locus_id=locus_id,
                    context_key=context_key,
                    state=state,
                    primary_frequency=_round_optional(primary_frequency),
                    recurrence_frequency=_round_optional(recurrence_frequency),
                    recurrence_minus_primary=_round_optional(delta),
                    primary_sample_ids=tuple(sorted(item.sample_id for item in primary)),
                    recurrence_sample_ids=tuple(sorted(item.sample_id for item in recurrence)),
                    progression_sample_ids=tuple(sorted(item.sample_id for item in progression)),
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    label=label,
                    reason=reason,
                    limitations=(
                        "Primary/recurrence frequency is descriptive and does not establish "
                        "recurrence causation.",
                        "Sampling, ascertainment, treatment exposure, and cohort composition "
                        "remain confounders.",
                    ),
                    content_address=content_hash(
                        {
                            "variant_id": variant_id,
                            "locus_id": locus_id,
                            "context_key": context_key,
                            "state": state,
                            "primary": primary_frequency,
                            "recurrence": recurrence_frequency,
                            "delta": delta,
                        }
                    ),
                )
            )
        state = _aggregate_state(tuple(item.state for item in results), mismatch, issues)
        return PrimaryRecurrenceComparatorReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Primary/recurrence comparisons preserve treatment exposure as metadata.",
                "A recurrence difference is not a treatment-selection or prognosis claim.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class TreatmentSelectionObservation:
    """One variant frequency observation around a treatment exposure."""

    observation_id: str
    variant_id: str
    sample_id: str
    treatment_id: str
    selection_phase: str
    frequency: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    response_label: str | None = None
    timepoint: float | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "variant_id",
            "sample_id",
            "treatment_id",
            "selection_phase",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.frequency <= 1:
            raise ValidationError("treatment-selection frequency must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TreatmentSelectionSignal:
    """Pre/post treatment descriptive frequency signal."""

    variant_id: str
    treatment_id: str
    context_key: str
    state: CohortAlphaState
    pre_treatment_frequency: float | None
    post_treatment_frequency: float | None
    frequency_delta: float | None
    selection_label: SelectionLabel
    pre_sample_ids: tuple[str, ...]
    post_sample_ids: tuple[str, ...]
    response_labels: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TreatmentSelectionReport:
    """Treatment-selection signal output."""

    input_hash: str
    context_key: str
    state: CohortAlphaState
    results: tuple[TreatmentSelectionSignal, ...]
    issues: tuple[CohortAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TreatmentSelectionSignalDetector:
    """Detect descriptive pre/post frequency changes with sample gates."""

    def detect(
        self,
        observations: Iterable[TreatmentSelectionObservation | Mapping[str, Any]],
        *,
        context_key: str,
        change_threshold: float = 0.20,
        pre_phases: Iterable[str] = ("pre_treatment", "baseline"),
        post_phases: Iterable[str] = ("on_treatment", "post_treatment", "progression"),
    ) -> TreatmentSelectionReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if not 0 <= change_threshold <= 1:
            raise ValidationError(
                "treatment-selection change_threshold must be between zero and one"
            )
        parsed, issues, mismatch = _parse_context_records(values, _coerce_treatment, context_key)
        pre_set = {str(item).lower() for item in pre_phases}
        post_set = {str(item).lower() for item in post_phases}
        groups: dict[tuple[str, str], list[TreatmentSelectionObservation]] = defaultdict(list)
        for item in parsed:
            groups[(item.variant_id, item.treatment_id)].append(item)
        results: list[TreatmentSelectionSignal] = []
        for (variant_id, treatment_id), group in sorted(groups.items()):
            pre = tuple(item for item in group if item.selection_phase.lower() in pre_set)
            post = tuple(item for item in group if item.selection_phase.lower() in post_set)
            pre_frequency = median(item.frequency for item in pre) if pre else None
            post_frequency = median(item.frequency for item in post) if post else None
            delta = (
                post_frequency - pre_frequency
                if pre_frequency is not None and post_frequency is not None
                else None
            )
            if delta is None:
                state = CohortAlphaState.PARTIAL
                label = SelectionLabel.UNKNOWN
                reason = "pre-treatment and post-treatment observations are both required"
            elif delta >= change_threshold:
                state = CohortAlphaState.SUPPORTED
                label = SelectionLabel.ENRICHED
                reason = (
                    "post-treatment frequency exceeds pre-treatment frequency by the declared "
                    "threshold"
                )
            elif delta <= -change_threshold:
                state = CohortAlphaState.SUPPORTED
                label = SelectionLabel.DEPLETED
                reason = (
                    "post-treatment frequency is below pre-treatment frequency by the declared "
                    "threshold"
                )
            else:
                state = CohortAlphaState.SUPPORTED
                label = SelectionLabel.STABLE
                reason = "pre/post treatment frequency change is within the declared threshold"
            results.append(
                TreatmentSelectionSignal(
                    variant_id=variant_id,
                    treatment_id=treatment_id,
                    context_key=context_key,
                    state=state,
                    pre_treatment_frequency=_round_optional(pre_frequency),
                    post_treatment_frequency=_round_optional(post_frequency),
                    frequency_delta=_round_optional(delta),
                    selection_label=label,
                    pre_sample_ids=tuple(sorted(item.sample_id for item in pre)),
                    post_sample_ids=tuple(sorted(item.sample_id for item in post)),
                    response_labels=tuple(
                        sorted({item.response_label for item in group if item.response_label})
                    ),
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    reason=reason,
                    limitations=(
                        "Pre/post frequency change is a descriptive selection signal, not a "
                        "treatment-response claim.",
                        "Sampling, censoring, response, purity, and exposure timing require "
                        "external controls.",
                    ),
                    content_address=content_hash(
                        {
                            "variant_id": variant_id,
                            "treatment_id": treatment_id,
                            "context_key": context_key,
                            "state": state,
                            "pre": pre_frequency,
                            "post": post_frequency,
                            "delta": delta,
                        }
                    ),
                )
            )
        state = _aggregate_state(tuple(item.state for item in results), mismatch, issues)
        return TreatmentSelectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Treatment-selection signals retain exposure and response metadata without "
                "causal interpretation.",
                "The detector does not infer benefit, resistance, prognosis, or treatment "
                "recommendation.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class CrossCohortReplicationObservation:
    """One cohort-specific effect or support observation."""

    observation_id: str
    feature_id: str
    cohort_id: str
    effect: float
    support: float
    sample_count: int
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    assay_label: str = "unspecified"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "feature_id",
            "cohort_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "assay_label",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1:
            raise ValidationError("replication support must be between zero and one")
        if self.sample_count < 1:
            raise ValidationError("replication sample_count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CrossCohortReplicationResult:
    """Replication and effect-direction concordance for one feature."""

    feature_id: str
    context_key: str
    state: CohortAlphaState
    cohort_ids: tuple[str, ...]
    sample_counts: Mapping[str, int]
    effects_by_cohort: Mapping[str, float]
    support_by_cohort: Mapping[str, float]
    positive_cohort_ids: tuple[str, ...]
    negative_cohort_ids: tuple[str, ...]
    direction_concordance: float | None
    median_effect: float | None
    effect_range: tuple[float, float] | None
    replicated: bool
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CrossCohortReplicationReport:
    """Cross-cohort replication output."""

    input_hash: str
    context_key: str
    state: CohortAlphaState
    results: tuple[CrossCohortReplicationResult, ...]
    issues: tuple[CohortAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CrossCohortReplicationEngine:
    """Compare cohort-specific effects with explicit coverage and concordance."""

    def replicate(
        self,
        observations: Iterable[CrossCohortReplicationObservation | Mapping[str, Any]],
        *,
        context_key: str,
        minimum_cohorts: int = 2,
        minimum_concordance: float = 0.75,
    ) -> CrossCohortReplicationReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if minimum_cohorts < 1:
            raise ValidationError("minimum_cohorts must be positive")
        if not 0 <= minimum_concordance <= 1:
            raise ValidationError("minimum_concordance must be between zero and one")
        parsed, issues, mismatch = _parse_context_records(values, _coerce_replication, context_key)
        groups: dict[str, list[CrossCohortReplicationObservation]] = defaultdict(list)
        for item in parsed:
            groups[item.feature_id].append(item)
        results: list[CrossCohortReplicationResult] = []
        for feature_id, group in sorted(groups.items()):
            by_cohort: dict[str, list[CrossCohortReplicationObservation]] = defaultdict(list)
            for item in group:
                by_cohort[item.cohort_id].append(item)
            cohort_ids = tuple(sorted(by_cohort))
            effects = {
                cohort_id: median(item.effect for item in rows)
                for cohort_id, rows in sorted(by_cohort.items())
            }
            supports = {
                cohort_id: median(item.support for item in rows)
                for cohort_id, rows in sorted(by_cohort.items())
            }
            positive = tuple(
                sorted(cohort_id for cohort_id, effect in effects.items() if effect > 0)
            )
            negative = tuple(
                sorted(cohort_id for cohort_id, effect in effects.items() if effect < 0)
            )
            if effects and (positive or negative):
                majority_sign = 1 if len(positive) >= len(negative) else -1
                concordance = sum(
                    (effect > 0 if majority_sign == 1 else effect < 0)
                    for effect in effects.values()
                ) / len(effects)
            else:
                majority_sign = 0
                concordance = None
            replicated = (
                len(cohort_ids) >= minimum_cohorts
                and concordance is not None
                and concordance >= minimum_concordance
            )
            if not cohort_ids:
                state = CohortAlphaState.ABSTAINED
                reason = "no exact-context cohort observations were supplied"
            elif len(positive) and len(negative):
                state = CohortAlphaState.AMBIGUOUS
                reason = "cohort effect directions disagree"
            elif len(cohort_ids) < minimum_cohorts:
                state = CohortAlphaState.PARTIAL
                reason = "fewer cohorts than the declared replication minimum were supplied"
            elif replicated:
                state = CohortAlphaState.SUPPORTED
                reason = (
                    "cohort effects meet the declared coverage and direction-concordance thresholds"
                )
            else:
                state = CohortAlphaState.PARTIAL
                reason = (
                    "cohort coverage exists but direction concordance is below the declared "
                    "threshold"
                )
            effect_values = tuple(effects.values())
            results.append(
                CrossCohortReplicationResult(
                    feature_id=feature_id,
                    context_key=context_key,
                    state=state,
                    cohort_ids=cohort_ids,
                    sample_counts={
                        cohort_id: sum(item.sample_count for item in rows)
                        for cohort_id, rows in by_cohort.items()
                    },
                    effects_by_cohort={
                        cohort_id: round(effect, 9) for cohort_id, effect in effects.items()
                    },
                    support_by_cohort={
                        cohort_id: round(support, 9) for cohort_id, support in supports.items()
                    },
                    positive_cohort_ids=positive,
                    negative_cohort_ids=negative,
                    direction_concordance=None if concordance is None else round(concordance, 9),
                    median_effect=None if not effect_values else round(median(effect_values), 9),
                    effect_range=None
                    if not effect_values
                    else (round(min(effect_values), 9), round(max(effect_values), 9)),
                    replicated=replicated,
                    observation_ids=tuple(sorted(item.observation_id for item in group)),
                    source_ids=tuple(sorted({item.source_id for item in group})),
                    reason=reason,
                    limitations=(
                        "Cross-cohort concordance is a bounded replication summary, not a "
                        "generalization guarantee.",
                        "Cohort ascertainment, scale, ancestry, batch, and sample-size "
                        "heterogeneity require review.",
                    ),
                    content_address=content_hash(
                        {
                            "feature_id": feature_id,
                            "context_key": context_key,
                            "state": state,
                            "cohorts": cohort_ids,
                            "effects": effects,
                            "concordance": concordance,
                        }
                    ),
                )
            )
        state = _aggregate_state(tuple(item.state for item in results), mismatch, issues)
        return CrossCohortReplicationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Replication retains cohort-specific effect and sample-size metadata.",
                "Concordance does not establish transportability, causality, or clinical utility.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


def _parse_context_records(
    values: tuple[Any, ...],
    coerce: Any,
    context_key: str,
) -> tuple[list[Any], list[CohortAlphaIssue], bool]:
    parsed: list[Any] = []
    issues: list[CohortAlphaIssue] = []
    mismatch = False
    for row_number, value in enumerate(values, start=1):
        try:
            item = coerce(value)
        except (TypeError, ValueError, ValidationError) as exc:
            issues.append(
                CohortAlphaIssue(
                    "invalid_cohort_alpha_row",
                    str(exc),
                    content_hash(value),
                    row_number=row_number,
                    severity="error",
                )
            )
            continue
        if item.context_key != context_key:
            mismatch = True
            issues.append(
                CohortAlphaIssue(
                    "context_mismatch",
                    "cohort alpha record is outside the requested context",
                    item.raw_hash,
                    row_number=row_number,
                    source_id=item.source_id,
                    severity="warning",
                )
            )
            continue
        parsed.append(item)
    return parsed, issues, mismatch


def _aggregate_state(
    states: tuple[CohortAlphaState, ...],
    mismatch: bool,
    issues: Iterable[CohortAlphaIssue],
) -> CohortAlphaState:
    if not states:
        return CohortAlphaState.OUT_OF_DOMAIN if mismatch else CohortAlphaState.ABSTAINED
    if CohortAlphaState.CONTRADICTORY in states:
        return CohortAlphaState.CONTRADICTORY
    if CohortAlphaState.AMBIGUOUS in states:
        return CohortAlphaState.AMBIGUOUS
    if any(issue.severity == "error" for issue in issues):
        return CohortAlphaState.PARTIAL
    if CohortAlphaState.PARTIAL in states:
        return CohortAlphaState.PARTIAL
    if all(item == CohortAlphaState.SUPPORTED for item in states):
        return CohortAlphaState.SUPPORTED
    return CohortAlphaState.ABSENT


def _timing_label(group: Iterable[ClonalityTimingObservation]) -> TimingLabel:
    values = tuple(group)
    phases = {item.phase for item in values}
    if PhaseLabel.PRIMARY in phases:
        return TimingLabel.EARLY
    if PhaseLabel.RECURRENCE in phases or PhaseLabel.PROGRESSION in phases:
        return TimingLabel.LATE
    return TimingLabel.INDETERMINATE


def _coerce_clonality(
    value: ClonalityTimingObservation | Mapping[str, Any],
) -> ClonalityTimingObservation:
    if isinstance(value, ClonalityTimingObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("clonality timing observation must be a mapping")
    return ClonalityTimingObservation(
        observation_id=str(value.get("observation_id", value.get("id", "clonality-input"))),
        variant_id=str(value.get("variant_id", value.get("variant", ""))),
        sample_id=str(value.get("sample_id", value.get("sample", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "clonality-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        cancer_cell_fraction=_optional_float(value, "cancer_cell_fraction", "ccf"),
        purity=_optional_float(value, "purity"),
        copy_number=_optional_float(value, "copy_number", "cn"),
        timepoint=_optional_float(value, "timepoint", "collection_time"),
        phase=_phase(value.get("phase", value.get("specimen_phase", PhaseLabel.UNKNOWN.value))),
        region_id=_optional_text(value, "region_id", "region"),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_primary_recurrence(
    value: PrimaryRecurrenceObservation | Mapping[str, Any],
) -> PrimaryRecurrenceObservation:
    if isinstance(value, PrimaryRecurrenceObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("primary-recurrence observation must be a mapping")
    return PrimaryRecurrenceObservation(
        observation_id=str(
            value.get("observation_id", value.get("id", "primary-recurrence-input"))
        ),
        variant_id=str(value.get("variant_id", value.get("variant", ""))),
        locus_id=str(value.get("locus_id", value.get("locus", ""))),
        sample_id=str(value.get("sample_id", value.get("sample", ""))),
        phase=_phase(value.get("phase", PhaseLabel.UNKNOWN.value)),
        frequency=float(value.get("frequency", value.get("prevalence", value.get("value", 0.0)))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "primary-recurrence-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        treatment_exposed=_optional_bool(value, "treatment_exposed", "exposed"),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_treatment(
    value: TreatmentSelectionObservation | Mapping[str, Any],
) -> TreatmentSelectionObservation:
    if isinstance(value, TreatmentSelectionObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("treatment-selection observation must be a mapping")
    return TreatmentSelectionObservation(
        observation_id=str(value.get("observation_id", value.get("id", "treatment-input"))),
        variant_id=str(value.get("variant_id", value.get("variant", ""))),
        sample_id=str(value.get("sample_id", value.get("sample", ""))),
        treatment_id=str(value.get("treatment_id", value.get("treatment", ""))),
        selection_phase=str(value.get("selection_phase", value.get("phase", ""))),
        frequency=float(value.get("frequency", value.get("value", 0.0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "treatment-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        response_label=_optional_text(value, "response_label", "response"),
        timepoint=_optional_float(value, "timepoint", "collection_time"),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_replication(
    value: CrossCohortReplicationObservation | Mapping[str, Any],
) -> CrossCohortReplicationObservation:
    if isinstance(value, CrossCohortReplicationObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("cross-cohort replication observation must be a mapping")
    return CrossCohortReplicationObservation(
        observation_id=str(value.get("observation_id", value.get("id", "replication-input"))),
        feature_id=str(value.get("feature_id", value.get("variant_id", value.get("feature", "")))),
        cohort_id=str(value.get("cohort_id", value.get("cohort", ""))),
        effect=float(value.get("effect", value.get("effect_size", 0.0))),
        support=float(value.get("support", value.get("confidence", 0.0))),
        sample_count=int(value.get("sample_count", value.get("n", 0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "replication-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        assay_label=str(value.get("assay_label", value.get("assay", "unspecified"))),
        attributes=dict(value.get("attributes", {})),
    )


def _phase(value: Any) -> PhaseLabel:
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {"baseline": "primary", "relapse": "recurrence", "progression": "progression"}
    try:
        return PhaseLabel(aliases.get(normalized, normalized))
    except ValueError as exc:
        raise ValidationError(f"unsupported specimen phase: {value}") from exc


def _optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return None


def _optional_float(row: Mapping[str, Any], *names: str) -> float | None:
    value = _optional_text(row, *names)
    return None if value is None else float(value)


def _optional_bool(row: Mapping[str, Any], *names: str) -> bool | None:
    value = _optional_text(row, *names)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 9)


__all__ = [
    "ClonalityLabel",
    "ClonalityTimingIntegrator",
    "ClonalityTimingObservation",
    "ClonalityTimingReport",
    "ClonalityTimingResult",
    "CohortAlphaIssue",
    "CohortAlphaState",
    "CrossCohortReplicationEngine",
    "CrossCohortReplicationObservation",
    "CrossCohortReplicationReport",
    "CrossCohortReplicationResult",
    "PhaseLabel",
    "PrimaryRecurrenceComparator",
    "PrimaryRecurrenceComparatorReport",
    "PrimaryRecurrenceComparison",
    "PrimaryRecurrenceObservation",
    "SelectionLabel",
    "TimingLabel",
    "TreatmentSelectionObservation",
    "TreatmentSelectionReport",
    "TreatmentSelectionSignal",
    "TreatmentSelectionSignalDetector",
]

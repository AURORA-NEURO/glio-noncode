"""Callable-space, matched-background cohort recurrence summaries.

The returned support and uncertainty fields are descriptive indices only. They
are not calibrated probabilities, hypothesis-test p-values, or clinical claims.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import islice
from typing import Any

from .models import ReferenceContext

MAX_COHORT_OBSERVATIONS = 250_000
MAX_MATCHED_CONTROL_LOCI = 500
MIN_MATCHED_CONTROL_LOCI = 5
DEFAULT_MATCHED_CONTROL_LOCI = 20

_REQUIRED_MATCHING_FIELDS = (
    "variant_class",
    "sequence_context",
    "molecular_context",
    "recurrence_phase",
    "locus_length",
    "batch_id",
    "ascertainment_group",
)
_GLOBAL_MATCH_FIELDS = (
    "context",
    "disease_class",
    "ancestry_group",
    "variant_class",
    "sequence_context",
    "molecular_context",
    "recurrence_phase",
    "locus_length",
)


@dataclass(frozen=True, slots=True)
class CohortObservation:
    """One subject-by-locus observation with explicit callability and context."""

    observation_id: str
    subject_id: str
    locus_id: str
    mutated: bool
    callable: bool
    mutability_score: float
    chromatin_score: float
    ancestry_group: str
    disease_class: str
    context: ReferenceContext
    variant_class: str | None = None
    sequence_context: str | None = None
    molecular_context: str | None = None
    recurrence_phase: str | None = None
    locus_length: int | None = None
    batch_id: str | None = None
    ascertainment_group: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> CohortObservation:
        """Validate and parse one versioned-input observation record."""

        required = {
            "observation_id",
            "subject_id",
            "locus_id",
            "mutated",
            "callable",
            "mutability_score",
            "chromatin_score",
            "ancestry_group",
            "disease_class",
            "context",
        }
        optional = set(_REQUIRED_MATCHING_FIELDS)
        unknown = set(raw) - required - optional
        missing = required - set(raw)
        if unknown:
            raise ValueError(f"cohort observation contains unsupported fields: {sorted(unknown)}")
        if missing:
            raise ValueError(f"cohort observation is missing fields: {sorted(missing)}")

        context_raw = raw["context"]
        if not isinstance(context_raw, Mapping):
            raise ValueError("cohort observation context must be an object")
        text_fields = (
            "observation_id",
            "subject_id",
            "locus_id",
            "ancestry_group",
            "disease_class",
        )
        values: dict[str, Any] = {name: _observation_text(raw[name], name) for name in text_fields}
        values["mutated"] = _observation_bool(raw["mutated"], "mutated")
        values["callable"] = _observation_bool(raw["callable"], "callable")
        values["mutability_score"] = _observation_score(raw["mutability_score"], "mutability_score")
        values["chromatin_score"] = _observation_score(raw["chromatin_score"], "chromatin_score")
        values["context"] = ReferenceContext.from_dict(context_raw)
        for name in _REQUIRED_MATCHING_FIELDS:
            value = raw.get(name)
            if value is not None and name != "locus_length":
                value = _observation_text(value, name)
            if name == "locus_length" and value is not None and type(value) is not int:
                raise ValueError("locus_length must be an integer or null")
            values[name] = value
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        """Serialize one cohort observation using the CLI input field names."""

        return {
            "observation_id": self.observation_id,
            "subject_id": self.subject_id,
            "locus_id": self.locus_id,
            "mutated": self.mutated,
            "callable": self.callable,
            "mutability_score": self.mutability_score,
            "chromatin_score": self.chromatin_score,
            "ancestry_group": self.ancestry_group,
            "disease_class": self.disease_class,
            "context": self.context.to_dict(),
            "variant_class": self.variant_class,
            "sequence_context": self.sequence_context,
            "molecular_context": self.molecular_context,
            "recurrence_phase": self.recurrence_phase,
            "locus_length": self.locus_length,
            "batch_id": self.batch_id,
            "ascertainment_group": self.ascertainment_group,
        }

    def __post_init__(self) -> None:
        for name in ("observation_id", "subject_id", "locus_id", "ancestry_group", "disease_class"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} must be a non-empty string of at most 256 characters")
        if type(self.mutated) is not bool or type(self.callable) is not bool:
            raise ValueError("mutated and callable must be booleans")
        if self.mutated and not self.callable:
            raise ValueError("a non-callable cohort observation cannot be marked mutated")
        if not isinstance(self.context, ReferenceContext):
            raise ValueError("context must be a ReferenceContext")
        if self.disease_class != self.context.disease_class:
            raise ValueError("disease_class must match context.disease_class")
        for name in ("mutability_score", "chromatin_score"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number between 0 and 1")
            try:
                finite_value = math.isfinite(float(value))
            except OverflowError:
                finite_value = False
            if not finite_value:
                raise ValueError(f"{name} must be a finite number between 0 and 1")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in _REQUIRED_MATCHING_FIELDS:
            value = getattr(self, name)
            if name == "locus_length":
                if value is not None and (type(value) is not int or value < 1):
                    raise ValueError("locus_length must be a positive integer when supplied")
            elif value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 256
            ):
                raise ValueError(f"{name} must be a non-empty string of at most 256 characters")


@dataclass(frozen=True, slots=True)
class ControlLocusRate:
    """Aggregate rate for one matched null locus; contains no subject identifiers."""

    locus_id: str
    mutated_count: int
    callable_count: int
    mutation_rate: float
    mutability_gap: float
    chromatin_gap: float

    def to_dict(self) -> dict[str, object]:
        return {
            "locus_id": self.locus_id,
            "mutated_count": self.mutated_count,
            "callable_count": self.callable_count,
            "mutation_rate": self.mutation_rate,
            "mutability_gap": self.mutability_gap,
            "chromatin_gap": self.chromatin_gap,
        }


@dataclass(frozen=True, slots=True)
class MatchedControl:
    """Control-selection diagnostics and per-locus rates for the matched null."""

    target_locus_id: str
    control_locus_ids: tuple[str, ...]
    matching_dimensions: tuple[str, ...]
    mean_mutability_gap: float
    mean_chromatin_gap: float
    warnings: tuple[str, ...]
    candidate_count: int
    eligible_count: int
    effective_sample_size: float
    control_rates: tuple[ControlLocusRate, ...]
    unmatched_covariates: tuple[str, ...]
    excluded_locus_counts: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "target_locus_id": self.target_locus_id,
            "control_locus_ids": list(self.control_locus_ids),
            "matching_dimensions": list(self.matching_dimensions),
            "mean_mutability_gap": self.mean_mutability_gap,
            "mean_chromatin_gap": self.mean_chromatin_gap,
            "candidate_count": self.candidate_count,
            "eligible_count": self.eligible_count,
            "effective_sample_size": self.effective_sample_size,
            "control_rates": [rate.to_dict() for rate in self.control_rates],
            "unmatched_covariates": list(self.unmatched_covariates),
            "excluded_locus_counts": dict(self.excluded_locus_counts),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class RecurrenceResult:
    """A descriptive recurrence comparison with explicit estimability status."""

    locus_id: str
    status: str
    observed_count: int
    callable_count: int
    observed_rate: float | None
    expected_rate: float | None
    enrichment: float | None
    z_like_score: float | None
    support: float
    uncertainty: float
    control_rate_sd: float | None
    matched_control: MatchedControl
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "glio.cohort-recurrence.v2",
            "locus_id": self.locus_id,
            "status": self.status,
            "observed_count": self.observed_count,
            "callable_count": self.callable_count,
            "observed_rate": self.observed_rate,
            "expected_rate": self.expected_rate,
            "enrichment": self.enrichment,
            "z_like_score": self.z_like_score,
            "support": self.support,
            "support_interpretation": "descriptive index; not a probability",
            "uncertainty": self.uncertainty,
            "uncertainty_interpretation": "uncalibrated descriptive index",
            "control_rate_sd": self.control_rate_sd,
            "matched_control": self.matched_control.to_dict(),
            "limitations": list(self.limitations),
        }


class MatchedControlBuilder:
    """Select distinct control loci matched on explicit design dimensions."""

    def build(
        self,
        target: CohortObservation,
        pool: Iterable[CohortObservation],
        *,
        limit: int = DEFAULT_MATCHED_CONTROL_LOCI,
        target_subjects: Mapping[str, CohortObservation] | None = None,
    ) -> MatchedControl:
        if type(limit) is not int or not 1 <= limit <= MAX_MATCHED_CONTROL_LOCI:
            raise ValueError(f"limit must be between 1 and {MAX_MATCHED_CONTROL_LOCI}")
        rows = tuple(islice(pool, MAX_COHORT_OBSERVATIONS + 1))
        if len(rows) > MAX_COHORT_OBSERVATIONS:
            raise ValueError(f"cohort exceeds {MAX_COHORT_OBSERVATIONS} observations")

        target_rows = tuple(target_subjects.values()) if target_subjects else (target,)
        unmatched = tuple(
            name
            for name in _REQUIRED_MATCHING_FIELDS
            if any(getattr(row, name) is None for row in target_rows)
        )
        groups: dict[str, list[CohortObservation]] = defaultdict(list)
        for row in rows:
            if row.locus_id != target.locus_id and _matches_global_dimensions(row, target):
                groups[row.locus_id].append(row)

        candidates = len(groups)
        target_subject_ids = (
            set(target_subjects) if target_subjects is not None else {target.subject_id}
        )
        selected_candidates: list[tuple[float, str, tuple[ControlLocusRate, ...]]] = []
        excluded_locus_counts: dict[str, int] = defaultdict(int)
        for control_locus_id, group in groups.items():
            if not target_subject_ids:
                excluded_locus_counts["target_has_no_callable_subjects"] += 1
                continue
            by_subject = {row.subject_id: row for row in group}
            if not target_subject_ids.issubset(by_subject):
                excluded_locus_counts["incomplete_callable_subject_set"] += 1
                continue
            paired = tuple(by_subject[subject_id] for subject_id in sorted(target_subject_ids))
            if any(not row.callable for row in paired):
                excluded_locus_counts["non_callable_for_target_subject"] += 1
                continue
            if target_subjects is not None and any(
                row.batch_id != target_subjects[subject_id].batch_id
                or row.ascertainment_group != target_subjects[subject_id].ascertainment_group
                for subject_id, row in zip(sorted(target_subject_ids), paired, strict=True)
            ):
                excluded_locus_counts["batch_or_ascertainment_mismatch"] += 1
                continue
            if not paired:
                continue
            mutability_gap = sum(
                abs(
                    row.mutability_score
                    - target_subjects.get(row.subject_id, target).mutability_score
                )
                for row in paired
            ) / len(paired)
            chromatin_gap = sum(
                abs(
                    row.chromatin_score
                    - target_subjects.get(row.subject_id, target).chromatin_score
                )
                for row in paired
            ) / len(paired)
            mutated_count = sum(row.mutated for row in paired)
            rate = mutated_count / len(paired)
            selected_candidates.append(
                (
                    mutability_gap + chromatin_gap,
                    control_locus_id,
                    (
                        ControlLocusRate(
                            locus_id=control_locus_id,
                            mutated_count=mutated_count,
                            callable_count=len(paired),
                            mutation_rate=rate,
                            mutability_gap=mutability_gap,
                            chromatin_gap=chromatin_gap,
                        ),
                    ),
                )
            )

        selected_candidates.sort(key=lambda item: (item[0], item[1]))
        rates = tuple(item[2][0] for item in selected_candidates[:limit])
        warnings: list[str] = []
        if unmatched:
            warnings.append(
                "Required matching covariates are missing; the estimate is not estimable."
            )
        if len(rates) < MIN_MATCHED_CONTROL_LOCI:
            warnings.append(
                f"Fewer than {MIN_MATCHED_CONTROL_LOCI} complete, callable matched control "
                "loci were available."
            )
        if not rates:
            warnings.append(
                "No complete matched controls were available for the target callable subjects."
            )
        mutability_gap = sum(rate.mutability_gap for rate in rates) / len(rates) if rates else 0.0
        chromatin_gap = sum(rate.chromatin_gap for rate in rates) / len(rates) if rates else 0.0
        return MatchedControl(
            target_locus_id=target.locus_id,
            control_locus_ids=tuple(rate.locus_id for rate in rates),
            matching_dimensions=(
                "reference_context",
                "disease_class",
                "ancestry_group",
                "variant_class",
                "sequence_context",
                "molecular_context",
                "recurrence_phase",
                "locus_length",
                "subject_level_callability",
                "batch_id",
                "ascertainment_group",
                "mutability_score_nearest_match",
                "chromatin_score_nearest_match",
            ),
            mean_mutability_gap=round(mutability_gap, 6),
            mean_chromatin_gap=round(chromatin_gap, 6),
            warnings=tuple(warnings),
            candidate_count=candidates,
            eligible_count=len(selected_candidates),
            effective_sample_size=float(len(rates)),
            control_rates=rates,
            unmatched_covariates=unmatched,
            excluded_locus_counts=tuple(sorted(excluded_locus_counts.items())),
        )


class RecurrenceModel:
    """Compare target recurrence only with independent matched control loci."""

    def evaluate(
        self,
        observations: Iterable[CohortObservation],
        locus_id: str,
        *,
        control_limit: int = DEFAULT_MATCHED_CONTROL_LOCI,
    ) -> RecurrenceResult:
        values = tuple(islice(observations, MAX_COHORT_OBSERVATIONS + 1))
        if len(values) > MAX_COHORT_OBSERVATIONS:
            raise ValueError(f"cohort exceeds {MAX_COHORT_OBSERVATIONS} observations")
        _validate_unique_observations(values)
        target_rows = tuple(row for row in values if row.locus_id == locus_id)
        if not target_rows:
            raise ValueError(f"locus not found: {locus_id}")
        target = target_rows[0]
        _validate_target_stratum(target_rows)
        callable_target_rows = tuple(row for row in target_rows if row.callable)
        target_subjects = {row.subject_id: row for row in callable_target_rows}
        observed = sum(row.mutated for row in callable_target_rows)
        callable_count = len(callable_target_rows)
        observed_rate = observed / callable_count if callable_count else None

        control = MatchedControlBuilder().build(
            target,
            values,
            limit=control_limit,
            target_subjects=target_subjects,
        )
        rates = tuple(rate.mutation_rate for rate in control.control_rates)
        expected_rate = sum(rates) / len(rates) if rates else None
        control_sd = (
            math.sqrt(sum((rate - expected_rate) ** 2 for rate in rates) / len(rates))
            if rates
            else None
        )
        limitations = [
            "This recurrence summary is descriptive and does not establish a driver mechanism.",
            "Support and uncertainty are uncalibrated indices, not probabilities or p-values.",
            "Matched controls reduce only declared design differences; residual confounding may "
            "remain.",
            "No multiple-testing correction or causal interpretation is performed.",
        ]
        if not callable_count:
            limitations.append(
                "The target locus has no callable subjects, so its recurrence rate is undefined."
            )
        if control.unmatched_covariates:
            limitations.append(
                "Required matching covariates are missing from one or more target observations."
            )

        estimable = (
            callable_count > 0
            and len(rates) >= MIN_MATCHED_CONTROL_LOCI
            and not control.unmatched_covariates
            and control_sd is not None
            and control_sd > 0.0
        )
        if control_sd == 0.0:
            limitations.append(
                "Matched control rates have zero variance; a standardized contrast is undefined."
            )
        if len(rates) < MIN_MATCHED_CONTROL_LOCI:
            limitations.append(
                f"At least {MIN_MATCHED_CONTROL_LOCI} complete unique matched loci are required "
                "for an estimate."
            )

        if (
            estimable
            and observed_rate is not None
            and expected_rate is not None
            and control_sd is not None
        ):
            z_like = (observed_rate - expected_rate) / control_sd
            enrichment = observed_rate / expected_rate if expected_rate > 0.0 else None
            support = max(0.0, z_like) / (1.0 + max(0.0, z_like))
            uncertainty = min(
                1.0,
                1.0 / math.sqrt(len(rates))
                + control.mean_mutability_gap
                + control.mean_chromatin_gap,
            )
            status = "estimated"
        else:
            z_like = None
            enrichment = None
            support = 0.0
            uncertainty = 1.0
            status = "not_estimable"

        return RecurrenceResult(
            locus_id=locus_id,
            status=status,
            observed_count=observed,
            callable_count=callable_count,
            observed_rate=_rounded_or_none(observed_rate),
            expected_rate=_rounded_or_none(expected_rate),
            enrichment=_rounded_or_none(enrichment),
            z_like_score=_rounded_or_none(z_like),
            support=round(support, 6),
            uncertainty=round(uncertainty, 6),
            control_rate_sd=_rounded_or_none(control_sd),
            matched_control=control,
            limitations=tuple(dict.fromkeys((*limitations, *control.warnings))),
        )


def _matches_global_dimensions(row: CohortObservation, target: CohortObservation) -> bool:
    return all(getattr(row, name) == getattr(target, name) for name in _GLOBAL_MATCH_FIELDS)


def _observation_text(value: object, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string")
    return value


def _observation_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _observation_score(value: object, name: str) -> float:
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be a number")
    try:
        return float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error


def _validate_unique_observations(values: tuple[CohortObservation, ...]) -> None:
    observation_ids: set[str] = set()
    subject_locus_pairs: set[tuple[str, str]] = set()
    for row in values:
        if row.observation_id in observation_ids:
            raise ValueError(f"duplicate cohort observation_id: {row.observation_id}")
        observation_ids.add(row.observation_id)
        subject_locus = (row.subject_id, row.locus_id)
        if subject_locus in subject_locus_pairs:
            raise ValueError("cohort contains duplicate subject-by-locus observations")
        subject_locus_pairs.add(subject_locus)


def _validate_target_stratum(rows: tuple[CohortObservation, ...]) -> None:
    first = rows[0]
    for row in rows[1:]:
        if not _matches_global_dimensions(row, first):
            raise ValueError("target locus spans multiple contexts or matching strata")


def _rounded_or_none(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


__all__ = [
    "MAX_COHORT_OBSERVATIONS",
    "MAX_MATCHED_CONTROL_LOCI",
    "MIN_MATCHED_CONTROL_LOCI",
    "CohortObservation",
    "ControlLocusRate",
    "MatchedControl",
    "MatchedControlBuilder",
    "RecurrenceModel",
    "RecurrenceResult",
]

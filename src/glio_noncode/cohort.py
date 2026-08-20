"""Matched-background cohort controls for recurrence and convergence views."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .models import ReferenceContext


@dataclass(frozen=True, slots=True)
class CohortObservation:
    """One callable observation in a defined cohort context."""

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

    def __post_init__(self) -> None:
        for value in (self.mutability_score, self.chromatin_score):
            if not 0.0 <= value <= 1.0:
                raise ValueError("cohort scores must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class MatchedControl:
    """A control set description and its selection diagnostics."""

    target_locus_id: str
    control_locus_ids: tuple[str, ...]
    matching_dimensions: tuple[str, ...]
    mean_mutability_gap: float
    mean_chromatin_gap: float
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecurrenceResult:
    """Recurrence result with a local background rather than a raw count."""

    locus_id: str
    observed_count: int
    callable_count: int
    expected_rate: float
    enrichment: float
    z_like_score: float
    support: float
    uncertainty: float
    matched_control: MatchedControl
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "locus_id": self.locus_id,
            "observed_count": self.observed_count,
            "callable_count": self.callable_count,
            "expected_rate": self.expected_rate,
            "enrichment": self.enrichment,
            "z_like_score": self.z_like_score,
            "support": self.support,
            "uncertainty": self.uncertainty,
            "matched_control": {
                "target_locus_id": self.matched_control.target_locus_id,
                "control_locus_ids": list(self.matched_control.control_locus_ids),
                "matching_dimensions": list(self.matched_control.matching_dimensions),
                "mean_mutability_gap": self.matched_control.mean_mutability_gap,
                "mean_chromatin_gap": self.matched_control.mean_chromatin_gap,
                "warnings": list(self.matched_control.warnings),
            },
            "limitations": list(self.limitations),
        }


class MatchedControlBuilder:
    """Select transparent controls using only declared dimensions."""

    def build(self, target: CohortObservation, pool: Iterable[CohortObservation], *, limit: int = 20) -> MatchedControl:
        candidates = [
            observation
            for observation in pool
            if observation.locus_id != target.locus_id
            and observation.callable
            and observation.disease_class == target.disease_class
            and observation.ancestry_group == target.ancestry_group
            and observation.context.genome_build == target.context.genome_build
        ]
        candidates.sort(
            key=lambda item: (
                abs(item.mutability_score - target.mutability_score)
                + abs(item.chromatin_score - target.chromatin_score),
                item.locus_id,
            )
        )
        selected = candidates[:limit]
        warnings: list[str] = []
        if len(selected) < 5:
            warnings.append("Fewer than five matched control loci were available.")
        if not selected:
            warnings.append("No matched controls were available; recurrence is not interpretable.")
        mutability_gap = sum(abs(item.mutability_score - target.mutability_score) for item in selected) / max(1, len(selected))
        chromatin_gap = sum(abs(item.chromatin_score - target.chromatin_score) for item in selected) / max(1, len(selected))
        return MatchedControl(
            target_locus_id=target.locus_id,
            control_locus_ids=tuple(item.locus_id for item in selected),
            matching_dimensions=("genome_build", "disease_class", "ancestry_group", "mutability_score", "chromatin_score"),
            mean_mutability_gap=round(mutability_gap, 6),
            mean_chromatin_gap=round(chromatin_gap, 6),
            warnings=tuple(warnings),
        )


class RecurrenceModel:
    """Compute a cautious enrichment view for a locus."""

    def evaluate(self, observations: Iterable[CohortObservation], locus_id: str) -> RecurrenceResult:
        values = list(observations)
        target_rows = [row for row in values if row.locus_id == locus_id]
        if not target_rows:
            raise ValueError(f"locus not found: {locus_id}")
        target = target_rows[0]
        callable_rows = [row for row in values if row.callable and row.disease_class == target.disease_class]
        observed = sum(row.mutated for row in target_rows)
        callable_count = len(callable_rows)
        if callable_count == 0:
            expected_rate = 0.0
        else:
            weighted_total = sum(0.5 + row.mutability_score + 0.5 * row.chromatin_score for row in callable_rows)
            weighted_mutations = sum(
                (0.5 + row.mutability_score + 0.5 * row.chromatin_score) for row in callable_rows if row.mutated
            )
            expected_rate = min(1.0, weighted_mutations / max(weighted_total, 1e-9))
        control = MatchedControlBuilder().build(target, values)
        expected_count = max(1e-9, expected_rate * max(1, len(target_rows)))
        enrichment = observed / expected_count
        variance = max(expected_count, 1.0)
        z_like = (observed - expected_count) / math.sqrt(variance)
        support = 1.0 - math.exp(-max(0.0, z_like) / 2.0)
        uncertainty = min(1.0, 0.45 + 0.1 * len(control.warnings) + control.mean_mutability_gap + control.mean_chromatin_gap)
        limitations = (
            "This is a recurrence view, not proof of a driver mechanism.",
            "Callable-space, ascertainment, ancestry, batch, and cohort composition can alter the estimate.",
        )
        return RecurrenceResult(
            locus_id=locus_id,
            observed_count=observed,
            callable_count=callable_count,
            expected_rate=round(expected_rate, 6),
            enrichment=round(enrichment, 6),
            z_like_score=round(z_like, 6),
            support=round(support, 6),
            uncertainty=round(uncertainty, 6),
            matched_control=control,
            limitations=limitations,
        )

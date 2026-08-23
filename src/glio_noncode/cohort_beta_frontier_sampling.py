"""Sampling and denominator notes for aggregate cohort inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSamplingNote:
    operation: str
    sample_unit: str
    denominator: str
    observed_sample_count: int
    observed_variant_count: int
    inclusion_rules: tuple[str, ...]
    exclusion_rules: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSamplingReport:
    notes: tuple[CohortBetaFrontierSamplingNote, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_sampling_report(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierSamplingReport:
    notes = []
    for operation in ("C05", "C06", "C07", "C08"):
        rows = tuple(item for item in evaluation.rows if item.operation == operation)
        counts = [int(item.result.get("observed_sample_count", item.result.get("observed_gene_count", 0))) for item in rows]
        variants = [int(item.result.get("observed_variant_count", 0)) for item in rows]
        if operation == "C05":
            unit, denominator = "distinct pseudonymous samples", "callable recurrence observations"
        elif operation == "C06":
            unit, denominator = "distinct pseudonymous variants", "callable bases in selected region"
        elif operation == "C07":
            unit, denominator = "distinct variants and samples", "feature support rows"
        else:
            unit, denominator = "distinct genes and variants", "versioned set membership rows"
        inclusion = ("exact target context", "valid typed row", "public source receipt")
        exclusion = ("foreign context", "invalid row", "non-callable row where required")
        notes.append(CohortBetaFrontierSamplingNote(operation, unit, denominator, max(counts, default=0), max(variants, default=0), inclusion, exclusion, content_hash({"operation": operation, "unit": unit, "denominator": denominator, "counts": counts}, prefix="sampling-note")))
    return CohortBetaFrontierSamplingReport(tuple(notes), len(notes) == 4 and all(item.observed_sample_count >= 0 for item in notes), content_hash({"fixture": fixture.fixture_id, "notes": notes}, prefix="sampling-report"))


def sampling_summary(report: CohortBetaFrontierSamplingReport) -> Mapping[str, Any]:
    return {"accepted": report.accepted, "operations": {item.operation: {"sample_unit": item.sample_unit, "denominator": item.denominator, "observed_sample_count": item.observed_sample_count, "observed_variant_count": item.observed_variant_count} for item in report.notes}}


__all__ = ["CohortBetaFrontierSamplingNote", "CohortBetaFrontierSamplingReport", "build_cohort_beta_frontier_sampling_report", "sampling_summary"]

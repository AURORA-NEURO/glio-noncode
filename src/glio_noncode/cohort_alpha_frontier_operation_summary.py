"""Per-operation summaries used by report cards and review handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationSummary:
    operation: str
    title: str
    total: int
    supported: int
    review: int
    quarantine: int
    claim: str
    limitation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationSummaryReport:
    summaries: tuple[CohortAlphaFrontierOperationSummary, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_operation_summaries(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierOperationSummaryReport:
    names = {
        "C09": ("clonality and timing", "descriptive clonal fraction and phase summary"),
        "C10": ("primary and recurrence", "descriptive phase-specific frequency comparison"),
        "C11": ("treatment selection", "descriptive pre/post frequency signal"),
        "C12": ("cross-cohort replication", "descriptive direction concordance summary"),
    }
    summaries = []
    for operation in ("C09", "C10", "C11", "C12"):
        rows = tuple(row for row in evaluation.rows if row.operation == operation)
        decisions = tuple(policy.for_record(row.record_id) for row in rows)
        title, claim = names[operation]
        summaries.append(CohortAlphaFrontierOperationSummary(operation, title, len(rows), sum(row.observed_state.value == "supported" for row in rows), sum(item.disposition.value == "review" for item in decisions), sum(item.disposition.value == "quarantine" for item in decisions), claim, "aggregate and descriptive; incomplete or foreign paths are not publication evidence", content_hash({"operation": operation, "title": title, "total": len(rows), "supported": sum(row.observed_state.value == "supported" for row in rows), "review": sum(item.disposition.value == "review" for item in decisions), "quarantine": sum(item.disposition.value == "quarantine" for item in decisions), "claim": claim}, prefix="alpha-operation-summary")))
    values = tuple(summaries)
    return CohortAlphaFrontierOperationSummaryReport(values, len(values) == 4 and all(item.total == 4 for item in values), content_hash(values, prefix="alpha-operation-summaries"))


__all__ = ["CohortAlphaFrontierOperationSummary", "CohortAlphaFrontierOperationSummaryReport", "build_cohort_alpha_frontier_operation_summaries"]

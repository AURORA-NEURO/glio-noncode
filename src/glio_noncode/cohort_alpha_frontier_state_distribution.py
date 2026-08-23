"""State distribution summaries by operation and control boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha import CohortAlphaState
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierStateDistributionRow:
    operation: str
    counts: dict[str, int]
    total: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierStateDistribution:
    rows: tuple[CohortAlphaFrontierStateDistributionRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_state_distribution(evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierStateDistribution:
    rows = []
    for operation in ("C09", "C10", "C11", "C12"):
        selected = tuple(row for row in evaluation.rows if row.operation == operation)
        counts = {state.value: sum(row.observed_state is state for row in selected) for state in CohortAlphaState}
        accepted = len(selected) == 4 and counts["supported"] == 1 and counts["out_of_domain"] == 1 and counts["abstained"] == 1 and (operation != "C12" and counts["partial"] == 1 or operation == "C12" and counts["ambiguous"] == 1)
        rows.append(CohortAlphaFrontierStateDistributionRow(operation, counts, len(selected), accepted, content_hash({"operation": operation, "counts": counts, "total": len(selected), "accepted": accepted}, prefix="alpha-state-distribution")))
    values = tuple(rows)
    return CohortAlphaFrontierStateDistribution(values, all(item.accepted for item in values), content_hash(values, prefix="alpha-state-distribution-report"))


__all__ = ["CohortAlphaFrontierStateDistribution", "CohortAlphaFrontierStateDistributionRow", "build_cohort_alpha_frontier_state_distribution"]

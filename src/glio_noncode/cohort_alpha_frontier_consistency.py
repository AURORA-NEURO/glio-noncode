"""Cross-object consistency checks for the alpha release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierConsistencyCheck:
    check_id: str
    left_value: int
    right_value: int
    equal: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierConsistencyReport:
    checks: tuple[CohortAlphaFrontierConsistencyCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_consistency(evaluation: CohortAlphaFrontierEvaluation, metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierConsistencyReport:
    raw = (
        ("rows-metrics", len(evaluation.rows), metrics.total_rows, "evaluation and metrics row totals"),
        ("rows-policy", len(evaluation.rows), len(policy.decisions), "evaluation and policy row totals"),
        ("accepted-metrics", sum(row.accepted for row in evaluation.rows), metrics.accepted_rows, "accepted rows match metrics"),
        ("supported-metrics", sum(row.observed_state.value == "supported" for row in evaluation.rows), metrics.supported_rows, "supported rows match metrics"),
        ("partition-policy", len(policy.decisions), policy.publishable_count + policy.review_count + policy.quarantine_count, "policy partitions cover all rows"),
    )
    checks = tuple(CohortAlphaFrontierConsistencyCheck(check_id, left, right, left == right, detail, content_hash({"id": check_id, "left": left, "right": right, "equal": left == right, "detail": detail}, prefix="alpha-consistency")) for check_id, left, right, detail in raw)
    return CohortAlphaFrontierConsistencyReport(checks, all(item.equal for item in checks), content_hash(checks, prefix="alpha-consistency-report"))


__all__ = ["CohortAlphaFrontierConsistencyCheck", "CohortAlphaFrontierConsistencyReport", "evaluate_cohort_alpha_frontier_consistency"]

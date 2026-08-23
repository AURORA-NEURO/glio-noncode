"""Runtime statistics kept separate from scientific result metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRuntimeStatistics:
    stage_count: int
    accepted_stage_count: int
    failed_stage_count: int
    extended_receipt_count: int
    acceptance_percent: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_cohort_alpha_frontier_runtime_statistics(stages: tuple[CohortAlphaFrontierRuntimeStage, ...], extended_receipt_count: int) -> CohortAlphaFrontierRuntimeStatistics:
    accepted = sum(stage.accepted for stage in stages)
    body = {"stages": len(stages), "accepted": accepted, "failed": len(stages) - accepted, "extended": extended_receipt_count}
    return CohortAlphaFrontierRuntimeStatistics(len(stages), accepted, len(stages) - accepted, extended_receipt_count, round(100 * accepted / max(1, len(stages)), 2), content_hash(body, prefix="alpha-runtime-statistics"))


__all__ = ["CohortAlphaFrontierRuntimeStatistics", "measure_cohort_alpha_frontier_runtime_statistics"]

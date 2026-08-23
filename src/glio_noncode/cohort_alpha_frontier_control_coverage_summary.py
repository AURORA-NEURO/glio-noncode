"""Summary of control classes and their intended responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_control_registry import CohortAlphaFrontierControlRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierControlCoverageSummary:
    positive_count: int
    incomplete_count: int
    contradictory_count: int
    foreign_count: int
    empty_count: int
    total_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def summarize_cohort_alpha_frontier_controls(registry: CohortAlphaFrontierControlRegistry) -> CohortAlphaFrontierControlCoverageSummary:
    counts = registry.observed_counts
    values = (counts.get("positive", 0), counts.get("incomplete_control", 0), counts.get("contradictory_control", 0), counts.get("foreign_context", 0), counts.get("empty_control", 0))
    body = {"positive": values[0], "incomplete": values[1], "contradictory": values[2], "foreign": values[3], "empty": values[4], "total": sum(values)}
    return CohortAlphaFrontierControlCoverageSummary(*values, sum(values), registry.accepted and sum(values) == 16, content_hash(body, prefix="alpha-control-summary"))


__all__ = ["CohortAlphaFrontierControlCoverageSummary", "summarize_cohort_alpha_frontier_controls"]

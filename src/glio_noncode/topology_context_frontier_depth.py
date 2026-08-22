"""Depth audit for topology evidence and controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import TopologyContextFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierDepthDimension:
    dimension_id: str
    observed: float
    threshold: float
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierDepthReport:
    dimensions: tuple[TopologyContextFrontierDepthDimension, ...]
    accepted: bool
    mean_depth: float
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "dimensions": [item.to_dict() for item in self.dimensions],
            "accepted": self.accepted,
            "mean_depth": self.mean_depth,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_context_frontier_depth(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierDepthReport:
    total = max(1, len(evaluation.rows))
    dimensions = (
        TopologyContextFrontierDepthDimension(
            "fixture",
            min(1.0, len(fixture.records) / 16),
            1.0,
            len(fixture.records) == 16,
            "closed fixture cardinality",
        ),
        TopologyContextFrontierDepthDimension(
            "state",
            evaluation.state_match_count / total,
            1.0,
            evaluation.state_match_count == total,
            "state expectations",
        ),
        TopologyContextFrontierDepthDimension(
            "issues",
            evaluation.issue_match_count / total,
            0.75,
            evaluation.issue_match_count / total >= 0.75,
            "issue floors",
        ),
        TopologyContextFrontierDepthDimension(
            "operations",
            len({item.operation for item in evaluation.rows}) / 4,
            1.0,
            len({item.operation for item in evaluation.rows}) == 4,
            "operation diversity",
        ),
        TopologyContextFrontierDepthDimension(
            "controls",
            len(fixture.control_records) / 12,
            1.0,
            len(fixture.control_records) == 12,
            "negative controls",
        ),
        TopologyContextFrontierDepthDimension(
            "receipts",
            min(1.0, len(fixture.sources) / 4),
            1.0,
            len(fixture.sources) == 4,
            "source receipts",
        ),
    )
    mean_depth = round(sum(item.observed for item in dimensions) / len(dimensions), 6)
    return TopologyContextFrontierDepthReport(
        dimensions, all(item.passed for item in dimensions), mean_depth
    )


__all__ = [
    "TopologyContextFrontierDepthDimension",
    "TopologyContextFrontierDepthReport",
    "audit_topology_context_frontier_depth",
]

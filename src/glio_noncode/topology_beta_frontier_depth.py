"""Depth accounting across identity, context, signal, and provenance fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierDepthDimension:
    dimension: str
    observed: int
    expected: int
    coverage: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierDepthReport:
    dimensions: tuple[TopologyBetaFrontierDepthDimension, ...]
    mean_depth: float
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def dimension(self, name: str) -> TopologyBetaFrontierDepthDimension:
        for item in self.dimensions:
            if item.dimension == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"dimensions": [item.to_dict() for item in self.dimensions], "mean_depth": self.mean_depth, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_beta_frontier_depth(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierDepthReport:
    total = len(evaluation.rows)
    dimensions = (
        TopologyBetaFrontierDepthDimension("operation_identity", len({item.operation for item in evaluation.rows}), 4, len({item.operation for item in evaluation.rows}) / 4, "all four operation identities are present"),
        TopologyBetaFrontierDepthDimension("record_context", sum(bool(item.adapter.measurements) for item in evaluation.rows), total, sum(bool(item.adapter.measurements) for item in evaluation.rows) / total, "each replay has measurements"),
        TopologyBetaFrontierDepthDimension("source_lineage", sum(bool(item.adapter.source_ids) for item in evaluation.rows), total, sum(bool(item.adapter.source_ids) for item in evaluation.rows) / total, "every result retains source IDs"),
        TopologyBetaFrontierDepthDimension("evidence_identity", sum(bool(item.adapter.evidence_ids) for item in evaluation.rows), total, sum(bool(item.adapter.evidence_ids) for item in evaluation.rows) / total, "every nonempty operation retains evidence IDs"),
        TopologyBetaFrontierDepthDimension("content_address", sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), total, sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows) / total, "every result has a content address"),
        TopologyBetaFrontierDepthDimension("public_boundary", sum(bool(row.payload.get("public_aggregate")) for row in fixture.records), len(fixture.records), sum(bool(row.payload.get("public_aggregate")) for row in fixture.records) / len(fixture.records), "every fixture payload declares aggregate scope"),
    )
    mean_depth = sum(item.coverage for item in dimensions) / len(dimensions)
    return TopologyBetaFrontierDepthReport(dimensions, mean_depth, mean_depth >= 0.95)


__all__ = ["TopologyBetaFrontierDepthDimension", "TopologyBetaFrontierDepthReport", "audit_topology_beta_frontier_depth"]

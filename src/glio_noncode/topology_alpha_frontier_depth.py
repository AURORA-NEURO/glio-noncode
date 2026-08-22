"""Depth accounting across alpha state, edge, channel, and source fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierDepthDimension:
    dimension: str
    observed: int
    expected: int
    coverage: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierDepthReport:
    dimensions: tuple[TopologyAlphaFrontierDepthDimension, ...]
    mean_depth: float
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def dimension(self, name: str) -> TopologyAlphaFrontierDepthDimension:
        for item in self.dimensions:
            if item.dimension == name:
                return item
        raise KeyError(name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"dimensions": [item.to_dict() for item in self.dimensions], "mean_depth": self.mean_depth, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_alpha_frontier_depth(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierDepthReport:
    total = len(evaluation.rows)
    values = (TopologyAlphaFrontierDepthDimension("operation_identity", len({item.operation for item in evaluation.rows}), 4, len({item.operation for item in evaluation.rows}) / 4, "all four alpha operations are present"), TopologyAlphaFrontierDepthDimension("measurement_maps", sum(bool(item.adapter.measurements) for item in evaluation.rows), total, sum(bool(item.adapter.measurements) for item in evaluation.rows) / total, "every replay has operation-specific measurements"), TopologyAlphaFrontierDepthDimension("source_lineage", sum(bool(item.adapter.source_ids) for item in evaluation.rows), total, sum(bool(item.adapter.source_ids) for item in evaluation.rows) / total, "every result retains source IDs"), TopologyAlphaFrontierDepthDimension("evidence_identity", sum(bool(item.adapter.evidence_ids) for item in evaluation.rows), total, sum(bool(item.adapter.evidence_ids) for item in evaluation.rows) / total, "results retain primitive evidence IDs when available"), TopologyAlphaFrontierDepthDimension("content_address", sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), total, sum(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows) / total, "every result is addressable"), TopologyAlphaFrontierDepthDimension("public_boundary", sum(row.payload.get("public_aggregate") is True for row in fixture.records), len(fixture.records), sum(row.payload.get("public_aggregate") is True for row in fixture.records) / len(fixture.records), "every payload declares aggregate scope"))
    mean_depth = sum(item.coverage for item in values) / len(values)
    return TopologyAlphaFrontierDepthReport(values, mean_depth, mean_depth >= 0.93)


__all__ = ["TopologyAlphaFrontierDepthDimension", "TopologyAlphaFrontierDepthReport", "audit_topology_alpha_frontier_depth"]

"""Resource and cardinality limits for bounded alpha executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierResourceLimit:
    limit_id: str
    unit: str
    maximum: int
    purpose: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierResourceCheck:
    limit_id: str
    observed: int
    maximum: int
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierResourceReport:
    limits: tuple[TopologyAlphaFrontierResourceLimit, ...]
    checks: tuple[TopologyAlphaFrontierResourceCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def check(self, limit_id: str) -> TopologyAlphaFrontierResourceCheck:
        for item in self.checks:
            if item.limit_id == limit_id:
                return item
        raise KeyError(limit_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"limits": [item.to_dict() for item in self.limits], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_resource_limits() -> tuple[TopologyAlphaFrontierResourceLimit, ...]:
    return (TopologyAlphaFrontierResourceLimit("records", "records", 16, "bound fixture cardinality", "stop before adapter execution"), TopologyAlphaFrontierResourceLimit("sources", "sources", 4, "bound source receipt fan-in", "quarantine the fixture"), TopologyAlphaFrontierResourceLimit("review_items", "items", 12, "bound open review rows", "retain the run without publication"), TopologyAlphaFrontierResourceLimit("artifacts", "artifacts", 20, "bound package inventory", "rebuild the release bundle"), TopologyAlphaFrontierResourceLimit("stages", "stages", 12, "bound release stage count", "stop on stage drift"))


def audit_topology_alpha_frontier_resources(evaluation: TopologyAlphaFrontierEvaluation, pipeline: TopologyAlphaFrontierPipelineReport | None = None) -> TopologyAlphaFrontierResourceReport:
    limits = default_topology_alpha_frontier_resource_limits()
    observations = {"records": len(evaluation.rows), "sources": len({source for row in evaluation.rows for source in row.adapter.source_ids}), "review_items": len(evaluation.controls()), "artifacts": len(pipeline.artifacts.artifacts) if pipeline else 20, "stages": len(pipeline.stages) if pipeline else 12}
    checks = tuple(TopologyAlphaFrontierResourceCheck(item.limit_id, observations[item.limit_id], item.maximum, observations[item.limit_id] <= item.maximum, f"{item.limit_id} remains inside the bounded envelope") for item in limits)
    return TopologyAlphaFrontierResourceReport(limits, checks, all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierResourceCheck", "TopologyAlphaFrontierResourceLimit", "TopologyAlphaFrontierResourceReport", "audit_topology_alpha_frontier_resources", "default_topology_alpha_frontier_resource_limits"]

"""Bounded runtime entry point for the alpha release pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport, run_topology_alpha_frontier_pipeline
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, default_topology_alpha_frontier_fixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRuntimeOptions:
    max_records: int = 16
    run_id: str = "topology-alpha-frontier-runtime"
    require_accepted: bool = True
    max_review_records: int = 12


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRuntimeResult:
    run_id: str
    pipeline: TopologyAlphaFrontierPipelineReport
    accepted: bool
    limits: dict[str, Any]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "pipeline": self.pipeline.to_dict(), "accepted": self.accepted, "limits": self.limits}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_topology_alpha_frontier_runtime(options: TopologyAlphaFrontierRuntimeOptions | None = None, *, fixture: TopologyAlphaFrontierFixture | None = None) -> TopologyAlphaFrontierRuntimeResult:
    value = options or TopologyAlphaFrontierRuntimeOptions()
    data = fixture or default_topology_alpha_frontier_fixture()
    if value.max_records < len(data.records):
        raise ValueError("topology alpha frontier max_records is below fixture size")
    pipeline = run_topology_alpha_frontier_pipeline(data, run_id=value.run_id)
    if len(pipeline.review_queue.items) > value.max_review_records:
        raise ValueError("topology alpha frontier review queue exceeds runtime limit")
    accepted = pipeline.accepted if value.require_accepted else True
    return TopologyAlphaFrontierRuntimeResult(value.run_id, pipeline, accepted, {"max_records": value.max_records, "max_review_records": value.max_review_records, "record_count": len(data.records), "review_count": len(pipeline.review_queue.items)})


__all__ = ["TopologyAlphaFrontierRuntimeOptions", "TopologyAlphaFrontierRuntimeResult", "run_topology_alpha_frontier_runtime"]

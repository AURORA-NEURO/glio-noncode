"""Runtime options for the C01-C04 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_pipeline import LinkGraphFoundationFrontierPipelineReport, run_link_graph_foundation_frontier_pipeline
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRuntimeOptions:
    run_id: str = "link-graph-foundation-frontier-runtime"
    include_payload: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRuntimeResult:
    run_id: str
    accepted: bool
    failed_stages: tuple[str, ...]
    pipeline: LinkGraphFoundationFrontierPipelineReport | None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"run_id": self.run_id, "accepted": self.accepted, "failed_stages": self.failed_stages}))

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "accepted": self.accepted, "failed_stages": self.failed_stages, "pipeline": self.pipeline.to_dict() if self.pipeline else None, "content_address": self.content_address}


def run_link_graph_foundation_frontier_runtime(options: LinkGraphFoundationFrontierRuntimeOptions | None = None) -> LinkGraphFoundationFrontierRuntimeResult:
    selected = options or LinkGraphFoundationFrontierRuntimeOptions()
    pipeline = run_link_graph_foundation_frontier_pipeline(run_id=selected.run_id)
    return LinkGraphFoundationFrontierRuntimeResult(selected.run_id, pipeline.accepted, pipeline.failed_stages, pipeline if selected.include_payload else None)


__all__ = ["LinkGraphFoundationFrontierRuntimeOptions", "LinkGraphFoundationFrontierRuntimeResult", "run_link_graph_foundation_frontier_runtime"]

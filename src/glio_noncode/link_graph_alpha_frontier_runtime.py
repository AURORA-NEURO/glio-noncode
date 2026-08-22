"""Runtime entry point with bounded options and explicit execution result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport, run_link_graph_alpha_frontier_pipeline
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierRuntimeOptions:
    run_id: str = "link-graph-alpha-frontier-runtime"
    include_payload: bool = True
    require_accepted: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierRuntimeResult:
    run_id: str
    accepted: bool
    failed_stages: tuple[str, ...]
    pipeline: LinkGraphAlphaFrontierPipelineReport | None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash({"run_id": self.run_id, "accepted": self.accepted, "failed_stages": self.failed_stages, "pipeline": self.pipeline.content_address if self.pipeline else None}))

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "accepted": self.accepted, "failed_stages": self.failed_stages, "pipeline": self.pipeline.to_dict() if self.pipeline else None, "content_address": self.content_address}


def run_link_graph_alpha_frontier_runtime(options: LinkGraphAlphaFrontierRuntimeOptions | None = None) -> LinkGraphAlphaFrontierRuntimeResult:
    selected = options or LinkGraphAlphaFrontierRuntimeOptions()
    pipeline = run_link_graph_alpha_frontier_pipeline(run_id=selected.run_id)
    accepted = pipeline.accepted if selected.require_accepted else True
    return LinkGraphAlphaFrontierRuntimeResult(selected.run_id, accepted, pipeline.failed_stages, pipeline if selected.include_payload else None)


__all__ = ["LinkGraphAlphaFrontierRuntimeOptions", "LinkGraphAlphaFrontierRuntimeResult", "run_link_graph_alpha_frontier_runtime"]

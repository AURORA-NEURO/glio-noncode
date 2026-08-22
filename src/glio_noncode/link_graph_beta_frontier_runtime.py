"""Runtime options and bounded output for beta frontier execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_pipeline import run_link_graph_beta_frontier_pipeline
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierRuntimeOptions:
    run_id: str = "link-graph-beta-frontier-runtime"
    include_payload: bool = False
    max_rows: int = 16


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierRuntimeResult:
    run_id: str
    accepted: bool
    row_count: int
    payload: dict[str, Any]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "accepted": self.accepted, "row_count": self.row_count, "payload": self.payload}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_beta_frontier_runtime(options: LinkGraphBetaFrontierRuntimeOptions | None = None) -> LinkGraphBetaFrontierRuntimeResult:
    selected = options or LinkGraphBetaFrontierRuntimeOptions()
    if selected.max_rows <= 0:
        raise ValueError("max_rows must be positive")
    pipeline = run_link_graph_beta_frontier_pipeline(run_id=selected.run_id)
    row_count = min(selected.max_rows, len(pipeline.evaluation.rows))
    if selected.include_payload:
        payload = pipeline.to_dict()
        evaluation_payload = dict(payload["evaluation"])
        evaluation_payload["rows"] = list(evaluation_payload["rows"])[:row_count]
        payload["evaluation"] = evaluation_payload
    else:
        payload = {"failed_stages": pipeline.failed_stages, "state_accuracy": pipeline.metrics.state_accuracy, "release": pipeline.release.to_dict()}
    return LinkGraphBetaFrontierRuntimeResult(selected.run_id, pipeline.accepted, row_count, payload, content_hash(payload))


__all__ = ["LinkGraphBetaFrontierRuntimeOptions", "LinkGraphBetaFrontierRuntimeResult", "run_link_graph_beta_frontier_runtime"]

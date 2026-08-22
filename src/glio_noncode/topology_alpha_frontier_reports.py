"""Human-readable alpha operation summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_metrics import TopologyAlphaFrontierMetrics
from .topology_alpha_frontier_quality_gate import TopologyAlphaFrontierQualityReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReport:
    report_id: str
    title: str
    fixture_id: str
    summary: str
    operation_summaries: dict[str, dict[str, Any]]
    quality_score: float
    accepted: bool
    limitations: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"report_id": self.report_id, "title": self.title, "fixture_id": self.fixture_id, "summary": self.summary, "operation_summaries": self.operation_summaries, "quality_score": self.quality_score, "accepted": self.accepted, "limitations": self.limitations}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_report(evaluation: TopologyAlphaFrontierEvaluation, metrics: TopologyAlphaFrontierMetrics, quality: TopologyAlphaFrontierQualityReport) -> TopologyAlphaFrontierReport:
    summaries = {operation: {"record_count": len(evaluation.by_operation(operation)), "states": {state: len(tuple(row for row in evaluation.by_operation(operation) if row.observed_state == state)) for state in {row.observed_state for row in evaluation.by_operation(operation)}}, "review_count": len(tuple(row for row in evaluation.by_operation(operation) if row.role == "control"))} for operation in sorted({item.operation for item in evaluation.rows})}
    return TopologyAlphaFrontierReport("topology-alpha-frontier-report", "Domain 09 topology alpha aggregate review", evaluation.fixture_id, "Four topology-alpha operations replayed with positive and control records.", summaries, quality.quality_score, bool(evaluation.accepted and metrics.accepted and quality.accepted), ("Public aggregate scope only.", "State, orientation, channel, and edge outputs remain descriptive.", "External calibration remains separate."))


__all__ = ["TopologyAlphaFrontierReport", "build_topology_alpha_frontier_report"]

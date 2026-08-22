"""Structured report sections for topology context evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_metrics import TopologyContextFrontierMetrics
from .topology_context_frontier_quality_gate import TopologyContextFrontierQualityReport


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReportSection:
    section_id: str
    title: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierReport:
    sections: tuple[TopologyContextFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"sections": [item.to_dict() for item in self.sections], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_report(
    evaluation: TopologyContextFrontierEvaluation,
    metrics: TopologyContextFrontierMetrics,
    quality: TopologyContextFrontierQualityReport,
) -> TopologyContextFrontierReport:
    sections = (
        TopologyContextFrontierReportSection(
            "coverage",
            "Operation coverage",
            "accepted" if evaluation.accepted else "review",
            f"{len(evaluation.rows)} records",
        ),
        TopologyContextFrontierReportSection(
            "states",
            "State accounting",
            "accepted" if evaluation.state_match_count == 16 else "review",
            f"{evaluation.state_match_count}/16 matches",
        ),
        TopologyContextFrontierReportSection(
            "metrics",
            "Operational metrics",
            "accepted" if metrics.accepted else "review",
            f"{len(metrics.metrics)} metrics",
        ),
        TopologyContextFrontierReportSection(
            "quality",
            "Quality gate",
            "accepted" if quality.accepted else "review",
            f"{len(quality.checks)} checks",
        ),
        TopologyContextFrontierReportSection(
            "limits", "Evidence limits", "bounded", "Descriptive topology evidence only"
        ),
    )
    return TopologyContextFrontierReport(
        sections, all(item.status in {"accepted", "bounded"} for item in sections)
    )


__all__ = [
    "TopologyContextFrontierReport",
    "TopologyContextFrontierReportSection",
    "build_topology_context_frontier_report",
]

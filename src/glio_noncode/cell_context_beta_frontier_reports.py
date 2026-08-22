"""Human-readable report sections for beta release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_metrics import CellContextBetaFrontierMetrics
from .cell_context_beta_frontier_quality_gate import CellContextBetaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierReportSection:
    section_id: str
    title: str
    summary: str
    rows: tuple[dict[str, Any], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.section_id or not self.title or not self.summary:
            raise ValueError("beta report section is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierReport:
    report_id: str
    sections: tuple[CellContextBetaFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError("beta report has no sections")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_beta_frontier_report(
    evaluation: CellContextBetaFrontierEvaluation,
    metrics: CellContextBetaFrontierMetrics,
    quality: CellContextBetaFrontierQualityReport,
) -> CellContextBetaFrontierReport:
    sections = (
        CellContextBetaFrontierReportSection(
            "coverage",
            "Coverage",
            "All four beta prior families execute against the closed fixture.",
            (
                {
                    "records": len(evaluation.records),
                    "positive": len(evaluation.positive_rows),
                    "controls": len(evaluation.control_rows),
                },
            ),
        ),
        CellContextBetaFrontierReportSection(
            "states",
            "States",
            "Support, ambiguity, quarantine, and domain refusal remain distinct.",
            tuple(
                {"record_id": item.record_id, "state": item.observed_state}
                for item in evaluation.records
            ),
        ),
        CellContextBetaFrontierReportSection(
            "metrics",
            "Metrics",
            "Bounded support metrics are review summaries rather than probabilities.",
            tuple(item.to_dict() for item in metrics.metrics),
        ),
        CellContextBetaFrontierReportSection(
            "quality",
            "Quality",
            "Release quality checks are retained with their observed values.",
            tuple(item.to_dict() for item in quality.checks),
        ),
    )
    return CellContextBetaFrontierReport(
        "cell-context-beta-frontier-report", sections, evaluation.accepted and quality.accepted
    )


__all__ = [
    "CellContextBetaFrontierReport",
    "CellContextBetaFrontierReportSection",
    "build_cell_context_beta_frontier_report",
]

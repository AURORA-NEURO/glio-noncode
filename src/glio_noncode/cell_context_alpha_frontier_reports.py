"""Structured report sections for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_metrics import CellContextAlphaFrontierMetrics
from .cell_context_alpha_frontier_quality_gate import CellContextAlphaFrontierQualityReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReportSection:
    section_id: str
    title: str
    summary: str
    rows: tuple[dict[str, Any], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReport:
    report_id: str
    sections: tuple[CellContextAlphaFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_alpha_frontier_report(
    evaluation: CellContextAlphaFrontierEvaluation,
    metrics: CellContextAlphaFrontierMetrics,
    quality: CellContextAlphaFrontierQualityReport,
) -> CellContextAlphaFrontierReport:
    sections = (
        CellContextAlphaFrontierReportSection(
            "coverage",
            "Coverage",
            "Four context-alpha priors execute against aggregate evidence.",
            (
                {
                    "records": len(evaluation.records),
                    "positive": len(evaluation.positive_rows),
                    "controls": len(evaluation.control_rows),
                },
            ),
        ),
        CellContextAlphaFrontierReportSection(
            "states",
            "States",
            "Niche, territory, recurrence, and treatment states remain separate.",
            tuple(
                {
                    "record_id": row.record_id,
                    "operation": row.operation,
                    "state": row.observed_state,
                }
                for row in evaluation.records
            ),
        ),
        CellContextAlphaFrontierReportSection(
            "metrics",
            "Metrics",
            "Support and delta values are descriptive summaries.",
            tuple(item.to_dict() for item in metrics.metrics),
        ),
        CellContextAlphaFrontierReportSection(
            "quality",
            "Quality",
            "The release gate retains every observed check.",
            tuple(item.to_dict() for item in quality.checks),
        ),
    )
    return CellContextAlphaFrontierReport(
        "cell-context-alpha-frontier-report", sections, evaluation.accepted and quality.accepted
    )


__all__ = [
    "CellContextAlphaFrontierReport",
    "CellContextAlphaFrontierReportSection",
    "build_cell_context_alpha_frontier_report",
]

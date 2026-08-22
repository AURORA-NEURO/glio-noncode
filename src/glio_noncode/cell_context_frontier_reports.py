"""Structured release report sections for Domain 08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_metrics import CellContextFrontierMetrics
from .cell_context_frontier_public_data import CellContextFrontierFixture
from .cell_context_frontier_views import CellContextFrontierReviewView
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierReportSection:
    section_id: str
    title: str
    summary: str
    rows: tuple[dict[str, Any], ...]
    severity: str = "info"
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.section_id or not self.title or not self.summary:
            raise ValidationError("cell report section is incomplete")
        if self.severity not in {"info", "warning", "error"}:
            raise ValidationError("cell report severity is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierReport:
    report_id: str
    fixture_id: str
    sections: tuple[CellContextFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.report_id or not self.fixture_id or not self.sections:
            raise ValidationError("cell report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def section(self, section_id: str) -> CellContextFrontierReportSection:
        for item in self.sections:
            if item.section_id == section_id:
                return item
        raise KeyError(section_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cell_context_frontier_report(
    fixture: CellContextFrontierFixture,
    evaluation: CellContextFrontierEvaluation,
    metrics: CellContextFrontierMetrics,
    view: CellContextFrontierReviewView,
) -> CellContextFrontierReport:
    state_rows = tuple(
        {
            "record_id": item.record_id,
            "operation": item.operation,
            "role": item.role,
            "expected_state": item.record.expected_state.value,
            "observed_state": item.observed_state,
            "issue_codes": list(item.observed_issue_codes),
        }
        for item in evaluation.records
    )
    sections = (
        CellContextFrontierReportSection(
            "overview",
            "Context assembly overview",
            "Four Domain 08 context operations execute against public aggregate evidence.",
            (
                {
                    "fixture_id": fixture.fixture_id,
                    "source_count": len(fixture.sources),
                    "record_count": len(fixture.records),
                },
            ),
        ),
        CellContextFrontierReportSection(
            "state_matrix",
            "Context state matrix",
            "Supported, partial, ambiguous, contradictory, abstained, and "
            "foreign-context states remain explicit.",
            state_rows,
        ),
        CellContextFrontierReportSection(
            "metrics",
            "Release metrics",
            "Metric floors are retained for review.",
            tuple(item.to_dict() for item in metrics.metrics),
        ),
        CellContextFrontierReportSection(
            "review",
            "Review projection",
            "Uncertain and refused context rows are routed for review.",
            tuple(item.to_dict() for item in view.rows),
            "warning",
        ),
        CellContextFrontierReportSection(
            "limits",
            "Evidence limits",
            "Taxonomy observations do not establish diagnosis, prognosis, or treatment.",
            ({"limit": "external calibration and transport remain open"},),
            "warning",
        ),
        CellContextFrontierReportSection(
            "dimensions",
            "Dimension preservation",
            "Disease, age, molecular class, molecular state, and territory remain "
            "separate before assembly.",
            (
                {"dimension": "disease_ontology"},
                {"dimension": "age_route"},
                {"dimension": "molecular_class"},
                {"dimension": "molecular_state"},
                {"dimension": "territory"},
            ),
        ),
    )
    return CellContextFrontierReport(
        "glio-noncode-d08-c01-c04-report",
        fixture.fixture_id,
        sections,
        evaluation.accepted and metrics.accepted and view.accepted,
    )


__all__ = [
    "CellContextFrontierReport",
    "CellContextFrontierReportSection",
    "build_cell_context_frontier_report",
]

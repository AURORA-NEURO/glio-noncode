"""Human- and machine-readable reports for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_metrics import ChromatinContextFrontierMetrics
from .chromatin_context_frontier_public_data import ChromatinContextFrontierFixture
from .chromatin_context_frontier_views import ChromatinContextFrontierReviewView
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReportSection:
    section_id: str
    title: str
    summary: str
    rows: tuple[dict[str, Any], ...]
    severity: str = "info"
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.section_id or not self.title or not self.summary:
            raise ValidationError("report section is incomplete")
        if self.severity not in {"info", "warning", "error"}:
            raise ValidationError("report section severity is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReport:
    report_id: str
    fixture_id: str
    sections: tuple[ChromatinContextFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.report_id or not self.fixture_id or not self.sections:
            raise ValidationError("context report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def section(self, section_id: str) -> ChromatinContextFrontierReportSection:
        for item in self.sections:
            if item.section_id == section_id:
                return item
        raise KeyError(section_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_report(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation,
    metrics: ChromatinContextFrontierMetrics,
    view: ChromatinContextFrontierReviewView,
) -> ChromatinContextFrontierReport:
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
    metric_rows = tuple(item.to_dict() for item in metrics.metrics)
    review_rows = tuple(item.to_dict() for item in view.rows)
    sections = (
        ChromatinContextFrontierReportSection(
            "overview",
            "Context track overview",
            "Four Domain 07 context operations are executed against public aggregate evidence.",
            (
                {
                    "fixture_id": fixture.fixture_id,
                    "record_count": len(fixture.records),
                    "source_count": len(fixture.sources),
                },
            ),
        ),
        ChromatinContextFrontierReportSection(
            "state_matrix",
            "Observed state matrix",
            "Supported, partial, ambiguous, abstained, and foreign-context states remain explicit.",
            state_rows,
        ),
        ChromatinContextFrontierReportSection(
            "metrics",
            "Release metrics",
            "Metric floors and observed values are retained for review.",
            metric_rows,
        ),
        ChromatinContextFrontierReportSection(
            "review",
            "Review queue",
            "Uncertain or refused paths are routed to a review surface.",
            review_rows,
            "warning",
        ),
        ChromatinContextFrontierReportSection(
            "limits",
            "Evidence limits",
            "Assay observation does not establish target linkage or clinical effect.",
            ({"limit": "external calibration and transport remain open"},),
            "warning",
        ),
    )
    return ChromatinContextFrontierReport(
        "glio-noncode-d07-c01-c04-report",
        fixture.fixture_id,
        sections,
        evaluation.accepted and metrics.accepted and view.accepted,
    )


__all__ = [
    "ChromatinContextFrontierReport",
    "ChromatinContextFrontierReportSection",
    "build_chromatin_context_frontier_report",
]

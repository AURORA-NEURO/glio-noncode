"""Review-oriented report projections for chromatin-alpha results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_metrics import ChromatinAlphaFrontierMetrics
from .chromatin_alpha_frontier_public_data import ChromatinAlphaFrontierFixture
from .chromatin_alpha_frontier_views import ChromatinAlphaFrontierReviewView
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReportSection:
    section_id: str
    title: str
    rows: tuple[dict[str, Any], ...]
    summary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.section_id or not self.title or not self.summary:
            raise ValidationError("report section is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReport:
    report_id: str
    fixture_id: str
    sections: tuple[ChromatinAlphaFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.report_id or not self.fixture_id or not self.sections:
            raise ValidationError("report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def section(self, section_id: str) -> ChromatinAlphaFrontierReportSection:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        raise KeyError(section_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_report(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
    metrics: ChromatinAlphaFrontierMetrics,
    view: ChromatinAlphaFrontierReviewView,
) -> ChromatinAlphaFrontierReport:
    sections = (
        ChromatinAlphaFrontierReportSection(
            "summary",
            "Chromatin-alpha frontier summary",
            (
                {
                    "fixture_id": fixture.fixture_id,
                    "context_key": fixture.context_key,
                    "boundary": fixture.evidence_boundary,
                    "record_count": len(fixture.records),
                    "positive_count": len(fixture.positive_records),
                    "control_count": len(fixture.control_records),
                },
            ),
            "A closed aggregate fixture covers four chromatin-alpha operations.",
        ),
        ChromatinAlphaFrontierReportSection(
            "metrics",
            "Operation metrics",
            tuple(
                {
                    "metric_id": metric.metric_id,
                    "value": metric.value,
                    "numerator": metric.numerator,
                    "denominator": metric.denominator,
                    "interpretation": metric.interpretation,
                }
                for metric in metrics.metrics
            ),
            "Expected state and issue paths are reconciled across positive and control rows.",
        ),
        ChromatinAlphaFrontierReportSection(
            "review",
            "Review rows",
            tuple(
                {
                    "record_id": row.record_id,
                    "operation": row.operation,
                    "role": row.role,
                    "state": row.state,
                    "decision": row.decision,
                    "issue_codes": list(row.issue_codes),
                    "measurements": row.measurements,
                    "source_ids": list(row.source_ids),
                }
                for row in view.rows
            ),
            "Every row retains operation, state, issue, measurement, source, and decision fields.",
        ),
        ChromatinAlphaFrontierReportSection(
            "reconciliation",
            "Expected path reconciliation",
            tuple(
                {
                    "record_id": item.record_id,
                    "expected_state": item.expected_state,
                    "observed_state": item.observed_state,
                    "state_match": item.state_match,
                    "issue_match": item.issue_match,
                    "accepted": item.accepted,
                }
                for item in evaluation.records
            ),
            "The report retains row-level comparisons for replay and review.",
        ),
    )
    return ChromatinAlphaFrontierReport(
        "chromatin-alpha-frontier-report",
        fixture.fixture_id,
        sections,
        evaluation.accepted and metrics.accepted and view.accepted,
    )


__all__ = [
    "ChromatinAlphaFrontierReport",
    "ChromatinAlphaFrontierReportSection",
    "build_chromatin_alpha_frontier_report",
]

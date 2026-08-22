"""Report projections for programmatic and review-oriented consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_metrics import MethylationFrontierMetrics
from .methylation_frontier_public_data import MethylationFrontierFixture
from .methylation_frontier_views import MethylationFrontierReviewView
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierReportSection:
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
class MethylationFrontierReport:
    report_id: str
    fixture_id: str
    sections: tuple[MethylationFrontierReportSection, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.report_id or not self.fixture_id or not self.sections:
            raise ValidationError("report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def section(self, section_id: str) -> MethylationFrontierReportSection:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        raise KeyError(section_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_methylation_frontier_report(
    fixture: MethylationFrontierFixture,
    evaluation: MethylationFrontierEvaluation,
    metrics: MethylationFrontierMetrics,
    view: MethylationFrontierReviewView,
) -> MethylationFrontierReport:
    sections = (
        MethylationFrontierReportSection(
            "summary",
            "Methylation frontier summary",
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
            "A closed public aggregate fixture covers four methylation operations.",
        ),
        MethylationFrontierReportSection(
            "operations",
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
            "Expected states and issue paths are compared across positive and control rows.",
        ),
        MethylationFrontierReportSection(
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
                    "source_ids": list(row.source_ids),
                }
                for row in view.rows
            ),
            "Every row retains state, issue, source, and decision context.",
        ),
        MethylationFrontierReportSection(
            "reconciliation",
            "Expected path reconciliation",
            tuple(
                {
                    "record_id": item.record_id,
                    "state_match": item.state_match,
                    "issue_match": item.issue_match,
                    "accepted": item.accepted,
                }
                for item in evaluation.records
            ),
            "The serialized report retains row-level comparisons for replay and review.",
        ),
    )
    return MethylationFrontierReport(
        "methylation-frontier-report",
        fixture.fixture_id,
        sections,
        evaluation.accepted and metrics.accepted,
    )


__all__ = [
    "MethylationFrontierReport",
    "MethylationFrontierReportSection",
    "build_methylation_frontier_report",
]

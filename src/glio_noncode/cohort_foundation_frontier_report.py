"""Compact report over the complete C01-C04 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_metrics import CohortFoundationMetrics


@dataclass(frozen=True, slots=True)
class CohortFoundationReportSection:
    section_id: str
    title: str
    values: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationReport:
    report_id: str
    title: str
    sections: tuple[CohortFoundationReportSection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_report(runtime: Any) -> CohortFoundationReport:
    metrics: CohortFoundationMetrics = runtime.metrics
    sections = (
        CohortFoundationReportSection("coverage", "Coverage", {"records": metrics.execution_count, "accepted": metrics.accepted_count, "positive": metrics.positive_count, "controls": metrics.control_count}, content_hash(("coverage", metrics.content_address))),
        CohortFoundationReportSection("operations", "Operations", {item.operation.value: item.to_dict() for item in metrics.operation_metrics}, content_hash(("operations", metrics.content_address))),
        CohortFoundationReportSection("release", "Release", {"state": runtime.release.state.value, "release_id": runtime.release.release_id, "bundle_id": runtime.bundle.bundle_id}, content_hash(("release", runtime.release.content_address))),
        CohortFoundationReportSection("limitations", "Limitations", {"boundary": runtime.fixture.boundary, "review_count": len(runtime.review.items), "diagnostic_count": len(runtime.diagnostics.findings)}, content_hash(("limitations", runtime.review.content_address, runtime.diagnostics.content_address))),
    )
    body = {"report_id": "cohort-foundation-frontier-report", "sections": sections, "accepted": runtime.accepted}
    return CohortFoundationReport(body["report_id"], "Domain 12 C01-C04 cohort foundation evidence", sections, runtime.accepted, content_hash(body))


__all__ = ["CohortFoundationReport", "CohortFoundationReportSection", "build_cohort_foundation_frontier_report"]

"""Structured report rendering for C09-C12 release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy, CohortAlphaFrontierQualityGate, CohortAlphaFrontierReleaseManifest, CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReportSection:
    section_id: str
    title: str
    order: int
    body: str
    visible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReport:
    report_id: str
    title: str
    sections: tuple[CohortAlphaFrontierReportSection, ...]
    claim_ceiling: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def to_markdown(self) -> str:
        parts = [f"# {self.title}", "", f"Release: `{self.report_id}`", "", f"Claim ceiling: {self.claim_ceiling}", ""]
        for section in self.sections:
            if section.visible:
                parts.extend((f"## {section.order}. {section.title}", "", section.body, ""))
        return "\n".join(parts)


def build_cohort_alpha_frontier_report(evaluation: CohortAlphaFrontierEvaluation, metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy, review: CohortAlphaFrontierReviewQueue, quality: CohortAlphaFrontierQualityGate, manifest: CohortAlphaFrontierReleaseManifest) -> CohortAlphaFrontierReport:
    sections = (
        CohortAlphaFrontierReportSection("scope", "Scope", 1, "C09-C12 covers clonality timing, primary recurrence comparison, treatment-selection signal detection, and cross-cohort replication in a bounded adult glioma context.", True, ""),
        CohortAlphaFrontierReportSection("coverage", "Coverage", 2, f"{metrics.total_rows} records evaluated; {metrics.supported_rows} supported observations; {metrics.control_rows} boundary controls; {metrics.acceptance_percent:.2f}% state reconciliation.", True, ""),
        CohortAlphaFrontierReportSection("publication", "Publication policy", 3, f"{policy.publishable_count} paths publish, {policy.review_count} paths remain in review, and {policy.quarantine_count} paths are quarantined.", True, ""),
        CohortAlphaFrontierReportSection("review", "Review queue", 4, f"{review.open_count} queue items remain visible with explicit evidence requirements.", review.open_count > 0, ""),
        CohortAlphaFrontierReportSection("quality", "Quality gates", 5, f"Quality gate accepted: {quality.accepted}. Blocking failures: {quality.blocking_failures}.", True, ""),
        CohortAlphaFrontierReportSection("release", "Release status", 6, f"Manifest ready: {manifest.ready}. Checks: {', '.join(manifest.checks)}.", True, ""),
    )
    hydrated = tuple(CohortAlphaFrontierReportSection(item.section_id, item.title, item.order, item.body, item.visible, content_hash({"section_id": item.section_id, "title": item.title, "order": item.order, "body": item.body, "visible": item.visible}, prefix="alpha-report-section")) for item in sections)
    return CohortAlphaFrontierReport("cohort-alpha-frontier-c09-c12-report", "GLIO non-code cohort alpha frontier", hydrated, manifest.claim_ceiling, quality.accepted and manifest.ready, content_hash(hydrated, prefix="alpha-report"))


__all__ = ["CohortAlphaFrontierReport", "CohortAlphaFrontierReportSection", "build_cohort_alpha_frontier_report"]

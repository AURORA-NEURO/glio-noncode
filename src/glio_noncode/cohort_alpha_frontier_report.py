"""Structured C09-C12 report with independent record and claim denominators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_claim_evidence import CohortAlphaFrontierClaimEvidenceReport
from .cohort_alpha_frontier_dataset_manifest import CohortAlphaFrontierDatasetManifest
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import (
    CohortAlphaFrontierMetrics,
    CohortAlphaFrontierPolicy,
    CohortAlphaFrontierQualityGate,
    CohortAlphaFrontierReleaseManifest,
    CohortAlphaFrontierReviewQueue,
)
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
    coverage_state: str = "unverified"
    structural_record_count: int = 0
    expected_structural_record_count: int = 0
    missing_structural_record_count: int = 0
    extra_structural_record_count: int = 0
    complete_pipeline_claim_count: int = 0
    expected_pipeline_claim_count: int = 0
    missing_pipeline_claim_count: int = 0
    extra_pipeline_claim_count: int = 0
    dataset_manifest_address: str | None = None
    claim_evidence_address: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def to_markdown(self) -> str:
        parts = [
            f"# {self.title}",
            "",
            f"Release: `{self.report_id}`",
            "",
            f"Coverage state: `{self.coverage_state}`",
            "",
            f"Claim ceiling: {self.claim_ceiling}",
            "",
        ]
        for section in self.sections:
            if section.visible:
                parts.extend((f"## {section.order}. {section.title}", "", section.body, ""))
        return "\n".join(parts)


def _coverage_state(
    dataset: CohortAlphaFrontierDatasetManifest | None,
    claims: CohortAlphaFrontierClaimEvidenceReport | None,
) -> str:
    if dataset is None or claims is None:
        return "unverified"
    if claims.dataset_manifest_address != dataset.content_address:
        return "inconsistent"
    states = {dataset.coverage_state, claims.coverage_state}
    if "inconsistent" in states:
        return "inconsistent"
    if "unexpected" in states:
        return "unexpected"
    if "partial" in states:
        return "partial"
    if states != {"complete"} or not dataset.accepted or not claims.accepted:
        return "invalid"
    return "complete"


def build_cohort_alpha_frontier_report(
    evaluation: CohortAlphaFrontierEvaluation,
    metrics: CohortAlphaFrontierMetrics,
    policy: CohortAlphaFrontierPolicy,
    review: CohortAlphaFrontierReviewQueue,
    quality: CohortAlphaFrontierQualityGate,
    manifest: CohortAlphaFrontierReleaseManifest,
    *,
    dataset_manifest: CohortAlphaFrontierDatasetManifest | None = None,
    claim_evidence: CohortAlphaFrontierClaimEvidenceReport | None = None,
) -> CohortAlphaFrontierReport:
    """Build a report that cannot infer completion from observed item counts."""

    del evaluation
    coverage_state = _coverage_state(dataset_manifest, claim_evidence)
    structural_record_count = dataset_manifest.record_count if dataset_manifest else 0
    expected_structural_record_count = (
        dataset_manifest.expected_record_count if dataset_manifest else 0
    )
    missing_structural_record_count = (
        sum(len(record_ids) for _, record_ids in dataset_manifest.missing_record_ids_by_operation)
        if dataset_manifest
        else 0
    )
    extra_structural_record_count = (
        sum(len(record_ids) for _, record_ids in dataset_manifest.extra_record_ids_by_operation)
        if dataset_manifest
        else 0
    )
    complete_pipeline_claim_count = (
        claim_evidence.complete_claim_count if claim_evidence else 0
    )
    expected_pipeline_claim_count = claim_evidence.expected_claim_count if claim_evidence else 0
    missing_pipeline_claim_count = claim_evidence.missing_claim_count if claim_evidence else 0
    extra_pipeline_claim_count = claim_evidence.extra_claim_count if claim_evidence else 0
    sections = (
        CohortAlphaFrontierReportSection(
            "scope",
            "Scope",
            1,
            (
                "C09-C12 covers clonality timing, primary recurrence comparison, "
                "treatment-selection signal detection, and cross-cohort replication "
                "in a bounded adult glioma context."
            ),
            True,
            "",
        ),
        CohortAlphaFrontierReportSection(
            "coverage",
            "Coverage",
            2,
            (
                f"Structural input records: {structural_record_count}/"
                f"{expected_structural_record_count} (missing "
                f"{missing_structural_record_count}, extra {extra_structural_record_count}); "
                f"complete pipeline claims: "
                f"{complete_pipeline_claim_count}/{expected_pipeline_claim_count}; "
                f"missing claims: {missing_pipeline_claim_count}; extra claims: "
                f"{extra_pipeline_claim_count}; coverage state: {coverage_state}."
            ),
            True,
            "",
        ),
        CohortAlphaFrontierReportSection(
            "reconciliation",
            "State reconciliation",
            3,
            (
                f"{metrics.total_rows} records evaluated; {metrics.supported_rows} "
                f"supported observations; {metrics.control_rows} boundary controls; "
                f"{metrics.acceptance_percent:.2f}% state reconciliation."
            ),
            True,
            "",
        ),
        CohortAlphaFrontierReportSection(
            "publication",
            "Publication policy",
            4,
            (
                f"{policy.publishable_count} paths publish, {policy.review_count} "
                f"paths remain in review, and {policy.quarantine_count} paths are quarantined."
            ),
            True,
            "",
        ),
        CohortAlphaFrontierReportSection(
            "review",
            "Review queue",
            5,
            f"{review.open_count} queue items remain visible with explicit evidence requirements.",
            review.open_count > 0,
            "",
        ),
        CohortAlphaFrontierReportSection(
            "quality",
            "Quality gates",
            6,
            (
                f"Quality gate accepted: {quality.accepted}. Blocking failures: "
                f"{quality.blocking_failures}."
            ),
            True,
            "",
        ),
        CohortAlphaFrontierReportSection(
            "release",
            "Release status",
            7,
            f"Manifest ready: {manifest.ready}. Checks: {', '.join(manifest.checks)}.",
            True,
            "",
        ),
    )
    hydrated = tuple(
        CohortAlphaFrontierReportSection(
            item.section_id,
            item.title,
            item.order,
            item.body,
            item.visible,
            content_hash(
                {
                    "section_id": item.section_id,
                    "title": item.title,
                    "order": item.order,
                    "body": item.body,
                    "visible": item.visible,
                },
                prefix="alpha-report-section",
            ),
        )
        for item in sections
    )
    accepted = (
        quality.accepted
        and manifest.ready
        and coverage_state == "complete"
        and dataset_manifest is not None
        and claim_evidence is not None
    )
    body = {
        "report_id": "cohort-alpha-frontier-c09-c12-report",
        "title": "GLIO non-code cohort alpha frontier",
        "sections": hydrated,
        "claim_ceiling": manifest.claim_ceiling,
        "accepted": accepted,
        "coverage_state": coverage_state,
        "structural_record_count": structural_record_count,
        "expected_structural_record_count": expected_structural_record_count,
        "missing_structural_record_count": missing_structural_record_count,
        "extra_structural_record_count": extra_structural_record_count,
        "complete_pipeline_claim_count": complete_pipeline_claim_count,
        "expected_pipeline_claim_count": expected_pipeline_claim_count,
        "missing_pipeline_claim_count": missing_pipeline_claim_count,
        "extra_pipeline_claim_count": extra_pipeline_claim_count,
        "dataset_manifest_address": (
            dataset_manifest.content_address if dataset_manifest is not None else None
        ),
        "claim_evidence_address": (
            claim_evidence.content_address if claim_evidence is not None else None
        ),
    }
    return CohortAlphaFrontierReport(
        report_id=body["report_id"],
        title=body["title"],
        sections=hydrated,
        claim_ceiling=manifest.claim_ceiling,
        accepted=accepted,
        content_address=content_hash(body, prefix="alpha-report"),
        coverage_state=coverage_state,
        structural_record_count=structural_record_count,
        expected_structural_record_count=expected_structural_record_count,
        missing_structural_record_count=missing_structural_record_count,
        extra_structural_record_count=extra_structural_record_count,
        complete_pipeline_claim_count=complete_pipeline_claim_count,
        expected_pipeline_claim_count=expected_pipeline_claim_count,
        missing_pipeline_claim_count=missing_pipeline_claim_count,
        extra_pipeline_claim_count=extra_pipeline_claim_count,
        dataset_manifest_address=body["dataset_manifest_address"],
        claim_evidence_address=body["claim_evidence_address"],
    )


__all__ = [
    "CohortAlphaFrontierReport",
    "CohortAlphaFrontierReportSection",
    "build_cohort_alpha_frontier_report",
]

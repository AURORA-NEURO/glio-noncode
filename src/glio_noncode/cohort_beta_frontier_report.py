"""Human-readable report for the C05-C08 release rehearsal."""

from __future__ import annotations

from typing import Any

from .cohort_beta_frontier_assurance import CohortBetaFrontierAssurance
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics
from .cohort_beta_frontier_release import CohortBetaFrontierReleaseManifest
from .cohort_beta_frontier_review import CohortBetaFrontierReviewQueue


def build_cohort_beta_frontier_report(metrics: CohortBetaFrontierMetrics, release: CohortBetaFrontierReleaseManifest, assurance: CohortBetaFrontierAssurance, review: CohortBetaFrontierReviewQueue) -> dict[str, Any]:
    return {"title": "Domain 12 C05-C08 aggregate evidence report", "release_state": release.state.value, "release_ready": release.ready, "assurance_percent": assurance.assurance_percent, "total_rows": metrics.total_rows, "accepted_rows": metrics.accepted_rows, "review_count": review.open_count, "operations": [{"operation": item.operation, "acceptance_percent": item.acceptance_percent, "supported": item.supported, "partial": item.partial, "absent": item.absent, "out_of_domain": item.out_of_domain, "contradictory": item.contradictory} for item in metrics.operations], "claim_ceiling": release.claim_ceiling}


def render_cohort_beta_frontier_report_markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report['title']}", "", f"Release: **{report['release_state']}**", f"Assurance: **{report['assurance_percent']}%**", "", "| Operation | Accepted | Supported | Partial | Absent | Foreign | Contradictory |", "|---|---:|---:|---:|---:|---:|---:|"]
    lines.extend(f"| {row['operation']} | {row['acceptance_percent']}% | {row['supported']} | {row['partial']} | {row['absent']} | {row['out_of_domain']} | {row['contradictory']} |" for row in report["operations"])
    lines.extend(("", f"Open review items: **{report['review_count']}**", f"Claim ceiling: {report['claim_ceiling']}"))
    return "\n".join(lines) + "\n"


__all__ = ["build_cohort_beta_frontier_report", "render_cohort_beta_frontier_report_markdown"]

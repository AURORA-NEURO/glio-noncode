"""Structural performance and cardinality budgets for release assurance."""

from __future__ import annotations

from .release_assurance_contracts import (
    RELEASE_ASSURANCE_CHECK_COUNT,
    RELEASE_ASSURANCE_DOMAIN_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
    RELEASE_ASSURANCE_EVENT_COUNT,
    RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_METRIC_COUNT,
    RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL,
    ReleaseAssurancePerformanceBudget,
    ReleaseAssurancePerformanceReport,
    ReleaseAssuranceExportPacket,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceSnapshot,
)
from .serialization import content_hash


def _budget(name: str, maximum: int, observed: int, unit: str, detail: str) -> ReleaseAssurancePerformanceBudget:
    body = {
        "name": name,
        "maximum": maximum,
        "observed": observed,
        "unit": unit,
        "passed": observed <= maximum,
        "detail": detail,
    }
    return ReleaseAssurancePerformanceBudget(
        **body,
        content_address=content_hash(body, prefix="release-assurance-performance-budget"),
    )


def audit_release_assurance_performance(
    snapshot: ReleaseAssuranceSnapshot,
    *,
    runtime: ReleaseAssuranceRuntimeReport | None = None,
    packet: ReleaseAssuranceExportPacket | None = None,
) -> ReleaseAssurancePerformanceReport:
    """Measure bounded structural counts without timing-dependent claims."""

    graph_nodes = 0
    event_count = 0
    metric_count = 0
    stage_count = 0
    artifact_count = 0
    if runtime is not None:
        graph_nodes = len(runtime.graph.nodes)
        event_count = len(runtime.observability.events)
        metric_count = len(runtime.observability.metrics)
        stage_count = len(runtime.stages)
    if packet is not None:
        artifact_count = len(packet.artifacts)
    budgets = (
        _budget("domains", RELEASE_ASSURANCE_DOMAIN_COUNT, len(snapshot.domains), "rows", "four domain rows are expected"),
        _budget("evidence", RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT, len(snapshot.evidence), "links", "twenty evidence links are expected"),
        _budget("checks", RELEASE_ASSURANCE_CHECK_COUNT, len(snapshot.checks), "checks", "twenty-eight checks are expected"),
        _budget("runtime-stages", RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL, stage_count, "stages", "runtime stage count is bounded"),
        _budget("events", RELEASE_ASSURANCE_EVENT_COUNT, event_count, "events", "observability event count is bounded"),
        _budget("metrics", RELEASE_ASSURANCE_METRIC_COUNT, metric_count, "metrics", "observability metric count is bounded"),
        _budget("graph-nodes", 53, graph_nodes, "nodes", "lineage graph node count is bounded"),
        _budget("export-artifacts", RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT, artifact_count, "artifacts", "export artifact count is bounded"),
    )
    accepted = snapshot.accepted and all(item.passed for item in budgets)
    body = {"bundle_id": snapshot.bundle_id, "budgets": budgets, "accepted": accepted}
    return ReleaseAssurancePerformanceReport(
        snapshot.bundle_id,
        budgets,
        accepted,
        content_hash(body, prefix="release-assurance-performance"),
    )


def release_assurance_budget_status(report: ReleaseAssurancePerformanceReport) -> dict[str, object]:
    """Return a small status projection for dashboards and CI logs."""

    return {
        "bundle_id": report.bundle_id,
        "accepted": report.accepted,
        "budget_count": len(report.budgets),
        "failed_budget_names": tuple(item.name for item in report.budgets if not item.passed),
        "content_address": report.content_address,
    }


__all__ = ["audit_release_assurance_performance", "release_assurance_budget_status"]

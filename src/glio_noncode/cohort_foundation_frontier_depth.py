"""Depth audit with explicit quantitative thresholds for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_artifacts import CohortFoundationArtifactInventory
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_lineage import CohortFoundationLineageGraph
from .cohort_foundation_frontier_metrics import CohortFoundationMetrics
from .cohort_foundation_frontier_public_data import CohortFoundationFixture, audit_cohort_foundation_frontier_data
from .cohort_foundation_frontier_quality_gate import CohortFoundationQualityGate
from .cohort_foundation_frontier_release import CohortFoundationReleaseManifest


@dataclass(frozen=True, slots=True)
class CohortFoundationDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    minimum: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationDepthAudit:
    audit_id: str
    accepted: bool
    checks: tuple[CohortFoundationDepthCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_cohort_foundation_frontier_depth(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation, metrics: CohortFoundationMetrics, lineage: CohortFoundationLineageGraph, quality: CohortFoundationQualityGate, release: CohortFoundationReleaseManifest, inventory: CohortFoundationArtifactInventory) -> CohortFoundationDepthAudit:
    audit = audit_cohort_foundation_frontier_data(fixture)
    values = (
        ("source-count", len(fixture.sources), 5, "public source receipts"),
        ("record-count", len(fixture.records), 16, "positive and control records"),
        ("operation-count", len(metrics.operation_metrics), 4, "operation metrics"),
        ("execution-count", len(evaluation.executions), 16, "executed records"),
        ("lineage-node-count", len(lineage.nodes), 33, "fixture, sources, records, executions"),
        ("lineage-edge-count", len(lineage.edges), 32, "source and execution edges"),
        ("artifact-count", len(inventory.artifacts), 11, "release artifact inventory"),
        ("quality-check-count", len(quality.checks), 10, "blocking quality checks"),
        ("accepted-evaluation", evaluation.accepted, True, "fixture evaluation"),
        ("accepted-quality", quality.accepted, True, "quality gate"),
        ("ready-release", release.ready, True, "release manifest"),
        ("data-audit", audit.accepted, True, "public data audit"),
    )
    checks = tuple(CohortFoundationDepthCheck(check_id, observed >= minimum if isinstance(observed, (int, float)) and isinstance(minimum, (int, float)) else observed == minimum, observed, minimum, detail, content_hash((check_id, observed, minimum, detail))) for check_id, observed, minimum, detail in values)
    body = {"audit_id": "cohort-foundation-frontier-depth", "checks": checks}
    return CohortFoundationDepthAudit(body["audit_id"], all(item.passed for item in checks), checks, content_hash(body))


__all__ = ["CohortFoundationDepthAudit", "CohortFoundationDepthCheck", "audit_cohort_foundation_frontier_depth"]

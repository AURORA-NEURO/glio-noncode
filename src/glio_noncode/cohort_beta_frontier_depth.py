"""Quantitative depth audit preventing a shallow four-function release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_lineage import CohortBetaFrontierLineage
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_quality_gate import CohortBetaFrontierQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDepthCheck:
    check_id: str
    observed: int
    minimum: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDepthAudit:
    checks: tuple[CohortBetaFrontierDepthCheck, ...]
    accepted: bool
    score_percent: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_cohort_beta_frontier_depth(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, metrics: CohortBetaFrontierMetrics, lineage: CohortBetaFrontierLineage, quality: CohortBetaFrontierQualityGate) -> CohortBetaFrontierDepthAudit:
    checks_raw = (("operation-count", len(metrics.operations), 4), ("fixture-paths", len(fixture.records), 16), ("control-paths", metrics.control_rows, 12), ("lineage-edges", len(lineage.edges), 32), ("quality-checks", len(quality.checks), 6), ("reconciled-rows", sum(item.accepted for item in evaluation.rows), 16))
    checks = tuple(CohortBetaFrontierDepthCheck(check_id, observed, minimum, observed >= minimum, content_hash({"check_id": check_id, "observed": observed, "minimum": minimum}, prefix="depth-check")) for check_id, observed, minimum in checks_raw)
    return CohortBetaFrontierDepthAudit(checks, all(item.accepted for item in checks), round(100 * sum(item.accepted for item in checks) / len(checks), 2), content_hash(checks, prefix="depth"))


__all__ = ["CohortBetaFrontierDepthAudit", "CohortBetaFrontierDepthCheck", "audit_cohort_beta_frontier_depth"]

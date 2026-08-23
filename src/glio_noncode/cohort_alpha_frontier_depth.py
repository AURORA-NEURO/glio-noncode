"""Depth audit for the C09-C12 release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierLineage, CohortAlphaFrontierMetrics, CohortAlphaFrontierQualityGate
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDepthCheck:
    check_id: str
    observed: int
    minimum: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDepthAudit:
    checks: tuple[CohortAlphaFrontierDepthCheck, ...]
    score_percent: float
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_cohort_alpha_frontier_depth(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation, metrics: CohortAlphaFrontierMetrics, lineage: CohortAlphaFrontierLineage, quality: CohortAlphaFrontierQualityGate) -> CohortAlphaFrontierDepthAudit:
    raw = (("fixture-paths", len(fixture.records), 16), ("accepted-rows", sum(item.accepted for item in evaluation.rows), 16), ("supported-rows", metrics.supported_rows, 4), ("control-rows", metrics.control_rows, 12), ("lineage-edges", len(lineage.edges), 32), ("quality-checks", len(quality.checks), 6))
    checks = tuple(CohortAlphaFrontierDepthCheck(check_id, observed, minimum, observed >= minimum, content_hash({"check_id": check_id, "observed": observed, "minimum": minimum}, prefix="alpha-depth-check")) for check_id, observed, minimum in raw)
    return CohortAlphaFrontierDepthAudit(checks, round(100 * sum(item.accepted for item in checks) / len(checks), 2), all(item.accepted for item in checks), content_hash(checks, prefix="alpha-depth"))


__all__ = ["CohortAlphaFrontierDepthAudit", "CohortAlphaFrontierDepthCheck", "audit_cohort_alpha_frontier_depth"]

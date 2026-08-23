"""Blocking release quality checks for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_contracts import CohortBetaFrontierContractRegistry
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_lineage import CohortBetaFrontierLineage
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_reconciliation import CohortBetaFrontierReconciliation
from .cohort_beta_frontier_schema import CohortBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierGateCheck:
    check_id: str
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierQualityGate:
    checks: tuple[CohortBetaFrontierGateCheck, ...]
    accepted: bool
    blocking_failures: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_beta_frontier_quality(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, contracts: CohortBetaFrontierContractRegistry, schema: CohortBetaFrontierSchemaReport, lineage: CohortBetaFrontierLineage, reconciliation: CohortBetaFrontierReconciliation) -> CohortBetaFrontierQualityGate:
    checks = [("fixture-closed", len(fixture.records) == 16, "sixteen bounded paths"), ("evaluation-accepted", evaluation.accepted, "all expected states observed"), ("contracts-complete", {item.operation for item in contracts.contracts} == {"C05", "C06", "C07", "C08"}, "four operation contracts"), ("schema-accepted", schema.accepted, "field schema accepted"), ("lineage-closed", lineage.closed, "source and result lineage closed"), ("reconciled", reconciliation.reconciled, "expected state reconciliation")]
    values = tuple(CohortBetaFrontierGateCheck(check_id, accepted, detail, content_hash({"check_id": check_id, "accepted": accepted, "detail": detail}, prefix="gate-check")) for check_id, accepted, detail in checks)
    body = {"checks": values}
    return CohortBetaFrontierQualityGate(values, all(item.accepted for item in values), sum(not item.accepted for item in values), content_hash(body, prefix="quality"))


__all__ = ["CohortBetaFrontierGateCheck", "CohortBetaFrontierQualityGate", "evaluate_cohort_beta_frontier_quality"]

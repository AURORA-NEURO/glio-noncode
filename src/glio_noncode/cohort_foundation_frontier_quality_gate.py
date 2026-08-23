"""Blocking quality gate for the C01-C04 frontier release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_contracts import CohortFoundationContractRegistry
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_lineage import CohortFoundationLineageGraph
from .cohort_foundation_frontier_public_data import CohortFoundationFixture, audit_cohort_foundation_frontier_data
from .cohort_foundation_frontier_public_data import CohortFoundationOperation
from .cohort_foundation_frontier_reconciliation import CohortFoundationReconciliation
from .cohort_foundation_frontier_schema import CohortFoundationSchemaReport, validate_cohort_foundation_frontier_schema


@dataclass(frozen=True, slots=True)
class CohortFoundationQualityCheck:
    check_id: str
    passed: bool
    blocking: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationQualityGate:
    gate_id: str
    accepted: bool
    checks: tuple[CohortFoundationQualityCheck, ...]
    blocking_failures: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_foundation_frontier_quality(
    fixture: CohortFoundationFixture,
    evaluation: CohortFoundationEvaluation,
    contracts: CohortFoundationContractRegistry,
    schema: CohortFoundationSchemaReport,
    lineage: CohortFoundationLineageGraph,
    reconciliation: CohortFoundationReconciliation,
) -> CohortFoundationQualityGate:
    audit = audit_cohort_foundation_frontier_data(fixture)
    values = (
        ("data-audit", audit.accepted, True, audit.accepted, True, "source and record closure"),
        ("schema", validate_cohort_foundation_frontier_schema(schema), True, len(schema.checks), 4, "four operation schemas"),
        ("contracts", len(contracts.contracts) == 4, True, len(contracts.contracts), 4, "four operation contracts"),
        ("evaluation", evaluation.accepted, True, evaluation.accepted, True, "positive and control execution"),
        ("reconciliation", reconciliation.reconciled, True, reconciliation.mismatches, (), "expected states and policy reconcile"),
        ("lineage-root", fixture.fixture_id in lineage.roots, True, lineage.roots, (fixture.fixture_id,), "fixture is a lineage root"),
        ("lineage-coverage", len(lineage.edges) >= len(fixture.records) * 2, True, len(lineage.edges), len(fixture.records) * 2, "source and execution edges exist"),
        ("context-closure", all(item.context_key == fixture.context_key for item in lineage.nodes if item.kind.value == "execution"), True, True, True, "executions use target context"),
        ("control-balance", all(sum(item.role.value == "control" for item in fixture.records_for(operation)) >= 3 for operation in CohortFoundationOperation), True, True, True, "each operation has controls"),
        ("positive-balance", all(any(item.role.value == "positive" for item in fixture.records_for(operation)) for operation in CohortFoundationOperation), True, True, True, "each operation has a positive"),
    )
    checks = tuple(CohortFoundationQualityCheck(check_id, passed, blocking, observed, expected, detail, content_hash((check_id, passed, observed, expected, detail))) for check_id, passed, blocking, observed, expected, detail in values)
    failures = tuple(item.check_id for item in checks if item.blocking and not item.passed)
    body = {"gate_id": "cohort-foundation-frontier-quality-v1", "checks": checks, "failures": failures}
    return CohortFoundationQualityGate(body["gate_id"], not failures, checks, failures, content_hash(body))


__all__ = ["CohortFoundationQualityCheck", "CohortFoundationQualityGate", "evaluate_cohort_foundation_frontier_quality"]

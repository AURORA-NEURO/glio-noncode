"""Blocking quality checks for Domain 12 release candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_contracts import CohortFrontierContractRegistry
from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_lineage import CohortFrontierLineageGraph
from .cohort_frontier_public_data import CohortFrontierFixture, audit_cohort_frontier_data
from .cohort_frontier_reconciliation import CohortFrontierReconciliation
from .cohort_frontier_schema import CohortFrontierSchemaManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFrontierGateCheck:
    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierQualityGate:
    gate_id: str
    checks: tuple[CohortFrontierGateCheck, ...]
    accepted: bool
    blocking_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def evaluate_cohort_frontier_quality(fixture: CohortFrontierFixture, evaluation: CohortFrontierEvaluation, contracts: CohortFrontierContractRegistry, schema: CohortFrontierSchemaManifest, lineage: CohortFrontierLineageGraph, reconciliation: CohortFrontierReconciliation) -> CohortFrontierQualityGate:
    audit = audit_cohort_frontier_data(fixture)
    checks: list[CohortFrontierGateCheck] = []
    def add(check_id: str, passed: bool, observed: Any, required: Any, rationale: str) -> None:
        body = {"check_id": check_id, "passed": passed, "severity": "blocking", "observed": observed, "required": required, "rationale": rationale}
        checks.append(CohortFrontierGateCheck(**body, content_address=content_hash(body)))
    add("data-audit", audit.accepted, audit.failed_check_ids, (), "public fixture and source audit passes")
    add("evaluation", evaluation.accepted, evaluation.passed_checks, len(evaluation.checks), "positive and control replay passes")
    add("contract-coverage", len(contracts.contracts) == 4, len(contracts.contracts), 4, "four operation contracts")
    add("schema-coverage", len(schema.operations) == 4, len(schema.operations), 4, "four operation schemas")
    add("lineage-acyclic", lineage.acyclic, lineage.acyclic, True, "lineage has no cycles")
    add("lineage-terminals", len(lineage.terminal_addresses) == len(fixture.records), len(lineage.terminal_addresses), len(fixture.records), "every record has a terminal")
    add("reconciliation", reconciliation.reconciled, reconciliation.mismatched_record_ids, (), "expected and observed receipts reconcile")
    add("addresses", all(bool(item.content_address) for item in evaluation.executions), True, True, "execution addresses exist")
    add("boundary", fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "boundary is explicit")
    add("positive-count", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per operation")
    add("control-count", len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation")
    add("issue-vocabulary", all(set(item.issue_codes) <= set(contracts.issue_codes()) for item in evaluation.executions), True, True, "issue codes are declared")
    blocking = tuple(item.check_id for item in checks if not item.passed)
    body = {"gate_id": "cohort-frontier-quality-gate", "checks": tuple(checks), "accepted": not blocking, "blocking_check_ids": blocking}
    return CohortFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierGateCheck", "CohortFrontierQualityGate", "evaluate_cohort_frontier_quality"]

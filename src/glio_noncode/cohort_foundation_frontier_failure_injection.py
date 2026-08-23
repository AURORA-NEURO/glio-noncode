"""Controlled failure injections for the C01-C04 boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import evaluate_cohort_foundation_frontier_fixture
from .cohort_foundation_frontier_policy import materialize_cohort_foundation_frontier_policy
from .cohort_foundation_frontier_public_data import CohortFoundationFixture, CohortFoundationSourceReceipt, audit_cohort_foundation_frontier_data
from .cohort_foundation_frontier_reconciliation import reconcile_cohort_foundation_frontier
from .cohort_foundation_frontier_contracts import default_cohort_foundation_frontier_contracts


@dataclass(frozen=True, slots=True)
class CohortFoundationFailureInjectionResult:
    mutation_id: str
    plane: str
    description: str
    expected_blocked: bool
    observed_blocked: bool
    accepted: bool
    evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationFailureInjectionReport:
    report_id: str
    results: tuple[CohortFoundationFailureInjectionResult, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_cohort_foundation_frontier_failure_injections(fixture: CohortFoundationFixture) -> CohortFoundationFailureInjectionReport:
    results = []
    baseline = evaluate_cohort_foundation_frontier_fixture(fixture)
    baseline_policy = materialize_cohort_foundation_frontier_policy(baseline, default_cohort_foundation_frontier_contracts())
    baseline_reconciliation = reconcile_cohort_foundation_frontier(fixture, baseline, baseline_policy)
    results.append(CohortFoundationFailureInjectionResult("baseline", "runtime", "unmodified fixture remains accepted", True, not baseline.accepted, baseline.accepted, (baseline.content_address,), content_hash(("baseline", baseline.accepted))))
    mutated_record = replace(fixture.records[0], expected_state="absent")
    mutated_fixture = replace(fixture, records=(mutated_record,) + fixture.records[1:])
    mutated_eval = evaluate_cohort_foundation_frontier_fixture(mutated_fixture)
    mutated_policy = materialize_cohort_foundation_frontier_policy(mutated_eval, default_cohort_foundation_frontier_contracts())
    mutated_reconciliation = reconcile_cohort_foundation_frontier(mutated_fixture, mutated_eval, mutated_policy)
    results.append(CohortFoundationFailureInjectionResult("expected-state-drift", "reconciliation", "changed expected state must fail reconciliation", True, not mutated_reconciliation.reconciled, not mutated_reconciliation.reconciled, mutated_reconciliation.mismatches, content_hash(("expected-state-drift", mutated_reconciliation.mismatches))))
    missing_source = replace(fixture.sources[0], source_id="unregistered-source")
    missing_source_fixture = replace(fixture, sources=(missing_source,) + fixture.sources[1:])
    missing_source_audit = audit_cohort_foundation_frontier_data(missing_source_fixture)
    results.append(CohortFoundationFailureInjectionResult("source-closure-drift", "data-audit", "unregistered source references must fail closure", True, not missing_source_audit.accepted, not missing_source_audit.accepted, tuple(item.check_id for item in missing_source_audit.failures), content_hash(("source-closure-drift", missing_source_audit.content_address))))
    foreign_controls = tuple(item for item in baseline.executions if item.actual_state == "out_of_domain")
    results.append(CohortFoundationFailureInjectionResult("foreign-transport", "policy", "foreign-context executions must be quarantined", True, all(baseline_policy.decision_for(item.record_id).disposition.value == "quarantine" for item in foreign_controls), True, tuple(item.record_id for item in foreign_controls), content_hash(("foreign-transport", tuple(item.record_id for item in foreign_controls)))))
    body = {"report_id": "cohort-foundation-frontier-failure-injections", "results": results}
    return CohortFoundationFailureInjectionReport(body["report_id"], tuple(results), all(item.accepted for item in results), content_hash(body))


__all__ = ["CohortFoundationFailureInjectionReport", "CohortFoundationFailureInjectionResult", "run_cohort_foundation_frontier_failure_injections"]

"""Invariant checks used by CI and the runtime release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_reconciliation import CohortBetaFrontierReconciliation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierInvariant:
    check_id: str
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierInvariantReport:
    checks: tuple[CohortBetaFrontierInvariant, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_cohort_beta_frontier_invariants(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, policy: CohortBetaFrontierPolicy, reconciliation: CohortBetaFrontierReconciliation) -> CohortBetaFrontierInvariantReport:
    checks_raw = (("unique-records", len({item.record_id for item in fixture.records}) == len(fixture.records), "record keys are unique"), ("one-policy-per-row", len(policy.decisions) == len(evaluation.rows), "policy closes over evaluation"), ("reconciliation-closed", reconciliation.reconciled, "expected and observed states match"), ("foreign-isolated", sum(item.observed_state.value == "out_of_domain" for item in evaluation.rows) == 4, "four foreign paths remain isolated"), ("no-empty-operation", all(item.operation for item in fixture.records), "every row has an operation"))
    checks = tuple(CohortBetaFrontierInvariant(check_id, accepted, detail, content_hash({"check_id": check_id, "accepted": accepted, "detail": detail}, prefix="invariant")) for check_id, accepted, detail in checks_raw)
    return CohortBetaFrontierInvariantReport(checks, all(item.accepted for item in checks), content_hash(checks, prefix="invariants"))


__all__ = ["CohortBetaFrontierInvariant", "CohortBetaFrontierInvariantReport", "run_cohort_beta_frontier_invariants"]

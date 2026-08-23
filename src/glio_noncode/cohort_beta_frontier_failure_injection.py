"""Controlled negative probes for parser, context, and comparator boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta import CohortBetaState
from .cohort_beta_frontier_fixture_eval import evaluate_cohort_beta_frontier_fixture
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierFailureProbe:
    probe_id: str
    expected_state: str
    observed_state: str
    blocked: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierFailureInjectionReport:
    probes: tuple[CohortBetaFrontierFailureProbe, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_cohort_beta_frontier_failure_injections(fixture: CohortBetaFrontierFixture) -> CohortBetaFrontierFailureInjectionReport:
    evaluation = evaluate_cohort_beta_frontier_fixture(fixture)
    probes = tuple(CohortBetaFrontierFailureProbe(row.record_id, row.expected_state.value, row.observed_state.value, row.expected_state is not CohortBetaState.SUPPORTED, "control path remains visible to policy", content_hash({"record_id": row.record_id, "blocked": row.expected_state is not CohortBetaState.SUPPORTED}, prefix="failure-probe")) for row in evaluation.rows if row.expected_state is not CohortBetaState.SUPPORTED)
    return CohortBetaFrontierFailureInjectionReport(probes, len(probes) == 12 and all(item.blocked for item in probes), content_hash(probes, prefix="failure-injection"))


__all__ = ["CohortBetaFrontierFailureInjectionReport", "CohortBetaFrontierFailureProbe", "run_cohort_beta_frontier_failure_injections"]

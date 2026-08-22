"""Cohort convergence release bundle assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_lineage import CohortFrontierLineageGraph
from .cohort_frontier_metrics import CohortFrontierMetricsReport
from .cohort_frontier_policy import CohortFrontierPolicy, CohortFrontierPolicyDecision
from .cohort_frontier_public_data import CohortFrontierFixture
from .cohort_frontier_reconciliation import CohortFrontierReconciliation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierReleaseBundle:
    bundle_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    lineage_address: str
    reconciliation_address: str
    policy_id: str
    policy_address: str
    policy_decisions: tuple[CohortFrontierPolicyDecision, ...]
    release_notes: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        if not self.release_notes:
            raise ValueError("cohort release bundle requires notes")

    @property
    def publishable(self) -> bool:
        return all(item.publishable for item in self.policy_decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


def assemble_cohort_frontier_bundle(fixture: CohortFrontierFixture, evaluation: CohortFrontierEvaluation, metrics: CohortFrontierMetricsReport, lineage: CohortFrontierLineageGraph, reconciliation: CohortFrontierReconciliation, policy: CohortFrontierPolicy, *, bundle_id: str = "cohort-frontier-release") -> CohortFrontierReleaseBundle:
    body = {"bundle_id": bundle_id, "fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "metrics_address": metrics.content_address, "lineage_address": lineage.content_address, "reconciliation_address": reconciliation.content_address, "policy_id": policy.policy_id, "policy_address": policy.content_address, "policy_decisions": policy.decide(evaluation), "release_notes": ("Aggregate public fixture only.", "No patient-level inputs are included.", "Cohort limitations, parity gaps, shift, and privacy floors remain visible.", "A published discovery result is a manifest, not a clinical cohort claim.")}
    return CohortFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierReleaseBundle", "assemble_cohort_frontier_bundle"]

"""Release bundle assembly for the Domain 13 planning frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_lineage import ValidationFrontierLineageGraph
from .validation_frontier_metrics import ValidationFrontierMetricsReport
from .validation_frontier_policy import ValidationFrontierPolicy, ValidationFrontierPolicyDecision
from .validation_frontier_public_data import ValidationFrontierFixture
from .validation_frontier_reconciliation import ValidationFrontierReconciliation


@dataclass(frozen=True, slots=True)
class ValidationFrontierReleaseBundle:
    bundle_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    lineage_address: str
    reconciliation_address: str
    policy_id: str
    policy_address: str
    policy_decisions: tuple[ValidationFrontierPolicyDecision, ...]
    release_notes: tuple[str, ...]
    content_address: str

    @property
    def publishable(self) -> bool:
        return all(item.publishable for item in self.policy_decisions)

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        if not self.release_notes:
            raise ValueError("validation release bundle requires notes")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


def assemble_validation_frontier_bundle(fixture: ValidationFrontierFixture, evaluation: ValidationFrontierEvaluation, metrics: ValidationFrontierMetricsReport, lineage: ValidationFrontierLineageGraph, reconciliation: ValidationFrontierReconciliation, policy: ValidationFrontierPolicy, *, bundle_id: str = "validation-frontier-release") -> ValidationFrontierReleaseBundle:
    body = {"bundle_id": bundle_id, "fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "metrics_address": metrics.content_address, "lineage_address": lineage.content_address, "reconciliation_address": reconciliation.content_address, "policy_id": policy.policy_id, "policy_address": policy.content_address, "policy_decisions": policy.decide(evaluation), "release_notes": ("Aggregate public planning fixture only.", "No patient-level inputs are included.", "Planning outputs retain blockers, alternatives, controls, and limitations.", "A ready plan is a review artifact, not experimental success.")}
    return ValidationFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierReleaseBundle", "assemble_validation_frontier_bundle"]

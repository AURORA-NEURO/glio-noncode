"""Release bundle assembly for causal frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_lineage import CausalFrontierLineageGraph
from .causal_frontier_metrics import CausalFrontierMetricsReport
from .causal_frontier_policy import CausalFrontierPolicy, CausalFrontierPolicyDecision
from .causal_frontier_public_data import CausalFrontierFixture
from .causal_frontier_reconciliation import CausalFrontierReconciliation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierReleaseBundle:
    bundle_id: str
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    lineage_address: str
    reconciliation_address: str
    policy_id: str
    policy_address: str
    policy_decisions: tuple[CausalFrontierPolicyDecision, ...]
    release_notes: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        if not self.release_notes:
            raise ValueError("release bundle requires notes")

    @property
    def publishable(self) -> bool:
        return all(item.decision.value in {"allow_review", "allow_publication"} for item in self.policy_decisions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"publishable": self.publishable}


def assemble_causal_frontier_bundle(
    fixture: CausalFrontierFixture,
    evaluation: CausalFrontierEvaluation,
    metrics: CausalFrontierMetricsReport,
    lineage: CausalFrontierLineageGraph,
    reconciliation: CausalFrontierReconciliation,
    policy: CausalFrontierPolicy,
    *,
    bundle_id: str = "causal-frontier-release",
) -> CausalFrontierReleaseBundle:
    decisions = policy.decide(evaluation)
    notes = (
        "Aggregate public fixture only.",
        "No patient-level inputs are included in this release surface.",
        "Issue-bearing outputs remain reviewable and abstention is retained.",
        "A published dossier is a content-addressed manifest, not a causal conclusion.",
    )
    body = {
        "bundle_id": bundle_id,
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "metrics_address": metrics.content_address,
        "lineage_address": lineage.content_address,
        "reconciliation_address": reconciliation.content_address,
        "policy_id": policy.policy_id,
        "policy_address": policy.content_address,
        "policy_decisions": decisions,
        "release_notes": notes,
    }
    return CausalFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierReleaseBundle", "assemble_causal_frontier_bundle"]

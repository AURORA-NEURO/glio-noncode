"""Immutable Domain 06 C13-C16 evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import SequenceFrontierEvaluationReport
from .sequence_frontier_lineage import SequenceFrontierLineageReport
from .sequence_frontier_metrics import SequenceFrontierMetrics
from .sequence_frontier_policy import SequenceFrontierPolicyReport
from .sequence_frontier_public_data import SequenceFrontierDataAudit, SequenceFrontierFixture
from .sequence_frontier_reconciliation import SequenceFrontierReconciliationReport
from .sequence_frontier_replay import SequenceFrontierReplayReport
from .sequence_frontier_scenario_matrix import SequenceFrontierScenarioReport
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierBundle:
    bundle_id: str
    bundle_version: str
    fixture: SequenceFrontierFixture
    data_audit: SequenceFrontierDataAudit
    evaluation: SequenceFrontierEvaluationReport
    replay: SequenceFrontierReplayReport
    scenarios: SequenceFrontierScenarioReport
    policy: SequenceFrontierPolicyReport
    lineage: SequenceFrontierLineageReport
    reconciliation: SequenceFrontierReconciliationReport
    metrics: SequenceFrontierMetrics
    content_address: str

    def __post_init__(self) -> None:
        for name in ("bundle_id", "bundle_version", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    @property
    def accepted(self) -> bool:
        return all(
            (
                self.data_audit.accepted,
                self.evaluation.accepted,
                self.replay.accepted,
                self.scenarios.accepted,
                self.policy.accepted,
                self.lineage.accepted,
                self.reconciliation.accepted,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_sequence_frontier_bundle(
    fixture: SequenceFrontierFixture,
    data_audit: SequenceFrontierDataAudit,
    evaluation: SequenceFrontierEvaluationReport,
    replay: SequenceFrontierReplayReport,
    scenarios: SequenceFrontierScenarioReport,
    policy: SequenceFrontierPolicyReport,
    lineage: SequenceFrontierLineageReport,
    reconciliation: SequenceFrontierReconciliationReport,
    metrics: SequenceFrontierMetrics,
) -> SequenceFrontierBundle:
    body = {
        "bundle_id": "sequence-frontier-bundle",
        "bundle_version": "2026.08.d06-c13-c16.v1",
        "fixture": fixture,
        "data_audit": data_audit,
        "evaluation": evaluation,
        "replay": replay,
        "scenarios": scenarios,
        "policy": policy,
        "lineage": lineage,
        "reconciliation": reconciliation,
        "metrics": metrics,
    }
    return SequenceFrontierBundle(**body, content_address=content_hash(body))


__all__ = ["SequenceFrontierBundle", "build_sequence_frontier_bundle"]

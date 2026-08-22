"""Composed evidence bundle for Domain 09 topology frontier runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_fixture_eval import TopologyFrontierEvaluationReport
from .topology_frontier_lineage import TopologyFrontierLineageReport
from .topology_frontier_metrics import TopologyFrontierMetrics
from .topology_frontier_policy import TopologyFrontierPolicyReport
from .topology_frontier_public_data import TopologyFrontierDataAudit, TopologyFrontierFixture
from .topology_frontier_reconciliation import TopologyFrontierReconciliationReport
from .topology_frontier_replay import TopologyFrontierReplayReport
from .topology_frontier_scenario_matrix import TopologyFrontierScenarioReport


@dataclass(frozen=True, slots=True)
class TopologyFrontierEvidenceBundle:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    data_audit: TopologyFrontierDataAudit
    evaluation: TopologyFrontierEvaluationReport
    replay: TopologyFrontierReplayReport
    scenarios: TopologyFrontierScenarioReport
    policy: TopologyFrontierPolicyReport
    lineage: TopologyFrontierLineageReport
    reconciliation: TopologyFrontierReconciliationReport
    metrics: TopologyFrontierMetrics
    bundle_address: str

    @property
    def accepted(self) -> bool:
        return all((self.data_audit.accepted, self.evaluation.accepted, self.replay.accepted, self.scenarios.accepted, self.policy.accepted, self.lineage.accepted, self.reconciliation.accepted))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_topology_frontier_bundle(
    fixture: TopologyFrontierFixture,
    *,
    data_audit: TopologyFrontierDataAudit,
    evaluation: TopologyFrontierEvaluationReport,
    replay: TopologyFrontierReplayReport,
    scenarios: TopologyFrontierScenarioReport,
    policy: TopologyFrontierPolicyReport,
    lineage: TopologyFrontierLineageReport,
    reconciliation: TopologyFrontierReconciliationReport,
    metrics: TopologyFrontierMetrics,
) -> TopologyFrontierEvidenceBundle:
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "record_ids": tuple(item.record_id for item in fixture.records),
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "data_audit": data_audit,
        "evaluation": evaluation,
        "replay": replay,
        "scenarios": scenarios,
        "policy": policy,
        "lineage": lineage,
        "reconciliation": reconciliation,
        "metrics": metrics,
    }
    return TopologyFrontierEvidenceBundle(**body, bundle_address=content_hash(body))


__all__ = [
    "TopologyFrontierEvidenceBundle",
    "build_topology_frontier_bundle",
]

"""Content-addressed evidence bundle for Domain 08 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_fixture_eval import CellStateFrontierEvaluationReport
from .cell_state_frontier_lineage import CellStateFrontierLineageReport
from .cell_state_frontier_metrics import CellStateFrontierMetrics
from .cell_state_frontier_policy import CellStateFrontierPolicyReport
from .cell_state_frontier_public_data import CellStateFrontierDataAudit, CellStateFrontierFixture
from .cell_state_frontier_reconciliation import CellStateFrontierReconciliationReport
from .cell_state_frontier_replay import CellStateFrontierReplayReport
from .cell_state_frontier_scenario_matrix import CellStateFrontierScenarioReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellStateFrontierBundle:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    data_audit: CellStateFrontierDataAudit
    evaluation: CellStateFrontierEvaluationReport
    replay: CellStateFrontierReplayReport
    scenarios: CellStateFrontierScenarioReport
    policy: CellStateFrontierPolicyReport
    lineage: CellStateFrontierLineageReport
    reconciliation: CellStateFrontierReconciliationReport
    metrics: CellStateFrontierMetrics
    record_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    records_address: str
    bundle_address: str

    @property
    def accepted(self) -> bool:
        return all((self.data_audit.accepted, self.evaluation.accepted, self.replay.accepted, self.scenarios.accepted, self.policy.accepted, self.reconciliation.accepted))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_cell_state_frontier_bundle(
    fixture: CellStateFrontierFixture,
    data_audit: CellStateFrontierDataAudit,
    evaluation: CellStateFrontierEvaluationReport,
    replay: CellStateFrontierReplayReport,
    scenarios: CellStateFrontierScenarioReport,
    policy: CellStateFrontierPolicyReport,
    lineage: CellStateFrontierLineageReport,
    reconciliation: CellStateFrontierReconciliationReport,
    metrics: CellStateFrontierMetrics,
) -> CellStateFrontierBundle:
    record_ids = tuple(item.record_id for item in fixture.records)
    source_ids = tuple(item.source_id for item in fixture.sources)
    records_address = content_hash({"records": evaluation.receipts})
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "data_audit": data_audit,
        "evaluation": evaluation,
        "replay": replay,
        "scenarios": scenarios,
        "policy": policy,
        "lineage": lineage,
        "reconciliation": reconciliation,
        "metrics": metrics,
        "record_ids": record_ids,
        "source_ids": source_ids,
        "records_address": records_address,
    }
    return CellStateFrontierBundle(
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.context_key,
        fixture.evidence_boundary,
        data_audit,
        evaluation,
        replay,
        scenarios,
        policy,
        lineage,
        reconciliation,
        metrics,
        record_ids,
        source_ids,
        records_address,
        content_hash(body),
    )


__all__ = ["CellStateFrontierBundle", "build_cell_state_frontier_bundle"]

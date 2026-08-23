"""Release bundle assembly for control frontier artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_metrics import ControlFrontierMetrics
from .control_frontier_reconciliation import ControlFrontierReconciliation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierReleaseBundle:
    bundle_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    reconciliation_address: str
    manifest: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_control_frontier_bundle(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation, metrics: ControlFrontierMetrics, reconciliation: ControlFrontierReconciliation, *, bundle_id: str = "control-frontier-bundle") -> ControlFrontierReleaseBundle:
    manifest = {"boundary": fixture.evidence_boundary, "record_count": len(evaluation.executions), "operation_count": len(metrics.operation_metrics), "reconciled": reconciliation.reconciled, "research_only": True}
    body = {"bundle_id": bundle_id, "fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "metrics_address": metrics.content_address, "reconciliation_address": reconciliation.content_address, "manifest": manifest, "accepted": bool(reconciliation.reconciled)}
    return ControlFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierReleaseBundle", "assemble_control_frontier_bundle"]

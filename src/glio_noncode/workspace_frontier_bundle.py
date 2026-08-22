"""Composed workspace frontier release inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_metrics import WorkspaceFrontierMetricsReport
from .workspace_frontier_public_data import WorkspaceFrontierFixture
from .workspace_frontier_reconciliation import WorkspaceFrontierReconciliation


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReleaseBundle:
    fixture_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    reconciliation_address: str
    accepted: bool
    public_boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_workspace_frontier_bundle(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation, metrics: WorkspaceFrontierMetricsReport, reconciliation: WorkspaceFrontierReconciliation) -> WorkspaceFrontierReleaseBundle:
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "metrics_address": metrics.content_address,
        "reconciliation_address": reconciliation.content_address,
        "accepted": evaluation.accepted and reconciliation.reconciled,
        "public_boundary": fixture.evidence_boundary,
    }
    return WorkspaceFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierReleaseBundle", "assemble_workspace_frontier_bundle"]

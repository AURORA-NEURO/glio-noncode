"""Composed release inputs for the C05-C08 projection frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_metrics import BetaFrontierMetricsReport
from .workspace_beta_frontier_public_data import BetaFrontierFixture
from .workspace_beta_frontier_reconciliation import BetaFrontierReconciliation


@dataclass(frozen=True, slots=True)
class BetaFrontierReleaseBundle:
    """Address set used by release and review artifacts."""

    fixture_id: str
    fixture_address: str
    evaluation_address: str
    metrics_address: str
    reconciliation_address: str
    accepted: bool
    public_boundary: str
    operation_addresses: dict[str, str]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_beta_frontier_bundle(
    fixture: BetaFrontierFixture,
    evaluation: BetaFrontierEvaluation,
    metrics: BetaFrontierMetricsReport,
    reconciliation: BetaFrontierReconciliation,
) -> BetaFrontierReleaseBundle:
    """Assemble an immutable package without rewriting projection payloads."""

    operation_addresses: dict[str, str] = {}
    for execution in evaluation.executions:
        operation_addresses.setdefault(execution.operation.value, execution.content_address)
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_address": fixture.content_address,
        "evaluation_address": evaluation.content_address,
        "metrics_address": metrics.content_address,
        "reconciliation_address": reconciliation.content_address,
        "accepted": evaluation.accepted and reconciliation.reconciled,
        "public_boundary": fixture.evidence_boundary,
        "operation_addresses": operation_addresses,
    }
    return BetaFrontierReleaseBundle(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierReleaseBundle", "assemble_beta_frontier_bundle"]

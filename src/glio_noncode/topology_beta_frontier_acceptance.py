"""Release acceptance gates assembled from the complete beta evidence surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_contracts import TopologyBetaFrontierContractReport
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_integrity import TopologyBetaFrontierIntegrityReport
from .topology_beta_frontier_quality_gate import TopologyBetaFrontierQualityReport
from .topology_beta_frontier_review_queue import TopologyBetaFrontierReviewQueue
from .topology_beta_frontier_schema import TopologyBetaFrontierSchemaReport


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierAcceptanceGate:
    gate_id: str
    category: str
    passed: bool
    observed: Any
    expected: Any
    blocking: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierAcceptanceReport:
    gates: tuple[TopologyBetaFrontierAcceptanceGate, ...]
    blocking_failures: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def gate(self, gate_id: str) -> TopologyBetaFrontierAcceptanceGate:
        for item in self.gates:
            if item.gate_id == gate_id:
                return item
        raise KeyError(gate_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"gates": [item.to_dict() for item in self.gates], "blocking_failures": self.blocking_failures, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_acceptance(evaluation: TopologyBetaFrontierEvaluation, contracts: TopologyBetaFrontierContractReport, schema: TopologyBetaFrontierSchemaReport, quality: TopologyBetaFrontierQualityReport, integrity: TopologyBetaFrontierIntegrityReport, review_queue: TopologyBetaFrontierReviewQueue) -> TopologyBetaFrontierAcceptanceReport:
    gates = (
        TopologyBetaFrontierAcceptanceGate("evaluation", "replay", evaluation.accepted, evaluation.state_match_count, len(evaluation.rows), True, "all state and issue expectations replay"),
        TopologyBetaFrontierAcceptanceGate("contracts", "schema", contracts.accepted, len(contracts.contracts), 4, True, "all operation contracts are present"),
        TopologyBetaFrontierAcceptanceGate("schema", "schema", schema.accepted, len(schema.failed()), 0, True, "envelope schema has no failed checks"),
        TopologyBetaFrontierAcceptanceGate("quality", "quality", quality.accepted, quality.quality_score, 1.0, True, "quality floor is complete"),
        TopologyBetaFrontierAcceptanceGate("integrity", "integrity", integrity.accepted, len(integrity.checks), 6, True, "content and source integrity checks pass"),
        TopologyBetaFrontierAcceptanceGate("review-queue", "review", review_queue.accepted, review_queue.count, 12, False, "all controls are visible in the review queue"),
    )
    failures = tuple(item.gate_id for item in gates if item.blocking and not item.passed)
    return TopologyBetaFrontierAcceptanceReport(gates, failures, not failures)


__all__ = ["TopologyBetaFrontierAcceptanceGate", "TopologyBetaFrontierAcceptanceReport", "build_topology_beta_frontier_acceptance"]

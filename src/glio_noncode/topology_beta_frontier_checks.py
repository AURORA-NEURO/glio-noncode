"""Invariant checks that run after evaluation and before release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierInvariantResult:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierInvariantReport:
    results: tuple[TopologyBetaFrontierInvariantResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"results": [item.to_dict() for item in self.results], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_topology_beta_frontier_invariants(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierInvariantReport:
    result = (
        TopologyBetaFrontierInvariantResult("record-addresses", all(bool(item.adapter.content_address) for item in evaluation.rows), "every output is content addressed"),
        TopologyBetaFrontierInvariantResult("record-identity", len({item.record_id for item in evaluation.rows}) == len(evaluation.rows), "record identifiers are unique"),
        TopologyBetaFrontierInvariantResult("operation-balance", all(len(fixture.operation_records(item)) == 4 for item in __import__("glio_noncode.topology_beta_frontier_public_data", fromlist=["TopologyBetaFrontierOperation"]).TopologyBetaFrontierOperation), "operation cardinality remains four"),
        TopologyBetaFrontierInvariantResult("state-closure", all(item.observed_state for item in evaluation.rows), "every output has a state"),
        TopologyBetaFrontierInvariantResult("issue-closure", all(item.observed_issue_codes is not None for item in evaluation.rows), "issue tuples are explicit"),
        TopologyBetaFrontierInvariantResult("public-scope", all(row.payload.get("public_aggregate") is True for row in fixture.records), "all records remain aggregate scoped"),
    )
    return TopologyBetaFrontierInvariantReport(result, all(item.passed for item in result))


__all__ = ["TopologyBetaFrontierInvariantReport", "TopologyBetaFrontierInvariantResult", "run_topology_beta_frontier_invariants"]

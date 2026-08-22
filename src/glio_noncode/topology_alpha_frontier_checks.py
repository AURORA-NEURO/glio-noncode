"""Invariant checks for alpha replay and aggregate scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, TopologyAlphaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierInvariantResult:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierInvariantReport:
    results: tuple[TopologyAlphaFrontierInvariantResult, ...]
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


def run_topology_alpha_frontier_invariants(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierInvariantReport:
    results = (TopologyAlphaFrontierInvariantResult("record-addresses", all(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), "every output is content addressed"), TopologyAlphaFrontierInvariantResult("record-identity", len({item.record_id for item in evaluation.rows}) == len(evaluation.rows), "record identifiers are unique"), TopologyAlphaFrontierInvariantResult("operation-balance", all(len(fixture.operation_records(item)) == 4 for item in TopologyAlphaFrontierOperation), "operation cardinality remains four"), TopologyAlphaFrontierInvariantResult("state-closure", all(item.observed_state for item in evaluation.rows), "every output has a state"), TopologyAlphaFrontierInvariantResult("issue-closure", all(item.observed_issue_codes is not None for item in evaluation.rows), "issue tuples are explicit"), TopologyAlphaFrontierInvariantResult("public-scope", all(row.payload.get("public_aggregate") is True for row in fixture.records), "aggregate boundary is retained"))
    return TopologyAlphaFrontierInvariantReport(results, all(item.passed for item in results))


__all__ = ["TopologyAlphaFrontierInvariantReport", "TopologyAlphaFrontierInvariantResult", "run_topology_alpha_frontier_invariants"]

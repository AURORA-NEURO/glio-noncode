"""Invariant checks for topology context execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import (
    TopologyContextFrontierFixture,
    TopologyContextFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierInvariant:
    invariant_id: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierInvariantReport:
    results: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"results": self.results, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_topology_context_frontier_invariants(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierInvariantReport:
    checks = (
        ("record-addresses", len(fixture.records) == 16),
        (
            "operation-balance",
            all(
                len(fixture.operation_records(item)) == 4
                for item in TopologyContextFrontierOperation
            ),
        ),
        ("state-replay", evaluation.state_match_count == 16),
        ("issue-replay", evaluation.issue_match_count == 16),
        ("unique-record-ids", len({item.record_id for item in fixture.records}) == 16),
        (
            "unique-result-addresses",
            len({item.adapter.content_address for item in evaluation.rows}) == 16,
        ),
    )
    results = tuple({"invariant_id": key, "passed": passed} for key, passed in checks)
    return TopologyContextFrontierInvariantReport(results, all(item["passed"] for item in results))


__all__ = [
    "TopologyContextFrontierInvariant",
    "TopologyContextFrontierInvariantReport",
    "run_topology_context_frontier_invariants",
]

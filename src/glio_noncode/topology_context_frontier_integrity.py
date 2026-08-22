"""Content-address and result-integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import TopologyContextFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierIntegrityCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierIntegrityReport:
    checks: tuple[TopologyContextFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_context_frontier_integrity(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierIntegrityReport:
    checks = (
        TopologyContextFrontierIntegrityCheck(
            "fixture-address", bool(fixture.content_address), "fixture has an address"
        ),
        TopologyContextFrontierIntegrityCheck(
            "record-addresses",
            all(item.content_address for item in fixture.records),
            "records have addresses",
        ),
        TopologyContextFrontierIntegrityCheck(
            "result-addresses",
            all(item.adapter.content_address for item in evaluation.rows),
            "results have addresses",
        ),
        TopologyContextFrontierIntegrityCheck(
            "address-cardinality",
            len({item.adapter.content_address for item in evaluation.rows}) == 16,
            "result addresses are unique",
        ),
        TopologyContextFrontierIntegrityCheck(
            "state-closure", evaluation.accepted, "evaluation is accepted"
        ),
    )
    return TopologyContextFrontierIntegrityReport(checks, all(item.passed for item in checks))


__all__ = [
    "TopologyContextFrontierIntegrityCheck",
    "TopologyContextFrontierIntegrityReport",
    "evaluate_topology_context_frontier_integrity",
]

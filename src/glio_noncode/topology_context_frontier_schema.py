"""Schema checks for the public topology context envelope."""

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
class TopologyContextFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierSchemaReport:
    checks: tuple[TopologyContextFrontierSchemaCheck, ...]
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


def validate_topology_context_frontier_schema(
    fixture: TopologyContextFrontierFixture,
    evaluation: TopologyContextFrontierEvaluation,
) -> TopologyContextFrontierSchemaReport:
    checks = (
        TopologyContextFrontierSchemaCheck(
            "fixture-id", bool(fixture.fixture_id), "fixture ID is present"
        ),
        TopologyContextFrontierSchemaCheck(
            "fixture-version", fixture.version.startswith("2026."), "version is pinned"
        ),
        TopologyContextFrontierSchemaCheck(
            "record-cardinality", len(fixture.records) == 16, "sixteen records are required"
        ),
        TopologyContextFrontierSchemaCheck(
            "operation-cardinality",
            all(
                len(fixture.operation_records(item)) == 4
                for item in TopologyContextFrontierOperation
            ),
            "four records exist per operation",
        ),
        TopologyContextFrontierSchemaCheck(
            "evaluation-cardinality",
            len(evaluation.rows) == len(fixture.records),
            "evaluation covers every record",
        ),
        TopologyContextFrontierSchemaCheck(
            "address-closure",
            bool(fixture.content_address)
            and all(item.adapter.content_address for item in evaluation.rows),
            "addresses are present",
        ),
    )
    return TopologyContextFrontierSchemaReport(
        checks=checks, accepted=all(item.passed for item in checks)
    )


__all__ = [
    "TopologyContextFrontierSchemaCheck",
    "TopologyContextFrontierSchemaReport",
    "validate_topology_context_frontier_schema",
]

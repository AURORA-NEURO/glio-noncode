"""Schema checks for the public topology-alpha envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture, TopologyAlphaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    expected: Any = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSchemaReport:
    checks: tuple[TopologyAlphaFrontierSchemaCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "failed": self.failed()}
        if include_address:
            value["content_address"] = self.content_address
        return value


def validate_topology_alpha_frontier_schema(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierSchemaReport:
    checks = (
        TopologyAlphaFrontierSchemaCheck("fixture-id", bool(fixture.fixture_id), "fixture identity is present"),
        TopologyAlphaFrontierSchemaCheck("fixture-version", fixture.version.startswith("2026."), "fixture version is pinned"),
        TopologyAlphaFrontierSchemaCheck("aggregate-boundary", fixture.boundary == "public_aggregate_non_patient", "aggregate boundary is explicit"),
        TopologyAlphaFrontierSchemaCheck("record-cardinality", len(fixture.records) == 16, "sixteen records are required", len(fixture.records), 16),
        TopologyAlphaFrontierSchemaCheck("source-cardinality", len(fixture.sources) == 4, "four source receipts are required", len(fixture.sources), 4),
        TopologyAlphaFrontierSchemaCheck("operation-cardinality", all(len(fixture.operation_records(item)) == 4 for item in TopologyAlphaFrontierOperation), "each operation has four records"),
        TopologyAlphaFrontierSchemaCheck("public-payloads", all(row.payload.get("public_aggregate") is True for row in fixture.records), "each payload carries aggregate scope"),
        TopologyAlphaFrontierSchemaCheck("evaluation-cardinality", len(evaluation.rows) == len(fixture.records), "evaluation covers every record"),
        TopologyAlphaFrontierSchemaCheck("address-closure", bool(fixture.content_address) and all(row.adapter.content_address.startswith("sha256:") for row in evaluation.rows), "fixture and result addresses are present"),
        TopologyAlphaFrontierSchemaCheck("accepted-replay", evaluation.accepted, "all fixture expectations replay successfully"),
    )
    return TopologyAlphaFrontierSchemaReport(checks, all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierSchemaCheck", "TopologyAlphaFrontierSchemaReport", "validate_topology_alpha_frontier_schema"]

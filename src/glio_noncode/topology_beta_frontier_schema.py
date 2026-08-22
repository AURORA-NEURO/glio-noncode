"""Envelope and field checks for C05-C08 records and replay outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture, TopologyBetaFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    expected: Any = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierSchemaReport:
    checks: tuple[TopologyBetaFrontierSchemaCheck, ...]
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


def validate_topology_beta_frontier_schema(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierSchemaReport:
    checks = (
        TopologyBetaFrontierSchemaCheck("fixture-id", bool(fixture.fixture_id), "fixture identity is present"),
        TopologyBetaFrontierSchemaCheck("fixture-version", fixture.version.startswith("2026."), "fixture version is pinned"),
        TopologyBetaFrontierSchemaCheck("aggregate-boundary", fixture.boundary == "public_aggregate_non_patient", "aggregate boundary is explicit"),
        TopologyBetaFrontierSchemaCheck("record-cardinality", len(fixture.records) == 16, "sixteen records are required", len(fixture.records), 16),
        TopologyBetaFrontierSchemaCheck("source-cardinality", len(fixture.sources) == 4, "four source receipts are required", len(fixture.sources), 4),
        TopologyBetaFrontierSchemaCheck("operation-cardinality", all(len(fixture.operation_records(item)) == 4 for item in TopologyBetaFrontierOperation), "each operation has four records"),
        TopologyBetaFrontierSchemaCheck("public-payloads", all(bool(row.payload.get("public_aggregate")) for row in fixture.records), "each payload carries its public boundary"),
        TopologyBetaFrontierSchemaCheck("evaluation-cardinality", len(evaluation.rows) == len(fixture.records), "evaluation covers every record"),
        TopologyBetaFrontierSchemaCheck("address-closure", bool(fixture.content_address) and all(row.adapter.content_address.startswith("sha256:") for row in evaluation.rows), "fixture and adapter addresses are present"),
        TopologyBetaFrontierSchemaCheck("accepted-replay", evaluation.accepted, "all fixture expectations replay successfully"),
    )
    return TopologyBetaFrontierSchemaReport(checks, all(item.passed for item in checks))


__all__ = ["TopologyBetaFrontierSchemaCheck", "TopologyBetaFrontierSchemaReport", "validate_topology_beta_frontier_schema"]

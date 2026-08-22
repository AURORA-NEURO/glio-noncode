"""Invariant checks for beta frontier records and replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierInvariantReport:
    fixture_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": self.checks, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def run_link_graph_beta_frontier_invariants(fixture: LinkGraphBetaFrontierFixture, evaluation: LinkGraphBetaFrontierEvaluation) -> LinkGraphBetaFrontierInvariantReport:
    source_ids = {source.source_id for source in fixture.sources}
    record_ids = [record.record_id for record in fixture.records]
    checks = ({"check_id": "unique_record_ids", "passed": len(record_ids) == len(set(record_ids)), "detail": "record IDs are unique"}, {"check_id": "operation_balance", "passed": all(len(fixture.operation_records(operation)) == 4 for operation in LinkGraphBetaFrontierOperation), "detail": "each operation has four records"}, {"check_id": "source_closure", "passed": all(set(record.source_ids) <= source_ids for record in fixture.records), "detail": "record receipts resolve"}, {"check_id": "context_closure", "passed": all(record.context_key in {fixture.context_key, fixture.foreign_context_key} for record in fixture.records), "detail": "contexts are declared"}, {"check_id": "replay_acceptance", "passed": evaluation.accepted, "detail": "replay agrees"}, {"check_id": "address_presence", "passed": bool(fixture.content_address) and all(record.content_address for record in fixture.records), "detail": "content addresses exist"})
    return LinkGraphBetaFrontierInvariantReport(fixture.fixture_id, checks, all(item["passed"] for item in checks))


__all__ = ["LinkGraphBetaFrontierInvariantReport", "run_link_graph_beta_frontier_invariants"]

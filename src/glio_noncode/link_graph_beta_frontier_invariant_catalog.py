"""Named invariants for beta evidence identity and state closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierOperation, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierInvariant:
    invariant_id: str
    description: str
    category: str
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierInvariantResult:
    invariant_id: str
    passed: bool
    observed: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierInvariantCatalogReport:
    fixture_id: str
    invariants: tuple[LinkGraphBetaFrontierInvariant, ...]
    results: tuple[LinkGraphBetaFrontierInvariantResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        blocking = {item.invariant_id for item in self.invariants if item.blocking}
        return tuple(item.invariant_id for item in self.results if item.invariant_id in blocking and not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "invariants": [item.to_dict() for item in self.invariants], "results": [item.to_dict() for item in self.results], "blocking_failures": self.blocking_failures, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_invariant_catalog(fixture: LinkGraphBetaFrontierFixture | None = None, evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierInvariantCatalogReport:
    value = fixture or default_link_graph_beta_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_beta_frontier_fixture_eval", fromlist=["evaluate_link_graph_beta_frontier_fixture"]).evaluate_link_graph_beta_frontier_fixture(value)
    invariants = (LinkGraphBetaFrontierInvariant("unique-record-ids", "record IDs are unique", "identity"), LinkGraphBetaFrontierInvariant("operation-balance", "each operation has four records", "coverage"), LinkGraphBetaFrontierInvariant("role-balance", "four positive and twelve controls exist", "coverage"), LinkGraphBetaFrontierInvariant("state-closure", "replayed states are declared", "state"), LinkGraphBetaFrontierInvariant("issue-closure", "replayed issues are declared", "issues"), LinkGraphBetaFrontierInvariant("address-closure", "fixture and rows have addresses", "integrity"))
    ids = [record.record_id for record in value.records]
    declared_states = {record.expected_state for record in value.records}
    observed_states = {row.observed_state for row in replay.rows}
    declared_issues = {issue for record in value.records for issue in record.expected_issue_codes}
    observed_issues = {issue for row in replay.rows for issue in row.observed_issue_codes}
    checks = ((len(ids) == len(set(ids)), len(ids), "record identity"), (all(len(value.operation_records(operation)) == 4 for operation in LinkGraphBetaFrontierOperation), {operation.value: len(value.operation_records(operation)) for operation in LinkGraphBetaFrontierOperation}, "operation balance"), (len(value.positive_records) == 4 and len(value.control_records) == 12, (len(value.positive_records), len(value.control_records)), "role balance"), (observed_states <= declared_states, sorted(observed_states), "state closure"), (observed_issues <= declared_issues, sorted(observed_issues), "issue closure"), (bool(value.content_address) and all(record.content_address for record in value.records), value.content_address, "address closure"))
    results = tuple(LinkGraphBetaFrontierInvariantResult(item.invariant_id, passed, observed, detail) for item, (passed, observed, detail) in zip(invariants, checks))
    return LinkGraphBetaFrontierInvariantCatalogReport(value.fixture_id, invariants, results, all(item.passed for item in results))


__all__ = ["LinkGraphBetaFrontierInvariant", "LinkGraphBetaFrontierInvariantCatalogReport", "LinkGraphBetaFrontierInvariantResult", "evaluate_link_graph_beta_frontier_invariant_catalog"]

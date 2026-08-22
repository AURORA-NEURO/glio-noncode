"""Named invariants used to keep the four link operations closed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierOperation, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierInvariant:
    invariant_id: str
    description: str
    category: str
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierInvariantResult:
    invariant_id: str
    passed: bool
    measured_value: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierInvariantReport:
    fixture_id: str
    invariants: tuple[LinkGraphFoundationFrontierInvariant, ...]
    results: tuple[LinkGraphFoundationFrontierInvariantResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        blocking = {item.invariant_id for item in self.invariants if item.blocking}
        return tuple(item.invariant_id for item in self.results if item.invariant_id in blocking and not item.passed)

    def result(self, invariant_id: str) -> LinkGraphFoundationFrontierInvariantResult:
        return next(item for item in self.results if item.invariant_id == invariant_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "invariants": [item.to_dict() for item in self.invariants], "results": [item.to_dict() for item in self.results], "blocking_failures": self.blocking_failures, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_foundation_frontier_invariants() -> tuple[LinkGraphFoundationFrontierInvariant, ...]:
    return (LinkGraphFoundationFrontierInvariant("unique-record-ids", "record identifiers are unique", "identity"), LinkGraphFoundationFrontierInvariant("operation-balance", "each operation has four records", "coverage"), LinkGraphFoundationFrontierInvariant("role-balance", "four positive and twelve control records exist", "coverage"), LinkGraphFoundationFrontierInvariant("context-preserved", "context keys are preserved through replay", "context"), LinkGraphFoundationFrontierInvariant("state-closed", "all observed states are declared link states", "state"), LinkGraphFoundationFrontierInvariant("issue-closed", "observed issues are declared by the fixture", "issues"), LinkGraphFoundationFrontierInvariant("address-stable", "fixture and rows have content addresses", "integrity"))


def _checks(fixture: LinkGraphFoundationFrontierFixture, evaluation: LinkGraphFoundationFrontierEvaluation) -> tuple[tuple[bool, Any, str], ...]:
    record_ids = tuple(item.record_id for item in fixture.records)
    operations = {operation.value: len(fixture.operation_records(operation)) for operation in LinkGraphFoundationFrontierOperation}
    allowed_contexts = {fixture.context_key, fixture.foreign_context_key}
    contexts = all(record.context_key in allowed_contexts for record in fixture.records) and len(evaluation.rows) == len(fixture.records)
    states = {row.observed_state for row in evaluation.rows}
    declared_issues = {issue for record in fixture.records for issue in record.expected_issue_codes}
    observed_issues = {issue for row in evaluation.rows for issue in row.observed_issue_codes}
    return ((len(record_ids) == len(set(record_ids)), len(record_ids), "record identity"), (all(value == 4 for value in operations.values()), operations, "operation balance"), (len(fixture.positive_records) == 4 and len(fixture.control_records) == 12, (len(fixture.positive_records), len(fixture.control_records)), "role balance"), (contexts, contexts, "context preservation"), (states <= {"supported", "absent", "ambiguous", "abstained", "partial", "contradictory", "out_of_domain"}, sorted(states), "state closure"), (observed_issues <= declared_issues, sorted(observed_issues), "issue closure"), (bool(fixture.content_address) and all(item.content_address for item in fixture.records), fixture.content_address, "address stability"))


def evaluate_link_graph_foundation_frontier_invariants(fixture: LinkGraphFoundationFrontierFixture | None = None, evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierInvariantReport:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    replay = evaluation or __import__("glio_noncode.link_graph_foundation_frontier_fixture_eval", fromlist=["evaluate_link_graph_foundation_frontier_fixture"]).evaluate_link_graph_foundation_frontier_fixture(value)
    invariants = default_link_graph_foundation_frontier_invariants()
    results = tuple(LinkGraphFoundationFrontierInvariantResult(item.invariant_id, passed, measured, detail) for item, (passed, measured, detail) in zip(invariants, _checks(value, replay)))
    return LinkGraphFoundationFrontierInvariantReport(value.fixture_id, invariants, results, all(item.passed for item in results if item.invariant_id in {rule.invariant_id for rule in invariants if rule.blocking}))


__all__ = ["LinkGraphFoundationFrontierInvariant", "LinkGraphFoundationFrontierInvariantReport", "LinkGraphFoundationFrontierInvariantResult", "default_link_graph_foundation_frontier_invariants", "evaluate_link_graph_foundation_frontier_invariants"]

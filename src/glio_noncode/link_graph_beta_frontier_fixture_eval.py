"""Deterministic replay for the C05-C08 beta aggregate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_adapters import LinkGraphBetaFrontierAdapterResult, execute_link_graph_beta_frontier_record
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, LinkGraphBetaFrontierRecord, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierEvaluationRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    issue_match: bool
    adapter: LinkGraphBetaFrontierAdapterResult

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierEvaluation:
    fixture_id: str
    rows: tuple[LinkGraphBetaFrontierEvaluationRow, ...]
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.rows if not item.state_match or not item.issue_match)

    def by_operation(self, operation: str) -> tuple[LinkGraphBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def by_state(self, state: str) -> tuple[LinkGraphBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.observed_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rows": [item.to_dict() for item in self.rows], "state_match_count": self.state_match_count, "issue_match_count": self.issue_match_count, "failed_record_ids": self.failed_record_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_beta_frontier_fixture(fixture: LinkGraphBetaFrontierFixture | None = None) -> LinkGraphBetaFrontierEvaluation:
    value = fixture or default_link_graph_beta_frontier_fixture()
    rows = []
    for record in value.records:
        adapter = execute_link_graph_beta_frontier_record(record)
        rows.append(LinkGraphBetaFrontierEvaluationRow(record.record_id, record.operation.value, record.role.value, record.expected_state, adapter.state, adapter.state == record.expected_state, record.expected_issue_codes, adapter.issue_codes, set(record.expected_issue_codes) <= set(adapter.issue_codes), adapter))
    observed = tuple(rows)
    state_count = sum(item.state_match for item in observed)
    issue_count = sum(item.issue_match for item in observed)
    return LinkGraphBetaFrontierEvaluation(value.fixture_id, observed, state_count, issue_count, bool(observed) and state_count == len(observed) and issue_count == len(observed))


def execute_link_graph_beta_frontier_record_for_test(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierAdapterResult:
    return execute_link_graph_beta_frontier_record(record)


__all__ = ["LinkGraphBetaFrontierEvaluation", "LinkGraphBetaFrontierEvaluationRow", "evaluate_link_graph_beta_frontier_fixture", "execute_link_graph_beta_frontier_record_for_test"]

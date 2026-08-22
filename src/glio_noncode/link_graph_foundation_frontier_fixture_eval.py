"""Deterministic fixture replay for C01-C04 link baselines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_adapters import LinkGraphFoundationFrontierAdapterResult, execute_link_graph_foundation_frontier_record
from .link_graph_foundation_frontier_public_data import LinkGraphFoundationFrontierFixture, LinkGraphFoundationFrontierRecord, default_link_graph_foundation_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierEvaluationRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    issue_match: bool
    adapter: LinkGraphFoundationFrontierAdapterResult

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierEvaluation:
    fixture_id: str
    rows: tuple[LinkGraphFoundationFrontierEvaluationRow, ...]
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

    def by_operation(self, operation: str) -> tuple[LinkGraphFoundationFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def by_state(self, state: str) -> tuple[LinkGraphFoundationFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.observed_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rows": [item.to_dict() for item in self.rows], "state_match_count": self.state_match_count, "issue_match_count": self.issue_match_count, "failed_record_ids": self.failed_record_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_foundation_frontier_fixture(fixture: LinkGraphFoundationFrontierFixture | None = None) -> LinkGraphFoundationFrontierEvaluation:
    value = fixture or default_link_graph_foundation_frontier_fixture()
    rows = []
    for record in value.records:
        adapter = execute_link_graph_foundation_frontier_record(record)
        rows.append(LinkGraphFoundationFrontierEvaluationRow(record.record_id, record.operation.value, record.role.value, record.expected_state, adapter.state, adapter.state == record.expected_state, record.expected_issue_codes, adapter.issue_codes, set(record.expected_issue_codes) <= set(adapter.issue_codes), adapter))
    values = tuple(rows)
    state_count = sum(item.state_match for item in values)
    issue_count = sum(item.issue_match for item in values)
    return LinkGraphFoundationFrontierEvaluation(value.fixture_id, values, state_count, issue_count, bool(values) and state_count == len(values) and issue_count == len(values))


def execute_link_graph_foundation_frontier_record_for_test(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierAdapterResult:
    return execute_link_graph_foundation_frontier_record(record)


__all__ = ["LinkGraphFoundationFrontierEvaluation", "LinkGraphFoundationFrontierEvaluationRow", "evaluate_link_graph_foundation_frontier_fixture", "execute_link_graph_foundation_frontier_record_for_test"]

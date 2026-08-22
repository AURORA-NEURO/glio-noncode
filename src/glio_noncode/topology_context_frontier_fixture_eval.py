"""Deterministic evaluation and state accounting for Domain 09 fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_adapters import (
    TopologyContextFrontierAdapterResult,
    execute_topology_context_frontier_record,
)
from .topology_context_frontier_public_data import (
    TopologyContextFrontierFixture,
    TopologyContextFrontierRecord,
    default_topology_context_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierEvaluationRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    issue_match: bool
    adapter: TopologyContextFrontierAdapterResult

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierEvaluation:
    fixture_id: str
    rows: tuple[TopologyContextFrontierEvaluationRow, ...]
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(
            item.record_id for item in self.rows if not item.state_match or not item.issue_match
        )

    def by_operation(self, operation: str) -> tuple[TopologyContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def by_state(self, state: str) -> tuple[TopologyContextFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.observed_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "rows": [item.to_dict() for item in self.rows],
            "state_match_count": self.state_match_count,
            "issue_match_count": self.issue_match_count,
            "failed_record_ids": self.failed_record_ids,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def _issue_match(expected: tuple[str, ...], observed: tuple[str, ...]) -> bool:
    expected_set = set(expected)
    observed_set = set(observed)
    return expected_set <= observed_set


def evaluate_topology_context_frontier_fixture(
    fixture: TopologyContextFrontierFixture | None = None,
) -> TopologyContextFrontierEvaluation:
    value = fixture or default_topology_context_frontier_fixture()
    rows: list[TopologyContextFrontierEvaluationRow] = []
    for record in value.records:
        adapter = execute_topology_context_frontier_record(record)
        state_match = adapter.state == record.expected_state.value
        issue_match = _issue_match(record.expected_issue_codes, adapter.issue_codes)
        rows.append(
            TopologyContextFrontierEvaluationRow(
                record_id=record.record_id,
                operation=record.operation.value,
                role=record.role.value,
                expected_state=record.expected_state.value,
                observed_state=adapter.state,
                state_match=state_match,
                expected_issue_codes=record.expected_issue_codes,
                observed_issue_codes=adapter.issue_codes,
                issue_match=issue_match,
                adapter=adapter,
            )
        )
    state_count = sum(item.state_match for item in rows)
    issue_count = sum(item.issue_match for item in rows)
    return TopologyContextFrontierEvaluation(
        fixture_id=value.fixture_id,
        rows=tuple(rows),
        state_match_count=state_count,
        issue_match_count=issue_count,
        accepted=state_count == len(rows) and issue_count == len(rows),
    )


def execute_topology_context_frontier_record_for_test(
    record: TopologyContextFrontierRecord,
) -> TopologyContextFrontierAdapterResult:
    return execute_topology_context_frontier_record(record)


__all__ = [
    "TopologyContextFrontierEvaluation",
    "TopologyContextFrontierEvaluationRow",
    "evaluate_topology_context_frontier_fixture",
    "execute_topology_context_frontier_record_for_test",
]

"""Deterministic replay of Domain 11 C01-C04 aggregate rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_adapters import (
    CausalFoundationFrontierAdapterResult,
    execute_causal_foundation_frontier_record,
)
from .causal_foundation_frontier_public_data import (
    CausalFoundationFrontierFixture,
    CausalFoundationFrontierRecord,
    default_causal_foundation_frontier_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierEvaluationRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    issue_match: bool
    adapter: CausalFoundationFrontierAdapterResult

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierEvaluation:
    fixture_id: str
    rows: tuple[CausalFoundationFrontierEvaluationRow, ...]
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

    @property
    def state_counts(self) -> dict[str, int]:
        return {state: sum(item.observed_state == state for item in self.rows) for state in sorted({item.observed_state for item in self.rows})}

    @property
    def issue_counts(self) -> dict[str, int]:
        values = sorted({issue for item in self.rows for issue in item.observed_issue_codes})
        return {issue: sum(issue in item.observed_issue_codes for item in self.rows) for issue in values}

    def by_operation(self, operation: str) -> tuple[CausalFoundationFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def by_state(self, state: str) -> tuple[CausalFoundationFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.observed_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "fixture_id": self.fixture_id,
            "rows": [item.to_dict() for item in self.rows],
            "state_match_count": self.state_match_count,
            "issue_match_count": self.issue_match_count,
            "failed_record_ids": self.failed_record_ids,
            "state_counts": self.state_counts,
            "issue_counts": self.issue_counts,
            "accepted": self.accepted,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_foundation_frontier_fixture(
    fixture: CausalFoundationFrontierFixture | None = None,
) -> CausalFoundationFrontierEvaluation:
    value = fixture or default_causal_foundation_frontier_fixture()
    rows: list[CausalFoundationFrontierEvaluationRow] = []
    for record in value.records:
        adapter = execute_causal_foundation_frontier_record(record)
        rows.append(
            CausalFoundationFrontierEvaluationRow(
                record.record_id,
                record.operation.value,
                record.role.value,
                record.expected_state.value,
                adapter.state.value,
                adapter.state is record.expected_state,
                record.expected_issue_codes,
                adapter.issue_codes,
                set(record.expected_issue_codes) <= set(adapter.issue_codes),
                adapter,
            )
        )
    values = tuple(rows)
    states = sum(item.state_match for item in values)
    issues = sum(item.issue_match for item in values)
    return CausalFoundationFrontierEvaluation(value.fixture_id, values, states, issues, bool(values) and states == len(values) and issues == len(values))


def execute_causal_foundation_frontier_record_for_test(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    return execute_causal_foundation_frontier_record(record)


__all__ = [
    "CausalFoundationFrontierEvaluation",
    "CausalFoundationFrontierEvaluationRow",
    "evaluate_causal_foundation_frontier_fixture",
    "execute_causal_foundation_frontier_record_for_test",
]

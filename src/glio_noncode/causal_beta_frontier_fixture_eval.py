"""Deterministic evaluation of C05-C08 positive and control rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta import CausalBetaState
from .causal_beta_frontier_adapters import CausalBetaFrontierAdapterResult, execute_causal_beta_frontier_record
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, CausalBetaFrontierRecord, default_causal_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierEvaluationRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    issue_match: bool
    adapter: CausalBetaFrontierAdapterResult

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierEvaluation:
    fixture_id: str
    rows: tuple[CausalBetaFrontierEvaluationRow, ...]
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
        return {issue: sum(issue in item.observed_issue_codes for item in self.rows) for issue in sorted({issue for item in self.rows for issue in item.observed_issue_codes})}

    def by_operation(self, operation: str) -> tuple[CausalBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def by_state(self, state: str) -> tuple[CausalBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.observed_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "rows": [item.to_dict() for item in self.rows], "state_match_count": self.state_match_count, "issue_match_count": self.issue_match_count, "failed_record_ids": self.failed_record_ids, "state_counts": self.state_counts, "issue_counts": self.issue_counts, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_beta_frontier_fixture(fixture: CausalBetaFrontierFixture | None = None) -> CausalBetaFrontierEvaluation:
    value = fixture or default_causal_beta_frontier_fixture()
    rows = tuple(CausalBetaFrontierEvaluationRow(record.record_id, record.operation.value, record.role.value, record.expected_state.value, (result := execute_causal_beta_frontier_record(record)).state.value, result.state is record.expected_state, record.expected_issue_codes, result.issue_codes, set(record.expected_issue_codes) <= set(result.issue_codes), result) for record in value.records)
    state_count = sum(item.state_match for item in rows)
    issue_count = sum(item.issue_match for item in rows)
    return CausalBetaFrontierEvaluation(value.fixture_id, rows, state_count, issue_count, bool(rows) and state_count == len(rows) and issue_count == len(rows))


def execute_causal_beta_frontier_record_for_test(record: CausalBetaFrontierRecord) -> CausalBetaFrontierAdapterResult:
    return execute_causal_beta_frontier_record(record)


__all__ = ["CausalBetaFrontierEvaluation", "CausalBetaFrontierEvaluationRow", "evaluate_causal_beta_frontier_fixture", "execute_causal_beta_frontier_record_for_test"]

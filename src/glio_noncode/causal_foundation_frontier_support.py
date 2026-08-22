"""Small deterministic helpers shared by the causal foundation surfaces."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture


def state_counts(evaluation: CausalFoundationFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(item.observed_state for item in evaluation.rows).items()))


def issue_counts(evaluation: CausalFoundationFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(issue for item in evaluation.rows for issue in item.observed_issue_codes).items()))


def operation_counts(fixture: CausalFoundationFrontierFixture) -> dict[str, int]:
    return {operation.value: len(fixture.operation_records(operation)) for operation in fixture.records[0].operation.__class__}


def record_ids(fixture: CausalFoundationFrontierFixture) -> tuple[str, ...]:
    return tuple(item.record_id for item in fixture.records)


def check(check_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "detail": detail}


__all__ = ["check", "issue_counts", "operation_counts", "record_ids", "state_counts"]

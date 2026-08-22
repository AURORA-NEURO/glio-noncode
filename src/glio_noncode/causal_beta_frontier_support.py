"""Small deterministic helpers for the beta frontier surfaces."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture, CausalBetaFrontierOperation


def state_counts(evaluation: CausalBetaFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(item.observed_state for item in evaluation.rows).items()))


def issue_counts(evaluation: CausalBetaFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(issue for item in evaluation.rows for issue in item.observed_issue_codes).items()))


def operation_counts(fixture: CausalBetaFrontierFixture) -> dict[str, int]:
    return {operation.value: len(fixture.operation_records(operation)) for operation in CausalBetaFrontierOperation}


def check(check_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "detail": detail}


__all__ = ["check", "issue_counts", "operation_counts", "state_counts"]

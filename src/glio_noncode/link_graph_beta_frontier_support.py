"""Small deterministic summaries shared by C05-C08 quality reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture


def state_counts(evaluation: LinkGraphBetaFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(row.observed_state for row in evaluation.rows).items()))


def issue_counts(evaluation: LinkGraphBetaFrontierEvaluation) -> dict[str, int]:
    return dict(sorted(Counter(issue for row in evaluation.rows for issue in row.observed_issue_codes).items()))


def operation_counts(fixture: LinkGraphBetaFrontierFixture) -> dict[str, int]:
    return {operation.value: len(fixture.operation_records(operation)) for operation in sorted(set(item.operation for item in fixture.records), key=lambda item: item.value)}


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check_id": name, "passed": bool(passed), "detail": detail}


def record_ids(fixture: LinkGraphBetaFrontierFixture) -> tuple[str, ...]:
    return tuple(record.record_id for record in fixture.records)


__all__ = ["check", "issue_counts", "operation_counts", "record_ids", "state_counts"]

"""Stable tabular views for C05-C08 review and summary."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics
from .causal_beta_frontier_policy import CausalBetaFrontierPolicyDecision
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_reconciliation import CausalBetaFrontierReconciliation
from .causal_beta_frontier_review import CausalBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    issue_codes: tuple[str, ...]
    decision: str
    priority: str
    state_match: bool
    issue_match: bool
    accepted: bool
    source_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "role": self.role, "expected_state": self.expected_state, "observed_state": self.observed_state, "issue_codes": self.issue_codes, "decision": self.decision, "priority": self.priority, "state_match": self.state_match, "issue_match": self.issue_match, "accepted": self.accepted, "source_count": self.source_count}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierReviewView:
    fixture_id: str
    rows: tuple[CausalBetaFrontierReviewRow, ...]
    columns: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_csv(self) -> str:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(self.columns)
        for row in self.rows:
            values = row.to_dict(False)
            writer.writerow([";".join(map(str, values.get(column, ()))) if isinstance(values.get(column), tuple) else values.get(column, "") for column in self.columns])
        return stream.getvalue()

    def by_operation(self, operation: str) -> tuple[CausalBetaFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "columns": self.columns, "rows": [item.to_dict() for item in self.rows], "row_count": len(self.rows), "content_csv": self.to_csv()}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_review_view(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, decisions: tuple[CausalBetaFrontierPolicyDecision, ...], reconciliation: CausalBetaFrontierReconciliation, review: CausalBetaFrontierReviewQueue) -> CausalBetaFrontierReviewView:
    evaluation_map = {item.record_id: item for item in evaluation.rows}
    decision_map = {item.record_id: item for item in decisions}
    reconciliation_map = {item.record_id: item for item in reconciliation.items}
    review_map = {item.record_id: item for item in review.items}
    rows = tuple(CausalBetaFrontierReviewRow(record.record_id, record.operation.value, record.role.value, record.expected_state.value, evaluation_map[record.record_id].observed_state, evaluation_map[record.record_id].observed_issue_codes, decision_map[record.record_id].decision.value, review_map[record.record_id].priority, reconciliation_map[record.record_id].state_match, reconciliation_map[record.record_id].issue_match, reconciliation_map[record.record_id].accepted, len(record.source_ids)) for record in fixture.records)
    columns = ("record_id", "operation", "role", "expected_state", "observed_state", "issue_codes", "decision", "priority", "state_match", "issue_match", "accepted", "source_count")
    return CausalBetaFrontierReviewView(fixture.fixture_id, rows, columns)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierSummaryView:
    fixture_id: str
    metrics: CausalBetaFrontierMetrics
    accepted: bool
    retained_count: int
    review_count: int
    blocked_count: int
    top_issue_codes: tuple[tuple[str, int], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "metrics": self.metrics.to_dict(), "accepted": self.accepted, "retained_count": self.retained_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "top_issue_codes": self.top_issue_codes}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_beta_frontier_summary_view(fixture: CausalBetaFrontierFixture, metrics: CausalBetaFrontierMetrics, review: CausalBetaFrontierReviewQueue, accepted: bool) -> CausalBetaFrontierSummaryView:
    return CausalBetaFrontierSummaryView(fixture.fixture_id, metrics, accepted, review.retained_count, review.review_count, review.blocked_count, tuple(sorted(metrics.issue_counts.items(), key=lambda item: (-item[1], item[0]))))


__all__ = ["CausalBetaFrontierReviewRow", "CausalBetaFrontierReviewView", "CausalBetaFrontierSummaryView", "build_causal_beta_frontier_review_view", "build_causal_beta_frontier_summary_view"]

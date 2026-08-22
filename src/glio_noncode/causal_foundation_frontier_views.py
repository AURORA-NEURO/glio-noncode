"""Stable row, control, and summary views for causal foundation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_metrics import CausalFoundationFrontierMetrics
from .causal_foundation_frontier_policy import CausalFoundationFrontierPolicyDecision
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .causal_foundation_frontier_reconciliation import CausalFoundationFrontierReconciliation
from .causal_foundation_frontier_review import CausalFoundationFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierReviewRow:
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
class CausalFoundationFrontierReviewView:
    fixture_id: str
    rows: tuple[CausalFoundationFrontierReviewRow, ...]
    columns: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def by_decision(self, decision: str) -> tuple[CausalFoundationFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.decision == decision)

    def by_operation(self, operation: str) -> tuple[CausalFoundationFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_csv(self) -> str:
        lines = [",".join(self.columns)]
        for row in self.rows:
            values = row.to_dict(False)
            lines.append(",".join(_csv(values.get(column, "")) for column in self.columns))
        return "\n".join(lines) + "\n"

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "columns": self.columns, "rows": [item.to_dict() for item in self.rows], "row_count": len(self.rows), "content_csv": self.to_csv()}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _csv(value: Any) -> str:
    import csv
    import io

    stream = io.StringIO()
    csv.writer(stream, lineterminator="").writerow([";".join(map(str, value)) if isinstance(value, (tuple, list)) else value])
    return stream.getvalue()


def build_causal_foundation_frontier_review_view(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, decisions: tuple[CausalFoundationFrontierPolicyDecision, ...], reconciliation: CausalFoundationFrontierReconciliation, review: CausalFoundationFrontierReviewQueue) -> CausalFoundationFrontierReviewView:
    decision_map = {item.record_id: item for item in decisions}
    reconciliation_map = {item.record_id: item for item in reconciliation.items}
    review_map = {item.record_id: item for item in review.items}
    rows = tuple(CausalFoundationFrontierReviewRow(record.record_id, record.operation.value, record.role.value, record.expected_state.value, evaluation.by_operation(record.operation.value)[next(index for index, item in enumerate(evaluation.by_operation(record.operation.value)) if item.record_id == record.record_id)].observed_state, tuple(evaluation.by_operation(record.operation.value)[next(index for index, item in enumerate(evaluation.by_operation(record.operation.value)) if item.record_id == record.record_id)].observed_issue_codes), decision_map[record.record_id].decision.value, review_map[record.record_id].priority, reconciliation_map[record.record_id].state_match, reconciliation_map[record.record_id].issue_match, reconciliation_map[record.record_id].accepted, len(record.source_ids)) for record in fixture.records)
    columns = ("record_id", "operation", "role", "expected_state", "observed_state", "issue_codes", "decision", "priority", "state_match", "issue_match", "accepted", "source_count")
    return CausalFoundationFrontierReviewView(fixture.fixture_id, rows, columns)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierSummaryView:
    fixture_id: str
    metrics: CausalFoundationFrontierMetrics
    accepted: bool
    retained_count: int
    review_count: int
    quarantine_count: int
    top_issue_codes: tuple[tuple[str, int], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "metrics": self.metrics.to_dict(), "accepted": self.accepted, "retained_count": self.retained_count, "review_count": self.review_count, "quarantine_count": self.quarantine_count, "top_issue_codes": self.top_issue_codes}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_foundation_frontier_summary_view(fixture: CausalFoundationFrontierFixture, metrics: CausalFoundationFrontierMetrics, review: CausalFoundationFrontierReviewQueue, accepted: bool) -> CausalFoundationFrontierSummaryView:
    top = tuple(sorted(metrics.issue_counts.items(), key=lambda item: (-item[1], item[0])))
    return CausalFoundationFrontierSummaryView(fixture.fixture_id, metrics, accepted, review.retained_count, review.review_count, review.blocked_count, top)


__all__ = ["CausalFoundationFrontierReviewRow", "CausalFoundationFrontierReviewView", "CausalFoundationFrontierSummaryView", "build_causal_foundation_frontier_review_view", "build_causal_foundation_frontier_summary_view"]

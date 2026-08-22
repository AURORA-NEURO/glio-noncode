"""Review-oriented rows for workspace frontier decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_policy import WorkspaceFrontierPolicyDecision
from .workspace_frontier_public_data import WorkspaceFrontierFixture
from .workspace_frontier_release import WorkspaceFrontierReleaseManifest


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReviewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    decision: str
    publishable: bool
    source_count: int
    notes: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierReviewView:
    fixture_id: str
    rows: tuple[WorkspaceFrontierReviewRow, ...]
    release_id: str
    content_address: str

    def accepted_rows(self) -> tuple[WorkspaceFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.publishable)

    def issue_rows(self) -> tuple[WorkspaceFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.issue_codes)

    def by_operation(self, operation: str) -> tuple[WorkspaceFrontierReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_workspace_frontier_review_view(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation, decisions: tuple[WorkspaceFrontierPolicyDecision, ...], release: WorkspaceFrontierReleaseManifest) -> WorkspaceFrontierReviewView:
    source_counts = {record.record_id: len(record.source_ids) for record in fixture.records}
    record_map = fixture.record_map()
    decision_map = {item.record_id: item for item in decisions}
    rows = []
    for execution in evaluation.executions:
        record = record_map[execution.record_id]
        decision = decision_map[execution.record_id]
        body = {
            "record_id": execution.record_id,
            "operation": execution.operation.value,
            "role": execution.role.value,
            "state": execution.state,
            "issue_codes": execution.issue_codes,
            "decision": decision.decision.value,
            "publishable": decision.publishable,
            "source_count": source_counts[record.record_id],
            "notes": record.notes,
        }
        rows.append(WorkspaceFrontierReviewRow(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "rows": tuple(rows), "release_id": release.release_id}
    return WorkspaceFrontierReviewView(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierReviewRow", "WorkspaceFrontierReviewView", "build_workspace_frontier_review_view"]

"""Consumer views over planning executions without losing held states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .planning_frontier_serialization import safe_jsonable
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReviewView:
    view_id: str
    rows: tuple[dict[str, Any], ...]
    counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningSummaryView:
    fixture_id: str
    operation_summaries: tuple[dict[str, Any], ...]
    state_summary: dict[str, int]
    boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_review_view(evaluation: PlanningEvaluation, *, view_id: str = "planning-review-view") -> PlanningReviewView:
    rows = tuple({
        "record_id": item.record_id,
        "operation": item.operation.value,
        "role": item.role.value,
        "state": item.observed_state.value,
        "issue_codes": item.issue_codes,
        "output_keys": tuple(sorted(item.output.keys())),
        "content_address": item.content_address,
    } for item in evaluation.executions)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    accepted = len(rows) == 16 and counts.get("ready_for_review", 0) == 4
    body = {"view_id": view_id, "rows": rows, "counts": counts, "accepted": accepted}
    return PlanningReviewView(view_id, rows, counts, accepted, content_hash(body, prefix="planning-review-view"))


def build_planning_summary_view(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningSummaryView:
    groups: dict[str, list[Any]] = {}
    for item in evaluation.executions:
        groups.setdefault(item.operation.value, []).append(item)
    summaries = tuple({
        "operation": operation,
        "scenario_count": len(rows),
        "ready_count": sum(item.observed_state.value == "ready_for_review" for item in rows),
        "review_count": sum(item.observed_state.value == "review" for item in rows),
        "blocked_count": sum(item.observed_state.value == "blocked" for item in rows),
        "abstained_count": sum(item.observed_state.value == "abstained" for item in rows),
        "issue_codes": tuple(sorted({code for item in rows for code in item.issue_codes})),
    } for operation, rows in sorted(groups.items()))
    state_summary: dict[str, int] = {}
    for item in evaluation.executions:
        state_summary[item.observed_state.value] = state_summary.get(item.observed_state.value, 0) + 1
    body = {"fixture_id": fixture.fixture_id, "operation_summaries": summaries, "state_summary": state_summary, "boundary": fixture.evidence_boundary}
    return PlanningSummaryView(fixture.fixture_id, summaries, state_summary, fixture.evidence_boundary, content_hash(body, prefix="planning-summary-view"))


__all__ = ["PlanningReviewView", "PlanningSummaryView", "build_planning_review_view", "build_planning_summary_view"]

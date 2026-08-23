"""Review urgency and service-level projections for control outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierReviewSlaRow:
    record_id: str
    priority: int
    target_hours: int
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierReviewSla:
    rows: tuple[ControlFrontierReviewSlaRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_control_frontier_review_sla(evaluation: ControlFrontierEvaluation) -> ControlFrontierReviewSla:
    rows = []
    for execution in evaluation.executions:
        priority = 100 if execution.state.value in {"blocked", "out_of_domain", "drift"} else 70 if execution.issue_codes else 20
        body = {"record_id": execution.record_id, "priority": priority, "target_hours": 4 if priority >= 100 else 24 if priority >= 70 else 72, "reasons": execution.issue_codes or ("routine receipt review",)}
        rows.append(ControlFrontierReviewSlaRow(**body, content_address=content_hash(body)))
    return ControlFrontierReviewSla(tuple(rows), len(rows) == len(evaluation.executions), content_hash(tuple(rows)))


__all__ = ["ControlFrontierReviewSla", "ControlFrontierReviewSlaRow", "build_control_frontier_review_sla"]

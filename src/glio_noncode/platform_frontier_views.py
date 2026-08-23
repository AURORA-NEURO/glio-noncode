"""Stable review projection for platform executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierReviewEntry:
    record_id: str
    role: PlatformFrontierRole
    operation: str
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    review_required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierView:
    fixture_id: str
    entries: tuple[PlatformFrontierReviewEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_view(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierView:
    entries = []
    for row in evaluation.executions:
        body = {"record_id": row.record_id, "role": row.role, "operation": row.operation.value, "state": row.state.value, "accepted": row.accepted, "issue_codes": row.issue_codes, "review_required": row.role is PlatformFrontierRole.CONTROL or bool(row.issue_codes)}
        entries.append(PlatformFrontierReviewEntry(**body, content_address=content_hash(body)))
    return PlatformFrontierView(evaluation.fixture_id, tuple(entries), len(entries) == len(evaluation.executions), content_hash(tuple(entries)))


def platform_frontier_review_summary(view: PlatformFrontierView) -> dict[str, Any]:
    return {"fixture_id": view.fixture_id, "entry_count": len(view.entries), "review_count": sum(item.review_required for item in view.entries), "accepted_count": sum(item.accepted for item in view.entries), "control_count": sum(item.role is PlatformFrontierRole.CONTROL for item in view.entries)}


__all__ = ["PlatformFrontierReviewEntry", "PlatformFrontierView", "build_platform_frontier_view", "platform_frontier_review_summary"]

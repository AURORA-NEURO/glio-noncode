"""Sanitized review views that retain positive and control rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    SequenceEffectRole,
    SequenceEffectState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectReviewEntry:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    priority: int
    action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectOperationView:
    operation: str
    record_ids: tuple[str, ...]
    accepted_count: int
    review_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectView:
    fixture_id: str
    context_key: str
    entries: tuple[SequenceEffectReviewEntry, ...]
    operation_views: tuple[SequenceEffectOperationView, ...]
    source_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "context_key": self.context_key,
                        "entries": self.entries,
                        "operation_views": self.operation_views,
                        "source_ids": self.source_ids,
                        "accepted": self.accepted,
                    }
                ),
            )

    @property
    def review_count(self) -> int:
        return sum(item.priority > 0 for item in self.entries)

    @property
    def accepted_record_ids(self) -> tuple[str, ...]:
        return tuple(
            item.record_id
            for item in self.entries
            if item.state in {SequenceEffectState.SUPPORTED.value}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "context_key": self.context_key,
            "accepted": self.accepted,
            "review_count": self.review_count,
            "accepted_record_ids": list(self.accepted_record_ids),
            "entries": [item.to_dict() for item in self.entries],
            "operation_views": [item.to_dict() for item in self.operation_views],
            "source_ids": list(self.source_ids),
            "content_address": self.content_address,
        }


def _priority(role: SequenceEffectRole, state: SequenceEffectState) -> tuple[int, str]:
    if role is SequenceEffectRole.POSITIVE and state is SequenceEffectState.SUPPORTED:
        return 0, "retain-research-view"
    if state is SequenceEffectState.ABSTAINED:
        return 3, "supply-missing-input"
    if state is SequenceEffectState.INVALID:
        return 3, "repair-invalid-row"
    return 2, "review-effect-boundary"


def build_sequence_effect_view(
    fixture: SequenceEffectFixture, evaluation: SequenceEffectEvaluation
) -> SequenceEffectView:
    entries = tuple(
        SequenceEffectReviewEntry(
            item.record_id,
            item.operation.value,
            item.role.value,
            item.adapter_state.value,
            item.issue_codes,
            *_priority(item.role, item.adapter_state),
            item.content_address,
        )
        for item in evaluation.executions
    )
    operations = []
    for operation in sorted({item.operation.value for item in evaluation.executions}):
        rows = tuple(item for item in entries if item.operation == operation)
        operations.append(
            SequenceEffectOperationView(
                operation,
                tuple(item.record_id for item in rows),
                sum(item.priority == 0 for item in rows),
                sum(item.priority > 0 for item in rows),
                content_hash(
                    {"operation": operation, "record_ids": tuple(item.record_id for item in rows)}
                ),
            )
        )
    return SequenceEffectView(
        fixture.fixture_id,
        fixture.context_key,
        entries,
        tuple(operations),
        tuple(source.source_id for source in fixture.sources),
        True,
    )


def filter_sequence_effect_review_queue(
    view: SequenceEffectView,
    *,
    maximum_priority: int | None = None,
    operations: tuple[str, ...] = (),
) -> tuple[SequenceEffectReviewEntry, ...]:
    return tuple(
        item
        for item in view.entries
        if item.priority > 0
        and (maximum_priority is None or item.priority <= maximum_priority)
        and (not operations or item.operation in operations)
    )


def sequence_effect_review_summary(view: SequenceEffectView) -> dict[str, Any]:
    return {
        "fixture_id": view.fixture_id,
        "review_count": view.review_count,
        "accepted_count": len(view.accepted_record_ids),
        "by_operation": {item.operation: item.review_count for item in view.operation_views},
        "content_address": content_hash(
            {
                "fixture_id": view.fixture_id,
                "review_count": view.review_count,
                "accepted_count": len(view.accepted_record_ids),
            }
        ),
    }


__all__ = [
    "SequenceEffectOperationView",
    "SequenceEffectReviewEntry",
    "SequenceEffectView",
    "build_sequence_effect_view",
    "filter_sequence_effect_review_queue",
    "sequence_effect_review_summary",
]

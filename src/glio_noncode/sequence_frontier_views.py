"""Review and source-participation views for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import (
    SequenceFrontierEvaluationReport,
    SequenceFrontierExecutionReceipt,
)
from .sequence_frontier_public_data import (
    SequenceFrontierFixture,
    SequenceFrontierOperation,
    SequenceFrontierRole,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierReviewEntry:
    record_id: str
    operation: SequenceFrontierOperation
    role: SequenceFrontierRole
    state: str
    issue_codes: tuple[str, ...]
    context_key: str
    priority: int
    action: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "state", "context_key", "action", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"is_review": self.state not in {"accepted", "published"}}


@dataclass(frozen=True, slots=True)
class SequenceFrontierOperationView:
    operation: SequenceFrontierOperation
    record_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    state_counts: tuple[tuple[str, int], ...]
    review_record_ids: tuple[str, ...]
    issue_count: int
    content_address: str

    @property
    def review_count(self) -> int:
        return len(self.review_record_ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_count": self.review_count}


@dataclass(frozen=True, slots=True)
class SequenceFrontierSourceMatrixRow:
    source_id: str
    record_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]
    positive_record_ids: tuple[str, ...]
    control_record_ids: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.source_id, "source_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierView:
    fixture_id: str
    context_key: str
    operation_views: tuple[SequenceFrontierOperationView, ...]
    review_queue: tuple[SequenceFrontierReviewEntry, ...]
    source_matrix: tuple[SequenceFrontierSourceMatrixRow, ...]
    accepted_record_ids: tuple[str, ...]
    published_record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.operation_views) and all(
            item.context_key == self.context_key for item in self.review_queue
        )

    @property
    def review_count(self) -> int:
        return len(self.review_queue)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "review_count": self.review_count}


def _priority(receipt: SequenceFrontierExecutionReceipt) -> int:
    return {"out_of_domain": 4, "invalid": 4, "review": 2, "abstained": 1}.get(
        receipt.adapter_state, 0
    )


def _action(receipt: SequenceFrontierExecutionReceipt) -> str:
    return {
        "out_of_domain": "verify_context_before_reuse",
        "invalid": "repair_metadata_or_quarantine",
        "review": "retain_uncertainty_for_adjudication",
        "abstained": "record_absence_without_negative_inference",
        "accepted": "no_review_action",
        "published": "no_review_action",
    }.get(receipt.adapter_state, "inspect_state")


def build_sequence_frontier_view(
    fixture: SequenceFrontierFixture, evaluation: SequenceFrontierEvaluationReport
) -> SequenceFrontierView:
    receipts = evaluation.receipts
    operation_views: list[SequenceFrontierOperationView] = []
    for operation in SequenceFrontierOperation:
        rows = tuple(item for item in receipts if item.operation is operation)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.adapter_state] = counts.get(row.adapter_state, 0) + 1
        body = {
            "operation": operation,
            "record_ids": tuple(item.record_id for item in rows),
            "positive_count": sum(item.role is SequenceFrontierRole.POSITIVE for item in rows),
            "control_count": sum(item.role is SequenceFrontierRole.CONTROL for item in rows),
            "state_counts": tuple(sorted(counts.items())),
            "review_record_ids": tuple(
                item.record_id
                for item in rows
                if item.adapter_state not in {"accepted", "published"}
            ),
            "issue_count": sum(bool(item.observed_issue_codes) for item in rows),
        }
        operation_views.append(
            SequenceFrontierOperationView(**body, content_address=content_hash(body))
        )
    queue: list[SequenceFrontierReviewEntry] = []
    for receipt in receipts:
        if receipt.adapter_state in {"accepted", "published"}:
            continue
        body = {
            "record_id": receipt.record_id,
            "operation": receipt.operation,
            "role": receipt.role,
            "state": receipt.adapter_state,
            "issue_codes": receipt.observed_issue_codes,
            "context_key": receipt.context_key,
            "priority": _priority(receipt),
            "action": _action(receipt),
        }
        queue.append(SequenceFrontierReviewEntry(**body, content_address=content_hash(body)))
    queue.sort(key=lambda item: (-item.priority, item.record_id))
    source_matrix: list[SequenceFrontierSourceMatrixRow] = []
    for source in fixture.sources:
        source_records = tuple(
            item for item in fixture.records if source.source_id in item.source_ids
        )
        body = {
            "source_id": source.source_id,
            "record_ids": tuple(item.record_id for item in source_records),
            "operation_ids": tuple(dict.fromkeys(item.operation.value for item in source_records)),
            "positive_record_ids": tuple(
                item.record_id
                for item in source_records
                if item.role is SequenceFrontierRole.POSITIVE
            ),
            "control_record_ids": tuple(
                item.record_id
                for item in source_records
                if item.role is SequenceFrontierRole.CONTROL
            ),
        }
        source_matrix.append(
            SequenceFrontierSourceMatrixRow(**body, content_address=content_hash(body))
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "operation_views": operation_views,
        "review_queue": queue,
        "source_matrix": source_matrix,
        "accepted_record_ids": tuple(
            item.record_id for item in receipts if item.adapter_state == "accepted"
        ),
        "published_record_ids": tuple(
            item.record_id for item in receipts if item.adapter_state == "published"
        ),
    }
    return SequenceFrontierView(**body, content_address=content_hash(body))


def filter_sequence_frontier_review_queue(
    view: SequenceFrontierView,
    *,
    operation: SequenceFrontierOperation | None = None,
    minimum_priority: int = 0,
    states: tuple[str, ...] = (),
) -> tuple[SequenceFrontierReviewEntry, ...]:
    if minimum_priority < 0:
        raise ValueError("minimum review priority cannot be negative")
    return tuple(
        item
        for item in view.review_queue
        if (operation is None or item.operation is operation)
        and item.priority >= minimum_priority
        and (not states or item.state in states)
    )


def sequence_frontier_review_summary(view: SequenceFrontierView) -> dict[str, Any]:
    states: dict[str, int] = {}
    operations: dict[str, int] = {}
    for item in view.review_queue:
        states[item.state] = states.get(item.state, 0) + 1
        operations[item.operation.value] = operations.get(item.operation.value, 0) + 1
    body = {
        "fixture_id": view.fixture_id,
        "context_key": view.context_key,
        "review_count": view.review_count,
        "accepted_count": len(view.accepted_record_ids),
        "published_count": len(view.published_record_ids),
        "by_state": dict(sorted(states.items())),
        "by_operation": dict(sorted(operations.items())),
    }
    return body | {"content_address": content_hash(body)}


__all__ = [
    "SequenceFrontierOperationView",
    "SequenceFrontierReviewEntry",
    "SequenceFrontierSourceMatrixRow",
    "SequenceFrontierView",
    "build_sequence_frontier_view",
    "filter_sequence_frontier_review_queue",
    "sequence_frontier_review_summary",
]

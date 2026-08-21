"""Review queue and source participation views for C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_fixture_eval import (
    FrontierAtlasEvaluationReport,
    FrontierAtlasExecutionReceipt,
)
from .frontier_atlas_public_data import (
    FrontierAtlasFixture,
    FrontierAtlasOperation,
    FrontierAtlasRole,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasReviewEntry:
    record_id: str
    operation: FrontierAtlasOperation
    role: FrontierAtlasRole
    state: str
    issue_codes: tuple[str, ...]
    context_key: str
    priority: int
    action: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "state", "context_key", "action", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.priority < 0:
            raise ValueError("review priority cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"is_review": self.state not in {"accepted", "published"}}


@dataclass(frozen=True, slots=True)
class FrontierAtlasOperationView:
    operation: FrontierAtlasOperation
    record_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    state_counts: tuple[tuple[str, int], ...]
    review_record_ids: tuple[str, ...]
    issue_count: int
    content_address: str

    @property
    def accepted_count(self) -> int:
        return dict(self.state_counts).get("accepted", 0)

    @property
    def published_count(self) -> int:
        return dict(self.state_counts).get("published", 0)

    @property
    def review_count(self) -> int:
        return len(self.review_record_ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted_count": self.accepted_count,
            "published_count": self.published_count,
            "review_count": self.review_count,
        }


@dataclass(frozen=True, slots=True)
class FrontierAtlasSourceMatrixRow:
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
class FrontierAtlasView:
    fixture_id: str
    context_key: str
    operation_views: tuple[FrontierAtlasOperationView, ...]
    review_queue: tuple[FrontierAtlasReviewEntry, ...]
    source_matrix: tuple[FrontierAtlasSourceMatrixRow, ...]
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


def _priority(receipt: FrontierAtlasExecutionReceipt) -> int:
    return {"out_of_domain": 4, "invalid": 4, "review": 2, "abstained": 1}.get(
        receipt.adapter_state, 0
    )


def _action(receipt: FrontierAtlasExecutionReceipt) -> str:
    return {
        "out_of_domain": "verify_context_before_reuse",
        "invalid": "repair_metadata_or_quarantine",
        "review": "retain_evidence_for_adjudication",
        "abstained": "record_absence_without_negative_inference",
        "accepted": "no_review_action",
        "published": "no_review_action",
    }.get(receipt.adapter_state, "inspect_state")


def _entry(receipt: FrontierAtlasExecutionReceipt) -> FrontierAtlasReviewEntry:
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
    return FrontierAtlasReviewEntry(**body, content_address=content_hash(body))


def _operation_view(
    operation: FrontierAtlasOperation, receipts: tuple[FrontierAtlasExecutionReceipt, ...]
) -> FrontierAtlasOperationView:
    counts: dict[str, int] = {}
    for receipt in receipts:
        counts[receipt.adapter_state] = counts.get(receipt.adapter_state, 0) + 1
    body = {
        "operation": operation,
        "record_ids": tuple(item.record_id for item in receipts),
        "positive_count": sum(item.role is FrontierAtlasRole.POSITIVE for item in receipts),
        "control_count": sum(item.role is FrontierAtlasRole.CONTROL for item in receipts),
        "state_counts": tuple(sorted(counts.items())),
        "review_record_ids": tuple(
            item.record_id
            for item in receipts
            if item.adapter_state not in {"accepted", "published"}
        ),
        "issue_count": sum(bool(item.observed_issue_codes) for item in receipts),
    }
    return FrontierAtlasOperationView(**body, content_address=content_hash(body))


def build_frontier_atlas_view(
    fixture: FrontierAtlasFixture, evaluation: FrontierAtlasEvaluationReport
) -> FrontierAtlasView:
    receipts = evaluation.receipts
    operation_views = tuple(
        _operation_view(operation, tuple(item for item in receipts if item.operation is operation))
        for operation in FrontierAtlasOperation
    )
    queue = tuple(
        sorted(
            (
                _entry(item)
                for item in receipts
                if item.adapter_state not in {"accepted", "published"}
            ),
            key=lambda item: (-item.priority, item.record_id),
        )
    )
    source_matrix: list[FrontierAtlasSourceMatrixRow] = []
    for source in fixture.sources:
        records = tuple(
            record for record in fixture.records if source.source_id in record.source_ids
        )
        body = {
            "source_id": source.source_id,
            "record_ids": tuple(record.record_id for record in records),
            "operation_ids": tuple(dict.fromkeys(record.operation.value for record in records)),
            "positive_record_ids": tuple(
                record.record_id for record in records if record.role is FrontierAtlasRole.POSITIVE
            ),
            "control_record_ids": tuple(
                record.record_id for record in records if record.role is FrontierAtlasRole.CONTROL
            ),
        }
        source_matrix.append(
            FrontierAtlasSourceMatrixRow(**body, content_address=content_hash(body))
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "operation_views": operation_views,
        "review_queue": queue,
        "source_matrix": tuple(source_matrix),
        "accepted_record_ids": tuple(
            item.record_id for item in receipts if item.adapter_state == "accepted"
        ),
        "published_record_ids": tuple(
            item.record_id for item in receipts if item.adapter_state == "published"
        ),
    }
    return FrontierAtlasView(**body, content_address=content_hash(body))


def filter_frontier_atlas_review_queue(
    view: FrontierAtlasView,
    *,
    operation: FrontierAtlasOperation | None = None,
    minimum_priority: int = 0,
    states: tuple[str, ...] = (),
) -> tuple[FrontierAtlasReviewEntry, ...]:
    if minimum_priority < 0:
        raise ValueError("minimum review priority cannot be negative")
    return tuple(
        item
        for item in view.review_queue
        if (operation is None or item.operation is operation)
        and item.priority >= minimum_priority
        and (not states or item.state in states)
    )


def frontier_atlas_review_summary(view: FrontierAtlasView) -> dict[str, Any]:
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
    "FrontierAtlasOperationView",
    "FrontierAtlasReviewEntry",
    "FrontierAtlasSourceMatrixRow",
    "FrontierAtlasView",
    "build_frontier_atlas_view",
    "filter_frontier_atlas_review_queue",
    "frontier_atlas_review_summary",
]

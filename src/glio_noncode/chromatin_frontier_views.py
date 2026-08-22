"""Review and source-matrix views for Domain 07 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_frontier_fixture_eval import (
    ChromatinFrontierEvaluationReport,
    ChromatinFrontierExecutionReceipt,
)
from .chromatin_frontier_public_data import (
    ChromatinFrontierFixture,
    ChromatinFrontierOperation,
    ChromatinFrontierRole,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ChromatinFrontierReviewEntry:
    record_id: str
    operation: ChromatinFrontierOperation
    role: ChromatinFrontierRole
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
        return jsonable(self) | {"is_review": self.state not in {"supported"}}


@dataclass(frozen=True, slots=True)
class ChromatinFrontierOperationView:
    operation: ChromatinFrontierOperation
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
class ChromatinFrontierSourceMatrixRow:
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
class ChromatinFrontierView:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    operation_views: tuple[ChromatinFrontierOperationView, ...]
    review_queue: tuple[ChromatinFrontierReviewEntry, ...]
    source_matrix: tuple[ChromatinFrontierSourceMatrixRow, ...]
    accepted_record_ids: tuple[str, ...]
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


def _priority(receipt: ChromatinFrontierExecutionReceipt) -> int:
    return {"out_of_domain": 4, "invalid": 4, "ambiguous": 3, "partial": 2, "abstained": 1}.get(
        receipt.adapter_state, 0
    )


def _action(receipt: ChromatinFrontierExecutionReceipt) -> str:
    return {
        "out_of_domain": "verify_context_before_reuse",
        "invalid": "repair_metadata_or_quarantine",
        "ambiguous": "retain_replicate_disagreement_for_review",
        "partial": "retain_missing_assay_terms_for_review",
        "abstained": "record_missing_reference_without_inference",
        "supported": "no_review_action",
    }.get(receipt.adapter_state, "inspect_state")


def build_chromatin_frontier_view(
    fixture: ChromatinFrontierFixture,
    evaluation: ChromatinFrontierEvaluationReport,
) -> ChromatinFrontierView:
    receipts = evaluation.receipts
    operation_views: list[ChromatinFrontierOperationView] = []
    for operation in ChromatinFrontierOperation:
        rows = tuple(item for item in receipts if item.operation is operation)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.adapter_state] = counts.get(row.adapter_state, 0) + 1
        body = {
            "operation": operation,
            "record_ids": tuple(item.record_id for item in rows),
            "positive_count": sum(item.role is ChromatinFrontierRole.POSITIVE for item in rows),
            "control_count": sum(item.role is ChromatinFrontierRole.CONTROL for item in rows),
            "state_counts": tuple(sorted(counts.items())),
            "review_record_ids": tuple(
                item.record_id for item in rows if item.adapter_state != "supported"
            ),
            "issue_count": sum(bool(item.observed_issue_codes) for item in rows),
        }
        operation_views.append(
            ChromatinFrontierOperationView(**body, content_address=content_hash(body))
        )
    queue: list[ChromatinFrontierReviewEntry] = []
    for receipt in receipts:
        if receipt.adapter_state == "supported":
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
        queue.append(ChromatinFrontierReviewEntry(**body, content_address=content_hash(body)))
    queue.sort(key=lambda item: (-item.priority, item.record_id))
    source_matrix: list[ChromatinFrontierSourceMatrixRow] = []
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
                if item.role is ChromatinFrontierRole.POSITIVE
            ),
            "control_record_ids": tuple(
                item.record_id
                for item in source_records
                if item.role is ChromatinFrontierRole.CONTROL
            ),
        }
        source_matrix.append(
            ChromatinFrontierSourceMatrixRow(**body, content_address=content_hash(body))
        )
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "operation_views": operation_views,
        "review_queue": queue,
        "source_matrix": source_matrix,
        "accepted_record_ids": tuple(
            item.record_id for item in receipts if item.adapter_state == "supported"
        ),
    }
    return ChromatinFrontierView(
        fixture.fixture_id,
        fixture.context_key,
        fixture.evidence_boundary,
        tuple(operation_views),
        tuple(queue),
        tuple(source_matrix),
        body["accepted_record_ids"],
        content_hash(body),
    )


def filter_chromatin_frontier_review_queue(
    view: ChromatinFrontierView,
    *,
    states: tuple[str, ...] | None = None,
    operations: tuple[ChromatinFrontierOperation, ...] | None = None,
    maximum_priority: int | None = None,
) -> tuple[ChromatinFrontierReviewEntry, ...]:
    return tuple(
        item
        for item in view.review_queue
        if (states is None or item.state in states)
        and (operations is None or item.operation in operations)
        and (maximum_priority is None or item.priority <= maximum_priority)
    )


def chromatin_frontier_review_summary(view: ChromatinFrontierView) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    operation_counts: dict[str, int] = {}
    for item in view.review_queue:
        state_counts[item.state] = state_counts.get(item.state, 0) + 1
        operation_counts[item.operation.value] = operation_counts.get(item.operation.value, 0) + 1
    body = {
        "fixture_id": view.fixture_id,
        "review_count": len(view.review_queue),
        "state_counts": tuple(sorted(state_counts.items())),
        "operation_counts": tuple(sorted(operation_counts.items())),
        "source_count": len(view.source_matrix),
    }
    return body | {"content_address": content_hash(body)}


__all__ = [
    "ChromatinFrontierOperationView",
    "ChromatinFrontierReviewEntry",
    "ChromatinFrontierSourceMatrixRow",
    "ChromatinFrontierView",
    "build_chromatin_frontier_view",
    "chromatin_frontier_review_summary",
    "filter_chromatin_frontier_review_queue",
]

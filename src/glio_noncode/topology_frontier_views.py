"""Review and source-matrix views for Domain 09 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .topology_frontier_fixture_eval import (
    TopologyFrontierEvaluationReport,
    TopologyFrontierExecutionReceipt,
)
from .topology_frontier_public_data import (
    TopologyFrontierFixture,
    TopologyFrontierOperation,
    TopologyFrontierRole,
)


@dataclass(frozen=True, slots=True)
class TopologyFrontierReviewEntry:
    record_id: str
    operation: TopologyFrontierOperation
    role: TopologyFrontierRole
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
        return jsonable(self) | {"is_review": self.state != "supported"}


@dataclass(frozen=True, slots=True)
class TopologyFrontierOperationView:
    operation: TopologyFrontierOperation
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
class TopologyFrontierSourceMatrixRow:
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
class TopologyFrontierView:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    operation_views: tuple[TopologyFrontierOperationView, ...]
    review_queue: tuple[TopologyFrontierReviewEntry, ...]
    source_matrix: tuple[TopologyFrontierSourceMatrixRow, ...]
    accepted_record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.operation_views) and all(item.context_key == self.context_key for item in self.review_queue)

    @property
    def review_count(self) -> int:
        return len(self.review_queue)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "review_count": self.review_count}


def _priority(receipt: TopologyFrontierExecutionReceipt) -> int:
    return {"out_of_domain": 4, "invalid": 4, "partial": 2, "abstained": 1}.get(receipt.adapter_state, 0)


def _action(receipt: TopologyFrontierExecutionReceipt) -> str:
    return {"out_of_domain": "verify_exact_context_before_reuse", "invalid": "repair_row_or_quarantine", "partial": "retain_uncertainty_for_review", "supported": "no_review_action"}.get(receipt.adapter_state, "inspect_state")


def build_topology_frontier_view(fixture: TopologyFrontierFixture, evaluation: TopologyFrontierEvaluationReport) -> TopologyFrontierView:
    operation_views: list[TopologyFrontierOperationView] = []
    for operation in TopologyFrontierOperation:
        rows = tuple(item for item in evaluation.receipts if item.operation is operation)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.adapter_state] = counts.get(row.adapter_state, 0) + 1
        body = {"operation": operation, "record_ids": tuple(item.record_id for item in rows), "positive_count": sum(item.role is TopologyFrontierRole.POSITIVE for item in rows), "control_count": sum(item.role is TopologyFrontierRole.CONTROL for item in rows), "state_counts": tuple(sorted(counts.items())), "review_record_ids": tuple(item.record_id for item in rows if item.adapter_state != "supported"), "issue_count": sum(bool(item.observed_issue_codes) for item in rows)}
        operation_views.append(TopologyFrontierOperationView(**body, content_address=content_hash(body)))
    queue: list[TopologyFrontierReviewEntry] = []
    for receipt in evaluation.receipts:
        if receipt.adapter_state == "supported":
            continue
        body = {"record_id": receipt.record_id, "operation": receipt.operation, "role": receipt.role, "state": receipt.adapter_state, "issue_codes": receipt.observed_issue_codes, "context_key": receipt.context_key, "priority": _priority(receipt), "action": _action(receipt)}
        queue.append(TopologyFrontierReviewEntry(**body, content_address=content_hash(body)))
    queue.sort(key=lambda item: (-item.priority, item.record_id))
    matrix: list[TopologyFrontierSourceMatrixRow] = []
    for source in fixture.sources:
        rows = tuple(item for item in fixture.records if source.source_id in item.source_ids)
        body = {"source_id": source.source_id, "record_ids": tuple(item.record_id for item in rows), "operation_ids": tuple(dict.fromkeys(item.operation.value for item in rows)), "positive_record_ids": tuple(item.record_id for item in rows if item.role is TopologyFrontierRole.POSITIVE), "control_record_ids": tuple(item.record_id for item in rows if item.role is TopologyFrontierRole.CONTROL)}
        matrix.append(TopologyFrontierSourceMatrixRow(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "context_key": fixture.context_key, "evidence_boundary": fixture.evidence_boundary, "operation_views": operation_views, "review_queue": queue, "source_matrix": matrix, "accepted_record_ids": tuple(item.record_id for item in evaluation.receipts if item.adapter_state == "supported")}
    return TopologyFrontierView(fixture.fixture_id, fixture.context_key, fixture.evidence_boundary, tuple(operation_views), tuple(queue), tuple(matrix), body["accepted_record_ids"], content_hash(body))


def filter_topology_frontier_review_queue(view: TopologyFrontierView, *, states: tuple[str, ...] | None = None, operations: tuple[TopologyFrontierOperation, ...] | None = None, maximum_priority: int | None = None) -> tuple[TopologyFrontierReviewEntry, ...]:
    return tuple(item for item in view.review_queue if (states is None or item.state in states) and (operations is None or item.operation in operations) and (maximum_priority is None or item.priority <= maximum_priority))


def topology_frontier_review_summary(view: TopologyFrontierView) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    operation_counts: dict[str, int] = {}
    for item in view.review_queue:
        state_counts[item.state] = state_counts.get(item.state, 0) + 1
        operation_counts[item.operation.value] = operation_counts.get(item.operation.value, 0) + 1
    body = {"fixture_id": view.fixture_id, "review_count": len(view.review_queue), "state_counts": tuple(sorted(state_counts.items())), "operation_counts": tuple(sorted(operation_counts.items())), "source_count": len(view.source_matrix)}
    return body | {"content_address": content_hash(body)}


__all__ = [
    "TopologyFrontierOperationView",
    "TopologyFrontierReviewEntry",
    "TopologyFrontierSourceMatrixRow",
    "TopologyFrontierView",
    "build_topology_frontier_view",
    "filter_topology_frontier_review_queue",
    "topology_frontier_review_summary",
]

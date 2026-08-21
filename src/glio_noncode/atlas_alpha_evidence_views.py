"""Review-oriented views over the C09-C12 evidence receipts.

These views deliberately operate on sanitized receipts rather than fixture
payloads. They make the review queue, operation balance, and source closure
visible without introducing a second interpretation layer over the adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import (
    AtlasAlphaEvidenceEvaluationReport,
    AtlasAlphaEvidenceExecutionReceipt,
)
from .atlas_alpha_evidence_public_data import (
    AtlasAlphaEvidenceFixture,
    AtlasAlphaEvidenceOperation,
    AtlasAlphaEvidenceRole,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceReviewEntry:
    """One actionable review row with preserved ambiguity."""

    record_id: str
    operation: AtlasAlphaEvidenceOperation
    role: AtlasAlphaEvidenceRole
    state: str
    issue_codes: tuple[str, ...]
    context_key: str
    priority: int
    action: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.state, "state")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.action, "action")
        if self.priority < 0:
            raise ValueError("review priority cannot be negative")

    @property
    def is_review(self) -> bool:
        return self.state != "supported"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"is_review": self.is_review}


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceOperationView:
    """One operation's counts and review record IDs."""

    operation: AtlasAlphaEvidenceOperation
    record_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    state_counts: tuple[tuple[str, int], ...]
    review_record_ids: tuple[str, ...]
    issue_count: int
    content_address: str

    def __post_init__(self) -> None:
        if self.positive_count < 0 or self.control_count < 0 or self.issue_count < 0:
            raise ValueError("operation view counts cannot be negative")

    @property
    def supported_count(self) -> int:
        return dict(self.state_counts).get("supported", 0)

    @property
    def review_count(self) -> int:
        return len(self.review_record_ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "supported_count": self.supported_count,
            "review_count": self.review_count,
        }


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceSourceMatrixRow:
    """One public source's receipt participation matrix."""

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
class AtlasAlphaEvidenceView:
    """Complete sanitized review view."""

    fixture_id: str
    context_key: str
    operation_views: tuple[AtlasAlphaEvidenceOperationView, ...]
    review_queue: tuple[AtlasAlphaEvidenceReviewEntry, ...]
    source_matrix: tuple[AtlasAlphaEvidenceSourceMatrixRow, ...]
    supported_record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.operation_views) and not any(
            item.context_key != self.context_key for item in self.review_queue
        )

    @property
    def review_count(self) -> int:
        return len(self.review_queue)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "review_count": self.review_count}


def _priority(receipt: AtlasAlphaEvidenceExecutionReceipt) -> int:
    if receipt.adapter_state == "out_of_domain":
        return 4
    if receipt.adapter_state == "ambiguous":
        return 3
    if receipt.adapter_state == "invalid":
        return 3
    if receipt.adapter_state == "partial":
        return 2
    if receipt.adapter_state == "abstained":
        return 1
    return 0


def _action(receipt: AtlasAlphaEvidenceExecutionReceipt) -> str:
    if receipt.adapter_state == "out_of_domain":
        return "verify_context_before_reuse"
    if receipt.adapter_state == "ambiguous":
        return "retain_competing_evidence_for_review"
    if receipt.adapter_state == "invalid":
        return "repair_input_row_or_quarantine"
    if receipt.adapter_state == "partial":
        return "request_missing_channel_or_coverage"
    if receipt.adapter_state == "abstained":
        return "record_absence_without_negative_inference"
    return "no_review_action"


def _entry(receipt: AtlasAlphaEvidenceExecutionReceipt) -> AtlasAlphaEvidenceReviewEntry:
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
    return AtlasAlphaEvidenceReviewEntry(**body, content_address=content_hash(body))


def _operation_view(
    operation: AtlasAlphaEvidenceOperation, receipts: tuple[AtlasAlphaEvidenceExecutionReceipt, ...]
) -> AtlasAlphaEvidenceOperationView:
    states: dict[str, int] = {}
    for receipt in receipts:
        states[receipt.adapter_state] = states.get(receipt.adapter_state, 0) + 1
    review_ids = tuple(
        receipt.record_id for receipt in receipts if receipt.adapter_state != "supported"
    )
    body = {
        "operation": operation,
        "record_ids": tuple(item.record_id for item in receipts),
        "positive_count": sum(item.role is AtlasAlphaEvidenceRole.POSITIVE for item in receipts),
        "control_count": sum(item.role is AtlasAlphaEvidenceRole.CONTROL for item in receipts),
        "state_counts": tuple(sorted(states.items())),
        "review_record_ids": review_ids,
        "issue_count": sum(bool(item.observed_issue_codes) for item in receipts),
    }
    return AtlasAlphaEvidenceOperationView(**body, content_address=content_hash(body))


def _source_matrix(
    fixture: AtlasAlphaEvidenceFixture,
) -> tuple[AtlasAlphaEvidenceSourceMatrixRow, ...]:
    rows: list[AtlasAlphaEvidenceSourceMatrixRow] = []
    for source in fixture.sources:
        records = tuple(
            record for record in fixture.records if source.source_id in record.source_ids
        )
        body = {
            "source_id": source.source_id,
            "record_ids": tuple(record.record_id for record in records),
            "operation_ids": tuple(dict.fromkeys(record.operation.value for record in records)),
            "positive_record_ids": tuple(
                record.record_id
                for record in records
                if record.role is AtlasAlphaEvidenceRole.POSITIVE
            ),
            "control_record_ids": tuple(
                record.record_id
                for record in records
                if record.role is AtlasAlphaEvidenceRole.CONTROL
            ),
        }
        rows.append(AtlasAlphaEvidenceSourceMatrixRow(**body, content_address=content_hash(body)))
    return tuple(rows)


def build_atlas_alpha_evidence_view(
    fixture: AtlasAlphaEvidenceFixture, evaluation: AtlasAlphaEvidenceEvaluationReport
) -> AtlasAlphaEvidenceView:
    """Build the deterministic operation and review view."""

    receipts = evaluation.receipts
    operation_views = tuple(
        _operation_view(operation, tuple(item for item in receipts if item.operation is operation))
        for operation in AtlasAlphaEvidenceOperation
    )
    entries = tuple(
        sorted(
            (_entry(receipt) for receipt in receipts if receipt.adapter_state != "supported"),
            key=lambda item: (-item.priority, item.record_id),
        )
    )
    source_matrix = _source_matrix(fixture)
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "operation_views": operation_views,
        "review_queue": entries,
        "source_matrix": source_matrix,
        "supported_record_ids": tuple(
            item.record_id for item in receipts if item.adapter_state == "supported"
        ),
    }
    return AtlasAlphaEvidenceView(**body, content_address=content_hash(body))


def filter_atlas_alpha_evidence_review_queue(
    view: AtlasAlphaEvidenceView,
    *,
    operation: AtlasAlphaEvidenceOperation | None = None,
    minimum_priority: int = 0,
    states: tuple[str, ...] = (),
) -> tuple[AtlasAlphaEvidenceReviewEntry, ...]:
    """Filter review entries without changing their order or meaning."""

    if minimum_priority < 0:
        raise ValueError("minimum review priority cannot be negative")
    return tuple(
        item
        for item in view.review_queue
        if (operation is None or item.operation is operation)
        and item.priority >= minimum_priority
        and (not states or item.state in states)
    )


def review_queue_summary(view: AtlasAlphaEvidenceView) -> dict[str, Any]:
    """Return counts suitable for a dashboard or release receipt."""

    by_state: dict[str, int] = {}
    by_operation: dict[str, int] = {}
    for item in view.review_queue:
        by_state[item.state] = by_state.get(item.state, 0) + 1
        by_operation[item.operation.value] = by_operation.get(item.operation.value, 0) + 1
    return {
        "fixture_id": view.fixture_id,
        "context_key": view.context_key,
        "review_count": len(view.review_queue),
        "supported_count": len(view.supported_record_ids),
        "by_state": dict(sorted(by_state.items())),
        "by_operation": dict(sorted(by_operation.items())),
        "highest_priority": max((item.priority for item in view.review_queue), default=0),
        "content_address": content_hash(
            {
                "fixture_id": view.fixture_id,
                "context_key": view.context_key,
                "review_count": len(view.review_queue),
                "supported_count": len(view.supported_record_ids),
                "by_state": dict(sorted(by_state.items())),
                "by_operation": dict(sorted(by_operation.items())),
            }
        ),
    }


__all__ = [
    "AtlasAlphaEvidenceOperationView",
    "AtlasAlphaEvidenceReviewEntry",
    "AtlasAlphaEvidenceSourceMatrixRow",
    "AtlasAlphaEvidenceView",
    "build_atlas_alpha_evidence_view",
    "filter_atlas_alpha_evidence_review_queue",
    "review_queue_summary",
]

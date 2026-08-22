"""Expected-versus-observed reconciliation for context operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValidationError("reconciliation row needs an ID")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierReconciliation:
    items: tuple[ChromatinContextFrontierReconciliationItem, ...]
    accepted: bool
    matched_count: int
    mismatch_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValidationError("reconciliation requires items")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation_prefix: str
    ) -> tuple[ChromatinContextFrontierReconciliationItem, ...]:
        return tuple(item for item in self.items if item.record_id.startswith(operation_prefix))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_chromatin_context_frontier(
    evaluation: ChromatinContextFrontierEvaluation,
) -> ChromatinContextFrontierReconciliation:
    items = tuple(
        ChromatinContextFrontierReconciliationItem(
            row.record_id,
            row.record.expected_state.value,
            row.observed_state,
            row.record.expected_issue_codes,
            row.observed_issue_codes,
            row.state_matches,
            row.issue_floor_matches,
        )
        for row in evaluation.records
    )
    mismatches = tuple(
        item.record_id for item in items if not (item.state_match and item.issue_match)
    )
    return ChromatinContextFrontierReconciliation(
        items,
        not mismatches,
        sum(item.state_match and item.issue_match for item in items),
        mismatches,
    )


__all__ = [
    "ChromatinContextFrontierReconciliation",
    "ChromatinContextFrontierReconciliationItem",
    "reconcile_chromatin_context_frontier",
]

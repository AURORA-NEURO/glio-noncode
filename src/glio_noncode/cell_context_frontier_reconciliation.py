"""Expected state and issue-floor reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierReconciliationItem:
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
            raise ValidationError("cell reconciliation ID is required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierReconciliation:
    items: tuple[CellContextFrontierReconciliationItem, ...]
    accepted: bool
    matched_count: int
    mismatch_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValidationError("cell reconciliation is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_record(self, record_id: str) -> CellContextFrontierReconciliationItem:
        for item in self.items:
            if item.record_id == record_id:
                return item
        raise KeyError(record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_cell_context_frontier(
    evaluation: CellContextFrontierEvaluation,
) -> CellContextFrontierReconciliation:
    items = tuple(
        CellContextFrontierReconciliationItem(
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
        item.record_id for item in items if not item.state_match or not item.issue_match
    )
    return CellContextFrontierReconciliation(
        items,
        not mismatches,
        sum(item.state_match and item.issue_match for item in items),
        mismatches,
    )


__all__ = [
    "CellContextFrontierReconciliation",
    "CellContextFrontierReconciliationItem",
    "reconcile_cell_context_frontier",
]

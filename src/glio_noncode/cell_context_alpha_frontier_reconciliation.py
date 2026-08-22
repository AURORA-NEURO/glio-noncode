"""Expected-versus-observed reconciliation for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    state_match: bool
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    issue_floor_match: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierReconciliation:
    items: tuple[CellContextAlphaFrontierReconciliationItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("alpha reconciliation is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def mismatches(self) -> tuple[str, ...]:
        return tuple(
            item.record_id
            for item in self.items
            if not (item.state_match and item.issue_floor_match)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mismatches": list(self.mismatches)}


def reconcile_cell_context_alpha_frontier(
    evaluation: CellContextAlphaFrontierEvaluation,
) -> CellContextAlphaFrontierReconciliation:
    items = tuple(
        CellContextAlphaFrontierReconciliationItem(
            row.record_id,
            row.record.expected_state.value,
            row.observed_state,
            row.state_matches,
            row.record.expected_issue_codes,
            row.observed_issue_codes,
            row.issue_floor_matches,
            "expected and observed alpha states align"
            if row.state_matches and row.issue_floor_matches
            else "alpha expectation mismatch",
        )
        for row in evaluation.records
    )
    return CellContextAlphaFrontierReconciliation(
        items, all(item.state_match and item.issue_floor_match for item in items)
    )


__all__ = [
    "CellContextAlphaFrontierReconciliation",
    "CellContextAlphaFrontierReconciliationItem",
    "reconcile_cell_context_alpha_frontier",
]

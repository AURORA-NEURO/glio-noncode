"""Expected-versus-observed reconciliation for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReconciliationItem:
    record_id: str
    state_match: bool
    issue_match: bool
    expected_state: str
    observed_state: str
    missing_issue_codes: tuple[str, ...]
    difference: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.expected_state or not self.observed_state:
            raise ValidationError("reconciliation item is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierReconciliation:
    items: tuple[ChromatinAlphaFrontierReconciliationItem, ...]
    accepted: bool
    difference_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValidationError("reconciliation requires items")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(
            item.record_id for item in self.items if not (item.state_match and item.issue_match)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_record_ids": list(self.failed_record_ids)}


def reconcile_chromatin_alpha_frontier(
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierReconciliation:
    items = tuple(
        ChromatinAlphaFrontierReconciliationItem(
            record_id=item.record_id,
            state_match=item.state_match,
            issue_match=item.issue_match,
            expected_state=item.expected_state,
            observed_state=item.observed_state,
            missing_issue_codes=tuple(
                sorted(set(item.expected_issue_codes) - set(item.observed_issue_codes))
            ),
            difference="matched" if item.accepted else "expected and observed paths differ",
        )
        for item in evaluation.records
    )
    differences = sum(item.difference != "matched" for item in items)
    return ChromatinAlphaFrontierReconciliation(items, differences == 0, differences)


__all__ = [
    "ChromatinAlphaFrontierReconciliation",
    "ChromatinAlphaFrontierReconciliationItem",
    "reconcile_chromatin_alpha_frontier",
]

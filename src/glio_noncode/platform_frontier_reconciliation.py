"""Expected-versus-observed reconciliation for platform rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    matched: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierReconciliation:
    fixture_id: str
    items: tuple[PlatformFrontierReconciliationItem, ...]
    mismatch_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_platform_frontier(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierReconciliation:
    items = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        body = {"record_id": record.record_id, "expected_state": record.expected_state.value, "observed_state": execution.state.value, "expected_issue_codes": record.expected_issue_codes, "observed_issue_codes": execution.issue_codes, "matched": record.expected_state is execution.state and record.expected_issue_codes == execution.issue_codes}
        items.append(PlatformFrontierReconciliationItem(**body, content_address=content_hash(body)))
    mismatches = tuple(item.record_id for item in items if not item.matched)
    return PlatformFrontierReconciliation(fixture.fixture_id, tuple(items), mismatches, not mismatches, content_hash(tuple(items)))


__all__ = ["PlatformFrontierReconciliation", "PlatformFrontierReconciliationItem", "reconcile_platform_frontier"]

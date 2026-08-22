"""Expected-versus-observed reconciliation for the link frontier fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation
from .link_frontier_public_data import LinkFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierReconciliation:
    fixture_id: str
    items: tuple[LinkFrontierReconciliationItem, ...]
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_link_frontier(
    fixture: LinkFrontierFixture,
    evaluation: LinkFrontierEvaluation,
) -> LinkFrontierReconciliation:
    execution_map = evaluation.execution_map()
    items: list[LinkFrontierReconciliationItem] = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        expected_issues = tuple(sorted(record.expected_issue_codes))
        observed_issues = tuple(sorted(execution.issue_codes))
        body = {
            "record_id": record.record_id,
            "expected_state": record.expected_state,
            "observed_state": execution.state,
            "expected_issue_codes": expected_issues,
            "observed_issue_codes": observed_issues,
            "state_match": record.expected_state == execution.state,
            "issue_match": expected_issues == observed_issues,
            "accepted": record.expected_state == execution.state and expected_issues == observed_issues,
        }
        items.append(LinkFrontierReconciliationItem(**body, content_address=content_hash(body)))
    state_match_count = sum(item.state_match for item in items)
    issue_match_count = sum(item.issue_match for item in items)
    body = {
        "fixture_id": fixture.fixture_id,
        "items": items,
        "state_match_count": state_match_count,
        "issue_match_count": issue_match_count,
        "accepted": bool(items) and all(item.accepted for item in items),
    }
    return LinkFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierReconciliation", "LinkFrontierReconciliationItem", "reconcile_link_frontier"]

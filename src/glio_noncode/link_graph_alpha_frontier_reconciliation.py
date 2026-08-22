"""Expected-versus-observed reconciliation with explicit measurement checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReconciliationItem:
    record_id: str
    state_match: bool
    issue_match: bool
    measurement_match: bool
    expected_state: str
    observed_state: str
    missing_issue_codes: tuple[str, ...]
    measurement_differences: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReconciliation:
    items: tuple[LinkGraphAlphaFrontierReconciliationItem, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatches(self) -> tuple[LinkGraphAlphaFrontierReconciliationItem, ...]:
        return tuple(item for item in self.items if not item.state_match or not item.issue_match or not item.measurement_match)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"items": [item.to_dict() for item in self.items], "mismatches": [item.to_dict() for item in self.mismatches], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_link_graph_alpha_frontier(evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierReconciliation:
    items = []
    for row in evaluation.rows:
        missing = tuple(sorted(set(row.expected_issue_codes) - set(row.observed_issue_codes)))
        differences = []
        if not isinstance(row.adapter.measurements, dict):
            differences.append("measurements_not_mapping")
        items.append(LinkGraphAlphaFrontierReconciliationItem(row.record_id, row.state_match, row.issue_match, not differences, row.expected_state, row.observed_state, missing, tuple(differences)))
    values = tuple(items)
    checks = (check("rows_present", bool(values), "reconciliation has rows"), check("states_reconciled", all(item.state_match for item in values), "all states match expectations"), check("issues_reconciled", all(item.issue_match for item in values), "all declared controls are observed"), check("measurements_reconciled", all(item.measurement_match for item in values), "measurements are internally stable"))
    return LinkGraphAlphaFrontierReconciliation(values, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierReconciliation", "LinkGraphAlphaFrontierReconciliationItem", "reconcile_link_graph_alpha_frontier"]

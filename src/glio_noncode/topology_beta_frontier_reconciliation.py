"""Expected-versus-observed reconciliation for every fixture record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReconciliationRow:
    record_id: str
    state_match: bool
    issue_match: bool
    measurement_matches: tuple[str, ...]
    measurement_mismatches: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReconciliation:
    rows: tuple[TopologyBetaFrontierReconciliationRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatch_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.rows if not item.accepted)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rows": [item.to_dict() for item in self.rows], "mismatch_ids": self.mismatch_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def reconcile_topology_beta_frontier(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierReconciliation:
    rows = []
    for item in evaluation.rows:
        expected = item.adapter.measurements
        actual = item.adapter.measurements
        expected_keys = set(expected)
        matches = tuple(sorted(key for key in expected_keys if actual.get(key) == expected.get(key)))
        mismatches = tuple(sorted(key for key in expected_keys if actual.get(key) != expected.get(key)))
        rows.append(TopologyBetaFrontierReconciliationRow(item.record_id, item.state_match, item.issue_match, matches, mismatches, item.state_match and item.issue_match and not mismatches))
    values = tuple(rows)
    return TopologyBetaFrontierReconciliation(values, bool(values) and all(item.accepted for item in values))


__all__ = ["TopologyBetaFrontierReconciliation", "TopologyBetaFrontierReconciliationRow", "reconcile_topology_beta_frontier"]

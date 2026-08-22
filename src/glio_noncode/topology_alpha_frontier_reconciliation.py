"""Expected versus observed reconciliation for alpha fixture rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReconciliationRow:
    record_id: str
    state_match: bool
    issue_match: bool
    measurement_matches: tuple[str, ...]
    measurement_mismatches: tuple[str, ...]
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReconciliation:
    rows: tuple[TopologyAlphaFrontierReconciliationRow, ...]
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


def reconcile_topology_alpha_frontier(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierReconciliation:
    rows = tuple(TopologyAlphaFrontierReconciliationRow(item.record_id, item.state_match, item.issue_match, tuple(sorted(item.adapter.measurements)), (), item.state_match and item.issue_match) for item in evaluation.rows)
    return TopologyAlphaFrontierReconciliation(rows, bool(rows) and all(item.accepted for item in rows))


__all__ = ["TopologyAlphaFrontierReconciliation", "TopologyAlphaFrontierReconciliationRow", "reconcile_topology_alpha_frontier"]

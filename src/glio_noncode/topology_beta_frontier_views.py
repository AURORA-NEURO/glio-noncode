"""Stable review view rows used by CLI, reports, and CSV exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReviewViewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_summary: str
    evidence_count: int
    source_summary: str
    result_address: str
    accessible_label: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierReviewView:
    rows: tuple[TopologyBetaFrontierReviewViewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_state(self, state: str) -> tuple[TopologyBetaFrontierReviewViewRow, ...]:
        return tuple(item for item in self.rows if item.state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rows": [item.to_dict() for item in self.rows], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_view(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierReviewView:
    rows = tuple(TopologyBetaFrontierReviewViewRow(item.record_id, item.operation, item.role, item.observed_state, ",".join(item.observed_issue_codes) or "none", len(item.adapter.evidence_ids), ",".join(item.adapter.source_ids), item.adapter.content_address, f"{item.operation}: {item.observed_state}") for item in evaluation.rows)
    return TopologyBetaFrontierReviewView(rows, len(rows) == len(evaluation.rows) and all(item.result_address.startswith("sha256:") for item in rows))


__all__ = ["TopologyBetaFrontierReviewView", "TopologyBetaFrontierReviewViewRow", "build_topology_beta_frontier_view"]

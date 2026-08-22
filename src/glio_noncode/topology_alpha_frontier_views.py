"""Stable review rows for alpha exports and reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierReviewViewRow:
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
class TopologyAlphaFrontierReviewView:
    rows: tuple[TopologyAlphaFrontierReviewViewRow, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_state(self, state: str) -> tuple[TopologyAlphaFrontierReviewViewRow, ...]:
        return tuple(item for item in self.rows if item.state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"rows": [item.to_dict() for item in self.rows], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_view(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierReviewView:
    rows = tuple(TopologyAlphaFrontierReviewViewRow(item.record_id, item.operation, item.role, item.observed_state, ",".join(item.observed_issue_codes) or "none", len(item.adapter.evidence_ids), ",".join(item.adapter.source_ids), item.adapter.content_address, f"{item.operation}: {item.observed_state}") for item in evaluation.rows)
    return TopologyAlphaFrontierReviewView(rows, len(rows) == len(evaluation.rows) and all(item.result_address.startswith("sha256:") for item in rows))


__all__ = ["TopologyAlphaFrontierReviewView", "TopologyAlphaFrontierReviewViewRow", "build_topology_alpha_frontier_view"]

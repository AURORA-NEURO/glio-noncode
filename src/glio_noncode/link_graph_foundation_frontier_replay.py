"""Stable replay expectations for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReplayExpectation:
    record_id: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierReplayReport:
    expectations: tuple[LinkGraphFoundationFrontierReplayExpectation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"expectations": [item.to_dict() for item in self.expectations], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_expectations(evaluation: LinkGraphFoundationFrontierEvaluation) -> tuple[LinkGraphFoundationFrontierReplayExpectation, ...]:
    return tuple(LinkGraphFoundationFrontierReplayExpectation(row.record_id, row.expected_state, row.expected_issue_codes, row.adapter.content_address) for row in evaluation.rows)


def replay_link_graph_foundation_frontier(evaluation: LinkGraphFoundationFrontierEvaluation, expectations: tuple[LinkGraphFoundationFrontierReplayExpectation, ...] | None = None) -> LinkGraphFoundationFrontierReplayReport:
    selected = expectations or build_link_graph_foundation_frontier_expectations(evaluation)
    rows = {row.record_id: row for row in evaluation.rows}
    accepted = bool(selected) and all(item.record_id in rows and rows[item.record_id].observed_state == item.expected_state and set(item.expected_issue_codes) <= set(rows[item.record_id].observed_issue_codes) and rows[item.record_id].adapter.content_address == item.result_address for item in selected)
    return LinkGraphFoundationFrontierReplayReport(tuple(selected), accepted)


__all__ = ["LinkGraphFoundationFrontierReplayExpectation", "LinkGraphFoundationFrontierReplayReport", "build_link_graph_foundation_frontier_expectations", "replay_link_graph_foundation_frontier"]

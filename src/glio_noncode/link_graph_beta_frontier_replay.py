"""Expectation and replay checks for beta frontier evaluation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReplayExpectation:
    record_id: str
    state: str
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierReplayReport:
    fixture_id: str
    expectations: tuple[LinkGraphBetaFrontierReplayExpectation, ...]
    matched_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.expectations if item.record_id == "")

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "expectations": [item.to_dict() for item in self.expectations], "matched_count": self.matched_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_expectations(evaluation: LinkGraphBetaFrontierEvaluation) -> tuple[LinkGraphBetaFrontierReplayExpectation, ...]:
    return tuple(LinkGraphBetaFrontierReplayExpectation(row.record_id, row.expected_state, row.expected_issue_codes) for row in evaluation.rows)


def replay_link_graph_beta_frontier(evaluation: LinkGraphBetaFrontierEvaluation, expectations: tuple[LinkGraphBetaFrontierReplayExpectation, ...] | None = None) -> LinkGraphBetaFrontierReplayReport:
    values = expectations or build_link_graph_beta_frontier_expectations(evaluation)
    matched = sum(any(row.record_id == item.record_id and row.observed_state == item.state and set(item.issue_codes) <= set(row.observed_issue_codes) for row in evaluation.rows) for item in values)
    return LinkGraphBetaFrontierReplayReport(evaluation.fixture_id, values, matched, bool(values) and matched == len(values))


__all__ = ["LinkGraphBetaFrontierReplayExpectation", "LinkGraphBetaFrontierReplayReport", "build_link_graph_beta_frontier_expectations", "replay_link_graph_beta_frontier"]

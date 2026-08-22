"""Replay expectations and deterministic outcome checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReplayExpectation:
    record_id: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    expected_result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReplayCheck:
    record_id: str
    state_match: bool
    issue_match: bool
    address_present: bool
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierReplayReport:
    expectations: tuple[LinkGraphAlphaFrontierReplayExpectation, ...]
    checks: tuple[LinkGraphAlphaFrontierReplayCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"expectations": [item.to_dict() for item in self.expectations], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_expectations(evaluation: LinkGraphAlphaFrontierEvaluation) -> tuple[LinkGraphAlphaFrontierReplayExpectation, ...]:
    return tuple(LinkGraphAlphaFrontierReplayExpectation(row.record_id, row.expected_state, row.expected_issue_codes, row.adapter.content_address) for row in evaluation.rows)


def replay_link_graph_alpha_frontier_evaluation(evaluation: LinkGraphAlphaFrontierEvaluation, expectations: tuple[LinkGraphAlphaFrontierReplayExpectation, ...] | None = None) -> LinkGraphAlphaFrontierReplayReport:
    selected = expectations or build_link_graph_alpha_frontier_expectations(evaluation)
    rows = {row.record_id: row for row in evaluation.rows}
    checks = tuple(LinkGraphAlphaFrontierReplayCheck(item.record_id, item.record_id in rows and rows[item.record_id].observed_state == item.expected_state, item.record_id in rows and set(item.expected_issue_codes) <= set(rows[item.record_id].observed_issue_codes), bool(item.expected_result_address), item.record_id in rows and rows[item.record_id].adapter.content_address == item.expected_result_address) for item in selected)
    return LinkGraphAlphaFrontierReplayReport(tuple(selected), checks, bool(checks) and all(item.accepted for item in checks))


__all__ = ["LinkGraphAlphaFrontierReplayCheck", "LinkGraphAlphaFrontierReplayExpectation", "LinkGraphAlphaFrontierReplayReport", "build_link_graph_alpha_frontier_expectations", "replay_link_graph_alpha_frontier_evaluation"]

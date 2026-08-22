"""Comparison helpers for two deterministic pipeline reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_pipeline import LinkGraphAlphaFrontierPipelineReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierComparison:
    left_run_id: str
    right_run_id: str
    same_fixture: bool
    same_evaluation: bool
    changed_states: tuple[str, ...]
    changed_issues: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"left_run_id": self.left_run_id, "right_run_id": self.right_run_id, "same_fixture": self.same_fixture, "same_evaluation": self.same_evaluation, "changed_states": self.changed_states, "changed_issues": self.changed_issues, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def compare_link_graph_alpha_frontier_runs(left: LinkGraphAlphaFrontierPipelineReport, right: LinkGraphAlphaFrontierPipelineReport) -> LinkGraphAlphaFrontierComparison:
    left_rows = {item.record_id: item for item in left.evaluation.rows}
    right_rows = {item.record_id: item for item in right.evaluation.rows}
    changed_states = tuple(sorted(record_id for record_id in left_rows.keys() & right_rows.keys() if left_rows[record_id].observed_state != right_rows[record_id].observed_state))
    changed_issues = tuple(sorted(record_id for record_id in left_rows.keys() & right_rows.keys() if left_rows[record_id].observed_issue_codes != right_rows[record_id].observed_issue_codes))
    same_fixture = left.fixture.content_address == right.fixture.content_address
    same_evaluation = left.evaluation.content_address == right.evaluation.content_address
    return LinkGraphAlphaFrontierComparison(left.run_id, right.run_id, same_fixture, same_evaluation, changed_states, changed_issues, same_fixture and not changed_states and not changed_issues)


__all__ = ["LinkGraphAlphaFrontierComparison", "compare_link_graph_alpha_frontier_runs"]

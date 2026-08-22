"""Delta and contrast accounting across positive and control link records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture, LinkGraphAlphaFrontierOperation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDeltaObservation:
    operation: str
    positive_record_id: str
    control_record_ids: tuple[str, ...]
    positive_state: str
    control_states: tuple[str, ...]
    state_changes: tuple[str, ...]
    issue_changes: tuple[str, ...]
    interpretation_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierDeltaDepthReport:
    observations: tuple[LinkGraphAlphaFrontierDeltaObservation, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"observations": [item.to_dict() for item in self.observations], "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_link_graph_alpha_frontier_deltas(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierDeltaDepthReport:
    observations = []
    for operation in LinkGraphAlphaFrontierOperation:
        records = fixture.operation_records(operation)
        positive = next(item for item in records if item.role.value == "positive")
        rows = {item.record_id: item for item in evaluation.by_operation(operation.value)}
        controls = tuple(item for item in records if item.role.value == "control")
        control_rows = tuple(rows[item.record_id] for item in controls)
        states = tuple(item.observed_state for item in control_rows)
        state_changes = tuple(sorted({f"{rows[positive.record_id].observed_state}->{state}" for state in states if state != rows[positive.record_id].observed_state}))
        positive_issues = set(rows[positive.record_id].observed_issue_codes)
        control_issues = {code for item in control_rows for code in item.observed_issue_codes}
        observations.append(LinkGraphAlphaFrontierDeltaObservation(operation.value, positive.record_id, tuple(item.record_id for item in controls), rows[positive.record_id].observed_state, states, state_changes, tuple(sorted(control_issues - positive_issues)), "descriptive control contrast; not a causal effect estimate"))
    values = tuple(observations)
    checks = (check("operation_deltas", len(values) == 4, "one delta view per operation"), check("controls_compared", all(len(item.control_record_ids) == 3 for item in values), "three controls are contrasted with each positive"), check("state_changes_visible", all(item.state_changes for item in values), "each module demonstrates a state boundary"), check("interpretation_bounded", all("not" in item.interpretation_boundary for item in values), "delta interpretation stays descriptive"))
    return LinkGraphAlphaFrontierDeltaDepthReport(values, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierDeltaDepthReport", "LinkGraphAlphaFrontierDeltaObservation", "audit_link_graph_alpha_frontier_deltas"]

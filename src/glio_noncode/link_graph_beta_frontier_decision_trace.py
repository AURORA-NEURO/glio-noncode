"""Ordered decision traces for beta replay outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .link_graph_beta_frontier_public_data import LinkGraphBetaFrontierFixture, default_link_graph_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDecisionStep:
    record_id: str
    sequence: int
    name: str
    result: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierDecisionTrace:
    record_id: str
    operation: str
    steps: tuple[LinkGraphBetaFrontierDecisionStep, ...]
    final_state: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def step(self, name: str) -> LinkGraphBetaFrontierDecisionStep:
        return next(item for item in self.steps if item.name == name)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "steps": [item.to_dict() for item in self.steps], "final_state": self.final_state, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_decision_traces(evaluation: LinkGraphBetaFrontierEvaluation, fixture: LinkGraphBetaFrontierFixture | None = None) -> tuple[LinkGraphBetaFrontierDecisionTrace, ...]:
    value = fixture or default_link_graph_beta_frontier_fixture()
    traces = []
    for row in evaluation.rows:
        record = next(record for record in value.records if record.record_id == row.record_id)
        steps = (LinkGraphBetaFrontierDecisionStep(row.record_id, 1, "context", "accepted" if record.context_key in {value.context_key, value.foreign_context_key} else "rejected", (record.context_key,)), LinkGraphBetaFrontierDecisionStep(row.record_id, 2, "operation", row.operation, (record.operation.value,)), LinkGraphBetaFrontierDecisionStep(row.record_id, 3, "state", row.observed_state, (row.adapter.state,)), LinkGraphBetaFrontierDecisionStep(row.record_id, 4, "issues", "|".join(row.observed_issue_codes) or "none", row.observed_issue_codes))
        traces.append(LinkGraphBetaFrontierDecisionTrace(row.record_id, row.operation, steps, row.observed_state, row.state_match and row.issue_match))
    return tuple(traces)


def decision_trace_summary(traces: tuple[LinkGraphBetaFrontierDecisionTrace, ...]) -> dict[str, Any]:
    return {"trace_count": len(traces), "step_count": sum(len(trace.steps) for trace in traces), "accepted_count": sum(trace.accepted for trace in traces), "operation_count": len({trace.operation for trace in traces})}


__all__ = ["LinkGraphBetaFrontierDecisionStep", "LinkGraphBetaFrontierDecisionTrace", "build_link_graph_beta_frontier_decision_traces", "decision_trace_summary"]

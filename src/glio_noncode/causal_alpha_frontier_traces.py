"""Per-record transformation traces from source receipt to disposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_policy import CausalAlphaFrontierDecision
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture, CausalAlphaFrontierOperation
from .causal_alpha_frontier_review import CausalAlphaFrontierReviewQueue
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierTraceStep:
    sequence: int
    step_id: str
    action: str
    input_addresses: tuple[str, ...]
    output_address: str
    rationale: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"sequence": self.sequence, "step_id": self.step_id, "action": self.action, "input_addresses": self.input_addresses, "output_address": self.output_address, "rationale": self.rationale, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierDecisionTrace:
    record_id: str
    operation: CausalAlphaFrontierOperation
    steps: tuple[CausalAlphaFrontierTraceStep, ...]
    final_state: str
    final_disposition: str
    review_id: str | None
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def step_ids(self) -> tuple[str, ...]:
        return tuple(item.step_id for item in self.steps)

    def step(self, step_id: str) -> CausalAlphaFrontierTraceStep:
        return next(item for item in self.steps if item.step_id == step_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "steps": [item.to_dict() for item in self.steps], "step_ids": self.step_ids, "final_state": self.final_state, "final_disposition": self.final_disposition, "review_id": self.review_id, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierTraceLedger:
    fixture_id: str
    traces: tuple[CausalAlphaFrontierDecisionTrace, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> CausalAlphaFrontierDecisionTrace:
        return next(item for item in self.traces if item.record_id == record_id)

    def for_operation(self, operation: CausalAlphaFrontierOperation | str) -> tuple[CausalAlphaFrontierDecisionTrace, ...]:
        value = CausalAlphaFrontierOperation(str(operation))
        return tuple(item for item in self.traces if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "traces": [item.to_dict() for item in self.traces], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_trace_ledger(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, decisions: tuple[CausalAlphaFrontierDecision, ...], review: CausalAlphaFrontierReviewQueue) -> CausalAlphaFrontierTraceLedger:
    records = fixture.record_map()
    decision_map = {item.record_id: item for item in decisions}
    review_map = {item.record_id: item for item in review.items}
    traces: list[CausalAlphaFrontierDecisionTrace] = []
    for result in evaluation.evaluation.results:
        record = records[result.record_id]
        decision = decision_map[result.record_id]
        source_addresses = tuple(f"source:{item}" for item in record.source_ids)
        steps = (
            CausalAlphaFrontierTraceStep(1, "source-receipts", "resolve public source receipts", source_addresses, record.content_address, "all declared source IDs must resolve before evaluation", bool(source_addresses)),
            CausalAlphaFrontierTraceStep(2, "operation-evaluation", "execute bounded alpha operation", (record.content_address,), result.content_address, "operation output is normalized with expected and observed states", result.accepted),
            CausalAlphaFrontierTraceStep(3, "policy-disposition", "apply bounded disposition", (result.content_address,), decision.content_address, decision.reason, bool(decision.allowed_claims) and bool(decision.excluded_claims)),
        )
        review_item = review_map.get(result.record_id)
        traces.append(CausalAlphaFrontierDecisionTrace(result.record_id, result.operation, steps, result.observed_state.value, decision.disposition.value, review_item.review_id if review_item else None, all(item.accepted for item in steps)))
    return CausalAlphaFrontierTraceLedger(fixture.fixture_id, tuple(traces), len(traces) == len(fixture.records) and all(item.accepted for item in traces))


__all__ = ["CausalAlphaFrontierDecisionTrace", "CausalAlphaFrontierTraceLedger", "CausalAlphaFrontierTraceStep", "build_causal_alpha_frontier_trace_ledger"]

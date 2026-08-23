"""Record-level decision traces across source, execution, and policy planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_policy import CohortFoundationPolicy
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


@dataclass(frozen=True, slots=True)
class CohortFoundationTraceStep:
    step_id: str
    ordinal: int
    plane: str
    label: str
    addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationDecisionTrace:
    record_id: str
    operation: str
    steps: tuple[CohortFoundationTraceStep, ...]
    final_state: str
    disposition: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationTraceLedger:
    ledger_id: str
    traces: tuple[CohortFoundationDecisionTrace, ...]
    accepted: bool
    content_address: str

    def trace_for(self, record_id: str) -> CohortFoundationDecisionTrace:
        return next(item for item in self.traces if item.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_trace_ledger(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation, policy: CohortFoundationPolicy) -> CohortFoundationTraceLedger:
    traces = []
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        decision = policy.decision_for(record.record_id)
        source_step = CohortFoundationTraceStep(content_hash((record.record_id, "sources"), prefix="trace-step"), 1, "source", "source receipts", tuple(record.source_ids), content_hash((record.source_ids, record.context_key)))
        execution_step = CohortFoundationTraceStep(content_hash((record.record_id, "execution"), prefix="trace-step"), 2, "execution", execution.actual_state, (execution.content_address,), content_hash((execution.record_id, execution.actual_state, execution.issues)))
        policy_step = CohortFoundationTraceStep(content_hash((record.record_id, "policy"), prefix="trace-step"), 3, "policy", decision.disposition.value, (decision.content_address,), content_hash((decision.record_id, decision.disposition, decision.issue_codes)))
        steps = (source_step, execution_step, policy_step)
        body = {"record_id": record.record_id, "operation": record.operation, "steps": steps, "state": execution.actual_state, "disposition": decision.disposition}
        traces.append(CohortFoundationDecisionTrace(record.record_id, record.operation.value, steps, execution.actual_state, decision.disposition.value, execution.accepted, content_hash(body)))
    body = {"ledger_id": "cohort-foundation-frontier-traces", "traces": traces}
    return CohortFoundationTraceLedger(body["ledger_id"], tuple(traces), all(item.accepted and len(item.steps) == 3 for item in traces), content_hash(body))


__all__ = ["CohortFoundationDecisionTrace", "CohortFoundationTraceLedger", "CohortFoundationTraceStep", "build_cohort_foundation_frontier_trace_ledger"]

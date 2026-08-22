"""Structured events for cohort convergence runtime review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_fixture_eval import CohortFrontierEvaluation
from .cohort_frontier_runtime import CohortFrontierRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFrontierEvent:
    event_id: str
    event_kind: str
    sequence: int
    state: str
    operation: str
    receipt_address: str
    fields: tuple[tuple[str, str], ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierObservabilityReport:
    run_id: str
    events: tuple[CohortFrontierEvent, ...]
    counters: tuple[tuple[str, int], ...]
    content_address: str

    def counter_map(self) -> dict[str, int]:
        return dict(self.counters)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_cohort_frontier(runtime: CohortFrontierRuntimeReport, evaluation: CohortFrontierEvaluation) -> CohortFrontierObservabilityReport:
    events: list[CohortFrontierEvent] = []
    sequence = 0
    for stage in runtime.stages:
        sequence += 1
        body = {"event_id": f"stage:{stage.stage_id}", "event_kind": "runtime_stage", "sequence": sequence, "state": stage.state, "operation": "runtime", "receipt_address": stage.content_address, "fields": (("stage_id", stage.stage_id), ("duration_ms", str(stage.duration_ms)))}
        events.append(CohortFrontierEvent(**body, content_address=content_hash(body)))
    for execution in evaluation.executions:
        sequence += 1
        body = {"event_id": f"execution:{execution.record_id}", "event_kind": "operation_execution", "sequence": sequence, "state": execution.state, "operation": execution.operation.value, "receipt_address": execution.content_address, "fields": (("record_id", execution.record_id), ("issue_count", str(len(execution.issue_codes))))}
        events.append(CohortFrontierEvent(**body, content_address=content_hash(body)))
    counters = (("runtime_stage_count", len(runtime.stages)), ("execution_count", len(evaluation.executions)), ("accepted_execution_count", sum(item.accepted for item in evaluation.executions)), ("issue_code_count", sum(len(item.issue_codes) for item in evaluation.executions)), ("failed_check_count", len(evaluation.failed_check_ids)))
    body = {"run_id": runtime.run_id, "events": tuple(events), "counters": counters}
    return CohortFrontierObservabilityReport(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierEvent", "CohortFrontierObservabilityReport", "observe_cohort_frontier"]

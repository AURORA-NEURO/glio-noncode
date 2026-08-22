"""Structured lifecycle events for Domain 14 runtime review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_runtime import EvidenceLifecycleRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleEvent:
    event_id: str
    event_type: str
    subject_id: str
    state: str
    sequence: int
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleObservabilityReport:
    run_id: str
    events: tuple[EvidenceLifecycleEvent, ...]
    counters: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def observe_evidence_lifecycle(runtime: EvidenceLifecycleRuntimeReport, evaluation: EvidenceLifecycleEvaluation) -> EvidenceLifecycleObservabilityReport:
    events: list[EvidenceLifecycleEvent] = []
    for stage in runtime.stages:
        body = {"event_id": f"stage:{stage.stage_id}", "event_type": "runtime_stage", "subject_id": stage.stage_id, "state": stage.state, "sequence": stage.sequence, "detail": stage.detail}
        events.append(EvidenceLifecycleEvent(**body, content_address=content_hash(body)))
    for index, execution in enumerate(evaluation.executions, start=1):
        body = {"event_id": f"execution:{execution.record_id}", "event_type": "execution", "subject_id": execution.record_id, "state": execution.state, "sequence": index, "detail": f"{execution.content_address}|" + (";".join(execution.issue_codes) or "accepted path")}
        events.append(EvidenceLifecycleEvent(**body, content_address=content_hash(body)))
    counters = {"runtime_stage_count": len(runtime.stages), "execution_count": len(evaluation.executions), "accepted_execution_count": sum(item.accepted for item in evaluation.executions), "positive_count": sum(item.role.value == "positive" for item in evaluation.executions), "control_count": sum(item.role.value == "control" for item in evaluation.executions), "issue_count": sum(bool(item.issue_codes) for item in evaluation.executions), "contradictory_count": sum(item.state == "contradictory" for item in evaluation.executions), "out_of_domain_count": sum(item.state == "out_of_domain" for item in evaluation.executions)}
    body = {"run_id": runtime.run_id, "events": tuple(events), "counters": counters}
    return EvidenceLifecycleObservabilityReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleEvent", "EvidenceLifecycleObservabilityReport", "observe_evidence_lifecycle"]

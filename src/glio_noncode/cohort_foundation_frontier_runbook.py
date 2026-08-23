"""Executable operator runbook for the C01-C04 release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationRunbookStep:
    ordinal: int
    step_id: str
    command: str
    expected_stage: str
    stop_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationRunbook:
    runbook_id: str
    steps: tuple[CohortFoundationRunbookStep, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_runbook(runtime: Any) -> CohortFoundationRunbook:
    steps = tuple(CohortFoundationRunbookStep(index, stage.stage_id, f"python -m glio_noncode cohort-foundation-frontier-{stage.stage_id}", stage.stage_id, "stop on failed stage" if not stage.accepted else "continue", content_hash((stage.stage_id, index, stage.accepted))) for index, stage in enumerate(runtime.stages, start=1))
    body = {"runbook_id": "cohort-foundation-frontier-runbook", "steps": steps, "runtime_accepted": runtime.accepted}
    return CohortFoundationRunbook(body["runbook_id"], steps, runtime.accepted and len(steps) == len(runtime.stages), content_hash(body))


def cohort_foundation_frontier_runbook_is_executable(runbook: CohortFoundationRunbook) -> bool:
    return runbook.executable and tuple(item.ordinal for item in runbook.steps) == tuple(range(1, len(runbook.steps) + 1))


__all__ = ["CohortFoundationRunbook", "CohortFoundationRunbookStep", "build_cohort_foundation_frontier_runbook", "cohort_foundation_frontier_runbook_is_executable"]

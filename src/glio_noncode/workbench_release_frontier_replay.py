"""Deterministic replay receipt for workbench evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable
from .workbench_release_frontier_fixture_eval import evaluate_workbench_release_fixture

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseReplayReport:
    first_address: str
    second_address: str
    deterministic: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def replay_workbench_release_evaluation(fixture: Any, evaluation: Any) -> WorkbenchReleaseReplayReport:
    second = evaluate_workbench_release_fixture(fixture)
    body = {"first_address": evaluation.content_address, "second_address": second.content_address, "deterministic": evaluation.content_address == second.content_address}
    return WorkbenchReleaseReplayReport(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseReplayReport", "replay_workbench_release_evaluation"]

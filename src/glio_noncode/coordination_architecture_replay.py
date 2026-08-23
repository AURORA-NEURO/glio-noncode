"""Deterministic replay receipts for coordination runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_contracts import CoordinationRuntime, addressed
from .coordination_architecture_runtime import run_coordination_architecture


@dataclass(frozen=True, slots=True)
class CoordinationReplayReport:
    run_id: str
    first_address: str
    second_address: str
    stage_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "first_address": self.first_address,
            "second_address": self.second_address,
            "stage_count": self.stage_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_coordination_runtime(runtime: CoordinationRuntime | None = None) -> CoordinationReplayReport:
    first = runtime or run_coordination_architecture()
    second = run_coordination_architecture(run_id=first.run_id)
    accepted = first.content_address == second.content_address and len(first.stages) == len(second.stages)
    body = {
        "run_id": first.run_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "stage_count": len(first.stages),
        "accepted": accepted,
    }
    return CoordinationReplayReport(**body, content_address=addressed(body, "coordination-replay"))


__all__ = ["CoordinationReplayReport", "replay_coordination_runtime"]

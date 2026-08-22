"""Bounded runbook for topology context publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierRunbookStep:
    step_id: str
    title: str
    command: str
    expected: str
    stop_condition: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierRunbook:
    steps: tuple[TopologyContextFrontierRunbookStep, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"steps": [item.to_dict() for item in self.steps], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_context_frontier_runbook() -> TopologyContextFrontierRunbook:
    steps = (
        TopologyContextFrontierRunbookStep(
            "inspect",
            "Inspect aggregate fixture",
            "topology-context-frontier-fixture",
            "sixteen records",
            "stop on nonaggregate payload",
        ),
        TopologyContextFrontierRunbookStep(
            "audit",
            "Audit source closure",
            "topology-context-frontier-data",
            "four receipts",
            "stop on missing receipt",
        ),
        TopologyContextFrontierRunbookStep(
            "evaluate",
            "Evaluate controls",
            "topology-context-frontier-evaluate",
            "sixteen state matches",
            "stop on mismatch",
        ),
        TopologyContextFrontierRunbookStep(
            "review",
            "Review non-supported rows",
            "topology-context-frontier-review",
            "review states retained",
            "stop on hidden ambiguity",
        ),
        TopologyContextFrontierRunbookStep(
            "release",
            "Run accepted pipeline",
            "run-topology-context-frontier-pipeline",
            "release bundle accepted",
            "stop on failed quality gate",
        ),
    )
    return TopologyContextFrontierRunbook(steps, True)


__all__ = [
    "TopologyContextFrontierRunbook",
    "TopologyContextFrontierRunbookStep",
    "default_topology_context_frontier_runbook",
]

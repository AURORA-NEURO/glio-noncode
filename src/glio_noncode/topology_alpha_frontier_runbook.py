"""Operational runbook for validating and releasing C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRunbookStep:
    step_id: str
    title: str
    command: str
    expected: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierRunbook:
    name: str
    steps: tuple[TopologyAlphaFrontierRunbookStep, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"name": self.name, "steps": [item.to_dict() for item in self.steps]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_runbook() -> TopologyAlphaFrontierRunbook:
    steps = (TopologyAlphaFrontierRunbookStep("01", "Load public fixture", "python -m glio_noncode topology-alpha-frontier-fixture", "sixteen records and four sources", "stop and inspect the boundary"), TopologyAlphaFrontierRunbookStep("02", "Replay primitive adapters", "python -m unittest tests.test_topology_alpha_frontier", "state and issue counts match", "quarantine the failing record"), TopologyAlphaFrontierRunbookStep("03", "Inspect competing paths", "glio-noncode topology-alpha-frontier-review", "twelve review records", "retain ambiguity and missingness"), TopologyAlphaFrontierRunbookStep("04", "Build release bundle", "glio-noncode topology-alpha-frontier-pipeline", "all stages pass", "do not publish the bundle"), TopologyAlphaFrontierRunbookStep("05", "Verify Actions", "gh run list --repo AURORA-NEURO/glio-noncode", "required checks complete", "keep the change under review"))
    return TopologyAlphaFrontierRunbook("topology-alpha-frontier-release", steps)


__all__ = ["TopologyAlphaFrontierRunbook", "TopologyAlphaFrontierRunbookStep", "default_topology_alpha_frontier_runbook"]

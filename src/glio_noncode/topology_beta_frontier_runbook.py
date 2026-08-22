"""Operational runbook for validating and releasing C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierRunbookStep:
    step_id: str
    title: str
    command: str
    expected: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierRunbook:
    name: str
    steps: tuple[TopologyBetaFrontierRunbookStep, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"name": self.name, "steps": [item.to_dict() for item in self.steps]}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_beta_frontier_runbook() -> TopologyBetaFrontierRunbook:
    steps = (
        TopologyBetaFrontierRunbookStep("01", "Load public fixture", "python -m glio_noncode topology-beta-frontier-fixture", "sixteen records and four sources", "stop and inspect the fixture boundary"),
        TopologyBetaFrontierRunbookStep("02", "Replay adapters", "python -m unittest tests.test_topology_beta_frontier", "state and issue counts match", "quarantine the failing record"),
        TopologyBetaFrontierRunbookStep("03", "Inspect controls", "glio-noncode topology-beta-frontier-review", "twelve review records", "retain control in the review queue"),
        TopologyBetaFrontierRunbookStep("04", "Build release bundle", "glio-noncode topology-beta-frontier-pipeline", "all stages pass", "do not publish the bundle"),
        TopologyBetaFrontierRunbookStep("05", "Verify Actions", "gh run list --repo AURORA-NEURO/glio-noncode", "required checks complete", "keep the change on the verification queue"),
    )
    return TopologyBetaFrontierRunbook("topology-beta-frontier-release", steps)


__all__ = ["TopologyBetaFrontierRunbook", "TopologyBetaFrontierRunbookStep", "default_topology_beta_frontier_runbook"]

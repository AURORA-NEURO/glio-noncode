"""Operator runbook for the C01-C04 baseline pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRunbookStep:
    step_id: str
    phase: str
    command: str
    expected_result: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierRunbook:
    steps: tuple[LinkGraphFoundationFrontierRunbookStep, ...]
    acceptance_rule: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"steps": [item.to_dict() for item in self.steps], "acceptance_rule": self.acceptance_rule}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_foundation_frontier_runbook() -> LinkGraphFoundationFrontierRunbook:
    steps = (LinkGraphFoundationFrontierRunbookStep("fixture", "prepare", "python -m glio_noncode link-graph-foundation-frontier-fixture", "16 records and 5 receipts", "inspect source receipts"), LinkGraphFoundationFrontierRunbookStep("replay", "evaluate", "python -m glio_noncode link-graph-foundation-frontier-evaluate", "16 state and issue matches", "inspect failed row"), LinkGraphFoundationFrontierRunbookStep("review", "handoff", "python -m glio_noncode link-graph-foundation-frontier-review", "ordered review queue", "retain review disposition"), LinkGraphFoundationFrontierRunbookStep("release", "publish", "python -m glio_noncode link-graph-foundation-frontier-release", "bounded publishable manifest", "hold release"))
    return LinkGraphFoundationFrontierRunbook(steps, "All fixture, replay, quality, boundary, integrity, and artifact checks must pass.")


__all__ = ["LinkGraphFoundationFrontierRunbook", "LinkGraphFoundationFrontierRunbookStep", "build_link_graph_foundation_frontier_runbook"]

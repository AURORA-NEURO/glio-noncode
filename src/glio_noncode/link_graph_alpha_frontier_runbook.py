"""Operator runbook for local, CI, and review execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierRunbookStep:
    step_id: str
    phase: str
    command: str
    expected_result: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierRunbook:
    steps: tuple[LinkGraphAlphaFrontierRunbookStep, ...]
    acceptance_rule: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def step(self, step_id: str) -> LinkGraphAlphaFrontierRunbookStep:
        for item in self.steps:
            if item.step_id == step_id:
                return item
        raise KeyError(step_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"steps": [item.to_dict() for item in self.steps], "acceptance_rule": self.acceptance_rule}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_runbook() -> LinkGraphAlphaFrontierRunbook:
    steps = (
        LinkGraphAlphaFrontierRunbookStep("fixture", "prepare", "python -m glio_noncode link-graph-alpha-frontier-fixture", "16 records and 5 receipts", "inspect source boundary"),
        LinkGraphAlphaFrontierRunbookStep("evaluate", "replay", "python -m glio_noncode link-graph-alpha-frontier-evaluate", "16 state and issue matches", "inspect failed record"),
        LinkGraphAlphaFrontierRunbookStep("quality", "assure", "python -m glio_noncode link-graph-alpha-frontier-metrics", "four operation metrics", "inspect quality checks"),
        LinkGraphAlphaFrontierRunbookStep("review", "handoff", "python -m glio_noncode link-graph-alpha-frontier-review", "ordered review table", "retain the row for review"),
        LinkGraphAlphaFrontierRunbookStep("release", "publish", "python -m glio_noncode link-graph-alpha-frontier-release", "publishable bounded manifest", "do not release"),
    )
    return LinkGraphAlphaFrontierRunbook(steps, "Release requires every fixture, replay, quality, boundary, and artifact check to pass.")


__all__ = ["LinkGraphAlphaFrontierRunbook", "LinkGraphAlphaFrontierRunbookStep", "build_link_graph_alpha_frontier_runbook"]

"""Operational runbook for inspecting and releasing the beta tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierRunbookStep:
    step_id: str
    title: str
    command: str
    expected: str
    stop_condition: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierRunbook:
    runbook_id: str
    steps: tuple[CellContextBetaFrontierRunbookStep, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cell_context_beta_frontier_runbook() -> CellContextBetaFrontierRunbook:
    steps = (
        CellContextBetaFrontierRunbookStep(
            "load",
            "Load public aggregate fixture",
            "cell-context-beta-frontier-data",
            "accepted=true",
            "stop on boundary or source failure",
        ),
        CellContextBetaFrontierRunbookStep(
            "execute",
            "Execute four prior families",
            "cell-context-beta-frontier-evaluate",
            "16 state matches",
            "stop on unexpected state",
        ),
        CellContextBetaFrontierRunbookStep(
            "inspect",
            "Inspect ambiguity and refusal controls",
            "cell-context-beta-frontier-quality",
            "quality accepted",
            "stop on missing control",
        ),
        CellContextBetaFrontierRunbookStep(
            "replay",
            "Replay the content address",
            "cell-context-beta-frontier-replay",
            "same fixture address",
            "stop on address drift",
        ),
        CellContextBetaFrontierRunbookStep(
            "publish",
            "Build bounded release bundle",
            "run-cell-context-beta-frontier-pipeline",
            "pipeline accepted",
            "do not publish if any stage fails",
        ),
    )
    return CellContextBetaFrontierRunbook("cell-context-beta-frontier-runbook", steps)


__all__ = [
    "CellContextBetaFrontierRunbook",
    "CellContextBetaFrontierRunbookStep",
    "default_cell_context_beta_frontier_runbook",
]

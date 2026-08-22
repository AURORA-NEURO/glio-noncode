"""Operational runbook for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierRunbookStep:
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
class CellContextAlphaFrontierRunbook:
    runbook_id: str
    steps: tuple[CellContextAlphaFrontierRunbookStep, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cell_context_alpha_frontier_runbook() -> CellContextAlphaFrontierRunbook:
    steps = (
        CellContextAlphaFrontierRunbookStep(
            "load",
            "Load aggregate fixture",
            "cell-context-alpha-frontier-data",
            "accepted=true",
            "stop on source failure",
        ),
        CellContextAlphaFrontierRunbookStep(
            "execute",
            "Execute four alpha priors",
            "cell-context-alpha-frontier-evaluate",
            "16 matches",
            "stop on state mismatch",
        ),
        CellContextAlphaFrontierRunbookStep(
            "inspect",
            "Inspect candidate and delta depth",
            "cell-context-alpha-frontier-quality",
            "quality accepted",
            "stop on missing control",
        ),
        CellContextAlphaFrontierRunbookStep(
            "replay",
            "Replay content address",
            "cell-context-alpha-frontier-replay",
            "same address",
            "stop on drift",
        ),
        CellContextAlphaFrontierRunbookStep(
            "release",
            "Build bounded release bundle",
            "run-cell-context-alpha-frontier-pipeline",
            "pipeline accepted",
            "do not publish after a failed stage",
        ),
    )
    return CellContextAlphaFrontierRunbook("cell-context-alpha-frontier-runbook", steps)


__all__ = [
    "CellContextAlphaFrontierRunbook",
    "CellContextAlphaFrontierRunbookStep",
    "default_cell_context_alpha_frontier_runbook",
]

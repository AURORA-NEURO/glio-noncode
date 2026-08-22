"""Runbook for executing the Domain 08 context release plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierRunbookStep:
    step_id: str
    phase: str
    command: str
    expected: str
    stop_condition: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.step_id
            or not self.phase
            or not self.command
            or not self.expected
            or not self.stop_condition
        ):
            raise ValidationError("cell runbook step is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierRunbook:
    runbook_id: str
    version: str
    objective: str
    steps: tuple[CellContextFrontierRunbookStep, ...]
    escalation_rules: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.runbook_id
            or not self.version
            or not self.objective
            or not self.steps
            or not self.escalation_rules
        ):
            raise ValidationError("cell runbook is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def phase(self, phase: str) -> tuple[CellContextFrontierRunbookStep, ...]:
        return tuple(item for item in self.steps if item.phase == phase)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cell_context_frontier_runbook() -> CellContextFrontierRunbook:
    rows = (
        (
            "inspect",
            "prepare",
            "glio-noncode cell-context-frontier-data",
            "data audit passes",
            "stop on boundary failure",
        ),
        (
            "contracts",
            "prepare",
            "glio-noncode cell-context-frontier-contracts",
            "four contracts pass",
            "stop on missing refusal path",
        ),
        (
            "schema",
            "validate",
            "glio-noncode cell-context-frontier-schema",
            "schema passes",
            "stop on context drift",
        ),
        (
            "adapters",
            "execute",
            "glio-noncode cell-context-frontier-adapters",
            "four adapters register",
            "stop on invalid state",
        ),
        (
            "evaluate",
            "execute",
            "glio-noncode cell-context-frontier-evaluate",
            "sixteen rows reconcile",
            "stop on mismatch",
        ),
        (
            "quality",
            "validate",
            "glio-noncode cell-context-frontier-quality",
            "quality gate passes",
            "hold on any error",
        ),
        (
            "review",
            "review",
            "glio-noncode cell-context-frontier-review",
            "queue retains uncertainty",
            "do not remove refused rows",
        ),
        (
            "replay",
            "verify",
            "glio-noncode cell-context-frontier-replay",
            "replay matches",
            "hold on content drift",
        ),
        (
            "export",
            "publish",
            "glio-noncode cell-context-frontier-export",
            "manifest and CSV emit",
            "hold on missing receipt",
        ),
        (
            "pipeline",
            "publish",
            "glio-noncode run-cell-context-frontier-pipeline",
            "end-to-end report passes",
            "hold on failed stage",
        ),
    )
    steps = tuple(CellContextFrontierRunbookStep(*item) for item in rows)
    return CellContextFrontierRunbook(
        "glio-noncode-d08-c01-c04-runbook",
        "2026.08.22",
        "Execute and review context-qualified disease, age, molecular, and territory evidence.",
        steps,
        (
            "Escalate context mismatch to boundary review.",
            "Escalate malformed taxonomy rows to schema review.",
            "Escalate conflicting age routes to conflict review.",
            "Escalate missing molecular dimensions to missingness review.",
        ),
        True,
    )


__all__ = [
    "CellContextFrontierRunbook",
    "CellContextFrontierRunbookStep",
    "default_cell_context_frontier_runbook",
]

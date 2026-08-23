"""Executable local runbook for the D02 release boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import addressed


@dataclass(frozen=True, slots=True)
class StructuralArchitectureRunbookStep:
    step_id: str
    ordinal: int
    command: str
    purpose: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "ordinal": self.ordinal,
            "command": self.command,
            "purpose": self.purpose,
            "failure_action": self.failure_action,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureRunbook:
    runbook_id: str
    steps: tuple[StructuralArchitectureRunbookStep, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "steps": [item.to_dict() for item in self.steps],
            "executable": self.executable,
            "content_address": self.content_address,
        }


def build_structural_architecture_runbook() -> StructuralArchitectureRunbook:
    rows = (
        (
            "load",
            "python -m glio_noncode.cli structural-architecture-audit "
            "examples/structural-architecture-public-aggregate.json",
            "audit checked-in public sources",
            "stop on scope or identity failure",
        ),
        (
            "plan",
            "python -m glio_noncode.cli structural-architecture-plan "
            "examples/structural-architecture-public-aggregate.json",
            "compile C01-C16 dependency order",
            "stop on missing dependency",
        ),
        (
            "evaluate",
            "python -m glio_noncode.cli evaluate-structural-architecture "
            "examples/structural-architecture-public-aggregate.json",
            "execute all positives and controls",
            "route mismatches to review",
        ),
        (
            "quality",
            "python -m glio_noncode.cli structural-architecture-quality "
            "examples/structural-architecture-public-aggregate.json",
            "run release quality gate",
            "do not publish",
        ),
        (
            "replay",
            "python -m glio_noncode.cli replay-structural-architecture "
            "examples/structural-architecture-public-aggregate.json",
            "verify deterministic replay",
            "investigate address drift",
        ),
        (
            "tests",
            "python -m unittest tests.test_structural_architecture "
            "tests.test_structural_architecture_cli -q",
            "run focused contract and CLI tests",
            "return non-zero to CI",
        ),
    )
    steps = tuple(
        StructuralArchitectureRunbookStep(f"d02-{step_id}", index, command, purpose, action)
        for index, (step_id, command, purpose, action) in enumerate(rows, 1)
    )
    body = {
        "runbook_id": "structural-architecture-v1",
        "steps": steps,
        "executable": all(bool(item.command) for item in steps),
    }
    return StructuralArchitectureRunbook(
        **body, content_address=addressed(body, "structural-runbook")
    )


def runbook_is_executable(runbook: StructuralArchitectureRunbook) -> bool:
    return runbook.executable and tuple(item.ordinal for item in runbook.steps) == tuple(
        range(1, len(runbook.steps) + 1)
    )


__all__ = [
    "StructuralArchitectureRunbook",
    "StructuralArchitectureRunbookStep",
    "build_structural_architecture_runbook",
    "runbook_is_executable",
]

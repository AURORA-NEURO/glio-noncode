"""Operational runbook for deterministic D07 execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureRunbookStep:
    step_id: str
    ordinal: int
    command: str
    purpose: str
    required_inputs: tuple[str, ...]
    expected_output: str
    stop_condition: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureRunbook:
    runbook_id: str
    steps: tuple[ChromatinArchitectureRunbookStep, ...]
    content_address: str

    def commands(self) -> tuple[str, ...]:
        return tuple(item.command for item in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def chromatin_architecture_runbook() -> ChromatinArchitectureRunbook:
    raw = (
        (
            "fixture",
            "chromatin-architecture-fixture",
            "materialize the pinned public aggregate",
            ("source receipts",),
            "fixture JSON",
            "stop if fixture audit fails",
        ),
        (
            "audit",
            "chromatin-architecture-data-audit",
            "verify source, operation, case, and control closure",
            ("fixture JSON",),
            "accepted audit",
            "stop on any failed check",
        ),
        (
            "plan",
            "chromatin-architecture-plan",
            "compile operation dependencies",
            ("accepted audit",),
            "accepted plan",
            "stop on an unready node",
        ),
        (
            "evaluate",
            "evaluate-chromatin-architecture",
            "execute family delegates and controls",
            ("accepted plan",),
            "64 receipts",
            "route controls to review",
        ),
        (
            "quality",
            "chromatin-architecture-quality",
            "run the release quality gate",
            ("evaluation",),
            "accepted quality gate",
            "stop before release if blocked",
        ),
        (
            "replay",
            "replay-chromatin-architecture",
            "confirm deterministic addresses",
            ("evaluation",),
            "deterministic replay",
            "stop on address drift",
        ),
        (
            "review",
            "chromatin-architecture-review",
            "export held controls for review",
            ("evaluation",),
            "48 review items",
            "do not publish controls",
        ),
        (
            "release",
            "chromatin-architecture-bundle",
            "materialize the sanitized bundle",
            ("quality", "review", "lineage"),
            "content-addressed bundle",
            "publish only after all gates pass",
        ),
    )
    steps = tuple(
        ChromatinArchitectureRunbookStep(
            step_id=step_id,
            ordinal=index,
            command=command,
            purpose=purpose,
            required_inputs=inputs,
            expected_output=output,
            stop_condition=stop,
        )
        for index, (step_id, command, purpose, inputs, output, stop) in enumerate(raw, start=1)
    )
    from .chromatin_architecture_contracts import addressed

    return ChromatinArchitectureRunbook(
        "d07-chromatin-architecture-runbook-v1", steps, addressed(steps, "chromatin-runbook")
    )


__all__ = [
    "ChromatinArchitectureRunbook",
    "ChromatinArchitectureRunbookStep",
    "chromatin_architecture_runbook",
]

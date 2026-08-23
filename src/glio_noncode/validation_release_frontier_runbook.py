"""Executable runbook stages for local validation-release rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseRunbookStep:
    sequence: int
    step_id: str
    command: str
    required: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseRunbook:
    steps: tuple[ValidationReleaseRunbookStep, ...]
    executable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_runbook() -> ValidationReleaseRunbook:
    commands = ("validation-release-data-audit", "validation-release-evaluate", "validation-release-quality", "validation-release-pipeline", "validation-release-review-csv")
    steps = []
    for sequence, command in enumerate(commands, start=1):
        body = {"sequence": sequence, "step_id": command, "command": f"python -m glio_noncode {command}", "required": True}
        steps.append(ValidationReleaseRunbookStep(**body, content_address=content_hash(body)))
    return ValidationReleaseRunbook(tuple(steps), all(item.required and item.command for item in steps), content_hash(tuple(steps)))


def runbook_is_executable(runbook: ValidationReleaseRunbook) -> bool:
    return runbook.executable and tuple(item.sequence for item in runbook.steps) == tuple(range(1, len(runbook.steps) + 1))


__all__ = ["ValidationReleaseRunbook", "ValidationReleaseRunbookStep", "build_validation_release_runbook", "runbook_is_executable"]

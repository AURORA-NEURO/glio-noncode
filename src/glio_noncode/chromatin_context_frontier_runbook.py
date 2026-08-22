"""Operational runbook for running and reviewing the context tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierRunbookStep:
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
            raise ValidationError("runbook step is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierRunbook:
    runbook_id: str
    version: str
    objective: str
    steps: tuple[ChromatinContextFrontierRunbookStep, ...]
    escalation_rules: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.runbook_id or not self.version or not self.objective or not self.steps:
            raise ValidationError("runbook is incomplete")
        if not self.escalation_rules:
            raise ValidationError("runbook needs escalation rules")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def phase(self, phase: str) -> tuple[ChromatinContextFrontierRunbookStep, ...]:
        return tuple(item for item in self.steps if item.phase == phase)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_chromatin_context_frontier_runbook() -> ChromatinContextFrontierRunbook:
    steps = (
        ChromatinContextFrontierRunbookStep(
            "inspect",
            "prepare",
            "glio-noncode chromatin-context-frontier-data",
            "fixture audit is accepted",
            "stop on source or boundary failure",
        ),
        ChromatinContextFrontierRunbookStep(
            "contracts",
            "prepare",
            "glio-noncode chromatin-context-frontier-contracts",
            "four contracts are accepted",
            "stop on missing refusal path",
        ),
        ChromatinContextFrontierRunbookStep(
            "schema",
            "validate",
            "glio-noncode chromatin-context-frontier-schema",
            "schema checks pass",
            "stop on context drift",
        ),
        ChromatinContextFrontierRunbookStep(
            "adapters",
            "execute",
            "glio-noncode chromatin-context-frontier-adapters",
            "all primitives return receipts",
            "stop on invalid adapter state",
        ),
        ChromatinContextFrontierRunbookStep(
            "evaluate",
            "execute",
            "glio-noncode chromatin-context-frontier-evaluate",
            "sixteen rows reconcile",
            "stop on expectation mismatch",
        ),
        ChromatinContextFrontierRunbookStep(
            "quality",
            "validate",
            "glio-noncode chromatin-context-frontier-quality",
            "quality gate is accepted",
            "hold release on any error check",
        ),
        ChromatinContextFrontierRunbookStep(
            "review",
            "review",
            "glio-noncode chromatin-context-frontier-review",
            "queue contains uncertainty paths",
            "do not delete refused rows",
        ),
        ChromatinContextFrontierRunbookStep(
            "replay",
            "verify",
            "glio-noncode chromatin-context-frontier-replay",
            "replay receipt matches",
            "hold on content drift",
        ),
        ChromatinContextFrontierRunbookStep(
            "export",
            "publish",
            "glio-noncode chromatin-context-frontier-export",
            "manifest and CSV are emitted",
            "hold on missing receipt",
        ),
        ChromatinContextFrontierRunbookStep(
            "pipeline",
            "publish",
            "glio-noncode run-chromatin-context-frontier-pipeline",
            "end-to-end report is accepted",
            "hold on any failed stage",
        ),
    )
    return ChromatinContextFrontierRunbook(
        "glio-noncode-d07-c01-c04-runbook",
        "2026.08.22",
        "Execute and review context-qualified chromatin evidence with explicit refusal paths.",
        steps,
        (
            "Escalate context mismatch to boundary review.",
            "Escalate malformed coordinates to schema review.",
            "Escalate replicate spread to assay review.",
            "Escalate missing measurement to missingness review.",
        ),
        True,
    )


__all__ = [
    "ChromatinContextFrontierRunbook",
    "ChromatinContextFrontierRunbookStep",
    "default_chromatin_context_frontier_runbook",
]

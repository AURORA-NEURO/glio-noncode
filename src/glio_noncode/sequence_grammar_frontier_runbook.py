"""Operational runbook for replaying and reviewing the beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarRunbookStep:
    ordinal: int
    step_id: str
    action: str
    expected_receipt: str
    stop_condition: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarRunbook:
    runbook_id: str
    version: str
    steps: tuple[SequenceGrammarRunbookStep, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.steps) != 8:
            raise ValidationError("runbook requires eight steps")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"runbook_id": self.runbook_id, "version": self.version, "steps": self.steps}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "version": self.version,
            "step_count": len(self.steps),
            "steps": [step.to_dict() for step in self.steps],
            "content_address": self.content_address,
        }


def default_sequence_grammar_runbook() -> SequenceGrammarRunbook:
    rows = (
        (
            "load",
            "load the public aggregate fixture",
            "fixture receipt",
            "stop on boundary failure",
        ),
        ("audit", "audit sources and record closure", "data audit receipt", "stop on failed audit"),
        (
            "evaluate",
            "execute all four operation adapters",
            "evaluation receipt",
            "stop on unexpected state",
        ),
        (
            "schema",
            "validate payload and output schemas",
            "schema receipt",
            "stop on missing field",
        ),
        (
            "review",
            "inspect the twelve control rows",
            "review queue receipt",
            "hold unsupported rows",
        ),
        ("replay", "replay the same fixture", "replay receipt", "stop on address drift"),
        (
            "release",
            "build the research-only manifest",
            "release receipt",
            "do not promote clinical meaning",
        ),
        (
            "rollback",
            "retain the previous release target",
            "rollback target",
            "rollback on quality failure",
        ),
    )
    steps = tuple(
        SequenceGrammarRunbookStep(index, *row) for index, row in enumerate(rows, start=1)
    )
    return SequenceGrammarRunbook("sequence-grammar-beta-runbook", "2026.08.v1", steps)


__all__ = [
    "SequenceGrammarRunbook",
    "SequenceGrammarRunbookStep",
    "default_sequence_grammar_runbook",
]

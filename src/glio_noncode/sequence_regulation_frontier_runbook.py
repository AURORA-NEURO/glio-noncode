"""Operational runbook for reviewing a C09-C12 bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationRunbookStep:
    step_id: str
    title: str
    action: str
    evidence: str

    def __post_init__(self) -> None:
        if not self.step_id or not self.title or not self.action or not self.evidence:
            raise ValidationError("runbook step is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationRunbook:
    runbook_id: str
    steps: tuple[SequenceRegulationRunbookStep, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.steps) < 8:
            raise ValidationError("runbook requires at least eight steps")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_sequence_regulation_runbook() -> SequenceRegulationRunbook:
    steps = tuple(
        SequenceRegulationRunbookStep(step_id, title, action, evidence)
        for step_id, title, action, evidence in (
            ("01", "Load", "Load the checked-in public aggregate fixture", "fixture receipt"),
            ("02", "Audit", "Run source, boundary, and count checks", "data audit"),
            ("03", "Schema", "Validate operation fields and context", "schema report"),
            ("04", "Execute", "Run each record through its declared primitive", "adapter results"),
            ("05", "Compare", "Compare positive and control paths", "evaluation report"),
            ("06", "Trace", "Inspect stage and result receipts", "trace events"),
            ("07", "Review", "Route partial, invalid, and boundary rows", "review queue"),
            ("08", "Gate", "Apply quality checks and thresholds", "quality report"),
            ("09", "Bundle", "Assemble portable release artifacts", "bundle receipt"),
            ("10", "Publish", "Publish only an accepted aggregate manifest", "release manifest"),
        )
    )
    return SequenceRegulationRunbook("runbook:sequence-regulation-frontier", steps, True)


__all__ = [
    "SequenceRegulationRunbook",
    "SequenceRegulationRunbookStep",
    "default_sequence_regulation_runbook",
]

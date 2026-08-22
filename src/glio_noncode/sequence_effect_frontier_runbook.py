"""Operational runbook for the sequence-effect frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectRunbookStep:
    step_id: str
    phase: str
    command: str
    success_signal: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectRunbook:
    runbook_id: str
    steps: tuple[SequenceEffectRunbookStep, ...]
    release_boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "runbook_id": self.runbook_id,
                        "steps": self.steps,
                        "release_boundary": self.release_boundary,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "step_count": len(self.steps),
            "steps": [item.to_dict() for item in self.steps],
            "release_boundary": self.release_boundary,
            "content_address": self.content_address,
        }


def default_sequence_effect_runbook() -> SequenceEffectRunbook:
    steps = tuple(
        SequenceEffectRunbookStep(step_id, phase, command, signal, action)
        for step_id, phase, command, signal, action in (
            (
                "01",
                "boundary",
                "sequence-effect-data-audit",
                "accepted=true",
                "hold release and inspect source closure",
            ),
            (
                "02",
                "contracts",
                "sequence-effect-contracts",
                "four operations",
                "repair contract manifest",
            ),
            (
                "03",
                "evaluation",
                "sequence-effect-evaluate",
                "96 checks pass",
                "inspect record-level issue paths",
            ),
            (
                "04",
                "schema",
                "sequence-effect-schema",
                "four schemas",
                "repair field or invariant declaration",
            ),
            (
                "05",
                "quality",
                "sequence-effect-quality-gate",
                "25 checks pass",
                "keep release blocked",
            ),
            (
                "06",
                "replay",
                "sequence-effect-replay",
                "deterministic",
                "compare fixture and execution addresses",
            ),
            (
                "07",
                "review",
                "sequence-effect-review-queue",
                "12 review rows",
                "repair controls before promotion",
            ),
            (
                "08",
                "release",
                "sequence-effect-pipeline",
                "status=ready",
                "do not publish a failed release",
            ),
        )
    )
    return SequenceEffectRunbook(
        "sequence-effect-runbook-v1", steps, "public_aggregate_non_patient"
    )


__all__ = ["SequenceEffectRunbook", "SequenceEffectRunbookStep", "default_sequence_effect_runbook"]

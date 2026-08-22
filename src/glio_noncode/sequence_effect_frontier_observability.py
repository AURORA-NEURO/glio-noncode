"""Structured runtime events and comparison for sequence-effect runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .sequence_effect_frontier_runtime import SequenceEffectRuntimeReport
from .sequence_effect_frontier_views import SequenceEffectView
from .serialization import content_hash, jsonable


class SequenceEffectStage(StrEnum):
    DATA = "data"
    EVALUATION = "evaluation"
    QUALITY = "quality"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class SequenceEffectEvent:
    event_id: str
    stage: SequenceEffectStage
    event_kind: str
    status: str
    address: str
    attributes: dict[str, Any]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "event_id": self.event_id,
                        "stage": self.stage,
                        "event_kind": self.event_kind,
                        "status": self.status,
                        "address": self.address,
                        "attributes": self.attributes,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectTrace:
    run_id: str
    events: tuple[SequenceEffectEvent, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"run_id": self.run_id, "events": self.events, "accepted": self.accepted}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "accepted": self.accepted,
            "event_count": len(self.events),
            "events": [item.to_dict() for item in self.events],
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectRunComparison:
    equivalent: bool
    changed_event_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_effect_trace(
    runtime: SequenceEffectRuntimeReport, view: SequenceEffectView
) -> SequenceEffectTrace:
    events = tuple(
        SequenceEffectEvent(
            f"{runtime.run_id}:{stage.stage_id}",
            SequenceEffectStage.DATA
            if stage.stage_id == "data-boundary"
            else SequenceEffectStage.EVALUATION
            if stage.stage_id == "fixture-evaluation"
            else SequenceEffectStage.QUALITY
            if stage.stage_id
            in {"contracts", "schema", "metrics", "lineage", "policy", "reconciliation"}
            else SequenceEffectStage.RELEASE,
            stage.stage_id,
            stage.status,
            stage.output_address,
            {**stage.counts, "review_count": view.review_count},
        )
        for stage in runtime.stages
    )
    return SequenceEffectTrace(
        runtime.run_id, events, all(event.address.startswith("sha256:") for event in events)
    )


def compare_sequence_effect_runs(
    left: SequenceEffectRuntimeReport, right: SequenceEffectRuntimeReport
) -> SequenceEffectRunComparison:
    changed = ("content-address",) if left.content_address != right.content_address else ()
    return SequenceEffectRunComparison(
        not changed,
        changed,
        content_hash(
            {"left": left.content_address, "right": right.content_address, "changed": changed}
        ),
    )


def sequence_effect_review_budget(
    view: SequenceEffectView, maximum_priority: int = 3
) -> dict[str, Any]:
    eligible = tuple(
        item.record_id for item in view.entries if 0 < item.priority <= maximum_priority
    )
    return {
        "maximum_priority": maximum_priority,
        "eligible_record_ids": list(eligible),
        "eligible_review_count": len(eligible),
        "content_address": content_hash(
            {"maximum_priority": maximum_priority, "eligible": eligible}
        ),
    }


__all__ = [
    "SequenceEffectEvent",
    "SequenceEffectRunComparison",
    "SequenceEffectStage",
    "SequenceEffectTrace",
    "build_sequence_effect_trace",
    "compare_sequence_effect_runs",
    "sequence_effect_review_budget",
]

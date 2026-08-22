"""Structured runtime trace and review budget for the grammar frontier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_runtime import SequenceGrammarRuntimeReport
from .sequence_grammar_frontier_views import SequenceGrammarView
from .serialization import content_hash, jsonable


class SequenceGrammarStage(StrEnum):
    INGEST = "ingest"
    DATA_AUDIT = "data_audit"
    EVALUATE = "evaluate"
    SCHEMA = "schema"
    METRICS = "metrics"
    LINEAGE = "lineage"
    POLICY = "policy"
    RECONCILE = "reconcile"
    QUALITY = "quality"
    RELEASE_READY = "release_ready"


@dataclass(frozen=True, slots=True)
class SequenceGrammarEvent:
    ordinal: int
    stage: SequenceGrammarStage
    status: str
    detail: str
    receipt: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.ordinal < 1 or not self.receipt.startswith("sha256:"):
            raise ValidationError("observability event is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "ordinal": self.ordinal,
                        "stage": self.stage,
                        "status": self.status,
                        "detail": self.detail,
                        "receipt": self.receipt,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarTrace:
    run_id: str
    accepted: bool
    events: tuple[SequenceGrammarEvent, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.events) != 10:
            raise ValidationError("trace requires ten stage events")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"run_id": self.run_id, "accepted": self.accepted, "events": self.events}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "accepted": self.accepted,
            "events": [event.to_dict() for event in self.events],
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceGrammarRunComparison:
    equivalent: bool
    same_receipts: bool
    same_status: bool
    differing_fields: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "equivalent": self.equivalent,
                        "same_receipts": self.same_receipts,
                        "same_status": self.same_status,
                        "differing_fields": self.differing_fields,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_grammar_trace(
    runtime: SequenceGrammarRuntimeReport, view: SequenceGrammarView
) -> SequenceGrammarTrace:
    del view
    events = tuple(
        SequenceGrammarEvent(
            stage.ordinal,
            SequenceGrammarStage(stage.stage_id.replace("-", "_")),
            stage.status,
            stage.detail,
            stage.receipt,
        )
        for stage in runtime.stages
    )
    return SequenceGrammarTrace(runtime.run_id, runtime.accepted, events)


def compare_sequence_grammar_runs(
    first: SequenceGrammarRuntimeReport, second: SequenceGrammarRuntimeReport
) -> SequenceGrammarRunComparison:
    first_receipts = tuple(stage.receipt for stage in first.stages)
    second_receipts = tuple(stage.receipt for stage in second.stages)
    differing = []
    if first_receipts != second_receipts:
        differing.append("stage_receipts")
    if first.status != second.status:
        differing.append("status")
    if first.content_address != second.content_address:
        differing.append("runtime_address")
    return SequenceGrammarRunComparison(
        not differing,
        first_receipts == second_receipts,
        first.status == second.status,
        tuple(differing),
    )


def sequence_grammar_review_budget(view: SequenceGrammarView) -> dict[str, Any]:
    by_priority: dict[str, int] = {}
    for entry in view.entries:
        by_priority[str(entry.priority)] = by_priority.get(str(entry.priority), 0) + 1
    return {
        "fixture_id": view.fixture_id,
        "eligible_review_count": view.review_count,
        "publishable_count": view.publishable_count,
        "by_priority": dict(sorted(by_priority.items())),
        "content_address": content_hash(
            {"fixture_id": view.fixture_id, "by_priority": by_priority}
        ),
    }


__all__ = [
    "SequenceGrammarEvent",
    "SequenceGrammarRunComparison",
    "SequenceGrammarStage",
    "SequenceGrammarTrace",
    "build_sequence_grammar_trace",
    "compare_sequence_grammar_runs",
    "sequence_grammar_review_budget",
]

"""Replay checks for deterministic C09-C12 results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .sequence_regulation_frontier_runtime import (
    SequenceRegulationRuntimeOptions,
    run_sequence_regulation_runtime,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationReplayReport:
    first_address: str
    second_address: str
    record_addresses_equal: bool
    state_paths_equal: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.first_address or not self.second_address:
            raise ValidationError("replay requires two receipts")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_sequence_regulation_evaluation(
    fixture: SequenceRegulationFixture,
) -> SequenceRegulationReplayReport:
    first = run_sequence_regulation_runtime(
        SequenceRegulationRuntimeOptions("replay-one"), fixture=fixture
    )
    second = run_sequence_regulation_runtime(
        SequenceRegulationRuntimeOptions("replay-two"), fixture=fixture
    )
    first_states = tuple(item.observed_state for item in first.evaluation.records)
    second_states = tuple(item.observed_state for item in second.evaluation.records)
    first_addresses = tuple(item.adapter.content_address for item in first.evaluation.records)
    second_addresses = tuple(item.adapter.content_address for item in second.evaluation.records)
    return SequenceRegulationReplayReport(
        first.evaluation.content_address,
        second.evaluation.content_address,
        first_addresses == second_addresses,
        first_states == second_states,
        first.evaluation.accepted
        and second.evaluation.accepted
        and first_addresses == second_addresses,
    )


__all__ = ["SequenceRegulationReplayReport", "replay_sequence_regulation_evaluation"]

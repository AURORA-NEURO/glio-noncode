"""Trace and comparison records for Domain 10 link frontier runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_runtime import LinkFrontierPipeline
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierTraceEvent:
    sequence: int
    stage_id: str
    state: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierTrace:
    fixture_id: str
    run_id: str
    events: tuple[LinkFrontierTraceEvent, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierRunComparison:
    left_run_id: str
    right_run_id: str
    same_stage_ids: bool
    same_states: bool
    same_addresses: bool
    equivalent: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_link_frontier_trace(pipeline: LinkFrontierPipeline, *, run_id: str = "link-ci") -> LinkFrontierTrace:
    events: list[LinkFrontierTraceEvent] = []
    for sequence, stage in enumerate(pipeline.stages, start=1):
        body = {
            "sequence": sequence,
            "stage_id": stage.stage_id,
            "state": stage.state,
            "output_address": stage.output_address,
            "detail": stage.detail,
        }
        events.append(LinkFrontierTraceEvent(**body, content_address=content_hash(body)))
    body = {"fixture_id": pipeline.fixture_id, "run_id": run_id, "events": events, "accepted": pipeline.accepted}
    return LinkFrontierTrace(**body, content_address=content_hash(body))


def compare_link_frontier_runs(left: LinkFrontierTrace, right: LinkFrontierTrace) -> LinkFrontierRunComparison:
    stage_ids_left = tuple(event.stage_id for event in left.events)
    stage_ids_right = tuple(event.stage_id for event in right.events)
    states_left = tuple(event.state for event in left.events)
    states_right = tuple(event.state for event in right.events)
    addresses_left = tuple(event.output_address for event in left.events)
    addresses_right = tuple(event.output_address for event in right.events)
    body = {
        "left_run_id": left.run_id,
        "right_run_id": right.run_id,
        "same_stage_ids": stage_ids_left == stage_ids_right,
        "same_states": states_left == states_right,
        "same_addresses": addresses_left == addresses_right,
        "equivalent": stage_ids_left == stage_ids_right and states_left == states_right and addresses_left == addresses_right,
    }
    return LinkFrontierRunComparison(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierRunComparison", "LinkFrontierTrace", "LinkFrontierTraceEvent", "build_link_frontier_trace", "compare_link_frontier_runs"]

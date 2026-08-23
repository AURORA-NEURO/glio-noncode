"""Bounded release manifest for planning review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .planning_frontier_quality_gate import PlanningQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningRelease:
    release_id: str
    fixture_id: str
    included_records: tuple[str, ...]
    held_records: tuple[str, ...]
    exclusions: tuple[str, ...]
    ready: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_release(fixture: PlanningFixture, evaluation: PlanningEvaluation, quality: PlanningQualityGate, *, release_id: str = "planning-release") -> PlanningRelease:
    included = tuple(item.record_id for item in evaluation.executions if item.observed_state.value == "ready_for_review")
    held = tuple(item.record_id for item in evaluation.executions if item.observed_state.value != "ready_for_review")
    exclusions = ("no efficacy conclusion", "no safety conclusion", "no clinical conclusion", "no institutional approval conclusion")
    body = {"release_id": release_id, "fixture_id": fixture.fixture_id, "included_records": included, "held_records": held, "exclusions": exclusions, "ready": bool(quality.accepted and evaluation.accepted)}
    return PlanningRelease(**body, content_address=content_hash(body, prefix="planning-release"))


__all__ = ["PlanningRelease", "build_planning_release"]

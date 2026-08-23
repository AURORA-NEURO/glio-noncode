"""Reusable typed builder for independently named planning assurance planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningNamedPlane:
    plane_id: str
    category: str
    observed: Any
    required: Any
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_named_planning_plane(
    plane_id: str,
    category: str,
    fixture: PlanningFixture,
    evaluation: PlanningEvaluation,
    predicate: Callable[[PlanningFixture, PlanningEvaluation], bool],
    detail: str,
) -> PlanningNamedPlane:
    observed = bool(predicate(fixture, evaluation))
    body = {"plane_id": plane_id, "category": category, "observed": observed, "required": True, "accepted": observed, "detail": detail}
    return PlanningNamedPlane(**body, content_address=content_hash(body, prefix="planning-named-plane"))


__all__ = ["PlanningNamedPlane", "build_named_planning_plane"]

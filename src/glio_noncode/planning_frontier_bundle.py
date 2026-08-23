"""Content-addressed bundle assembly for a planning run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .planning_frontier_provenance import PlanningProvenance
from .planning_frontier_release import PlanningRelease
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningBundle:
    bundle_id: str
    fixture_address: str
    evaluation_address: str
    provenance_address: str
    release_address: str
    publishable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_planning_bundle(fixture: PlanningFixture, evaluation: PlanningEvaluation, provenance: PlanningProvenance, release: PlanningRelease, *, bundle_id: str = "planning-bundle") -> PlanningBundle:
    body = {"bundle_id": bundle_id, "fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "provenance_address": provenance.content_address, "release_address": release.content_address, "publishable": bool(provenance.closed and release.ready)}
    return PlanningBundle(**body, content_address=content_hash(body, prefix="planning-bundle"))


__all__ = ["PlanningBundle", "assemble_planning_bundle"]

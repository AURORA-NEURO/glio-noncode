"""Release package composition with explicit artifact and exclusion ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture
from .planning_frontier_governance import build_planning_artifact_inventory, build_planning_claim_boundary
from .planning_frontier_provenance import build_planning_provenance
from .planning_frontier_quality_gate import PlanningQualityGate
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningReleasePackage:
    package_id: str
    fixture_id: str
    artifact_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    included_states: tuple[str, ...]
    excluded_claims: tuple[str, ...]
    quality_address: str
    provenance_address: str
    publishable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assemble_planning_release_package(fixture: PlanningFixture, evaluation: PlanningEvaluation, quality: PlanningQualityGate, *, package_id: str = "planning-release-package") -> PlanningReleasePackage:
    inventory = build_planning_artifact_inventory(fixture, evaluation)
    provenance = build_planning_provenance(fixture, evaluation)
    boundary = build_planning_claim_boundary()
    included_states = tuple(dict.fromkeys(item.observed_state.value for item in evaluation.executions))
    body = {
        "package_id": package_id,
        "fixture_id": fixture.fixture_id,
        "artifact_ids": tuple(item["artifact_id"] for item in inventory.artifacts),
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "included_states": included_states,
        "excluded_claims": boundary.excluded_uses,
        "quality_address": quality.content_address,
        "provenance_address": provenance.content_address,
        "publishable": bool(quality.accepted and inventory.accepted and provenance.closed and boundary.accepted),
    }
    return PlanningReleasePackage(**body, content_address=content_hash(body, prefix="planning-release-package"))


__all__ = ["PlanningReleasePackage", "assemble_planning_release_package"]

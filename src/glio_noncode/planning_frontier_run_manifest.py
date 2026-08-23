"""Run manifest with explicit input and implementation identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PLANNING_FRONTIER_VERSION, PlanningFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningRunManifest:
    run_id: str
    contract_version: str
    fixture_id: str
    fixture_address: str
    operation_names: tuple[str, ...]
    stage_policy: tuple[str, ...]
    research_boundary: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_run_manifest(fixture: PlanningFixture, *, run_id: str = "planning-runtime") -> PlanningRunManifest:
    operations = tuple(item.value for item in fixture.operations)
    stages = ("audit", "adapt", "schema", "evaluate", "measure", "quality", "assure", "release")
    body = {"run_id": run_id, "contract_version": PLANNING_FRONTIER_VERSION, "fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "operation_names": operations, "stage_policy": stages, "research_boundary": fixture.evidence_boundary}
    return PlanningRunManifest(**body, content_address=content_hash(body, prefix="planning-run-manifest"))


__all__ = ["PlanningRunManifest", "build_planning_run_manifest"]

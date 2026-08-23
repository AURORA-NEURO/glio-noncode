"""Change-control record for fixture, schema, and policy revisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_schema_migrations import CohortAlphaFrontierMigrationPlan
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierChangeRequest:
    change_id: str
    area: str
    reason: str
    required_checks: tuple[str, ...]
    rollback: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierChangeControl:
    requests: tuple[CohortAlphaFrontierChangeRequest, ...]
    migration_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_change_control(migration: CohortAlphaFrontierMigrationPlan) -> CohortAlphaFrontierChangeControl:
    raw = (("fixture", "public receipt or boundary update", ("schema", "fixture", "replay"), "restore prior fixture version"), ("policy", "claim ceiling or disposition change", ("contracts", "quality", "report"), "restore prior policy"), ("schema", "field or null policy change", ("migration", "dictionary", "CLI"), "restore prior schema"), ("runtime", "stage ordering or output change", ("focused tests", "full suite", "replay"), "restore prior runtime"))
    requests = tuple(CohortAlphaFrontierChangeRequest(f"change-{area}", area, reason, checks, rollback, content_hash({"id": area, "reason": reason, "checks": checks, "rollback": rollback}, prefix="alpha-change")) for area, reason, checks, rollback in raw)
    return CohortAlphaFrontierChangeControl(requests, migration.content_address, migration.accepted and len(requests) == 4 and all(item.required_checks for item in requests), content_hash({"requests": requests, "migration": migration.content_address}, prefix="alpha-change-control"))


__all__ = ["CohortAlphaFrontierChangeControl", "CohortAlphaFrontierChangeRequest", "build_cohort_alpha_frontier_change_control"]

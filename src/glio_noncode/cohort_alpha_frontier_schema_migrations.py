"""Versioned schema migration receipts for C09-C12 payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import C09_C12_FIXTURE_VERSION
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierMigration:
    migration_id: str
    from_version: str
    to_version: str
    operation: str
    changes: tuple[str, ...]
    reversible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierMigrationPlan:
    current_version: str
    target_version: str
    migrations: tuple[CohortAlphaFrontierMigration, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_migrations() -> tuple[CohortAlphaFrontierMigration, ...]:
    raw = (("m01", "2026.08.d12-c09-c12.v0", C09_C12_FIXTURE_VERSION, "C09", ("add source receipt", "add context key")), ("m02", "2026.08.d12-c09-c12.v0", C09_C12_FIXTURE_VERSION, "C10", ("add phase field", "add recurrence comparator")), ("m03", "2026.08.d12-c09-c12.v0", C09_C12_FIXTURE_VERSION, "C11", ("add exposure phase", "add selection threshold")), ("m04", "2026.08.d12-c09-c12.v0", C09_C12_FIXTURE_VERSION, "C12", ("add cohort key", "add concordance threshold")))
    return tuple(CohortAlphaFrontierMigration(f"alpha-{migration_id}", old, new, operation, changes, True, content_hash({"id": migration_id, "old": old, "new": new, "operation": operation, "changes": changes}, prefix="alpha-migration")) for migration_id, old, new, operation, changes in raw)


def build_cohort_alpha_frontier_migration_plan(target_version: str = C09_C12_FIXTURE_VERSION) -> CohortAlphaFrontierMigrationPlan:
    migrations = default_cohort_alpha_frontier_migrations()
    accepted = target_version == C09_C12_FIXTURE_VERSION and all(item.reversible and item.to_version == target_version for item in migrations)
    return CohortAlphaFrontierMigrationPlan("2026.08.d12-c09-c12.v0", target_version, migrations, accepted, content_hash({"target": target_version, "migrations": migrations, "accepted": accepted}, prefix="alpha-migration-plan"))


__all__ = ["CohortAlphaFrontierMigration", "CohortAlphaFrontierMigrationPlan", "build_cohort_alpha_frontier_migration_plan", "default_cohort_alpha_frontier_migrations"]

"""Forward-compatible schema migration receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSchemaMigration:
    migration_id: str
    from_version: str
    to_version: str
    additions: tuple[str, ...]
    breaking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierSchemaMigrationReport:
    migrations: tuple[CohortBetaFrontierSchemaMigration, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_schema_migration_report() -> CohortBetaFrontierSchemaMigrationReport:
    values = tuple(CohortBetaFrontierSchemaMigration(f"c05-c08-v{version}-to-v{version + 1}", str(version), str(version + 1), additions, False, content_hash({"version": version, "additions": additions}, prefix="migration")) for version, additions in ((1, ("source_version",)), (2, ("content_address",)), (3, ("policy_disposition",))))
    return CohortBetaFrontierSchemaMigrationReport(values, all(not item.breaking for item in values), content_hash(values, prefix="migration-report"))


__all__ = ["CohortBetaFrontierSchemaMigration", "CohortBetaFrontierSchemaMigrationReport", "build_cohort_beta_frontier_schema_migration_report"]

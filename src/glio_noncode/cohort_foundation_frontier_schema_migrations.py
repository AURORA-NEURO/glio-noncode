"""Schema version and compatibility receipts for future fixture evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFoundationSchemaMigration:
    migration_id: str
    from_version: str
    to_version: str
    added_fields: tuple[str, ...]
    retained_fields: tuple[str, ...]
    removed_fields: tuple[str, ...]
    backward_compatible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationSchemaMigrationReport:
    report_id: str
    current_version: str
    migrations: tuple[CohortFoundationSchemaMigration, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_schema_migrations() -> tuple[CohortFoundationSchemaMigration, ...]:
    definitions = (
        ("cohort-foundation-v1-0-to-v1-1", "1.0.0", "1.1.0", ("source_version", "aggregate_boundary"), ("context_key", "source_ids", "expected_state"), (), True),
        ("cohort-foundation-v1-1-to-v1-2", "1.1.0", "1.2.0", ("policy_disposition", "review_roles"), ("source_version", "aggregate_boundary", "context_key"), (), True),
        ("cohort-foundation-v1-2-to-v2-0", "1.2.0", "2.0.0", ("trace_steps", "content_address"), ("policy_disposition", "review_roles", "context_key"), ("legacy_note"), False),
    )
    return tuple(CohortFoundationSchemaMigration(migration_id, from_version, to_version, added, retained, removed if isinstance(removed, tuple) else (removed,), compatible, content_hash((migration_id, from_version, to_version, added, retained, removed, compatible))) for migration_id, from_version, to_version, added, retained, removed, compatible in definitions)


def build_cohort_foundation_frontier_schema_migration_report() -> CohortFoundationSchemaMigrationReport:
    migrations = default_cohort_foundation_frontier_schema_migrations()
    body = {"report_id": "cohort-foundation-frontier-schema-migrations", "current_version": migrations[-1].to_version, "migrations": migrations}
    return CohortFoundationSchemaMigrationReport(body["report_id"], migrations[-1].to_version, migrations, all(item.from_version != item.to_version for item in migrations), content_hash(body))


__all__ = ["CohortFoundationSchemaMigration", "CohortFoundationSchemaMigrationReport", "build_cohort_foundation_frontier_schema_migration_report", "default_cohort_foundation_frontier_schema_migrations"]

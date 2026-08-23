"""Explicit schema migration receipts for future fixture evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import VALIDATION_RELEASE_FRONTIER_VERSION


@dataclass(frozen=True, slots=True)
class ValidationReleaseContractMigration:
    migration_id: str
    from_version: str
    to_version: str
    operations: tuple[str, ...]
    reversible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseMigrationReport:
    migrations: tuple[ValidationReleaseContractMigration, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_contract_migrations() -> ValidationReleaseMigrationReport:
    body = {"migration_id": "d13-c13-c16-v1", "from_version": "2026.08.d13-c13-c16.v0", "to_version": VALIDATION_RELEASE_FRONTIER_VERSION, "operations": ("off_target_risk", "value_of_information", "experiment_package", "claim_update"), "reversible": True}
    migration = ValidationReleaseContractMigration(**body, content_address=content_hash(body))
    return ValidationReleaseMigrationReport((migration,), migration.reversible, content_hash((migration,)))


__all__ = ["ValidationReleaseContractMigration", "ValidationReleaseMigrationReport", "build_validation_release_contract_migrations"]

"""Explicit compatibility checks for future D08 fixture revisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cell_state_architecture_contracts import CELL_STATE_ARCHITECTURE_VERSION
from .cell_state_architecture_schema import normalize_cell_state_architecture_mapping

D08_MIGRATION_ID = "d08-cell-state-architecture-migration.v1"


def current_cell_state_architecture_migration() -> dict[str, Any]:
    return {
        "migration_id": D08_MIGRATION_ID,
        "from_versions": (CELL_STATE_ARCHITECTURE_VERSION,),
        "to_version": CELL_STATE_ARCHITECTURE_VERSION,
        "operations": (
            "preserve enum values",
            "preserve content addresses",
            "reject unknown boundary",
        ),
        "reversible": True,
    }


def migrate_cell_state_architecture_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = normalize_cell_state_architecture_mapping(raw)
    if value.get("version") != CELL_STATE_ARCHITECTURE_VERSION:
        raise ValueError(f"unsupported D08 version: {value.get('version')}")
    return value


def migration_is_identity(raw: Mapping[str, Any]) -> bool:
    return migrate_cell_state_architecture_mapping(
        raw
    ) == normalize_cell_state_architecture_mapping(raw)


__all__ = [
    "D08_MIGRATION_ID",
    "current_cell_state_architecture_migration",
    "migrate_cell_state_architecture_mapping",
    "migration_is_identity",
]

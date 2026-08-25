"""Public-key, path, and payload boundary checks for program handoffs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .module_fabric_support import contains_private_key
from .program_runtime_offline_bundle import (
    PROGRAM_RUNTIME_OFFLINE_FORBIDDEN_KEYS,
    public_program_projection,
)
from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .serialization import content_hash, jsonable


def _keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        found = {str(key) for key in value}
        for item in value.values():
            found.update(_keys(item))
        return found
    if isinstance(value, (list, tuple)):
        found: set[str] = set()
        for item in value:
            found.update(_keys(item))
        return found
    return set()


def _values(bundle: ProgramRuntimeOfflineBundle) -> list[Any]:
    values: list[Any] = []
    for artifact in bundle.artifacts:
        if artifact.media_type == "application/json":
            try:
                values.append(json.loads(artifact.payload or "{}"))
            except json.JSONDecodeError:
                values.append({"invalid_json": True})
    return values


def program_runtime_offline_key_inventory(bundle: ProgramRuntimeOfflineBundle) -> dict[str, Any]:
    """Return a deterministic key inventory for boundary review."""

    found: set[str] = set()
    for value in _values(bundle):
        found.update(_keys(value))
    forbidden = tuple(
        sorted(key for key in found if key.casefold() in PROGRAM_RUNTIME_OFFLINE_FORBIDDEN_KEYS)
    )
    return {
        "bundle_id": bundle.bundle_id,
        "keys": tuple(sorted(found)),
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
        "content_address": content_hash(
            {
                "bundle_id": bundle.bundle_id,
                "keys": tuple(sorted(found)),
                "forbidden_keys": forbidden,
            },
            prefix="program-runtime-offline-key-inventory",
        ),
    }


def audit_program_runtime_offline_boundary(bundle: ProgramRuntimeOfflineBundle) -> dict[str, Any]:
    """Audit public projection, private-key absence, and relative paths."""

    inventory = program_runtime_offline_key_inventory(bundle)
    path_checks = {
        "relative": all(
            not item.relative_path.startswith(("/", "\\")) for item in bundle.artifacts
        ),
        "no_parent": all(".." not in item.relative_path.split("/") for item in bundle.artifacts),
        "unique": len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count,
        "non_empty": all(item.relative_path and item.artifact_id for item in bundle.artifacts),
    }
    projection_checks = []
    for artifact in bundle.artifacts:
        if artifact.media_type != "application/json":
            continue
        try:
            value = json.loads(artifact.payload or "{}")
            projected = public_program_projection(value)
            projection_checks.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "accepted": projected == value and not contains_private_key(value),
                    "key_count": len(_keys(value)),
                }
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            projection_checks.append(
                {"artifact_id": artifact.artifact_id, "accepted": False, "key_count": 0}
            )
    accepted = (
        bool(inventory["accepted"])
        and all(path_checks.values())
        and all(item["accepted"] for item in projection_checks)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "inventory": inventory,
        "path_checks": path_checks,
        "projection_checks": projection_checks,
        "accepted": accepted,
    }
    return jsonable(
        body | {"content_address": content_hash(body, prefix="program-runtime-offline-boundary")}
    )


__all__ = ["audit_program_runtime_offline_boundary", "program_runtime_offline_key_inventory"]

"""Stable cache and rebuild observations for the module workbench."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_OBSERVABILITY_VERSION = "module-workbench-observability-v1"
MODULE_WORKBENCH_REBUILD_MODES = frozenset({"snapshot", "incremental", "full"})


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchObservability:
    """A bounded, timestamp-free explanation of the current workbench build."""

    rebuild_mode: str
    cache_hit: bool
    source_file_count: int
    test_file_count: int
    module_count: int
    task_count: int
    reused_module_count: int
    reparsed_module_count: int
    inventory_address: str
    certification_address: str
    lineage_address: str
    quality_address: str
    workbench_address: str
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.rebuild_mode not in MODULE_WORKBENCH_REBUILD_MODES:
            raise ValidationError("module workbench rebuild mode is invalid")
        if self.reused_module_count + self.reparsed_module_count != self.module_count:
            raise ValidationError("module workbench reuse counts must equal module count")
        for name in (
            "source_file_count",
            "test_file_count",
            "module_count",
            "task_count",
            "reused_module_count",
            "reparsed_module_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or value < 0:
                raise ValidationError(f"module workbench observability {name} cannot be negative")
        for name in (
            "inventory_address",
            "certification_address",
            "lineage_address",
            "quality_address",
            "workbench_address",
            "content_address",
        ):
            if not getattr(self, name).strip():
                raise ValidationError(f"module workbench observability {name} is required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_module_workbench_observability(
    *,
    rebuild_mode: str,
    cache_hit: bool,
    source_file_count: int,
    test_file_count: int,
    module_count: int,
    task_count: int,
    reused_module_count: int,
    reparsed_module_count: int,
    inventory_address: str,
    certification_address: str,
    lineage_address: str,
    quality_address: str,
    workbench_address: str,
    accepted: bool,
) -> ModuleWorkbenchObservability:
    """Build an addressed observation from server-local build facts."""

    body = {
        "rebuild_mode": rebuild_mode,
        "cache_hit": cache_hit,
        "source_file_count": source_file_count,
        "test_file_count": test_file_count,
        "module_count": module_count,
        "task_count": task_count,
        "reused_module_count": reused_module_count,
        "reparsed_module_count": reparsed_module_count,
        "inventory_address": inventory_address,
        "certification_address": certification_address,
        "lineage_address": lineage_address,
        "quality_address": quality_address,
        "workbench_address": workbench_address,
        "accepted": accepted,
    }
    return ModuleWorkbenchObservability(
        **body,
        content_address=content_hash(body, prefix="module-workbench-observability"),
    )


def module_workbench_observability_schema() -> dict[str, Any]:
    """Return the public field contract for the observability projection."""

    return {
        "version": MODULE_WORKBENCH_OBSERVABILITY_VERSION,
        "fields": list(ModuleWorkbenchObservability.__dataclass_fields__),
        "rebuild_modes": sorted(MODULE_WORKBENCH_REBUILD_MODES),
        "timestamp_free": True,
        "filesystem_paths": False,
        "read_only": True,
    }


def module_workbench_observability_capabilities() -> dict[str, Any]:
    """Describe the bounded read-only operations exposed by this projection."""

    operations = ("inspect_cache_mode", "inspect_reuse_counts", "inspect_addresses")
    return {
        "version": MODULE_WORKBENCH_OBSERVABILITY_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "timestamp_free": True,
        "filesystem_paths": False,
        "read_only": True,
    }


def module_workbench_observability_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchObservability:
    """Validate a serialized observation before a caller stores or forwards it."""

    fields = set(ModuleWorkbenchObservability.__dataclass_fields__)
    if set(value) != fields:
        raise ValidationError("module workbench observability fields are invalid")
    return ModuleWorkbenchObservability(**dict(value))


__all__ = [
    "MODULE_WORKBENCH_OBSERVABILITY_VERSION",
    "MODULE_WORKBENCH_REBUILD_MODES",
    "ModuleWorkbenchObservability",
    "build_module_workbench_observability",
    "module_workbench_observability_capabilities",
    "module_workbench_observability_from_mapping",
    "module_workbench_observability_schema",
]

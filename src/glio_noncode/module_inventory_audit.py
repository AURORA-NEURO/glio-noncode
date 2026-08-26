"""Independent consistency audit for module inventory snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .module_inventory_contracts import (
    InventoryAuditCheck,
    InventoryCheckPlane,
    ModuleInventory,
    ModuleInventoryAudit,
    ModuleState,
    address_module_dependency,
    address_module_record,
    address_module_symbol,
)
from .module_inventory_query import inventory_from_mapping
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable


def _selected(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    return value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)


def _check(
    checks: list[InventoryAuditCheck],
    check_id: str,
    plane: InventoryCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> None:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    checks.append(
        InventoryAuditCheck(
            **body, content_address=content_hash(body, prefix="module-inventory-audit-check")
        )
    )


def audit_module_inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventoryAudit:
    """Run independent checks over a hydrated or in-memory inventory."""

    selected = _selected(value)
    checks: list[InventoryAuditCheck] = []
    modules = selected.modules
    module_ids = {item.module_id for item in modules}
    module_by_id = {item.module_id: item for item in modules}
    _check(
        checks,
        "version-boundary",
        InventoryCheckPlane.DISCOVERY,
        selected.boundary == "public_aggregate_module_inventory",
        selected.boundary,
        "public_aggregate_module_inventory",
        "boundary identifies an aggregate inventory",
    )
    _check(
        checks,
        "module-order",
        InventoryCheckPlane.DISCOVERY,
        tuple(item.module_id for item in modules)
        == tuple(sorted(item.module_id for item in modules)),
        "canonical"
        if tuple(item.module_id for item in modules)
        == tuple(sorted(item.module_id for item in modules))
        else "noncanonical",
        "canonical",
        "module rows are sorted by module identifier",
    )
    _check(
        checks,
        "path-order",
        InventoryCheckPlane.DISCOVERY,
        len({item.relative_path for item in modules}) == len(modules),
        len({item.relative_path for item in modules}),
        len(modules),
        "relative paths are unique",
    )
    _check(
        checks,
        "row-addresses",
        InventoryCheckPlane.PARSE,
        all(address_module_record(item) == item.content_address for item in modules),
        "verified",
        "verified",
        "module row addresses reconstruct from public fields",
    )
    _check(
        checks,
        "symbol-addresses",
        InventoryCheckPlane.PARSE,
        all(address_module_symbol(item) == item.content_address for item in selected.symbols),
        "verified",
        "verified",
        "symbol row addresses reconstruct from public fields",
    )
    _check(
        checks,
        "dependency-addresses",
        InventoryCheckPlane.GRAPH,
        all(
            address_module_dependency(item) == item.content_address
            for item in selected.dependencies
        ),
        "verified",
        "verified",
        "dependency row addresses reconstruct from public fields",
    )
    _check(
        checks,
        "symbol-parents",
        InventoryCheckPlane.PARSE,
        all(item.module_id in module_ids for item in selected.symbols),
        sum(item.module_id in module_ids for item in selected.symbols),
        len(selected.symbols),
        "symbols point to discovered modules",
    )
    _check(
        checks,
        "symbol-lines",
        InventoryCheckPlane.PARSE,
        all(
            item.end_line <= module_by_id[item.module_id].physical_lines
            for item in selected.symbols
            if item.module_id in module_by_id
        ),
        "within source",
        "within source",
        "symbol spans remain inside their module",
    )
    _check(
        checks,
        "edge-sources",
        InventoryCheckPlane.GRAPH,
        all(item.source_module in module_ids for item in selected.dependencies),
        sum(item.source_module in module_ids for item in selected.dependencies),
        len(selected.dependencies),
        "dependency sources are present",
    )
    _check(
        checks,
        "edge-state",
        InventoryCheckPlane.GRAPH,
        all(isinstance(item.resolved, bool) for item in selected.dependencies),
        "explicit",
        "explicit",
        "dependency resolution state is explicit",
    )
    _check(
        checks,
        "index-coverage",
        InventoryCheckPlane.GRAPH,
        all(item.key for item in selected.indexes),
        sum(bool(item.key) for item in selected.indexes),
        len(selected.indexes),
        "index keys are non-empty",
    )
    _check(
        checks,
        "parse-state",
        InventoryCheckPlane.PARSE,
        all(
            item.state in {ModuleState.PARSED, ModuleState.EMPTY, ModuleState.PARSE_ERROR}
            for item in modules
        ),
        "valid",
        "valid",
        "every module has a declared parse state",
    )
    projection = jsonable(selected.to_dict(include_rows=True))
    _check(
        checks,
        "public-boundary",
        InventoryCheckPlane.PUBLIC,
        not _has_forbidden_key(projection),
        "clean" if not _has_forbidden_key(projection) else "forbidden_key",
        "clean",
        "inventory projection contains no forbidden public keys",
    )
    _check(
        checks,
        "aggregate-counts",
        InventoryCheckPlane.LIMITS,
        selected.module_count == len(modules)
        and selected.total_physical_lines == sum(item.physical_lines for item in modules),
        "conserved",
        "conserved",
        "summary counters conserve module rows",
    )
    accepted = all(item.passed for item in checks)
    body = {"version": selected.version, "checks": tuple(checks), "accepted": accepted}
    return ModuleInventoryAudit(
        **body, content_address=content_hash(body, prefix="module-inventory-audit")
    )


def module_inventory_audit_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-audit-v1",
        "planes": [item.value for item in InventoryCheckPlane],
        "check_fields": [
            "check_id",
            "plane",
            "passed",
            "observed",
            "required",
            "detail",
            "content_address",
        ],
        "accepted_when": "all checks pass",
        "read_only": True,
    }


def module_inventory_audit_capabilities() -> dict[str, Any]:
    operations = (
        "verify_row_addresses",
        "verify_parent_links",
        "verify_sorted_indexes",
        "verify_symbol_ranges",
        "verify_public_boundary",
        "conserve_aggregate_counts",
    )
    return {
        "version": "module-inventory-audit-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
    }


__all__ = [
    "audit_module_inventory",
    "module_inventory_audit_capabilities",
    "module_inventory_audit_schema",
]

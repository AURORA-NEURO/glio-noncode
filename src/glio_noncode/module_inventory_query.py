"""Bounded query, hydration, and structural diff operations for inventories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_inventory_contracts import (
    MODULE_INVENTORY_DEFAULT_LIMIT,
    MODULE_INVENTORY_MAX_LIMIT,
    InventoryAuditCheck,
    InventoryCheckPlane,
    InventoryIndexRow,
    InventoryIssue,
    InventoryResource,
    ModuleDependency,
    ModuleInventory,
    ModuleInventoryAudit,
    ModuleInventoryDiff,
    ModuleInventoryQueryResult,
    ModuleRecord,
    ModuleRole,
    ModuleState,
    ModuleSymbol,
)
from .serialization import canonical_json, content_hash


def _enum(value: Any, kind: type) -> Any:
    try:
        return kind(str(value))
    except ValueError as exc:
        raise ValidationError(f"invalid inventory enum value: {value!r}") from exc


def _record(value: Mapping[str, Any]) -> ModuleRecord:
    raw = dict(value)
    raw.pop("density", None)
    return ModuleRecord(
        module_id=str(raw.get("module_id", "")),
        relative_path=str(raw.get("relative_path", "")),
        package=str(raw.get("package", "")),
        family=str(raw.get("family", "")),
        role=_enum(raw.get("role", ModuleRole.SUPPORT.value), ModuleRole),
        state=_enum(raw.get("state", ModuleState.PARSE_ERROR.value), ModuleState),
        physical_lines=int(raw.get("physical_lines", 0)),
        nonblank_lines=int(raw.get("nonblank_lines", 0)),
        comment_lines=int(raw.get("comment_lines", 0)),
        public_symbol_count=int(raw.get("public_symbol_count", 0)),
        class_count=int(raw.get("class_count", 0)),
        function_count=int(raw.get("function_count", 0)),
        import_count=int(raw.get("import_count", 0)),
        local_dependency_count=int(raw.get("local_dependency_count", 0)),
        test_reference_count=int(raw.get("test_reference_count", 0)),
        source_digest=str(raw.get("source_digest", "")),
        content_address=str(raw.get("content_address", "")),
    )


def _symbol(value: Mapping[str, Any]) -> ModuleSymbol:
    return ModuleSymbol(
        module_id=str(value.get("module_id", "")),
        name=str(value.get("name", "")),
        kind=str(value.get("kind", "")),
        line=int(value.get("line", 0)),
        end_line=int(value.get("end_line", 0)),
        public=bool(value.get("public", False)),
        content_address=str(value.get("content_address", "")),
    )


def _dependency(value: Mapping[str, Any]) -> ModuleDependency:
    return ModuleDependency(
        source_module=str(value.get("source_module", "")),
        target_module=str(value.get("target_module", "")),
        import_name=str(value.get("import_name", "")),
        relative=bool(value.get("relative", False)),
        resolved=bool(value.get("resolved", False)),
        content_address=str(value.get("content_address", "")),
    )


def _issue(value: Mapping[str, Any]) -> InventoryIssue:
    return InventoryIssue(
        issue_id=str(value.get("issue_id", "")),
        relative_path=str(value.get("relative_path", "")),
        code=str(value.get("code", "")),
        severity=str(value.get("severity", "error")),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "")),
    )


def _index(value: Mapping[str, Any]) -> InventoryIndexRow:
    return InventoryIndexRow(
        index_name=str(value.get("index_name", "")),
        key=str(value.get("key", "")),
        values=tuple(str(item) for item in value.get("values", ())),
        content_address=str(value.get("content_address", "")),
    )


def inventory_from_mapping(value: Mapping[str, Any]) -> ModuleInventory:
    """Hydrate a complete JSON inventory without reading source files."""

    if not isinstance(value, Mapping):
        raise ValidationError("module inventory must be an object")
    raw_audit = value.get("audit")
    if not isinstance(raw_audit, Mapping):
        raise ValidationError("module inventory audit is required")
    raw_checks = raw_audit.get("checks", ())
    checks = tuple(
        InventoryAuditCheck(
            check_id=str(item.get("check_id", "")),
            plane=_enum(
                item.get("plane", "public"),
                InventoryCheckPlane,
            ),
            passed=bool(item.get("passed", False)),
            observed=item.get("observed"),
            required=item.get("required"),
            detail=str(item.get("detail", "")),
            content_address=str(item.get("content_address", "")),
        )
        for item in raw_checks
        if isinstance(item, Mapping)
    )
    audit = ModuleInventoryAudit(
        version=str(raw_audit.get("version", "")),
        checks=checks,
        accepted=bool(raw_audit.get("accepted", False)),
        content_address=str(raw_audit.get("content_address", "")),
    )
    return ModuleInventory(
        version=str(value.get("version", "")),
        boundary=str(value.get("boundary", "")),
        root_label=str(value.get("root_label", "")),
        modules=tuple(
            _record(item) for item in value.get("modules", ()) if isinstance(item, Mapping)
        ),
        symbols=tuple(
            _symbol(item) for item in value.get("symbols", ()) if isinstance(item, Mapping)
        ),
        dependencies=tuple(
            _dependency(item) for item in value.get("dependencies", ()) if isinstance(item, Mapping)
        ),
        issues=tuple(_issue(item) for item in value.get("issues", ()) if isinstance(item, Mapping)),
        indexes=tuple(
            _index(item) for item in value.get("indexes", ()) if isinstance(item, Mapping)
        ),
        audit=audit,
        accepted=bool(value.get("accepted", False)),
        content_address=str(value.get("content_address", "")),
    )


def _as_inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    return value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)


def _match(value: Mapping[str, Any], text: str | None) -> bool:
    return not text or str(text).casefold() in canonical_json(value).casefold()


def _rows(value: ModuleInventory, resource: InventoryResource) -> list[Mapping[str, Any]]:
    if resource is InventoryResource.MODULES:
        return [item.to_dict() for item in value.modules]
    if resource is InventoryResource.SYMBOLS:
        return [item.to_dict() for item in value.symbols]
    if resource is InventoryResource.DEPENDENCIES:
        return [item.to_dict() for item in value.dependencies]
    if resource is InventoryResource.ISSUES:
        return [item.to_dict() for item in value.issues]
    return [item.to_dict() for item in value.indexes]


def query_module_inventory(
    inventory: ModuleInventory | Mapping[str, Any],
    *,
    resource: str = "modules",
    module_id: str | None = None,
    family: str | None = None,
    role: str | None = None,
    state: str | None = None,
    symbol: str | None = None,
    target_module: str | None = None,
    index_name: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_INVENTORY_DEFAULT_LIMIT,
) -> ModuleInventoryQueryResult:
    """Return a stable page over one inventory resource."""

    value = _as_inventory(inventory)
    try:
        selected_resource = InventoryResource(str(resource).casefold())
    except ValueError as exc:
        raise ValidationError(f"unsupported module inventory resource: {resource}") from exc
    if offset < 0:
        raise ValidationError("module inventory offset cannot be negative")
    if limit < 1 or limit > MODULE_INVENTORY_MAX_LIMIT:
        raise ValidationError(
            f"module inventory limit must be between 1 and {MODULE_INVENTORY_MAX_LIMIT}"
        )
    items = _rows(value, selected_resource)
    index_used: str | None = None
    if selected_resource is InventoryResource.MODULES:
        if module_id is not None:
            items = [item for item in items if item.get("module_id") == module_id]
            index_used = "module_id"
        if family is not None:
            items = [item for item in items if item.get("family") == family]
            index_used = "family"
        if role is not None:
            items = [item for item in items if item.get("role") == role]
            index_used = "role" if index_used is None else f"{index_used}+role"
        if state is not None:
            items = [item for item in items if item.get("state") == state]
            index_used = "state" if index_used is None else f"{index_used}+state"
    elif selected_resource is InventoryResource.SYMBOLS:
        if module_id is not None:
            items = [item for item in items if item.get("module_id") == module_id]
            index_used = "module_id"
        if symbol is not None:
            items = [item for item in items if item.get("name") == symbol]
            index_used = "symbol" if index_used is None else f"{index_used}+symbol"
    elif selected_resource is InventoryResource.DEPENDENCIES:
        if module_id is not None:
            items = [item for item in items if item.get("source_module") == module_id]
            index_used = "source_module"
        if target_module is not None:
            items = [item for item in items if item.get("target_module") == target_module]
            index_used = (
                "dependency_target" if index_used is None else f"{index_used}+dependency_target"
            )
    elif selected_resource is InventoryResource.INDEXES and index_name is not None:
        items = [item for item in items if item.get("index_name") == index_name]
        index_used = "index_name"
    if text:
        items = [item for item in items if _match(item, text)]
    selected = tuple(items[offset : offset + limit])
    query = {
        "resource": selected_resource,
        "module_id": module_id,
        "family": family,
        "role": role,
        "state": state,
        "symbol": symbol,
        "target_module": target_module,
        "index_name": index_name,
        "text": text,
    }
    body = {
        "resource": selected_resource,
        "query": query,
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "items": selected,
        "index_used": index_used,
        "accepted": value.accepted,
    }
    return ModuleInventoryQueryResult(
        **body, content_address=content_hash(body, prefix="module-inventory-query")
    )


def _dependency_key(item: ModuleDependency) -> str:
    return f"{item.source_module}|{item.target_module}|{item.import_name}"


def diff_module_inventories(
    left: ModuleInventory | Mapping[str, Any],
    right: ModuleInventory | Mapping[str, Any],
) -> ModuleInventoryDiff:
    """Compare content addresses and dependency edges, not machine paths."""

    left_value = _as_inventory(left)
    right_value = _as_inventory(right)
    left_modules = {item.module_id: item for item in left_value.modules}
    right_modules = {item.module_id: item for item in right_value.modules}
    common = set(left_modules) & set(right_modules)
    changed = tuple(
        sorted(
            item
            for item in common
            if left_modules[item].source_digest != right_modules[item].source_digest
            or left_modules[item].content_address != right_modules[item].content_address
        )
    )
    left_dependencies = {_dependency_key(item): item for item in left_value.dependencies}
    right_dependencies = {_dependency_key(item): item for item in right_value.dependencies}
    summary_fields = tuple(
        field
        for field in (
            "module_count",
            "total_physical_lines",
            "total_nonblank_lines",
            "total_public_symbols",
            "dependency_count",
            "issue_count",
        )
        if left_value.summary().get(field) != right_value.summary().get(field)
    )
    body = {
        "left_address": left_value.content_address,
        "right_address": right_value.content_address,
        "added_modules": tuple(sorted(set(right_modules) - set(left_modules))),
        "removed_modules": tuple(sorted(set(left_modules) - set(right_modules))),
        "changed_modules": changed,
        "unchanged_modules": tuple(sorted(common - set(changed))),
        "added_dependencies": tuple(sorted(set(right_dependencies) - set(left_dependencies))),
        "removed_dependencies": tuple(sorted(set(left_dependencies) - set(right_dependencies))),
        "changed_summary_fields": summary_fields,
        "accepted": left_value.accepted and right_value.accepted,
    }
    return ModuleInventoryDiff(
        **body, content_address=content_hash(body, prefix="module-inventory-diff")
    )


__all__ = ["diff_module_inventories", "inventory_from_mapping", "query_module_inventory"]

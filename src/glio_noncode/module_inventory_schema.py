"""Schema declaration and validation for module inventory payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_inventory import module_inventory_schema as _base_schema
from .module_inventory_contracts import ModuleInventory
from .module_inventory_query import inventory_from_mapping
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleInventorySchemaField:
    """One public field declaration."""

    name: str
    value_type: str
    required: bool
    description: str
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.name.strip()
            or not self.value_type.strip()
            or not self.description.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module inventory schema field is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventorySchemaReport:
    """Schema validation result with explicit issue codes."""

    version: str
    checks: tuple[Mapping[str, Any], ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.content_address.strip():
            raise ValidationError("module inventory schema report requires an address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "checks": [dict(item) for item in self.checks],
            "check_count": len(self.checks),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def default_module_inventory_schema() -> dict[str, Any]:
    """Return a full field-level schema suitable for clients and fixtures."""

    base = _base_schema()
    fields = tuple(
        ModuleInventorySchemaField(
            name=name,
            value_type="integer" if name.endswith("count") or name.endswith("lines") else "string",
            required=True,
            description=f"Canonical public inventory field: {name}.",
            content_address=content_hash(
                {
                    "name": name,
                    "value_type": "integer"
                    if name.endswith("count") or name.endswith("lines")
                    else "string",
                    "required": True,
                },
                prefix="module-inventory-schema-field",
            ),
        )
        for name in base["module_fields"]
    )
    return base | {
        "schema_version": "module-inventory-schema-v1",
        "fields": [item.to_dict() for item in fields],
        "field_count": len(fields),
    }


def _check(
    checks: list[Mapping[str, Any]],
    code: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "code": code,
            "passed": bool(passed),
            "observed": observed,
            "required": required,
            "detail": detail,
        }
    )


def validate_module_inventory_schema(
    value: ModuleInventory | Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> ModuleInventorySchemaReport:
    """Validate presence and type-level invariants without source execution."""

    inventory = value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)
    selected = schema or default_module_inventory_schema()
    checks: list[Mapping[str, Any]] = []
    _check(
        checks,
        "schema-version",
        selected.get("schema_version") == "module-inventory-schema-v1",
        selected.get("schema_version"),
        "module-inventory-schema-v1",
        "schema version is supported",
    )
    _check(
        checks,
        "boundary",
        selected.get("boundary") == inventory.boundary,
        selected.get("boundary"),
        inventory.boundary,
        "schema boundary matches inventory",
    )
    fields = selected.get("fields", ())
    names = tuple(item.get("name") for item in fields if isinstance(item, Mapping))
    required_names = tuple(str(item) for item in selected.get("module_fields", ()))
    _check(
        checks,
        "field-coverage",
        set(required_names).issubset(set(names)),
        len(set(required_names) & set(names)),
        len(set(required_names)),
        "schema declares all module fields",
    )
    _check(
        checks,
        "module-row-shape",
        all(item.module_id and item.content_address for item in inventory.modules),
        sum(bool(item.module_id and item.content_address) for item in inventory.modules),
        len(inventory.modules),
        "module rows satisfy required identifiers",
    )
    _check(
        checks,
        "resource-shape",
        isinstance(inventory.symbols, tuple)
        and isinstance(inventory.dependencies, tuple)
        and isinstance(inventory.indexes, tuple),
        "tuple",
        "tuple",
        "resource collections are bounded typed rows",
    )
    accepted = all(bool(item.get("passed")) for item in checks)
    body = {"version": "module-inventory-schema-v1", "checks": tuple(checks), "accepted": accepted}
    return ModuleInventorySchemaReport(
        **body, content_address=content_hash(body, prefix="module-inventory-schema-report")
    )


def module_inventory_schema_capabilities() -> dict[str, Any]:
    operations = (
        "declare_module_fields",
        "declare_resource_collections",
        "validate_schema_version",
        "validate_field_coverage",
        "validate_row_shape",
    )
    return {
        "version": "module-inventory-schema-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
    }


__all__ = [
    "ModuleInventorySchemaField",
    "ModuleInventorySchemaReport",
    "default_module_inventory_schema",
    "module_inventory_schema_capabilities",
    "validate_module_inventory_schema",
]

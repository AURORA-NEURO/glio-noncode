"""Schema diff and compatibility classification for platform releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_schema import PlatformFrontierSchema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierSchemaDiff:
    added_fields: tuple[str, ...]
    removed_fields: tuple[str, ...]
    changed_fields: tuple[str, ...]
    compatible: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diff_platform_frontier_schema(before: PlatformFrontierSchema, after: PlatformFrontierSchema) -> PlatformFrontierSchemaDiff:
    left = {f"{operation}:{field.name}": field.type_name for operation, fields in before.operation_fields.items() for field in fields}
    right = {f"{operation}:{field.name}": field.type_name for operation, fields in after.operation_fields.items() for field in fields}
    added = tuple(sorted(set(right) - set(left)))
    removed = tuple(sorted(set(left) - set(right)))
    changed = tuple(sorted(key for key in set(left) & set(right) if left[key] != right[key]))
    body = {"added_fields": added, "removed_fields": removed, "changed_fields": changed, "compatible": not removed and not changed}
    return PlatformFrontierSchemaDiff(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierSchemaDiff", "diff_platform_frontier_schema"]

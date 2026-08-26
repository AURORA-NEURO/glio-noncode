"""Typed contracts for the repository-wide module inventory.

The inventory is a static, read-only view over source files that belong to the
local package.  It never imports source modules and never executes discovered
symbols.  Every row is content addressed so that a source snapshot can be
compared without relying on machine-specific absolute paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_INVENTORY_VERSION = "module-inventory-v1"
MODULE_INVENTORY_BOUNDARY = "public_aggregate_module_inventory"
MODULE_INVENTORY_MAX_MODULES = 8_000
MODULE_INVENTORY_MAX_SYMBOLS = 120_000
MODULE_INVENTORY_MAX_DEPENDENCIES = 240_000
MODULE_INVENTORY_MAX_ISSUES = 20_000
MODULE_INVENTORY_DEFAULT_LIMIT = 50
MODULE_INVENTORY_MAX_LIMIT = 500


class ModuleRole(StrEnum):
    """Coarse role assigned from path and public surface shape."""

    CORE = "core"
    DOMAIN = "domain"
    FRONTIER = "frontier"
    INTEGRATION = "integration"
    SUPPORT = "support"


class ModuleState(StrEnum):
    """Static parse state for a source module."""

    PARSED = "parsed"
    EMPTY = "empty"
    PARSE_ERROR = "parse_error"


class InventoryResource(StrEnum):
    """Resources available through the bounded query surface."""

    MODULES = "modules"
    SYMBOLS = "symbols"
    DEPENDENCIES = "dependencies"
    ISSUES = "issues"
    INDEXES = "indexes"


class InventoryCheckPlane(StrEnum):
    """Independent inventory audit planes."""

    DISCOVERY = "discovery"
    PARSE = "parse"
    GRAPH = "graph"
    PUBLIC = "public"
    LIMITS = "limits"


class InventoryStageState(StrEnum):
    """Execution state for deterministic inventory stages."""

    COMPLETE = "complete"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} is required")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return result


def _non_negative(value: Any, field: str) -> int:
    result = int(value)
    if result < 0:
        raise ValidationError(f"{field} cannot be negative")
    return result


def _addressed(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(
        {key: value for key, value in body.items() if key != "content_address"}, prefix=prefix
    )


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    """One statically discovered Python module."""

    module_id: str
    relative_path: str
    package: str
    family: str
    role: ModuleRole
    state: ModuleState
    physical_lines: int
    nonblank_lines: int
    comment_lines: int
    public_symbol_count: int
    class_count: int
    function_count: int
    import_count: int
    local_dependency_count: int
    test_reference_count: int
    source_digest: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "module_id",
            "relative_path",
            "package",
            "family",
            "source_digest",
            "content_address",
        ):
            _text(getattr(self, name), name)
        if "\\" in self.relative_path or self.relative_path.startswith("/"):
            raise ValidationError("module relative_path must use safe forward-slash form")
        for name in (
            "physical_lines",
            "nonblank_lines",
            "comment_lines",
            "public_symbol_count",
            "class_count",
            "function_count",
            "import_count",
            "local_dependency_count",
            "test_reference_count",
        ):
            _non_negative(getattr(self, name), name)
        if self.nonblank_lines > self.physical_lines:
            raise ValidationError("nonblank_lines cannot exceed physical_lines")
        if self.comment_lines > self.physical_lines:
            raise ValidationError("comment_lines cannot exceed physical_lines")
        if self.local_dependency_count > self.import_count:
            raise ValidationError("local_dependency_count cannot exceed import_count")

    @property
    def density(self) -> float:
        """Return nonblank source density with stable six-place rounding."""

        if self.physical_lines == 0:
            return 0.0
        return round(self.nonblank_lines / self.physical_lines, 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"density": self.density}


@dataclass(frozen=True, slots=True)
class ModuleSymbol:
    """One class or function discovered from the module AST."""

    module_id: str
    name: str
    kind: str
    line: int
    end_line: int
    public: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("module_id", "name", "kind", "content_address"):
            _text(getattr(self, name), name)
        if self.kind not in {"class", "function", "async_function"}:
            raise ValidationError("symbol kind is unsupported")
        if self.line < 1 or self.end_line < self.line:
            raise ValidationError("symbol line range is invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleDependency:
    """One import edge, retaining both resolved and raw import forms."""

    source_module: str
    target_module: str
    import_name: str
    relative: bool
    resolved: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_module", "target_module", "import_name", "content_address"):
            _text(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InventoryIssue:
    """A bounded issue retained instead of silently dropping a source row."""

    issue_id: str
    relative_path: str
    code: str
    severity: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("issue_id", "relative_path", "code", "severity", "detail", "content_address"):
            _text(getattr(self, name), name)
        if self.severity not in {"info", "warning", "error"}:
            raise ValidationError("inventory issue severity is unsupported")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InventoryIndexRow:
    """Address-only index row for deterministic lookup."""

    index_name: str
    key: str
    values: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("index_name", "key", "content_address"):
            _text(getattr(self, name), name)
        if tuple(sorted(set(self.values))) != self.values:
            raise ValidationError("inventory index values must be unique and sorted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class InventoryAuditCheck:
    """One deterministic check over the inventory closure."""

    check_id: str
    plane: InventoryCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("check_id", "detail", "content_address"):
            _text(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryAudit:
    """Audit report for discovery, parsing, graph, and public closure."""

    version: str
    checks: tuple[InventoryAuditCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.version, "version")
        _text(self.content_address, "content_address")
        if not self.checks:
            raise ValidationError("module inventory audit requires checks")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "checks": [item.to_dict() for item in self.checks],
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ModuleInventory:
    """Complete source, symbol, dependency, index, and issue snapshot."""

    version: str
    boundary: str
    root_label: str
    modules: tuple[ModuleRecord, ...]
    symbols: tuple[ModuleSymbol, ...]
    dependencies: tuple[ModuleDependency, ...]
    issues: tuple[InventoryIssue, ...]
    indexes: tuple[InventoryIndexRow, ...]
    audit: ModuleInventoryAudit
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("version", "boundary", "root_label", "content_address"):
            _text(getattr(self, name), name)
        if self.boundary != MODULE_INVENTORY_BOUNDARY:
            raise ValidationError("module inventory boundary is invalid")
        if not self.modules:
            raise ValidationError("module inventory requires at least one module")
        if len(self.modules) > MODULE_INVENTORY_MAX_MODULES:
            raise ValidationError("module inventory module limit exceeded")
        if len(self.symbols) > MODULE_INVENTORY_MAX_SYMBOLS:
            raise ValidationError("module inventory symbol limit exceeded")
        if len(self.dependencies) > MODULE_INVENTORY_MAX_DEPENDENCIES:
            raise ValidationError("module inventory dependency limit exceeded")
        if len(self.issues) > MODULE_INVENTORY_MAX_ISSUES:
            raise ValidationError("module inventory issue limit exceeded")

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def parsed_module_count(self) -> int:
        return sum(item.state is ModuleState.PARSED for item in self.modules)

    @property
    def total_physical_lines(self) -> int:
        return sum(item.physical_lines for item in self.modules)

    @property
    def total_nonblank_lines(self) -> int:
        return sum(item.nonblank_lines for item in self.modules)

    @property
    def total_public_symbols(self) -> int:
        return sum(item.public_symbol_count for item in self.modules)

    @property
    def domain_count(self) -> int:
        return len({item.family for item in self.modules})

    def summary(self) -> dict[str, Any]:
        roles: dict[str, int] = {}
        states: dict[str, int] = {}
        families: dict[str, int] = {}
        for item in self.modules:
            roles[item.role.value] = roles.get(item.role.value, 0) + 1
            states[item.state.value] = states.get(item.state.value, 0) + 1
            families[item.family] = families.get(item.family, 0) + 1
        return {
            "version": self.version,
            "boundary": self.boundary,
            "root_label": self.root_label,
            "module_count": self.module_count,
            "parsed_module_count": self.parsed_module_count,
            "domain_count": self.domain_count,
            "total_physical_lines": self.total_physical_lines,
            "total_nonblank_lines": self.total_nonblank_lines,
            "total_public_symbols": self.total_public_symbols,
            "symbol_count": len(self.symbols),
            "dependency_count": len(self.dependencies),
            "issue_count": len(self.issues),
            "role_counts": dict(sorted(roles.items())),
            "state_counts": dict(sorted(states.items())),
            "family_counts": dict(sorted(families.items())),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_rows: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = self.summary() | {"audit": self.audit.to_dict()}
        if include_rows:
            result |= {
                "modules": [item.to_dict() for item in self.modules],
                "symbols": [item.to_dict() for item in self.symbols],
                "dependencies": [item.to_dict() for item in self.dependencies],
                "issues": [item.to_dict() for item in self.issues],
                "indexes": [item.to_dict() for item in self.indexes],
            }
        return result


@dataclass(frozen=True, slots=True)
class ModuleInventoryQueryResult:
    """Bounded, content-addressed inventory query page."""

    resource: InventoryResource
    query: Mapping[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[Mapping[str, Any], ...]
    index_used: str | None
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.total < 0 or self.offset < 0 or self.limit < 1:
            raise ValidationError("inventory query paging is invalid")
        if len(self.items) > self.limit:
            raise ValidationError("inventory query returned too many rows")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"item_count": len(self.items)}


@dataclass(frozen=True, slots=True)
class ModuleInventoryDiff:
    """Structural difference between two inventories."""

    left_address: str
    right_address: str
    added_modules: tuple[str, ...]
    removed_modules: tuple[str, ...]
    changed_modules: tuple[str, ...]
    unchanged_modules: tuple[str, ...]
    added_dependencies: tuple[str, ...]
    removed_dependencies: tuple[str, ...]
    changed_summary_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryStage:
    """One stage receipt from the deterministic runtime."""

    stage_id: str
    order: int
    state: InventoryStageState
    input_count: int
    output_count: int
    issue_count: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("stage_id", "detail", "content_address"):
            _text(getattr(self, name), name)
        for name in ("order", "input_count", "output_count", "issue_count"):
            _non_negative(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryRuntime:
    """Replayable runtime receipt for a module inventory build."""

    runtime_id: str
    version: str
    stages: tuple[ModuleInventoryStage, ...]
    inventory_address: str
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for name in ("runtime_id", "version", "inventory_address", "content_address"):
            _text(getattr(self, name), name)
        if tuple(item.order for item in self.stages) != tuple(range(1, len(self.stages) + 1)):
            raise ValidationError("inventory runtime stages must have contiguous order")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_record(record: ModuleRecord) -> str:
    """Recompute a module row address without trusting its stored address."""

    body = {
        "module_id": record.module_id,
        "relative_path": record.relative_path,
        "package": record.package,
        "family": record.family,
        "role": record.role,
        "state": record.state,
        "physical_lines": record.physical_lines,
        "nonblank_lines": record.nonblank_lines,
        "comment_lines": record.comment_lines,
        "public_symbol_count": record.public_symbol_count,
        "class_count": record.class_count,
        "function_count": record.function_count,
        "import_count": record.import_count,
        "local_dependency_count": record.local_dependency_count,
        "test_reference_count": record.test_reference_count,
        "source_digest": record.source_digest,
    }
    return _addressed(body, "module-inventory-module")


def address_module_symbol(symbol: ModuleSymbol) -> str:
    body = symbol.to_dict() | {"content_address": None}
    return _addressed(body, "module-inventory-symbol")


def address_module_dependency(edge: ModuleDependency) -> str:
    body = edge.to_dict() | {"content_address": None}
    return _addressed(body, "module-inventory-dependency")


__all__ = [
    "InventoryCheckPlane",
    "InventoryIndexRow",
    "InventoryIssue",
    "InventoryResource",
    "InventoryStageState",
    "MODULE_INVENTORY_BOUNDARY",
    "MODULE_INVENTORY_DEFAULT_LIMIT",
    "MODULE_INVENTORY_MAX_DEPENDENCIES",
    "MODULE_INVENTORY_MAX_ISSUES",
    "MODULE_INVENTORY_MAX_LIMIT",
    "MODULE_INVENTORY_MAX_MODULES",
    "MODULE_INVENTORY_MAX_SYMBOLS",
    "MODULE_INVENTORY_VERSION",
    "ModuleDependency",
    "ModuleInventory",
    "ModuleInventoryAudit",
    "InventoryAuditCheck",
    "ModuleInventoryDiff",
    "ModuleInventoryQueryResult",
    "ModuleInventoryRuntime",
    "ModuleInventoryStage",
    "ModuleRecord",
    "ModuleRole",
    "ModuleState",
    "ModuleSymbol",
    "address_module_dependency",
    "address_module_record",
    "address_module_symbol",
]

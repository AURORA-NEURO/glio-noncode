"""Static discovery and construction for the repository module inventory."""

from __future__ import annotations

import ast
import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_inventory_contracts import (
    MODULE_INVENTORY_BOUNDARY,
    MODULE_INVENTORY_MAX_DEPENDENCIES,
    MODULE_INVENTORY_MAX_ISSUES,
    MODULE_INVENTORY_MAX_MODULES,
    MODULE_INVENTORY_MAX_SYMBOLS,
    MODULE_INVENTORY_VERSION,
    InventoryAuditCheck,
    InventoryCheckPlane,
    InventoryIndexRow,
    InventoryIssue,
    InventoryResource,
    ModuleDependency,
    ModuleInventory,
    ModuleInventoryAudit,
    ModuleRecord,
    ModuleRole,
    ModuleState,
    ModuleSymbol,
    address_module_dependency,
    address_module_record,
    address_module_symbol,
)
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable

_MODULE_FILE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.py$")
_MODULE_REFERENCE = re.compile(r"\bglio_noncode(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_PACKAGE_NAME = "glio_noncode"
_PUBLIC_DENY = frozenset(
    {"agent", "assistant", "author", "email", "language", "model", "patient", "subject"}
)
_FAMILY_RULES: tuple[tuple[str, str], ...] = (
    ("module_inventory", "platform"),
    ("deployment", "platform"),
    ("service", "platform"),
    ("api", "platform"),
    ("platform", "platform"),
    ("storage", "persistence"),
    ("run_", "persistence"),
    ("batch", "persistence"),
    ("program", "release"),
    ("mission", "release"),
    ("release", "release"),
    ("intake", "intake"),
    ("variant", "intake"),
    ("variation", "intake"),
    ("structural", "structural"),
    ("specimen", "specimen"),
    ("sample", "specimen"),
    ("reference", "reference"),
    ("atlas", "reference"),
    ("sequence", "sequence"),
    ("chromatin", "chromatin"),
    ("methylation", "chromatin"),
    ("cell", "cell"),
    ("topology", "topology"),
    ("link", "linking"),
    ("causal", "causal"),
    ("cohort", "cohort"),
    ("validation", "validation"),
    ("assay", "validation"),
    ("experiment", "validation"),
    ("evidence", "evidence"),
    ("review", "workspace"),
    ("workspace", "workspace"),
)


def _safe_relative(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError("module path escapes source root") from exc
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValidationError("module path contains unsafe component")
    return relative.as_posix()


def _module_id(relative_path: str) -> str:
    path = relative_path[:-3] if relative_path.endswith(".py") else relative_path
    parts = path.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([_PACKAGE_NAME, *parts]) if parts else _PACKAGE_NAME


def _family(module_id: str) -> str:
    normalized = module_id.casefold()
    for token, family in _FAMILY_RULES:
        if token in normalized:
            return family
    return "core"


def _role(module_id: str, family: str) -> ModuleRole:
    normalized = module_id.casefold()
    if "frontier" in normalized:
        return ModuleRole.FRONTIER
    if family in {"platform", "release", "persistence"} or any(
        token in normalized for token in ("_api", "_cli", "service_", "deployment_")
    ):
        return ModuleRole.INTEGRATION
    if family == "core":
        return ModuleRole.SUPPORT
    if family in {
        "intake",
        "structural",
        "specimen",
        "reference",
        "sequence",
        "chromatin",
        "cell",
        "topology",
        "linking",
        "causal",
        "cohort",
        "validation",
        "evidence",
        "workspace",
    }:
        return ModuleRole.DOMAIN
    return ModuleRole.SUPPORT


def _line_counts(text: str) -> tuple[int, int, int]:
    lines = text.splitlines()
    physical = len(lines)
    nonblank = sum(bool(line.strip()) for line in lines)
    comments = sum(line.lstrip().startswith("#") for line in lines)
    return physical, nonblank, comments


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _body_address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(
        {key: value for key, value in body.items() if key != "content_address"}, prefix=prefix
    )


def _symbol_rows(module_id: str, tree: ast.AST) -> tuple[ModuleSymbol, ...]:
    rows: list[ModuleSymbol] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(node, ast.ClassDef):
                kind = "class"
            elif isinstance(node, ast.AsyncFunctionDef):
                kind = "async_function"
            else:
                kind = "function"
            line = int(getattr(node, "lineno", 1))
            end_line = int(getattr(node, "end_lineno", line))
            body = {
                "module_id": module_id,
                "name": node.name,
                "kind": kind,
                "line": line,
                "end_line": end_line,
                "public": not node.name.startswith("_"),
            }
            rows.append(
                ModuleSymbol(**body, content_address=_body_address(body, "module-inventory-symbol"))
            )
    return tuple(sorted(rows, key=lambda item: (item.module_id, item.line, item.name, item.kind)))


def _relative_target(module_id: str, level: int, imported: str | None) -> str | None:
    parts = module_id.split(".")
    if not parts or level < 1 or level > len(parts):
        return None
    # The package initializer is represented by ``glio_noncode`` rather than
    # a dotted module path.  A level-one import from that initializer still
    # resolves inside the package; dropping the only package component makes
    # every ``from .module`` edge appear external and blocks certification.
    base = [parts[0]] if module_id == _PACKAGE_NAME and level == 1 else parts[:-level]
    if imported:
        base.extend(imported.split("."))
    return ".".join(base) if base else None


def _import_rows(module_id: str, tree: ast.AST) -> tuple[tuple[str, str, bool], ...]:
    rows: set[tuple[str, str, bool]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw = alias.name
                target = (
                    raw if raw == _PACKAGE_NAME or raw.startswith(f"{_PACKAGE_NAME}.") else None
                )
                if target:
                    rows.add((target, raw, False))
        elif isinstance(node, ast.ImportFrom):
            raw = node.module or ""
            if node.level:
                base = _relative_target(module_id, node.level, raw or None)
                if base:
                    rows.add((base, "." * node.level + raw, True))
                    if not raw:
                        for alias in node.names:
                            if alias.name != "*":
                                rows.add(
                                    (f"{base}.{alias.name}", "." * node.level + alias.name, True)
                                )
            elif raw == _PACKAGE_NAME or raw.startswith(f"{_PACKAGE_NAME}."):
                rows.add((raw, raw, False))
    return tuple(sorted(rows, key=lambda item: (item[0], item[1], item[2])))


def _module_files(root: Path) -> tuple[Path, ...]:
    if not root.exists() or not root.is_dir():
        raise ValidationError("module inventory source root must be an existing directory")
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if path.is_symlink() or not path.is_file():
            continue
        if _MODULE_FILE.fullmatch(path.name):
            files.append(path)
    return tuple(sorted(files, key=lambda item: item.as_posix().casefold()))


def _test_reference_counts(test_root: Path | None, module_ids: Iterable[str]) -> dict[str, int]:
    counts = {module_id: 0 for module_id in module_ids}
    if test_root is None or not test_root.exists() or not test_root.is_dir():
        return counts
    test_files = tuple(
        sorted(
            (path for path in test_root.rglob("*.py") if path.is_file() and not path.is_symlink()),
            key=lambda item: item.as_posix().casefold(),
        )
    )
    test_payloads: list[str] = []
    for path in test_files:
        try:
            test_payloads.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    known = set(counts)
    for text in test_payloads:
        references = set(_MODULE_REFERENCE.findall(text))
        for module_id in references & known:
            counts[module_id] += 1
    return counts


def _index_rows(
    modules: tuple[ModuleRecord, ...],
    symbols: tuple[ModuleSymbol, ...],
    dependencies: tuple[ModuleDependency, ...],
) -> tuple[InventoryIndexRow, ...]:
    values: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in modules:
        values["family"][item.family].add(item.module_id)
        values["role"][item.role.value].add(item.module_id)
        values["state"][item.state.value].add(item.module_id)
        values["package"][item.package].add(item.module_id)
    for item in symbols:
        values["symbol"][item.name].add(item.module_id)
    for item in dependencies:
        values["dependency_target"][item.target_module].add(item.source_module)
    rows: list[InventoryIndexRow] = []
    for index_name in sorted(values):
        for key in sorted(values[index_name]):
            body = {
                "index_name": index_name,
                "key": key,
                "values": tuple(sorted(values[index_name][key])),
            }
            rows.append(
                InventoryIndexRow(
                    **body, content_address=_body_address(body, "module-inventory-index")
                )
            )
    return tuple(rows)


def _audit(
    modules: tuple[ModuleRecord, ...],
    symbols: tuple[ModuleSymbol, ...],
    dependencies: tuple[ModuleDependency, ...],
    issues: tuple[InventoryIssue, ...],
    indexes: tuple[InventoryIndexRow, ...],
) -> ModuleInventoryAudit:
    module_ids = {item.module_id for item in modules}
    checks: list[InventoryAuditCheck] = []

    def add(
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
                **body, content_address=_body_address(body, "module-inventory-audit-check")
            )
        )

    add(
        "modules-present",
        InventoryCheckPlane.DISCOVERY,
        bool(modules),
        len(modules),
        ">0",
        "source discovery returned module rows",
    )
    add(
        "module-identities-unique",
        InventoryCheckPlane.DISCOVERY,
        len(module_ids) == len(modules),
        len(module_ids),
        len(modules),
        "module identifiers are unique",
    )
    add(
        "parse-errors-visible",
        InventoryCheckPlane.PARSE,
        not any(item.state is ModuleState.PARSE_ERROR for item in modules) or bool(issues),
        sum(item.state is ModuleState.PARSE_ERROR for item in modules),
        "visible",
        "parse failures remain visible as issues",
    )
    add(
        "symbol-parents-exist",
        InventoryCheckPlane.PARSE,
        all(item.module_id in module_ids for item in symbols),
        len(symbols),
        len(symbols),
        "every symbol points to a discovered module",
    )
    add(
        "dependency-sources-exist",
        InventoryCheckPlane.GRAPH,
        all(item.source_module in module_ids for item in dependencies),
        len(dependencies),
        len(dependencies),
        "every dependency has a discovered source",
    )
    add(
        "dependency-resolution-explicit",
        InventoryCheckPlane.GRAPH,
        all(isinstance(item.resolved, bool) for item in dependencies),
        sum(item.resolved for item in dependencies),
        len(dependencies),
        "unresolved imports are explicit",
    )
    add(
        "index-values-sorted",
        InventoryCheckPlane.GRAPH,
        all(tuple(sorted(item.values)) == item.values for item in indexes),
        len(indexes),
        len(indexes),
        "index rows are canonical",
    )
    public_projection = jsonable(
        {
            "modules": modules,
            "symbols": symbols,
            "dependencies": dependencies,
            "issues": issues,
            "indexes": indexes,
        }
    )
    add(
        "public-key-boundary",
        InventoryCheckPlane.PUBLIC,
        not _has_forbidden_key(public_projection),
        "clean" if not _has_forbidden_key(public_projection) else "forbidden_key",
        "clean",
        "inventory rows contain no forbidden public keys",
    )
    add(
        "source-limit",
        InventoryCheckPlane.LIMITS,
        len(modules) <= MODULE_INVENTORY_MAX_MODULES,
        len(modules),
        MODULE_INVENTORY_MAX_MODULES,
        "module count is within the contract",
    )
    add(
        "symbol-limit",
        InventoryCheckPlane.LIMITS,
        len(symbols) <= MODULE_INVENTORY_MAX_SYMBOLS,
        len(symbols),
        MODULE_INVENTORY_MAX_SYMBOLS,
        "symbol count is within the contract",
    )
    add(
        "dependency-limit",
        InventoryCheckPlane.LIMITS,
        len(dependencies) <= MODULE_INVENTORY_MAX_DEPENDENCIES,
        len(dependencies),
        MODULE_INVENTORY_MAX_DEPENDENCIES,
        "dependency count is within the contract",
    )
    add(
        "issue-limit",
        InventoryCheckPlane.LIMITS,
        len(issues) <= MODULE_INVENTORY_MAX_ISSUES,
        len(issues),
        MODULE_INVENTORY_MAX_ISSUES,
        "issue count is within the contract",
    )
    accepted = all(item.passed for item in checks)
    body = {"version": MODULE_INVENTORY_VERSION, "checks": checks, "accepted": accepted}
    return ModuleInventoryAudit(
        **body, content_address=_body_address(body, "module-inventory-audit")
    )


def build_module_inventory(
    source_root: str | Path | None = None,
    *,
    test_root: str | Path | None = None,
    root_label: str = "src/glio_noncode",
) -> ModuleInventory:
    """Discover and statically parse the package without importing it."""

    root = Path(source_root) if source_root is not None else Path(__file__).resolve().parent
    tests = Path(test_root) if test_root is not None else root.parent.parent / "tests"
    files = _module_files(root)
    if len(files) > MODULE_INVENTORY_MAX_MODULES:
        raise ValidationError("module inventory source root exceeds module limit")
    discovered = tuple(
        sorted(
            (
                _module_id(_safe_relative(path, root)),
                path,
            )
            for path in files
        )
    )
    issues: list[InventoryIssue] = []
    module_ids = tuple(item[0] for item in discovered)
    test_counts = _test_reference_counts(tests, module_ids)
    known = set(module_ids)
    modules: list[ModuleRecord] = []
    symbols: list[ModuleSymbol] = []
    dependency_specs: list[tuple[str, str, str, bool, bool]] = []
    for module_id, path in discovered:
        relative = _safe_relative(path, root)
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=relative)
            state = ModuleState.EMPTY if not tree.body else ModuleState.PARSED
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            detail = str(exc).replace("\r", " ").replace("\n", " ")[:480]
            body = {
                "issue_id": f"{module_id}:parse",
                "relative_path": relative,
                "code": "parse_error",
                "severity": "error",
                "detail": detail,
            }
            issues.append(
                InventoryIssue(
                    **body, content_address=_body_address(body, "module-inventory-issue")
                )
            )
            text = ""
            tree = None
            state = ModuleState.PARSE_ERROR
        physical, nonblank, comments = _line_counts(text)
        family = _family(module_id)
        role = _role(module_id, family)
        module_symbols = _symbol_rows(module_id, tree) if tree is not None else ()
        symbols.extend(module_symbols)
        imports = _import_rows(module_id, tree) if tree is not None else ()
        resolved_imports = []
        for target, raw, relative_import in imports:
            resolved = target in known or any(
                candidate.startswith(f"{target}.") for candidate in known
            )
            resolved_target = target
            if not resolved and target.rpartition(".")[0] in known:
                resolved_target = target.rpartition(".")[0]
                resolved = True
            dependency_specs.append((module_id, resolved_target, raw, relative_import, resolved))
            resolved_imports.append(resolved)
        body = {
            "module_id": module_id,
            "relative_path": relative,
            "package": module_id.rpartition(".")[0] or _PACKAGE_NAME,
            "family": family,
            "role": role,
            "state": state,
            "physical_lines": physical,
            "nonblank_lines": nonblank,
            "comment_lines": comments,
            "public_symbol_count": sum(item.public for item in module_symbols),
            "class_count": sum(item.kind == "class" for item in module_symbols),
            "function_count": sum(
                item.kind in {"function", "async_function"} for item in module_symbols
            ),
            "import_count": len(imports),
            "local_dependency_count": sum(resolved_imports),
            "test_reference_count": test_counts.get(module_id, 0),
            "source_digest": _digest(text.encode("utf-8")),
        }
        modules.append(
            ModuleRecord(**body, content_address=_body_address(body, "module-inventory-module"))
        )
    dependencies: list[ModuleDependency] = []
    for source, target, raw, relative_import, resolved in sorted(set(dependency_specs)):
        body = {
            "source_module": source,
            "target_module": target,
            "import_name": raw,
            "relative": relative_import,
            "resolved": resolved,
        }
        dependencies.append(
            ModuleDependency(
                **body, content_address=_body_address(body, "module-inventory-dependency")
            )
        )
    modules_tuple = tuple(sorted(modules, key=lambda item: item.module_id))
    symbols_tuple = tuple(
        sorted(symbols, key=lambda item: (item.module_id, item.line, item.name, item.kind))
    )
    dependencies_tuple = tuple(
        sorted(
            dependencies,
            key=lambda item: (item.source_module, item.target_module, item.import_name),
        )
    )
    issues_tuple = tuple(sorted(issues, key=lambda item: item.issue_id))
    indexes = _index_rows(modules_tuple, symbols_tuple, dependencies_tuple)
    audit = _audit(modules_tuple, symbols_tuple, dependencies_tuple, issues_tuple, indexes)
    body = {
        "version": MODULE_INVENTORY_VERSION,
        "boundary": MODULE_INVENTORY_BOUNDARY,
        "root_label": root_label,
        "modules": modules_tuple,
        "symbols": symbols_tuple,
        "dependencies": dependencies_tuple,
        "issues": issues_tuple,
        "indexes": indexes,
        "audit": audit,
        "accepted": audit.accepted,
    }
    return ModuleInventory(**body, content_address=content_hash(body, prefix="module-inventory"))


def verify_module_inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    """Verify a constructed inventory's boundary and internal row identities."""

    if isinstance(value, ModuleInventory):
        selected = value
    else:
        raise ValidationError("mapping hydration is provided by the offline packet loader")
    if selected.boundary != MODULE_INVENTORY_BOUNDARY:
        raise ValidationError("module inventory boundary is invalid")
    for item in selected.modules:
        if address_module_record(item) != item.content_address:
            raise ValidationError(f"module address mismatch: {item.module_id}")
    for item in selected.symbols:
        if address_module_symbol(item) != item.content_address:
            raise ValidationError(f"symbol address mismatch: {item.module_id}:{item.name}")
    for item in selected.dependencies:
        if address_module_dependency(item) != item.content_address:
            raise ValidationError(
                f"dependency address mismatch: {item.source_module}:{item.target_module}"
            )
    if not selected.audit.accepted or not selected.accepted:
        raise ValidationError("module inventory is not accepted")
    return selected


def module_inventory_schema() -> dict[str, Any]:
    """Return the machine-readable shape without source payloads."""

    return {
        "version": MODULE_INVENTORY_VERSION,
        "boundary": MODULE_INVENTORY_BOUNDARY,
        "resources": [
            item.value
            for item in (
                InventoryResource.MODULES,
                InventoryResource.SYMBOLS,
                InventoryResource.DEPENDENCIES,
                InventoryResource.ISSUES,
                InventoryResource.INDEXES,
            )
        ],
        "module_fields": [
            "module_id",
            "relative_path",
            "package",
            "family",
            "role",
            "state",
            "physical_lines",
            "nonblank_lines",
            "comment_lines",
            "public_symbol_count",
            "class_count",
            "function_count",
            "import_count",
            "local_dependency_count",
            "test_reference_count",
            "source_digest",
            "content_address",
        ],
        "guarantees": [
            "source files are discovered in lexical order",
            "AST parsing does not import or execute modules",
            "absolute machine paths are excluded from output",
            "unresolved local imports remain explicit",
            "queries and exports are bounded and deterministic",
        ],
        "forbidden_public_keys": sorted(_PUBLIC_DENY),
    }


def module_inventory_capabilities() -> dict[str, Any]:
    """Describe the supported inventory operations."""

    operations = (
        "discover_source_modules",
        "parse_module_symbols",
        "resolve_local_dependencies",
        "count_module_lines",
        "count_test_references",
        "build_module_indexes",
        "audit_module_inventory",
        "query_module_inventory",
        "diff_module_inventories",
        "run_module_inventory_runtime",
        "write_module_inventory_packet",
        "verify_module_inventory_packet",
    )
    return {
        "version": MODULE_INVENTORY_VERSION,
        "boundary": MODULE_INVENTORY_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "accepted_output": "aggregate source structure and content addresses",
    }


__all__ = [
    "build_module_inventory",
    "module_inventory_capabilities",
    "module_inventory_schema",
    "verify_module_inventory",
]

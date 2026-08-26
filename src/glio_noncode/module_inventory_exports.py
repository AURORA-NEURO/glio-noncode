"""Deterministic JSON, CSV, and Markdown projections for module inventory."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .module_inventory_contracts import ModuleInventory
from .module_inventory_graph import ModuleInventoryGraph
from .module_inventory_query import inventory_from_mapping
from .serialization import canonical_json, jsonable


def _inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    return value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)


def module_inventory_json(
    value: ModuleInventory | Mapping[str, Any], *, include_rows: bool = True
) -> str:
    """Render canonical JSON with one trailing newline."""

    selected = _inventory(value)
    return canonical_json(selected.to_dict(include_rows=include_rows)) + "\n"


def module_inventory_summary(value: ModuleInventory | Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact aggregate view for dashboards and release reports."""

    selected = _inventory(value)
    summary = selected.summary()
    family_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[Any]] = defaultdict(list)
    for item in selected.modules:
        grouped[item.family].append(item)
    for family in sorted(grouped):
        rows = grouped[family]
        family_rows.append(
            {
                "family": family,
                "module_count": len(rows),
                "physical_lines": sum(item.physical_lines for item in rows),
                "nonblank_lines": sum(item.nonblank_lines for item in rows),
                "public_symbol_count": sum(item.public_symbol_count for item in rows),
                "dependency_count": sum(item.local_dependency_count for item in rows),
                "test_reference_count": sum(item.test_reference_count for item in rows),
                "accepted_parse_count": sum(
                    item.state.value in {"parsed", "empty"} for item in rows
                ),
            }
        )
    summary["families"] = family_rows
    summary["largest_modules"] = [
        {
            "module_id": item.module_id,
            "physical_lines": item.physical_lines,
            "nonblank_lines": item.nonblank_lines,
            "family": item.family,
        }
        for item in sorted(
            selected.modules, key=lambda item: (-item.nonblank_lines, item.module_id)
        )[:20]
    ]
    return jsonable(summary)


def _csv(rows: Iterable[Mapping[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        values: dict[str, Any] = {}
        for field in fields:
            value = row.get(field, "")
            values[field] = (
                ";".join(str(item) for item in value) if isinstance(value, (tuple, list)) else value
            )
        writer.writerow(values)
    return output.getvalue()


def module_inventory_modules_csv(value: ModuleInventory | Mapping[str, Any]) -> str:
    selected = _inventory(value)
    fields = (
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
    )
    return _csv((item.to_dict() for item in selected.modules), fields)


def module_inventory_symbols_csv(value: ModuleInventory | Mapping[str, Any]) -> str:
    selected = _inventory(value)
    fields = ("module_id", "name", "kind", "line", "end_line", "public", "content_address")
    return _csv((item.to_dict() for item in selected.symbols), fields)


def module_inventory_dependencies_csv(value: ModuleInventory | Mapping[str, Any]) -> str:
    selected = _inventory(value)
    fields = (
        "source_module",
        "target_module",
        "import_name",
        "relative",
        "resolved",
        "content_address",
    )
    return _csv((item.to_dict() for item in selected.dependencies), fields)


def module_inventory_indexes_csv(value: ModuleInventory | Mapping[str, Any]) -> str:
    selected = _inventory(value)
    fields = ("index_name", "key", "values", "content_address")
    return _csv((item.to_dict() for item in selected.indexes), fields)


def module_inventory_graph_csv(value: ModuleInventoryGraph) -> str:
    rows = []
    for edge in value.edges:
        rows.append(
            {
                "source_module": edge.source_module,
                "target_module": edge.target_module,
                "import_names": edge.import_names,
                "relative_import": edge.relative_import,
                "resolved": edge.resolved,
                "content_address": edge.content_address,
            }
        )
    return _csv(
        tuple(rows),
        (
            "source_module",
            "target_module",
            "import_names",
            "relative_import",
            "resolved",
            "content_address",
        ),
    )


def render_module_inventory_markdown(value: ModuleInventory | Mapping[str, Any]) -> str:
    """Render a human-readable module depth report without absolute paths."""

    selected = _inventory(value)
    summary = module_inventory_summary(selected)
    lines = [
        "# Module inventory",
        "",
        "This report is a deterministic static view of the package source. "
        "It does not import or execute discovered modules.",
        "",
        f"- Inventory address: `{selected.content_address}`",
        f"- Modules: **{selected.module_count}** ({selected.parsed_module_count} parsed)",
        f"- Physical lines: **{selected.total_physical_lines:,}**",
        f"- Nonblank lines: **{selected.total_nonblank_lines:,}**",
        f"- Public symbols: **{selected.total_public_symbols:,}**",
        f"- Local dependency edges: **{len(selected.dependencies):,}**",
        f"- Accepted: **{str(selected.accepted).lower()}**",
        "",
        "## Family depth",
        "",
        "| Family | Modules | Physical lines | Nonblank lines | Public symbols | "
        "Dependencies | Test references |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["families"]:
        cells = (
            row["family"],
            row["module_count"],
            row["physical_lines"],
            row["nonblank_lines"],
            row["public_symbol_count"],
            row["dependency_count"],
            row["test_reference_count"],
        )
        lines.append(
            "| "
            + " | ".join(f"{cell:,}" if isinstance(cell, int) else str(cell) for cell in cells)
            + " |"
        )
    lines.extend(
        [
            "",
            "## Largest modules by nonblank source",
            "",
            "| Module | Family | Physical lines | Nonblank lines |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in summary["largest_modules"]:
        cells = (
            f"`{row['module_id']}`",
            row["family"],
            row["physical_lines"],
            row["nonblank_lines"],
        )
        lines.append(
            "| "
            + " | ".join(f"{cell:,}" if isinstance(cell, int) else str(cell) for cell in cells)
            + " |"
        )
    lines.extend(
        [
            "",
            "## Audit",
            "",
            f"Checks: **{selected.audit.passed_count}/{len(selected.audit.checks)} passed**.",
            "",
        ]
    )
    for check in selected.audit.checks:
        mark = "PASS" if check.passed else "BLOCK"
        lines.append(f"- **{mark}** `{check.check_id}` — {check.detail}")
    return "\n".join(lines) + "\n"


def render_module_inventory_depth_markdown(value: ModuleInventory | Mapping[str, Any]) -> str:
    """Render a module-by-module detail table for review."""

    selected = _inventory(value)
    lines = [
        "# Module depth matrix",
        "",
        "| Module | Role | State | Nonblank | Symbols | Imports | Local edges | Tests |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in selected.modules:
        cells = (
            f"`{item.module_id}`",
            item.role.value,
            item.state.value,
            item.nonblank_lines,
            item.public_symbol_count,
            item.import_count,
            item.local_dependency_count,
            item.test_reference_count,
        )
        lines.append(
            "| "
            + " | ".join(f"{cell:,}" if isinstance(cell, int) else str(cell) for cell in cells)
            + " |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "module_inventory_dependencies_csv",
    "module_inventory_graph_csv",
    "module_inventory_indexes_csv",
    "module_inventory_json",
    "module_inventory_modules_csv",
    "module_inventory_summary",
    "module_inventory_symbols_csv",
    "render_module_inventory_depth_markdown",
    "render_module_inventory_markdown",
]

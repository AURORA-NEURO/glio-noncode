"""Joined, path-free detail projections for one inspected source module."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_inventory import module_inventory_capabilities
from .module_inventory_contracts import ModuleInventory
from .module_inventory_depth import build_module_inventory_depth
from .module_inventory_graph import build_module_inventory_graph
from .module_inventory_query import inventory_from_mapping
from .module_inventory_review import build_module_inventory_review_queue
from .serialization import content_hash

MODULE_INVENTORY_DETAIL_SCHEMA = "module-inventory-detail-v1"


def _inventory(value: ModuleInventory | Mapping[str, Any]) -> ModuleInventory:
    return value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)


def _module_id(value: object) -> str:
    if type(value) is not str or not value.strip() or len(value) > 512:
        raise ValidationError("module detail module_id is required and bounded")
    if "\\" in value or value.startswith("/"):
        raise ValidationError("module detail module_id must be a dotted identifier")
    return value.strip()


def _address(body: Mapping[str, Any]) -> str:
    return content_hash(body, prefix="module-inventory-detail")


def build_module_inventory_detail(
    value: ModuleInventory | Mapping[str, Any], *, module_id: str
) -> dict[str, Any]:
    """Join static, graph, depth, and review evidence for one module.

    The projection never reads source text. It retains only the source digest,
    bounded static counters, declared symbols, dependency edges, parse issues,
    depth dimensions, and queued review evidence.
    """

    inventory = _inventory(value)
    selected_id = _module_id(module_id)
    selected = next((item for item in inventory.modules if item.module_id == selected_id), None)
    if selected is None:
        raise ValidationError(f"module detail module_id is not present: {selected_id}")

    graph = build_module_inventory_graph(inventory)
    node = next((item for item in graph.nodes if item.module_id == selected_id), None)
    if node is None:
        raise ValidationError(f"module detail graph node is missing: {selected_id}")
    depth = build_module_inventory_depth(inventory)
    assessment = next(item for item in depth.assessments if item.module_id == selected_id)
    review = build_module_inventory_review_queue(inventory)
    review_items = tuple(item for item in review.items if item.module_id == selected_id)
    symbols = tuple(item for item in inventory.symbols if item.module_id == selected_id)
    outgoing = tuple(item for item in inventory.dependencies if item.source_module == selected_id)
    incoming = tuple(item for item in inventory.dependencies if item.target_module == selected_id)
    issues = tuple(
        item for item in inventory.issues if item.relative_path == selected.relative_path
    )

    summary = {
        "symbol_count": len(symbols),
        "public_symbol_count": selected.public_symbol_count,
        "test_reference_count": selected.test_reference_count,
        "fan_in": node.incoming_count,
        "fan_out": node.outgoing_count,
        "unresolved_outgoing_count": node.unresolved_outgoing_count,
        "issue_count": len(issues),
        "review_item_count": len(review_items),
        "blocker_count": sum(item.severity.value == "blocker" for item in review_items),
        "high_count": sum(item.severity.value == "high" for item in review_items),
        "depth_score": assessment.score,
        "depth_tier": assessment.tier,
    }
    body = {
        "schema": MODULE_INVENTORY_DETAIL_SCHEMA,
        "inventory_address": inventory.content_address,
        "module_id": selected_id,
        "module": selected.to_dict(),
        "depth": assessment.to_dict(),
        "graph": node.to_dict(),
        "symbols": [item.to_dict() for item in symbols],
        "outgoing_dependencies": [item.to_dict() for item in outgoing],
        "incoming_dependencies": [item.to_dict() for item in incoming],
        "issues": [item.to_dict() for item in issues],
        "review_items": [item.to_dict() for item in review_items],
        "summary": summary,
        "accepted": inventory.accepted and graph.accepted and depth.accepted and review.accepted,
        "limitations": [
            (
                "This dossier is derived from static source inspection and does not "
                "execute the module."
            ),
            "Source payloads, absolute paths, and machine-specific metadata are excluded.",
            "Depth and review rows are planning signals, not scientific or clinical evidence.",
        ],
    }
    return body | {"content_address": _address(body)}


def module_inventory_detail_schema() -> dict[str, Any]:
    """Return the closed field declaration for one-module detail responses."""

    return {
        "schema": MODULE_INVENTORY_DETAIL_SCHEMA,
        "boundary": "public_aggregate_module_detail",
        "required": [
            "schema",
            "inventory_address",
            "module_id",
            "module",
            "depth",
            "graph",
            "symbols",
            "outgoing_dependencies",
            "incoming_dependencies",
            "issues",
            "review_items",
            "summary",
            "accepted",
            "limitations",
            "content_address",
        ],
        "excluded": ["source_text", "absolute_path", "machine_metadata"],
        "read_only": True,
    }


def module_inventory_detail_capabilities() -> dict[str, Any]:
    """Return bounded operations for module detail inspection."""

    operations = (
        "select_exact_module",
        "join_static_symbols",
        "join_dependency_neighborhood",
        "join_depth_assessment",
        "join_review_items",
        "emit_path_free_projection",
    )
    return {
        "schema": MODULE_INVENTORY_DETAIL_SCHEMA,
        "operation_count": len(operations),
        "operations": list(operations),
        "inventory_capabilities": module_inventory_capabilities()["operations"],
        "read_only": True,
    }


__all__ = [
    "MODULE_INVENTORY_DETAIL_SCHEMA",
    "build_module_inventory_detail",
    "module_inventory_detail_capabilities",
    "module_inventory_detail_schema",
]

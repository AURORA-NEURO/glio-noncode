"""Deterministic staged runtime for module inventory production."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .module_inventory import build_module_inventory
from .module_inventory_audit import audit_module_inventory
from .module_inventory_contracts import (
    MODULE_INVENTORY_VERSION,
    InventoryStageState,
    ModuleInventory,
    ModuleInventoryRuntime,
    ModuleInventoryStage,
)
from .module_inventory_graph import build_module_inventory_graph
from .serialization import canonical_json, content_hash


def _stage(
    stage_id: str,
    order: int,
    input_count: int,
    output_count: int,
    issue_count: int,
    detail: str,
    state: InventoryStageState = InventoryStageState.COMPLETE,
) -> ModuleInventoryStage:
    body = {
        "stage_id": stage_id,
        "order": order,
        "state": state,
        "input_count": input_count,
        "output_count": output_count,
        "issue_count": issue_count,
        "detail": detail,
    }
    return ModuleInventoryStage(
        **body, content_address=content_hash(body, prefix="module-inventory-stage")
    )


def run_module_inventory(
    source_root: str | Path | None = None,
    *,
    test_root: str | Path | None = None,
    runtime_id: str = "glio-noncode-module-inventory-runtime",
    inventory: ModuleInventory | None = None,
) -> ModuleInventoryRuntime:
    """Build an inventory and graph, then record each closure stage."""

    selected = inventory or build_module_inventory(source_root, test_root=test_root)
    graph = build_module_inventory_graph(selected)
    independent_audit = audit_module_inventory(selected)
    stages = (
        _stage(
            "discover",
            1,
            0,
            selected.module_count,
            len(selected.issues),
            "source files discovered in lexical order",
        ),
        _stage(
            "parse",
            2,
            selected.module_count,
            selected.parsed_module_count,
            len(selected.issues),
            "source files parsed with AST without execution",
        ),
        _stage(
            "symbols",
            3,
            selected.module_count,
            len(selected.symbols),
            0,
            "classes and functions projected as symbol rows",
        ),
        _stage(
            "dependencies",
            4,
            selected.module_count,
            len(selected.dependencies),
            sum(not item.resolved for item in selected.dependencies),
            "local import edges resolved or retained as unresolved",
        ),
        _stage(
            "indexes",
            5,
            selected.module_count,
            len(selected.indexes),
            0,
            "family, role, state, package, symbol, and target indexes closed",
        ),
        _stage(
            "graph",
            6,
            len(selected.dependencies),
            graph.node_count + graph.edge_count,
            graph.unresolved_edge_count,
            "dependency graph, roots, leaves, and cycles computed",
        ),
        _stage(
            "audit",
            7,
            selected.module_count,
            independent_audit.passed_count,
            independent_audit.failed_count,
            "independent row, graph, count, and public checks completed",
            InventoryStageState.COMPLETE
            if independent_audit.accepted
            else InventoryStageState.BLOCKED,
        ),
    )
    body = {
        "runtime_id": runtime_id,
        "version": MODULE_INVENTORY_VERSION,
        "stages": stages,
        "inventory_address": selected.content_address,
        "accepted": selected.accepted and independent_audit.accepted,
    }
    return ModuleInventoryRuntime(
        **body, content_address=content_hash(body, prefix="module-inventory-runtime")
    )


def module_inventory_runtime_json(runtime: ModuleInventoryRuntime) -> str:
    return canonical_json(runtime.to_dict()) + "\n"


def module_inventory_runtime_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-runtime-v1",
        "stage_fields": [
            "stage_id",
            "order",
            "state",
            "input_count",
            "output_count",
            "issue_count",
            "detail",
            "content_address",
        ],
        "stage_order": [
            "discover",
            "parse",
            "symbols",
            "dependencies",
            "indexes",
            "graph",
            "audit",
        ],
        "runtime_fields": [
            "runtime_id",
            "version",
            "stages",
            "inventory_address",
            "accepted",
            "content_address",
        ],
        "replay_rule": "same source bytes and test reference bytes produce the same addresses",
    }


def module_inventory_runtime_capabilities() -> dict[str, Any]:
    operations = (
        "run_discovery_stage",
        "run_parse_stage",
        "run_symbol_stage",
        "run_dependency_stage",
        "run_index_stage",
        "run_graph_stage",
        "run_audit_stage",
        "replay_runtime_receipt",
    )
    return {
        "version": "module-inventory-runtime-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "module_inventory_runtime_capabilities",
    "module_inventory_runtime_json",
    "module_inventory_runtime_schema",
    "run_module_inventory",
]

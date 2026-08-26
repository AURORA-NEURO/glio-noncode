"""Actionable, read-only review queue for module inventory depth."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .module_inventory_contracts import ModuleInventory
from .module_inventory_graph import ModuleInventoryGraph, build_module_inventory_graph
from .module_inventory_query import inventory_from_mapping
from .serialization import content_hash, jsonable


class ModuleReviewSeverity(StrEnum):
    """Priority assigned to a static review item."""

    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ModuleReviewKind(StrEnum):
    """Reason a module or graph condition was routed to review."""

    PARSE_FAILURE = "parse_failure"
    UNRESOLVED_IMPORT = "unresolved_import"
    NO_TEST_REFERENCE = "no_test_reference"
    LARGE_MODULE = "large_module"
    ISOLATED_MODULE = "isolated_module"
    LOW_PUBLIC_SURFACE = "low_public_surface"
    HIGH_FAN_OUT = "high_fan_out"
    CYCLE = "cycle"


@dataclass(frozen=True, slots=True)
class ModuleReviewItem:
    """One bounded recommendation backed by inventory evidence."""

    item_id: str
    module_id: str
    kind: ModuleReviewKind
    severity: ModuleReviewSeverity
    priority: int
    evidence: tuple[str, ...]
    next_action: str
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if (
            not self.item_id.strip()
            or not self.module_id.strip()
            or not self.next_action.strip()
            or not self.content_address.strip()
        ):
            raise ValidationError("module review item identifiers are required")
        if self.priority < 0 or self.priority > 100:
            raise ValidationError("module review priority must be between 0 and 100")
        if tuple(sorted(set(self.evidence))) != self.evidence:
            raise ValidationError("module review evidence must be unique and sorted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryReviewQueue:
    """Priority-ordered review queue with explicit disposition state."""

    inventory_address: str
    items: tuple[ModuleReviewItem, ...]
    open_count: int
    blocker_count: int
    high_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.inventory_address.strip() or not self.content_address.strip():
            raise ValidationError("module inventory review queue requires addresses")
        if tuple(
            (item.priority, item.severity.value, item.item_id) for item in self.items
        ) != tuple(
            sorted((item.priority, item.severity.value, item.item_id) for item in self.items)
        ):
            raise ValidationError("module review items must be priority ordered")
        if self.open_count != len(self.items):
            raise ValidationError("module review open count must conserve items")

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_address": self.inventory_address,
            "items": [item.to_dict() for item in self.items],
            "item_count": len(self.items),
            "open_count": self.open_count,
            "blocker_count": self.blocker_count,
            "high_count": self.high_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _item(
    module_id: str,
    kind: ModuleReviewKind,
    severity: ModuleReviewSeverity,
    priority: int,
    evidence: tuple[str, ...],
    next_action: str,
) -> ModuleReviewItem:
    body = {
        "item_id": f"{kind.value}:{module_id}",
        "module_id": module_id,
        "kind": kind,
        "severity": severity,
        "priority": priority,
        "evidence": tuple(sorted(set(evidence))),
        "next_action": next_action,
        "accepted": False,
    }
    return ModuleReviewItem(**body, content_address=_address(body, "module-inventory-review-item"))


def build_module_inventory_review_queue(
    value: ModuleInventory | Mapping[str, Any],
    graph: ModuleInventoryGraph | None = None,
    *,
    large_module_threshold: int = 1_000,
    high_fan_out_threshold: int = 30,
) -> ModuleInventoryReviewQueue:
    """Turn static depth signals into stable next actions."""

    inventory = value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)
    if large_module_threshold < 1 or high_fan_out_threshold < 1:
        raise ValidationError("module review thresholds must be positive")
    selected_graph = graph or build_module_inventory_graph(inventory)
    node_by_id = {item.module_id: item for item in selected_graph.nodes}
    items: list[ModuleReviewItem] = []
    for module in inventory.modules:
        node = node_by_id[module.module_id]
        if module.state.value == "parse_error":
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.PARSE_FAILURE,
                    ModuleReviewSeverity.BLOCKER,
                    0,
                    ("parse state is parse_error",),
                    "repair the syntax or encoding issue, then replay the inventory",
                )
            )
        if node.unresolved_outgoing_count:
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.UNRESOLVED_IMPORT,
                    ModuleReviewSeverity.HIGH,
                    10,
                    (f"unresolved outgoing edges={node.unresolved_outgoing_count}",),
                    "confirm the import target or declare the dependency boundary",
                )
            )
        if module.test_reference_count == 0:
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.NO_TEST_REFERENCE,
                    ModuleReviewSeverity.MEDIUM,
                    35,
                    ("test reference count=0",),
                    "add focused contract coverage or document why the module is "
                    "intentionally uncovered",
                )
            )
        if module.nonblank_lines >= large_module_threshold:
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.LARGE_MODULE,
                    ModuleReviewSeverity.LOW,
                    60,
                    (
                        f"nonblank lines={module.nonblank_lines}",
                        f"threshold={large_module_threshold}",
                    ),
                    "split stable seams or add a module-level structural review",
                )
            )
        if module.public_symbol_count == 0 and module.state.value == "parsed":
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.LOW_PUBLIC_SURFACE,
                    ModuleReviewSeverity.LOW,
                    65,
                    ("public symbol count=0",),
                    "confirm that the module is an intentional implementation-only boundary",
                )
            )
        if node.incoming_count == 0 and node.outgoing_count == 0:
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.ISOLATED_MODULE,
                    ModuleReviewSeverity.INFORMATIONAL,
                    80,
                    ("incoming edges=0", "outgoing edges=0"),
                    "confirm that the module is reachable through the intended package surface",
                )
            )
        if node.outgoing_count >= high_fan_out_threshold:
            items.append(
                _item(
                    module.module_id,
                    ModuleReviewKind.HIGH_FAN_OUT,
                    ModuleReviewSeverity.MEDIUM,
                    45,
                    (
                        f"outgoing edges={node.outgoing_count}",
                        f"threshold={high_fan_out_threshold}",
                    ),
                    "review dependency direction and preserve a bounded public seam",
                )
            )
    for component in selected_graph.cycle_components:
        for module_id in component:
            items.append(
                _item(
                    module_id,
                    ModuleReviewKind.CYCLE,
                    ModuleReviewSeverity.HIGH,
                    20,
                    ("cycle=" + ",".join(component),),
                    "review the cycle before changing dependency ownership",
                )
            )
    ordered = tuple(
        sorted(items, key=lambda item: (item.priority, item.severity.value, item.item_id))
    )
    body = {
        "inventory_address": inventory.content_address,
        "items": ordered,
        "accepted": inventory.accepted,
    }
    return ModuleInventoryReviewQueue(
        inventory_address=inventory.content_address,
        items=ordered,
        open_count=len(ordered),
        blocker_count=sum(item.severity is ModuleReviewSeverity.BLOCKER for item in ordered),
        high_count=sum(item.severity is ModuleReviewSeverity.HIGH for item in ordered),
        accepted=inventory.accepted
        and not any(item.severity is ModuleReviewSeverity.BLOCKER for item in ordered),
        content_address=_address(body, "module-inventory-review-queue"),
    )


def query_module_inventory_review(
    value: ModuleInventoryReviewQueue,
    *,
    module_id: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("module review paging is invalid")
    rows = [item.to_dict() for item in value.items]
    if module_id:
        rows = [item for item in rows if item["module_id"] == module_id]
    if kind:
        rows = [item for item in rows if item["kind"] == kind]
    if severity:
        rows = [item for item in rows if item["severity"] == severity]
    if accepted is not None:
        rows = [item for item in rows if item["accepted"] is accepted]
    if text:
        rows = [item for item in rows if text.casefold() in str(item).casefold()]
    body = {
        "inventory_address": value.inventory_address,
        "query": {
            "module_id": module_id,
            "kind": kind,
            "severity": severity,
            "accepted": accepted,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-inventory-review-query")}


def module_inventory_review_markdown(value: ModuleInventoryReviewQueue) -> str:
    lines = [
        "# Module inventory review queue",
        "",
        f"Inventory: `{value.inventory_address}`",
        f"Open items: **{value.open_count:,}**",
        f"Blockers: **{value.blocker_count:,}**",
        f"High priority: **{value.high_count:,}**",
        "",
        "| Priority | Severity | Module | Kind | Next action |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for item in value.items:
        cells = (
            item.priority,
            item.severity.value,
            f"`{item.module_id}`",
            item.kind.value,
            item.next_action,
        )
        lines.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def module_inventory_review_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-review-v1",
        "item_fields": [
            "item_id",
            "module_id",
            "kind",
            "severity",
            "priority",
            "evidence",
            "next_action",
            "accepted",
            "content_address",
        ],
        "kinds": [item.value for item in ModuleReviewKind],
        "severities": [item.value for item in ModuleReviewSeverity],
        "sort": ["priority", "severity", "item_id"],
        "read_only": True,
    }


def module_inventory_review_capabilities() -> dict[str, Any]:
    operations = (
        "rank_parse_gaps",
        "rank_unresolved_imports",
        "rank_test_coverage_gaps",
        "rank_large_modules",
        "rank_isolated_modules",
        "rank_dependency_cycles",
        "query_review_items",
        "export_review_markdown",
    )
    return {
        "version": "module-inventory-review-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
    }


__all__ = [
    "ModuleInventoryReviewQueue",
    "ModuleReviewItem",
    "ModuleReviewKind",
    "ModuleReviewSeverity",
    "build_module_inventory_review_queue",
    "module_inventory_review_capabilities",
    "module_inventory_review_markdown",
    "module_inventory_review_schema",
    "query_module_inventory_review",
]

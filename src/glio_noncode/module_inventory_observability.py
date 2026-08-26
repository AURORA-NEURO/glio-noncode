"""Timestamp-free observability projections for module inventory quality."""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_inventory_contracts import ModuleInventory, ModuleState
from .module_inventory_query import inventory_from_mapping
from .serialization import canonical_json, content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ModuleInventoryEvent:
    """One deterministic observation over an inventory row."""

    event_id: str
    order: int
    event_type: str
    module_id: str | None
    state: str
    value: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("event_id", "event_type", "state", "detail", "content_address"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"module inventory event {name} is required")
        if self.module_id is not None and not self.module_id.strip():
            raise ValidationError("module inventory event module_id cannot be blank")
        if self.order < 1 or self.value < 0:
            raise ValidationError("module inventory event order and value must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryMetrics:
    """Aggregate counters suitable for a release dashboard."""

    module_count: int
    parsed_count: int
    empty_count: int
    parse_error_count: int
    physical_line_count: int
    nonblank_line_count: int
    comment_line_count: int
    public_symbol_count: int
    class_count: int
    function_count: int
    import_count: int
    local_dependency_count: int
    unresolved_dependency_count: int
    isolated_module_count: int
    family_count: int
    role_count: int
    issue_count: int
    test_reference_count: int
    maximum_fan_in: int
    maximum_fan_out: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "module_count",
            "parsed_count",
            "empty_count",
            "parse_error_count",
            "physical_line_count",
            "nonblank_line_count",
            "comment_line_count",
            "public_symbol_count",
            "class_count",
            "function_count",
            "import_count",
            "local_dependency_count",
            "unresolved_dependency_count",
            "isolated_module_count",
            "family_count",
            "role_count",
            "issue_count",
            "test_reference_count",
            "maximum_fan_in",
            "maximum_fan_out",
        ):
            if getattr(self, name) < 0:
                raise ValidationError(f"module inventory metric {name} cannot be negative")
        if not self.content_address.strip():
            raise ValidationError("module inventory metrics require an address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleInventoryObservability:
    """Events and metrics from one inventory snapshot."""

    inventory_address: str
    events: tuple[ModuleInventoryEvent, ...]
    metrics: ModuleInventoryMetrics
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.inventory_address.strip() or not self.content_address.strip():
            raise ValidationError("module inventory observability requires addresses")
        if tuple(item.order for item in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("module inventory event orders must be contiguous")

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_address": self.inventory_address,
            "event_count": len(self.events),
            "events": [item.to_dict() for item in self.events],
            "metrics": self.metrics.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def build_module_inventory_observability(
    value: ModuleInventory | Mapping[str, Any],
) -> ModuleInventoryObservability:
    """Build stable events in module, dependency, and issue order."""

    inventory = value if isinstance(value, ModuleInventory) else inventory_from_mapping(value)
    events: list[ModuleInventoryEvent] = []
    order = 1
    for module in inventory.modules:
        body = {
            "event_id": f"module:{module.module_id}",
            "order": order,
            "event_type": "module_discovered",
            "module_id": module.module_id,
            "state": module.state.value,
            "value": module.nonblank_lines,
            "detail": "module row observed",
        }
        events.append(
            ModuleInventoryEvent(**body, content_address=_address(body, "module-inventory-event"))
        )
        order += 1
    for dependency in inventory.dependencies:
        body = {
            "event_id": (
                f"dependency:{dependency.source_module}:"
                f"{dependency.target_module}:{dependency.import_name}"
            ),
            "order": order,
            "event_type": "dependency_resolution",
            "module_id": dependency.source_module,
            "state": "resolved" if dependency.resolved else "unresolved",
            "value": 1,
            "detail": dependency.target_module,
        }
        events.append(
            ModuleInventoryEvent(**body, content_address=_address(body, "module-inventory-event"))
        )
        order += 1
    for issue in inventory.issues:
        body = {
            "event_id": f"issue:{issue.issue_id}",
            "order": order,
            "event_type": "inventory_issue",
            "module_id": None,
            "state": issue.severity,
            "value": 1,
            "detail": issue.code,
        }
        events.append(
            ModuleInventoryEvent(**body, content_address=_address(body, "module-inventory-event"))
        )
        order += 1
    incoming = Counter(item.target_module for item in inventory.dependencies if item.resolved)
    outgoing = Counter(item.source_module for item in inventory.dependencies)
    module_ids = {item.module_id for item in inventory.modules}
    metrics_body = {
        "module_count": len(inventory.modules),
        "parsed_count": sum(item.state is ModuleState.PARSED for item in inventory.modules),
        "empty_count": sum(item.state is ModuleState.EMPTY for item in inventory.modules),
        "parse_error_count": sum(
            item.state is ModuleState.PARSE_ERROR for item in inventory.modules
        ),
        "physical_line_count": sum(item.physical_lines for item in inventory.modules),
        "nonblank_line_count": sum(item.nonblank_lines for item in inventory.modules),
        "comment_line_count": sum(item.comment_lines for item in inventory.modules),
        "public_symbol_count": sum(item.public_symbol_count for item in inventory.modules),
        "class_count": sum(item.class_count for item in inventory.modules),
        "function_count": sum(item.function_count for item in inventory.modules),
        "import_count": sum(item.import_count for item in inventory.modules),
        "local_dependency_count": sum(item.resolved for item in inventory.dependencies),
        "unresolved_dependency_count": sum(not item.resolved for item in inventory.dependencies),
        "isolated_module_count": sum(
            item.module_id not in incoming and item.module_id not in outgoing
            for item in inventory.modules
        ),
        "family_count": len({item.family for item in inventory.modules}),
        "role_count": len({item.role.value for item in inventory.modules}),
        "issue_count": len(inventory.issues),
        "test_reference_count": sum(item.test_reference_count for item in inventory.modules),
        "maximum_fan_in": max((incoming.get(item, 0) for item in module_ids), default=0),
        "maximum_fan_out": max((outgoing.get(item, 0) for item in module_ids), default=0),
    }
    metrics = ModuleInventoryMetrics(
        **metrics_body, content_address=_address(metrics_body, "module-inventory-metrics")
    )
    body = {
        "inventory_address": inventory.content_address,
        "events": tuple(events),
        "metrics": metrics,
        "accepted": inventory.accepted,
    }
    return ModuleInventoryObservability(
        **body, content_address=_address(body, "module-inventory-observability")
    )


def query_module_inventory_observability(
    value: ModuleInventoryObservability,
    *,
    event_type: str | None = None,
    state: str | None = None,
    module_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("module inventory observability paging is invalid")
    rows = [item.to_dict() for item in value.events]
    if event_type:
        rows = [item for item in rows if item["event_type"] == event_type]
    if state:
        rows = [item for item in rows if item["state"] == state]
    if module_id:
        rows = [item for item in rows if item.get("module_id") == module_id]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "inventory_address": value.inventory_address,
        "query": {"event_type": event_type, "state": state, "module_id": module_id, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(body, prefix="module-inventory-observability-query")
    }


def module_inventory_observability_events_csv(value: ModuleInventoryObservability) -> str:
    fields = (
        "event_id",
        "order",
        "event_type",
        "module_id",
        "state",
        "value",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.events:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_inventory_observability_metrics_csv(value: ModuleInventoryObservability) -> str:
    row = value.metrics.to_dict()
    fields = tuple(row)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue()


def module_inventory_observability_json(value: ModuleInventoryObservability) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_inventory_observability_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-observability-v1",
        "event_fields": [
            "event_id",
            "order",
            "event_type",
            "module_id",
            "state",
            "value",
            "detail",
            "content_address",
        ],
        "metric_fields": list(ModuleInventoryMetrics.__dataclass_fields__),
        "timestamp_free": True,
        "read_only": True,
    }


def module_inventory_observability_capabilities() -> dict[str, Any]:
    operations = (
        "emit_module_events",
        "aggregate_module_metrics",
        "query_event_page",
        "export_event_csv",
        "export_metrics_csv",
    )
    return {
        "version": "module-inventory-observability-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "timestamp_free": True,
        "read_only": True,
    }


__all__ = [
    "ModuleInventoryEvent",
    "ModuleInventoryMetrics",
    "ModuleInventoryObservability",
    "build_module_inventory_observability",
    "module_inventory_observability_capabilities",
    "module_inventory_observability_events_csv",
    "module_inventory_observability_json",
    "module_inventory_observability_metrics_csv",
    "module_inventory_observability_schema",
    "query_module_inventory_observability",
]

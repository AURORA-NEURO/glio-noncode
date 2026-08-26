"""Offline queries and artifact diffs for module inventory packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_inventory_packet import load_module_inventory_packet, verify_module_inventory_packet
from .module_inventory_packet_contracts import ModuleInventoryPacket
from .module_inventory_query import inventory_from_mapping, query_module_inventory
from .serialization import canonical_json, content_hash


def _packet(value: ModuleInventoryPacket | str | Path) -> ModuleInventoryPacket:
    return (
        value if isinstance(value, ModuleInventoryPacket) else load_module_inventory_packet(value)
    )


def _artifact_payload(packet: ModuleInventoryPacket, artifact_id: str) -> Any:
    artifact = next((item for item in packet.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        raise ValidationError(f"packet artifact is unavailable: {artifact_id}")
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"packet artifact is not JSON: {artifact_id}") from exc


def query_module_inventory_packet(
    packet: ModuleInventoryPacket | str | Path,
    *,
    resource: str = "artifacts",
    module_id: str | None = None,
    family: str | None = None,
    role: str | None = None,
    state: str | None = None,
    symbol: str | None = None,
    target_module: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Query a verified packet without reopening the source tree."""

    selected = _packet(packet)
    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("module inventory packet paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "artifacts":
        rows = [item.to_dict(include_payload=False) for item in selected.artifacts]
        if text:
            rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
        items = rows[offset : offset + limit]
        index_used = "artifact_id"
    elif normalized == "checks":
        rows = [item.to_dict() for item in selected.checks]
        if text:
            rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
        items = rows[offset : offset + limit]
        index_used = "check_id"
    elif normalized in {"modules", "symbols", "dependencies", "indexes"}:
        inventory_payload = _artifact_payload(selected, "inventory")
        inventory = inventory_from_mapping(inventory_payload)
        result = query_module_inventory(
            inventory,
            resource=normalized,
            module_id=module_id,
            family=family,
            role=role,
            state=state,
            symbol=symbol,
            target_module=target_module,
            text=text,
            offset=offset,
            limit=limit,
        ).to_dict()
        return result | {
            "packet_id": selected.packet_id,
            "packet_address": selected.content_address,
        }
    else:
        raise ValidationError("unsupported module inventory packet resource")
    body = {
        "packet_id": selected.packet_id,
        "packet_address": selected.content_address,
        "resource": normalized,
        "query": {
            "module_id": module_id,
            "family": family,
            "role": role,
            "state": state,
            "symbol": symbol,
            "target_module": target_module,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": items,
        "index_used": index_used,
        "accepted": selected.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-inventory-packet-query")}


def diff_module_inventory_packets(
    left: ModuleInventoryPacket | str | Path,
    right: ModuleInventoryPacket | str | Path,
) -> dict[str, Any]:
    """Compare exact artifact identities between two verified packets."""

    left_value = _packet(left)
    right_value = _packet(right)
    left_map = {item.artifact_id: item for item in left_value.artifacts}
    right_map = {item.artifact_id: item for item in right_value.artifacts}
    common = set(left_map) & set(right_map)
    body = {
        "left_packet_id": left_value.packet_id,
        "right_packet_id": right_value.packet_id,
        "added_artifact_ids": tuple(sorted(set(right_map) - set(left_map))),
        "removed_artifact_ids": tuple(sorted(set(left_map) - set(right_map))),
        "changed_artifact_ids": tuple(
            sorted(
                item
                for item in common
                if left_map[item].content_address != right_map[item].content_address
            )
        ),
        "unchanged_artifact_ids": tuple(
            sorted(
                item
                for item in common
                if left_map[item].content_address == right_map[item].content_address
            )
        ),
        "left_accepted": left_value.accepted,
        "right_accepted": right_value.accepted,
        "accepted": left_value.accepted and right_value.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-inventory-packet-diff")}


def replay_module_inventory_packet(directory: str | Path) -> dict[str, Any]:
    """Return a compact offline replay receipt for packet verification."""

    verification = verify_module_inventory_packet(directory)
    packet = load_module_inventory_packet(directory) if verification.accepted else None
    body = {
        "packet_id": verification.packet_id,
        "verification_address": verification.content_address,
        "accepted": verification.accepted,
        "artifact_count": packet.artifact_count if packet is not None else 0,
        "replayed_resources": ("artifacts", "checks") if packet is not None else (),
    }
    return body | {"content_address": content_hash(body, prefix="module-inventory-packet-replay")}


def module_inventory_packet_query_schema() -> dict[str, Any]:
    return {
        "version": "module-inventory-packet-query-v1",
        "resources": ["artifacts", "modules", "symbols", "dependencies", "indexes", "checks"],
        "filters": ["module_id", "family", "role", "state", "symbol", "target_module", "text"],
        "paging": {"offset_minimum": 0, "limit_minimum": 1, "limit_maximum": 500},
        "requires": "verified packet directory for filesystem inputs",
    }


def module_inventory_packet_query_capabilities() -> dict[str, Any]:
    operations = (
        "query_artifacts",
        "query_modules",
        "query_symbols",
        "query_dependencies",
        "query_indexes",
        "query_checks",
        "diff_packets",
        "replay_packet",
    )
    return {
        "version": "module-inventory-packet-query-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
    }


__all__ = [
    "diff_module_inventory_packets",
    "module_inventory_packet_query_capabilities",
    "module_inventory_packet_query_schema",
    "query_module_inventory_packet",
    "replay_module_inventory_packet",
]

"""Offline queries, diffs, and replay receipts for certification packets."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_certification_packet import (
    load_module_certification_packet,
    verify_module_certification_packet,
)
from .module_certification_packet_contracts import ModuleCertificationPacket
from .serialization import canonical_json, content_hash


def _packet(value: ModuleCertificationPacket | str | Path) -> ModuleCertificationPacket:
    return (
        value
        if isinstance(value, ModuleCertificationPacket)
        else load_module_certification_packet(value)
    )


def _artifact_payload(packet: ModuleCertificationPacket, artifact_id: str) -> Any:
    artifact = next((item for item in packet.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        raise ValidationError(f"certification packet artifact is unavailable: {artifact_id}")
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"certification packet artifact is not JSON: {artifact_id}") from exc


def _table_payload(packet: ModuleCertificationPacket, artifact_id: str) -> list[dict[str, Any]]:
    artifact = next((item for item in packet.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        raise ValidationError(f"certification packet table is unavailable: {artifact_id}")
    reader = csv.DictReader(io.StringIO(artifact.payload, newline=""))
    return [dict(row) for row in reader]


def query_module_certification_packet(
    packet: ModuleCertificationPacket | str | Path,
    *,
    resource: str = "artifacts",
    module_id: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Query verified packet data without reopening the source tree."""

    selected = _packet(packet)
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("certification packet paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "artifacts":
        rows = [item.to_dict(include_payload=False) for item in selected.artifacts]
        index_used = "artifact_id"
    elif normalized == "checks":
        rows = [item.to_dict() for item in selected.checks]
        index_used = "check_id"
    elif normalized == "matrix":
        rows = [_artifact_payload(selected, "matrix")]
        index_used = "matrix_address"
    elif normalized == "modules":
        rows = _artifact_payload(selected, "matrix").get("rows", [])
        index_used = "module_id"
    elif normalized == "gaps":
        rows = _table_payload(selected, "gaps")
        index_used = "gap_id"
    elif normalized == "tasks":
        rows = _artifact_payload(selected, "tasks").get("tasks", [])
        index_used = "task_id"
    elif normalized == "summary":
        rows = [_artifact_payload(selected, "summary")]
        index_used = "matrix_address"
    else:
        raise ValidationError("unsupported certification packet resource")
    if module_id:
        rows = [item for item in rows if item.get("module_id") == module_id]
    if kind:
        rows = [item for item in rows if item.get("kind") == kind]
    if state:
        rows = [item for item in rows if item.get("state") == state]
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item).casefold()]
    items = rows[offset : offset + limit]
    body = {
        "packet_id": selected.packet_id,
        "packet_address": selected.content_address,
        "resource": normalized,
        "query": {
            "module_id": module_id,
            "kind": kind,
            "state": state,
            "text": text,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": items,
        "index_used": index_used,
        "accepted": selected.accepted,
    }
    return body | {
        "content_address": content_hash(body, prefix="module-certification-packet-query")
    }


def diff_module_certification_packets(
    left: ModuleCertificationPacket | str | Path,
    right: ModuleCertificationPacket | str | Path,
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
    return body | {"content_address": content_hash(body, prefix="module-certification-packet-diff")}


def replay_module_certification_packet(directory: str | Path) -> dict[str, Any]:
    """Return a compact offline replay receipt after packet verification."""

    verification = verify_module_certification_packet(directory)
    packet = load_module_certification_packet(directory) if verification.accepted else None
    body = {
        "packet_id": verification.packet_id,
        "verification_address": verification.content_address,
        "accepted": verification.accepted,
        "artifact_count": packet.artifact_count if packet is not None else 0,
        "replayed_resources": (
            "artifacts",
            "checks",
            "modules",
            "gaps",
            "tasks",
        )
        if packet is not None
        else (),
    }
    return body | {
        "content_address": content_hash(body, prefix="module-certification-packet-replay")
    }


def module_certification_packet_query_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-packet-query-v1",
        "boundary": "public_aggregate_module_certification_packet_query",
        "resources": ["artifacts", "checks", "matrix", "modules", "gaps", "tasks", "summary"],
        "filters": ["module_id", "kind", "state", "text"],
        "paging": {"offset_minimum": 0, "limit_minimum": 1, "limit_maximum": 512},
        "requires": "verified packet directory for filesystem inputs",
    }


def module_certification_packet_query_capabilities() -> dict[str, Any]:
    operations = (
        "query_artifacts",
        "query_checks",
        "query_matrix",
        "query_modules",
        "query_gaps",
        "query_tasks",
        "query_summary",
        "diff_packets",
        "replay_packet",
    )
    return {
        "version": "module-certification-packet-query-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
        "verified_input": True,
    }


__all__ = [
    "diff_module_certification_packets",
    "module_certification_packet_query_capabilities",
    "module_certification_packet_query_schema",
    "query_module_certification_packet",
    "replay_module_certification_packet",
]

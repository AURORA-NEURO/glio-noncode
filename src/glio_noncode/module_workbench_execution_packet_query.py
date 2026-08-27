"""Offline queries, replay receipts, and diffs for execution packets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet import (
    load_module_workbench_execution_packet,
    verify_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
    ModuleWorkbenchExecutionPacket,
)
from .serialization import canonical_json, content_hash

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 512
_RESOURCE_NAMES = ("manifest", "artifacts", "checks", "links", "summary")


def _packet(
    value: ModuleWorkbenchExecutionPacket | str | Path,
) -> ModuleWorkbenchExecutionPacket:
    if isinstance(value, ModuleWorkbenchExecutionPacket):
        return value
    return load_module_workbench_execution_packet(value)


def _page(
    rows: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    text: str | None,
) -> tuple[list[dict[str, Any]], int]:
    if offset < 0 or limit < 1 or limit > _MAX_LIMIT:
        raise ValidationError("execution packet query paging is invalid")
    filtered = rows
    if text:
        needle = text.casefold()
        filtered = [row for row in rows if needle in canonical_json(row).casefold()]
    return filtered[offset : offset + limit], len(filtered)


def _links(value: ModuleWorkbenchExecutionPacket) -> list[dict[str, Any]]:
    return [
        {"name": "report", "address": value.report_address},
        {"name": "portfolio", "address": value.portfolio_address},
        {"name": "initial_ledger", "address": value.initial_ledger_address},
        {"name": "ledger", "address": value.ledger_address},
        {"name": "review", "address": value.review_address},
        {"name": "audit", "address": value.audit_address},
        {"name": "policy", "address": value.policy_address},
        {"name": "gate", "address": value.gate_address},
        {"name": "runtime", "address": value.runtime_address},
    ]


def _summary(value: ModuleWorkbenchExecutionPacket) -> dict[str, Any]:
    return {
        "packet_id": value.packet_id,
        "packet_address": value.content_address,
        "version": value.version,
        "boundary": value.boundary,
        "state": value.state,
        "accepted": value.accepted,
        "artifact_count": value.artifact_count,
        "check_count": len(value.checks),
        "passed_check_count": value.passed_check_count,
        "failed_check_count": value.failed_check_count,
        "link_count": len(_links(value)),
    }


def query_module_workbench_execution_packet(
    value: ModuleWorkbenchExecutionPacket | str | Path,
    *,
    resource: str = "artifacts",
    artifact_id: str | None = None,
    kind: str | None = None,
    plane: str | None = None,
    passed: bool | None = None,
    link_name: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded, addressable view over a verified packet."""

    packet = _packet(value)
    if not isinstance(packet, ModuleWorkbenchExecutionPacket):
        raise ValidationError("execution packet query requires a typed packet")
    normalized = resource.casefold().strip()
    if normalized not in _RESOURCE_NAMES:
        raise ValidationError("unsupported execution packet resource")
    if normalized == "manifest":
        rows = [packet.to_dict(include_payloads=False)]
        index_used = "packet_id"
    elif normalized == "artifacts":
        rows = [item.to_dict(include_payload=False) for item in packet.artifacts]
        if artifact_id:
            rows = [row for row in rows if row.get("artifact_id") == artifact_id]
        if kind:
            rows = [row for row in rows if row.get("kind") == kind]
        index_used = "artifact_id"
    elif normalized == "checks":
        rows = [item.to_dict() for item in packet.checks]
        if plane:
            rows = [row for row in rows if row.get("plane") == plane]
        if passed is not None:
            rows = [row for row in rows if row.get("passed") is passed]
        index_used = "check_id"
    elif normalized == "links":
        rows = _links(packet)
        if link_name:
            rows = [row for row in rows if row.get("name") == link_name]
        index_used = "name"
    else:
        rows = [_summary(packet)]
        index_used = "packet_id"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    body = {
        "packet_id": packet.packet_id,
        "packet_address": packet.content_address,
        "resource": normalized,
        "query": {
            "artifact_id": artifact_id,
            "kind": kind,
            "plane": plane,
            "passed": passed,
            "link_name": link_name,
            "text": text,
        },
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": items,
        "accepted": packet.accepted,
    }
    return body | {
        "content_address": content_hash(body, prefix="module-workbench-execution-packet-query")
    }


def replay_module_workbench_execution_packet(
    value: ModuleWorkbenchExecutionPacket | str | Path,
) -> dict[str, Any]:
    """Re-verify a packet and return a compact, deterministic replay receipt."""

    if isinstance(value, ModuleWorkbenchExecutionPacket):
        packet = value
        verification = None
    else:
        verification = verify_module_workbench_execution_packet(value)
        packet = load_module_workbench_execution_packet(value) if verification.accepted else None
    if packet is None:
        body = {
            "packet_id": verification.packet_id,
            "packet_address": None,
            "verification_address": verification.content_address,
            "accepted": False,
            "artifact_count": verification.artifact_count,
            "replayed_artifacts": (),
            "replayed_json_artifacts": (),
        }
        return body | {
            "content_address": content_hash(body, prefix="module-workbench-execution-packet-replay")
        }
    verified_artifacts = tuple(item.artifact_id for item in packet.artifacts)
    json_artifacts = tuple(
        item.artifact_id for item in packet.artifacts if item.media_type == "application/json"
    )
    body = {
        "packet_id": packet.packet_id,
        "packet_address": packet.content_address,
        "verification_address": verification.content_address if verification else None,
        "accepted": packet.accepted,
        "artifact_count": packet.artifact_count,
        "replayed_artifacts": verified_artifacts,
        "replayed_json_artifacts": json_artifacts,
        "check_count": len(packet.checks),
    }
    return body | {
        "content_address": content_hash(body, prefix="module-workbench-execution-packet-replay")
    }


def diff_module_workbench_execution_packets(
    left: ModuleWorkbenchExecutionPacket | str | Path,
    right: ModuleWorkbenchExecutionPacket | str | Path,
) -> dict[str, Any]:
    """Compare packet artifacts, checks, links, and state without source access."""

    left_packet = _packet(left)
    right_packet = _packet(right)
    left_artifacts = {item.artifact_id: item for item in left_packet.artifacts}
    right_artifacts = {item.artifact_id: item for item in right_packet.artifacts}
    common = set(left_artifacts) & set(right_artifacts)
    changed = tuple(
        sorted(
            artifact_id
            for artifact_id in common
            if left_artifacts[artifact_id].content_address
            != right_artifacts[artifact_id].content_address
        )
    )
    unchanged = tuple(
        sorted(
            artifact_id
            for artifact_id in common
            if left_artifacts[artifact_id].content_address
            == right_artifacts[artifact_id].content_address
        )
    )
    left_links = {row["name"]: row["address"] for row in _links(left_packet)}
    right_links = {row["name"]: row["address"] for row in _links(right_packet)}
    link_changes = tuple(
        sorted(
            name
            for name in set(left_links) | set(right_links)
            if left_links.get(name) != right_links.get(name)
        )
    )
    body = {
        "left_packet_id": left_packet.packet_id,
        "right_packet_id": right_packet.packet_id,
        "left_packet_address": left_packet.content_address,
        "right_packet_address": right_packet.content_address,
        "added_artifact_ids": tuple(sorted(set(right_artifacts) - set(left_artifacts))),
        "removed_artifact_ids": tuple(sorted(set(left_artifacts) - set(right_artifacts))),
        "changed_artifact_ids": changed,
        "unchanged_artifact_ids": unchanged,
        "changed_link_names": link_changes,
        "state_changed": left_packet.state != right_packet.state,
        "acceptance_changed": left_packet.accepted != right_packet.accepted,
        "left_accepted": left_packet.accepted,
        "right_accepted": right_packet.accepted,
    }
    body["accepted"] = left_packet.accepted and right_packet.accepted
    return body | {
        "content_address": content_hash(body, prefix="module-workbench-execution-packet-diff")
    }


def module_workbench_execution_packet_query_schema() -> dict[str, Any]:
    """Describe offline packet query resources and filters."""

    return {
        "version": "module-workbench-execution-packet-query-v1",
        "packet_version": MODULE_WORKBENCH_EXECUTION_PACKET_VERSION,
        "resources": list(_RESOURCE_NAMES),
        "filters": ["artifact_id", "kind", "plane", "passed", "link_name", "text"],
        "paging": {"offset_minimum": 0, "limit_minimum": 1, "limit_maximum": _MAX_LIMIT},
        "inputs": ["verified_packet_directory", "typed_packet"],
        "outputs": ["bounded_rows", "replay_receipt", "packet_diff"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_query_capabilities() -> dict[str, Any]:
    """Declare packet query and replay capabilities."""

    operations = (
        "query_manifest",
        "query_artifacts",
        "query_checks",
        "query_links",
        "query_summary",
        "filter_artifact_kind",
        "filter_check_plane",
        "filter_check_status",
        "filter_link_name",
        "page_results",
        "replay_verified_packet",
        "diff_packet_artifacts",
        "diff_packet_links",
        "compare_acceptance",
        "export_query_address",
    )
    return {
        "version": "module-workbench-execution-packet-query-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "offline": True,
        "read_only": True,
        "deterministic": True,
        "identity_free": True,
    }


__all__ = [
    "diff_module_workbench_execution_packets",
    "module_workbench_execution_packet_query_capabilities",
    "module_workbench_execution_packet_query_schema",
    "query_module_workbench_execution_packet",
    "replay_module_workbench_execution_packet",
]

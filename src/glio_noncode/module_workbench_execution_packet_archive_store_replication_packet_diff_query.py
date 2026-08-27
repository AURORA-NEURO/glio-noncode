"""Bounded query and export projections for packet diffs and release gates."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_runtime import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
)
from .serialization import canonical_json, content_hash

_DIFF_RESOURCES = ("summary", "artifacts", "checks")
_RELEASE_RESOURCES = ("summary", "checks")
_RUNTIME_RESOURCES = ("summary", "stages")


def _page(
    rows: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    text: str | None,
) -> tuple[list[dict[str, Any]], int]:
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT
    ):
        raise ValidationError("packet diff query paging is invalid")
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item).casefold()]
    return rows[offset : offset + limit], len(rows)


def _result(
    *,
    resource: str,
    query: dict[str, Any],
    items: list[dict[str, Any]],
    total: int,
    offset: int,
    limit: int,
    accepted: bool,
    reference_address: str,
) -> dict[str, Any]:
    body = {
        "resource": resource,
        "query": query,
        "total": total,
        "offset": offset,
        "limit": limit,
        "reference_address": reference_address,
        "items": items,
        "accepted": accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX,
        )
    }


def query_module_workbench_execution_packet_archive_store_replication_packet_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    *,
    resource: str = "summary",
    action: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT,  # noqa: E501
) -> dict[str, Any]:
    """Return a bounded diff summary, artifact rows, or safety checks."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff(value)
    normalized = resource.casefold().strip()
    if normalized not in _DIFF_RESOURCES:
        raise ValidationError("unsupported packet diff resource")
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "diff_id"
    elif normalized == "artifacts":
        rows = [item.to_dict() for item in value.artifacts]
        if action:
            rows = [item for item in rows if item.get("action") == action]
        if accepted is not None:
            rows = [item for item in rows if item.get("accepted") is accepted]
        index_used = "artifact_id"
    else:
        rows = [item.to_dict() for item in value.checks]
        if accepted is not None:
            rows = [item for item in rows if item.get("passed") is accepted]
        index_used = "plane"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    result = _result(
        resource=normalized,
        query={"action": action, "accepted": accepted, "text": text},
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        accepted=value.accepted,
        reference_address=value.content_address,
    )
    result["index_used"] = index_used
    result["content_address"] = content_hash(
        {key: item for key, item in result.items() if key != "content_address"},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX,
    )
    return result


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    *,
    resource: str = "summary",
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT,  # noqa: E501
) -> dict[str, Any]:
    """Return release summary or bounded release checks."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(value)
    normalized = resource.casefold().strip()
    if normalized not in _RELEASE_RESOURCES:
        raise ValidationError("unsupported packet diff release resource")
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "release_id"
    else:
        rows = [item.to_dict() for item in value.checks]
        if accepted is not None:
            rows = [item for item in rows if item.get("passed") is accepted]
        index_used = "plane"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    result = _result(
        resource=normalized,
        query={"accepted": accepted, "text": text},
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        accepted=value.accepted,
        reference_address=value.content_address,
    )
    result["index_used"] = index_used
    result["content_address"] = content_hash(
        {key: item for key, item in result.items() if key != "content_address"},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX,
    )
    return result


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
    *,
    resource: str = "summary",
    kind: str | None = None,
    state: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT,  # noqa: E501
) -> dict[str, Any]:
    """Return a bounded diff-runtime summary or stage page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(value)
    normalized = resource.casefold().strip()
    if normalized not in _RUNTIME_RESOURCES:
        raise ValidationError("unsupported packet diff runtime resource")
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "diff_id"
    else:
        rows = [item.to_dict() for item in value.stages]
        if kind:
            rows = [item for item in rows if item.get("kind") == kind]
        if state:
            rows = [item for item in rows if item.get("state") == state]
        index_used = "kind"
    items, total = _page(rows, offset=offset, limit=limit, text=None)
    result = _result(
        resource=normalized,
        query={"kind": kind, "state": state},
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        accepted=value.accepted,
        reference_address=value.content_address,
    )
    result["index_used"] = index_used
    result["content_address"] = content_hash(
        {key: item for key, item in result.items() if key != "content_address"},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX,
    )
    return result


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify one addressed diff query response."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("packet diff query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("packet diff query address mismatch")
    if not isinstance(value.get("total"), int) or value["total"] < len(value.get("items", ())):
        raise ValidationError("packet diff query total is inconsistent")
    if value.get("offset", -1) < 0 or value.get("limit", 0) < 1:
        raise ValidationError("packet diff query paging is invalid")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_query(value)
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_query_csv(
    value: Mapping[str, Any],
) -> str:
    """Export any diff query page with explicit common columns."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_query(value)
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "ordinal",
        "artifact_id",
        "check_id",
        "action",
        "plane",
        "passed",
        "accepted",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for ordinal, item in enumerate(value.get("items", ())):
        writer.writerow(
            {
                "resource": value.get("resource"),
                "ordinal": ordinal,
                "artifact_id": item.get("artifact_id"),
                "check_id": item.get("check_id"),
                "action": item.get("action"),
                "plane": item.get("plane"),
                "passed": item.get("passed"),
                "accepted": item.get("accepted"),
                "detail": item.get("detail"),
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_query_markdown(
    value: Mapping[str, Any],
) -> str:
    """Render a bounded diff query page for human review."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_query(value)
    lines = [
        "# Archive Store Replication Packet Diff Query",
        "",
        f"- Resource: `{value.get('resource')}`",
        f"- Reference: `{value.get('reference_address')}`",
        f"- Query: `{value.get('content_address')}`",
        f"- Rows: `{len(value.get('items', ()))} / {value.get('total')}`",
        "",
        "| Ordinal | ID | Action | Plane | Passed / accepted | Detail |",
        "|---:|---|---|---|---:|---|",
    ]
    for ordinal, item in enumerate(value.get("items", ())):
        identifier = item.get("artifact_id") or item.get("check_id") or item.get("diff_id")
        outcome = item.get("passed", item.get("accepted", ""))
        lines.append(
            f"| {ordinal} | `{identifier or ''}` | `{item.get('action', '')}` | "
            f"`{item.get('plane', '')}` | {str(outcome).lower()} | {item.get('detail', '')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_query_schema() -> dict[
    str, Any
]:
    """Describe diff, release, and runtime query resources."""

    return {
        "version": (
            "module-workbench-execution-packet-archive-store-replication-packet-"
            "diff-query-v1"
        ),
        "resources": {
            "diff": list(_DIFF_RESOURCES),
            "release": list(_RELEASE_RESOURCES),
            "runtime": list(_RUNTIME_RESOURCES),
        },
        "filters": ["action", "accepted", "kind", "state", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT,  # noqa: E501
        },
        "addressed_response": True,
        "path_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_query_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    """Declare diff query and export operations."""

    return {
        "version": (
            "module-workbench-execution-packet-archive-store-replication-packet-"
            "diff-query-v1"
        ),
        "operations": [
            "query_diff_summary",
            "query_diff_artifacts",
            "query_diff_checks",
            "query_release_summary",
            "query_release_checks",
            "query_runtime_summary",
            "query_runtime_stages",
            "filter_diff_actions",
            "filter_runtime_stages",
            "verify_query_address",
            "export_query_json",
            "export_query_csv",
            "render_query_markdown",
        ],
        "guarantees": [
            "bounded_pages",
            "stable_order",
            "content_addressed_response",
            "no_filesystem_paths",
            "no_private_or_attribution_fields",
        ],
    }

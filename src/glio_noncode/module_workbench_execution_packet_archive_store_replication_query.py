"""Bounded query and export projections for archive-store replication."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication import (
    verify_module_workbench_execution_packet_archive_store_promotion,
    verify_module_workbench_execution_packet_archive_store_replication,
    verify_module_workbench_execution_packet_archive_store_replication_receipt,
)
from .module_workbench_execution_packet_archive_store_replication_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_QUERY_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
)
from .serialization import canonical_json, content_hash

_PLAN_RESOURCES = ("summary", "entries", "operations", "checks")
_RECEIPT_RESOURCES = ("summary",)
_PROMOTION_RESOURCES = ("summary", "checks")


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
        or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_LIMIT
    ):
        raise ValidationError("replication query paging is invalid")
    filtered = rows
    if text:
        needle = text.casefold()
        filtered = [item for item in rows if needle in canonical_json(item).casefold()]
    return filtered[offset : offset + limit], len(filtered)


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
        "index_used": "content_address",
        "reference_address": reference_address,
        "items": items,
        "accepted": accepted,
    }
    return body | {
        "content_address": content_hash(
            body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_QUERY_PREFIX
        )
    }


def query_module_workbench_execution_packet_archive_store_replication(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    *,
    resource: str = "summary",
    action: str | None = None,
    accepted: bool | None = None,
    plane: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded plan projection with stable filter semantics."""

    verify_module_workbench_execution_packet_archive_store_replication(value)
    normalized = resource.casefold().strip()
    if normalized not in _PLAN_RESOURCES:
        raise ValidationError("unsupported replication plan resource")
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "replication_id"
    elif normalized == "entries":
        rows = [item.to_dict() for item in value.entries]
        if action:
            rows = [item for item in rows if item.get("action") == action]
        if accepted is not None:
            rows = [item for item in rows if item.get("accepted") is accepted]
        index_used = "archive_address"
    elif normalized == "operations":
        rows = [item.to_dict() for item in value.operations]
        if action:
            rows = [item for item in rows if item.get("action") == action]
        if accepted is not None:
            rows = [item for item in rows if item.get("accepted") is accepted]
        index_used = "operation_id"
    else:
        rows = [item.to_dict() for item in value.checks]
        if plane:
            rows = [item for item in rows if item.get("plane") == plane]
        if accepted is not None:
            rows = [item for item in rows if item.get("passed") is accepted]
        index_used = "plane"
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    result = _result(
        resource=normalized,
        query={"action": action, "accepted": accepted, "plane": plane, "text": text},
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
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_QUERY_PREFIX,
    )
    return result


def query_module_workbench_execution_packet_archive_store_replication_receipt(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
    *,
    resource: str = "summary",
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return the receipt summary through the same bounded query contract."""

    verify_module_workbench_execution_packet_archive_store_replication_receipt(value)
    normalized = resource.casefold().strip()
    if normalized not in _RECEIPT_RESOURCES:
        raise ValidationError("unsupported replication receipt resource")
    rows, total = _page([value.to_dict()], offset=offset, limit=limit, text=text)
    return _result(
        resource=normalized,
        query={"text": text},
        items=rows,
        total=total,
        offset=offset,
        limit=limit,
        accepted=value.accepted,
        reference_address=value.content_address,
    )


def query_module_workbench_execution_packet_archive_store_promotion(
    value: ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    *,
    resource: str = "summary",
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return promotion summary or bounded check rows."""

    verify_module_workbench_execution_packet_archive_store_promotion(value)
    normalized = resource.casefold().strip()
    if normalized not in _PROMOTION_RESOURCES:
        raise ValidationError("unsupported replication promotion resource")
    if normalized == "summary":
        rows = [value.summary()]
    else:
        rows = [item.to_dict() for item in value.checks]
        if passed is not None:
            rows = [item for item in rows if item.get("passed") is passed]
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    return _result(
        resource=normalized,
        query={"passed": passed, "text": text},
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        accepted=value.accepted,
        reference_address=value.content_address,
    )


def verify_module_workbench_execution_packet_archive_store_replication_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a serialized query response's address and conservation fields."""

    if not isinstance(value, Mapping):
        raise ValidationError("replication query response must be an object")
    if not isinstance(value.get("content_address"), str):
        raise ValidationError("replication query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("replication query response address mismatch")
    if value.get("total") != len(value.get("items", ())):
        raise ValidationError("replication query response total must equal page size")
    if value.get("offset", 0) < 0 or value.get("limit", 0) < 1:
        raise ValidationError("replication query response paging is invalid")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_query(value)
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_query_csv(
    value: Mapping[str, Any],
) -> str:
    """Export a page without flattening nested evidence into lossy strings."""

    verify_module_workbench_execution_packet_archive_store_replication_query(value)
    fields = ("resource", "ordinal", "address", "action", "plane", "accepted", "detail")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for ordinal, item in enumerate(value.get("items", ())):
        writer.writerow(
            {
                "resource": value.get("resource"),
                "ordinal": ordinal,
                "address": item.get("archive_address")
                or item.get("operation_address")
                or item.get("check_id")
                or item.get("content_address"),
                "action": item.get("action"),
                "plane": item.get("plane"),
                "accepted": item.get("accepted", item.get("passed")),
                "detail": item.get("detail"),
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_query_markdown(
    value: Mapping[str, Any],
) -> str:
    """Render any bounded query page for human review."""

    verify_module_workbench_execution_packet_archive_store_replication_query(value)
    lines = [
        "# Archive Store Replication Query",
        "",
        f"- Resource: `{value.get('resource')}`",
        f"- Reference: `{value.get('reference_address')}`",
        f"- Query address: `{value.get('content_address')}`",
        f"- Total: `{value.get('total')}`; offset `{value.get('offset')}`; "
        f"limit `{value.get('limit')}`",
        f"- Accepted: `{str(value.get('accepted')).lower()}`",
        "",
        "| Ordinal | Address | Action | Plane | Accepted | Detail |",
        "|---:|---|---|---|---:|---|",
    ]
    for ordinal, item in enumerate(value.get("items", ())):
        address = (
            item.get("archive_address")
            or item.get("operation_address")
            or item.get("check_id")
            or item.get("content_address")
            or ""
        )
        lines.append(
            f"| {ordinal} | `{address}` | `{item.get('action', '')}` | `{item.get('plane', '')}` | "
            f"{str(item.get('accepted', item.get('passed', ''))).lower()} | "
            f"{item.get('detail', '')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_query_schema() -> dict[str, Any]:
    """Describe query resources, filters, and bounded paging."""

    return {
        "version": "module-workbench-execution-packet-archive-store-replication-query-v1",
        "resources": list(_PLAN_RESOURCES),
        "receipt_resources": list(_RECEIPT_RESOURCES),
        "promotion_resources": list(_PROMOTION_RESOURCES),
        "filters": ["action", "accepted", "plane", "passed", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_MAX_LIMIT,
        },
        "outputs": ["items", "total", "reference_address", "content_address"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_query_capabilities() -> dict[
    str, Any
]:
    """Declare query, filter, export, and verification operations."""

    return {
        "version": "module-workbench-execution-packet-archive-store-replication-query-v1",
        "operations": [
            "query_plan_summary",
            "query_plan_entries",
            "query_plan_operations",
            "query_plan_checks",
            "query_receipt_summary",
            "query_promotion_summary",
            "query_promotion_checks",
            "filter_action",
            "filter_acceptance",
            "filter_plane",
            "filter_passed",
            "filter_text",
            "page_rows",
            "verify_query_address",
            "export_query_json",
            "export_query_csv",
            "render_query_markdown",
        ],
        "guarantees": [
            "bounded_rows",
            "stable_sort_order",
            "addressed_query_response",
            "nested_values_remain_explicit",
            "no_binary_payloads",
            "no_filesystem_paths",
        ],
    }

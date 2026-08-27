"""Bounded query and export projections for release-window reviews."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_QUERY_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


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
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT
    ):
        raise ValidationError("release-window query paging is invalid")
    if text is not None:
        text = _text(text, "release-window query text", 512).casefold()
        rows = [row for row in rows if text in canonical_json(row).casefold()]
    return rows[offset : offset + limit], len(rows)


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    *,
    resource: str = "summary",
    kind: str | None = None,
    severity: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded summary or policy-check page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        value
    )
    normalized = _text(resource, "release-window query resource", 64).casefold()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "window_id"
    elif normalized == "checks":
        rows = [item.to_dict() for item in value.checks]
        if kind is not None:
            kind = _text(kind, "release-window query kind", 64)
            rows = [row for row in rows if row["kind"] == kind]
        if severity is not None:
            severity = _text(severity, "release-window query severity", 64)
            if severity not in {
                item.value
                for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity
            }:
                raise ValidationError("release-window query severity is invalid")
            rows = [row for row in rows if row["severity"] == severity]
        if passed is not None:
            if not isinstance(passed, bool):
                raise ValidationError("release-window query passed filter must be boolean")
            rows = [row for row in rows if row["passed"] is passed]
        index_used = "kind"
    else:
        raise ValidationError("unsupported release-window query resource")
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    body = {
        "resource": normalized,
        "query": {
            "kind": kind,
            "severity": severity,
            "passed": passed,
            "text": text,
        },
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": items,
        "accepted": value.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify the independent address of a query response."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("release-window query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("release-window query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "total",
        "offset",
        "limit",
        "index_used",
        "accepted",
        "content_address",
        "reference_address",
        "ordinal",
        "check_id",
        "kind",
        "severity",
        "passed",
        "observed",
        "expected",
        "detail",
        "remediation",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    rows = value.get("items", [])
    if not isinstance(rows, list):
        raise ValidationError("release-window query items must be a list")
    envelope = {
        key: value.get(key)
        for key in fields
        if key
        in {
            "resource",
            "total",
            "offset",
            "limit",
            "index_used",
            "accepted",
            "content_address",
            "reference_address",
        }
    }
    for row in rows:
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query(
        value
    )
    resource = value.get("resource")
    lines = [
        "# Archive Store Replication Packet Diff Release Window Query",
        "",
        f"- resource: `{resource}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- accepted: `{str(value.get('accepted')).lower()}`",
        f"- reference: `{value.get('reference_address')}`",
        f"- address: `{value.get('content_address')}`",
        "",
    ]
    if resource == "summary":
        lines.extend(["| Window | State | Ready | Score | Checks |", "|---|---|---|---:|---:|"])
        for row in value.get("items", []):
            lines.append(
                f"| {row.get('window_id')} | {row.get('state')} | {str(row.get('release_ready')).lower()} | "
                f"{row.get('score')} | {row.get('passed_count')}/{row.get('check_count')} |"
            )
    else:
        lines.extend(["| # | Kind | Severity | Passed | Detail |", "|---:|---|---|---|---|"])
        for row in value.get("items", []):
            lines.append(
                f"| {row.get('ordinal')} | {row.get('kind')} | {row.get('severity')} | "
                f"{str(row.get('passed')).lower()} | {row.get('detail')} |"
            )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded release-window query resources and filters."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_QUERY_PREFIX
        + "-v1",
        "resources": {"summary": ["summary"], "checks": ["checks"]},
        "filters": ["kind", "severity", "passed", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
        },
        "addressed_response": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_capabilities() -> (
    dict[str, Any]
):
    """Declare query and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
        "query_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_QUERY_PREFIX
        + "-v1",
        "operations": ["summary", "checks", "filter", "page", "json", "csv", "markdown", "verify"],
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query"
    )
]

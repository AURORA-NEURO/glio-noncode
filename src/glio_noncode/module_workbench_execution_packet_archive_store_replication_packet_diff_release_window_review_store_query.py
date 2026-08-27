"""Bounded queries and exports for durable release-window review stores."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    *,
    resource: str = "summary",
    kind: str | None = None,
    state: str | None = None,
    accepted: bool | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded summary, operation, check, or ledger-entry page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        value
    )
    if resource not in {"summary", "operations", "checks", "entries"}:
        raise ValidationError("review store query resource is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review store query offset is invalid")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1
        <= limit
        <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_LIMIT
    ):
        raise ValidationError("review store query limit is invalid")
    if accepted is not None and not isinstance(accepted, bool):
        raise ValidationError("review store accepted filter is invalid")
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("review store passed filter is invalid")
    if text is not None:
        text = _text(text, "review store query text")
    if resource == "summary":
        rows = [value.summary()]
        index_used = "store_id"
    elif resource == "operations":
        rows = [item.to_dict() for item in value.operations]
        if kind is not None:
            rows = [row for row in rows if row["kind"] == kind]
        if state is not None:
            rows = [row for row in rows if row["state"] == state]
        if accepted is not None:
            rows = [row for row in rows if row["accepted"] is accepted]
        if text is not None:
            rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
        index_used = "ordinal"
    elif resource == "checks":
        rows = [item.to_dict() for item in value.checks]
        if kind is not None:
            rows = [row for row in rows if row["kind"] == kind]
        if state is not None:
            rows = [row for row in rows if row["state"] == state]
        if passed is not None:
            rows = [row for row in rows if row["passed"] is passed]
        if text is not None:
            rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
        index_used = "ordinal"
    else:
        ledger = getattr(value, "ledger", None)
        if ledger is None:
            raise ValidationError("review store entries require a hydrated ledger")
        rows = [item.to_dict() for item in ledger.entries]
        if state is not None:
            rows = [row for row in rows if row["state"] == state]
        if accepted is not None:
            rows = [row for row in rows if row["accepted"] is accepted]
        if text is not None:
            rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
        index_used = "ordinal"
    body = {
        "resource": resource,
        "query": {
            "kind": kind,
            "state": state,
            "accepted": accepted,
            "passed": passed,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
        "release_ready": value.release_ready,
        "append_only": value.append_only,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY_PREFIX,
        )
    }


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_directory(
    directory: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Load a durable store and execute one bounded query."""

    return query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            directory
        ),
        **kwargs,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review store query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("review store query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query(
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
        "release_ready",
        "append_only",
        "reference_address",
        "content_address",
        "ordinal",
        "operation_id",
        "entry_id",
        "kind",
        "state",
        "passed",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query(
        value
    )
    lines = [
        "# Durable Release-Window Review Store Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Identifier | Kind | State | Accepted | Passed | Detail |",
        "|---:|---|---|---|---|---|---|",
    ]
    for row in value.get("items", []):
        identifier = (
            row.get("entry_id") or row.get("operation_id") or row.get("store_id") or row.get("kind")
        )
        lines.append(
            f"| {row.get('ordinal', '')} | {identifier} | {row.get('kind', '')} | {row.get('state', '')} | {str(row.get('accepted', '')).lower()} | {str(row.get('passed', '')).lower()} | {row.get('detail', '')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "operations", "checks", "entries"],
        "filters": ["kind", "state", "accepted", "passed", "text"],
        "bounded": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "operations", "checks", "entries"],
        "filters": ["kind", "state", "accepted", "passed", "text", "offset", "limit"],
        "exports": ["json", "csv", "markdown"],
        "identity_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query"
    )
]

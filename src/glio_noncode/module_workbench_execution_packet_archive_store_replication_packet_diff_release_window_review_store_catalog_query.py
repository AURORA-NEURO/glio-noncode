"""Bounded, deterministic queries over durable review-store catalogs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
)
from .serialization import canonical_json, content_hash

CATALOG_QUERY_RESOURCES = ("summary", "entries", "operations", "checks")


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _bounded(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _filter_row(
    row: Mapping[str, Any],
    *,
    store_id: str | None,
    state: str | None,
    accepted: bool | None,
    release_ready: bool | None,
    window_address: str | None,
    text: str | None,
) -> bool:
    if store_id is not None and row.get("store_id") != store_id:
        return False
    if state is not None and row.get("state", row.get("store_state")) != state:
        return False
    if accepted is not None and row.get("accepted") != accepted:
        return False
    if release_ready is not None and row.get("release_ready") != release_ready:
        return False
    if window_address is not None and row.get("window_address") != window_address:
        return False
    if text is not None:
        haystack = " ".join(str(value) for value in row.values()).casefold()
        if text.casefold() not in haystack:
            return False
    return True


def _rows(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    resource: str,
) -> list[dict[str, Any]]:
    if resource == "summary":
        return [value.summary()]
    if resource == "entries":
        return [item.to_dict() for item in value.entries]
    if resource == "operations":
        return [item.to_dict() for item in value.operations]
    if resource == "checks":
        return [item.to_dict() for item in value.checks]
    raise ValidationError(f"resource must be one of {', '.join(CATALOG_QUERY_RESOURCES)}")


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    *,
    resource: str = "summary",
    store_id: str | None = None,
    state: str | None = None,
    accepted: bool | None = None,
    release_ready: bool | None = None,
    window_address: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return one bounded catalog resource page."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("catalog queries require a typed catalog")
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        value
    )
    resource = _text(resource, "catalog query resource", 64)
    if resource not in CATALOG_QUERY_RESOURCES:
        raise ValidationError(f"resource must be one of {', '.join(CATALOG_QUERY_RESOURCES)}")
    if store_id is not None:
        store_id = _text(store_id, "catalog query store ID", 256)
    if state is not None:
        state = _text(state, "catalog query state", 64)
    if window_address is not None:
        window_address = _text(window_address, "catalog query window address", 512)
    if text is not None:
        text = _text(text, "catalog query text", 4096)
    offset = _bounded(offset, "catalog query offset", 1000000)
    limit = _bounded(
        limit,
        "catalog query limit",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
        if resource == "entries"
        else MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
    )
    if limit == 0:
        raise ValidationError("catalog query limit must be positive")
    source = _rows(value, resource)
    filtered = [
        row
        for row in source
        if _filter_row(
            row,
            store_id=store_id,
            state=state,
            accepted=accepted,
            release_ready=release_ready,
            window_address=window_address,
            text=text,
        )
    ]
    page = filtered[offset : offset + limit]
    payload = {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
        + "-query",
        "catalog_id": value.catalog_id,
        "catalog_address": value.content_address,
        "resource": resource,
        "offset": offset,
        "limit": limit,
        "total": len(filtered),
        "returned": len(page),
        "accepted": True,
        "rows": page,
    }
    payload["query_address"] = content_hash(
        payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
        + "-query",
    )
    return payload


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_directory(
    directory: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    return query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            directory
        ),
        **kwargs,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query(
    payload: Mapping[str, Any],
) -> bool:
    """Verify the query receipt address without reintroducing transport paths."""

    if not isinstance(payload, Mapping) or not payload.get("accepted"):
        return False
    address = payload.get("query_address")
    if not isinstance(address, str):
        return False
    body = dict(payload)
    body.pop("query_address", None)
    return address == content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX
        + "-query",
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_json(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query(
        payload
    ):
        raise ValidationError("catalog query receipt is invalid")
    return canonical_json(dict(payload)) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_csv(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query(
        payload
    ):
        raise ValidationError("catalog query receipt is invalid")
    rows = payload.get("rows", ())
    if not isinstance(rows, list):
        raise ValidationError("catalog query rows are invalid")
    fields = (
        "ordinal",
        "store_id",
        "operation_id",
        "kind",
        "state",
        "store_state",
        "window_address",
        "store_address",
        "ledger_address",
        "release_ready",
        "accepted",
        "passed",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_markdown(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query(
        payload
    ):
        raise ValidationError("catalog query receipt is invalid")
    rows = payload.get("rows", ())
    if not isinstance(rows, list):
        raise ValidationError("catalog query rows are invalid")
    lines = [
        "# Review-Store Catalog Query",
        "",
        f"- resource: `{payload.get('resource')}`",
        f"- returned: `{payload.get('returned')}` of `{payload.get('total')}`",
        f"- query address: `{payload.get('query_address')}`",
        "",
        "| # | Store | Kind | State | Accepted | Address |",
        "|---:|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('ordinal', '')} | `{row.get('store_id', '')}` | `{row.get('kind', '')}` | `{row.get('state', row.get('store_state', ''))}` | `{str(row.get('accepted', '')).lower()}` | `{row.get('content_address', '')}` |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "resources": list(CATALOG_QUERY_RESOURCES),
        "filters": [
            "store_id",
            "state",
            "accepted",
            "release_ready",
            "window_address",
            "text",
            "offset",
            "limit",
        ],
        "limits": {
            "entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
            "operations": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
            "default_limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": [
            "query",
            "filter",
            "paginate",
            "json",
            "csv",
            "markdown",
            "verify",
            "schema",
            "capabilities",
        ],
        "resources": list(CATALOG_QUERY_RESOURCES),
        "guarantees": [
            "bounded results",
            "deterministic ordering",
            "addressed query receipts",
            "canonical JSON",
            "path-free output",
            "timestamp-free output",
            "identity-free output",
        ],
    }

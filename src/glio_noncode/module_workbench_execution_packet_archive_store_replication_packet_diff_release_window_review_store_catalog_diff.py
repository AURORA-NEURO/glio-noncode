"""Compare durable review-store catalogs by addressed member history."""

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
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_action,
)
from .serialization import canonical_json, content_hash


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


def _action(
    ordinal: int, store_id: str, kind: str, left: Any | None, right: Any | None
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction:
    if (
        kind
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.ADDED.value
    ):
        detail = "member store was added to the catalog"
    elif (
        kind
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.REMOVED.value
    ):
        detail = "member store was removed from the catalog"
    elif (
        kind
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.UNCHANGED.value
    ):
        detail = "member store address is unchanged"
    else:
        detail = "member store address or state changed"
    body = {
        "ordinal": ordinal,
        "store_id": store_id,
        "kind": kind,
        "left_address": None if left is None else left.content_address,
        "right_address": None if right is None else right.content_address,
        "left_state": None if left is None else left.store_state,
        "right_state": None if right is None else right.store_state,
        "accepted": True,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction(
        **body, content_address="pending:action"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_action(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    *,
    diff_id: str = "glio-noncode-review-store-catalog-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff:
    """Classify every member ID in two verified catalog revisions."""

    if not isinstance(
        left,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ) or not isinstance(
        right,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("catalog diff requires two typed catalogs")
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        left
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        right
    )
    diff_id = _text(diff_id, "catalog diff ID", 256)
    left_entries = {item.store_id: item for item in left.entries}
    right_entries = {item.store_id: item for item in right.entries}
    actions = []
    for ordinal, store_id in enumerate(sorted(set(left_entries) | set(right_entries))):
        left_entry = left_entries.get(store_id)
        right_entry = right_entries.get(store_id)
        if left_entry is None:
            kind = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.ADDED.value
        elif right_entry is None:
            kind = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.REMOVED.value
        elif left_entry.content_address == right_entry.content_address:
            kind = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.UNCHANGED.value
        else:
            kind = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind.CHANGED.value
        actions.append(_action(ordinal, store_id, kind, left_entry, right_entry))
    action_tuple = tuple(actions)
    added_count = sum(item.kind == "added" for item in action_tuple)
    removed_count = sum(item.kind == "removed" for item in action_tuple)
    unchanged_count = sum(item.kind == "unchanged" for item in action_tuple)
    changed_count = sum(item.kind == "changed" for item in action_tuple)
    append_only = removed_count == 0 and changed_count == 0
    if left.content_address == right.content_address:
        state = "exact"
    elif append_only:
        state = "append_only"
    else:
        state = "divergent"
    body = {
        "diff_id": diff_id,
        "left_catalog_id": left.catalog_id,
        "right_catalog_id": right.catalog_id,
        "left_catalog_address": left.content_address,
        "right_catalog_address": right.content_address,
        "state": state,
        "append_only": append_only,
        "accepted": all(item.accepted for item in action_tuple),
        "actions": action_tuple,
        "added_count": added_count,
        "removed_count": removed_count,
        "unchanged_count": unchanged_count,
        "changed_count": changed_count,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff(
        **body, content_address="pending:diff"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_from_directories(
    left_directory: str | Path, right_directory: str | Path, **kwargs: Any
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff:
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            left_directory
        ),
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            right_directory
        ),
        **kwargs,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
) -> bool:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
    ):
        raise ValidationError("catalog diff verification requires a typed diff")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            value
        )
        != value.content_address
    ):
        raise ValidationError("catalog diff content address mismatch")
    return True


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "store_id",
        "kind",
        "left_address",
        "right_address",
        "left_state",
        "right_state",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for action in value.actions:
        writer.writerow(action.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
        value
    )
    lines = [
        "# Review-Store Catalog Diff",
        "",
        f"- state: `{value.state}`",
        f"- append-only: `{str(value.append_only).lower()}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- added: `{value.added_count}`",
        f"- removed: `{value.removed_count}`",
        f"- changed: `{value.changed_count}`",
        f"- unchanged: `{value.unchanged_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Store | Action | Left state | Right state |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {action.ordinal} | `{action.store_id}` | `{action.kind}` | `{action.left_state or ''}` | `{action.right_state or ''}` |"
        for action in value.actions
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
    *,
    action: str | None = None,
    store_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
        value
    )
    if action is not None and action not in {"added", "removed", "unchanged", "changed"}:
        raise ValidationError("catalog diff action is invalid")
    offset = _bounded(offset, "catalog diff query offset", 1000000)
    limit = _bounded(
        limit,
        "catalog diff query limit",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
        * 2,
    )
    if limit == 0:
        raise ValidationError("catalog diff query limit must be positive")
    if text is not None:
        text = _text(text, "catalog diff query text", 4096).casefold()
    rows = [item.to_dict() for item in value.actions]
    if action is not None:
        rows = [row for row in rows if row["kind"] == action]
    if store_id is not None:
        rows = [row for row in rows if row["store_id"] == store_id]
    if text is not None:
        rows = [
            row for row in rows if text in " ".join(str(item) for item in row.values()).casefold()
        ]
    page = rows[offset : offset + limit]
    payload = {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_PREFIX
        + "-query",
        "diff_id": value.diff_id,
        "diff_address": value.content_address,
        "resource": "actions",
        "offset": offset,
        "limit": limit,
        "total": len(rows),
        "returned": len(page),
        "accepted": True,
        "rows": page,
    }
    payload["query_address"] = content_hash(
        payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_PREFIX
        + "-query",
    )
    return payload


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query(
    payload: Mapping[str, Any],
) -> bool:
    if (
        not isinstance(payload, Mapping)
        or not payload.get("accepted")
        or not isinstance(payload.get("query_address"), str)
    ):
        return False
    body = dict(payload)
    address = body.pop("query_address")
    return address == content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_PREFIX
        + "-query",
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_json(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query(
        payload
    ):
        raise ValidationError("catalog diff query receipt is invalid")
    return canonical_json(dict(payload)) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_csv(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query(
        payload
    ):
        raise ValidationError("catalog diff query receipt is invalid")
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "store_id",
        "kind",
        "left_state",
        "right_state",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in payload.get("rows", ()):
        writer.writerow({field: row.get(field) for field in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_markdown(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query(
        payload
    ):
        raise ValidationError("catalog diff query receipt is invalid")
    lines = [
        "# Review-Store Catalog Diff Query",
        "",
        f"- returned: `{payload.get('returned')}` of `{payload.get('total')}`",
        f"- query address: `{payload.get('query_address')}`",
        "",
        "| # | Store | Action | Left | Right |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('store_id', '')}` | `{row.get('kind', '')}` | `{row.get('left_state', '')}` | `{row.get('right_state', '')}` |"
        for row in payload.get("rows", ())
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "states": ["exact", "append_only", "divergent"],
        "actions": ["added", "removed", "unchanged", "changed"],
        "limits": {
            "actions": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
            * 2,
            "limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": [
            "compare",
            "classify",
            "query",
            "verify",
            "json",
            "csv",
            "markdown",
            "schema",
            "capabilities",
        ],
        "guarantees": [
            "exact comparison",
            "append-only proof",
            "divergence classification",
            "bounded actions",
            "addressed query receipts",
            "deterministic output",
            "identity-free output",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "resource": "actions",
        "filters": ["action", "store_id", "text", "offset", "limit"],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": ["query", "filter", "paginate", "verify", "json", "csv", "markdown"],
        "guarantees": [
            "bounded results",
            "stable action ordering",
            "canonical receipt",
            "identity-free output",
        ],
    }

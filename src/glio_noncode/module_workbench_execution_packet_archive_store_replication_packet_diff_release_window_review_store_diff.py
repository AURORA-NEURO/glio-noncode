"""Revision comparison for durable release-window review stores."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_action,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _action(
    ordinal: int,
    entry_id: str,
    action: str,
    left_address: str | None,
    right_address: str | None,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction:
    body = {
        "ordinal": ordinal,
        "entry_id": _text(entry_id, "review store diff entry ID", 256),
        "action": action,
        "left_address": left_address,
        "right_address": right_address,
        "detail": _text(detail, "review store diff action detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction(
        **body, content_address="pending:action"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_action(
            provisional
        ),
    )


def _entries(
    store: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
) -> tuple[Any, ...]:
    ledger = getattr(store, "ledger", None)
    if ledger is None:
        raise ValidationError("review store diff requires a hydrated ledger")
    return tuple(ledger.entries)


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
    *,
    diff_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff:
    """Compare addressed ledger entries and prove whether the right side appends."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        left
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
        right
    )
    left_entries = _entries(left)
    right_entries = _entries(right)
    left_by_id = {item.entry_id: item for item in left_entries}
    right_by_id = {item.entry_id: item for item in right_entries}
    if len(left_by_id) != len(left_entries) or len(right_by_id) != len(right_entries):
        raise ValidationError("review store diff requires unique ledger entry IDs")
    ordered_ids = [item.entry_id for item in left_entries] + [
        item.entry_id for item in right_entries if item.entry_id not in left_by_id
    ]
    actions: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction
    ] = []
    for entry_id in ordered_ids:
        left_entry = left_by_id.get(entry_id)
        right_entry = right_by_id.get(entry_id)
        left_address = left_entry.content_address if left_entry is not None else None
        right_address = right_entry.content_address if right_entry is not None else None
        if left_entry is None:
            action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.ADDED.value
            detail = "right store contains a new review entry"
        elif right_entry is None:
            action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.REMOVED.value
            detail = "right store no longer contains a left review entry"
        elif left_address == right_address:
            action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.UNCHANGED.value
            detail = "review entry address is unchanged"
        else:
            action = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.CHANGED.value
            detail = "review entry ID is retained but its addressed content changed"
        actions.append(_action(len(actions), entry_id, action, left_address, right_address, detail))
    added_count = sum(item.action == "added" for item in actions)
    removed_count = sum(item.action == "removed" for item in actions)
    unchanged_count = sum(item.action == "unchanged" for item in actions)
    changed_count = sum(item.action == "changed" for item in actions)
    left_ids = tuple(item.entry_id for item in left_entries)
    right_ids = tuple(item.entry_id for item in right_entries)
    append_only = (
        removed_count == 0 and changed_count == 0 and right_ids[: len(left_ids)] == left_ids
    )
    state = (
        "exact"
        if append_only and added_count == 0
        else "append_only"
        if append_only
        else "divergent"
    )
    body = {
        "diff_id": _text(diff_id, "review store diff ID", 256),
        "left_store_address": left.content_address,
        "right_store_address": right.content_address,
        "left_head_address": left.head_address,
        "right_head_address": right.head_address,
        "actions": tuple(actions),
        "action_count": len(actions),
        "added_count": added_count,
        "removed_count": removed_count,
        "unchanged_count": unchanged_count,
        "changed_count": changed_count,
        "state": state,
        "append_only": append_only,
        "accepted": append_only,
    }
    provisional = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff(
            **body, content_address="pending:diff"
        )
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_from_directories(
    left_directory: str | Path,
    right_directory: str | Path,
    *,
    diff_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-store-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff:
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            left_directory
        ),
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            right_directory
        ),
        diff_id=diff_id,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
    ):
        raise ValidationError("review store diff verification requires a typed diff")
    for action in value.actions:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_action(
                action
            )
            != action.content_address
        ):
            raise ValidationError("review store diff action address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review store diff address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "entry_id",
        "action",
        "left_address",
        "right_address",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for action in value.actions:
        writer.writerow(action.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
        value
    )
    lines = [
        "# Durable Release-Window Review Store Diff",
        "",
        f"- state: `{value.state}`",
        f"- append-only: `{str(value.append_only).lower()}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- actions: `{value.action_count}`; added: `{value.added_count}`; removed: `{value.removed_count}`; changed: `{value.changed_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Entry | Action | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.entry_id} | {item.action} | {item.detail} |"
        for item in value.actions
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
    *,
    action: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
        value
    )
    if action is not None and action not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind
    }:
        raise ValidationError("review store diff query action is invalid")
    if text is not None:
        text = _text(text, "review store diff query text")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review store diff query offset is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 512:
        raise ValidationError("review store diff query limit is invalid")
    rows = [item.to_dict() for item in value.actions]
    if action is not None:
        rows = [row for row in rows if row["action"] == action]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {"action": action, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "diff": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review store diff query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX
            + "-query",
        )
        != value["content_address"]
    ):
        raise ValidationError("review store diff query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "entry_id",
        "action",
        "left_address",
        "right_address",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value.get("items", []):
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query(
        value
    )
    lines = [
        "# Durable Review Store Diff Query",
        "",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Entry | Action | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | {row.get('entry_id', '')} | {row.get('action', '')} | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX
        + "-v1",
        "actions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState
        ],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX
        + "-v1",
        "operations": ["build", "verify", "query", "json", "csv", "markdown"],
        "append_only_proof": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX
        + "-query-v1",
        "filters": ["action", "text", "offset", "limit"],
        "bounded": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX
        + "-query-v1",
        "resources": ["actions"],
        "exports": ["json", "csv", "markdown"],
        "identity_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff"
    )
]

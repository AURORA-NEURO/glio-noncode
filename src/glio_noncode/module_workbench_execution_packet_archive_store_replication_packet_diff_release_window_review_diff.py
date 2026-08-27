"""Compare release-window review-ledger revisions with append-only proofs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_ACTION_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_VERSION,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_action,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _action(
    ordinal: int,
    entry_id: str,
    action: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind,
    left_address: str | None,
    right_address: str | None,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction:
    body = {
        "ordinal": ordinal,
        "entry_id": _text(entry_id, "review diff entry ID", 256),
        "action": action.value,
        "left_address": left_address,
        "right_address": right_address,
        "detail": _text(detail, "review diff action detail", 4096),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_ACTION_PREFIX
        + ":pending-action",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_action(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    *,
    diff_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff:
    """Compare two revisions and prove whether the right side only appends."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        left
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        right
    )
    if (
        left.window_address != right.window_address
        or left.assurance_address != right.assurance_address
        or left.sensitivity_address != right.sensitivity_address
    ):
        raise ValidationError("review ledger diff inputs must share an evidence scope")
    left_map = {item.entry_id: item for item in left.entries}
    right_map = {item.entry_id: item for item in right.entries}
    if len(left_map) != len(left.entries) or len(right_map) != len(right.entries):
        raise ValidationError("review ledger diff inputs contain duplicate entry IDs")
    ordered_ids = [item.entry_id for item in right.entries]
    ordered_ids.extend(item.entry_id for item in left.entries if item.entry_id not in right_map)
    actions = []
    for ordinal, entry_id in enumerate(ordered_ids):
        left_entry = left_map.get(entry_id)
        right_entry = right_map.get(entry_id)
        if left_entry is None:
            actions.append(
                _action(
                    ordinal,
                    entry_id,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.ADDED,
                    None,
                    right_entry.content_address,
                    "entry exists only in the right revision",
                )
            )
        elif right_entry is None:
            actions.append(
                _action(
                    ordinal,
                    entry_id,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.REMOVED,
                    left_entry.content_address,
                    None,
                    "entry exists only in the left revision",
                )
            )
        elif left_entry.content_address == right_entry.content_address:
            actions.append(
                _action(
                    ordinal,
                    entry_id,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.UNCHANGED,
                    left_entry.content_address,
                    right_entry.content_address,
                    "entry is unchanged between revisions",
                )
            )
        else:
            actions.append(
                _action(
                    ordinal,
                    entry_id,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.CHANGED,
                    left_entry.content_address,
                    right_entry.content_address,
                    "entry content changed between revisions",
                )
            )
    action_tuple = tuple(actions)
    unchanged_prefix = tuple(item.entry_id for item in left.entries) == tuple(
        item.entry_id for item in right.entries[: len(left.entries)]
    ) and all(
        item.action
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.UNCHANGED.value
        for item in action_tuple[: len(left.entries)]
    )
    added_tail = all(
        item.action
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.ADDED.value
        for item in action_tuple[len(left.entries) :]
    )
    append_only = unchanged_prefix and added_tail
    added_count = sum(
        item.action
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.ADDED.value
        for item in action_tuple
    )
    removed_count = sum(
        item.action
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.REMOVED.value
        for item in action_tuple
    )
    unchanged_count = sum(
        item.action
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.UNCHANGED.value
        for item in action_tuple
    )
    changed_count = sum(
        item.action
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.CHANGED.value
        for item in action_tuple
    )
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState.EXACT.value
        if append_only and added_count == 0
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState.APPEND_ONLY.value
        if append_only
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState.DIVERGENT.value
    )
    body = {
        "diff_id": _text(diff_id, "review diff ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_BOUNDARY,
        "left_ledger_address": left.content_address,
        "right_ledger_address": right.content_address,
        "left_head_address": left.head_address,
        "right_head_address": right.head_address,
        "actions": action_tuple,
        "action_count": len(action_tuple),
        "added_count": added_count,
        "removed_count": removed_count,
        "unchanged_count": unchanged_count,
        "changed_count": changed_count,
        "state": state,
        "append_only": append_only,
        "accepted": changed_count == 0 and removed_count == 0,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX
        + ":pending-diff",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff:
    """Verify action addresses and diff aggregate address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
    ):
        raise ValidationError("review diff verification requires a typed diff")
    for item in value.actions:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_action(
                item
            )
            != item.content_address
        ):
            raise ValidationError("review diff action address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review diff address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
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
    for item in value.actions:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Diff",
        "",
        f"- state: `{value.state}`",
        f"- append-only: `{str(value.append_only).lower()}`",
        f"- actions: `{value.action_count}`; added: `{value.added_count}`; removed: `{value.removed_count}`; changed: `{value.changed_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Entry | Action | Detail |",
        "|---:|---|---|---|",
    ]
    for item in value.actions:
        lines.append(f"| {item.ordinal} | {item.entry_id} | {item.action} | {item.detail} |")
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
    *,
    resource: str = "summary",
    action: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded diff summary or action page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
        value
    )
    if resource not in {"summary", "actions"}:
        raise ValidationError("review diff query resource is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review diff query offset is invalid")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT
    ):
        raise ValidationError("review diff query limit is invalid")
    if action is not None and action not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind
    }:
        raise ValidationError("review diff action filter is invalid")
    if text is not None:
        _text(text, "review diff query text")
    if resource == "summary":
        rows = [value.summary()]
        index_used = "diff_id"
    else:
        rows = [item.to_dict() for item in value.actions]
        if action is not None:
            rows = [row for row in rows if row["action"] == action]
        if text is not None:
            rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
        index_used = "ordinal"
    body = {
        "resource": resource,
        "query": {"action": action, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "reference_address": value.content_address,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
        "append_only": value.append_only,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX
            + "-query",
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a diff query envelope."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review diff query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX
        + "-query",
    )
    if value["content_address"] != expected:
        raise ValidationError("review diff query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query(
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
        "append_only",
        "reference_address",
        "content_address",
        "ordinal",
        "entry_id",
        "action",
        "left_address",
        "right_address",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            writer.writerow(envelope | dict(row))
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Diff Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- append-only: `{str(value.get('append_only')).lower()}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Entry | Action | Detail |",
        "|---:|---|---|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('entry_id')} | {row.get('action')} | {row.get('detail')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_schema() -> (
    dict[str, Any]
):
    """Describe review-ledger revision diff semantics."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_BOUNDARY,
        "actions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState
        ],
        "append_only_proof": "unchanged left prefix followed by added right tail",
        "accepted_requires": ["no_changed_actions", "no_removed_actions"],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_capabilities() -> (
    dict[str, Any]
):
    """Declare review-ledger diff operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_VERSION,
        "operations": ["build", "verify", "json", "csv", "markdown", "query"],
        "append_only_proof": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded diff-action queries."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX
        + "-query-v1",
        "resources": {"summary": ["summary"], "actions": ["actions"]},
        "filters": ["action", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_query_capabilities() -> (
    dict[str, Any]
):
    """Declare diff query and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX
        + "-query-v1",
        "operations": ["summary", "actions", "filter", "page", "json", "csv", "markdown", "verify"],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
    )
]

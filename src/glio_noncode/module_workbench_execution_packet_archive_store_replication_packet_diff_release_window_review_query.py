"""Bounded queries and exports for release-window review ledgers."""

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
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_QUERY_PREFIX,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _optional_text(value: Any, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _enum_value(value: Any, enum_type: type, field: str) -> str | None:
    if value is None:
        return None
    normalized = value.value if isinstance(value, enum_type) else value
    if normalized not in {item.value for item in enum_type}:
        raise ValidationError(f"{field} is invalid")
    return normalized


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    *,
    resource: str = "summary",
    decision: str | None = None,
    state: str | None = None,
    release_ready: bool | None = None,
    accepted: bool | None = None,
    has_required_actions: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return one bounded summary or ordered entry page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        value
    )
    resource = _text(resource, "review query resource", 64).casefold()
    if resource not in {"summary", "entries"}:
        raise ValidationError("review query resource must be summary or entries")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("review query offset must be non-negative")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT
    ):
        raise ValidationError("review query limit is outside the bound")
    decision = _enum_value(
        decision,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
        "review query decision",
    )
    state = _enum_value(
        state,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState,
        "review query state",
    )
    release_ready = _optional_bool(release_ready, "review query release-ready filter")
    accepted = _optional_bool(accepted, "review query accepted filter")
    has_required_actions = _optional_bool(has_required_actions, "review query action filter")
    text = _optional_text(text, "review query text")
    if resource == "summary":
        rows: list[dict[str, Any]] = [value.summary()]
        index_used = "ledger_id"
    else:
        rows = [item.to_dict() for item in value.entries]
        if decision is not None:
            rows = [row for row in rows if row["decision"] == decision]
        if state is not None:
            rows = [row for row in rows if row["state"] == state]
        if release_ready is not None:
            rows = [row for row in rows if row["release_ready"] is release_ready]
        if accepted is not None:
            rows = [row for row in rows if row["accepted"] is accepted]
        if has_required_actions is not None:
            rows = [row for row in rows if bool(row["required_actions"]) is has_required_actions]
        index_used = "ordinal"
    if text is not None:
        needle = text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    body = {
        "resource": resource,
        "query": {
            "decision": decision,
            "state": state,
            "release_ready": release_ready,
            "accepted": accepted,
            "has_required_actions": has_required_actions,
            "text": text,
        },
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
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify the query envelope and its reference address."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("review query response must be addressed")
    if value.get("append_only") is not True:
        raise ValidationError("review query must preserve append-only state")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("review query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query(
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
        "window_address",
        "assurance_address",
        "sensitivity_address",
        "decision",
        "state",
        "release_ready",
        "rationale",
        "required_actions",
        "previous_entry_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    envelope = {key: value.get(key) for key in fields if key in value}
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            item = dict(row)
            item["required_actions"] = " | ".join(item.get("required_actions", ()))
            writer.writerow(envelope | item)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review Query",
        "",
        f"- resource: `{value.get('resource')}`",
        f"- page: `{value.get('offset')}` to `{value.get('limit')}` of `{value.get('total')}`",
        f"- append-only: `{str(value.get('append_only')).lower()}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Entry | Decision | State | Ready | Actions | Rationale |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for row in value.get("items", []):
        lines.append(
            f"| {row.get('ordinal')} | {row.get('entry_id')} | {row.get('decision')} | {row.get('state')} | "
            f"{str(row.get('release_ready')).lower()} | {len(row.get('required_actions', ()))} | {row.get('rationale')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_schema() -> (
    dict[str, Any]
):
    """Describe bounded ledger query filters."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_QUERY_PREFIX
        + "-v1",
        "resources": {"summary": ["summary"], "entries": ["entries"]},
        "filters": [
            "decision",
            "state",
            "release_ready",
            "accepted",
            "has_required_actions",
            "text",
        ],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT,
        },
        "append_only": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query_capabilities() -> (
    dict[str, Any]
):
    """Declare query, filter, and export operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_QUERY_PREFIX
        + "-v1",
        "operations": ["summary", "entries", "filter", "page", "json", "csv", "markdown", "verify"],
        "append_only": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query"
    )
    or name.startswith(
        "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_query"
    )
]

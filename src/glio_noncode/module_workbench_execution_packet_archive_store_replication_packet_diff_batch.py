"""Bounded multi-packet diff matrices for release-window review."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_batch"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-batch"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_ITEM_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-item"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_QUERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_ITEMS = 256
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_LIMIT = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT
)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _count(value: Any, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 1:
        raise ValidationError(f"{field} must be a ratio between zero and one")
    return float(value)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem:
    """One pair outcome in a bounded packet-diff matrix."""

    def __init__(
        self,
        ordinal: int,
        pair_id: str,
        left_packet_address: str,
        right_packet_address: str,
        diff_address: str,
        state: str,
        release_state: str,
        accepted: bool,
        release_ready: bool,
        changed_artifact_count: int,
        removed_required_count: int,
        passed_count: int,
        check_count: int,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.pair_id = pair_id
        self.left_packet_address = left_packet_address
        self.right_packet_address = right_packet_address
        self.diff_address = diff_address
        self.state = state
        self.release_state = release_state
        self.accepted = accepted
        self.release_ready = release_ready
        self.changed_artifact_count = changed_artifact_count
        self.removed_required_count = removed_required_count
        self.passed_count = passed_count
        self.check_count = check_count
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "batch item ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_ITEMS,
        )
        _text(self.pair_id, "batch pair ID", 256)
        for value, field in (
            (self.left_packet_address, "left packet address"),
            (self.right_packet_address, "right packet address"),
            (self.diff_address, "diff address"),
            (self.content_address, "batch item address"),
        ):
            _address(value, field)
        _text(self.state, "batch item state", 64)
        _text(self.release_state, "batch item release state", 64)
        _bool(self.accepted, "batch item accepted")
        _bool(self.release_ready, "batch item release ready")
        for value, field in (
            (self.changed_artifact_count, "changed artifact count"),
            (self.removed_required_count, "removed required count"),
            (self.passed_count, "passed count"),
            (self.check_count, "check count"),
        ):
            _count(value, field)
        if self.passed_count > self.check_count:
            raise ValidationError("batch item passed count exceeds check count")
        _text(self.detail, "batch item detail", 2048)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "pair_id": self.pair_id,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "diff_address": self.diff_address,
            "state": self.state,
            "release_state": self.release_state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "changed_artifact_count": self.changed_artifact_count,
            "removed_required_count": self.removed_required_count,
            "passed_count": self.passed_count,
            "check_count": self.check_count,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_item(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem,
) -> str:
    """Compute one deterministic matrix-item address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_ITEM_PREFIX,
    )


def _item(
    ordinal: int,
    pair_id: str,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    release: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem:
    body = {
        "ordinal": ordinal,
        "pair_id": pair_id,
        "left_packet_address": diff.left_packet_address,
        "right_packet_address": diff.right_packet_address,
        "diff_address": diff.content_address,
        "state": diff.state.value,
        "release_state": release.state.value,
        "accepted": diff.accepted,
        "release_ready": release.accepted,
        "changed_artifact_count": diff.changed_artifact_count,
        "removed_required_count": diff.removed_required_count,
        "passed_count": diff.passed_count,
        "check_count": diff.check_count,
        "detail": "packet pair diff and release decision verified",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_ITEM_PREFIX
        + ":pending-item",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_item(
            provisional
        ),
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch:
    """A content-addressed release matrix across multiple packet pairs."""

    def __init__(
        self,
        batch_id: str,
        version: str,
        boundary: str,
        items: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem, ...],
        item_count: int,
        accepted_count: int,
        release_ready_count: int,
        matched_count: int,
        extended_count: int,
        changed_count: int,
        diverged_count: int,
        blocked_count: int,
        promotable_count: int,
        hold_count: int,
        release_blocked_count: int,
        score: float,
        accepted: bool,
        release_ready: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.batch_id = batch_id
        self.version = version
        self.boundary = boundary
        self.items = items
        self.item_count = item_count
        self.accepted_count = accepted_count
        self.release_ready_count = release_ready_count
        self.matched_count = matched_count
        self.extended_count = extended_count
        self.changed_count = changed_count
        self.diverged_count = diverged_count
        self.blocked_count = blocked_count
        self.promotable_count = promotable_count
        self.hold_count = hold_count
        self.release_blocked_count = release_blocked_count
        self.score = score
        self.accepted = accepted
        self.release_ready = release_ready
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.batch_id, "diff batch ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_VERSION
        ):
            raise ValidationError("diff batch version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_BOUNDARY  # noqa: E501
        ):
            raise ValidationError("diff batch boundary is invalid")
        _count(
            self.item_count,
            "batch item count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_ITEMS,
        )
        if not self.items or self.item_count != len(self.items):
            raise ValidationError("diff batch item count does not conserve")
        if tuple(item.ordinal for item in self.items) != tuple(range(self.item_count)):
            raise ValidationError("diff batch item ordinals are not ordered")
        if len({item.pair_id for item in self.items}) != self.item_count:
            raise ValidationError("diff batch pair IDs must be unique")
        if any(
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_item(
                item
            )
            != item.content_address
            for item in self.items
        ):
            raise ValidationError("diff batch item address mismatch")
        counts = {
            "accepted_count": sum(item.accepted for item in self.items),
            "release_ready_count": sum(item.release_ready for item in self.items),
            "matched_count": sum(item.state == "matched" for item in self.items),
            "extended_count": sum(item.state == "extended" for item in self.items),
            "changed_count": sum(item.state == "changed" for item in self.items),
            "diverged_count": sum(item.state == "diverged" for item in self.items),
            "blocked_count": sum(item.state == "blocked" for item in self.items),
            "promotable_count": sum(item.release_state == "promotable" for item in self.items),
            "hold_count": sum(item.release_state == "hold" for item in self.items),
            "release_blocked_count": sum(item.release_state == "blocked" for item in self.items),
        }
        for field, expected in counts.items():
            if getattr(self, field) != expected:
                raise ValidationError(f"diff batch {field} does not conserve")
        for value, field in (
            (self.accepted_count, "accepted count"),
            (self.release_ready_count, "release-ready count"),
            (self.matched_count, "matched count"),
            (self.extended_count, "extended count"),
            (self.changed_count, "changed count"),
            (self.diverged_count, "diverged count"),
            (self.blocked_count, "blocked count"),
            (self.promotable_count, "promotable count"),
            (self.hold_count, "hold count"),
            (self.release_blocked_count, "release blocked count"),
        ):
            _count(value, field, self.item_count)
        _ratio(self.score, "diff batch score")
        expected_score = self.release_ready_count / self.item_count
        if abs(self.score - expected_score) > 1e-12:
            raise ValidationError("diff batch score does not conserve")
        _bool(self.accepted, "diff batch accepted")
        _bool(self.release_ready, "diff batch release ready")
        if self.accepted != (self.accepted_count == self.item_count):
            raise ValidationError("diff batch accepted state does not conserve")
        if self.release_ready != (self.release_ready_count == self.item_count):
            raise ValidationError("diff batch release state does not conserve")
        _text(self.detail, "diff batch detail", 2048)
        _address(self.content_address, "diff batch address")

    def summary(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "version": self.version,
            "boundary": self.boundary,
            "item_count": self.item_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "matched_count": self.matched_count,
            "extended_count": self.extended_count,
            "changed_count": self.changed_count,
            "diverged_count": self.diverged_count,
            "blocked_count": self.blocked_count,
            "promotable_count": self.promotable_count,
            "hold_count": self.hold_count,
            "release_blocked_count": self.release_blocked_count,
            "score": self.score,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary() | {"detail": self.detail}
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
) -> str:
    """Compute a deterministic batch address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_PREFIX,
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
    pairs: Sequence[
        tuple[
            str,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
        ]
    ],
    *,
    batch_id: str = (  # noqa: E501
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch:
    """Build a matrix from verified typed diff/release pairs."""

    _count(
        len(pairs),
        "diff batch input count",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_ITEMS,
    )
    if not pairs:
        raise ValidationError("diff batch requires at least one pair")
    seen: set[str] = set()
    items: list[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchItem] = []
    for ordinal, entry in enumerate(pairs):
        if not isinstance(entry, tuple) or len(entry) != 3:
            raise ValidationError("diff batch pair must contain ID, diff, and release")
        pair_id, diff, release = entry
        pair_id = _text(pair_id, "diff batch pair ID", 256)
        if pair_id in seen:
            raise ValidationError("diff batch pair IDs must be unique")
        seen.add(pair_id)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff(diff)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
            release
        )
        if release.diff_address != diff.content_address:
            raise ValidationError("diff batch release does not reference its diff")
        items.append(_item(ordinal, pair_id, diff, release))
    item_tuple = tuple(items)
    body = {
        "batch_id": batch_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_VERSION,  # noqa: E501
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_BOUNDARY,  # noqa: E501
        "items": item_tuple,
        "item_count": len(item_tuple),
        "accepted_count": sum(item.accepted for item in item_tuple),
        "release_ready_count": sum(item.release_ready for item in item_tuple),
        "matched_count": sum(item.state == "matched" for item in item_tuple),
        "extended_count": sum(item.state == "extended" for item in item_tuple),
        "changed_count": sum(item.state == "changed" for item in item_tuple),
        "diverged_count": sum(item.state == "diverged" for item in item_tuple),
        "blocked_count": sum(item.state == "blocked" for item in item_tuple),
        "promotable_count": sum(item.release_state == "promotable" for item in item_tuple),
        "hold_count": sum(item.release_state == "hold" for item in item_tuple),
        "release_blocked_count": sum(item.release_state == "blocked" for item in item_tuple),
        "score": sum(item.release_ready for item in item_tuple) / len(item_tuple),
        "accepted": all(item.accepted for item in item_tuple),
        "release_ready": all(item.release_ready for item in item_tuple),
        "detail": "verified packet diff matrix completed",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_PREFIX
        + ":pending-batch",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories(  # noqa: E501
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    *,
    batch_id: str = (  # noqa: E501
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch:
    """Load multiple persisted packet pairs and build one verified matrix."""

    if not pairs:
        raise ValidationError("diff batch requires at least one directory pair")
    typed_pairs = []
    for pair_id, left_directory, right_directory in pairs:
        diff = load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs(
            left_directory,
            right_directory,
            diff_id=f"{batch_id}:{pair_id}",
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        typed_pairs.append((pair_id, diff, release))
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
        typed_pairs,
        batch_id=batch_id,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch:
    """Verify every item and the aggregate matrix address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    ):
        raise ValidationError("diff batch verification requires a typed batch")
    for item in value.items:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_item(
                item
            )
            != item.content_address
        ):
            raise ValidationError("diff batch item address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(value)
        != value.content_address
    ):
        raise ValidationError("diff batch address mismatch")
    return value


def _page(
    rows: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    text: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_LIMIT
    ):
        raise ValidationError("diff batch query paging is invalid")
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item).casefold()]
    return rows[offset : offset + limit], len(rows)


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    *,
    resource: str = "summary",
    state: str | None = None,
    release_state: str | None = None,
    accepted: bool | None = None,
    release_ready: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_DEFAULT_LIMIT,  # noqa: E501
) -> dict[str, Any]:
    """Return a bounded matrix summary or item page."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(value)
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "batch_id"
    elif normalized == "items":
        rows = [item.to_dict() for item in value.items]
        if state:
            rows = [item for item in rows if item["state"] == state]
        if release_state:
            rows = [item for item in rows if item["release_state"] == release_state]
        if accepted is not None:
            rows = [item for item in rows if item["accepted"] is accepted]
        if release_ready is not None:
            rows = [item for item in rows if item["release_ready"] is release_ready]
        index_used = "pair_id"
    else:
        raise ValidationError("unsupported diff batch resource")
    items, total = _page(rows, offset=offset, limit=limit, text=text)
    body = {
        "resource": normalized,
        "query": {
            "state": state,
            "release_state": release_state,
            "accepted": accepted,
            "release_ready": release_ready,
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
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a content-addressed matrix query response."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("diff batch query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("diff batch query address mismatch")
    items = value.get("items", ())
    if not isinstance(value.get("total"), int) or value["total"] < len(items):
        raise ValidationError("diff batch query total is inconsistent")
    if not isinstance(value.get("offset"), int) or not isinstance(value.get("limit"), int):
        raise ValidationError("diff batch query paging is malformed")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
) -> str:
    """Serialize a full matrix as canonical JSON."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
) -> str:
    """Serialize matrix items as deterministic CSV."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(value)
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "pair_id",
        "left_packet_address",
        "right_packet_address",
        "state",
        "release_state",
        "accepted",
        "release_ready",
        "changed_artifact_count",
        "removed_required_count",
        "passed_count",
        "check_count",
        "diff_address",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "ordinal",
        "pair_id",
        "left_packet_address",
        "right_packet_address",
        "state",
        "release_state",
        "accepted",
        "release_ready",
        "changed_artifact_count",
        "removed_required_count",
        "diff_address",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for ordinal, item in enumerate(value.get("items", ())):
        writer.writerow(
            {
                "resource": value.get("resource"),
                "ordinal": ordinal,
                "pair_id": item.get("pair_id"),
                "left_packet_address": item.get("left_packet_address"),
                "right_packet_address": item.get("right_packet_address"),
                "state": item.get("state"),
                "release_state": item.get("release_state"),
                "accepted": item.get("accepted"),
                "release_ready": item.get("release_ready"),
                "changed_artifact_count": item.get("changed_artifact_count"),
                "removed_required_count": item.get("removed_required_count"),
                "diff_address": item.get("diff_address"),
                "detail": item.get("detail"),
                "content_address": item.get("content_address"),
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
) -> str:
    """Render a human-readable release matrix."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(value)
    lines = [
        "# Archive Store Replication Packet Diff Batch",
        "",
        f"- Batch: `{value.batch_id}`",
        f"- Address: `{value.content_address}`",
        f"- Items: `{value.item_count}`",
        f"- Release-ready: `{value.release_ready_count}/{value.item_count}`",
        f"- Score: `{value.score:.3f}`",
        "",
        "| Ordinal | Pair | State | Release | Accepted | Ready | Changed | Removed |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for item in value.items:
        lines.append(
            f"| {item.ordinal} | `{item.pair_id}` | `{item.state}` | "
            f"`{item.release_state}` | {str(item.accepted).lower()} | "
            f"{str(item.release_ready).lower()} | {item.changed_artifact_count} | "
            f"{item.removed_required_count} |"
        )
    return "\n".join(lines) + "\n"


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_markdown(  # noqa: E501
    value: Mapping[str, Any],
) -> str:
    """Render a bounded matrix item query."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Batch Query",
        "",
        f"- Resource: `{value.get('resource')}`",
        f"- Reference: `{value.get('reference_address')}`",
        f"- Rows: `{len(value.get('items', ()))} / {value.get('total')}`",
        "",
        "| Ordinal | Pair | State | Release | Ready | Address |",
        "|---:|---|---|---|---:|---|",
    ]
    for ordinal, item in enumerate(value.get("items", ())):
        lines.append(
            f"| {ordinal} | `{item.get('pair_id', '')}` | `{item.get('state', '')}` | "
            f"`{item.get('release_state', '')}` | "
            f"{str(item.get('release_ready', '')).lower()} | "
            f"`{item.get('content_address', '')}` |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_schema() -> dict[
    str, Any
]:
    """Describe matrix resources, conservation, and limits."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_VERSION,  # noqa: E501
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_BOUNDARY,  # noqa: E501
        "resources": ["summary", "items"],
        "states": ["matched", "extended", "changed", "diverged", "blocked"],
        "release_states": ["promotable", "hold", "blocked"],
        "filters": ["state", "release_state", "accepted", "release_ready", "text"],
        "limits": {
            "max_items": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_ITEMS,  # noqa: E501
            "max_query_limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_LIMIT,  # noqa: E501
        },
        "conservation": [
            "item_counts",
            "state_counts",
            "release_state_counts",
            "conserved_counts",
            "accepted_count",
            "release_ready_count",
            "bounded_score",
        ],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    """Declare matrix comparison and review operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_VERSION,  # noqa: E501
        "operations": [
            "load_packet_pair_directories",
            "verify_typed_packet_diffs",
            "build_release_matrix",
            "count_boundary_states",
            "count_release_states",
            "calculate_release_ready_score",
            "query_batch_summary",
            "query_batch_items",
            "filter_state",
            "filter_release_state",
            "filter_acceptance",
            "filter_release_readiness",
            "page_offset_limit",
            "verify_batch_address",
            "export_json",
            "export_csv",
            "render_markdown",
        ],
        "guarantees": [
            "verified_inputs",
            "unique_pair_ids",
            "ordered_items",
            "conserved_counts",
            "bounded_score",
            "content_addressed_items",
            "content_addressed_queries",
            "no_filesystem_paths",
            "no_private_or_attribution_fields",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_schema() -> (  # noqa: E501
    dict[str, Any]
):
    """Describe matrix query resources, filters, and bounds."""

    return {
        "version": (
            "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query-v1"
        ),
        "resources": {"summary": ["summary"], "items": ["items"]},
        "filters": ["state", "release_state", "accepted", "release_ready", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BATCH_MAX_LIMIT,  # noqa: E501
        },
        "addressed_response": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    """Declare bounded matrix query and export operations."""

    return {
        "version": (
            "module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query-v1"
        ),
        "operations": [
            "query_batch_summary",
            "query_batch_items",
            "filter_state",
            "filter_release_state",
            "filter_acceptance",
            "filter_release_readiness",
            "filter_text",
            "page_offset_limit",
            "verify_content_address",
            "export_json",
            "export_csv",
            "render_markdown",
        ],
        "guarantees": [
            "bounded_results",
            "deterministic_filters",
            "content_addressed_response",
            "fail_closed_verification",
            "no_filesystem_paths",
        ],
    }

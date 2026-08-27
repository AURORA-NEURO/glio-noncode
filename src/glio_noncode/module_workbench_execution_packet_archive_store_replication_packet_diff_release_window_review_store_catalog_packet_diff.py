"""Compare catalog release packets by exact artifact and release state."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_ACTION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_PREFIX
    + "-action"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_ARTIFACTS = 5
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_CHECKS = 32


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffActionKind(
    StrEnum
):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    ADDED = "added"
    REMOVED = "removed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffState(
    StrEnum
):
    EXACT = "exact"
    CHANGED = "changed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffReleaseTransition(
    StrEnum
):
    UNCHANGED = "unchanged"
    PROMOTED = "promoted"
    HELD = "held"
    BLOCKED = "blocked"
    RECOVERED = "recovered"
    REGRESSED = "regressed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheckState(
    StrEnum
):
    PASSED = "passed"
    FAILED = "failed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _public(value: Any) -> bool:
    forbidden = {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public(item) for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_action(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffAction,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_ACTION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffAction:
    """One deterministic artifact transition between two packets."""

    def __init__(
        self,
        ordinal: int,
        artifact_kind: str,
        action: str,
        left_address: str | None,
        right_address: str | None,
        left_byte_address: str | None,
        right_byte_address: str | None,
        left_byte_count: int | None,
        right_byte_count: int | None,
        changed_fields: tuple[str, ...],
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.artifact_kind = artifact_kind
        self.action = action
        self.left_address = left_address
        self.right_address = right_address
        self.left_byte_address = left_byte_address
        self.right_byte_address = right_byte_address
        self.left_byte_count = left_byte_count
        self.right_byte_count = right_byte_count
        self.changed_fields = tuple(changed_fields)
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "packet diff action ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_ARTIFACTS
            - 1,
        )
        if self.artifact_kind not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
        }:
            raise ValidationError("packet diff artifact kind is invalid")
        if self.action not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffActionKind
        }:
            raise ValidationError("packet diff action kind is invalid")
        _address(self.left_address, "packet diff left artifact address", optional=True)
        _address(self.right_address, "packet diff right artifact address", optional=True)
        _address(self.left_byte_address, "packet diff left byte address", optional=True)
        _address(self.right_byte_address, "packet diff right byte address", optional=True)
        for value, field in (
            (self.left_byte_count, "packet diff left byte count"),
            (self.right_byte_count, "packet diff right byte count"),
        ):
            if value is not None:
                _count(value, field, 50_000_000)
        if self.action == "unchanged" and self.changed_fields:
            raise ValidationError("unchanged packet diff actions cannot carry changed fields")
        if self.action == "added" and self.left_address is not None:
            raise ValidationError("added packet diff actions cannot carry a left address")
        if self.action == "removed" and self.right_address is not None:
            raise ValidationError("removed packet diff actions cannot carry a right address")
        _bool(self.accepted, "packet diff action accepted flag")
        _text(self.detail, "packet diff action detail")
        _address(self.content_address, "packet diff action content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet diff action crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "artifact_kind": self.artifact_kind,
            "action": self.action,
            "left_address": self.left_address,
            "right_address": self.right_address,
            "left_byte_address": self.left_byte_address,
            "right_byte_address": self.right_byte_address,
            "left_byte_count": self.left_byte_count,
            "right_byte_count": self.right_byte_count,
            "changed_fields": list(self.changed_fields),
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck:
    """One independently addressed packet transition check."""

    def __init__(
        self,
        ordinal: int,
        kind: str,
        state: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.state = state
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "packet diff check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "packet diff check kind", 256)
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheckState
        }:
            raise ValidationError("packet diff check state is invalid")
        _bool(self.passed, "packet diff check passed flag")
        if self.state != ("passed" if self.passed else "failed"):
            raise ValidationError("packet diff check state does not conserve")
        _text(self.detail, "packet diff check detail")
        _address(self.content_address, "packet diff check content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet diff check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": self.state,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffVerification:
    """Addressed receipt proving a packet comparison was recomputed."""

    def __init__(
        self,
        diff_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.diff_address = diff_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "packet diff verification diff address")
        _count(
            self.check_count,
            "packet diff verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("packet diff verification checks must be non-empty and conserved")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("packet diff verification check address mismatch")
        if self.passed_count != sum(
            item.passed for item in self.checks
        ) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("packet diff verification counts do not conserve")
        _count(self.passed_count, "packet diff verification passed count", self.check_count)
        _count(self.failed_count, "packet diff verification failed count", self.check_count)
        _bool(self.accepted, "packet diff verification accepted flag")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("packet diff verification acceptance does not conserve")
        _address(self.content_address, "packet diff verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet diff verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_address": self.diff_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff:
    """Complete left/right packet comparison and release transition."""

    def __init__(
        self,
        diff_id: str,
        version: str,
        boundary: str,
        left_packet_id: str,
        right_packet_id: str,
        left_packet_address: str,
        right_packet_address: str,
        left_state: str,
        right_state: str,
        state: str,
        release_transition: str,
        action_count: int,
        unchanged_count: int,
        changed_count: int,
        added_count: int,
        removed_count: int,
        accepted: bool,
        release_ready: bool,
        actions: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffAction,
            ...,
        ],
        check_count: int,
        passed_count: int,
        failed_count: int,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.left_packet_id = left_packet_id
        self.right_packet_id = right_packet_id
        self.left_packet_address = left_packet_address
        self.right_packet_address = right_packet_address
        self.left_state = left_state
        self.right_state = right_state
        self.state = state
        self.release_transition = release_transition
        self.action_count = action_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.accepted = accepted
        self.release_ready = release_ready
        self.actions = tuple(actions)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "packet diff ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERSION
        ):
            raise ValidationError("packet diff version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_BOUNDARY
        ):
            raise ValidationError("packet diff boundary is invalid")
        _text(self.left_packet_id, "left packet ID", 256)
        _text(self.right_packet_id, "right packet ID", 256)
        _address(self.left_packet_address, "left packet address")
        _address(self.right_packet_address, "right packet address")
        for value, field in (
            (self.left_state, "left packet state"),
            (self.right_state, "right packet state"),
        ):
            if value not in {"ready", "held", "blocked"}:
                raise ValidationError(f"{field} is invalid")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffState
        }:
            raise ValidationError("packet diff state is invalid")
        if self.state == "exact" and self.left_packet_address != self.right_packet_address:
            raise ValidationError("exact packet diffs require equal packet addresses")
        if self.state == "changed" and self.left_packet_address == self.right_packet_address:
            raise ValidationError("changed packet diffs require distinct packet addresses")
        if self.release_transition not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffReleaseTransition
        }:
            raise ValidationError("packet diff release transition is invalid")
        _count(
            self.action_count,
            "packet diff action count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_ARTIFACTS,
        )
        if self.action_count != len(self.actions) or self.action_count == 0:
            raise ValidationError("packet diff actions must be non-empty and conserved")
        for ordinal, action in enumerate(self.actions):
            if (
                action.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_action(
                    action
                )
                != action.content_address
            ):
                raise ValidationError("packet diff action address mismatch")
        counts = (
            sum(item.action == "unchanged" for item in self.actions),
            sum(item.action == "changed" for item in self.actions),
            sum(item.action == "added" for item in self.actions),
            sum(item.action == "removed" for item in self.actions),
        )
        if counts != (
            self.unchanged_count,
            self.changed_count,
            self.added_count,
            self.removed_count,
        ):
            raise ValidationError("packet diff action counts do not conserve")
        for value, field in (
            (self.unchanged_count, "packet diff unchanged count"),
            (self.changed_count, "packet diff changed count"),
            (self.added_count, "packet diff added count"),
            (self.removed_count, "packet diff removed count"),
        ):
            _count(value, field, self.action_count)
        _bool(self.accepted, "packet diff accepted flag")
        _bool(self.release_ready, "packet diff release-ready flag")
        _count(
            self.check_count,
            "packet diff check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("packet diff checks must be non-empty and conserved")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("packet diff check address mismatch")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.checks),
            sum(not item.passed for item in self.checks),
        ):
            raise ValidationError("packet diff check counts do not conserve")
        _count(self.passed_count, "packet diff passed count", self.check_count)
        _count(self.failed_count, "packet diff failed count", self.check_count)
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("packet diff acceptance does not conserve")
        if self.release_ready != (self.accepted and self.right_state == "ready"):
            raise ValidationError("packet diff readiness does not conserve")
        _address(self.content_address, "packet diff content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "left_packet_id": self.left_packet_id,
            "right_packet_id": self.right_packet_id,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "left_state": self.left_state,
            "right_state": self.right_state,
            "state": self.state,
            "release_transition": self.release_transition,
            "action_count": self.action_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "content_address": self.content_address,
        }

    def to_dict(
        self, *, include_actions: bool = True, include_checks: bool = True
    ) -> dict[str, Any]:
        body = self.summary()
        if include_actions:
            body["actions"] = [item.to_dict() for item in self.actions]
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _optional_address(value: Any, field: str) -> str | None:
    return _address(value, field, optional=True)


def _action(
    ordinal: int,
    kind: str,
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact
    | None,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact
    | None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffAction:
    fields = []
    if left is None:
        action = "added"
    elif right is None:
        action = "removed"
    else:
        for field in ("content_address", "byte_address", "byte_count"):
            if getattr(left, field) != getattr(right, field):
                fields.append(field)
        action = "unchanged" if not fields else "changed"
    detail = {
        "unchanged": "artifact is byte and content identical",
        "changed": "artifact content or exact bytes changed",
        "added": "artifact exists only in the right packet",
        "removed": "artifact exists only in the left packet",
    }[action]
    body = {
        "ordinal": ordinal,
        "artifact_kind": kind,
        "action": action,
        "left_address": None if left is None else left.content_address,
        "right_address": None if right is None else right.content_address,
        "left_byte_address": None if left is None else left.byte_address,
        "right_byte_address": None if right is None else right.byte_address,
        "left_byte_count": None if left is None else left.byte_count,
        "right_byte_count": None if right is None else right.byte_count,
        "changed_fields": tuple(fields),
        "accepted": True,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffAction(
        **body, content_address="pending:action"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffAction(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_action(
            provisional
        ),
    )


def _transition(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
) -> str:
    if (
        left.state == right.state
        and left.accepted == right.accepted
        and left.release_ready == right.release_ready
    ):
        return "unchanged"
    if left.state == "blocked" and right.state in {"held", "ready"}:
        return "recovered"
    if right.state == "ready" and left.state != "ready":
        return "promoted"
    if right.state == "blocked":
        return "blocked"
    if right.state == "held":
        return "held"
    return "regressed"


def _transition_values(
    left_state: str,
    left_accepted: bool,
    left_release_ready: bool,
    right_state: str,
    right_accepted: bool,
    right_release_ready: bool,
) -> str:
    if (
        left_state == right_state
        and left_accepted == right_accepted
        and left_release_ready == right_release_ready
    ):
        return "unchanged"
    if left_state == "blocked" and right_state in {"held", "ready"}:
        return "recovered"
    if right_state == "ready" and left_state != "ready":
        return "promoted"
    if right_state == "blocked":
        return "blocked"
    if right_state == "held":
        return "held"
    return "regressed"


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "state": "passed" if passed else "failed",
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_check(
            provisional
        ),
    )


def _checks(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffCheck,
    ...,
]:
    return (
        _check(
            0,
            "packet-boundary",
            value.left_packet_address.split(":", 1)[0] != ""
            and value.right_packet_address.split(":", 1)[0] != "",
            "addressed packets",
            (value.left_packet_address, value.right_packet_address),
            "both packet references are addressed",
        ),
        _check(
            1,
            "artifact-conservation",
            value.action_count == 5 and value.action_count == len(value.actions),
            5,
            value.action_count,
            "all five packet artifact kinds are compared",
        ),
        _check(
            2,
            "action-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_action(
                    item
                )
                == item.content_address
                for item in value.actions
            ),
            "recomputed action addresses",
            tuple(item.content_address for item in value.actions),
            "every artifact action address is conserved",
        ),
        _check(
            3,
            "state-classification",
            value.state
            == ("exact" if value.left_packet_address == value.right_packet_address else "changed"),
            "exact or changed",
            value.state,
            "packet state follows aggregate addresses",
        ),
        _check(
            4,
            "release-transition",
            value.release_transition
            == _transition_values(
                value.left_state,
                True,
                value.left_state == "ready",
                value.right_state,
                True,
                value.right_state == "ready",
            ),
            "known transition",
            value.release_transition,
            "release transition follows the compared packet states",
        ),
        _check(
            5,
            "public-boundary",
            _public(value.to_dict()),
            True,
            True,
            "diff projection contains deterministic public fields",
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    *,
    diff_id: str = "glio-noncode-review-store-catalog-packet-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff:
    if not isinstance(
        left,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    ) or not isinstance(
        right,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    ):
        raise ValidationError("packet diff requires two typed packets")
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        left
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        right
    )
    actions = []
    left_by_kind = {item.kind: item for item in left.artifacts}
    right_by_kind = {item.kind: item for item in right.artifacts}
    for ordinal, kind in enumerate(
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
    ):
        actions.append(_action(ordinal, kind, left_by_kind.get(kind), right_by_kind.get(kind)))
    actions = tuple(actions)
    body = {
        "diff_id": _text(diff_id, "packet diff ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_BOUNDARY,
        "left_packet_id": left.packet_id,
        "right_packet_id": right.packet_id,
        "left_packet_address": left.content_address,
        "right_packet_address": right.content_address,
        "left_state": left.state,
        "right_state": right.state,
        "state": "exact" if left.content_address == right.content_address else "changed",
        "release_transition": _transition(left, right),
        "action_count": len(actions),
        "unchanged_count": sum(item.action == "unchanged" for item in actions),
        "changed_count": sum(item.action == "changed" for item in actions),
        "added_count": sum(item.action == "added" for item in actions),
        "removed_count": sum(item.action == "removed" for item in actions),
        "accepted": True,
        "release_ready": right.release_ready,
        "actions": actions,
    }
    seed = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff(
        **body,
        check_count=6,
        passed_count=6,
        failed_count=0,
        checks=(
            _check(0, "packet-boundary", True, "addressed packets", "addressed", "temporary"),
            _check(1, "artifact-conservation", True, 5, 5, "temporary"),
            _check(
                2, "action-addresses", True, "recomputed action addresses", "conserved", "temporary"
            ),
            _check(3, "state-classification", True, "exact or changed", body["state"], "temporary"),
            _check(
                4,
                "release-transition",
                True,
                "known transition",
                body["release_transition"],
                "temporary",
            ),
            _check(5, "public-boundary", True, True, True, "temporary"),
        ),
        content_address="pending:diff",
    )
    checks = _checks(seed)
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff(
        **body,
        check_count=len(checks),
        passed_count=len(checks),
        failed_count=0,
        checks=checks,
        content_address="pending:diff",
    )
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff(
        **body,
        check_count=6,
        passed_count=6,
        failed_count=0,
        checks=_checks(value),
        content_address="pending:diff",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff(
        **body,
        check_count=6,
        passed_count=6,
        failed_count=0,
        checks=value.checks,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            value
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
    left_directory: str | Path,
    right_directory: str | Path,
    *,
    diff_id: str = "glio-noncode-review-store-catalog-packet-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff:
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            left_directory
        ),
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            right_directory
        ),
        diff_id=diff_id,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    ):
        raise ValidationError("packet diff verification requires a typed diff")
    checks = list(_checks(value))
    checks.insert(
        0,
        _check(
            0,
            "diff-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                value
            )
            == value.content_address,
            "recomputed diff address",
            value.content_address,
            "aggregate packet diff address is conserved",
        ),
    )
    checks = tuple(
        _check(ordinal, check.kind, check.passed, check.expected, check.observed, check.detail)
        for ordinal, check in enumerate(checks)
    )
    body = {
        "diff_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_verification(
            provisional
        ),
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "artifact_kind",
            "action",
            "left_address",
            "right_address",
            "left_byte_address",
            "right_byte_address",
            "left_byte_count",
            "right_byte_count",
            "changed_fields",
            "accepted",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for action in value.actions:
        row = action.to_dict()
        row["changed_fields"] = ",".join(action.changed_fields)
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        value
    )
    lines = [
        "# Review-Store Catalog Packet Diff",
        "",
        f"- state: `{value.state}`",
        f"- transition: `{value.release_transition}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- changed: `{value.changed_count}`",
        f"- unchanged: `{value.unchanged_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Artifact | Action | Left bytes | Right bytes |",
        "|---:|---|---|---:|---:|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.artifact_kind}` | `{item.action}` | {item.left_byte_count or ''} | {item.right_byte_count or ''} |"
        for item in value.actions
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    *,
    resource: str = "actions",
    action: str | None = None,
    artifact_kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        value
    )
    if resource not in {"summary", "actions", "checks"}:
        raise ValidationError("packet diff query resource is invalid")
    if action is not None and action not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffActionKind
    }:
        raise ValidationError("packet diff query action is invalid")
    if artifact_kind is not None and artifact_kind not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
    }:
        raise ValidationError("packet diff query artifact kind is invalid")
    if text is not None:
        text = _text(text, "packet diff query text")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("packet diff query bounds are invalid")
    if resource == "summary":
        rows = [value.summary()]
    elif resource == "checks":
        rows = [item.to_dict() for item in value.checks]
    else:
        rows = [item.to_dict() for item in value.actions]
        if action is not None:
            rows = [row for row in rows if row["action"] == action]
        if artifact_kind is not None:
            rows = [row for row in rows if row["artifact_kind"] == artifact_kind]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {
            "resource": resource,
            "action": action,
            "artifact_kind": artifact_kind,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "diff": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("packet diff query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("packet diff query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "artifact_kind",
            "action",
            "left_address",
            "right_address",
            "left_byte_count",
            "right_byte_count",
            "changed_fields",
            "accepted",
            "detail",
            "content_address",
        ),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in value.get("items", []):
        if isinstance(row, Mapping):
            row = dict(row)
            row["changed_fields"] = (
                ",".join(row.get("changed_fields", []))
                if isinstance(row.get("changed_fields"), list)
                else row.get("changed_fields", "")
            )
            writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query(
        value
    )
    lines = [
        "# Review-Store Catalog Packet Diff Query",
        "",
        f"- resource: `{value.get('query', {}).get('resource', '')}`",
        f"- rows: `{value.get('total', 0)}`",
        f"- address: `{value.get('content_address', '')}`",
        "",
        "| # | Artifact | Action | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('artifact_kind', '')}` | `{row.get('action', '')}` | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_BOUNDARY,
        "actions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffActionKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffState
        ],
        "transitions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiffReleaseTransition
        ],
        "resources": ["summary", "actions", "checks"],
        "max_artifacts": 5,
        "bounded": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_VERSION,
        "operations": ["build", "verify", "compare", "query", "json", "csv", "markdown"],
        "compares_exact_artifact_bytes": True,
        "classifies_release_transitions": True,
        "addressed_checks": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "actions", "checks"],
        "filters": ["action", "artifact_kind", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DIFF_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "actions", "checks"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }

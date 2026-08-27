"""Typed contracts for durable, identity-free release-window review stores.

The review ledger is intentionally immutable once built.  This module adds a
durable boundary around that ledger without making the store a second review
authority: every store points at one ledger address, records an append-only
operation chain, and exposes only deterministic aggregate values.  Filesystem
locations, timestamps, credentials, and attribution metadata are transport
concerns and are never part of these contracts.
"""

from __future__ import annotations

# ruff: noqa: E501
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-operation"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CHECK_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-check"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERIFICATION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-verification"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_REPLAY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-replay"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_QUERY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-query"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-diff"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_ACTION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-diff-action"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MANIFEST = "review-store.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_LEDGER = "review-ledger.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATIONS = "review-operations.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS = 128
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_TEXT = 4096

_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "credential",
        "email",
        "generated_by",
        "hostname",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "openai",
        "patient_id",
        "phone",
        "private",
        "private_key",
        "programming_language",
        "secret",
        "token",
        "user",
        "user_id",
        "username",
    }
)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _optional_text(value: Any, field: str, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _enum(value: Any, enum_type: type[StrEnum], field: str) -> str:
    if isinstance(value, enum_type):
        return value.value
    if not isinstance(value, str):
        raise ValidationError(f"{field} is invalid")
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValidationError(f"{field} is invalid") from exc


def _public(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in _FORBIDDEN_PUBLIC_KEYS:
                return False
            if not _public(item):
                return False
    elif isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState(
    StrEnum
):
    """Durable store states derived from the persisted review head."""

    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    DIVERGED = "diverged"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind(
    StrEnum
):
    """Operations retained in the append-only store journal."""

    GENESIS = "genesis"
    APPEND = "append"
    VERIFY = "verify"
    REPLAY = "replay"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationState(
    StrEnum
):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckPlane(
    StrEnum
):
    FORMAT = "format"
    LEDGER = "ledger"
    CHAIN = "chain"
    STORAGE = "storage"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState(
    StrEnum
):
    PASSED = "passed"
    FAILED = "failed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState(
    StrEnum
):
    MATCHED = "matched"
    DIVERGED = "diverged"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind(
    StrEnum
):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState(
    StrEnum
):
    EXACT = "exact"
    APPEND_ONLY = "append_only"
    DIVERGENT = "divergent"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation:
    """One addressed journal operation for a durable review store."""

    def __init__(
        self,
        ordinal: int,
        operation_id: str,
        kind: str,
        state: str,
        input_address: str | None,
        output_address: str | None,
        previous_operation_address: str | None,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.operation_id = operation_id
        self.kind = kind
        self.state = state
        self.input_address = input_address
        self.output_address = output_address
        self.previous_operation_address = previous_operation_address
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "review store operation ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS
            - 1,
        )
        _text(self.operation_id, "review store operation ID", 256)
        kind = _enum(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind,
            "review store operation kind",
        )
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationState,
            "review store operation state",
        )
        _optional_address(self.input_address, "review store operation input address")
        _optional_address(self.output_address, "review store operation output address")
        _optional_address(
            self.previous_operation_address, "review store operation previous address"
        )
        _bool(self.accepted, "review store operation accepted flag")
        _text(self.detail, "review store operation detail")
        _address(self.content_address, "review store operation content address")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationState.REJECTED.value
            and self.accepted
        ):
            raise ValidationError("rejected review store operations cannot be accepted")
        if (
            kind
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind.GENESIS.value
            and self.ordinal != 0
        ):
            raise ValidationError("genesis review store operation must be first")
        if self.ordinal == 0 and self.previous_operation_address is not None:
            raise ValidationError("first review store operation cannot have a predecessor")
        if self.ordinal > 0 and self.previous_operation_address is None:
            raise ValidationError("non-first review store operations require a predecessor")
        if not _public(self.to_dict()):
            raise ValidationError("review store operation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "previous_operation_address": self.previous_operation_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_operation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_OPERATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck:
    """One independent durable-store verification check."""

    def __init__(
        self,
        ordinal: int,
        plane: str,
        kind: str,
        state: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.plane = plane
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
            "review store check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS
            - 1,
        )
        _enum(
            self.plane,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckPlane,
            "review store check plane",
        )
        _text(self.kind, "review store check kind", 256)
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState,
            "review store check state",
        )
        _bool(self.passed, "review store check passed flag")
        _text(self.detail, "review store check detail")
        _address(self.content_address, "review store check content address")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState.PASSED.value
            and not self.passed
        ):
            raise ValidationError("passed review store checks must be marked passed")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheckState.FAILED.value
            and self.passed
        ):
            raise ValidationError("failed review store checks cannot be marked passed")
        if not _public(self.to_dict()):
            raise ValidationError("review store check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "plane": self.plane,
            "kind": self.kind,
            "state": self.state,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore:
    """Durable index around one immutable release-window review ledger."""

    def __init__(
        self,
        store_id: str,
        version: str,
        boundary: str,
        ledger_address: str,
        head_address: str | None,
        entry_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        append_only: bool,
        operations: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation,
            ...,
        ],
        operation_count: int,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck,
            ...,
        ],
        check_count: int,
        content_address: str,
    ) -> None:
        self.store_id = store_id
        self.version = version
        self.boundary = boundary
        self.ledger_address = ledger_address
        self.head_address = head_address
        self.entry_count = entry_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.append_only = append_only
        self.operations = tuple(operations)
        self.operation_count = operation_count
        self.checks = tuple(checks)
        self.check_count = check_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.store_id, "review store ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERSION
        ):
            raise ValidationError("review store version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_BOUNDARY
        ):
            raise ValidationError("review store boundary is invalid")
        _address(self.ledger_address, "review store ledger address")
        _optional_address(self.head_address, "review store head address")
        _count(self.entry_count, "review store entry count", 256)
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState,
            "review store state",
        )
        _bool(self.release_ready, "review store release-ready flag")
        _bool(self.accepted, "review store accepted flag")
        _bool(self.append_only, "review store append-only flag")
        if not self.append_only:
            raise ValidationError("review store must be append-only")
        _count(
            self.operation_count,
            "review store operation count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS,
        )
        if self.operation_count != len(self.operations):
            raise ValidationError("review store operation count does not conserve")
        for ordinal, operation in enumerate(self.operations):
            if not isinstance(
                operation,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperation,
            ):
                raise ValidationError("review store operations must be typed")
            if operation.ordinal != ordinal:
                raise ValidationError("review store operation ordinals are not contiguous")
            expected_previous = self.operations[ordinal - 1].content_address if ordinal else None
            if operation.previous_operation_address != expected_previous:
                raise ValidationError("review store operation chain is not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_operation(
                    operation
                )
                != operation.content_address
            ):
                raise ValidationError("review store operation address mismatch")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.EMPTY.value
            and (
                self.operation_count != 1
                or self.operations[0].kind
                != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind.GENESIS.value
            )
        ):
            raise ValidationError("empty review stores require exactly one genesis operation")
        if (
            state
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.EMPTY.value
            and not self.operation_count
        ):
            raise ValidationError("non-empty review stores require operations")
        _count(
            self.check_count,
            "review store check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS,
        )
        if self.check_count != len(self.checks):
            raise ValidationError("review store check count does not conserve")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(
                check,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck,
            ):
                raise ValidationError("review store checks must be typed")
            if check.ordinal != ordinal:
                raise ValidationError("review store check ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("review store check address mismatch")
        expected_accepted = (
            self.entry_count > 0
            and bool(self.operations)
            and all(item.accepted for item in self.operations)
            and all(item.passed for item in self.checks)
        )
        if self.accepted != expected_accepted:
            raise ValidationError("review store acceptance does not conserve")
        if (
            self.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.READY.value
            and not self.release_ready
        ):
            raise ValidationError("ready review stores must be release-ready")
        if (
            self.release_ready
            and self.state
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.READY.value
        ):
            raise ValidationError("only ready review stores may be release-ready")
        _address(self.content_address, "review store content address")
        if not _public(self.to_dict()):
            raise ValidationError("review store crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "store_id": self.store_id,
            "version": self.version,
            "boundary": self.boundary,
            "ledger_address": self.ledger_address,
            "head_address": self.head_address,
            "entry_count": self.entry_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "append_only": self.append_only,
            "operation_count": self.operation_count,
            "check_count": self.check_count,
            "content_address": self.content_address,
        }

    def to_dict(
        self, *, include_operations: bool = True, include_checks: bool = True
    ) -> dict[str, Any]:
        body = self.summary()
        if include_operations:
            body["operations"] = [item.to_dict() for item in self.operations]
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreVerification:
    """Independent verification receipt for a durable review store."""

    def __init__(
        self,
        store_id: str,
        store_address: str,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCheck,
            ...,
        ],
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.store_id = store_id
        self.store_address = store_address
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.store_id, "review store verification store ID", 256)
        _address(self.store_address, "review store verification store address")
        _count(
            self.check_count,
            "review store verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_CHECKS,
        )
        if self.check_count != len(self.checks):
            raise ValidationError("review store verification check count does not conserve")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("review store verification passed count does not conserve")
        if self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("review store verification failed count does not conserve")
        _count(self.passed_count, "review store verification passed count", self.check_count)
        _count(self.failed_count, "review store verification failed count", self.check_count)
        _bool(self.accepted, "review store verification accepted flag")
        if self.accepted != bool(self.checks) and self.accepted:
            raise ValidationError("empty review store verification cannot be accepted")
        if self.accepted != (self.check_count > 0 and self.failed_count == 0):
            raise ValidationError("review store verification acceptance does not conserve")
        _address(self.content_address, "review store verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("review store verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "store_id": self.store_id,
            "store_address": self.store_address,
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplay:
    """Addressed result of rehydrating a persisted review store."""

    def __init__(
        self,
        store_id: str,
        store_address: str,
        ledger_address: str,
        expected_head_address: str | None,
        observed_head_address: str | None,
        entry_count: int,
        operation_count: int,
        state: str,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.store_id = store_id
        self.store_address = store_address
        self.ledger_address = ledger_address
        self.expected_head_address = expected_head_address
        self.observed_head_address = observed_head_address
        self.entry_count = entry_count
        self.operation_count = operation_count
        self.state = state
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.store_id, "review store replay store ID", 256)
        _address(self.store_address, "review store replay store address")
        _address(self.ledger_address, "review store replay ledger address")
        _optional_address(self.expected_head_address, "review store replay expected head address")
        _optional_address(self.observed_head_address, "review store replay observed head address")
        _count(self.entry_count, "review store replay entry count", 256)
        _count(
            self.operation_count,
            "review store replay operation count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS,
        )
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState,
            "review store replay state",
        )
        _bool(self.accepted, "review store replay accepted flag")
        if self.accepted != (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplayState.MATCHED.value
        ):
            raise ValidationError("review store replay acceptance does not follow state")
        _address(self.content_address, "review store replay content address")
        if not _public(self.to_dict()):
            raise ValidationError("review store replay crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "store_id": self.store_id,
            "store_address": self.store_address,
            "ledger_address": self.ledger_address,
            "expected_head_address": self.expected_head_address,
            "observed_head_address": self.observed_head_address,
            "entry_count": self.entry_count,
            "operation_count": self.operation_count,
            "state": self.state,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_replay(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreReplay,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_REPLAY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction:
    """One operation or ledger-entry action in a store revision diff."""

    def __init__(
        self,
        ordinal: int,
        entry_id: str,
        action: str,
        left_address: str | None,
        right_address: str | None,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.entry_id = entry_id
        self.action = action
        self.left_address = left_address
        self.right_address = right_address
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "review store diff action ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS
            - 1,
        )
        _text(self.entry_id, "review store diff action entry ID", 256)
        _enum(
            self.action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind,
            "review store diff action",
        )
        _optional_address(self.left_address, "review store diff action left address")
        _optional_address(self.right_address, "review store diff action right address")
        _text(self.detail, "review store diff action detail")
        _address(self.content_address, "review store diff action content address")
        if not _public(self.to_dict()):
            raise ValidationError("review store diff action crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "entry_id": self.entry_id,
            "action": self.action,
            "left_address": self.left_address,
            "right_address": self.right_address,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_action(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_ACTION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff:
    """Deterministic comparison between two durable review-store revisions."""

    def __init__(
        self,
        diff_id: str,
        left_store_address: str,
        right_store_address: str,
        left_head_address: str | None,
        right_head_address: str | None,
        actions: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffAction,
            ...,
        ],
        action_count: int,
        added_count: int,
        removed_count: int,
        unchanged_count: int,
        changed_count: int,
        state: str,
        append_only: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.diff_id = diff_id
        self.left_store_address = left_store_address
        self.right_store_address = right_store_address
        self.left_head_address = left_head_address
        self.right_head_address = right_head_address
        self.actions = tuple(actions)
        self.action_count = action_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.state = state
        self.append_only = append_only
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "review store diff ID", 256)
        _address(self.left_store_address, "review store diff left store address")
        _address(self.right_store_address, "review store diff right store address")
        _optional_address(self.left_head_address, "review store diff left head address")
        _optional_address(self.right_head_address, "review store diff right head address")
        _count(
            self.action_count,
            "review store diff action count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_MAX_OPERATIONS,
        )
        if self.action_count != len(self.actions):
            raise ValidationError("review store diff action count does not conserve")
        expected_counts = {
            "added_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.ADDED.value
                for item in self.actions
            ),
            "removed_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.REMOVED.value
                for item in self.actions
            ),
            "unchanged_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.UNCHANGED.value
                for item in self.actions
            ),
            "changed_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffActionKind.CHANGED.value
                for item in self.actions
            ),
        }
        for ordinal, action in enumerate(self.actions):
            if action.ordinal != ordinal:
                raise ValidationError("review store diff action ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_action(
                    action
                )
                != action.content_address
            ):
                raise ValidationError("review store diff action address mismatch")
        if any(getattr(self, field) != value for field, value in expected_counts.items()):
            raise ValidationError("review store diff action counts do not conserve")
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState,
            "review store diff state",
        )
        expected_append_only = self.removed_count == 0 and self.changed_count == 0
        if self.append_only != expected_append_only:
            raise ValidationError("review store diff append-only flag does not conserve")
        expected_state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState.EXACT.value
            if self.added_count == 0 and expected_append_only
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState.APPEND_ONLY.value
            if expected_append_only
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState.DIVERGENT.value
        )
        if state != expected_state:
            raise ValidationError("review store diff state does not follow actions")
        _bool(self.accepted, "review store diff accepted flag")
        if self.accepted != expected_append_only:
            raise ValidationError("review store diff acceptance does not follow actions")
        _address(self.content_address, "review store diff content address")
        if not _public(self.to_dict()):
            raise ValidationError("review store diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "left_store_address": self.left_store_address,
            "right_store_address": self.right_store_address,
            "left_head_address": self.left_head_address,
            "right_head_address": self.right_head_address,
            "action_count": self.action_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "state": self.state,
            "append_only": self.append_only,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_actions: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_actions:
            body["actions"] = [item.to_dict() for item in self.actions]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiff,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_DIFF_PREFIX,
    )


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStore"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store"
    )
]

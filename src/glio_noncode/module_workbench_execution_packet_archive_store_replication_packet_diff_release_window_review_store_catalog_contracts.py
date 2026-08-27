"""Typed contracts for durable review-store catalogs and federation.

The durable review store closes one release-window ledger.  A catalog is the
next boundary: it indexes multiple independently addressed stores without
turning their decisions into a new approval authority.  Federation then
selects and reconciles a bounded release collection using explicit policy
checks.  Every public value is deterministic, path-free, timestamp-free, and
identity-free.
"""

from __future__ import annotations

# ruff: noqa: E501
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-entry"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-operation"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_CHECK_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-check"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERIFICATION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-verification"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_STAGE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-runtime-stage"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_QUERY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-query"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-federation"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_MEMBER_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-federation-member"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_CHECK_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-federation-check"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-diff"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_ACTION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-diff-action"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST = "review-store-catalog.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRIES = "review-store-catalog-entries.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATIONS = "review-store-catalog-operations.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS = 1024
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS = 256
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_TEXT = 4096

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


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState(
    StrEnum
):
    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    DIVERGED = "diverged"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind(
    StrEnum
):
    GENESIS = "genesis"
    REGISTER = "register"
    VERIFY = "verify"
    FEDERATE = "federate"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationState(
    StrEnum
):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckPlane(
    StrEnum
):
    FORMAT = "format"
    ENTRIES = "entries"
    OPERATIONS = "operations"
    STORAGE = "storage"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState(
    StrEnum
):
    PASSED = "passed"
    FAILED = "failed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind(
    StrEnum
):
    LOAD = "load"
    VERIFY_CATALOG = "verify_catalog"
    VERIFY_ENTRIES = "verify_entries"
    VERIFY_OPERATIONS = "verify_operations"
    RECONCILE_WINDOWS = "reconcile_windows"
    RESOLVE_RELEASE_SET = "resolve_release_set"
    EVALUATE_READINESS = "evaluate_readiness"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState(
    StrEnum
):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState(
    StrEnum
):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    DIVERGED = "diverged"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState(
    StrEnum
):
    EMPTY = "empty"
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    MIXED = "mixed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMemberDisposition(
    StrEnum
):
    INCLUDED = "included"
    HELD = "held"
    EXCLUDED = "excluded"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind(
    StrEnum
):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffState(
    StrEnum
):
    EXACT = "exact"
    APPEND_ONLY = "append_only"
    DIVERGENT = "divergent"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry:
    """One addressed member store in a catalog."""

    def __init__(
        self,
        ordinal: int,
        store_id: str,
        store_address: str,
        window_address: str,
        ledger_address: str,
        head_address: str | None,
        entry_count: int,
        operation_count: int,
        store_state: str,
        release_ready: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.store_id = store_id
        self.store_address = store_address
        self.window_address = window_address
        self.ledger_address = ledger_address
        self.head_address = head_address
        self.entry_count = entry_count
        self.operation_count = operation_count
        self.store_state = store_state
        self.release_ready = release_ready
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "catalog entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
            - 1,
        )
        _text(self.store_id, "catalog entry store ID", 256)
        _address(self.store_address, "catalog entry store address")
        _address(self.window_address, "catalog entry window address")
        _address(self.ledger_address, "catalog entry ledger address")
        _optional_address(self.head_address, "catalog entry head address")
        _count(self.entry_count, "catalog entry ledger count", 256)
        _count(self.operation_count, "catalog entry operation count", 512)
        _enum(
            self.store_state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState,
            "catalog entry store state",
        )
        _bool(self.release_ready, "catalog entry release-ready flag")
        _bool(self.accepted, "catalog entry accepted flag")
        _address(self.content_address, "catalog entry content address")
        if (
            self.release_ready
            and self.store_state
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.READY.value
        ):
            raise ValidationError("release-ready catalog entries must be ready")
        if (
            self.store_state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.READY.value
            and not self.accepted
        ):
            raise ValidationError("ready catalog entries must be accepted")
        if not _public(self.to_dict()):
            raise ValidationError("catalog entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "store_id": self.store_id,
            "store_address": self.store_address,
            "window_address": self.window_address,
            "ledger_address": self.ledger_address,
            "head_address": self.head_address,
            "entry_count": self.entry_count,
            "operation_count": self.operation_count,
            "store_state": self.store_state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ENTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation:
    """One append-only catalog journal operation."""

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
            "catalog operation ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS
            - 1,
        )
        _text(self.operation_id, "catalog operation ID", 256)
        kind = _enum(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind,
            "catalog operation kind",
        )
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationState,
            "catalog operation state",
        )
        _optional_address(self.input_address, "catalog operation input address")
        _optional_address(self.output_address, "catalog operation output address")
        _optional_address(self.previous_operation_address, "catalog operation predecessor")
        _bool(self.accepted, "catalog operation accepted flag")
        _text(self.detail, "catalog operation detail")
        _address(self.content_address, "catalog operation content address")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationState.REJECTED.value
            and self.accepted
        ):
            raise ValidationError("rejected catalog operations cannot be accepted")
        if (
            kind
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind.GENESIS.value
            and self.ordinal != 0
        ):
            raise ValidationError("catalog genesis operation must be first")
        if self.ordinal == 0 and self.previous_operation_address is not None:
            raise ValidationError("first catalog operation cannot have a predecessor")
        if self.ordinal > 0 and self.previous_operation_address is None:
            raise ValidationError("non-first catalog operations require a predecessor")
        if not _public(self.to_dict()):
            raise ValidationError("catalog operation crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_operation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_OPERATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck:
    """One independent catalog check."""

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
            "catalog check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
            - 1,
        )
        _enum(
            self.plane,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckPlane,
            "catalog check plane",
        )
        _text(self.kind, "catalog check kind", 256)
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState,
            "catalog check state",
        )
        _bool(self.passed, "catalog check passed flag")
        _text(self.detail, "catalog check detail")
        _address(self.content_address, "catalog check content address")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState.PASSED.value
            and not self.passed
        ):
            raise ValidationError("passed catalog checks must be marked passed")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheckState.FAILED.value
            and self.passed
        ):
            raise ValidationError("failed catalog checks cannot be marked passed")
        if not _public(self.to_dict()):
            raise ValidationError("catalog check crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    """Durable addressed catalog of independently verified review stores."""

    def __init__(
        self,
        catalog_id: str,
        version: str,
        boundary: str,
        entry_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        append_only: bool,
        entries: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
            ...,
        ],
        operation_count: int,
        operations: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
            ...,
        ],
        check_count: int,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.catalog_id = catalog_id
        self.version = version
        self.boundary = boundary
        self.entry_count = entry_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.append_only = append_only
        self.entries = tuple(entries)
        self.operation_count = operation_count
        self.operations = tuple(operations)
        self.check_count = check_count
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.catalog_id, "catalog ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION
        ):
            raise ValidationError("catalog version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_BOUNDARY
        ):
            raise ValidationError("catalog boundary is invalid")
        _count(
            self.entry_count,
            "catalog entry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
        )
        _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState,
            "catalog state",
        )
        _bool(self.release_ready, "catalog release-ready flag")
        _bool(self.accepted, "catalog accepted flag")
        _bool(self.append_only, "catalog append-only flag")
        if not self.append_only:
            raise ValidationError("catalog must be append-only")
        if self.entry_count != len(self.entries):
            raise ValidationError("catalog entry count does not conserve")
        store_ids: set[str] = set()
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(
                entry,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
            ):
                raise ValidationError("catalog entries must be typed")
            if entry.ordinal != ordinal:
                raise ValidationError("catalog entry ordinals are not contiguous")
            if entry.store_id in store_ids:
                raise ValidationError("catalog store IDs must be unique")
            store_ids.add(entry.store_id)
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_entry(
                    entry
                )
                != entry.content_address
            ):
                raise ValidationError("catalog entry address mismatch")
        _count(
            self.operation_count,
            "catalog operation count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_OPERATIONS,
        )
        if self.operation_count != len(self.operations):
            raise ValidationError("catalog operation count does not conserve")
        for ordinal, operation in enumerate(self.operations):
            if not isinstance(
                operation,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
            ):
                raise ValidationError("catalog operations must be typed")
            if operation.ordinal != ordinal:
                raise ValidationError("catalog operation ordinals are not contiguous")
            expected_previous = self.operations[ordinal - 1].content_address if ordinal else None
            if operation.previous_operation_address != expected_previous:
                raise ValidationError("catalog operation chain is not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_operation(
                    operation
                )
                != operation.content_address
            ):
                raise ValidationError("catalog operation address mismatch")
        if self.entry_count == 0:
            if (
                self.operation_count != 1
                or self.operations[0].kind
                != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperationKind.GENESIS.value
            ):
                raise ValidationError("empty catalogs require exactly one genesis operation")
        elif self.operation_count != self.entry_count + 1:
            raise ValidationError("catalog operations must conserve genesis and registrations")
        _count(
            self.check_count,
            "catalog check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
        )
        if self.check_count != len(self.checks):
            raise ValidationError("catalog check count does not conserve")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(
                check,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
            ):
                raise ValidationError("catalog checks must be typed")
            if check.ordinal != ordinal:
                raise ValidationError("catalog check ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("catalog check address mismatch")
        expected_accepted = (
            bool(self.entries)
            and all(item.accepted for item in self.entries)
            and bool(self.operations)
            and all(item.accepted for item in self.operations)
            and bool(self.checks)
            and all(item.passed for item in self.checks)
        )
        if self.accepted != expected_accepted:
            raise ValidationError("catalog acceptance does not conserve")
        if (
            self.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.READY.value
            and not self.release_ready
        ):
            raise ValidationError("ready catalogs must be release-ready")
        if self.release_ready != bool(self.entries) and self.release_ready:
            raise ValidationError("empty catalogs cannot be release-ready")
        if self.release_ready and not all(item.release_ready for item in self.entries):
            raise ValidationError("catalog readiness must conserve member readiness")
        if self.release_ready and not self.accepted:
            raise ValidationError("release-ready catalogs must be accepted")
        _address(self.content_address, "catalog content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "version": self.version,
            "boundary": self.boundary,
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
        self,
        *,
        include_entries: bool = True,
        include_operations: bool = True,
        include_checks: bool = True,
    ) -> dict[str, Any]:
        body = self.summary()
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        if include_operations:
            body["operations"] = [item.to_dict() for item in self.operations]
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogVerification:
    """Independent verification receipt for a catalog."""

    def __init__(
        self,
        catalog_id: str,
        catalog_address: str,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
            ...,
        ],
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.catalog_id, "catalog verification ID", 256)
        _address(self.catalog_address, "catalog verification catalog address")
        _count(
            self.check_count,
            "catalog verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
        )
        if self.check_count != len(self.checks):
            raise ValidationError("catalog verification check count does not conserve")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("catalog verification passed count does not conserve")
        if self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("catalog verification failed count does not conserve")
        _count(self.passed_count, "catalog verification passed count", self.check_count)
        _count(self.failed_count, "catalog verification failed count", self.check_count)
        _bool(self.accepted, "catalog verification accepted flag")
        expected_accepted = bool(self.checks) and all(item.passed for item in self.checks)
        if self.accepted != expected_accepted:
            raise ValidationError("catalog verification acceptance does not conserve")
        _address(self.content_address, "catalog verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage:
    """One deterministic stage in catalog verification and readiness."""

    def __init__(
        self,
        ordinal: int,
        kind: str,
        state: str,
        input_address: str | None,
        output_address: str | None,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.state = state
        self.input_address = input_address
        self.output_address = output_address
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "catalog runtime stage ordinal", 7)
        _enum(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageKind,
            "catalog runtime stage kind",
        )
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState,
            "catalog runtime stage state",
        )
        _optional_address(self.input_address, "catalog runtime stage input address")
        _optional_address(self.output_address, "catalog runtime stage output address")
        _bool(self.accepted, "catalog runtime stage accepted flag")
        _text(self.detail, "catalog runtime stage detail")
        _address(self.content_address, "catalog runtime stage content address")
        if (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStageState.COMPLETED.value
            and not self.accepted
        ):
            raise ValidationError("completed catalog runtime stages must be accepted")
        if not _public(self.to_dict()):
            raise ValidationError("catalog runtime stage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_STAGE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime:
    """Eight-stage fail-closed runtime for a durable catalog."""

    def __init__(
        self,
        catalog_id: str,
        catalog_address: str,
        state: str,
        release_ready: bool,
        accepted: bool,
        stages: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage,
            ...,
        ],
        completed_count: int,
        blocked_count: int,
        skipped_count: int,
        content_address: str,
    ) -> None:
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.stages = tuple(stages)
        self.completed_count = completed_count
        self.blocked_count = blocked_count
        self.skipped_count = skipped_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.catalog_id, "catalog runtime catalog ID", 256)
        _address(self.catalog_address, "catalog runtime catalog address")
        state = _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState,
            "catalog runtime state",
        )
        _bool(self.release_ready, "catalog runtime release-ready flag")
        _bool(self.accepted, "catalog runtime accepted flag")
        if len(self.stages) != 8:
            raise ValidationError("catalog runtime requires eight stages")
        for ordinal, stage in enumerate(self.stages):
            if not isinstance(
                stage,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage,
            ):
                raise ValidationError("catalog runtime stages must be typed")
            if stage.ordinal != ordinal:
                raise ValidationError("catalog runtime stage ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_stage(
                    stage
                )
                != stage.content_address
            ):
                raise ValidationError("catalog runtime stage address mismatch")
        if self.completed_count != sum(item.state == "completed" for item in self.stages):
            raise ValidationError("catalog runtime completed count does not conserve")
        if self.blocked_count != sum(item.state == "blocked" for item in self.stages):
            raise ValidationError("catalog runtime blocked count does not conserve")
        if self.skipped_count != sum(item.state == "skipped" for item in self.stages):
            raise ValidationError("catalog runtime skipped count does not conserve")
        _count(self.completed_count, "catalog runtime completed count", 8)
        _count(self.blocked_count, "catalog runtime blocked count", 8)
        _count(self.skipped_count, "catalog runtime skipped count", 8)
        if self.state == "completed" and (
            self.completed_count != 8 or self.blocked_count or self.skipped_count
        ):
            raise ValidationError("completed catalog runtime must close all stages")
        if self.accepted != (
            state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeState.COMPLETED.value
        ):
            raise ValidationError("catalog runtime acceptance is invalid")
        if self.release_ready and not self.accepted:
            raise ValidationError("catalog runtime readiness requires acceptance")
        _address(self.content_address, "catalog runtime content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog runtime crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "stage_count": len(self.stages),
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "skipped_count": self.skipped_count,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_RUNTIME_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember:
    """One selected member in a release collection."""

    def __init__(
        self,
        ordinal: int,
        store_id: str,
        store_address: str,
        window_address: str,
        ledger_address: str,
        head_address: str | None,
        store_state: str,
        disposition: str,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.store_id = store_id
        self.store_address = store_address
        self.window_address = window_address
        self.ledger_address = ledger_address
        self.head_address = head_address
        self.store_state = store_state
        self.disposition = disposition
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "federation member ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
            - 1,
        )
        _text(self.store_id, "federation member store ID", 256)
        _address(self.store_address, "federation member store address")
        _address(self.window_address, "federation member window address")
        _address(self.ledger_address, "federation member ledger address")
        _optional_address(self.head_address, "federation member head address")
        _enum(
            self.store_state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState,
            "federation member store state",
        )
        _enum(
            self.disposition,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMemberDisposition,
            "federation member disposition",
        )
        _bool(self.accepted, "federation member accepted flag")
        _text(self.detail, "federation member detail")
        _address(self.content_address, "federation member content address")
        if self.disposition == "included" and not self.accepted:
            raise ValidationError("included federation members must be accepted")
        if not _public(self.to_dict()):
            raise ValidationError("federation member crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "store_id": self.store_id,
            "store_address": self.store_address,
            "window_address": self.window_address,
            "ledger_address": self.ledger_address,
            "head_address": self.head_address,
            "store_state": self.store_state,
            "disposition": self.disposition,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_member(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_MEMBER_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck:
    """One explicit policy check for a federation."""

    def __init__(
        self,
        ordinal: int,
        kind: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "federation check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "federation check kind", 256)
        _bool(self.passed, "federation check passed flag")
        _text(self.detail, "federation check detail")
        _address(self.content_address, "federation check content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation:
    """A policy-evaluated, bounded collection of catalog members."""

    def __init__(
        self,
        federation_id: str,
        catalog_id: str,
        catalog_address: str,
        selected_window_address: str | None,
        require_same_window: bool,
        require_unique_ledger: bool,
        minimum_members: int,
        minimum_ready: int,
        member_count: int,
        ready_count: int,
        held_count: int,
        blocked_count: int,
        distinct_window_count: int,
        distinct_ledger_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        members: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember,
            ...,
        ],
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.federation_id = federation_id
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.selected_window_address = selected_window_address
        self.require_same_window = require_same_window
        self.require_unique_ledger = require_unique_ledger
        self.minimum_members = minimum_members
        self.minimum_ready = minimum_ready
        self.member_count = member_count
        self.ready_count = ready_count
        self.held_count = held_count
        self.blocked_count = blocked_count
        self.distinct_window_count = distinct_window_count
        self.distinct_ledger_count = distinct_ledger_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.members = tuple(members)
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.federation_id, "federation ID", 256)
        _text(self.catalog_id, "federation catalog ID", 256)
        _address(self.catalog_address, "federation catalog address")
        _optional_address(self.selected_window_address, "selected federation window address")
        _bool(self.require_same_window, "federation same-window policy")
        _bool(self.require_unique_ledger, "federation unique-ledger policy")
        _count(
            self.minimum_members,
            "federation minimum members",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
        )
        _count(
            self.minimum_ready,
            "federation minimum ready",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
        )
        _count(
            self.member_count,
            "federation member count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
        )
        _count(self.ready_count, "federation ready count", self.member_count)
        _count(self.held_count, "federation held count", self.member_count)
        _count(self.blocked_count, "federation blocked count", self.member_count)
        _count(self.distinct_window_count, "federation distinct window count", self.member_count)
        _count(self.distinct_ledger_count, "federation distinct ledger count", self.member_count)
        _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState,
            "federation state",
        )
        _bool(self.release_ready, "federation release-ready flag")
        _bool(self.accepted, "federation accepted flag")
        if self.member_count != len(self.members):
            raise ValidationError("federation member count does not conserve")
        if self.ready_count + self.held_count + self.blocked_count != self.member_count:
            raise ValidationError("federation state counts do not conserve")
        if self.minimum_ready > self.minimum_members and self.minimum_members:
            raise ValidationError("federation minimum ready cannot exceed minimum members")
        member_ids: set[str] = set()
        for ordinal, member in enumerate(self.members):
            if not isinstance(
                member,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember,
            ):
                raise ValidationError("federation members must be typed")
            if member.ordinal != ordinal:
                raise ValidationError("federation member ordinals are not contiguous")
            if member.store_id in member_ids:
                raise ValidationError("federation member IDs must be unique")
            member_ids.add(member.store_id)
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_member(
                    member
                )
                != member.content_address
            ):
                raise ValidationError("federation member address mismatch")
        if (
            len(self.checks)
            > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
        ):
            raise ValidationError("federation checks exceed the published limit")
        for ordinal, check in enumerate(self.checks):
            if check.ordinal != ordinal:
                raise ValidationError("federation check ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("federation check address mismatch")
        expected_accepted = (
            bool(self.members)
            and bool(self.checks)
            and all(item.passed for item in self.checks if item.kind != "minimum-ready")
        )
        if self.accepted != expected_accepted:
            raise ValidationError("federation acceptance does not conserve")
        if self.release_ready and (not self.accepted or self.state != "ready"):
            raise ValidationError("release-ready federation state is invalid")
        _address(self.content_address, "federation content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_id": self.federation_id,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "selected_window_address": self.selected_window_address,
            "require_same_window": self.require_same_window,
            "require_unique_ledger": self.require_unique_ledger,
            "minimum_members": self.minimum_members,
            "minimum_ready": self.minimum_ready,
            "member_count": self.member_count,
            "ready_count": self.ready_count,
            "held_count": self.held_count,
            "blocked_count": self.blocked_count,
            "distinct_window_count": self.distinct_window_count,
            "distinct_ledger_count": self.distinct_ledger_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "check_count": len(self.checks),
            "content_address": self.content_address,
        }

    def to_dict(
        self, *, include_members: bool = True, include_checks: bool = True
    ) -> dict[str, Any]:
        body = self.summary()
        if include_members:
            body["members"] = [item.to_dict() for item in self.members]
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction:
    """One member action in a catalog revision comparison."""

    def __init__(
        self,
        ordinal: int,
        store_id: str,
        kind: str,
        left_address: str | None,
        right_address: str | None,
        left_state: str | None,
        right_state: str | None,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.store_id = store_id
        self.kind = kind
        self.left_address = left_address
        self.right_address = right_address
        self.left_state = left_state
        self.right_state = right_state
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "catalog diff action ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
            - 1,
        )
        _text(self.store_id, "catalog diff action store ID", 256)
        _enum(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffActionKind,
            "catalog diff action kind",
        )
        _optional_address(self.left_address, "catalog diff left address")
        _optional_address(self.right_address, "catalog diff right address")
        _optional_text(self.left_state, "catalog diff left state", 64)
        _optional_text(self.right_state, "catalog diff right state", 64)
        _bool(self.accepted, "catalog diff action accepted flag")
        _text(self.detail, "catalog diff action detail")
        _address(self.content_address, "catalog diff action content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog diff action crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "store_id": self.store_id,
            "kind": self.kind,
            "left_address": self.left_address,
            "right_address": self.right_address,
            "left_state": self.left_state,
            "right_state": self.right_state,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_action(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_ACTION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff:
    """Addressed exact, append-only, or divergent catalog comparison."""

    def __init__(
        self,
        diff_id: str,
        left_catalog_id: str,
        right_catalog_id: str,
        left_catalog_address: str,
        right_catalog_address: str,
        state: str,
        append_only: bool,
        accepted: bool,
        actions: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffAction,
            ...,
        ],
        added_count: int,
        removed_count: int,
        unchanged_count: int,
        changed_count: int,
        content_address: str,
    ) -> None:
        self.diff_id = diff_id
        self.left_catalog_id = left_catalog_id
        self.right_catalog_id = right_catalog_id
        self.left_catalog_address = left_catalog_address
        self.right_catalog_address = right_catalog_address
        self.state = state
        self.append_only = append_only
        self.accepted = accepted
        self.actions = tuple(actions)
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "catalog diff ID", 256)
        _text(self.left_catalog_id, "left catalog ID", 256)
        _text(self.right_catalog_id, "right catalog ID", 256)
        _address(self.left_catalog_address, "left catalog address")
        _address(self.right_catalog_address, "right catalog address")
        _enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiffState,
            "catalog diff state",
        )
        _bool(self.append_only, "catalog diff append-only flag")
        _bool(self.accepted, "catalog diff accepted flag")
        if (
            len(self.actions)
            > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES
            * 2
        ):
            raise ValidationError("catalog diff actions exceed the published limit")
        counts = {"added": 0, "removed": 0, "unchanged": 0, "changed": 0}
        for ordinal, action in enumerate(self.actions):
            if action.ordinal != ordinal:
                raise ValidationError("catalog diff action ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_action(
                    action
                )
                != action.content_address
            ):
                raise ValidationError("catalog diff action address mismatch")
            counts[action.kind] += 1
        if (self.added_count, self.removed_count, self.unchanged_count, self.changed_count) != (
            counts["added"],
            counts["removed"],
            counts["unchanged"],
            counts["changed"],
        ):
            raise ValidationError("catalog diff counts do not conserve")
        _count(self.added_count, "catalog diff added count", len(self.actions))
        _count(self.removed_count, "catalog diff removed count", len(self.actions))
        _count(self.unchanged_count, "catalog diff unchanged count", len(self.actions))
        _count(self.changed_count, "catalog diff changed count", len(self.actions))
        expected_append_only = self.removed_count == 0 and self.changed_count == 0
        if self.append_only != expected_append_only:
            raise ValidationError("catalog diff append-only state does not conserve")
        if self.accepted != all(action.accepted for action in self.actions) and self.actions:
            raise ValidationError("catalog diff acceptance does not conserve")
        _address(self.content_address, "catalog diff content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "left_catalog_id": self.left_catalog_id,
            "right_catalog_id": self.right_catalog_id,
            "left_catalog_address": self.left_catalog_address,
            "right_catalog_address": self.right_catalog_address,
            "state": self.state,
            "append_only": self.append_only,
            "accepted": self.accepted,
            "action_count": len(self.actions),
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_actions: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_actions:
            body["actions"] = [item.to_dict() for item in self.actions]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogDiff,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DIFF_PREFIX,
    )

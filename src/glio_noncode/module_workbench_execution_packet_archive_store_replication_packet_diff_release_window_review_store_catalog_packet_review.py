"""Record append-only review decisions over catalog packet transitions."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ENTRY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
    + "-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DOCUMENT = "review.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_ENTRIES = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_CHECKS = 16


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind(
    StrEnum
):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"
    SUPERSEDE = "supersede"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheckState(
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ENTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry:
    """One append-only, evidence-linked decision over a packet transition."""

    def __init__(
        self,
        ordinal: int,
        decision_id: str,
        decision: str,
        diff_address: str,
        left_packet_address: str,
        right_packet_address: str,
        right_state: str,
        right_release_ready: bool,
        diff_accepted: bool,
        diff_release_ready: bool,
        action_required: bool,
        previous_entry_address: str | None,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.decision_id = decision_id
        self.decision = decision
        self.diff_address = diff_address
        self.left_packet_address = left_packet_address
        self.right_packet_address = right_packet_address
        self.right_state = right_state
        self.right_release_ready = right_release_ready
        self.diff_accepted = diff_accepted
        self.diff_release_ready = diff_release_ready
        self.action_required = action_required
        self.previous_entry_address = previous_entry_address
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "packet review entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_ENTRIES
            - 1,
        )
        _text(self.decision_id, "packet review decision ID", 256)
        if self.decision not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind
        }:
            raise ValidationError("packet review decision kind is invalid")
        for value, field in (
            (self.diff_address, "packet review diff address"),
            (self.left_packet_address, "packet review left packet address"),
            (self.right_packet_address, "packet review right packet address"),
        ):
            _address(value, field)
        if self.right_state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewState
        }:
            raise ValidationError("packet review right state is invalid")
        _bool(self.right_release_ready, "packet review right release-ready flag")
        _bool(self.diff_accepted, "packet review diff accepted flag")
        _bool(self.diff_release_ready, "packet review diff release-ready flag")
        _bool(self.action_required, "packet review action-required flag")
        if self.action_required != (self.decision != "promote"):
            raise ValidationError("packet review action requirement does not conserve")
        if self.decision == "promote" and (
            not self.diff_accepted
            or not self.diff_release_ready
            or self.right_state != "ready"
            or not self.right_release_ready
        ):
            raise ValidationError("promote decisions require release-ready evidence")
        if self.decision == "hold" and (
            not self.diff_accepted or self.diff_release_ready or self.right_state == "blocked"
        ):
            raise ValidationError("hold decisions require accepted non-ready evidence")
        if (
            self.decision == "block"
            and self.diff_accepted
            and self.diff_release_ready
            and self.right_state == "ready"
        ):
            raise ValidationError(
                "ready accepted evidence cannot be blocked without a changed release state"
            )
        _address(self.previous_entry_address, "packet review predecessor address", optional=True)
        _bool(self.accepted, "packet review entry accepted flag")
        _text(self.detail, "packet review decision detail")
        _address(self.content_address, "packet review entry content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet review entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "decision_id": self.decision_id,
            "decision": self.decision,
            "diff_address": self.diff_address,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "right_state": self.right_state,
            "right_release_ready": self.right_release_ready,
            "diff_accepted": self.diff_accepted,
            "diff_release_ready": self.diff_release_ready,
            "action_required": self.action_required,
            "previous_entry_address": self.previous_entry_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck:
    """One addressed review-ledger verification check."""

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
            "packet review check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "packet review check kind", 256)
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheckState
        }:
            raise ValidationError("packet review check state is invalid")
        _bool(self.passed, "packet review check passed flag")
        if self.state != ("passed" if self.passed else "failed"):
            raise ValidationError("packet review check state does not conserve")
        _text(self.detail, "packet review check detail")
        _address(self.content_address, "packet review check content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet review check crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewVerification:
    """Addressed receipt proving review ledger and chain invariants."""

    def __init__(
        self,
        review_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.review_address = review_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.review_address, "packet review verification review address")
        _count(
            self.check_count,
            "packet review verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError(
                "packet review verification checks must be non-empty and conserved"
            )
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("packet review verification check address mismatch")
        if self.passed_count != sum(
            item.passed for item in self.checks
        ) or self.failed_count != sum(not item.passed for item in self.checks):
            raise ValidationError("packet review verification counts do not conserve")
        _count(self.passed_count, "packet review verification passed count", self.check_count)
        _count(self.failed_count, "packet review verification failed count", self.check_count)
        _bool(self.accepted, "packet review verification accepted flag")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("packet review verification acceptance does not conserve")
        _address(self.content_address, "packet review verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet review verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "review_address": self.review_address,
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview:
    """Durable append-only packet review decision ledger."""

    def __init__(
        self,
        review_id: str,
        version: str,
        boundary: str,
        entry_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        head_address: str,
        entries: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.review_id = review_id
        self.version = version
        self.boundary = boundary
        self.entry_count = entry_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.head_address = head_address
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.review_id, "packet review ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION
        ):
            raise ValidationError("packet review version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_BOUNDARY
        ):
            raise ValidationError("packet review boundary is invalid")
        _count(
            self.entry_count,
            "packet review entry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_ENTRIES,
        )
        if self.entry_count != len(self.entries) or self.entry_count == 0:
            raise ValidationError("packet review entries must be non-empty and conserved")
        for ordinal, entry in enumerate(self.entries):
            if (
                entry.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_entry(
                    entry
                )
                != entry.content_address
            ):
                raise ValidationError("packet review entry address mismatch")
            expected_previous = self.entries[ordinal - 1].content_address if ordinal else None
            if entry.previous_entry_address != expected_previous:
                raise ValidationError("packet review entry chain is not contiguous")
        if self.head_address != self.entries[-1].content_address:
            raise ValidationError("packet review head does not match the last entry")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewState
        }:
            raise ValidationError("packet review state is invalid")
        expected_state = {
            "promote": "ready",
            "hold": "held",
            "block": "blocked",
            "supersede": "held",
        }[self.entries[-1].decision]
        if self.state != expected_state:
            raise ValidationError("packet review state does not follow the head decision")
        _bool(self.release_ready, "packet review release-ready flag")
        _bool(self.accepted, "packet review accepted flag")
        if self.release_ready != (self.state == "ready") or not self.accepted:
            raise ValidationError("packet review readiness or acceptance does not conserve")
        _address(self.head_address, "packet review head address")
        _address(self.content_address, "packet review content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet review crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "version": self.version,
            "boundary": self.boundary,
            "entry_count": self.entry_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "head_address": self.head_address,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def _entry(
    ordinal: int,
    decision_id: str,
    decision: str,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    previous_entry_address: str | None,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry:
    if decision not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind
    }:
        raise ValidationError("packet review decision kind is invalid")
    body = {
        "ordinal": ordinal,
        "decision_id": _text(decision_id, "packet review decision ID", 256),
        "decision": decision,
        "diff_address": diff.content_address,
        "left_packet_address": diff.left_packet_address,
        "right_packet_address": diff.right_packet_address,
        "right_state": diff.right_state,
        "right_release_ready": diff.release_ready,
        "diff_accepted": diff.accepted,
        "diff_release_ready": diff.release_ready,
        "action_required": decision != "promote",
        "previous_entry_address": previous_entry_address,
        "accepted": True,
        "detail": _text(detail, "packet review decision detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry(
        **body, content_address="pending:entry"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_entry(
            provisional
        ),
    )


def _default_decision(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
) -> str:
    if not diff.accepted or diff.right_state == "blocked":
        return "block"
    if diff.release_ready:
        return "promote"
    return "hold"


def _review_state(
    entry: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry,
) -> str:
    return {"promote": "ready", "hold": "held", "block": "blocked", "supersede": "held"}[
        entry.decision
    ]


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    *,
    review_id: str = "glio-noncode-review-store-catalog-packet-review",
    decision: str | None = None,
    decision_id: str = "glio-noncode-review-store-catalog-packet-decision-0",
    detail: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        diff
    )
    selected = decision or _default_decision(diff)
    if selected not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind
    }:
        raise ValidationError("packet review decision kind is invalid")
    detail = (
        detail
        or {
            "promote": "verified packet transition is release-ready",
            "hold": "packet transition is accepted but not release-ready",
            "block": "packet transition failed structural or acceptance requirements",
            "supersede": "packet transition supersedes an earlier review decision",
        }[selected]
    )
    entry = _entry(0, decision_id, selected, diff, None, detail)
    body = {
        "review_id": _text(review_id, "packet review ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_BOUNDARY,
        "entry_count": 1,
        "state": _review_state(entry),
        "release_ready": entry.decision == "promote",
        "accepted": True,
        "head_address": entry.content_address,
        "entries": (entry,),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview(
        **body, content_address="pending:review"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            provisional
        ),
    )


def append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_decision(
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    *,
    decision: str | None = None,
    decision_id: str | None = None,
    detail: str | None = None,
    expected_head_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        review
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
        diff
    )
    if expected_head_address is not None and expected_head_address != review.head_address:
        raise ValidationError("packet review expected head does not match")
    if diff.left_packet_address != review.entries[-1].right_packet_address:
        raise ValidationError("packet review diff does not continue the current head packet")
    selected = decision or _default_decision(diff)
    if selected not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind
    }:
        raise ValidationError("packet review decision kind is invalid")
    detail = (
        detail
        or {
            "promote": "verified packet transition is release-ready",
            "hold": "packet transition is accepted but not release-ready",
            "block": "packet transition failed structural or acceptance requirements",
            "supersede": "packet transition supersedes the prior review decision",
        }[selected]
    )
    entry = _entry(
        review.entry_count,
        decision_id or f"{review.review_id}-decision-{review.entry_count}",
        selected,
        diff,
        review.head_address,
        detail,
    )
    entries = review.entries + (entry,)
    body = {
        "review_id": review.review_id,
        "version": review.version,
        "boundary": review.boundary,
        "entry_count": len(entries),
        "state": _review_state(entry),
        "release_ready": entry.decision == "promote",
        "accepted": True,
        "head_address": entry.content_address,
        "entries": entries,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview(
        **body, content_address="pending:review"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories(
    left_directory: str | Path, right_directory: str | Path, **kwargs: Any
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories,
    )

    diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
        left_directory,
        right_directory,
        diff_id=kwargs.pop("diff_id", "glio-noncode-review-store-catalog-packet-diff"),
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        diff, **kwargs
    )


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "state": "passed" if passed else "failed",
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_check(
            provisional
        ),
    )


def _checks(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff
    | None = None,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewCheck,
    ...,
]:
    checks = [
        _check(
            0,
            "review-address",
            bool(value.content_address),
            "addressed review",
            value.content_address,
            "review aggregate is addressed",
        ),
        _check(
            1,
            "entry-conservation",
            value.entry_count == len(value.entries)
            and 0
            < value.entry_count
            <= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_ENTRIES,
            value.entry_count,
            len(value.entries),
            "review entry count is conserved",
        ),
        _check(
            2,
            "chain-continuity",
            all(
                (
                    entry.previous_entry_address
                    == (value.entries[index - 1].content_address if index else None)
                )
                for index, entry in enumerate(value.entries)
            ),
            "contiguous predecessor addresses",
            tuple(entry.previous_entry_address for entry in value.entries),
            "review decisions form an append-only chain",
        ),
        _check(
            3,
            "head-conservation",
            value.head_address == value.entries[-1].content_address,
            value.entries[-1].content_address,
            value.head_address,
            "review head matches the last decision",
        ),
        _check(
            4,
            "state-classification",
            value.state == _review_state(value.entries[-1]),
            _review_state(value.entries[-1]),
            value.state,
            "review state follows the head decision",
        ),
        _check(
            5,
            "readiness-classification",
            value.release_ready == (value.state == "ready"),
            value.state == "ready",
            value.release_ready,
            "review readiness follows promotion",
        ),
        _check(
            6,
            "public-boundary",
            _public(value.to_dict()),
            True,
            True,
            "review projection contains deterministic public fields",
        ),
    ]
    if diff is not None:
        head = value.entries[-1]
        checks.append(
            _check(
                7,
                "diff-link",
                head.diff_address == diff.content_address
                and head.left_packet_address == diff.left_packet_address
                and head.right_packet_address == diff.right_packet_address,
                diff.content_address,
                head.diff_address,
                "review head retains the compared diff",
            )
        )
    return tuple(checks)


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    *,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff
    | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    ):
        raise ValidationError("packet review verification requires a typed review")
    if diff is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff
        )
    checks = list(_checks(value, diff))
    checks.insert(
        0,
        _check(
            0,
            "aggregate-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                value
            )
            == value.content_address,
            "recomputed review address",
            value.content_address,
            "review aggregate address is conserved",
        ),
    )
    checks = tuple(
        _check(index, item.kind, item.passed, item.expected, item.observed, item.detail)
        for index, item in enumerate(checks)
    )
    body = {
        "review_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_verification(
            provisional
        ),
    )


def _entry_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewEntry(
        **dict(value)
    )


def _review_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview:
    body = dict(value)
    body["entries"] = tuple(_entry_from_dict(item) for item in body.get("entries", ()))
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview(
        **body
    )


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        value
    )
    if not verification.accepted:
        raise ValidationError("cannot persist an unverified packet review")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("packet review destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        document = canonical_bytes(value.to_dict())
        manifest_body = {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION,
            "review": value.to_dict(),
            "byte_count": len(document),
            "byte_address": hash_bytes(
                document,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
                + "-bytes",
            ),
        }
        manifest = manifest_body | {
            "manifest_address": content_hash(
                manifest_body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
                + "-manifest",
            )
        }
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DOCUMENT
        ).write_bytes(document)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MANIFEST
        ).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("packet review destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise ValidationError(f"{field} must be canonical JSON object")
    return value


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("packet review directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DOCUMENT,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("packet review files do not match the published set")
    manifest = _read_json(
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MANIFEST,
        "packet review manifest",
    )
    expected_manifest_keys = {
        "manifest_version",
        "review",
        "byte_count",
        "byte_address",
        "manifest_address",
    }
    if (
        set(manifest) != expected_manifest_keys
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION
    ):
        raise ValidationError("packet review manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest.get("manifest_address") != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
        + "-manifest",
    ):
        raise ValidationError("packet review manifest address mismatch")
    document_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DOCUMENT
    )
    document = document_path.read_bytes()
    if (
        len(document) != manifest["byte_count"]
        or hash_bytes(
            document,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_PREFIX
            + "-bytes",
        )
        != manifest["byte_address"]
    ):
        raise ValidationError("packet review document bytes do not match the manifest")
    review_document = _read_json(document_path, "packet review document")
    if review_document != manifest["review"]:
        raise ValidationError("packet review manifest document diverges")
    review = _review_from_dict(review_document)
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        review
    ).accepted:
        raise ValidationError("packet review verification failed")
    return review


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "decision_id",
            "decision",
            "diff_address",
            "left_packet_address",
            "right_packet_address",
            "right_state",
            "right_release_ready",
            "diff_accepted",
            "diff_release_ready",
            "action_required",
            "previous_entry_address",
            "accepted",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        value
    )
    lines = [
        "# Review-Store Catalog Packet Review",
        "",
        f"- state: `{value.state}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- entries: `{value.entry_count}`",
        f"- head: `{value.head_address}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Decision | Right state | Action required | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.decision}` | `{item.right_state}` | `{str(item.action_required).lower()}` | {item.detail} |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    *,
    resource: str = "entries",
    decision: str | None = None,
    action_required: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        value
    )
    if resource not in {"summary", "entries"}:
        raise ValidationError("packet review query resource is invalid")
    if decision is not None and decision not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind
    }:
        raise ValidationError("packet review query decision is invalid")
    if action_required is not None and not isinstance(action_required, bool):
        raise ValidationError("packet review query action-required filter is invalid")
    if text is not None:
        text = _text(text, "packet review query text")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("packet review query bounds are invalid")
    rows = (
        [value.summary()] if resource == "summary" else [item.to_dict() for item in value.entries]
    )
    if resource == "entries" and decision is not None:
        rows = [row for row in rows if row["decision"] == decision]
    if resource == "entries" and action_required is not None:
        rows = [row for row in rows if row["action_required"] == action_required]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {
            "resource": resource,
            "decision": decision,
            "action_required": action_required,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "review": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("packet review query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("packet review query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "decision_id",
            "decision",
            "diff_address",
            "left_packet_address",
            "right_packet_address",
            "right_state",
            "right_release_ready",
            "diff_accepted",
            "diff_release_ready",
            "action_required",
            "previous_entry_address",
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
            writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query(
        value
    )
    lines = [
        "# Review-Store Catalog Packet Review Query",
        "",
        f"- rows: `{value.get('total', 0)}`",
        f"- address: `{value.get('content_address', '')}`",
        "",
        "| # | Decision | State | Action required |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('decision', '')}` | `{row.get('right_state', '')}` | `{str(row.get('action_required', '')).lower()}` |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_BOUNDARY,
        "decisions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewDecisionKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewState
        ],
        "resources": ["summary", "entries"],
        "max_entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MAX_ENTRIES,
        "exact_files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_MANIFEST,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_DOCUMENT,
        ],
        "bounded": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_VERSION,
        "operations": [
            "build",
            "append",
            "verify",
            "write",
            "load",
            "query",
            "json",
            "csv",
            "markdown",
        ],
        "append_only": True,
        "expected_head_guard": True,
        "atomic_write": True,
        "canonical_json": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "entries"],
        "filters": ["decision", "action_required", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "entries"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }

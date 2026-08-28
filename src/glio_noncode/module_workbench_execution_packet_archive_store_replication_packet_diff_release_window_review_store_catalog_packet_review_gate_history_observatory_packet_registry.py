"""Deterministic registry for portable longitudinal observatory packets.

The registry is a public transport index for multiple closure packets.  It
does not merge their scientific claims or infer a winner.  It retains each
packet's addressed public summary, conserves state/readiness counts, and
provides an independent receipt that can detect reordered, duplicated,
tampered, or stale packet metadata.  Full packet hydration is used while
building a registry; persisted registry loads intentionally verify the
portable packet metadata boundary without requiring the original source
directories.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacket,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_observatory_directory,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet,
    packet_from_mapping,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_BOUNDARY = "public_registry_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_ENTRY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
    + "-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_REGISTRY = "registry.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PACKETS = "packets.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERIFICATION = "verification.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_PACKETS = 256
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_CHECKS = 32
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_QUERY_ITEMS = 256

_REGISTRY_FILES = {
    "registry": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_REGISTRY,
    "packets": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PACKETS,
    "verification": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERIFICATION,
}

Packet = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacket


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    EMPTY = "empty"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < (1 if positive else 0)
        or value > maximum
    ):
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _json_value(value: Any, field: str) -> Any:
    try:
        result = json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be canonical JSON data") from exc
    if not _public(result):
        raise ValidationError(f"{field} crosses the public boundary")
    return result


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


def _state(value: Any, field: str = "registry state") -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryState
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _file_address(kind: str, raw: bytes) -> str:
    return hash_bytes(
        raw,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
        + "-"
        + kind
        + "-bytes",
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryEntry,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_ENTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryEntry:
    """One addressed public packet summary in registry order."""

    def __init__(
        self,
        *,
        ordinal: int,
        packet_id: str,
        packet_address: str,
        verification_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        artifact_count: int,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.packet_id = packet_id
        self.packet_address = packet_address
        self.verification_address = verification_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.artifact_count = artifact_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "registry entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_PACKETS
            - 1,
        )
        _text(self.packet_id, "registry entry packet ID", 256)
        _address(self.packet_address, "registry entry packet address")
        _address(self.verification_address, "registry entry verification address")
        _state(self.state, "registry entry state")
        _bool(self.accepted, "registry entry accepted")
        _bool(self.release_ready, "registry entry release-ready")
        _count(self.artifact_count, "registry entry artifact count", 4, positive=True)
        _address(self.content_address, "registry entry content address")
        if self.release_ready and (self.state != "ready" or not self.accepted):
            raise ValidationError("registry entry readiness projection is invalid")
        if not _public(self.to_dict()):
            raise ValidationError("registry entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "packet_id": self.packet_id,
            "packet_address": self.packet_address,
            "verification_address": self.verification_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "artifact_count": self.artifact_count,
            "content_address": self.content_address,
        }


RegistryEntry = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryEntry


def _entry_from_packet(ordinal: int, value: Packet) -> RegistryEntry:
    body = {
        "ordinal": ordinal,
        "packet_id": value.packet_id,
        "packet_address": value.content_address,
        "verification_address": value.verification_address,
        "state": value.state,
        "accepted": value.accepted,
        "release_ready": value.release_ready,
        "artifact_count": value.artifact_count,
    }
    provisional = RegistryEntry(**body, content_address="pending:entry")
    return RegistryEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_entry(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryCheck:
    """Independent registry verification finding."""

    def __init__(
        self,
        *,
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
            "registry check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "registry check kind", 128)
        _bool(self.passed, "registry check passed")
        _json_value(self.expected, "registry check expected")
        _json_value(self.observed, "registry check observed")
        _text(self.detail, "registry check detail")
        _address(self.content_address, "registry check content address")
        if not _public(self.to_dict()):
            raise ValidationError("registry check crosses the public boundary")

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


RegistryCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryCheck


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> RegistryCheck:
    body = {
        "ordinal": ordinal,
        "kind": _text(kind, "registry check kind", 128),
        "passed": bool(passed),
        "expected": _json_value(expected, "registry check expected"),
        "observed": _json_value(observed, "registry check observed"),
        "detail": _text(detail, "registry check detail"),
    }
    provisional = RegistryCheck(**body, content_address="pending:check")
    return RegistryCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_check(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryVerification:
    """Addressed independent receipt for registry structure and conservation."""

    def __init__(
        self,
        *,
        registry_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: Sequence[RegistryCheck],
        content_address: str,
    ) -> None:
        self.registry_address = registry_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.registry_address, "registry verification registry address")
        _count(
            self.check_count,
            "registry verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_CHECKS,
            positive=True,
        )
        _count(self.passed_count, "registry verification passed count", self.check_count)
        _count(self.failed_count, "registry verification failed count", self.check_count)
        if (
            self.check_count != len(self.checks)
            or self.passed_count + self.failed_count != self.check_count
        ):
            raise ValidationError("registry verification counts are not conserved")
        _bool(self.accepted, "registry verification accepted")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, RegistryCheck) or check.ordinal != ordinal:
                raise ValidationError("registry verification checks are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("registry verification check address is invalid")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("registry verification acceptance is not conserved")
        _address(self.content_address, "registry verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("registry verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "registry_address": self.registry_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [item.to_dict() for item in self.checks]}


RegistryVerification = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryVerification


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistry,
) -> str:
    body = value.to_dict() | {"content_address": None}
    return content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistry:
    """Portable metadata index over unique observatory closure packets."""

    def __init__(
        self,
        *,
        registry_id: str,
        version: str,
        boundary: str,
        packet_count: int,
        ready_count: int,
        held_count: int,
        blocked_count: int,
        accepted_count: int,
        release_ready_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        entries: Sequence[RegistryEntry],
        content_address: str,
    ) -> None:
        self.registry_id = registry_id
        self.version = version
        self.boundary = boundary
        self.packet_count = packet_count
        self.ready_count = ready_count
        self.held_count = held_count
        self.blocked_count = blocked_count
        self.accepted_count = accepted_count
        self.release_ready_count = release_ready_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.registry_id, "registry ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION
        ):
            raise ValidationError("registry version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_BOUNDARY
        ):
            raise ValidationError("registry boundary is invalid")
        _count(
            self.packet_count,
            "registry packet count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_PACKETS,
        )
        for count, field in (
            (self.ready_count, "ready count"),
            (self.held_count, "held count"),
            (self.blocked_count, "blocked count"),
            (self.accepted_count, "accepted count"),
            (self.release_ready_count, "release-ready count"),
        ):
            _count(count, f"registry {field}", self.packet_count)
        if (
            self.packet_count != len(self.entries)
            or self.ready_count + self.held_count + self.blocked_count != self.packet_count
        ):
            raise ValidationError("registry state counts are not conserved")
        if (
            self.accepted_count > self.packet_count
            or self.release_ready_count > self.accepted_count
        ):
            raise ValidationError("registry acceptance counts are not conserved")
        _state(self.state)
        _bool(self.accepted, "registry accepted")
        _bool(self.release_ready, "registry release-ready")
        if self.release_ready != (
            self.packet_count > 0
            and self.ready_count == self.packet_count
            and self.release_ready_count == self.packet_count
        ):
            raise ValidationError("registry release projection is invalid")
        expected_state = (
            "empty"
            if self.packet_count == 0
            else "blocked"
            if self.blocked_count or self.accepted_count < self.packet_count
            else "ready"
            if self.release_ready
            else "held"
        )
        if self.state != expected_state:
            raise ValidationError("registry state projection is invalid")
        if not self.accepted:
            raise ValidationError("registry metadata must be structurally accepted")
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(entry, RegistryEntry) or entry.ordinal != ordinal:
                raise ValidationError("registry entries are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_entry(
                    entry
                )
                != entry.content_address
            ):
                raise ValidationError("registry entry address is invalid")
        if (
            len({entry.packet_id for entry in self.entries}) != self.packet_count
            or len({entry.packet_address for entry in self.entries}) != self.packet_count
        ):
            raise ValidationError("registry packet identities are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("registry crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "version": self.version,
            "boundary": self.boundary,
            "packet_count": self.packet_count,
            "ready_count": self.ready_count,
            "held_count": self.held_count,
            "blocked_count": self.blocked_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"entries": [item.to_dict() for item in self.entries]}


Registry = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistry


def _registry_metadata(
    registry_id: str, entries: Sequence[RegistryEntry], *, content_address: str
) -> Registry:
    ready_count = sum(item.state == "ready" for item in entries)
    held_count = sum(item.state == "held" for item in entries)
    blocked_count = sum(item.state == "blocked" for item in entries)
    accepted_count = sum(item.accepted for item in entries)
    release_ready_count = sum(item.release_ready for item in entries)
    packet_count = len(entries)
    release_ready = (
        packet_count > 0 and ready_count == packet_count and release_ready_count == packet_count
    )
    state = (
        "empty"
        if packet_count == 0
        else "blocked"
        if blocked_count or accepted_count < packet_count
        else "ready"
        if release_ready
        else "held"
    )
    return Registry(
        registry_id=_text(registry_id, "registry ID", 256),
        version=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION,
        boundary=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_BOUNDARY,
        packet_count=packet_count,
        ready_count=ready_count,
        held_count=held_count,
        blocked_count=blocked_count,
        accepted_count=accepted_count,
        release_ready_count=release_ready_count,
        state=state,
        accepted=True,
        release_ready=release_ready,
        entries=entries,
        content_address=content_address,
    )


def _registry_verification(
    registry: Registry, packets: Sequence[Packet] | None
) -> RegistryVerification:
    checks: list[RegistryCheck] = []

    def add(kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> None:
        checks.append(_check(len(checks), kind, passed, expected, observed, detail))

    packet_values = tuple(packets or ())
    packet_map = {item.packet_id: item for item in packet_values if isinstance(item, Packet)}
    add(
        "registry-address",
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            registry
        )
        == registry.content_address,
        "recomputed registry address",
        registry.content_address,
        "registry metadata address is conserved",
    )
    add(
        "entry-count",
        registry.packet_count == len(registry.entries),
        registry.packet_count,
        len(registry.entries),
        "registry packet and entry counts agree",
    )
    add(
        "entry-order",
        tuple(item.ordinal for item in registry.entries) == tuple(range(registry.packet_count)),
        list(range(registry.packet_count)),
        [item.ordinal for item in registry.entries],
        "entry ordinals are contiguous",
    )
    add(
        "packet-id-uniqueness",
        len({item.packet_id for item in registry.entries}) == registry.packet_count,
        registry.packet_count,
        len({item.packet_id for item in registry.entries}),
        "packet IDs are unique",
    )
    add(
        "packet-address-uniqueness",
        len({item.packet_address for item in registry.entries}) == registry.packet_count,
        registry.packet_count,
        len({item.packet_address for item in registry.entries}),
        "packet addresses are unique",
    )
    add(
        "state-conservation",
        registry.ready_count + registry.held_count + registry.blocked_count
        == registry.packet_count,
        registry.packet_count,
        registry.ready_count + registry.held_count + registry.blocked_count,
        "ready, held, and blocked counts are conserved",
    )
    add(
        "acceptance-conservation",
        registry.accepted_count == sum(item.accepted for item in registry.entries),
        registry.accepted_count,
        sum(item.accepted for item in registry.entries),
        "accepted packet count is conserved",
    )
    add(
        "readiness-conservation",
        registry.release_ready_count == sum(item.release_ready for item in registry.entries),
        registry.release_ready_count,
        sum(item.release_ready for item in registry.entries),
        "release-ready packet count is conserved",
    )
    add(
        "state-projection",
        registry.state
        == (
            "empty"
            if not registry.entries
            else "blocked"
            if registry.blocked_count or registry.accepted_count < registry.packet_count
            else "ready"
            if registry.release_ready
            else "held"
        ),
        registry.state,
        registry.state,
        "registry state matches conserved counts",
    )
    add(
        "release-projection",
        registry.release_ready
        == (
            registry.packet_count > 0
            and registry.ready_count == registry.packet_count
            and registry.release_ready_count == registry.packet_count
        ),
        True if registry.release_ready else False,
        registry.release_ready,
        "registry readiness matches all-ready closure",
    )
    entry_addresses = tuple(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_entry(
            item
        )
        == item.content_address
        for item in registry.entries
    )
    add(
        "entry-addresses",
        all(entry_addresses),
        True,
        all(entry_addresses),
        "entry content addresses are conserved",
    )
    packet_links = tuple(
        item.packet_id in packet_map
        and packet_map[item.packet_id].content_address == item.packet_address
        and address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            packet_map[item.packet_id]
        )
        == item.packet_address
        for item in registry.entries
    )
    add(
        "packet-links",
        (not packet_values and not registry.entries) or all(packet_links),
        True,
        all(packet_links) if packet_links else not registry.entries,
        "hydrated packet metadata links are conserved",
    )
    public = _public(registry.to_dict()) and all(_public(item.to_dict()) for item in packet_values)
    add("public-boundary", public, True, public, "registry and packet summaries remain public")
    body = {
        "registry_address": registry.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = RegistryVerification(**body, content_address="pending:verification")
    return RegistryVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_verification(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
    packets: Sequence[Packet],
    *,
    registry_id: str = "glio-noncode-observatory-packet-registry",
) -> Registry:
    """Build a canonical registry from fully verified typed packets."""

    if not isinstance(packets, Sequence) or isinstance(packets, (str, bytes)):
        raise ValidationError("registry packets must be a bounded sequence")
    if (
        len(packets)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_PACKETS
    ):
        raise ValidationError("registry packet count exceeds the bounded maximum")
    typed: list[Packet] = []
    for value in packets:
        if not isinstance(value, Packet):
            raise ValidationError("registry requires typed closure packets")
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            value
        )
        if not verification.accepted:
            raise ValidationError("registry requires accepted closure packets")
        typed.append(value)
    typed.sort(key=lambda item: (item.packet_id, item.content_address))
    if len({item.packet_id for item in typed}) != len(typed) or len(
        {item.content_address for item in typed}
    ) != len(typed):
        raise ValidationError("registry packet IDs and addresses must be unique")
    entries = tuple(_entry_from_packet(index, value) for index, value in enumerate(typed))
    provisional = _registry_metadata(registry_id, entries, content_address="pending:registry")
    registry = _registry_metadata(
        registry_id,
        entries,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            provisional
        ),
    )
    registry.packets = tuple(typed)
    verification = _registry_verification(registry, typed)
    registry.verification = verification
    if not verification.accepted:
        raise ValidationError("registry verification failed")
    return registry


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_from_directories(
    directories: Sequence[str | Path],
    *,
    registry_id: str = "glio-noncode-observatory-packet-registry",
) -> Registry:
    if not isinstance(directories, Sequence) or isinstance(directories, (str, bytes)):
        raise ValidationError("registry directories must be a bounded sequence")
    packets = tuple(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            item
        )
        for item in directories
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
        packets, registry_id=registry_id
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_from_observatory_directories(
    directories: Sequence[str | Path],
    *,
    registry_id: str = "glio-noncode-observatory-packet-registry",
    runtime_directory: str | Path | None = None,
) -> Registry:
    packets = tuple(
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_observatory_directory(
            item, runtime_directory=runtime_directory, packet_id=f"packet-{index}"
        )
        for index, item in enumerate(directories)
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
        packets, registry_id=registry_id
    )


def registry_entry_from_mapping(value: Mapping[str, Any]) -> RegistryEntry:
    if not isinstance(value, Mapping):
        raise ValidationError("registry entry mapping must be an object")
    try:
        return RegistryEntry(**dict(value))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("registry entry mapping is invalid") from exc


def registry_check_from_mapping(value: Mapping[str, Any]) -> RegistryCheck:
    if not isinstance(value, Mapping):
        raise ValidationError("registry check mapping must be an object")
    try:
        return RegistryCheck(**dict(value))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("registry check mapping is invalid") from exc


def registry_verification_from_mapping(value: Mapping[str, Any]) -> RegistryVerification:
    if not isinstance(value, Mapping):
        raise ValidationError("registry verification mapping must be an object")
    body = dict(value)
    try:
        checks = tuple(registry_check_from_mapping(item) for item in body.pop("checks"))
        return RegistryVerification(**(body | {"checks": checks}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("registry verification mapping is invalid") from exc


def registry_from_mapping(value: Mapping[str, Any]) -> Registry:
    if not isinstance(value, Mapping):
        raise ValidationError("registry mapping must be an object")
    body = dict(value)
    try:
        entries = tuple(registry_entry_from_mapping(item) for item in body.pop("entries"))
        return Registry(**(body | {"entries": entries}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("registry mapping is invalid") from exc


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
    value: Registry,
) -> RegistryVerification:
    if not isinstance(value, Registry):
        raise ValidationError("registry verification requires a typed registry")
    packets = getattr(value, "packets", None)
    return _registry_verification(value, packets if isinstance(packets, Sequence) else None)


def _require_hydrated(value: Registry) -> tuple[tuple[Packet, ...], RegistryVerification]:
    packets = getattr(value, "packets", None)
    verification = getattr(value, "verification", None)
    if not isinstance(packets, tuple) or not all(isinstance(item, Packet) for item in packets):
        raise ValidationError("registry packets are not hydrated")
    if not isinstance(verification, RegistryVerification):
        raise ValidationError("registry verification is not hydrated")
    return packets, verification


def _require_verified(value: Registry) -> tuple[tuple[Packet, ...], RegistryVerification]:
    packets, embedded = _require_hydrated(value)
    computed = _registry_verification(value, packets)
    if not computed.accepted or computed.to_dict() != embedded.to_dict():
        raise ValidationError("registry verification failed or is stale")
    return packets, embedded


def _payloads(value: Registry) -> dict[str, bytes]:
    packets, verification = _require_verified(value)
    return {
        "registry": canonical_bytes(value.to_dict()),
        "packets": canonical_bytes({"packets": [item.to_dict() for item in packets]}),
        "verification": canonical_bytes(verification.to_dict()),
    }


def _manifest(value: Registry, payloads: Mapping[str, bytes]) -> dict[str, Any]:
    receipts = []
    for kind in ("registry", "packets", "verification"):
        raw = payloads[kind]
        receipts.append(
            {
                "kind": kind,
                "file_name": _REGISTRY_FILES[kind],
                "byte_count": len(raw),
                "byte_address": _file_address(kind, raw),
                "content_address": content_hash(
                    json.loads(raw.decode("utf-8")),
                    prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
                    + "-"
                    + kind,
                ),
            }
        )
    body = {
        "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION,
        "registry_address": value.content_address,
        "verification_address": value.verification.content_address,
        "packet_count": value.packet_count,
        "files": receipts,
    }
    return body | {
        "manifest_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
            + "-manifest",
        )
    }


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
    value: Registry,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    _require_verified(value)
    payloads = _payloads(value)
    manifest = _manifest(value, payloads)
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("registry destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        files = {
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MANIFEST: canonical_bytes(
                manifest
            )
        }
        files.update({_REGISTRY_FILES[kind]: raw for kind, raw in payloads.items()})
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("registry destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_value(path: Path, field: str) -> Any:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not valid canonical JSON") from exc
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} must be canonical JSON")
    return value


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
    directory: str | Path,
) -> Registry:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("registry directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MANIFEST,
        *_REGISTRY_FILES.values(),
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("registry files do not match the published set")
    manifest = _read_value(
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MANIFEST,
        "registry manifest",
    )
    if not isinstance(manifest, Mapping):
        raise ValidationError("registry manifest must be an object")
    manifest = dict(manifest)
    manifest_address = manifest.pop("manifest_address", None)
    if manifest_address != content_hash(
        manifest,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
        + "-manifest",
    ):
        raise ValidationError("registry manifest address mismatch")
    if (
        manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION
    ):
        raise ValidationError("registry manifest version is invalid")
    registry_map = _read_value(directory / _REGISTRY_FILES["registry"], "registry document")
    packets_map = _read_value(directory / _REGISTRY_FILES["packets"], "registry packets document")
    verification_map = _read_value(
        directory / _REGISTRY_FILES["verification"], "registry verification document"
    )
    if not isinstance(packets_map, Mapping) or not isinstance(packets_map.get("packets"), list):
        raise ValidationError("registry packets document is invalid")
    registry = registry_from_mapping(registry_map)
    packets = tuple(packet_from_mapping(item) for item in packets_map["packets"])
    verification = registry_verification_from_mapping(verification_map)
    if (
        registry.packet_count != len(packets)
        or manifest.get("packet_count") != registry.packet_count
    ):
        raise ValidationError("registry packet count is not conserved")
    payloads = {
        kind: (directory / file_name).read_bytes() for kind, file_name in _REGISTRY_FILES.items()
    }
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list) or len(manifest_files) != 3:
        raise ValidationError("registry manifest file receipts are invalid")
    for receipt in manifest_files:
        if not isinstance(receipt, Mapping) or receipt.get("kind") not in _REGISTRY_FILES:
            raise ValidationError("registry manifest file kind is invalid")
        kind = str(receipt["kind"])
        raw = payloads[kind]
        if (
            receipt.get("file_name") != _REGISTRY_FILES[kind]
            or receipt.get("byte_count") != len(raw)
            or receipt.get("byte_address") != _file_address(kind, raw)
        ):
            raise ValidationError(f"registry {kind} byte receipt is invalid")
        expected_content = content_hash(
            json.loads(raw.decode("utf-8")),
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_PREFIX
            + "-"
            + kind,
        )
        if receipt.get("content_address") != expected_content:
            raise ValidationError(f"registry {kind} content receipt is invalid")
    if (
        registry.content_address != manifest.get("registry_address")
        or verification.content_address != manifest.get("verification_address")
        or verification.registry_address != registry.content_address
    ):
        raise ValidationError("registry nested addresses do not match")
    registry.packets = packets
    registry.verification = verification
    computed = _registry_verification(registry, packets)
    if not computed.accepted or computed.to_dict() != verification.to_dict():
        raise ValidationError("registry independent verification failed")
    return registry


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_json(
    value: Registry,
) -> str:
    _require_verified(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_csv(
    value: Registry,
) -> str:
    _require_verified(value)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "packet_id",
            "packet_address",
            "verification_address",
            "state",
            "accepted",
            "release_ready",
            "artifact_count",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_markdown(
    value: Registry,
) -> str:
    _require_verified(value)
    lines = [
        "# Observatory packet registry",
        "",
        f"- Registry: `{value.registry_id}`",
        f"- State: `{value.state}`",
        f"- Packets: `{value.packet_count}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        f"- Address: `{value.content_address}`",
        "",
        "| # | Packet | State | Accepted | Ready | Address |",
        "|---:|---|---|---:|---:|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.packet_id}` | {item.state} | {str(item.accepted).lower()} | {str(item.release_ready).lower()} | `{item.packet_address}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryQuery:
    """Bounded registry query parameters."""

    def __init__(
        self,
        *,
        resource: str = "summary",
        state: str | None = None,
        accepted: bool | None = None,
        release_ready: bool | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "registry query resource", 32)
        if self.resource not in {"summary", "entries", "packets", "verification", "checks"}:
            raise ValidationError("registry query resource is invalid")
        self.state = None if state is None else _state(state, "registry query state")
        self.accepted = accepted
        if accepted is not None:
            _bool(accepted, "registry query accepted")
        self.release_ready = release_ready
        if release_ready is not None:
            _bool(release_ready, "registry query release-ready")
        self.text = None if text is None else _text(text, "registry query text", 256)
        _count(
            offset,
            "registry query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_QUERY_ITEMS,
        )
        _count(limit, "registry query limit", 512, positive=True)
        self.offset = offset
        self.limit = limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "text": self.text,
            "offset": self.offset,
            "limit": self.limit,
        }


RegistryQuery = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryQuery


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryQueryResult,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_QUERY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryQueryResult:
    """Addressed bounded result page over registry resources."""

    def __init__(
        self,
        *,
        registry_address: str,
        query: RegistryQuery,
        total: int,
        offset: int,
        limit: int,
        items: Sequence[Mapping[str, Any]],
        content_address: str,
    ) -> None:
        self.registry_address = registry_address
        self.query = query
        self.total = total
        self.offset = offset
        self.limit = limit
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.registry_address, "registry query registry address")
        if not isinstance(self.query, RegistryQuery):
            raise ValidationError("registry query parameters are invalid")
        _count(
            self.total,
            "registry query total",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_QUERY_ITEMS,
        )
        _count(
            self.offset,
            "registry query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_QUERY_ITEMS,
        )
        _count(self.limit, "registry query limit", 512, positive=True)
        if (
            len(self.items) > self.limit
            or self.offset > self.total
            or not all(_public(item) for item in self.items)
        ):
            raise ValidationError("registry query page is not bounded or public")
        _address(self.content_address, "registry query content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_address": self.registry_address,
            "query": self.query.to_dict(),
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "items": list(self.items),
            "content_address": self.content_address,
        }


RegistryQueryResult = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryQueryResult


def _query_matches(item: Mapping[str, Any], query: RegistryQuery) -> bool:
    return (
        (query.state is None or item.get("state") == query.state)
        and (query.accepted is None or item.get("accepted") == query.accepted)
        and (query.release_ready is None or item.get("release_ready") == query.release_ready)
        and (query.text is None or query.text.casefold() in canonical_json(item).casefold())
    )


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
    value: Registry, query: RegistryQuery | None = None, **kwargs: Any
) -> RegistryQueryResult:
    _require_verified(value)
    query = query or RegistryQuery(**kwargs)
    if query.resource == "summary":
        candidates = (value.summary(),)
    elif query.resource == "entries":
        candidates = tuple(item.to_dict() for item in value.entries)
    elif query.resource == "packets":
        candidates = tuple(item.to_dict() for item in value.packets)
    elif query.resource == "verification":
        candidates = (value.verification.summary(),)
    else:
        candidates = tuple(item.to_dict() for item in value.verification.checks)
    filtered = tuple(item for item in candidates if _query_matches(item, query))
    provisional = RegistryQueryResult(
        registry_address=value.content_address,
        query=query,
        total=len(filtered),
        offset=query.offset,
        limit=query.limit,
        items=filtered[query.offset : query.offset + query.limit],
        content_address="pending:query",
    )
    return RegistryQueryResult(
        registry_address=provisional.registry_address,
        query=provisional.query,
        total=provisional.total,
        offset=provisional.offset,
        limit=provisional.limit,
        items=provisional.items,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
    value: RegistryQueryResult,
) -> bool:
    if not isinstance(value, RegistryQueryResult):
        raise ValidationError("registry query verification requires a typed result")
    return (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
            value
        )
        == value.content_address
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_json(
    value: RegistryQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
        value
    ):
        raise ValidationError("registry query address is invalid")
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_csv(
    value: RegistryQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
        value
    ):
        raise ValidationError("registry query address is invalid")
    fields = sorted({key for item in value.items for key in item}) or ["item"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(value.items)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_markdown(
    value: RegistryQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
        value
    ):
        raise ValidationError("registry query address is invalid")
    fields = sorted({key for item in value.items for key in item}) or ["item"]
    lines = [
        "# Observatory packet registry query",
        "",
        f"- Resource: `{value.query.resource}`",
        f"- Total: `{value.total}`",
        "",
        "| " + " | ".join(fields) + " |",
        "|" + "|".join("---" for _ in fields) + "|",
    ]
    lines.extend(
        "| " + " | ".join(str(item.get(field, "")) for field in fields) + " |"
        for item in value.items
    )
    if not value.items:
        lines.append("No matching items.")
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_BOUNDARY,
        "exact_files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MANIFEST,
            *_REGISTRY_FILES.values(),
        ],
        "resources": ["summary", "entries", "packets", "verification", "checks"],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryState
        ],
        "maximum_packets": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_PACKETS,
        "bounded": True,
        "canonical_json": True,
        "identity_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERSION,
        "operations": [
            "build",
            "build-from-directories",
            "verify",
            "write",
            "load",
            "query",
            "json",
            "csv",
            "markdown",
        ],
        "component_count": 3,
        "exact_file_count": 4,
        "independent_verification": True,
        "unique_packet_addresses": True,
        "conserved_state_counts": True,
        "atomic_write": True,
        "bounded": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "entries", "packets", "verification", "checks"],
        "filters": ["state", "accepted", "release_ready", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_capabilities() -> (
    dict[str, Any]
):
    return (
        module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_schema()
        | {"deterministic": True}
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_verification_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERIFICATION_PREFIX
        + "-v1",
        "check_fields": ["kind", "passed", "expected", "observed", "detail"],
        "maximum_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_MAX_CHECKS,
        "independent": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_verification_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_VERIFICATION_PREFIX
        + "-v1",
        "operations": ["verify", "json", "csv", "markdown"],
        "recomputes_registry_address": True,
        "recomputes_entry_addresses": True,
        "recomputes_state_counts": True,
        "identity_free": True,
    }

"""Federate multiple observatory packet registries without merging claims.

This module is the next public boundary above a single observatory packet
registry.  A federation preserves each member registry's addressed summary,
retains conserved packet rollups, evaluates an explicit bounded policy, and
emits an independent closure receipt.  It is useful when several release
windows, downloaded-data reruns, or institution-local registries must be
reviewed together while keeping their evidence boundaries separate.

The aggregate never combines scientific records and never promotes a held or
blocked member.  Directory locations are input-only.  The persisted handoff
has six exact JSON documents with canonical bytes and content-addressed file
receipts, so an offline reviewer can verify structure without access to the
source packet directories.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistry,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY = "public_registry_federation_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY_BOUNDARY = "public_registry_federation_policy"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_ENTRY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-entry"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REGISTRY_FEDERATION_POLICY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-policy"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_STAGE_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-stage"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_RUNTIME_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_FEDERATION = "federation.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_REGISTRIES = "registries.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY = "policy.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERIFICATION = "verification.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_RUNTIME = "runtime.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS = 4096
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_CHECKS = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_STAGES = 5
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS = 4096

_FEDERATION_FILES = {
    "federation": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_FEDERATION,
    "registries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_REGISTRIES,
    "policy": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY,
    "verification": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERIFICATION,
    "runtime": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_RUNTIME,
}

Registry = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistry


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    EMPTY = "empty"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStageState(
    StrEnum
):
    PASSED = "passed"
    HELD = "held"
    BLOCKED = "blocked"


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


def _json_value(value: Any, field: str) -> Any:
    try:
        result = json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be canonical JSON data") from exc
    if not _public(result):
        raise ValidationError(f"{field} crosses the public boundary")
    return result


def _state(value: Any, field: str = "federation state") -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationState
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _stage_state(value: Any, field: str = "stage state") -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStageState
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _file_address(kind: str, raw: bytes) -> str:
    return hash_bytes(
        raw,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
        + "-"
        + kind
        + "-bytes",
    )


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationPolicy,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REGISTRY_FEDERATION_POLICY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationPolicy:
    """Bounded policy for accepting a registry federation."""

    def __init__(
        self,
        *,
        policy_id: str,
        version: str,
        boundary: str,
        minimum_registries: int,
        maximum_registries: int,
        maximum_packets: int,
        maximum_blocked_registries: int,
        maximum_held_registries: int,
        require_all_registries_accepted: bool,
        require_all_release_ready: bool,
        allow_empty: bool,
        content_address: str,
    ) -> None:
        self.policy_id = policy_id
        self.version = version
        self.boundary = boundary
        self.minimum_registries = minimum_registries
        self.maximum_registries = maximum_registries
        self.maximum_packets = maximum_packets
        self.maximum_blocked_registries = maximum_blocked_registries
        self.maximum_held_registries = maximum_held_registries
        self.require_all_registries_accepted = require_all_registries_accepted
        self.require_all_release_ready = require_all_release_ready
        self.allow_empty = allow_empty
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.policy_id, "federation policy ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION
        ):
            raise ValidationError("federation policy version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY_BOUNDARY
        ):
            raise ValidationError("federation policy boundary is invalid")
        _count(
            self.minimum_registries,
            "minimum registries",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
        )
        _count(
            self.maximum_registries,
            "maximum registries",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
            positive=True,
        )
        _count(
            self.maximum_packets,
            "maximum packets",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS,
            positive=True,
        )
        _count(
            self.maximum_blocked_registries,
            "maximum blocked registries",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
        )
        _count(
            self.maximum_held_registries,
            "maximum held registries",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
        )
        if self.minimum_registries > self.maximum_registries:
            raise ValidationError("federation policy registry range is invalid")
        _bool(self.require_all_registries_accepted, "require all registries accepted")
        _bool(self.require_all_release_ready, "require all registries release-ready")
        _bool(self.allow_empty, "allow empty federation")
        _address(self.content_address, "federation policy content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "boundary": self.boundary,
            "minimum_registries": self.minimum_registries,
            "maximum_registries": self.maximum_registries,
            "maximum_packets": self.maximum_packets,
            "maximum_blocked_registries": self.maximum_blocked_registries,
            "maximum_held_registries": self.maximum_held_registries,
            "require_all_registries_accepted": self.require_all_registries_accepted,
            "require_all_release_ready": self.require_all_release_ready,
            "allow_empty": self.allow_empty,
            "content_address": self.content_address,
        }


Policy = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationPolicy


def default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
    *,
    policy_id: str = "glio-noncode-observatory-registry-federation-policy",
    minimum_registries: int = 1,
    maximum_registries: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
    maximum_packets: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS,
    maximum_blocked_registries: int = 0,
    maximum_held_registries: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
    require_all_registries_accepted: bool = True,
    require_all_release_ready: bool = True,
    allow_empty: bool = False,
) -> Policy:
    body = {
        "policy_id": _text(policy_id, "federation policy ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": "public_registry_federation_policy",
        "minimum_registries": minimum_registries,
        "maximum_registries": maximum_registries,
        "maximum_packets": maximum_packets,
        "maximum_blocked_registries": maximum_blocked_registries,
        "maximum_held_registries": maximum_held_registries,
        "require_all_registries_accepted": require_all_registries_accepted,
        "require_all_release_ready": require_all_release_ready,
        "allow_empty": allow_empty,
    }
    provisional = Policy(**body, content_address="pending:policy")
    return Policy(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationEntry,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_ENTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationEntry:
    """One addressed registry summary in deterministic federation order."""

    def __init__(
        self,
        *,
        ordinal: int,
        registry_id: str,
        registry_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        packet_count: int,
        ready_packet_count: int,
        held_packet_count: int,
        blocked_packet_count: int,
        accepted_packet_count: int,
        release_ready_packet_count: int,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.registry_id = registry_id
        self.registry_address = registry_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.packet_count = packet_count
        self.ready_packet_count = ready_packet_count
        self.held_packet_count = held_packet_count
        self.blocked_packet_count = blocked_packet_count
        self.accepted_packet_count = accepted_packet_count
        self.release_ready_packet_count = release_ready_packet_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "federation entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES
            - 1,
        )
        _text(self.registry_id, "federation entry registry ID", 256)
        _address(self.registry_address, "federation entry registry address")
        _state(self.state, "federation entry state")
        _bool(self.accepted, "federation entry accepted")
        _bool(self.release_ready, "federation entry release-ready")
        _count(
            self.packet_count,
            "federation entry packet count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS,
        )
        for count, field in (
            (self.ready_packet_count, "ready packet count"),
            (self.held_packet_count, "held packet count"),
            (self.blocked_packet_count, "blocked packet count"),
            (self.accepted_packet_count, "accepted packet count"),
            (self.release_ready_packet_count, "release-ready packet count"),
        ):
            _count(count, f"federation entry {field}", self.packet_count)
        if (
            self.ready_packet_count + self.held_packet_count + self.blocked_packet_count
            != self.packet_count
        ):
            raise ValidationError("federation entry packet states are not conserved")
        if (
            self.accepted_packet_count > self.packet_count
            or self.release_ready_packet_count > self.accepted_packet_count
        ):
            raise ValidationError("federation entry packet acceptance is not conserved")
        if self.release_ready and (self.state != "ready" or not self.accepted):
            raise ValidationError("federation entry readiness projection is invalid")
        _address(self.content_address, "federation entry content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "registry_id": self.registry_id,
            "registry_address": self.registry_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "packet_count": self.packet_count,
            "ready_packet_count": self.ready_packet_count,
            "held_packet_count": self.held_packet_count,
            "blocked_packet_count": self.blocked_packet_count,
            "accepted_packet_count": self.accepted_packet_count,
            "release_ready_packet_count": self.release_ready_packet_count,
            "content_address": self.content_address,
        }


FederationEntry = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationEntry


def _entry_from_registry(ordinal: int, value: Registry) -> FederationEntry:
    body = {
        "ordinal": ordinal,
        "registry_id": value.registry_id,
        "registry_address": value.content_address,
        "state": value.state,
        "accepted": value.accepted,
        "release_ready": value.release_ready,
        "packet_count": value.packet_count,
        "ready_packet_count": value.ready_count,
        "held_packet_count": value.held_count,
        "blocked_packet_count": value.blocked_count,
        "accepted_packet_count": value.accepted_count,
        "release_ready_packet_count": value.release_ready_count,
    }
    provisional = FederationEntry(**body, content_address="pending:entry")
    return FederationEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_entry(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationCheck:
    """Addressed independent structural or policy finding."""

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
            "federation check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "federation check kind", 128)
        _bool(self.passed, "federation check passed")
        self.expected = _json_value(self.expected, "federation check expected")
        self.observed = _json_value(self.observed, "federation check observed")
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


FederationCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationCheck


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> FederationCheck:
    body = {
        "ordinal": ordinal,
        "kind": _text(kind, "federation check kind", 128),
        "passed": bool(passed),
        "expected": _json_value(expected, "federation check expected"),
        "observed": _json_value(observed, "federation check observed"),
        "detail": _text(detail, "federation check detail"),
    }
    provisional = FederationCheck(**body, content_address="pending:check")
    return FederationCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_check(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationVerification:
    """Addressed receipt for independent federation verification."""

    def __init__(
        self,
        *,
        federation_address: str,
        policy_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: Sequence[FederationCheck],
        content_address: str,
    ) -> None:
        self.federation_address = federation_address
        self.policy_address = policy_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "federation verification federation address")
        _address(self.policy_address, "federation verification policy address")
        _count(
            self.check_count,
            "federation verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_CHECKS,
            positive=True,
        )
        _count(self.passed_count, "federation verification passed count", self.check_count)
        _count(self.failed_count, "federation verification failed count", self.check_count)
        if (
            self.check_count != len(self.checks)
            or self.passed_count + self.failed_count != self.check_count
        ):
            raise ValidationError("federation verification counts are not conserved")
        _bool(self.accepted, "federation verification accepted")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, FederationCheck) or check.ordinal != ordinal:
                raise ValidationError("federation verification checks are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("federation verification check address is invalid")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("federation verification acceptance is not conserved")
        _address(self.content_address, "federation verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_address": self.federation_address,
            "policy_address": self.policy_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [item.to_dict() for item in self.checks]}


FederationVerification = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationVerification


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStage,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_STAGE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStage:
    """One deterministic runtime closure stage."""

    def __init__(
        self,
        *,
        ordinal: int,
        name: str,
        state: str,
        input_address: str | None,
        output_address: str | None,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.name = name
        self.state = state
        self.input_address = input_address
        self.output_address = output_address
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "federation runtime stage ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_STAGES
            - 1,
        )
        _text(self.name, "federation runtime stage name", 64)
        _stage_state(self.state)
        if self.input_address is not None:
            _address(self.input_address, "federation runtime stage input address")
        if self.output_address is not None:
            _address(self.output_address, "federation runtime stage output address")
        _text(self.detail, "federation runtime stage detail")
        _address(self.content_address, "federation runtime stage content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation runtime stage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "name": self.name,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "detail": self.detail,
            "content_address": self.content_address,
        }


FederationStage = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStage


def _stage(
    ordinal: int,
    name: str,
    state: str,
    input_address: str | None,
    output_address: str | None,
    detail: str,
) -> FederationStage:
    body = {
        "ordinal": ordinal,
        "name": _text(name, "federation runtime stage name", 64),
        "state": _stage_state(state),
        "input_address": input_address,
        "output_address": output_address,
        "detail": _text(detail, "federation runtime stage detail"),
    }
    provisional = FederationStage(**body, content_address="pending:stage")
    return FederationStage(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_stage(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationRuntime,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_RUNTIME_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationRuntime:
    """Policy-controlled runtime closure for one federation."""

    def __init__(
        self,
        *,
        runtime_id: str,
        version: str,
        boundary: str,
        federation_address: str,
        policy_address: str,
        verification_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        stage_count: int,
        stages: Sequence[FederationStage],
        policy_check_count: int,
        policy_passed_count: int,
        policy_failed_count: int,
        policy_checks: Sequence[FederationCheck],
        content_address: str,
    ) -> None:
        self.runtime_id = runtime_id
        self.version = version
        self.boundary = boundary
        self.federation_address = federation_address
        self.policy_address = policy_address
        self.verification_address = verification_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.stage_count = stage_count
        self.stages = tuple(stages)
        self.policy_check_count = policy_check_count
        self.policy_passed_count = policy_passed_count
        self.policy_failed_count = policy_failed_count
        self.policy_checks = tuple(policy_checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.runtime_id, "federation runtime ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION
        ):
            raise ValidationError("federation runtime version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY
        ):
            raise ValidationError("federation runtime boundary is invalid")
        _address(self.federation_address, "federation runtime federation address")
        _address(self.policy_address, "federation runtime policy address")
        _address(self.verification_address, "federation runtime verification address")
        _state(self.state, "federation runtime state")
        _bool(self.accepted, "federation runtime accepted")
        _bool(self.release_ready, "federation runtime release-ready")
        _count(
            self.stage_count,
            "federation runtime stage count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_STAGES,
            positive=True,
        )
        if self.stage_count != len(self.stages):
            raise ValidationError("federation runtime stage count is not conserved")
        for ordinal, stage in enumerate(self.stages):
            if not isinstance(stage, FederationStage) or stage.ordinal != ordinal:
                raise ValidationError("federation runtime stages are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_stage(
                    stage
                )
                != stage.content_address
            ):
                raise ValidationError("federation runtime stage address is invalid")
        _count(
            self.policy_check_count,
            "federation policy check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_CHECKS,
            positive=True,
        )
        _count(self.policy_passed_count, "federation policy passed count", self.policy_check_count)
        _count(self.policy_failed_count, "federation policy failed count", self.policy_check_count)
        if (
            self.policy_check_count != len(self.policy_checks)
            or self.policy_passed_count + self.policy_failed_count != self.policy_check_count
        ):
            raise ValidationError("federation policy check counts are not conserved")
        for ordinal, check in enumerate(self.policy_checks):
            if not isinstance(check, FederationCheck) or check.ordinal != ordinal:
                raise ValidationError("federation policy checks are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("federation policy check address is invalid")
        expected_state = (
            "blocked" if not self.accepted else "ready" if self.release_ready else "held"
        )
        if self.state != expected_state:
            raise ValidationError("federation runtime state projection is invalid")
        if self.release_ready and not self.accepted:
            raise ValidationError("federation runtime readiness requires acceptance")
        _address(self.content_address, "federation runtime content address")
        if not _public(self.to_dict()):
            raise ValidationError("federation runtime crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "version": self.version,
            "boundary": self.boundary,
            "federation_address": self.federation_address,
            "policy_address": self.policy_address,
            "verification_address": self.verification_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "stage_count": self.stage_count,
            "policy_check_count": self.policy_check_count,
            "policy_passed_count": self.policy_passed_count,
            "policy_failed_count": self.policy_failed_count,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {
            "stages": [item.to_dict() for item in self.stages],
            "policy_checks": [item.to_dict() for item in self.policy_checks],
        }


FederationRuntime = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationRuntime


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederation,
) -> str:
    body = value.to_dict() | {
        "content_address": None,
        "verification_address": None,
        "runtime_address": None,
    }
    return content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederation:
    """Addressed aggregate over independently verified registries."""

    def __init__(
        self,
        *,
        federation_id: str,
        version: str,
        boundary: str,
        registry_count: int,
        total_packet_count: int,
        ready_registry_count: int,
        held_registry_count: int,
        blocked_registry_count: int,
        accepted_registry_count: int,
        release_ready_registry_count: int,
        ready_packet_count: int,
        held_packet_count: int,
        blocked_packet_count: int,
        accepted_packet_count: int,
        release_ready_packet_count: int,
        state: str,
        accepted: bool,
        release_ready: bool,
        policy_address: str,
        verification_address: str,
        runtime_address: str,
        entries: Sequence[FederationEntry],
        content_address: str,
    ) -> None:
        self.federation_id = federation_id
        self.version = version
        self.boundary = boundary
        self.registry_count = registry_count
        self.total_packet_count = total_packet_count
        self.ready_registry_count = ready_registry_count
        self.held_registry_count = held_registry_count
        self.blocked_registry_count = blocked_registry_count
        self.accepted_registry_count = accepted_registry_count
        self.release_ready_registry_count = release_ready_registry_count
        self.ready_packet_count = ready_packet_count
        self.held_packet_count = held_packet_count
        self.blocked_packet_count = blocked_packet_count
        self.accepted_packet_count = accepted_packet_count
        self.release_ready_packet_count = release_ready_packet_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.policy_address = policy_address
        self.verification_address = verification_address
        self.runtime_address = runtime_address
        self.entries = tuple(entries)
        self.content_address = content_address
        self.registries: tuple[Registry, ...] = ()
        self.policy: Policy | None = None
        self.verification: FederationVerification | None = None
        self.runtime: FederationRuntime | None = None
        self._validate()

    def _validate(self) -> None:
        _text(self.federation_id, "federation ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION
        ):
            raise ValidationError("federation version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY
        ):
            raise ValidationError("federation boundary is invalid")
        _count(
            self.registry_count,
            "federation registry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
        )
        _count(
            self.total_packet_count,
            "federation total packet count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS,
        )
        for count, field in (
            (self.ready_registry_count, "ready registry count"),
            (self.held_registry_count, "held registry count"),
            (self.blocked_registry_count, "blocked registry count"),
            (self.accepted_registry_count, "accepted registry count"),
            (self.release_ready_registry_count, "release-ready registry count"),
        ):
            _count(count, f"federation {field}", self.registry_count)
        for count, field in (
            (self.ready_packet_count, "ready packet count"),
            (self.held_packet_count, "held packet count"),
            (self.blocked_packet_count, "blocked packet count"),
            (self.accepted_packet_count, "accepted packet count"),
            (self.release_ready_packet_count, "release-ready packet count"),
        ):
            _count(count, f"federation {field}", self.total_packet_count)
        if (
            self.registry_count != len(self.entries)
            or self.ready_registry_count + self.held_registry_count + self.blocked_registry_count
            != self.registry_count
        ):
            raise ValidationError("federation registry states are not conserved")
        if (
            self.accepted_registry_count > self.registry_count
            or self.release_ready_registry_count > self.accepted_registry_count
        ):
            raise ValidationError("federation registry acceptance is not conserved")
        if (
            self.ready_packet_count + self.held_packet_count + self.blocked_packet_count
            != self.total_packet_count
        ):
            raise ValidationError("federation packet states are not conserved")
        if (
            self.accepted_packet_count > self.total_packet_count
            or self.release_ready_packet_count > self.accepted_packet_count
        ):
            raise ValidationError("federation packet acceptance is not conserved")
        _state(self.state)
        _bool(self.accepted, "federation accepted")
        _bool(self.release_ready, "federation release-ready")
        _address(self.policy_address, "federation policy address")
        _address(self.verification_address, "federation verification address")
        _address(self.runtime_address, "federation runtime address")
        if self.release_ready != (
            self.registry_count > 0
            and self.ready_registry_count == self.registry_count
            and self.release_ready_registry_count == self.registry_count
        ):
            raise ValidationError("federation release projection is invalid")
        expected_state = (
            "empty"
            if self.registry_count == 0
            else "blocked"
            if self.blocked_registry_count or self.accepted_registry_count < self.registry_count
            else "ready"
            if self.release_ready
            else "held"
        )
        if self.state != expected_state:
            raise ValidationError("federation state projection is invalid")
        if not self.accepted:
            raise ValidationError("federation metadata must be structurally accepted")
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(entry, FederationEntry) or entry.ordinal != ordinal:
                raise ValidationError("federation entries are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_entry(
                    entry
                )
                != entry.content_address
            ):
                raise ValidationError("federation entry address is invalid")
        if (
            len({entry.registry_id for entry in self.entries}) != self.registry_count
            or len({entry.registry_address for entry in self.entries}) != self.registry_count
        ):
            raise ValidationError("federation registry identities are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("federation crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_id": self.federation_id,
            "version": self.version,
            "boundary": self.boundary,
            "registry_count": self.registry_count,
            "total_packet_count": self.total_packet_count,
            "ready_registry_count": self.ready_registry_count,
            "held_registry_count": self.held_registry_count,
            "blocked_registry_count": self.blocked_registry_count,
            "accepted_registry_count": self.accepted_registry_count,
            "release_ready_registry_count": self.release_ready_registry_count,
            "ready_packet_count": self.ready_packet_count,
            "held_packet_count": self.held_packet_count,
            "blocked_packet_count": self.blocked_packet_count,
            "accepted_packet_count": self.accepted_packet_count,
            "release_ready_packet_count": self.release_ready_packet_count,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "policy_address": self.policy_address,
            "verification_address": self.verification_address,
            "runtime_address": self.runtime_address,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"entries": [item.to_dict() for item in self.entries]}


Federation = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederation


def _federation_metadata(
    federation_id: str,
    entries: Sequence[FederationEntry],
    policy: Policy,
    *,
    verification_address: str = "pending:verification",
    runtime_address: str = "pending:runtime",
    content_address: str = "pending:federation",
) -> Federation:
    registry_count = len(entries)
    total_packet_count = sum(item.packet_count for item in entries)
    ready_registry_count = sum(item.state == "ready" for item in entries)
    held_registry_count = sum(item.state == "held" for item in entries)
    blocked_registry_count = sum(item.state == "blocked" for item in entries)
    accepted_registry_count = sum(item.accepted for item in entries)
    release_ready_registry_count = sum(item.release_ready for item in entries)
    ready_packet_count = sum(item.ready_packet_count for item in entries)
    held_packet_count = sum(item.held_packet_count for item in entries)
    blocked_packet_count = sum(item.blocked_packet_count for item in entries)
    accepted_packet_count = sum(item.accepted_packet_count for item in entries)
    release_ready_packet_count = sum(item.release_ready_packet_count for item in entries)
    release_ready = (
        registry_count > 0
        and ready_registry_count == registry_count
        and release_ready_registry_count == registry_count
    )
    state = (
        "empty"
        if registry_count == 0
        else "blocked"
        if blocked_registry_count or accepted_registry_count < registry_count
        else "ready"
        if release_ready
        else "held"
    )
    return Federation(
        federation_id=_text(federation_id, "federation ID", 256),
        version=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        boundary=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY,
        registry_count=registry_count,
        total_packet_count=total_packet_count,
        ready_registry_count=ready_registry_count,
        held_registry_count=held_registry_count,
        blocked_registry_count=blocked_registry_count,
        accepted_registry_count=accepted_registry_count,
        release_ready_registry_count=release_ready_registry_count,
        ready_packet_count=ready_packet_count,
        held_packet_count=held_packet_count,
        blocked_packet_count=blocked_packet_count,
        accepted_packet_count=accepted_packet_count,
        release_ready_packet_count=release_ready_packet_count,
        state=state,
        accepted=True,
        release_ready=release_ready,
        policy_address=policy.content_address,
        verification_address=verification_address,
        runtime_address=runtime_address,
        entries=entries,
        content_address=content_address,
    )


def _build_federation_verification(
    value: Federation,
    registries: Sequence[Registry] | None,
    policy: Policy | None,
) -> FederationVerification:
    checks: list[FederationCheck] = []

    def add(kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> None:
        checks.append(_check(len(checks), kind, passed, expected, observed, detail))

    registry_values = tuple(registries or ())
    registry_by_id = {
        item.registry_id: item for item in registry_values if isinstance(item, Registry)
    }
    expected_counts = {
        "ready_registry_count": sum(item.state == "ready" for item in value.entries),
        "held_registry_count": sum(item.state == "held" for item in value.entries),
        "blocked_registry_count": sum(item.state == "blocked" for item in value.entries),
        "accepted_registry_count": sum(item.accepted for item in value.entries),
        "release_ready_registry_count": sum(item.release_ready for item in value.entries),
        "total_packet_count": sum(item.packet_count for item in value.entries),
        "ready_packet_count": sum(item.ready_packet_count for item in value.entries),
        "held_packet_count": sum(item.held_packet_count for item in value.entries),
        "blocked_packet_count": sum(item.blocked_packet_count for item in value.entries),
        "accepted_packet_count": sum(item.accepted_packet_count for item in value.entries),
        "release_ready_packet_count": sum(
            item.release_ready_packet_count for item in value.entries
        ),
    }
    add(
        "federation-address",
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value
        )
        == value.content_address,
        "recomputed federation address",
        value.content_address,
        "federation metadata address is conserved",
    )
    add(
        "entry-count",
        value.registry_count == len(value.entries),
        value.registry_count,
        len(value.entries),
        "federation registry and entry counts agree",
    )
    add(
        "entry-order",
        tuple(item.ordinal for item in value.entries) == tuple(range(value.registry_count)),
        list(range(value.registry_count)),
        [item.ordinal for item in value.entries],
        "federation entry ordinals are contiguous",
    )
    add(
        "registry-id-uniqueness",
        len({item.registry_id for item in value.entries}) == value.registry_count,
        value.registry_count,
        len({item.registry_id for item in value.entries}),
        "registry IDs are unique",
    )
    add(
        "registry-address-uniqueness",
        len({item.registry_address for item in value.entries}) == value.registry_count,
        value.registry_count,
        len({item.registry_address for item in value.entries}),
        "registry addresses are unique",
    )
    add(
        "registry-state-conservation",
        value.ready_registry_count + value.held_registry_count + value.blocked_registry_count
        == value.registry_count,
        value.registry_count,
        value.ready_registry_count + value.held_registry_count + value.blocked_registry_count,
        "registry states are conserved",
    )
    add(
        "registry-acceptance-conservation",
        value.accepted_registry_count == sum(item.accepted for item in value.entries),
        value.accepted_registry_count,
        sum(item.accepted for item in value.entries),
        "registry acceptance is conserved",
    )
    add(
        "registry-readiness-conservation",
        value.release_ready_registry_count == sum(item.release_ready for item in value.entries),
        value.release_ready_registry_count,
        sum(item.release_ready for item in value.entries),
        "registry readiness is conserved",
    )
    for field, detail in (
        ("total_packet_count", "packet totals are conserved"),
        ("ready_packet_count", "ready packet totals are conserved"),
        ("held_packet_count", "held packet totals are conserved"),
        ("blocked_packet_count", "blocked packet totals are conserved"),
        ("accepted_packet_count", "accepted packet totals are conserved"),
        ("release_ready_packet_count", "release-ready packet totals are conserved"),
    ):
        add(
            f"{field.replace('_', '-')}",
            getattr(value, field) == expected_counts[field],
            getattr(value, field),
            expected_counts[field],
            detail,
        )
    projected_state = (
        "empty"
        if value.registry_count == 0
        else "blocked"
        if value.blocked_registry_count or value.accepted_registry_count < value.registry_count
        else "ready"
        if value.release_ready
        else "held"
    )
    add(
        "state-projection",
        value.state == projected_state,
        projected_state,
        value.state,
        "federation state matches conserved registry counts",
    )
    projected_release = (
        value.registry_count > 0
        and value.ready_registry_count == value.registry_count
        and value.release_ready_registry_count == value.registry_count
    )
    add(
        "release-projection",
        value.release_ready == projected_release,
        projected_release,
        value.release_ready,
        "federation readiness matches all-ready registries",
    )
    add(
        "policy-link",
        policy is None or policy.content_address == value.policy_address,
        value.policy_address,
        None if policy is None else policy.content_address,
        "federation policy address is linked",
    )
    entry_addresses = tuple(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_entry(
            item
        )
        == item.content_address
        for item in value.entries
    )
    add(
        "entry-addresses",
        all(entry_addresses),
        True,
        all(entry_addresses),
        "federation entry addresses are conserved",
    )
    registry_links = tuple(
        item.registry_id in registry_by_id
        and registry_by_id[item.registry_id].content_address == item.registry_address
        and address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            registry_by_id[item.registry_id]
        )
        == item.registry_address
        for item in value.entries
    )
    add(
        "registry-links",
        not registry_values or all(registry_links),
        True if not registry_values else True,
        True if not registry_values else all(registry_links),
        "hydrated registry metadata links are conserved",
    )
    add(
        "public-boundary",
        _public(value.to_dict()) and _public(None if policy is None else policy.to_dict()),
        True,
        _public(value.to_dict()) and _public(None if policy is None else policy.to_dict()),
        "federation projections remain public",
    )
    body = {
        "federation_address": value.content_address,
        "policy_address": value.policy_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = FederationVerification(**body, content_address="pending:verification")
    return FederationVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
    registries: Sequence[Registry],
    *,
    federation_id: str = "glio-noncode-observatory-packet-registry-federation",
    policy: Policy | None = None,
) -> Federation:
    """Build a deterministic federation from independently verified registries."""

    if not isinstance(registries, Sequence) or isinstance(registries, (str, bytes)):
        raise ValidationError("federation registries must be a bounded sequence")
    if (
        len(registries)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES
    ):
        raise ValidationError("federation registry count exceeds its bound")
    policy = (
        policy
        or default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy()
    )
    if not isinstance(policy, Policy):
        raise ValidationError("federation requires a typed policy")
    values = []
    for item in registries:
        if not isinstance(item, Registry):
            raise ValidationError("federation requires typed registries")
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            item
        )
        if not verification.accepted:
            raise ValidationError("federation requires independently accepted registries")
        values.append(item)
    ordered = tuple(sorted(values, key=lambda item: (item.registry_id, item.content_address)))
    if len({item.registry_id for item in ordered}) != len(ordered) or len(
        {item.content_address for item in ordered}
    ) != len(ordered):
        raise ValidationError("federation registry identities must be unique")
    entries = tuple(_entry_from_registry(index, item) for index, item in enumerate(ordered))
    provisional = _federation_metadata(federation_id, entries, policy)
    federation_address = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
        provisional
    )
    addressed = _federation_metadata(
        federation_id, entries, policy, content_address=federation_address
    )
    verification = _build_federation_verification(addressed, ordered, policy)
    runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
        addressed, policy=policy, verification=verification
    )
    value = _federation_metadata(
        federation_id,
        entries,
        policy,
        verification_address=verification.content_address,
        runtime_address=runtime.content_address,
        content_address=federation_address,
    )
    value.registries = ordered
    value.policy = policy
    value.verification = verification
    value.runtime = runtime
    return value


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories(
    directories: Iterable[str | Path],
    *,
    federation_id: str = "glio-noncode-observatory-packet-registry-federation",
    policy: Policy | None = None,
) -> Federation:
    paths = tuple(Path(item) for item in directories)
    if (
        not paths
        or len(paths)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES
    ):
        raise ValidationError("federation registry directory count is outside its bound")
    registries = tuple(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            path
        )
        for path in paths
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
        registries, federation_id=federation_id, policy=policy
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
    value: Federation,
    *,
    registries: Sequence[Registry] | None = None,
    policy: Policy | None = None,
) -> FederationVerification:
    if not isinstance(value, Federation):
        raise ValidationError("federation verification requires a typed federation")
    hydrated = tuple(registries) if registries is not None else value.registries
    selected_policy = policy or value.policy
    return _build_federation_verification(value, hydrated, selected_policy)


def _policy_checks(federation: Federation, policy: Policy) -> tuple[FederationCheck, ...]:
    checks: list[FederationCheck] = []

    def add(kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> None:
        checks.append(_check(len(checks), kind, passed, expected, observed, detail))

    add(
        "minimum-registries",
        federation.registry_count >= policy.minimum_registries,
        policy.minimum_registries,
        federation.registry_count,
        "federation registry count meets the minimum",
    )
    add(
        "maximum-registries",
        federation.registry_count <= policy.maximum_registries,
        policy.maximum_registries,
        federation.registry_count,
        "federation registry count is within the maximum",
    )
    add(
        "maximum-packets",
        federation.total_packet_count <= policy.maximum_packets,
        policy.maximum_packets,
        federation.total_packet_count,
        "federation packet count is within the maximum",
    )
    add(
        "blocked-registry-budget",
        federation.blocked_registry_count <= policy.maximum_blocked_registries,
        policy.maximum_blocked_registries,
        federation.blocked_registry_count,
        "blocked registry count is within policy",
    )
    add(
        "held-registry-budget",
        federation.held_registry_count <= policy.maximum_held_registries,
        policy.maximum_held_registries,
        federation.held_registry_count,
        "held registry count is within policy",
    )
    add(
        "accepted-registries",
        not policy.require_all_registries_accepted
        or federation.accepted_registry_count == federation.registry_count,
        federation.registry_count if policy.require_all_registries_accepted else "not-required",
        federation.accepted_registry_count,
        "registry acceptance requirement is satisfied",
    )
    add(
        "release-ready-registries",
        not policy.require_all_release_ready
        or federation.release_ready_registry_count == federation.registry_count,
        federation.registry_count if policy.require_all_release_ready else "not-required",
        federation.release_ready_registry_count,
        "registry release-readiness requirement is satisfied",
    )
    add(
        "empty-federation",
        federation.registry_count > 0 or policy.allow_empty,
        "non-empty" if not policy.allow_empty else "empty-allowed",
        federation.registry_count,
        "empty federation policy is satisfied",
    )
    return tuple(checks)


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
    federation: Federation,
    *,
    policy: Policy | None = None,
    verification: FederationVerification | None = None,
    runtime_id: str = "glio-noncode-observatory-registry-federation-runtime",
) -> FederationRuntime:
    """Run the ordered load, verify, policy, project, and complete closure."""

    if not isinstance(federation, Federation):
        raise ValidationError("federation runtime requires a typed federation")
    policy = (
        policy
        or federation.policy
        or default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy()
    )
    if not isinstance(policy, Policy):
        raise ValidationError("federation runtime requires a typed policy")
    verification = verification or _build_federation_verification(
        federation, federation.registries, policy
    )
    if not isinstance(verification, FederationVerification):
        raise ValidationError("federation runtime requires a typed verification")
    policy_checks = _policy_checks(federation, policy)
    policy_accepted = all(item.passed for item in policy_checks)
    accepted = verification.accepted and policy_accepted
    release_ready = accepted and federation.release_ready
    final_state = "ready" if release_ready else "held" if accepted else "blocked"
    verification_state = "passed" if verification.accepted else "blocked"
    policy_state = "passed" if policy_accepted else "blocked"
    stages = (
        _stage(0, "load", "passed", None, federation.content_address, "federation input accepted"),
        _stage(
            1,
            "verify",
            verification_state,
            federation.content_address,
            verification.content_address,
            "independent federation verification completed",
        ),
        _stage(
            2,
            "policy",
            policy_state,
            verification.content_address,
            policy.content_address,
            "bounded federation policy evaluated",
        ),
        _stage(
            3,
            "project",
            "passed" if accepted else "blocked",
            policy.content_address,
            federation.content_address,
            "federation release projection prepared",
        ),
        _stage(
            4,
            "complete",
            "passed" if release_ready else "held" if accepted else "blocked",
            federation.content_address,
            federation.content_address,
            "federation runtime closure completed",
        ),
    )
    body = {
        "runtime_id": _text(runtime_id, "federation runtime ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY,
        "federation_address": federation.content_address,
        "policy_address": policy.content_address,
        "verification_address": verification.content_address,
        "state": final_state,
        "accepted": accepted,
        "release_ready": release_ready,
        "stage_count": len(stages),
        "stages": stages,
        "policy_check_count": len(policy_checks),
        "policy_passed_count": sum(item.passed for item in policy_checks),
        "policy_failed_count": sum(not item.passed for item in policy_checks),
        "policy_checks": policy_checks,
    }
    provisional = FederationRuntime(**body, content_address="pending:runtime")
    runtime = FederationRuntime(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
            provisional
        ),
    )
    return runtime


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
    value: FederationRuntime,
    federation: Federation,
    *,
    policy: Policy | None = None,
    verification: FederationVerification | None = None,
) -> FederationVerification:
    """Replay a runtime and return an addressed runtime verification receipt."""

    if not isinstance(value, FederationRuntime) or not isinstance(federation, Federation):
        raise ValidationError("runtime verification requires typed inputs")
    policy = policy or federation.policy
    if not isinstance(policy, Policy):
        raise ValidationError("runtime verification requires a typed policy")
    expected_verification = verification or _build_federation_verification(
        federation, federation.registries, policy
    )
    replay = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
        federation, policy=policy, verification=expected_verification, runtime_id=value.runtime_id
    )
    checks = (
        _check(
            0,
            "runtime-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
                value
            )
            == value.content_address,
            "recomputed runtime address",
            value.content_address,
            "runtime address is conserved",
        ),
        _check(
            1,
            "federation-link",
            value.federation_address == federation.content_address,
            federation.content_address,
            value.federation_address,
            "runtime federation link is conserved",
        ),
        _check(
            2,
            "policy-link",
            value.policy_address == policy.content_address,
            policy.content_address,
            value.policy_address,
            "runtime policy link is conserved",
        ),
        _check(
            3,
            "verification-link",
            value.verification_address == expected_verification.content_address,
            expected_verification.content_address,
            value.verification_address,
            "runtime verification link is conserved",
        ),
        _check(
            4,
            "runtime-replay",
            replay.to_dict() == value.to_dict(),
            True,
            replay.to_dict() == value.to_dict(),
            "runtime closure replays deterministically",
        ),
        _check(
            5,
            "public-boundary",
            _public(value.to_dict()),
            True,
            _public(value.to_dict()),
            "runtime projection remains public",
        ),
    )
    body = {
        "federation_address": federation.content_address,
        "policy_address": policy.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": checks,
    }
    provisional = FederationVerification(**body, content_address="pending:runtime-verification")
    return FederationVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification(
            provisional
        ),
    )


def federation_policy_from_mapping(value: Mapping[str, Any]) -> Policy:
    try:
        return Policy(**dict(_require_mapping(value, "federation policy mapping")))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation policy mapping is invalid") from exc


def federation_entry_from_mapping(value: Mapping[str, Any]) -> FederationEntry:
    try:
        return FederationEntry(**dict(_require_mapping(value, "federation entry mapping")))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation entry mapping is invalid") from exc


def federation_check_from_mapping(value: Mapping[str, Any]) -> FederationCheck:
    try:
        return FederationCheck(**dict(_require_mapping(value, "federation check mapping")))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation check mapping is invalid") from exc


def federation_verification_from_mapping(value: Mapping[str, Any]) -> FederationVerification:
    body = dict(_require_mapping(value, "federation verification mapping"))
    try:
        checks = tuple(federation_check_from_mapping(item) for item in body.pop("checks"))
        return FederationVerification(**(body | {"checks": checks}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation verification mapping is invalid") from exc


def federation_stage_from_mapping(value: Mapping[str, Any]) -> FederationStage:
    try:
        return FederationStage(**dict(_require_mapping(value, "federation stage mapping")))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation stage mapping is invalid") from exc


def federation_runtime_from_mapping(value: Mapping[str, Any]) -> FederationRuntime:
    body = dict(_require_mapping(value, "federation runtime mapping"))
    try:
        stages = tuple(federation_stage_from_mapping(item) for item in body.pop("stages"))
        checks = tuple(federation_check_from_mapping(item) for item in body.pop("policy_checks"))
        return FederationRuntime(**(body | {"stages": stages, "policy_checks": checks}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation runtime mapping is invalid") from exc


def federation_from_mapping(value: Mapping[str, Any]) -> Federation:
    body = dict(_require_mapping(value, "federation mapping"))
    try:
        entries = tuple(federation_entry_from_mapping(item) for item in body.pop("entries"))
        return Federation(**(body | {"entries": entries}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("federation mapping is invalid") from exc


def _manifest_body(value: Federation, documents: Mapping[str, bytes]) -> dict[str, Any]:
    artifacts = []
    for kind, file_name in _FEDERATION_FILES.items():
        raw = documents[file_name]
        artifacts.append(
            {
                "kind": kind,
                "file_name": file_name,
                "byte_count": len(raw),
                "byte_address": _file_address(kind, raw),
            }
        )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY,
        "federation_id": value.federation_id,
        "federation_address": value.content_address,
        "policy_address": value.policy_address,
        "verification_address": value.verification_address,
        "runtime_address": value.runtime_address,
        "artifact_count": len(documents),
        "artifact_files": artifacts,
    }


def _canonical_document(value: Any) -> bytes:
    return canonical_bytes(value)


def _require_verified(value: Federation) -> None:
    if not isinstance(value, Federation):
        raise ValidationError("federation operation requires a typed federation")
    policy = value.policy
    result = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
        value, policy=policy
    )
    if not result.accepted:
        raise ValidationError("federation verification failed")


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
    value: Federation,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a federation as six canonical, atomically replaced documents."""

    _require_verified(value)
    destination = Path(destination)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValidationError("federation destination must be a regular directory")
    if destination.exists() and not overwrite:
        raise ValidationError("federation destination already exists")
    policy = value.policy
    if not isinstance(policy, Policy):
        raise ValidationError("federation policy is not hydrated")
    verification = value.verification or _build_federation_verification(
        value, value.registries, policy
    )
    runtime = (
        value.runtime
        or run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
            value, policy=policy, verification=verification
        )
    )
    if (
        verification.content_address != value.verification_address
        or runtime.content_address != value.runtime_address
    ):
        raise ValidationError("federation closure receipt addresses are stale")
    documents = {
        _FEDERATION_FILES["federation"]: _canonical_document(value.to_dict()),
        _FEDERATION_FILES["registries"]: _canonical_document(
            {
                "registry_count": value.registry_count,
                "entries": [item.to_dict() for item in value.entries],
            }
        ),
        _FEDERATION_FILES["policy"]: _canonical_document(policy.to_dict()),
        _FEDERATION_FILES["verification"]: _canonical_document(verification.to_dict()),
        _FEDERATION_FILES["runtime"]: _canonical_document(runtime.to_dict()),
    }
    manifest = _manifest_body(value, documents)
    manifest["manifest_address"] = content_hash(
        manifest | {"manifest_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
        + "-manifest",
    )
    documents[
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MANIFEST
    ] = _canonical_document(manifest)
    expected_files = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MANIFEST,
        *_FEDERATION_FILES.values(),
    }
    if set(documents) != expected_files:
        raise ValidationError("federation artifact file set is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".glio-federation-", dir=str(destination.parent)))
    try:
        for file_name, raw in documents.items():
            (temporary / file_name).write_bytes(raw)
        if destination.exists():
            if destination.is_symlink():
                raise ValidationError("federation destination cannot be a symlink")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def _read_canonical_document(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"federation artifact is not a regular file: {path.name}")
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"federation artifact is not valid JSON: {path.name}") from exc
    if not isinstance(document, Mapping) or canonical_bytes(document) != raw:
        raise ValidationError(f"federation artifact is not canonical: {path.name}")
    return dict(document)


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
    directory: str | Path,
) -> Federation:
    """Load and strictly verify a six-document federation handoff."""

    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("federation input must be a regular directory")
    children = tuple(directory.iterdir())
    if any(item.is_symlink() for item in children):
        raise ValidationError("federation input cannot contain symlinks")
    expected_files = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MANIFEST,
        *_FEDERATION_FILES.values(),
    }
    if {item.name for item in children} != expected_files:
        raise ValidationError("federation input has an unexpected file set")
    documents = {item.name: _read_canonical_document(item) for item in children}
    manifest = documents[
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MANIFEST
    ]
    if manifest.get("manifest_address") != content_hash(
        manifest | {"manifest_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX
        + "-manifest",
    ):
        raise ValidationError("federation manifest address is invalid")
    if manifest.get("artifact_count") != len(_FEDERATION_FILES):
        raise ValidationError("federation manifest artifact count is invalid")
    artifact_rows = manifest.get("artifact_files")
    if not isinstance(artifact_rows, list) or {
        row.get("file_name") for row in artifact_rows if isinstance(row, Mapping)
    } != set(_FEDERATION_FILES.values()):
        raise ValidationError("federation manifest artifact files are invalid")
    raw_by_name = {name: (directory / name).read_bytes() for name in _FEDERATION_FILES.values()}
    for row in artifact_rows:
        if not isinstance(row, Mapping) or row.get("file_name") not in raw_by_name:
            raise ValidationError("federation manifest receipt is invalid")
        raw = raw_by_name[row["file_name"]]
        if row.get("byte_count") != len(raw) or row.get("byte_address") != _file_address(
            str(row.get("kind")), raw
        ):
            raise ValidationError("federation manifest byte receipt is invalid")
    value = federation_from_mapping(documents[_FEDERATION_FILES["federation"]])
    registry_document = documents[_FEDERATION_FILES["registries"]]
    registry_rows = registry_document.get("entries")
    if (
        registry_document.get("registry_count") != value.registry_count
        or not isinstance(registry_rows, list)
        or tuple(registry_rows) != tuple(item.to_dict() for item in value.entries)
    ):
        raise ValidationError("federation registry projection is not conserved")
    policy = federation_policy_from_mapping(documents[_FEDERATION_FILES["policy"]])
    verification = federation_verification_from_mapping(
        documents[_FEDERATION_FILES["verification"]]
    )
    runtime = federation_runtime_from_mapping(documents[_FEDERATION_FILES["runtime"]])
    if (
        manifest.get("federation_address") != value.content_address
        or manifest.get("policy_address") != policy.content_address
        or manifest.get("verification_address") != verification.content_address
        or manifest.get("runtime_address") != runtime.content_address
    ):
        raise ValidationError("federation manifest links are invalid")
    if (
        value.policy_address != policy.content_address
        or value.verification_address != verification.content_address
        or value.runtime_address != runtime.content_address
    ):
        raise ValidationError("federation closure links are invalid")
    if (
        verification.federation_address != value.content_address
        or verification.policy_address != policy.content_address
    ):
        raise ValidationError("federation verification links are invalid")
    if (
        runtime.federation_address != value.content_address
        or runtime.policy_address != policy.content_address
        or runtime.verification_address != verification.content_address
    ):
        raise ValidationError("federation runtime links are invalid")
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
        value, policy=policy
    ).accepted:
        raise ValidationError("loaded federation verification failed")
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
        runtime, value, policy=policy, verification=verification
    ).accepted:
        raise ValidationError("loaded federation runtime verification failed")
    value.policy = policy
    value.verification = verification
    value.runtime = runtime
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_json(
    value: Federation,
) -> str:
    _require_verified(value)
    return canonical_json(value.to_dict())


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_csv(
    value: Federation,
) -> str:
    _require_verified(value)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "registry_id",
            "registry_address",
            "state",
            "accepted",
            "release_ready",
            "packet_count",
            "ready_packet_count",
            "held_packet_count",
            "blocked_packet_count",
            "accepted_packet_count",
            "release_ready_packet_count",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.entries:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_markdown(
    value: Federation,
) -> str:
    _require_verified(value)
    lines = [
        "# Observatory Packet Registry Federation",
        "",
        f"- Federation: `{value.federation_id}`",
        f"- State: `{value.state}`",
        f"- Registries: `{value.registry_count}`",
        f"- Packets: `{value.total_packet_count}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        f"- Address: `{value.content_address}`",
        "",
        "| # | Registry | State | Accepted | Ready | Packets | Address |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.registry_id}` | {item.state} | {str(item.accepted).lower()} | {str(item.release_ready).lower()} | {item.packet_count} | `{item.registry_address}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQuery:
    """Bounded query parameters for a federation handoff."""

    def __init__(
        self,
        *,
        resource: str = "summary",
        state: str | None = None,
        accepted: bool | None = None,
        release_ready: bool | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "federation query resource", 32)
        if self.resource not in {
            "summary",
            "registries",
            "packet-rollup",
            "verification",
            "policy-checks",
            "stages",
        }:
            raise ValidationError("federation query resource is invalid")
        self.state = None if state is None else _state(state, "federation query state")
        self.accepted = accepted
        if accepted is not None:
            _bool(accepted, "federation query accepted")
        self.release_ready = release_ready
        if release_ready is not None:
            _bool(release_ready, "federation query release-ready")
        self.text = None if text is None else _text(text, "federation query text", 256)
        _count(
            offset,
            "federation query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS,
        )
        _count(
            limit,
            "federation query limit",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS,
            positive=True,
        )
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


FederationQuery = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQuery


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQueryResult,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_QUERY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQueryResult:
    """Addressed bounded query page over federation resources."""

    def __init__(
        self,
        *,
        federation_address: str,
        query: FederationQuery,
        total: int,
        offset: int,
        limit: int,
        items: Sequence[Mapping[str, Any]],
        content_address: str,
    ) -> None:
        self.federation_address = federation_address
        self.query = query
        self.total = total
        self.offset = offset
        self.limit = limit
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "federation query federation address")
        if not isinstance(self.query, FederationQuery):
            raise ValidationError("federation query parameters are invalid")
        _count(
            self.total,
            "federation query total",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS,
        )
        _count(
            self.offset,
            "federation query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS,
        )
        _count(
            self.limit,
            "federation query limit",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS,
            positive=True,
        )
        if (
            len(self.items) > self.limit
            or self.offset > self.total
            or not all(_public(item) for item in self.items)
        ):
            raise ValidationError("federation query page is not bounded or public")
        _address(self.content_address, "federation query content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "federation_address": self.federation_address,
            "query": self.query.to_dict(),
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "items": list(self.items),
            "content_address": self.content_address,
        }


FederationQueryResult = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQueryResult


def _federation_query_matches(item: Mapping[str, Any], query: FederationQuery) -> bool:
    return (
        (query.state is None or item.get("state") == query.state)
        and (query.accepted is None or item.get("accepted") == query.accepted)
        and (query.release_ready is None or item.get("release_ready") == query.release_ready)
        and (query.text is None or query.text.casefold() in canonical_json(item).casefold())
    )


def _packet_rollup_rows(value: Federation) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "ordinal": item.ordinal,
            "registry_id": item.registry_id,
            "registry_address": item.registry_address,
            "state": item.state,
            "accepted": item.accepted,
            "release_ready": item.release_ready,
            "packet_count": item.packet_count,
            "ready_packet_count": item.ready_packet_count,
            "held_packet_count": item.held_packet_count,
            "blocked_packet_count": item.blocked_packet_count,
            "accepted_packet_count": item.accepted_packet_count,
            "release_ready_packet_count": item.release_ready_packet_count,
            "rollup_kind": "registry-packets",
        }
        for item in value.entries
    )


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
    value: Federation,
    query: FederationQuery | None = None,
    **kwargs: Any,
) -> FederationQueryResult:
    _require_verified(value)
    query = query or FederationQuery(**kwargs)
    verification = value.verification or _build_federation_verification(
        value, value.registries, value.policy
    )
    policy = value.policy
    runtime = value.runtime
    if query.resource == "summary":
        candidates = (value.summary(),)
    elif query.resource == "registries":
        candidates = tuple(item.to_dict() for item in value.entries)
    elif query.resource == "packet-rollup":
        candidates = _packet_rollup_rows(value)
    elif query.resource == "verification":
        candidates = (verification.summary(),)
    elif query.resource == "policy-checks":
        policy_checks = (
            runtime.policy_checks
            if runtime
            else _policy_checks(
                value,
                policy
                or default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(),
            )
        )
        candidates = tuple(item.to_dict() for item in policy_checks)
    else:
        candidates = tuple(item.to_dict() for item in (runtime.stages if runtime else ()))
    filtered = tuple(item for item in candidates if _federation_query_matches(item, query))
    provisional = FederationQueryResult(
        federation_address=value.content_address,
        query=query,
        total=len(filtered),
        offset=query.offset,
        limit=query.limit,
        items=filtered[query.offset : query.offset + query.limit],
        content_address="pending:query",
    )
    return FederationQueryResult(
        federation_address=provisional.federation_address,
        query=provisional.query,
        total=provisional.total,
        offset=provisional.offset,
        limit=provisional.limit,
        items=provisional.items,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
    value: FederationQueryResult,
) -> bool:
    if not isinstance(value, FederationQueryResult):
        return False
    try:
        return (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
                value
            )
            == value.content_address
        )
    except ValidationError:
        return False


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_json(
    value: FederationQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
        value
    ):
        raise ValidationError("federation query verification failed")
    return canonical_json(value.to_dict())


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_csv(
    value: FederationQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
        value
    ):
        raise ValidationError("federation query verification failed")
    output = io.StringIO(newline="")
    keys = sorted({key for item in value.items for key in item})
    writer = csv.DictWriter(output, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    if keys:
        writer.writeheader()
        writer.writerows(value.items)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_markdown(
    value: FederationQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
        value
    ):
        raise ValidationError("federation query verification failed")
    lines = [
        "# Observatory Packet Registry Federation Query",
        "",
        f"- Resource: `{value.query.resource}`",
        f"- Total: `{value.total}`",
        "",
    ]
    if value.items:
        keys = sorted({key for item in value.items for key in item})
        lines.append("| " + " | ".join(keys) + " |")
        lines.append("|" + "|".join("---" for _ in keys) + "|")
        lines.extend(
            "| " + " | ".join(str(item.get(key, "")) for key in keys) + " |" for item in value.items
        )
    else:
        lines.append("No matching rows.")
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_schema() -> (
    dict[str, Any]
):
    """Return the stable public schema contract for a federation handoff."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY,
        "exact_files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MANIFEST,
            *_FEDERATION_FILES.values(),
        ],
        "maximum_registries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_REGISTRIES,
        "maximum_packets": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_PACKETS,
        "maximum_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_CHECKS,
        "maximum_stages": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_STAGES,
        "fields": [
            "federation_id",
            "registry_count",
            "total_packet_count",
            "ready_registry_count",
            "held_registry_count",
            "blocked_registry_count",
            "accepted_registry_count",
            "release_ready_registry_count",
            "ready_packet_count",
            "held_packet_count",
            "blocked_packet_count",
            "accepted_packet_count",
            "release_ready_packet_count",
            "state",
            "accepted",
            "release_ready",
            "policy_address",
            "verification_address",
            "runtime_address",
            "entries",
            "content_address",
        ],
        "state_values": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationState
        ],
        "persistence": "canonical_utf8_json",
        "path_policy": "directory_locations_are_input_only",
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY,
        "deterministic_order": True,
        "unique_registry_addresses": True,
        "conserved_registry_and_packet_rollups": True,
        "independent_verification": True,
        "policy_governed_runtime": True,
        "exact_byte_persistence": True,
        "canonical_json_enforcement": True,
        "symlink_rejection": True,
        "bounded_queries": True,
        "json_csv_markdown_exports": True,
        "offline_reload": True,
        "source_payloads_required_for_reload": False,
        "supports_ready_held_blocked_and_empty_states": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY_BOUNDARY,
        "fields": [
            "policy_id",
            "minimum_registries",
            "maximum_registries",
            "maximum_packets",
            "maximum_blocked_registries",
            "maximum_held_registries",
            "require_all_registries_accepted",
            "require_all_release_ready",
            "allow_empty",
            "content_address",
        ],
        "bounded": True,
        "replaceable": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY_BOUNDARY,
        "minimum_and_maximum_registry_limits": True,
        "packet_ceiling": True,
        "held_and_blocked_budgets": True,
        "all_ready_requirement": True,
        "empty_input_policy": True,
        "content_addressed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "fields": [
            "federation_address",
            "policy_address",
            "check_count",
            "passed_count",
            "failed_count",
            "accepted",
            "checks",
            "content_address",
        ],
        "independent": True,
        "maximum_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_CHECKS,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "independent": True,
        "address_recomputation": True,
        "entry_order_and_uniqueness": True,
        "registry_and_packet_conservation": True,
        "policy_link_validation": True,
        "public_boundary_validation": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "fields": [
            "runtime_id",
            "federation_address",
            "policy_address",
            "verification_address",
            "state",
            "accepted",
            "release_ready",
            "stages",
            "policy_checks",
            "content_address",
        ],
        "stages": ["load", "verify", "policy", "project", "complete"],
        "states": ["ready", "held", "blocked"],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "ordered_stages": True,
        "replayable": True,
        "policy_checks": True,
        "held_state_preservation": True,
        "blocked_state_preservation": True,
        "release_projection": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "resources": [
            "summary",
            "registries",
            "packet-rollup",
            "verification",
            "policy-checks",
            "stages",
        ],
        "filters": ["state", "accepted", "release_ready", "text", "offset", "limit"],
        "maximum_items": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_MAX_QUERY_ITEMS,
        "formats": ["json", "csv", "markdown"],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION,
        "resources": [
            "summary",
            "registries",
            "packet-rollup",
            "verification",
            "policy-checks",
            "stages",
        ],
        "state_filter": True,
        "acceptance_filter": True,
        "readiness_filter": True,
        "text_filter": True,
        "pagination": True,
        "deterministic_addresses": True,
    }


__all__ = [
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_VERSION",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_BOUNDARY",
    "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_POLICY_BOUNDARY",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationState",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStageState",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationPolicy",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationEntry",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationCheck",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationVerification",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationStage",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationRuntime",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederation",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQuery",
    "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketRegistryFederationQueryResult",
    "Policy",
    "FederationEntry",
    "FederationCheck",
    "FederationVerification",
    "FederationStage",
    "FederationRuntime",
    "Federation",
    "FederationQuery",
    "FederationQueryResult",
    "default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy",
    "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation",
    "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories",
    "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation",
    "run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime",
    "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime",
    "write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation",
    "load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation",
    "federation_policy_from_mapping",
    "federation_entry_from_mapping",
    "federation_check_from_mapping",
    "federation_verification_from_mapping",
    "federation_stage_from_mapping",
    "federation_runtime_from_mapping",
    "federation_from_mapping",
    "query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation",
    "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query",
    "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_json",
    "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_csv",
    "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_markdown",
    "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_json",
    "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_csv",
    "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_markdown",
]

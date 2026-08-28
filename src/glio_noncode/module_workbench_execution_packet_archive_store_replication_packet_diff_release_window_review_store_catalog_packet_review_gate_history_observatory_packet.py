"""Portable exact-byte handoff for longitudinal packet-review observatories.

This boundary packages a verified observatory, its independent verification,
the explicit release policy, and the policy runtime into one path-free public
handoff.  The packet is deliberately a transport boundary rather than a
scientific conclusion: a structurally valid held or blocked runtime remains
valid evidence and is never silently promoted to ready.
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
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_from_directories,
    observatory_from_mapping,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
    default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy,
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime,
    runtime_from_mapping,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_ARTIFACT_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
    + "-artifact"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_OBSERVATORY = "observatory.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION = "verification.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_POLICY = "policy.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_RUNTIME = "runtime.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_ARTIFACTS = 4
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_CHECKS = 24
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_QUERY_ITEMS = 256

_ARTIFACT_FILES = {
    "observatory": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_OBSERVATORY,
    "verification": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION,
    "policy": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_POLICY,
    "runtime": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_RUNTIME,
}

Observatory = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory
ObservatoryCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck
Policy = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy
PolicyCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck
RuntimeReport = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeReport


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifactKind(
    StrEnum
):
    OBSERVATORY = "observatory"
    VERIFICATION = "verification"
    POLICY = "policy"
    RUNTIME = "runtime"


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


def _kind(value: Any, field: str) -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifactKind
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _packet_state(value: Any, field: str = "packet state") -> str:
    value = _text(value, field, 32)
    if value not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketState
    }:
        raise ValidationError(f"{field} is invalid")
    return value


def _artifact_byte_address(kind: str, raw: bytes) -> str:
    return hash_bytes(
        raw,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_ARTIFACT_PREFIX
        + "-"
        + kind
        + "-bytes",
    )


def _artifact_content_address(kind: str, raw: bytes) -> str:
    return hash_bytes(
        raw,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_ARTIFACT_PREFIX
        + "-"
        + kind
        + "-content",
    )


def _packet_address_body(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_address", None)
    # The verification receipt points back to this address.  Excluding its
    # link from the address body keeps the packet address acyclic while the
    # independent receipt still verifies the link explicitly.
    body.pop("verification_address", None)
    body.pop("artifacts", None)
    return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_artifact(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_ARTIFACT_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact:
    """One exact-byte component of the observatory packet."""

    def __init__(
        self,
        *,
        ordinal: int,
        kind: str,
        file_name: str,
        byte_count: int,
        byte_address: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.file_name = file_name
        self.byte_count = byte_count
        self.byte_address = byte_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "packet artifact ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_ARTIFACTS
            - 1,
        )
        kind = _kind(self.kind, "packet artifact kind")
        if self.file_name != _ARTIFACT_FILES[kind]:
            raise ValidationError("packet artifact file name is not canonical")
        _count(self.byte_count, "packet artifact byte count", 16_777_216, positive=True)
        _address(self.byte_address, "packet artifact byte address")
        _address(self.content_address, "packet artifact content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet artifact crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "file_name": self.file_name,
            "byte_count": self.byte_count,
            "byte_address": self.byte_address,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryPacketCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryPacketCheck:
    """A packet verification check with expected and observed public values."""

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
            "packet check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "packet check kind", 128)
        _bool(self.passed, "packet check passed")
        _json_value(self.expected, "packet check expected")
        _json_value(self.observed, "packet check observed")
        _text(self.detail, "packet check detail")
        _address(self.content_address, "packet check content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet check crosses the public boundary")

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


PacketCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryPacketCheck


def _packet_check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> PacketCheck:
    body = {
        "ordinal": ordinal,
        "kind": _text(kind, "packet check kind", 128),
        "passed": bool(passed),
        "expected": _json_value(expected, "packet check expected"),
        "observed": _json_value(observed, "packet check observed"),
        "detail": _text(detail, "packet check detail"),
    }
    provisional = PacketCheck(**body, content_address="pending:check")
    return PacketCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_check(
            provisional
        ),
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketVerification:
    """Independent verification receipt for packet links and boundaries."""

    def __init__(
        self,
        *,
        packet_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: Sequence[PacketCheck],
        content_address: str,
    ) -> None:
        self.packet_address = packet_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.packet_address, "packet verification packet address")
        _count(
            self.check_count,
            "packet verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_CHECKS,
            positive=True,
        )
        _count(self.passed_count, "packet verification passed count", self.check_count)
        _count(self.failed_count, "packet verification failed count", self.check_count)
        if (
            self.check_count != len(self.checks)
            or self.passed_count + self.failed_count != self.check_count
        ):
            raise ValidationError("packet verification counts are not conserved")
        _bool(self.accepted, "packet verification accepted")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, PacketCheck) or check.ordinal != ordinal:
                raise ValidationError("packet verification checks are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("packet verification check address is invalid")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("packet verification acceptance is not conserved")
        _address(self.content_address, "packet verification content address")
        if not _public(self.to_dict()):
            raise ValidationError("packet verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "packet_address": self.packet_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [item.to_dict() for item in self.checks]}


PacketVerification = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketVerification


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacket,
) -> str:
    return content_hash(
        _packet_address_body(value.to_dict()),
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacket:
    """Portable packet metadata with optional hydrated public components."""

    def __init__(
        self,
        *,
        packet_id: str,
        version: str,
        boundary: str,
        observatory_address: str,
        verification_address: str,
        policy_address: str,
        runtime_address: str,
        state: str,
        release_ready: bool,
        accepted: bool,
        artifact_count: int,
        artifacts: Sequence[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact
        ],
        content_address: str,
    ) -> None:
        self.packet_id = packet_id
        self.version = version
        self.boundary = boundary
        self.observatory_address = observatory_address
        self.verification_address = verification_address
        self.policy_address = policy_address
        self.runtime_address = runtime_address
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.artifact_count = artifact_count
        self.artifacts = tuple(artifacts)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.packet_id, "packet ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION
        ):
            raise ValidationError("packet version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_BOUNDARY
        ):
            raise ValidationError("packet boundary is invalid")
        for value, field in (
            (self.observatory_address, "observatory address"),
            (self.verification_address, "verification address"),
            (self.policy_address, "policy address"),
            (self.runtime_address, "runtime address"),
        ):
            _address(value, field)
        _packet_state(self.state)
        _bool(self.release_ready, "packet release-ready")
        _bool(self.accepted, "packet accepted")
        _count(
            self.artifact_count,
            "packet artifact count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_ARTIFACTS,
            positive=True,
        )
        if self.artifact_count != len(self.artifacts) or self.artifact_count != 4:
            raise ValidationError("packet artifact count is not conserved")
        for ordinal, artifact in enumerate(self.artifacts):
            if (
                not isinstance(
                    artifact,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact,
                )
                or artifact.ordinal != ordinal
            ):
                raise ValidationError("packet artifacts are not contiguous")
        _address(self.content_address, "packet content address")
        if self.release_ready and self.state != "ready":
            raise ValidationError("ready packet projection is invalid")
        if not _public(self.to_dict()):
            raise ValidationError("packet crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "observatory_address": self.observatory_address,
            "verification_address": self.verification_address,
            "policy_address": self.policy_address,
            "runtime_address": self.runtime_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "artifact_count": self.artifact_count,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"artifacts": [item.to_dict() for item in self.artifacts]}


Packet = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacket


def _payloads(
    observatory: Observatory,
    verification: PacketVerification,
    policy: Policy,
    runtime_report: RuntimeReport,
) -> dict[str, Any]:
    return {
        "observatory": observatory.to_dict(),
        "verification": verification.to_dict(),
        "policy": policy.to_dict(),
        "runtime": runtime_report.to_dict(),
    }


def _build_artifact(
    ordinal: int, kind: str, payload: Any, content_address: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact:
    raw = canonical_bytes(payload)
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact(
        ordinal=ordinal,
        kind=kind,
        file_name=_ARTIFACT_FILES[kind],
        byte_count=len(raw),
        byte_address=_artifact_byte_address(kind, raw),
        content_address=content_address,
    )


def _placeholder_verification_address(
    packet_id: str, observatory_address: str, policy_address: str, runtime_address: str
) -> str:
    return content_hash(
        {
            "packet_id": packet_id,
            "observatory_address": observatory_address,
            "policy_address": policy_address,
            "runtime_address": runtime_address,
        },
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION_PREFIX
        + "-placeholder",
    )


def _packet_metadata(
    packet_id: str,
    observatory: Observatory,
    verification_address: str,
    policy: Policy,
    runtime_report: RuntimeReport,
    artifacts: Sequence[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact
    ],
    *,
    content_address: str,
) -> Packet:
    return Packet(
        packet_id=_text(packet_id, "packet ID", 256),
        version=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION,
        boundary=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_BOUNDARY,
        observatory_address=observatory.content_address,
        verification_address=verification_address,
        policy_address=policy.content_address,
        runtime_address=runtime_report.content_address,
        state=runtime_report.state,
        release_ready=runtime_report.release_ready,
        accepted=True,
        artifact_count=4,
        artifacts=artifacts,
        content_address=content_address,
    )


def _build_packet_verification(
    value: Packet,
    observatory: Observatory | None,
    policy: Policy | None,
    runtime_report: RuntimeReport | None,
) -> PacketVerification:
    checks: list[PacketCheck] = []

    def add(kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> None:
        checks.append(_packet_check(len(checks), kind, passed, expected, observed, detail))

    add(
        "packet-address",
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            value
        )
        == value.content_address,
        "recomputed packet address",
        value.content_address,
        "packet metadata address is conserved",
    )
    add(
        "artifact-count",
        value.artifact_count == 4 and len(value.artifacts) == 4,
        4,
        value.artifact_count,
        "packet contains four exact public component artifacts",
    )
    add(
        "artifact-order",
        tuple(item.ordinal for item in value.artifacts) == tuple(range(4)),
        [0, 1, 2, 3],
        [item.ordinal for item in value.artifacts],
        "artifact ordinals are contiguous",
    )
    add(
        "artifact-files",
        tuple(item.file_name for item in value.artifacts)
        == tuple(
            _ARTIFACT_FILES[item] for item in ("observatory", "verification", "policy", "runtime")
        ),
        list(_ARTIFACT_FILES.values()),
        [item.file_name for item in value.artifacts],
        "artifact file names are canonical",
    )
    add(
        "observatory-link",
        observatory is not None and observatory.content_address == value.observatory_address,
        value.observatory_address,
        None if observatory is None else observatory.content_address,
        "observatory address is linked",
    )
    observatory_verification = (
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            observatory
        )
        if isinstance(observatory, Observatory)
        else None
    )
    add(
        "observatory-verification",
        bool(observatory_verification and observatory_verification.accepted),
        True,
        None if observatory_verification is None else observatory_verification.accepted,
        "nested observatory independently verifies",
    )
    add(
        "policy-link",
        policy is not None and policy.content_address == value.policy_address,
        value.policy_address,
        None if policy is None else policy.content_address,
        "policy address is linked",
    )
    add(
        "runtime-link",
        runtime_report is not None and runtime_report.content_address == value.runtime_address,
        value.runtime_address,
        None if runtime_report is None else runtime_report.content_address,
        "runtime address is linked",
    )
    add(
        "runtime-observatory-link",
        bool(runtime_report and runtime_report.observatory_address == value.observatory_address),
        value.observatory_address,
        None if runtime_report is None else runtime_report.observatory_address,
        "runtime retains the observatory address",
    )
    add(
        "runtime-policy-link",
        bool(runtime_report and runtime_report.policy_address == value.policy_address),
        value.policy_address,
        None if runtime_report is None else runtime_report.policy_address,
        "runtime retains the policy address",
    )
    replayed_runtime = (
        run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
            observatory,
            policy=policy,
            runtime_id=runtime_report.runtime_id,
        )
        if isinstance(observatory, Observatory)
        and isinstance(policy, Policy)
        and isinstance(runtime_report, RuntimeReport)
        else None
    )
    add(
        "runtime-replay",
        bool(replayed_runtime and replayed_runtime.to_dict() == runtime_report.to_dict()),
        True,
        None
        if replayed_runtime is None
        else replayed_runtime.to_dict() == runtime_report.to_dict(),
        "runtime policy evaluation replays deterministically",
    )
    add(
        "state-projection",
        bool(runtime_report and runtime_report.state == value.state),
        value.state,
        None if runtime_report is None else runtime_report.state,
        "packet state matches runtime state",
    )
    add(
        "release-projection",
        bool(runtime_report and runtime_report.release_ready == value.release_ready),
        value.release_ready,
        None if runtime_report is None else runtime_report.release_ready,
        "packet readiness matches runtime readiness",
    )
    add(
        "public-boundary",
        _public(value.to_dict())
        and _public(None if observatory is None else observatory.to_dict())
        and _public(None if policy is None else policy.to_dict())
        and _public(None if runtime_report is None else runtime_report.to_dict()),
        True,
        _public(value.to_dict()),
        "packet projections contain no forbidden public keys",
    )
    body = {
        "packet_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = PacketVerification(**body, content_address="pending:verification")
    return PacketVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_verification(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
    observatory: Observatory,
    *,
    policy: Policy | None = None,
    runtime_report: RuntimeReport | None = None,
    packet_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory-packet",
) -> Packet:
    """Build a packet from a verified observatory and explicit policy runtime."""

    if not isinstance(observatory, Observatory):
        raise ValidationError("observatory packet requires a typed observatory")
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        observatory
    ).accepted:
        raise ValidationError("observatory packet requires an accepted observatory")
    policy = (
        policy
        or default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy()
    )
    if not isinstance(policy, Policy):
        raise ValidationError("observatory packet requires a typed policy")
    runtime_report = (
        runtime_report
        or run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
            observatory, policy=policy
        )
    )
    if not isinstance(runtime_report, RuntimeReport):
        raise ValidationError("observatory packet requires a typed runtime report")
    if (
        runtime_report.observatory_address != observatory.content_address
        or runtime_report.policy_address != policy.content_address
    ):
        raise ValidationError("observatory packet component links do not match")
    placeholder = _placeholder_verification_address(
        packet_id,
        observatory.content_address,
        policy.content_address,
        runtime_report.content_address,
    )
    placeholder_artifacts = (
        _build_artifact(0, "observatory", observatory.to_dict(), observatory.content_address),
        _build_artifact(1, "verification", {"packet_address": placeholder}, placeholder),
        _build_artifact(
            2,
            "policy",
            policy.to_dict(),
            _artifact_content_address("policy", canonical_bytes(policy.to_dict())),
        ),
        _build_artifact(
            3,
            "runtime",
            runtime_report.to_dict(),
            _artifact_content_address("runtime", canonical_bytes(runtime_report.to_dict())),
        ),
    )
    provisional = _packet_metadata(
        packet_id,
        observatory,
        placeholder,
        policy,
        runtime_report,
        placeholder_artifacts,
        content_address="pending:packet",
    )
    packet_address = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
        provisional
    )
    address_packet = _packet_metadata(
        packet_id,
        observatory,
        placeholder,
        policy,
        runtime_report,
        placeholder_artifacts,
        content_address=packet_address,
    )
    verification = _build_packet_verification(address_packet, observatory, policy, runtime_report)
    final_artifacts = (
        _build_artifact(0, "observatory", observatory.to_dict(), observatory.content_address),
        _build_artifact(1, "verification", verification.to_dict(), verification.content_address),
        _build_artifact(
            2,
            "policy",
            policy.to_dict(),
            _artifact_content_address("policy", canonical_bytes(policy.to_dict())),
        ),
        _build_artifact(
            3,
            "runtime",
            runtime_report.to_dict(),
            _artifact_content_address("runtime", canonical_bytes(runtime_report.to_dict())),
        ),
    )
    value = _packet_metadata(
        packet_id,
        observatory,
        verification.content_address,
        policy,
        runtime_report,
        final_artifacts,
        content_address=packet_address,
    )
    value.observatory = observatory
    value.verification = verification
    value.policy = policy
    value.runtime = runtime_report
    final_verification = _build_packet_verification(value, observatory, policy, runtime_report)
    if final_verification.content_address != verification.content_address:
        raise ValidationError("packet verification address is not deterministic")
    value.verification = final_verification
    return value


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_observatory_directory(
    observatory_directory: str | Path,
    *,
    runtime_directory: str | Path | None = None,
    policy: Policy | None = None,
    packet_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory-packet",
) -> Packet:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory import (
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory,
    )

    observatory = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        observatory_directory
    )
    runtime_report = None
    if runtime_directory is not None:
        from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime import (
            load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime,
        )

        runtime_report = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            runtime_directory
        )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
        observatory, policy=policy, runtime_report=runtime_report, packet_id=packet_id
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
    history_directories: Sequence[str | Path],
    *,
    observatory_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory",
    observation_ids: Sequence[str] | None = None,
    policy: Policy | None = None,
    packet_id: str = "glio-noncode-review-store-catalog-packet-review-gate-history-observatory-packet",
) -> Packet:
    observatory = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_from_directories(
        history_directories, observatory_id=observatory_id, observation_ids=observation_ids
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
        observatory, policy=policy, packet_id=packet_id
    )


def _artifact_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact:
    try:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifact(
            **dict(value)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("packet artifact mapping is invalid") from exc


def _check_from_mapping(value: Mapping[str, Any]) -> PacketCheck:
    try:
        return PacketCheck(**dict(value))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("packet check mapping is invalid") from exc


def packet_verification_from_mapping(value: Mapping[str, Any]) -> PacketVerification:
    if not isinstance(value, Mapping):
        raise ValidationError("packet verification mapping must be an object")
    body = dict(value)
    try:
        checks = tuple(_check_from_mapping(item) for item in body.pop("checks"))
        return PacketVerification(**(body | {"checks": checks}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("packet verification mapping is invalid") from exc


def packet_policy_from_mapping(value: Mapping[str, Any]) -> Policy:
    if not isinstance(value, Mapping):
        raise ValidationError("packet policy mapping must be an object")
    try:
        return Policy(**dict(value))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("packet policy mapping is invalid") from exc


def packet_from_mapping(value: Mapping[str, Any]) -> Packet:
    if not isinstance(value, Mapping):
        raise ValidationError("packet mapping must be an object")
    body = dict(value)
    try:
        artifacts = tuple(_artifact_from_mapping(item) for item in body.pop("artifacts"))
        return Packet(**(body | {"artifacts": artifacts}))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("packet mapping is invalid") from exc


def _component(value: Any, field: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
    value: Packet,
) -> PacketVerification:
    """Recompute all packet checks without trusting the embedded receipt."""

    if not isinstance(value, Packet):
        raise ValidationError("packet verification requires a typed packet")
    observatory = getattr(value, "observatory", None)
    policy = getattr(value, "policy", None)
    runtime_report = getattr(value, "runtime", None)
    return _build_packet_verification(
        value,
        observatory if isinstance(observatory, Observatory) else None,
        policy if isinstance(policy, Policy) else None,
        runtime_report if isinstance(runtime_report, RuntimeReport) else None,
    )


def _require_hydrated(
    value: Packet,
) -> tuple[Observatory, PacketVerification, Policy, RuntimeReport]:
    components = tuple(
        getattr(value, name, None) for name in ("observatory", "verification", "policy", "runtime")
    )
    if not all(isinstance(item, object) for item in components):
        raise ValidationError("packet components are not hydrated")
    observatory, verification, policy, runtime_report = components
    if (
        not isinstance(observatory, Observatory)
        or not isinstance(verification, PacketVerification)
        or not isinstance(policy, Policy)
        or not isinstance(runtime_report, RuntimeReport)
    ):
        raise ValidationError("packet components have invalid types")
    return observatory, verification, policy, runtime_report


def _require_verified(
    value: Packet,
) -> tuple[Observatory, PacketVerification, Policy, RuntimeReport]:
    components = _require_hydrated(value)
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
        value
    )
    if not verification.accepted:
        raise ValidationError("packet verification failed")
    embedded = components[1]
    if embedded.to_dict() != verification.to_dict():
        raise ValidationError("embedded packet verification is stale")
    return components


def _packet_payloads(value: Packet) -> dict[str, bytes]:
    observatory, verification, policy, runtime_report = _require_hydrated(value)
    return {
        "observatory": canonical_bytes(observatory.to_dict()),
        "verification": canonical_bytes(verification.to_dict()),
        "policy": canonical_bytes(policy.to_dict()),
        "runtime": canonical_bytes(runtime_report.to_dict()),
    }


def _manifest(value: Packet, payloads: Mapping[str, bytes]) -> dict[str, Any]:
    for artifact in value.artifacts:
        raw = payloads[artifact.kind]
        if artifact.byte_count != len(raw) or artifact.byte_address != _artifact_byte_address(
            artifact.kind, raw
        ):
            raise ValidationError(f"packet {artifact.kind} byte receipt is stale")
        expected_content = (
            value.verification_address
            if artifact.kind == "verification"
            else _artifact_content_address(artifact.kind, raw)
            if artifact.kind in {"policy", "runtime"}
            else value.observatory_address
        )
        if artifact.content_address != expected_content:
            raise ValidationError(f"packet {artifact.kind} content receipt is stale")
    body = value.to_dict() | {
        "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION,
        "artifact_files": [item.to_dict() for item in value.artifacts],
    }
    return body | {
        "manifest_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
            + "-manifest",
        )
    }


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
    value: Packet,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically publish exactly manifest plus four canonical JSON files."""

    _require_verified(value)
    payloads = _packet_payloads(value)
    manifest = _manifest(value, payloads)
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("packet destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        files = {
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MANIFEST: canonical_bytes(
                manifest
            )
        }
        files.update({_ARTIFACT_FILES[kind]: raw for kind, raw in payloads.items()})
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("packet destination is not a regular directory")
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
        raise ValidationError(f"{field} is not valid canonical JSON") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise ValidationError(f"{field} must be a canonical JSON object")
    return value


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
    directory: str | Path,
) -> Packet:
    """Load, rehydrate, and independently verify an exact packet directory."""

    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("observatory packet directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MANIFEST,
        *_ARTIFACT_FILES.values(),
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("observatory packet files do not match the published set")
    manifest = _read_json(
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MANIFEST,
        "observatory packet manifest",
    )
    expected_keys = set(
        Packet(
            packet_id="x",
            version=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION,
            boundary=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_BOUNDARY,
            observatory_address="x:x",
            verification_address="x:x",
            policy_address="x:x",
            runtime_address="x:x",
            state="ready",
            release_ready=True,
            accepted=True,
            artifact_count=4,
            artifacts=tuple(
                _build_artifact(index, kind, {"x": index}, "x:x")
                for index, kind in enumerate(("observatory", "verification", "policy", "runtime"))
            ),
            content_address="x:x",
        ).to_dict()
    ) | {"manifest_version", "artifact_files", "manifest_address"}
    if (
        set(manifest) != expected_keys
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION
        or manifest.get("artifact_files") != manifest.get("artifacts")
    ):
        raise ValidationError("observatory packet manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest["manifest_address"] != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
        + "-manifest",
    ):
        raise ValidationError("observatory packet manifest address mismatch")
    packet = packet_from_mapping(
        {
            key: manifest[key]
            for key in (
                "packet_id",
                "version",
                "boundary",
                "observatory_address",
                "verification_address",
                "policy_address",
                "runtime_address",
                "state",
                "release_ready",
                "accepted",
                "artifact_count",
                "artifacts",
                "content_address",
            )
        }
    )
    payload_maps = {
        kind: _read_json(directory / file_name, f"packet {kind}")
        for kind, file_name in _ARTIFACT_FILES.items()
    }
    payload_raw = {
        kind: (directory / file_name).read_bytes() for kind, file_name in _ARTIFACT_FILES.items()
    }
    for artifact in packet.artifacts:
        if (
            payload_raw[artifact.kind] != canonical_bytes(payload_maps[artifact.kind])
            or artifact.byte_count != len(payload_raw[artifact.kind])
            or artifact.byte_address
            != _artifact_byte_address(artifact.kind, payload_raw[artifact.kind])
        ):
            raise ValidationError(f"packet {artifact.kind} bytes do not match manifest")
    observatory = observatory_from_mapping(payload_maps["observatory"])
    verification = packet_verification_from_mapping(payload_maps["verification"])
    policy = packet_policy_from_mapping(payload_maps["policy"])
    runtime_report = runtime_from_mapping(payload_maps["runtime"])
    packet.observatory = observatory
    packet.verification = verification
    packet.policy = policy
    packet.runtime = runtime_report
    if (
        verification.content_address != packet.verification_address
        or policy.content_address != packet.policy_address
        or runtime_report.content_address != packet.runtime_address
        or observatory.content_address != packet.observatory_address
    ):
        raise ValidationError("observatory packet nested addresses do not match")
    _require_verified(packet)
    return packet


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_json(
    value: Packet,
) -> str:
    _require_verified(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_csv(
    value: Packet,
) -> str:
    _require_verified(value)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "kind",
            "file_name",
            "byte_count",
            "byte_address",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.artifacts:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_markdown(
    value: Packet,
) -> str:
    _require_verified(value)
    lines = [
        "# Packet-review gate history observatory packet",
        "",
        f"- Packet: `{value.packet_id}`",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        f"- Address: `{value.content_address}`",
        "",
        "| # | Kind | File | Bytes | Content address |",
        "|---:|---|---|---:|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.kind} | `{item.file_name}` | {item.byte_count} | `{item.content_address}` |"
        for item in value.artifacts
    )
    return "\n".join(lines) + "\n"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketQuery:
    """Bounded packet query parameters."""

    def __init__(
        self,
        *,
        resource: str = "summary",
        kind: str | None = None,
        state: str | None = None,
        passed: bool | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "packet query resource", 32)
        if self.resource not in {
            "summary",
            "artifacts",
            "verification",
            "observations",
            "transitions",
            "stages",
            "policy-checks",
        }:
            raise ValidationError("packet query resource is invalid")
        self.kind = None if kind is None else _kind(kind, "packet query kind")
        self.state = None if state is None else _packet_state(state, "packet query state")
        self.passed = passed
        if passed is not None:
            _bool(passed, "packet query passed")
        self.text = None if text is None else _text(text, "packet query text", 256)
        _count(
            offset,
            "packet query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_QUERY_ITEMS,
        )
        _count(limit, "packet query limit", 512, positive=True)
        self.offset = offset
        self.limit = limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "kind": self.kind,
            "state": self.state,
            "passed": self.passed,
            "text": self.text,
            "offset": self.offset,
            "limit": self.limit,
        }


PacketQuery = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketQuery


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryPacketQueryResult,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_QUERY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryPacketQueryResult:
    """Addressed bounded query page over packet and nested component rows."""

    def __init__(
        self,
        *,
        packet_address: str,
        query: PacketQuery,
        total: int,
        offset: int,
        limit: int,
        items: Sequence[Mapping[str, Any]],
        content_address: str,
    ) -> None:
        self.packet_address = packet_address
        self.query = query
        self.total = total
        self.offset = offset
        self.limit = limit
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.packet_address, "packet query packet address")
        if not isinstance(self.query, PacketQuery):
            raise ValidationError("packet query parameters are invalid")
        _count(
            self.total,
            "packet query total",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_QUERY_ITEMS,
        )
        _count(
            self.offset,
            "packet query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_QUERY_ITEMS,
        )
        _count(self.limit, "packet query limit", 512, positive=True)
        if (
            len(self.items) > self.limit
            or self.offset > self.total
            or not all(_public(item) for item in self.items)
        ):
            raise ValidationError("packet query page is not bounded or public")
        _address(self.content_address, "packet query content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_address": self.packet_address,
            "query": self.query.to_dict(),
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "items": list(self.items),
            "content_address": self.content_address,
        }


PacketQueryResult = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryPacketQueryResult


def _query_matches(item: Mapping[str, Any], query: PacketQuery) -> bool:
    return (
        (query.kind is None or item.get("kind") == query.kind)
        and (query.state is None or item.get("state") == query.state)
        and (query.passed is None or item.get("passed") == query.passed)
        and (query.text is None or query.text.casefold() in canonical_json(item).casefold())
    )


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
    value: Packet, query: PacketQuery | None = None, **kwargs: Any
) -> PacketQueryResult:
    _require_verified(value)
    query = query or PacketQuery(**kwargs)
    observatory = value.observatory
    verification = value.verification
    runtime_report = value.runtime
    if query.resource == "summary":
        candidates = (value.summary(),)
    elif query.resource == "artifacts":
        candidates = tuple(item.to_dict() for item in value.artifacts)
    elif query.resource == "verification":
        candidates = (verification.summary(),)
    elif query.resource == "observations":
        candidates = tuple(item.to_dict() for item in observatory.observations)
    elif query.resource == "transitions":
        candidates = tuple(item.to_dict() for item in observatory.transitions)
    elif query.resource == "stages":
        candidates = tuple(item.to_dict() for item in runtime_report.stages)
    else:
        candidates = tuple(item.to_dict() for item in runtime_report.policy_evaluation.checks)
    filtered = tuple(item for item in candidates if _query_matches(item, query))
    provisional = PacketQueryResult(
        packet_address=value.content_address,
        query=query,
        total=len(filtered),
        offset=query.offset,
        limit=query.limit,
        items=filtered[query.offset : query.offset + query.limit],
        content_address="pending:query",
    )
    return PacketQueryResult(
        packet_address=provisional.packet_address,
        query=provisional.query,
        total=provisional.total,
        offset=provisional.offset,
        limit=provisional.limit,
        items=provisional.items,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
    value: PacketQueryResult,
) -> bool:
    if not isinstance(value, PacketQueryResult):
        raise ValidationError("packet query verification requires a typed result")
    return (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
            value
        )
        == value.content_address
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_json(
    value: PacketQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
        value
    ):
        raise ValidationError("packet query address is invalid")
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_csv(
    value: PacketQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
        value
    ):
        raise ValidationError("packet query address is invalid")
    output = io.StringIO(newline="")
    fields = (
        sorted({key for item in value.items for key in item})
        if value.items
        else ("ordinal", "kind", "content_address")
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        writer.writerow(item)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_markdown(
    value: PacketQueryResult,
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
        value
    ):
        raise ValidationError("packet query address is invalid")
    fields = (
        sorted({key for item in value.items for key in item})
        if value.items
        else ["content_address"]
    )
    lines = [
        "# Packet-review gate history observatory packet query",
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


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_BOUNDARY,
        "exact_files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MANIFEST,
            *_ARTIFACT_FILES.values(),
        ],
        "artifact_kinds": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketArtifactKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryPacketState
        ],
        "resources": [
            "summary",
            "artifacts",
            "verification",
            "observations",
            "transitions",
            "stages",
            "policy-checks",
        ],
        "bounded": True,
        "atomic_write": True,
        "canonical_json": True,
        "rehydrates_components": True,
        "fail_closed": True,
        "path_free": True,
        "identity_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERSION,
        "operations": [
            "build",
            "build-from-observatory-directory",
            "build-from-history-directories",
            "verify",
            "write",
            "load",
            "query",
            "json",
            "csv",
            "markdown",
        ],
        "component_count": 4,
        "exact_file_count": 5,
        "independent_verification": True,
        "preserves_held_and_blocked": True,
        "atomic_write": True,
        "canonical_json": True,
        "bounded": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_QUERY_PREFIX
        + "-v1",
        "resources": [
            "summary",
            "artifacts",
            "verification",
            "observations",
            "transitions",
            "stages",
            "policy-checks",
        ],
        "filters": ["kind", "state", "passed", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_QUERY_PREFIX
        + "-v1",
        "resources": [
            "summary",
            "artifacts",
            "verification",
            "observations",
            "transitions",
            "stages",
            "policy-checks",
        ],
        "filters": ["kind", "state", "passed", "text", "offset", "limit"],
        "bounded": True,
        "deterministic": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_verification_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION_PREFIX
        + "-v1",
        "check_fields": ["kind", "passed", "expected", "observed", "detail"],
        "maximum_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_MAX_CHECKS,
        "independent": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_verification_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_VERIFICATION_PREFIX
        + "-v1",
        "operations": ["verify", "json", "csv", "markdown"],
        "recomputes_packet_address": True,
        "recomputes_component_links": True,
        "recomputes_nested_observatory": True,
        "identity_free": True,
    }

"""Portable exact-byte packets for catalog release evidence.

The catalog, runtime, federation, independent assurance, and release gate are
useful independently, but a release boundary also needs one portable handoff.
This module packages those five addressed projections into an exact six-file
directory with a manifest.  It never copies source paths or private metadata;
the loader rehydrates the public objects and verifies every byte and link
before returning a packet.
"""

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
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ARTIFACT_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX
    + "-artifact"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_CATALOG = "catalog.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_RUNTIME = "runtime.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_FEDERATION = "federation.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ASSURANCE = "assurance.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_GATE = "gate.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MAX_ARTIFACTS = 5
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MAX_CHECKS = 32
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX
    + "-verification"
)


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind(
    StrEnum
):
    CATALOG = "catalog"
    RUNTIME = "runtime"
    FEDERATION = "federation"
    ASSURANCE = "assurance"
    GATE = "gate"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheckState(
    StrEnum
):
    PASSED = "passed"
    FAILED = "failed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_artifact(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ARTIFACT_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact:
    """One exact-byte public artifact in a catalog packet."""

    def __init__(
        self,
        ordinal: int,
        kind: str,
        file_name: str,
        byte_count: int,
        byte_address: str,
        content_address: str,
    ):
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
            "catalog packet artifact ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MAX_ARTIFACTS
            - 1,
        )
        if self.kind not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
        }:
            raise ValidationError("catalog packet artifact kind is invalid")
        _text(self.file_name, "catalog packet artifact file name", 128)
        if "/" in self.file_name or "\\" in self.file_name or self.file_name in {".", ".."}:
            raise ValidationError("catalog packet artifact file name must be a leaf")
        _count(self.byte_count, "catalog packet artifact byte count", 50_000_000)
        _address(self.byte_address, "catalog packet artifact byte address")
        _address(self.content_address, "catalog packet artifact content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog packet artifact crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "file_name": self.file_name,
            "byte_count": self.byte_count,
            "byte_address": self.byte_address,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERIFICATION_PREFIX
        + "-check",
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheck:
    """One manifest or link verification result."""

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
    ):
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
            "catalog packet check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "catalog packet check kind", 256)
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheckState
        }:
            raise ValidationError("catalog packet check state is invalid")
        _bool(self.passed, "catalog packet check passed flag")
        _text(self.detail, "catalog packet check detail")
        _address(self.content_address, "catalog packet check address")
        if self.state != ("passed" if self.passed else "failed"):
            raise ValidationError("catalog packet check state does not conserve")
        if not _public(self.to_dict()):
            raise ValidationError("catalog packet check crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketVerification:
    """Addressed verification receipt for exact packet transport."""

    def __init__(
        self,
        packet_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheck,
            ...,
        ],
        content_address: str,
    ):
        self.packet_address = packet_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.packet_address, "catalog packet verification packet address")
        _count(
            self.check_count,
            "catalog packet verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError(
                "catalog packet verification checks must be non-empty and conserved"
            )
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("catalog packet verification check address mismatch")
        if self.passed_count != sum(
            check.passed for check in self.checks
        ) or self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("catalog packet verification counts do not conserve")
        _count(self.passed_count, "catalog packet verification passed count", self.check_count)
        _count(self.failed_count, "catalog packet verification failed count", self.check_count)
        _bool(self.accepted, "catalog packet verification accepted flag")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("catalog packet verification acceptance does not conserve")
        _address(self.content_address, "catalog packet verification address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog packet verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "packet_address": self.packet_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [check.to_dict() for check in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket:
    """Portable catalog release handoff and its exact artifact manifest."""

    def __init__(
        self,
        packet_id: str,
        version: str,
        boundary: str,
        catalog_id: str,
        catalog_address: str,
        runtime_address: str,
        federation_address: str,
        assurance_address: str,
        gate_address: str,
        artifact_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        artifacts: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact,
            ...,
        ],
        content_address: str,
    ):
        self.packet_id = packet_id
        self.version = version
        self.boundary = boundary
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.runtime_address = runtime_address
        self.federation_address = federation_address
        self.assurance_address = assurance_address
        self.gate_address = gate_address
        self.artifact_count = artifact_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.artifacts = tuple(artifacts)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.packet_id, "catalog packet ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION
        ):
            raise ValidationError("catalog packet version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_BOUNDARY
        ):
            raise ValidationError("catalog packet boundary is invalid")
        _text(self.catalog_id, "catalog packet catalog ID", 256)
        for value, field in (
            (self.catalog_address, "catalog packet catalog address"),
            (self.runtime_address, "catalog packet runtime address"),
            (self.federation_address, "catalog packet federation address"),
            (self.assurance_address, "catalog packet assurance address"),
            (self.gate_address, "catalog packet gate address"),
        ):
            _address(value, field)
        _count(
            self.artifact_count,
            "catalog packet artifact count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MAX_ARTIFACTS,
        )
        if self.artifact_count != len(self.artifacts) or self.artifact_count != 5:
            raise ValidationError("catalog packet requires exactly five public artifacts")
        kinds = set()
        names = set()
        for ordinal, artifact in enumerate(self.artifacts):
            if artifact.ordinal != ordinal or artifact.kind in kinds or artifact.file_name in names:
                raise ValidationError("catalog packet artifact ordering is not unique")
            kinds.add(artifact.kind)
            names.add(artifact.file_name)
        if kinds != {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
        }:
            raise ValidationError("catalog packet artifact kinds are incomplete")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketState
        }:
            raise ValidationError("catalog packet state is invalid")
        _bool(self.release_ready, "catalog packet release-ready flag")
        _bool(self.accepted, "catalog packet accepted flag")
        if self.release_ready and (not self.accepted or self.state != "ready"):
            raise ValidationError("release-ready catalog packet state is invalid")
        if not self.accepted and self.state != "blocked":
            raise ValidationError("rejected catalog packet must be blocked")
        _address(self.content_address, "catalog packet content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog packet crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "runtime_address": self.runtime_address,
            "federation_address": self.federation_address,
            "assurance_address": self.assurance_address,
            "gate_address": self.gate_address,
            "artifact_count": self.artifact_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_artifacts: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_artifacts:
            body["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return body


def _artifact(
    ordinal: int, kind: str, file_name: str, payload: Mapping[str, Any], content_address: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact:
    payload_bytes = canonical_bytes(payload)
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "file_name": file_name,
        "byte_count": len(payload_bytes),
        "byte_address": hash_bytes(
            payload_bytes,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ARTIFACT_PREFIX
            + "-bytes",
        ),
        "content_address": content_address,
    }
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact(
        **body
    )


def _payloads(
    catalog: Any, runtime: Any, federation: Any, assurance: Any, gate: Any
) -> tuple[tuple[str, str, Mapping[str, Any], str], ...]:
    return (
        (
            "catalog",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_CATALOG,
            catalog.to_dict(),
            catalog.content_address,
        ),
        (
            "runtime",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_RUNTIME,
            runtime.to_dict(),
            runtime.content_address,
        ),
        (
            "federation",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_FEDERATION,
            federation.to_dict(),
            federation.content_address,
        ),
        (
            "assurance",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ASSURANCE,
            assurance.to_dict(),
            assurance.content_address,
        ),
        (
            "gate",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_GATE,
            gate.to_dict(),
            gate.content_address,
        ),
    )


def _catalog_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog:
    body = dict(value)
    body["entries"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogEntry(
            **item
        )
        for item in body.get("entries", ())
    )
    body["operations"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogOperation(
            **item
        )
        for item in body.get("operations", ())
    )
    body["checks"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogCheck(
            **item
        )
        for item in body.get("checks", ())
    )
    body.pop("stores", None)
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog(
        **body
    )


def _runtime_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime:
    body = dict(value)
    body.pop("stage_count", None)
    body["stages"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntimeStage(
            **item
        )
        for item in body.get("stages", ())
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime(
        **body
    )


def _federation_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation:
    body = dict(value)
    body.pop("check_count", None)
    body["members"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember(
            **item
        )
        for item in body.get("members", ())
    )
    body["checks"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck(
            **item
        )
        for item in body.get("checks", ())
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation(
        **body
    )


def _assurance_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding,
    )

    body = dict(value)
    body["findings"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding(
            **item
        )
        for item in body.get("findings", ())
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance(
        **body
    )


def _gate_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate:
    body = dict(value)
    body["checks"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck(
            **item
        )
        for item in body.get("checks", ())
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate(
        **body
    )


def _packet(
    catalog: Any, runtime: Any, federation: Any, assurance: Any, gate: Any, *, packet_id: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket:
    payloads = _payloads(catalog, runtime, federation, assurance, gate)
    artifacts = tuple(
        _artifact(ordinal, kind, file_name, payload, address)
        for ordinal, (kind, file_name, payload, address) in enumerate(payloads)
    )
    body = {
        "packet_id": _text(packet_id, "catalog packet ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_BOUNDARY,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "runtime_address": runtime.content_address,
        "federation_address": federation.content_address,
        "assurance_address": assurance.content_address,
        "gate_address": gate.content_address,
        "artifact_count": len(artifacts),
        "state": gate.state,
        "release_ready": gate.release_ready,
        "accepted": gate.accepted,
        "artifacts": artifacts,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket(
        **body, content_address="pending:packet"
    )
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket(
        **(
            body
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
                    provisional
                )
            }
        )
    )
    value.catalog = catalog
    value.runtime = runtime
    value.federation = federation
    value.assurance = assurance
    value.gate = gate
    return value


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    federation: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    assurance: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
    gate: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
    *,
    packet_id: str = "glio-noncode-review-store-catalog-packet",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket:
    """Build a portable packet from the five already-addressed projections."""

    for value, label, verifier in (
        (
            catalog,
            "catalog",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
        ),
        (
            runtime,
            "catalog runtime",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
        ),
        (
            federation,
            "catalog federation",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
        ),
        (
            assurance,
            "catalog assurance",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
        ),
        (
            gate,
            "catalog gate",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
        ),
    ):
        if value is None:
            raise ValidationError(f"{label} is required")
        if verifier is not None:
            verifier(value)
    if not isinstance(
        catalog,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ) or not isinstance(
        federation,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    ):
        raise ValidationError("catalog packet components have invalid types")
    if (
        catalog.content_address != runtime.catalog_address
        or catalog.content_address != federation.catalog_address
        or catalog.content_address != assurance.catalog_address
        or catalog.content_address != gate.catalog_address
    ):
        raise ValidationError("catalog packet components reference different catalogs")
    if (
        federation.content_address != gate.federation_address
        or assurance.content_address != gate.assurance_address
        or runtime.content_address != gate.runtime_address
    ):
        raise ValidationError("catalog packet gate links do not conserve component addresses")
    return _packet(catalog, runtime, federation, assurance, gate, packet_id=packet_id)


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_from_directory(
    directory: str | Path, *, packet_id: str = "glio-noncode-review-store-catalog-packet"
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
        run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
    )

    catalog = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        directory
    )
    runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        catalog
    )
    federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        catalog
    )
    assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        catalog
    )
    gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        catalog, runtime, federation, assurance
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        catalog, runtime, federation, assurance, gate, packet_id=packet_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    *,
    payloads: Mapping[str, Mapping[str, Any]] | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    ):
        raise ValidationError("catalog packet verification requires a typed packet")
    checks: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheck
    ] = []

    def add(kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> None:
        ordinal = len(checks)
        body = {
            "ordinal": ordinal,
            "kind": kind,
            "state": "passed" if passed else "failed",
            "passed": passed,
            "expected": expected,
            "observed": observed,
            "detail": detail,
        }
        provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheck(
            **body, content_address="pending:check"
        )
        checks.append(
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketCheck(
                **body,
                content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_check(
                    provisional
                ),
            )
        )

    add(
        "packet-address",
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
            value
        )
        == value.content_address,
        "recomputed packet address",
        value.content_address,
        "packet aggregate address is conserved",
    )
    add(
        "artifact-count",
        value.artifact_count == 5 and len(value.artifacts) == 5,
        5,
        value.artifact_count,
        "packet contains exactly five public component artifacts",
    )
    add(
        "catalog-link",
        value.artifacts[0].content_address == value.catalog_address,
        value.catalog_address,
        value.artifacts[0].content_address,
        "catalog artifact address matches packet summary",
    )
    add(
        "runtime-link",
        value.artifacts[1].content_address == value.runtime_address,
        value.runtime_address,
        value.artifacts[1].content_address,
        "runtime artifact address matches packet summary",
    )
    add(
        "federation-link",
        value.artifacts[2].content_address == value.federation_address,
        value.federation_address,
        value.artifacts[2].content_address,
        "federation artifact address matches packet summary",
    )
    add(
        "assurance-link",
        value.artifacts[3].content_address == value.assurance_address,
        value.assurance_address,
        value.artifacts[3].content_address,
        "assurance artifact address matches packet summary",
    )
    add(
        "gate-link",
        value.artifacts[4].content_address == value.gate_address,
        value.gate_address,
        value.artifacts[4].content_address,
        "gate artifact address matches packet summary",
    )
    if payloads is None:
        add(
            "payload-bytes",
            True,
            "verified during load or build",
            "not-provided",
            "artifact bytes are checked when a packet directory is loaded",
        )
    else:
        for artifact in value.artifacts:
            payload = payloads.get(artifact.kind)
            raw = canonical_bytes(payload) if payload is not None else b""
            add(
                f"bytes-{artifact.kind}",
                payload is not None
                and len(raw) == artifact.byte_count
                and hash_bytes(
                    raw,
                    prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ARTIFACT_PREFIX
                    + "-bytes",
                )
                == artifact.byte_address,
                artifact.byte_address,
                hash_bytes(
                    raw,
                    prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ARTIFACT_PREFIX
                    + "-bytes",
                )
                if raw
                else None,
                f"{artifact.kind} bytes match manifest",
            )
            expected_address = getattr(value, f"{artifact.kind}_address")
            add(
                f"content-{artifact.kind}",
                payload is not None and payload.get("content_address") == expected_address,
                expected_address,
                payload.get("content_address") if payload is not None else None,
                f"{artifact.kind} content address matches packet summary",
            )
    add(
        "accepted-state",
        value.accepted == (value.state != "blocked"),
        value.accepted,
        value.state,
        "packet acceptance follows held or blocked state",
    )
    add(
        "readiness-state",
        value.release_ready == (value.state == "ready" and value.accepted),
        value.release_ready,
        value.state,
        "packet readiness follows the combined gate state",
    )
    add(
        "public-boundary",
        _public(value.to_dict()),
        True,
        True,
        "packet projection contains deterministic public fields",
    )
    body = {
        "packet_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_verification(
            provisional
        ),
    )


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        value
    )
    if not verification.accepted:
        raise ValidationError("cannot persist an unverified catalog packet")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("catalog packet destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        payloads = (
            {
                kind: payload
                for kind, _, payload, _ in _payloads(
                    getattr(value, "catalog", None),
                    getattr(value, "runtime", None),
                    getattr(value, "federation", None),
                    getattr(value, "assurance", None),
                    getattr(value, "gate", None),
                )
            }
            if all(
                hasattr(value, name)
                for name in ("catalog", "runtime", "federation", "assurance", "gate")
            )
            else None
        )
        if payloads is None:
            raise ValidationError("catalog packet must retain hydrated components before writing")
        artifact_files: dict[str, bytes] = {}
        for artifact in value.artifacts:
            artifact_files[artifact.file_name] = canonical_bytes(payloads[artifact.kind])
        manifest_body = value.to_dict() | {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION,
            "artifact_files": [item.to_dict() for item in value.artifacts],
        }
        manifest = manifest_body | {
            "manifest_address": content_hash(
                manifest_body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX
                + "-manifest",
            )
        }
        artifact_files[
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MANIFEST
        ] = canonical_bytes(manifest)
        for file_name, raw in artifact_files.items():
            (temporary / file_name).write_bytes(raw)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("catalog packet destination is not a regular directory")
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


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("catalog packet directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_CATALOG,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_RUNTIME,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_FEDERATION,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ASSURANCE,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_GATE,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("catalog packet files do not match the published set")
    manifest_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MANIFEST
    )
    manifest = _read_json(manifest_path, "catalog packet manifest")
    expected_manifest_keys = {
        "packet_id",
        "version",
        "boundary",
        "catalog_id",
        "catalog_address",
        "runtime_address",
        "federation_address",
        "assurance_address",
        "gate_address",
        "artifact_count",
        "state",
        "release_ready",
        "accepted",
        "content_address",
        "artifacts",
        "manifest_version",
        "artifact_files",
        "manifest_address",
    }
    if (
        set(manifest) != expected_manifest_keys
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION
        or manifest.get("artifact_files") != manifest.get("artifacts")
    ):
        raise ValidationError("catalog packet manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest.get("manifest_address") != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_PREFIX
        + "-manifest",
    ):
        raise ValidationError("catalog packet manifest address mismatch")
    packet = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket(
        **{
            key: manifest[key]
            for key in (
                "packet_id",
                "version",
                "boundary",
                "catalog_id",
                "catalog_address",
                "runtime_address",
                "federation_address",
                "assurance_address",
                "gate_address",
                "artifact_count",
                "state",
                "release_ready",
                "accepted",
                "content_address",
            )
        },
        artifacts=tuple(
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifact(
                **item
            )
            for item in manifest["artifacts"]
        ),
    )
    payload_paths = {
        "catalog": directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_CATALOG,
        "runtime": directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_RUNTIME,
        "federation": directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_FEDERATION,
        "assurance": directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ASSURANCE,
        "gate": directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_GATE,
    }
    payloads: dict[str, Mapping[str, Any]] = {}
    expected_names = {kind: path.name for kind, path in payload_paths.items()}
    for artifact in packet.artifacts:
        if artifact.file_name != expected_names[artifact.kind]:
            raise ValidationError("catalog packet artifact file name does not match its kind")
        raw = payload_paths[artifact.kind].read_bytes()
        if (
            len(raw) != artifact.byte_count
            or hash_bytes(
                raw,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ARTIFACT_PREFIX
                + "-bytes",
            )
            != artifact.byte_address
        ):
            raise ValidationError("catalog packet artifact bytes do not match manifest")
        payloads[artifact.kind] = _read_json(
            payload_paths[artifact.kind], f"catalog packet {artifact.kind}"
        )
    packet.catalog = _catalog_from_dict(payloads["catalog"])
    packet.runtime = _runtime_from_dict(payloads["runtime"])
    packet.federation = _federation_from_dict(payloads["federation"])
    packet.assurance = _assurance_from_dict(payloads["assurance"])
    packet.gate = _gate_from_dict(payloads["gate"])
    for component, verifier in (
        (
            packet.catalog,
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
        ),
        (
            packet.runtime,
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
        ),
        (
            packet.federation,
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
        ),
        (
            packet.assurance,
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
        ),
        (
            packet.gate,
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
        ),
    ):
        verifier(component)
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        packet, payloads=payloads
    )
    if not verification.accepted:
        raise ValidationError("catalog packet verification failed")
    return packet


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        value
    )
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
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for artifact in value.artifacts:
        writer.writerow(artifact.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        value
    )
    lines = [
        "# Durable Review-Store Catalog Packet",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- artifacts: `{value.artifact_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | File | Bytes | Content address |",
        "|---:|---|---|---:|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.kind} | `{item.file_name}` | {item.byte_count} | `{item.content_address}` |"
        for item in value.artifacts
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacket,
    *,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet(
        value
    )
    if kind is not None and kind not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
    }:
        raise ValidationError("catalog packet query kind is invalid")
    if text is not None:
        text = _text(text, "catalog packet query text")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("catalog packet query bounds are invalid")
    rows = [item.to_dict() for item in value.artifacts]
    if kind is not None:
        rows = [row for row in rows if row["kind"] == kind]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {"kind": kind, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "packet": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("catalog packet query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("catalog packet query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query(
        value
    )
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
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in value.get("items", []):
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query(
        value
    )
    lines = [
        "# Durable Review-Store Catalog Packet Query",
        "",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Kind | File | Bytes |",
        "|---:|---|---|---:|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | {row.get('kind', '')} | `{row.get('file_name', '')}` | {row.get('byte_count', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_BOUNDARY,
        "files": [
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_MANIFEST,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_CATALOG,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_RUNTIME,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_FEDERATION,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_ASSURANCE,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_GATE,
        ],
        "artifact_kinds": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketArtifactKind
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketState
        ],
        "exact_artifacts": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_VERSION,
        "operations": ["build", "verify", "write", "load", "query", "json", "csv", "markdown"],
        "component_count": 5,
        "exact_file_count": 6,
        "atomic_write": True,
        "canonical_json": True,
        "rehydrates_components": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_QUERY_PREFIX
        + "-v1",
        "resources": ["artifacts", "summary"],
        "filters": ["kind", "text", "offset", "limit"],
        "bounded": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_QUERY_PREFIX
        + "-v1",
        "addressed_receipts": True,
        "bounded": True,
        "resources": ["artifacts", "summary"],
        "identity_free": True,
    }

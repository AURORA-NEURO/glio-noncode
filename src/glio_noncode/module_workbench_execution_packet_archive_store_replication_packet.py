"""Build and transport a deterministic archive-store replication packet.

The replication planner produces an addressed decision, while this module
turns that decision into a portable, reviewable packet.  A packet contains
only canonical derived artifacts: it never embeds source paths, timestamps,
credentials, or opaque runtime metadata.  Binary payloads are kept outside
the manifest and are verified by their byte addresses before a packet is
accepted or replayed.

The packet boundary is intentionally stricter than a convenient export.  It
has a fixed artifact vocabulary, exact byte accounting, content-addressed
manifest and artifact records, a public-key scan, and atomic directory
replacement.  Those properties make the packet useful as a handoff between
offline jobs, CI stages, and human review without making the archive store
itself mutable or introducing a second source of truth.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication import (
    build_module_workbench_execution_packet_archive_store_promotion,
    module_workbench_execution_packet_archive_store_promotion_json,
    module_workbench_execution_packet_archive_store_replication_csv,
    module_workbench_execution_packet_archive_store_replication_json,
    render_module_workbench_execution_packet_archive_store_replication_markdown,
    verify_module_workbench_execution_packet_archive_store_promotion,
    verify_module_workbench_execution_packet_archive_store_replication,
    verify_module_workbench_execution_packet_archive_store_replication_receipt,
)
from .module_workbench_execution_packet_archive_store_replication_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt,
)
from .module_workbench_execution_packet_archive_store_replication_query import (
    query_module_workbench_execution_packet_archive_store_replication,
)
from .module_workbench_execution_packet_archive_store_replication_runtime import (
    module_workbench_execution_packet_archive_store_replication_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_runtime_json,
    verify_module_workbench_execution_packet_archive_store_replication_runtime,
)
from .module_workbench_execution_packet_archive_store_replication_runtime_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-packet-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-artifact"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_CHECK_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_QUERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MANIFEST = "packet.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY = "artifacts"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACTS = 32
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACT_BYTES = (
    8 * 1024 * 1024
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_TOTAL_BYTES = (
    32 * 1024 * 1024
)


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole(StrEnum):
    """Stable roles for packet artifacts."""

    PLAN = "plan"
    QUERY = "query"
    RUNTIME = "runtime"
    RECEIPT = "receipt"
    PROMOTION = "promotion"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane(StrEnum):
    """Independent packet acceptance planes."""

    FORMAT = "format"
    ARTIFACT = "artifact"
    REFERENCE = "reference"
    ACCOUNTING = "accounting"
    STORAGE = "storage"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState(StrEnum):
    """Outcome values used by typed packet checks."""

    PASSED = "passed"
    FAILED = "failed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact:
    """A manifest record for one canonical packet file."""

    artifact_id: str
    role: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole
    file_name: str
    media_type: str
    byte_count: int
    content_address: str
    required: bool
    accepted: bool
    detail: str

    def __init__(
        self,
        artifact_id: str,
        role: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole,
        file_name: str,
        media_type: str,
        byte_count: int,
        content_address: str,
        required: bool,
        accepted: bool,
        detail: str,
    ) -> None:
        self.artifact_id = artifact_id
        self.role = role
        self.file_name = file_name
        self.media_type = media_type
        self.byte_count = byte_count
        self.content_address = content_address
        self.required = required
        self.accepted = accepted
        self.detail = detail
        self._validate()

    def _validate(self) -> None:
        _text(self.artifact_id, "packet artifact ID", 256)
        _text(self.file_name, "packet artifact file name", 256)
        _text(self.media_type, "packet artifact media type", 256)
        _text(self.detail, "packet artifact detail", 4096)
        if not isinstance(
            self.role, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole
        ):
            raise ValidationError("packet artifact role is invalid")
        if isinstance(self.byte_count, bool) or not isinstance(self.byte_count, int):
            raise ValidationError("packet artifact byte count must be an integer")
        if (
            self.byte_count < 0
            or self.byte_count
            > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACT_BYTES
        ):
            raise ValidationError("packet artifact byte count is outside the limit")
        if not isinstance(self.required, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("packet artifact flags must be boolean")
        if not _safe_file_name(self.file_name):
            raise ValidationError("packet artifact file name is unsafe")
        if not isinstance(self.content_address, str) or not self.content_address.startswith(
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_PREFIX + ":"
        ):
            raise ValidationError("packet artifact address is invalid")
        if self.required and not self.accepted:
            raise ValidationError("required packet artifact cannot be rejected")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "role": self.role,
            "file_name": self.file_name,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "content_address": self.content_address,
            "required": self.required,
            "accepted": self.accepted,
            "detail": self.detail,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_artifact(
    payload: bytes,
) -> str:
    """Address artifact bytes independently from their manifest record."""

    return hash_bytes(
        payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck:
    """One independently inspectable packet acceptance result."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def __init__(
        self,
        check_id: str,
        plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane,
        state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.check_id = check_id
        self.plane = plane
        self.state = state
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.check_id, "packet check ID", 256)
        _text(self.detail, "packet check detail", 4096)
        if not isinstance(
            self.plane, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane
        ):
            raise ValidationError("packet check plane is invalid")
        if not isinstance(
            self.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState
        ):
            raise ValidationError("packet check state is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("packet check passed flag must be boolean")
        if self.passed != (
            self.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState.PASSED
        ):
            raise ValidationError("packet check state and passed flag disagree")
        if not isinstance(self.content_address, str) or not (
            self.content_address.startswith(
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_CHECK_PREFIX
                + ":"
            )
            or self.content_address.startswith("pending:")
        ):
            raise ValidationError("packet check address is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "plane": self.plane,
            "state": self.state,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck,
) -> str:
    """Recompute a check address from its public fields."""

    body = value.to_dict() | {"content_address": None}
    return content_hash(
        body, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_CHECK_PREFIX
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket:
    """Addressable packet manifest with no filesystem-specific values."""

    packet_id: str
    version: str
    boundary: str
    plan_address: str
    receipt_address: str | None
    promotion_address: str
    runtime_address: str | None
    artifacts: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact, ...]
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck, ...]
    artifact_count: int
    check_count: int
    passed_count: int
    total_byte_count: int
    accepted: bool
    detail: str
    content_address: str

    def __init__(
        self,
        packet_id: str,
        version: str,
        boundary: str,
        plan_address: str,
        receipt_address: str | None,
        promotion_address: str,
        runtime_address: str | None,
        artifacts: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact, ...],
        checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck, ...],
        artifact_count: int,
        check_count: int,
        passed_count: int,
        total_byte_count: int,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.packet_id = packet_id
        self.version = version
        self.boundary = boundary
        self.plan_address = plan_address
        self.receipt_address = receipt_address
        self.promotion_address = promotion_address
        self.runtime_address = runtime_address
        self.artifacts = artifacts
        self.checks = checks
        self.artifact_count = artifact_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.total_byte_count = total_byte_count
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.packet_id, "packet ID", 512)
        _text(self.version, "packet version", 256)
        _text(self.boundary, "packet boundary", 512)
        _address(self.plan_address, "packet plan address")
        _address(self.promotion_address, "packet promotion address")
        if self.receipt_address is not None:
            _address(self.receipt_address, "packet receipt address")
        if self.runtime_address is not None:
            _address(self.runtime_address, "packet runtime address")
        _count(self.artifact_count, "packet artifact count")
        _count(self.check_count, "packet check count")
        _count(self.passed_count, "packet passed count")
        _count(self.total_byte_count, "packet total byte count")
        if (
            self.artifact_count
            > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACTS
        ):
            raise ValidationError("packet artifact count is outside the limit")
        if (
            self.total_byte_count
            > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_TOTAL_BYTES
        ):
            raise ValidationError("packet total byte count is outside the limit")
        if not isinstance(self.accepted, bool):
            raise ValidationError("packet acceptance must be boolean")
        _text(self.detail, "packet detail", 8192)
        if not isinstance(self.content_address, str) or not (
            self.content_address.startswith(
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_PREFIX + ":"
            )
            or self.content_address.startswith("pending:")
        ):
            raise ValidationError("packet address is invalid")
        if self.artifact_count != len(self.artifacts) or self.check_count != len(self.checks):
            raise ValidationError("packet counts do not match rows")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("packet passed count does not match checks")
        if self.total_byte_count != sum(item.byte_count for item in self.artifacts):
            raise ValidationError("packet byte count does not match artifacts")
        if not self.artifacts or not self.checks:
            raise ValidationError("packet must contain artifacts and checks")
        if self.accepted != all(item.accepted for item in self.artifacts) or self.accepted != all(
            item.passed for item in self.checks
        ):
            raise ValidationError("packet acceptance does not match artifacts and checks")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValidationError("packet artifact IDs must be unique")
        if len({item.file_name for item in self.artifacts}) != len(self.artifacts):
            raise ValidationError("packet artifact files must be unique")
        if len({item.check_id for item in self.checks}) != len(self.checks):
            raise ValidationError("packet check IDs must be unique")

    def summary(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "packet_address": self.content_address,
            "plan_address": self.plan_address,
            "receipt_address": self.receipt_address,
            "promotion_address": self.promotion_address,
            "runtime_address": self.runtime_address,
            "artifact_count": self.artifact_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "total_byte_count": self.total_byte_count,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "boundary": self.boundary,
            "plan_address": self.plan_address,
            "receipt_address": self.receipt_address,
            "promotion_address": self.promotion_address,
            "runtime_address": self.runtime_address,
            "artifacts": tuple(item.to_dict() for item in self.artifacts),
            "checks": tuple(item.to_dict() for item in self.checks),
            "artifact_count": self.artifact_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "total_byte_count": self.total_byte_count,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
) -> str:
    """Recompute the packet manifest address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketVerification:
    """Verification result for a packet manifest and optional payload map."""

    packet_address: str
    artifact_count: int
    check_count: int
    passed_count: int
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck, ...]
    accepted: bool
    detail: str
    content_address: str

    def __init__(
        self,
        packet_address: str,
        artifact_count: int,
        check_count: int,
        passed_count: int,
        checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck, ...],
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.packet_address = packet_address
        self.artifact_count = artifact_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.checks = checks
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_address": self.packet_address,
            "artifact_count": self.artifact_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.check_count - self.passed_count,
            "checks": tuple(item.to_dict() for item in self.checks),
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} is invalid")
    return value


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


def _address(value: Any, field: str) -> str:
    if not isinstance(value, str) or ":" not in value or not value.split(":", 1)[1]:
        raise ValidationError(f"{field} is invalid")
    return value


def _safe_file_name(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        value == str(path)
        and path.parts
        and len(path.parts) == 2
        and path.parts[0]
        == MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY
        and all(part not in {"", ".", ".."} and "\\" not in part for part in path.parts)
        and path.suffix in {".json", ".csv", ".md"}
    )


def _forbidden_key(value: Any) -> bool:
    forbidden = {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "claude",
        "codex",
        "email",
        "hostname",
        "ip_address",
        "model",
        "openai",
        "private",
        "token",
        "user",
        "username",
    }
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in forbidden or _forbidden_key(item) for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return any(_forbidden_key(item) for item in value)
    return False


def _check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "state": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState.PASSED
        if passed
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState.FAILED,
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck(
        **body, content_address="pending:packet-check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_check(
            provisional
        ),
    )


def _artifact(
    artifact_id: str,
    role: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole,
    file_name: str,
    media_type: str,
    payload: bytes,
    *,
    required: bool = True,
    detail: str,
) -> tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact, bytes]:
    if (
        len(payload)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACT_BYTES
    ):
        raise ValidationError("packet artifact exceeds the byte limit")
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact(
        artifact_id=artifact_id,
        role=role,
        file_name=file_name,
        media_type=media_type,
        byte_count=len(payload),
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_artifact(
            payload
        ),
        required=required,
        accepted=True,
        detail=detail,
    )
    return provisional, payload


def _artifact_payloads(
    plan: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    receipt: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt | None,
    promotion: ModuleWorkbenchExecutionPacketArchiveStorePromotion,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime | None,
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    rows = (
        _artifact(
            "plan-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
            "artifacts/plan.json",
            "application/json",
            module_workbench_execution_packet_archive_store_replication_json(plan).encode("utf-8"),
            detail="canonical replication plan",
        ),
        _artifact(
            "plan-csv",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
            "artifacts/plan.csv",
            "text/csv",
            module_workbench_execution_packet_archive_store_replication_csv(plan).encode("utf-8"),
            detail="tabular replication plan",
        ),
        _artifact(
            "plan-markdown",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
            "artifacts/plan.md",
            "text/markdown",
            render_module_workbench_execution_packet_archive_store_replication_markdown(
                plan
            ).encode("utf-8"),
            detail="human-readable replication plan",
        ),
        _artifact(
            "query-summary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.QUERY,
            "artifacts/query-summary.json",
            "application/json",
            (
                canonical_json(
                    query_module_workbench_execution_packet_archive_store_replication(plan)
                )
                + "\n"
            ).encode("utf-8"),
            detail="bounded plan summary query",
        ),
        _artifact(
            "promotion-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PROMOTION,
            "artifacts/promotion.json",
            "application/json",
            module_workbench_execution_packet_archive_store_promotion_json(promotion).encode(
                "utf-8"
            ),
            detail="promotion decision",
        ),
    )
    for record, payload in rows:
        payloads[record.file_name] = payload
    if receipt is not None:
        record, payload = _artifact(
            "receipt-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.RECEIPT,
            "artifacts/receipt.json",
            "application/json",
            (canonical_json(receipt.to_dict()) + "\n").encode("utf-8"),
            detail="atomic apply receipt",
        )
        payloads[record.file_name] = payload
    if runtime is not None:
        runtime_rows = (
            _artifact(
                "runtime-json",
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.RUNTIME,
                "artifacts/runtime.json",
                "application/json",
                module_workbench_execution_packet_archive_store_replication_runtime_json(
                    runtime
                ).encode("utf-8"),
                detail="replication runtime receipt",
            ),
            _artifact(
                "runtime-csv",
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.RUNTIME,
                "artifacts/runtime.csv",
                "text/csv",
                module_workbench_execution_packet_archive_store_replication_runtime_csv(
                    runtime
                ).encode("utf-8"),
                detail="replication runtime stage table",
            ),
        )
        for record, payload in runtime_rows:
            payloads[record.file_name] = payload
    return payloads


def _records_for_payloads(
    payloads: Mapping[str, bytes],
    receipt: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole | None = None,
) -> tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact, ...]:
    del receipt
    role_by_name = {
        "artifacts/plan.json": (
            "plan-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
            "application/json",
            "canonical replication plan",
        ),
        "artifacts/plan.csv": (
            "plan-csv",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
            "text/csv",
            "tabular replication plan",
        ),
        "artifacts/plan.md": (
            "plan-markdown",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
            "text/markdown",
            "human-readable replication plan",
        ),
        "artifacts/query-summary.json": (
            "query-summary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.QUERY,
            "application/json",
            "bounded plan summary query",
        ),
        "artifacts/promotion.json": (
            "promotion-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PROMOTION,
            "application/json",
            "promotion decision",
        ),
        "artifacts/receipt.json": (
            "receipt-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.RECEIPT,
            "application/json",
            "atomic apply receipt",
        ),
        "artifacts/runtime.json": (
            "runtime-json",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.RUNTIME,
            "application/json",
            "replication runtime receipt",
        ),
        "artifacts/runtime.csv": (
            "runtime-csv",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.RUNTIME,
            "text/csv",
            "replication runtime stage table",
        ),
    }
    records = []
    for file_name in sorted(payloads):
        if file_name not in role_by_name:
            raise ValidationError("packet contains an unsupported artifact")
        artifact_id, role, media_type, detail = role_by_name[file_name]
        records.append(
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact(
                artifact_id=artifact_id,
                role=role,
                file_name=file_name,
                media_type=media_type,
                byte_count=len(payloads[file_name]),
                content_address=address_module_workbench_execution_packet_archive_store_replication_packet_artifact(
                    payloads[file_name]
                ),
                required=True,
                accepted=True,
                detail=detail,
            )
        )
    return tuple(records)


def build_module_workbench_execution_packet_archive_store_replication_packet(
    plan: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPlan,
    *,
    receipt: ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceipt | None = None,
    promotion: ModuleWorkbenchExecutionPacketArchiveStorePromotion | None = None,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationRuntime | None = None,
    packet_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet",
) -> tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket, dict[str, bytes]]:
    """Build an addressed packet and its private payload map."""

    verify_module_workbench_execution_packet_archive_store_replication(plan)
    if receipt is not None:
        verify_module_workbench_execution_packet_archive_store_replication_receipt(receipt)
    if promotion is None:
        promotion = build_module_workbench_execution_packet_archive_store_promotion(plan, receipt)
    verify_module_workbench_execution_packet_archive_store_promotion(promotion)
    if runtime is not None:
        verify_module_workbench_execution_packet_archive_store_replication_runtime(runtime)
    payloads = _artifact_payloads(plan, receipt, promotion, runtime)
    artifacts = _records_for_payloads(payloads)
    checks = (
        _check(
            "packet-format",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.FORMAT,
            True,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
            "packet format matches the published boundary",
        ),
        _check(
            "packet-plan-reference",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.REFERENCE,
            plan.content_address == plan.content_address,
            plan.content_address,
            plan.content_address,
            "packet references the addressed replication plan",
        ),
        _check(
            "packet-artifact-vocabulary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.ARTIFACT,
            set(payloads)
            <= {
                "artifacts/plan.json",
                "artifacts/plan.csv",
                "artifacts/plan.md",
                "artifacts/query-summary.json",
                "artifacts/promotion.json",
                "artifacts/receipt.json",
                "artifacts/runtime.json",
                "artifacts/runtime.csv",
            },
            tuple(sorted(payloads)),
            "published artifact vocabulary",
            "packet artifact names are from the fixed vocabulary",
        ),
        _check(
            "packet-byte-accounting",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.ACCOUNTING,
            sum(len(item) for item in payloads.values())
            == sum(item.byte_count for item in artifacts),
            sum(len(item) for item in payloads.values()),
            sum(item.byte_count for item in artifacts),
            "manifest byte counts equal the payload map",
        ),
        _check(
            "packet-public-boundary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.PUBLIC,
            not _forbidden_key({"plan": plan.to_dict(), "promotion": promotion.to_dict()}),
            "forbidden-key scan",
            "no private or attribution keys",
            "packet references remain identity-free",
        ),
    )
    body = {
        "packet_id": packet_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_BOUNDARY,
        "plan_address": plan.content_address,
        "receipt_address": receipt.content_address if receipt is not None else None,
        "promotion_address": promotion.content_address,
        "runtime_address": runtime.content_address if runtime is not None else None,
        "artifacts": artifacts,
        "checks": checks,
        "artifact_count": len(artifacts),
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "total_byte_count": sum(item.byte_count for item in artifacts),
        "accepted": all(item.passed for item in checks),
        "detail": "packet contains canonical replication, query, and promotion artifacts",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket(
        **body, content_address="pending:replication-packet"
    )
    packet = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet(
            provisional
        ),
    )
    return packet, payloads


def verify_module_workbench_execution_packet_archive_store_replication_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
    payloads: Mapping[str, bytes] | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketVerification:
    """Verify a packet manifest and, when supplied, every artifact byte."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket):
        raise ValidationError("packet verification requires a typed packet")
    checks = list(value.checks)
    checks.append(
        _check(
            "packet-address",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.FORMAT,
            address_module_workbench_execution_packet_archive_store_replication_packet(value)
            == value.content_address,
            value.content_address,
            "recomputed packet address",
            "packet manifest address is reproducible",
        )
    )
    checks.append(
        _check(
            "packet-check-addresses",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.ARTIFACT,
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_check(
                    item
                )
                == item.content_address
                for item in value.checks
            ),
            tuple(item.content_address for item in value.checks),
            "recomputed check addresses",
            "packet checks are content addressed",
        )
    )
    checks.append(
        _check(
            "packet-public-boundary-recheck",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.PUBLIC,
            not _forbidden_key(value.to_dict()),
            "forbidden-key scan",
            "no private or attribution keys",
            "packet manifest has no forbidden public fields",
        )
    )
    if payloads is not None:
        checks.append(
            _check(
                "packet-payload-set",
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.STORAGE,
                tuple(sorted(payloads))
                == tuple(sorted(item.file_name for item in value.artifacts)),
                tuple(sorted(payloads)),
                tuple(sorted(item.file_name for item in value.artifacts)),
                "payload names exactly match manifest artifact names",
            )
        )
        checks.append(
            _check(
                "packet-payload-addresses",
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane.STORAGE,
                all(
                    item.file_name in payloads
                    and len(payloads[item.file_name]) == item.byte_count
                    and (
                        address_module_workbench_execution_packet_archive_store_replication_packet_artifact(
                            payloads[item.file_name]
                        )
                        == item.content_address
                    )
                    for item in value.artifacts
                ),
                tuple(item.content_address for item in value.artifacts),
                "recomputed payload addresses",
                "artifact bytes match manifest addresses and sizes",
            )
        )
    accepted = bool(checks) and all(item.passed for item in checks)
    body = {
        "packet_address": value.content_address,
        "artifact_count": value.artifact_count,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "checks": tuple(checks),
        "accepted": accepted,
        "detail": "packet manifest and supplied payloads verified"
        if accepted
        else "packet verification is blocked by one or more checks",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketVerification(
        **body, content_address="pending:packet-verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketVerification(
        **body,
        content_address=content_hash(
            provisional.to_dict() | {"content_address": None},
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_CHECK_PREFIX,
        ),
    )


def module_workbench_execution_packet_archive_store_replication_packet_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
) -> str:
    """Serialize the packet manifest as canonical JSON."""

    verify_module_workbench_execution_packet_archive_store_replication_packet(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
) -> str:
    """Serialize the packet manifest as a stable artifact table."""

    verify_module_workbench_execution_packet_archive_store_replication_packet(value)
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "artifact_id",
        "role",
        "file_name",
        "media_type",
        "byte_count",
        "content_address",
        "required",
        "accepted",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for ordinal, item in enumerate(value.artifacts):
        writer.writerow({"ordinal": ordinal, **item.to_dict()})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
) -> str:
    """Render the packet manifest for human review."""

    verify_module_workbench_execution_packet_archive_store_replication_packet(value)
    lines = [
        "# Archive Store Replication Packet",
        "",
        f"- Packet: `{value.packet_id}`",
        f"- Address: `{value.content_address}`",
        f"- Plan: `{value.plan_address}`",
        f"- Artifacts: `{value.artifact_count}`; bytes `{value.total_byte_count:,}`",
        f"- Checks: `{value.passed_count}/{value.check_count}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "| Ordinal | Role | File | Bytes | Address | Accepted |",
        "|---:|---|---|---:|---|---:|",
    ]
    for ordinal, item in enumerate(value.artifacts):
        lines.append(
            f"| {ordinal} | `{item.role}` | `{item.file_name}` | {item.byte_count:,} | "
            f"`{item.content_address}` | {str(item.accepted).lower()} |"
        )
    return "\n".join(lines) + "\n"


def _packet_from_mapping(
    mapping: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket:
    artifacts = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifact(
            artifact_id=str(item["artifact_id"]),
            role=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole(
                item["role"]
            ),
            file_name=str(item["file_name"]),
            media_type=str(item["media_type"]),
            byte_count=int(item["byte_count"]),
            content_address=str(item["content_address"]),
            required=bool(item["required"]),
            accepted=bool(item["accepted"]),
            detail=str(item["detail"]),
        )
        for item in mapping.get("artifacts", ())
    )
    checks = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheck(
            check_id=str(item["check_id"]),
            plane=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckPlane(
                item["plane"]
            ),
            state=ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketCheckState(
                item["state"]
            ),
            passed=bool(item["passed"]),
            observed=item.get("observed"),
            expected=item.get("expected"),
            detail=str(item["detail"]),
            content_address=str(item["content_address"]),
        )
        for item in mapping.get("checks", ())
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket(
        packet_id=str(mapping["packet_id"]),
        version=str(mapping["version"]),
        boundary=str(mapping["boundary"]),
        plan_address=str(mapping["plan_address"]),
        receipt_address=mapping.get("receipt_address"),
        promotion_address=str(mapping["promotion_address"]),
        runtime_address=mapping.get("runtime_address"),
        artifacts=artifacts,
        checks=checks,
        artifact_count=int(mapping["artifact_count"]),
        check_count=int(mapping["check_count"]),
        passed_count=int(mapping["passed_count"]),
        total_byte_count=int(mapping["total_byte_count"]),
        accepted=bool(mapping["accepted"]),
        detail=str(mapping["detail"]),
        content_address=str(mapping["content_address"]),
    )


def write_module_workbench_execution_packet_archive_store_replication_packet(
    packet: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
    payloads: Mapping[str, bytes],
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write a verified packet through atomic directory replacement."""

    verification = verify_module_workbench_execution_packet_archive_store_replication_packet(
        packet, payloads
    )
    if not packet.accepted or not verification.accepted:
        raise ValidationError("cannot write a blocked replication packet")
    target = Path(destination)
    if target.exists() and not allow_existing:
        raise ValidationError("replication packet destination already exists")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".replication-packet-", dir=parent))
    try:
        artifact_root = (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY
        )
        artifact_root.mkdir()
        for item in packet.artifacts:
            path = temporary / item.file_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payloads[item.file_name])
        manifest = canonical_bytes(packet.to_dict())
        manifest_path = (
            temporary / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MANIFEST
        )
        with manifest_path.open("wb") as handle:
            handle.write(manifest)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def _read_packet(
    path: str | Path,
) -> tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket, dict[str, bytes]]:
    root = Path(path)
    if not root.is_dir() or root.is_symlink():
        raise ValidationError("replication packet directory is missing or unsafe")
    manifest_path = (
        root / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MANIFEST
    )
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValidationError("replication packet manifest is missing or unsafe")
    raw = manifest_path.read_bytes()
    try:
        mapping = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("replication packet manifest is not valid UTF-8 JSON") from exc
    if not isinstance(mapping, Mapping) or canonical_bytes(mapping) != raw:
        raise ValidationError("replication packet manifest is not canonical")
    packet = _packet_from_mapping(mapping)
    artifact_root = (
        root / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY
    )
    if not artifact_root.is_dir() or artifact_root.is_symlink():
        raise ValidationError("replication packet artifact directory is missing or unsafe")
    actual = tuple(sorted(f"artifacts/{item.name}" for item in artifact_root.iterdir()))
    expected = tuple(sorted(item.file_name for item in packet.artifacts))
    if actual != expected:
        raise ValidationError("replication packet artifact set does not match manifest")
    payloads: dict[str, bytes] = {}
    for item in packet.artifacts:
        artifact_path = root / item.file_name
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise ValidationError("replication packet artifact is not a regular file")
        payloads[item.file_name] = artifact_path.read_bytes()
    return packet, payloads


def load_module_workbench_execution_packet_archive_store_replication_packet(
    path: str | Path,
) -> tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket, dict[str, bytes]]:
    """Load only a packet whose manifest and artifact bytes verify."""

    packet, payloads = _read_packet(path)
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet(
        packet, payloads
    )
    if not verification.accepted:
        raise ValidationError("replication packet verification is blocked")
    return packet, payloads


def replay_module_workbench_execution_packet_archive_store_replication_packet(
    path: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketVerification:
    """Return a fresh verification receipt for a persisted packet."""

    packet, payloads = _read_packet(path)
    return verify_module_workbench_execution_packet_archive_store_replication_packet(
        packet, payloads
    )


def query_module_workbench_execution_packet_archive_store_replication_packet(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
    *,
    resource: str = "summary",
    role: str | None = None,
    accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded packet summary, artifacts, or checks."""

    verify_module_workbench_execution_packet_archive_store_replication_packet(value)
    if (
        isinstance(offset, bool)
        or isinstance(limit, bool)
        or offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_LIMIT
    ):
        raise ValidationError("replication packet query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "summary":
        rows = [value.summary()]
        index_used = "packet_id"
    elif normalized == "artifacts":
        rows = [item.to_dict() for item in value.artifacts]
        if role:
            rows = [item for item in rows if item["role"] == role]
        if accepted is not None:
            rows = [item for item in rows if item["accepted"] is accepted]
        index_used = "artifact_id"
    elif normalized == "checks":
        rows = [item.to_dict() for item in value.checks]
        if accepted is not None:
            rows = [item for item in rows if item["passed"] is accepted]
        index_used = "plane"
    else:
        raise ValidationError("unsupported replication packet resource")
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item).casefold()]
    total = len(rows)
    items = rows[offset : offset + limit]
    body = {
        "resource": normalized,
        "query": {"role": role, "accepted": accepted, "text": text},
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
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a packet query response address and page shape."""

    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("replication packet query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    expected = content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_QUERY_PREFIX,
    )
    if value["content_address"] != expected:
        raise ValidationError("replication packet query response address mismatch")
    if value.get("total") < len(value.get("items", ())):
        raise ValidationError("replication packet query total is inconsistent")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_query(value)
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_query(value)
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "ordinal",
        "artifact_id",
        "role",
        "file_name",
        "plane",
        "passed",
        "detail",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for ordinal, item in enumerate(value.get("items", ())):
        writer.writerow(
            {
                "resource": value.get("resource"),
                "ordinal": ordinal,
                "artifact_id": item.get("artifact_id"),
                "role": item.get("role"),
                "file_name": item.get("file_name"),
                "plane": item.get("plane"),
                "passed": item.get("passed", item.get("accepted")),
                "detail": item.get("detail"),
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_query_markdown(
    value: Mapping[str, Any],
) -> str:
    """Render a packet query page without exposing filesystem paths."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_query(value)
    lines = [
        "# Archive Store Replication Packet Query",
        "",
        f"- Resource: `{value.get('resource')}`",
        f"- Reference: `{value.get('reference_address')}`",
        f"- Query: `{value.get('content_address')}`",
        f"- Rows: `{len(value.get('items', ()))}/{value.get('total')}`",
        "",
        "| Ordinal | ID | Role | File / Plane | Accepted | Detail |",
        "|---:|---|---|---|---:|---|",
    ]
    for ordinal, item in enumerate(value.get("items", ())):
        lines.append(
            f"| {ordinal} | `{item.get('artifact_id', item.get('check_id', ''))}` | "
            f"`{item.get('role', '')}` | `{item.get('file_name', item.get('plane', ''))}` | "
            f"{str(item.get('accepted', item.get('passed', ''))).lower()} | "
            f"{item.get('detail', '')} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_schema() -> dict[str, Any]:
    """Describe packet files, limits, and verification guarantees."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_BOUNDARY,
        "manifest": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MANIFEST,
        "artifact_directory": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY
        ),
        "artifact_roles": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole
        ],
        "artifact_formats": ["json", "csv", "markdown"],
        "resources": ["summary", "artifacts", "checks"],
        "limits": {
            "max_artifacts": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACTS
            ),
            "max_artifact_bytes": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_ARTIFACT_BYTES
            ),
            "max_total_bytes": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_TOTAL_BYTES
            ),
            "max_query_limit": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_LIMIT
            ),
        },
        "path_free_manifest": True,
        "timestamp_free": True,
        "identity_free": True,
        "atomic_write": True,
        "content_addressed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_capabilities() -> dict[
    str, Any
]:
    """Declare packet construction, transport, and query operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
        "operations": [
            "build_replication_packet",
            "serialize_packet_manifest",
            "write_packet_atomically",
            "load_packet_with_byte_verification",
            "replay_packet_verification",
            "query_packet_summary",
            "query_packet_artifacts",
            "query_packet_checks",
            "export_packet_query_json",
            "export_packet_query_csv",
            "render_packet_query_markdown",
        ],
        "guarantees": [
            "fixed_artifact_vocabulary",
            "exact_artifact_byte_addresses",
            "exact_manifest_byte_accounting",
            "canonical_manifest_encoding",
            "atomic_directory_replacement",
            "symlink_rejection",
            "bounded_query_pages",
            "no_filesystem_paths_in_public_documents",
            "no_private_or_attribution_fields",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_query_schema() -> dict[
    str, Any
]:
    """Describe bounded packet query resources and filters."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
        "query_boundary": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_QUERY_PREFIX
        ),
        "resources": ["summary", "artifacts", "checks"],
        "filters": ["role", "accepted", "text"],
        "paging": {
            "offset_minimum": 0,
            "limit_minimum": 1,
            "limit_maximum": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_MAX_LIMIT
            ),
        },
        "response_fields": [
            "resource",
            "query",
            "total",
            "offset",
            "limit",
            "reference_address",
            "items",
            "accepted",
            "content_address",
        ],
        "path_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_query_capabilities() -> dict[
    str, Any
]:
    """Declare packet query and verification operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_VERSION,
        "operations": [
            "query_packet_summary",
            "query_packet_artifacts",
            "query_packet_checks",
            "filter_packet_role",
            "filter_packet_acceptance",
            "filter_packet_text",
            "page_packet_rows",
            "verify_packet_query_address",
            "export_packet_query_json",
            "export_packet_query_csv",
            "render_packet_query_markdown",
        ],
        "guarantees": [
            "bounded_rows",
            "stable_artifact_order",
            "addressed_query_response",
            "no_filesystem_paths",
            "no_private_or_attribution_fields",
        ],
    }

"""Contracts for the portable architecture-program runtime handoff.

The in-process program runtime is deliberately broad: it resolves sixteen
domain adapters, executes their public aggregate fixtures, and exposes
several reporting and release projections.  This module defines the smaller
transport contract that lets another process inspect those results without
importing the producer runtime.

The handoff is exact-byte addressed and public-aggregate only.  It contains
no user identity, credentials, attribution metadata, or model metadata.  A
consumer can therefore verify the directory using only the manifest and the
bytes in that directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION = "program-runtime-offline-bundle-v1"
PROGRAM_RUNTIME_OFFLINE_SCHEMA_VERSION = "program-runtime-offline-schema-v1"
PROGRAM_RUNTIME_OFFLINE_RUNTIME_VERSION = "program-runtime-offline-runtime-v1"
PROGRAM_RUNTIME_OFFLINE_RECONCILIATION_VERSION = "program-runtime-offline-reconciliation-v1"
PROGRAM_RUNTIME_OFFLINE_CERTIFICATION_VERSION = "program-runtime-offline-certification-v1"
PROGRAM_RUNTIME_OFFLINE_BOUNDARY = "public_aggregate_architecture_program_offline_handoff"
PROGRAM_RUNTIME_OFFLINE_MANIFEST_FILENAME = "bundle.json"
PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX = "program-runtime-offline-artifact"
PROGRAM_RUNTIME_OFFLINE_CHECK_PREFIX = "program-runtime-offline-check"
PROGRAM_RUNTIME_OFFLINE_DEFAULT_LIMIT = 50
PROGRAM_RUNTIME_OFFLINE_MAX_LIMIT = 500
PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS = 32

PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT = 16
PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT = 172
PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT = 18
PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT = 12
PROGRAM_RUNTIME_OFFLINE_HANDOFF_STAGE_COUNT = 11
PROGRAM_RUNTIME_OFFLINE_RELEASE_ARTIFACT_COUNT = 11
PROGRAM_RUNTIME_OFFLINE_OPERATION_COUNT = 16
PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT = 18


class ProgramRuntimeOfflineBundleState(StrEnum):
    """Transport lifecycle state for a program handoff."""

    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class ProgramRuntimeOfflineArtifactKind(StrEnum):
    """Stable categories for portable program projections."""

    RUNTIME = "runtime"
    REPORT = "report"
    SUMMARY = "summary"
    RECEIPTS = "receipts"
    CHECKS = "checks"
    DOMAINS = "domains"
    MARKDOWN = "markdown"
    REPLAY = "replay"
    FAILURE_CONTROLS = "failure_controls"
    SPECIFICATIONS = "specifications"
    MATRIX = "matrix"
    OPERATIONAL = "operational"
    OPERATIONS = "operations"
    STAGES = "stages"
    QUALITY = "quality"
    RELEASE_CHECKS = "release_checks"
    SOURCES = "sources"
    CAPABILITIES = "capabilities"


class ProgramRuntimeOfflineCheckPlane(StrEnum):
    """Independent assurance planes used by the handoff."""

    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    DENOMINATOR = "denominator"
    RUNTIME = "runtime"
    RELEASE = "release"
    OPERATIONAL = "operational"
    INDEX = "index"
    RECONCILIATION = "reconciliation"
    PUBLIC_BOUNDARY = "public_boundary"
    SCHEMA = "schema"
    REPLAY = "replay"
    CERTIFICATION = "certification"


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineArtifact:
    """One exact UTF-8 payload in the handoff directory."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: ProgramRuntimeOfflineArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "relative_path", "media_type", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("offline artifact counts cannot be negative")
        if not self.content_address.startswith(f"{PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX}:"):
            raise ValueError("program offline artifacts require exact-byte addresses")

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "kind": self.kind,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload and self.payload is not None:
            value["payload"] = self.payload
        return jsonable(value)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineCheck:
    """One independently addressable handoff invariant."""

    check_id: str
    plane: ProgramRuntimeOfflineCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{PROGRAM_RUNTIME_OFFLINE_CHECK_PREFIX}:"):
            raise ValueError("program offline checks require addressed receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineBundle:
    """Root manifest and immutable artifact inventory."""

    bundle_id: str
    version: str
    boundary: str
    run_id: str
    state: ProgramRuntimeOfflineBundleState
    accepted: bool
    artifacts: tuple[ProgramRuntimeOfflineArtifact, ...]
    checks: tuple[ProgramRuntimeOfflineCheck, ...]
    runtime_address: str
    domain_count: int
    stage_count: int
    warning_count: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "bundle_id",
            "version",
            "boundary",
            "run_id",
            "runtime_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION:
            raise ValueError("unsupported program offline bundle version")
        if min(self.domain_count, self.stage_count, self.warning_count) < 0:
            raise ValueError("program offline counts cannot be negative")
        if len(self.artifacts) > PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS:
            raise ValueError("program offline artifact ceiling exceeded")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    @property
    def ready(self) -> bool:
        return self.state is ProgramRuntimeOfflineBundleState.READY and self.accepted

    def manifest_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return jsonable(
            {
                "bundle_id": self.bundle_id,
                "version": self.version,
                "boundary": self.boundary,
                "run_id": self.run_id,
                "state": self.state,
                "accepted": self.accepted,
                "artifacts": tuple(
                    item.to_dict(include_payload=include_payloads) for item in self.artifacts
                ),
                "checks": tuple(item.to_dict() for item in self.checks),
                "runtime_address": self.runtime_address,
                "domain_count": self.domain_count,
                "stage_count": self.stage_count,
                "warning_count": self.warning_count,
                "artifact_count": self.artifact_count,
                "passed_check_count": self.passed_check_count,
                "failed_check_count": self.failed_check_count,
            }
        )

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return self.manifest_dict(include_payloads=include_payloads) | {
            "content_address": self.content_address
        }


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineVerification:
    """Result from verifying a materialized handoff directory."""

    bundle_id: str
    accepted: bool
    checks: tuple[ProgramRuntimeOfflineCheck, ...]
    content_address: str

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
        }


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineAudit:
    """In-memory audit over the complete portable inventory."""

    bundle_id: str
    checks: tuple[ProgramRuntimeOfflineCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
        }


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineQueryResult:
    """Bounded resource query with a content-addressed receipt."""

    bundle_id: str
    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineDiff:
    """Artifact and denominator comparison between two handoffs."""

    left_bundle_id: str
    right_bundle_id: str
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    unchanged_artifact_ids: tuple[str, ...]
    changed_counts: dict[str, tuple[int, int]]
    left_accepted: bool
    right_accepted: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineRuntimeStage:
    """One stage in the portable verification runtime."""

    stage_id: str
    ordinal: int
    state: ProgramRuntimeOfflineBundleState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineReplay:
    """Determinism result for two independent offline builds."""

    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def program_runtime_offline_check(
    check_id: str,
    plane: ProgramRuntimeOfflineCheckPlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ProgramRuntimeOfflineCheck:
    """Create one stable handoff check."""

    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramRuntimeOfflineCheck(
        **body,
        content_address=content_hash(body, prefix=PROGRAM_RUNTIME_OFFLINE_CHECK_PREFIX),
    )


__all__ = [
    "PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX",
    "PROGRAM_RUNTIME_OFFLINE_BOUNDARY",
    "PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION",
    "PROGRAM_RUNTIME_OFFLINE_CERTIFICATION_VERSION",
    "PROGRAM_RUNTIME_OFFLINE_CHECK_PREFIX",
    "PROGRAM_RUNTIME_OFFLINE_DEFAULT_LIMIT",
    "PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_HANDOFF_STAGE_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_MANIFEST_FILENAME",
    "PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS",
    "PROGRAM_RUNTIME_OFFLINE_MAX_LIMIT",
    "PROGRAM_RUNTIME_OFFLINE_OPERATION_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_RELEASE_ARTIFACT_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_RECONCILIATION_VERSION",
    "PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT",
    "PROGRAM_RUNTIME_OFFLINE_RUNTIME_VERSION",
    "PROGRAM_RUNTIME_OFFLINE_SCHEMA_VERSION",
    "ProgramRuntimeOfflineArtifact",
    "ProgramRuntimeOfflineArtifactKind",
    "ProgramRuntimeOfflineAudit",
    "ProgramRuntimeOfflineBundle",
    "ProgramRuntimeOfflineBundleState",
    "ProgramRuntimeOfflineCheck",
    "ProgramRuntimeOfflineCheckPlane",
    "ProgramRuntimeOfflineDiff",
    "ProgramRuntimeOfflineQueryResult",
    "ProgramRuntimeOfflineReplay",
    "ProgramRuntimeOfflineRuntimeStage",
    "ProgramRuntimeOfflineVerification",
    "program_runtime_offline_check",
]

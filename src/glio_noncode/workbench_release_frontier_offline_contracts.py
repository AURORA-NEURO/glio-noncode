"""Contracts for the portable D15 workbench-release handoff.

The online workbench runtime deliberately exposes many independently testable
planes.  This module gives an offline consumer a small, strict vocabulary for
those planes: exact-byte artifacts, addressed checks, a root manifest, and
bounded query/diff receipts.  Payloads remain ordinary public aggregate JSON;
the contract never carries a session identity, hidden attribution, or direct
identifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION = "workbench-release-offline-bundle-v1"
WORKBENCH_RELEASE_OFFLINE_SCHEMA_VERSION = "workbench-release-offline-schema-v1"
WORKBENCH_RELEASE_OFFLINE_MANIFEST = "bundle.json"
WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX = "workbench-release-bundle-artifact"
WORKBENCH_RELEASE_OFFLINE_CHECK_PREFIX = "workbench-release-bundle-check"
WORKBENCH_RELEASE_OFFLINE_DEFAULT_LIMIT = 50
WORKBENCH_RELEASE_OFFLINE_MAX_LIMIT = 500
WORKBENCH_RELEASE_OFFLINE_MAX_ARTIFACTS = 80
WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT = 56
WORKBENCH_RELEASE_OFFLINE_BOUNDARY = "public_aggregate_workbench_release_offline_handoff"


class WorkbenchReleaseOfflineBundleState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class WorkbenchReleaseOfflineArtifactKind(StrEnum):
    FIXTURE = "fixture"
    DATA_AUDIT = "data_audit"
    ADAPTERS = "adapters"
    SCHEMA = "schema"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    POLICY = "policy"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    QUALITY = "quality"
    REPLAY = "replay"
    VIEW = "view"
    REVIEW_QUEUE = "review_queue"
    HANDOFF = "handoff"
    INTEGRITY = "integrity"
    DEPTH = "depth"
    CONTROLS = "controls"
    VALIDATION = "validation"
    EVIDENCE = "evidence"
    ACCESS = "access"
    FAILURE_INJECTION = "failure_injection"
    DIAGNOSTICS = "diagnostics"
    ARTIFACTS = "artifacts"
    RELEASE = "release"
    SUMMARY = "summary"
    PROVENANCE = "provenance"
    SOURCE_REGISTRY = "source_registry"
    FRESHNESS = "freshness"
    COMPATIBILITY = "compatibility"
    RELEASE_CHECKS = "release_checks"
    EXECUTION_PLAN = "execution_plan"
    RUN_MANIFEST = "run_manifest"
    AUDIT_LOG = "audit_log"
    TRANSCRIPT = "transcript"
    REPORT = "report"
    REVIEW_CSV = "review_csv"
    DATA_DICTIONARY = "data_dictionary"
    REVIEW_SLA = "review_sla"
    REVIEW_PROTOCOL = "review_protocol"
    CLAIM_BOUNDARY = "claim_boundary"
    RECOVERY = "recovery"
    PERFORMANCE = "performance"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    QUERY = "query"
    PARTITIONS = "partitions"
    SCENARIO = "scenario"
    RESOURCES = "resources"
    BUNDLE = "bundle"
    OBSERVABILITY = "observability"
    RUNTIME = "runtime"
    STAGE_INDEX = "stage_index"
    DENOMINATOR_INDEX = "denominator_index"
    OPERATION_INDEX = "operation_index"
    PUBLIC_KEY_INDEX = "public_key_index"
    FIXTURE_INDEX = "fixture_index"


class WorkbenchReleaseOfflineCheckPlane(StrEnum):
    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    PUBLIC_BOUNDARY = "public_boundary"
    RUNTIME = "runtime"
    DENOMINATOR = "denominator"
    CLOSURE = "closure"
    REPLAY = "replay"
    SCHEMA = "schema"
    INDEX = "index"
    SECURITY = "security"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineArtifact:
    """One materializable payload with an address over its exact UTF-8 bytes."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: WorkbenchReleaseOfflineArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "relative_path", "media_type", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("offline artifact counts cannot be negative")
        if not self.content_address.startswith(f"{WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX}:"):
            raise ValueError("workbench offline artifacts require exact-byte addresses")

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
class WorkbenchReleaseOfflineCheck:
    """A named invariant that makes a bundle auditable without its producer."""

    check_id: str
    plane: WorkbenchReleaseOfflineCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{WORKBENCH_RELEASE_OFFLINE_CHECK_PREFIX}:"):
            raise ValueError("workbench offline checks require addressed check receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineBundle:
    """Root manifest and artifact inventory for a D15 public handoff."""

    bundle_id: str
    version: str
    boundary: str
    fixture_id: str
    run_id: str
    state: WorkbenchReleaseOfflineBundleState
    accepted: bool
    artifacts: tuple[WorkbenchReleaseOfflineArtifact, ...]
    checks: tuple[WorkbenchReleaseOfflineCheck, ...]
    runtime_address: str
    stage_count: int
    warning_count: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "bundle_id",
            "version",
            "boundary",
            "fixture_id",
            "run_id",
            "runtime_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION:
            raise ValueError("unsupported workbench offline bundle version")
        if self.stage_count < 0 or self.warning_count < 0:
            raise ValueError("workbench offline counts cannot be negative")
        if len(self.artifacts) > WORKBENCH_RELEASE_OFFLINE_MAX_ARTIFACTS:
            raise ValueError("workbench offline artifact ceiling exceeded")

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
        return self.state is WorkbenchReleaseOfflineBundleState.READY and self.accepted

    def manifest_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return jsonable(
            {
                "bundle_id": self.bundle_id,
                "version": self.version,
                "boundary": self.boundary,
                "fixture_id": self.fixture_id,
                "run_id": self.run_id,
                "state": self.state,
                "accepted": self.accepted,
                "artifacts": tuple(
                    item.to_dict(include_payload=include_payloads) for item in self.artifacts
                ),
                "checks": tuple(item.to_dict() for item in self.checks),
                "runtime_address": self.runtime_address,
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
class WorkbenchReleaseOfflineVerification:
    bundle_id: str
    accepted: bool
    checks: tuple[WorkbenchReleaseOfflineCheck, ...]
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
class WorkbenchReleaseOfflineQueryResult:
    bundle_id: str
    query: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineDiff:
    left_bundle_id: str
    right_bundle_id: str
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    unchanged_artifact_ids: tuple[str, ...]
    left_accepted: bool
    right_accepted: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def workbench_release_offline_check(
    check_id: str,
    plane: WorkbenchReleaseOfflineCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> WorkbenchReleaseOfflineCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseOfflineCheck(
        **body,
        content_address=content_hash(body, prefix=WORKBENCH_RELEASE_OFFLINE_CHECK_PREFIX),
    )


__all__ = [
    "WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT",
    "WORKBENCH_RELEASE_OFFLINE_ARTIFACT_PREFIX",
    "WORKBENCH_RELEASE_OFFLINE_BOUNDARY",
    "WORKBENCH_RELEASE_OFFLINE_CHECK_PREFIX",
    "WORKBENCH_RELEASE_OFFLINE_DEFAULT_LIMIT",
    "WORKBENCH_RELEASE_OFFLINE_MANIFEST",
    "WORKBENCH_RELEASE_OFFLINE_MAX_ARTIFACTS",
    "WORKBENCH_RELEASE_OFFLINE_MAX_LIMIT",
    "WORKBENCH_RELEASE_OFFLINE_SCHEMA_VERSION",
    "WORKBENCH_RELEASE_OFFLINE_BUNDLE_VERSION",
    "WorkbenchReleaseOfflineArtifact",
    "WorkbenchReleaseOfflineArtifactKind",
    "WorkbenchReleaseOfflineBundle",
    "WorkbenchReleaseOfflineBundleState",
    "WorkbenchReleaseOfflineCheck",
    "WorkbenchReleaseOfflineCheckPlane",
    "WorkbenchReleaseOfflineDiff",
    "WorkbenchReleaseOfflineQueryResult",
    "WorkbenchReleaseOfflineVerification",
    "workbench_release_offline_check",
]

"""Portable contracts for the D16 deployment-governance handoff.

The deployment frontier is useful only when a reviewer can move the result
between machines without importing the producer process.  These contracts
define that transfer boundary.  Every payload is addressed over its exact
UTF-8 bytes, every check is independently addressable, and the root manifest
contains enough information to verify the handoff without trusting a runtime
clock or a mutable database.

The contract is intentionally aggregate-only.  It does not model an
individual, a secret, a credential, a model, or an attribution record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION = "deployment-frontier-offline-bundle-v1"
DEPLOYMENT_FRONTIER_OFFLINE_SCHEMA_VERSION = "deployment-frontier-offline-schema-v1"
DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST = "bundle.json"
DEPLOYMENT_FRONTIER_OFFLINE_BOUNDARY = "public_aggregate_deployment_offline_handoff"
DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX = "deployment-frontier-offline-artifact"
DEPLOYMENT_FRONTIER_OFFLINE_CHECK_PREFIX = "deployment-frontier-offline-check"
DEPLOYMENT_FRONTIER_OFFLINE_RUNTIME_VERSION = "deployment-frontier-offline-runtime-v1"
DEPLOYMENT_FRONTIER_OFFLINE_RECONCILIATION_VERSION = "deployment-frontier-offline-reconciliation-v1"
DEPLOYMENT_FRONTIER_OFFLINE_CERTIFICATION_VERSION = "deployment-frontier-offline-certification-v1"
DEPLOYMENT_FRONTIER_OFFLINE_DEFAULT_LIMIT = 50
DEPLOYMENT_FRONTIER_OFFLINE_MAX_LIMIT = 500
DEPLOYMENT_FRONTIER_OFFLINE_MAX_ARTIFACTS = 80

# These are the source runtime denominators.  Keeping them in the contract
# makes a changed fixture fail loudly instead of silently shrinking a handoff.
DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT = 5
DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT = 16
DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT = 4
DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT = 12
DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT = 4
DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT = 16
DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT = 80
DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT = 38
DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT = 51


class DeploymentFrontierOfflineBundleState(StrEnum):
    """Lifecycle states used by the portable handoff."""

    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class DeploymentFrontierOfflineArtifactKind(StrEnum):
    """Stable inventory categories for D16 payloads."""

    FIXTURE = "fixture"
    RUNTIME = "runtime"
    AUDIT = "audit"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    POLICY = "policy"
    SCHEMA = "schema"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    QUALITY = "quality"
    REPLAY = "replay"
    RELEASE = "release"
    ARTIFACTS = "artifacts"
    SUMMARY = "summary"
    VIEW = "view"
    REVIEW_QUEUE = "review_queue"
    REVIEW_SLA = "review_sla"
    HANDOFF = "handoff"
    INTEGRITY = "integrity"
    DEPTH = "depth"
    OPERATIONAL = "operational"
    PERFORMANCE = "performance"
    ASSURANCE = "assurance"
    FAILURE_INJECTION = "failure_injection"
    COMPLIANCE = "compliance"
    DIAGNOSTICS = "diagnostics"
    EXECUTION_PLAN = "execution_plan"
    THRESHOLDS = "thresholds"
    VALIDATION = "validation"
    ACCESS = "access"
    COMPATIBILITY = "compatibility"
    RELEASE_CHECKS = "release_checks"
    RUNBOOK = "runbook"
    FRESHNESS = "freshness"
    AUDIT_LOG = "audit_log"
    TRANSCRIPT = "transcript"
    PACKAGE = "package"
    BUNDLE = "bundle"
    OBSERVABILITY = "observability"
    STAGE_INDEX = "stage_index"
    DENOMINATOR_INDEX = "denominator_index"
    OPERATION_INDEX = "operation_index"
    PUBLIC_KEY_INDEX = "public_key_index"
    FIXTURE_INDEX = "fixture_index"
    ISSUE_INDEX = "issue_index"
    STATE_INDEX = "state_index"
    REVIEW_CSV = "review_csv"
    SOURCES_CSV = "sources_csv"
    EXECUTIONS_CSV = "executions_csv"
    DATA_DICTIONARY = "data_dictionary"
    CAPABILITY_MAP = "capability_map"


class DeploymentFrontierOfflineCheckPlane(StrEnum):
    """Assurance planes represented by independent check receipts."""

    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    DENOMINATOR = "denominator"
    EVALUATION = "evaluation"
    RUNTIME = "runtime"
    INDEX = "index"
    PUBLIC_BOUNDARY = "public_boundary"
    CLOSURE = "closure"
    REPLAY = "replay"
    SCHEMA = "schema"
    SECURITY = "security"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineArtifact:
    """One exact-byte payload in a portable handoff."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: DeploymentFrontierOfflineArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "relative_path", "media_type", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("offline artifact counts cannot be negative")
        if not self.content_address.startswith(f"{DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX}:"):
            raise ValueError("deployment offline artifacts require exact-byte addresses")

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
class DeploymentFrontierOfflineCheck:
    """A named invariant that can be audited without producer state."""

    check_id: str
    plane: DeploymentFrontierOfflineCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{DEPLOYMENT_FRONTIER_OFFLINE_CHECK_PREFIX}:"):
            raise ValueError("deployment offline checks require addressed receipts")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineBundle:
    """Root identity and immutable inventory for D16."""

    bundle_id: str
    version: str
    boundary: str
    fixture_id: str
    run_id: str
    state: DeploymentFrontierOfflineBundleState
    accepted: bool
    artifacts: tuple[DeploymentFrontierOfflineArtifact, ...]
    checks: tuple[DeploymentFrontierOfflineCheck, ...]
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
        if self.version != DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION:
            raise ValueError("unsupported deployment offline bundle version")
        if self.stage_count < 0 or self.warning_count < 0:
            raise ValueError("deployment offline counts cannot be negative")
        if len(self.artifacts) > DEPLOYMENT_FRONTIER_OFFLINE_MAX_ARTIFACTS:
            raise ValueError("deployment offline artifact ceiling exceeded")

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
        return self.state is DeploymentFrontierOfflineBundleState.READY and self.accepted

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
class DeploymentFrontierOfflineVerification:
    """Result of checking a filesystem handoff."""

    bundle_id: str
    accepted: bool
    checks: tuple[DeploymentFrontierOfflineCheck, ...]
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
class DeploymentFrontierOfflineQueryResult:
    """Bounded query result with a reproducible query receipt."""

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
class DeploymentFrontierOfflineDiff:
    """Artifact-level comparison between two manifests."""

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


def deployment_frontier_offline_check(
    check_id: str,
    plane: DeploymentFrontierOfflineCheckPlane | str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> DeploymentFrontierOfflineCheck:
    """Create a content-addressed check without leaking mutable state."""

    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineCheck(
        **body,
        content_address=content_hash(body, prefix=DEPLOYMENT_FRONTIER_OFFLINE_CHECK_PREFIX),
    )


__all__ = [
    "DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_PREFIX",
    "DEPLOYMENT_FRONTIER_OFFLINE_BOUNDARY",
    "DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION",
    "DEPLOYMENT_FRONTIER_OFFLINE_CERTIFICATION_VERSION",
    "DEPLOYMENT_FRONTIER_OFFLINE_CHECK_PREFIX",
    "DEPLOYMENT_FRONTIER_OFFLINE_CONTROL_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_DEFAULT_LIMIT",
    "DEPLOYMENT_FRONTIER_OFFLINE_EVALUATION_CHECK_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST",
    "DEPLOYMENT_FRONTIER_OFFLINE_MAX_ARTIFACTS",
    "DEPLOYMENT_FRONTIER_OFFLINE_MAX_LIMIT",
    "DEPLOYMENT_FRONTIER_OFFLINE_OPERATION_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_POSITIVE_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_RECONCILIATION_VERSION",
    "DEPLOYMENT_FRONTIER_OFFLINE_RUNTIME_VERSION",
    "DEPLOYMENT_FRONTIER_OFFLINE_SCHEMA_VERSION",
    "DEPLOYMENT_FRONTIER_OFFLINE_SOURCE_COUNT",
    "DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT",
    "DeploymentFrontierOfflineArtifact",
    "DeploymentFrontierOfflineArtifactKind",
    "DeploymentFrontierOfflineBundle",
    "DeploymentFrontierOfflineBundleState",
    "DeploymentFrontierOfflineCheck",
    "DeploymentFrontierOfflineCheckPlane",
    "DeploymentFrontierOfflineDiff",
    "DeploymentFrontierOfflineQueryResult",
    "DeploymentFrontierOfflineVerification",
    "deployment_frontier_offline_check",
]

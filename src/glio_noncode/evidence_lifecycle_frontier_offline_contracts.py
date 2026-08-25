"""Contracts for the portable D14 evidence lifecycle handoff.

The in-memory D14 runtime is intentionally rich, but an offline consumer
should not need to import the producer or reconstruct private state.  These
contracts describe a closed manifest whose artifacts are addressed by their
exact UTF-8 bytes and whose checks preserve the public aggregate boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION = "evidence-lifecycle-offline-bundle-v1"
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_SCHEMA_VERSION = "evidence-lifecycle-offline-schema-v1"
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST = "bundle.json"
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX = "evidence-lifecycle-bundle-artifact"
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_CHECK_PREFIX = "evidence-lifecycle-bundle-check"
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_DEFAULT_LIMIT = 50
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_LIMIT = 500
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_ARTIFACTS = 32
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT = 21
EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY = "public_aggregate_non_patient_offline_handoff"


class EvidenceLifecycleOfflineBundleState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class EvidenceLifecycleOfflineArtifactKind(StrEnum):
    FIXTURE = "fixture"
    CATALOG = "catalog"
    DATA_AUDIT = "data_audit"
    CONTRACTS = "contracts"
    SCHEMA = "schema"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    POLICY = "policy"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    QUALITY = "quality"
    BUNDLE = "bundle"
    REPLAY = "replay"
    RELEASE = "release"
    REVIEW = "review"
    REVIEW_QUEUE = "review_queue"
    ARTIFACTS = "artifacts"
    SCENARIO_MATRIX = "scenario_matrix"
    OBSERVABILITY = "observability"
    REVIEW_CSV = "review_csv"
    RUNTIME = "runtime"


class EvidenceLifecycleOfflineCheckPlane(StrEnum):
    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    PUBLIC_BOUNDARY = "public_boundary"
    RUNTIME = "runtime"
    CLOSURE = "closure"
    REPLAY = "replay"
    SCHEMA = "schema"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineArtifact:
    artifact_id: str
    relative_path: str
    media_type: str
    kind: EvidenceLifecycleOfflineArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "relative_path", "media_type", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("offline artifact counts cannot be negative")
        if not self.content_address.startswith(f"{EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX}:"):
            raise ValueError("offline artifacts require exact-byte addresses")

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
class EvidenceLifecycleOfflineCheck:
    check_id: str
    plane: EvidenceLifecycleOfflineCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")
        if not self.content_address.startswith(f"{EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_CHECK_PREFIX}:"):
            raise ValueError("offline checks require bundle-check addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineBundle:
    bundle_id: str
    version: str
    boundary: str
    fixture_id: str
    run_id: str
    state: EvidenceLifecycleOfflineBundleState
    accepted: bool
    artifacts: tuple[EvidenceLifecycleOfflineArtifact, ...]
    checks: tuple[EvidenceLifecycleOfflineCheck, ...]
    runtime_address: str
    warning_count: int
    content_address: str

    def __post_init__(self) -> None:
        for name in ("bundle_id", "version", "boundary", "fixture_id", "run_id", "runtime_address", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION:
            raise ValueError("unsupported evidence lifecycle offline bundle version")
        if self.warning_count < 0:
            raise ValueError("offline bundle warning count cannot be negative")
        if len(self.artifacts) > EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_ARTIFACTS:
            raise ValueError("offline bundle artifact ceiling exceeded")

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
        return self.state is EvidenceLifecycleOfflineBundleState.READY and self.accepted

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
                "artifacts": tuple(item.to_dict(include_payload=include_payloads) for item in self.artifacts),
                "checks": tuple(item.to_dict() for item in self.checks),
                "runtime_address": self.runtime_address,
                "warning_count": self.warning_count,
                "artifact_count": self.artifact_count,
                "passed_check_count": self.passed_check_count,
                "failed_check_count": self.failed_check_count,
            }
        )

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return self.manifest_dict(include_payloads=include_payloads) | {"content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineVerification:
    bundle_id: str
    accepted: bool
    checks: tuple[EvidenceLifecycleOfflineCheck, ...]
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
class EvidenceLifecycleOfflineQueryResult:
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
class EvidenceLifecycleOfflineDiff:
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


def evidence_lifecycle_offline_check(
    check_id: str,
    plane: EvidenceLifecycleOfflineCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> EvidenceLifecycleOfflineCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return EvidenceLifecycleOfflineCheck(
        **body,
        content_address=content_hash(body, prefix=EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_CHECK_PREFIX),
    )


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_PREFIX",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_BOUNDARY",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_CHECK_PREFIX",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_DEFAULT_LIMIT",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_ARTIFACTS",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_LIMIT",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_SCHEMA_VERSION",
    "EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION",
    "EvidenceLifecycleOfflineArtifact",
    "EvidenceLifecycleOfflineArtifactKind",
    "EvidenceLifecycleOfflineBundle",
    "EvidenceLifecycleOfflineBundleState",
    "EvidenceLifecycleOfflineCheck",
    "EvidenceLifecycleOfflineCheckPlane",
    "EvidenceLifecycleOfflineDiff",
    "EvidenceLifecycleOfflineQueryResult",
    "EvidenceLifecycleOfflineVerification",
    "evidence_lifecycle_offline_check",
]

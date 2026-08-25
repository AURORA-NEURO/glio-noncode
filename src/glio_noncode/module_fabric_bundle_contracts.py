"""Contracts for the portable module-fabric release bundle.

The module-fabric runtime already proves that the repository capability ledger
can be resolved in memory.  These contracts describe the next boundary: a
directory that can be copied, inspected, and verified without importing the
producer.  The bundle contains only public aggregate projections and exact
byte receipts; it never embeds raw subject fields or execution attribution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

MODULE_FABRIC_BUNDLE_VERSION = "module-fabric-bundle-v1"
MODULE_FABRIC_BUNDLE_MANIFEST = "bundle.json"
MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX = "module-fabric-bundle-artifact"
MODULE_FABRIC_BUNDLE_DEFAULT_LIMIT = 50
MODULE_FABRIC_BUNDLE_MAX_LIMIT = 500
MODULE_FABRIC_BUNDLE_MAX_ARTIFACTS = 64


class FabricBundleState(StrEnum):
    """Lifecycle state for a materialized module-fabric bundle."""

    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class FabricBundleArtifactKind(StrEnum):
    """Stable artifact facets available to offline consumers."""

    FIXTURE = "fixture"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    DEPTH = "depth"
    LINEAGE = "lineage"
    REPLAY = "replay"
    QUALITY = "quality"
    RELEASE = "release"
    RUNTIME = "runtime"
    COMPLIANCE = "compliance"
    CATALOG = "catalog"
    SCHEMA = "schema"
    DICTIONARY = "dictionary"
    SOURCES = "sources"
    SUMMARY = "summary"
    REVIEW = "review"
    CHECKS = "checks"
    REPORT = "report"


class FabricBundleCheckPlane(StrEnum):
    """Verification plane retained in the bundle manifest."""

    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    PUBLIC_BOUNDARY = "public_boundary"
    CLOSURE = "closure"
    RUNTIME = "runtime"
    SCHEMA = "schema"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class FabricBundleCheck:
    """One deterministic assertion over the bundle boundary."""

    check_id: str
    plane: FabricBundleCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("check_id", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address.startswith("module-fabric-bundle-check:"):
            raise ValueError("bundle checks require module-fabric-bundle-check addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricBundleArtifact:
    """One exact UTF-8 artifact in the offline bundle."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: FabricBundleArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "artifact_id",
            "relative_path",
            "media_type",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("bundle artifact counts cannot be negative")
        if not self.content_address.startswith(f"{MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX}:"):
            raise ValueError("bundle artifacts require bundle artifact addresses")

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        body = {
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "kind": self.kind,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload and self.payload is not None:
            body["payload"] = self.payload
        return jsonable(body)


@dataclass(frozen=True, slots=True)
class FabricBundle:
    """Complete in-memory representation of a portable module-fabric handoff."""

    bundle_id: str
    version: str
    boundary: str
    fixture_id: str
    run_id: str
    state: FabricBundleState
    accepted: bool
    artifacts: tuple[FabricBundleArtifact, ...]
    checks: tuple[FabricBundleCheck, ...]
    runtime_address: str
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
        if self.version != MODULE_FABRIC_BUNDLE_VERSION:
            raise ValueError("unsupported module-fabric bundle version")
        if self.warning_count < 0:
            raise ValueError("bundle warning count cannot be negative")
        if len(self.artifacts) > MODULE_FABRIC_BUNDLE_MAX_ARTIFACTS:
            raise ValueError("module-fabric bundle artifact ceiling exceeded")

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
        return self.state is FabricBundleState.READY and self.accepted

    def manifest_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return jsonable({
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
        })

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return self.manifest_dict(include_payloads=include_payloads) | {
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class FabricBundleVerification:
    """Result of verifying a bundle directory or in-memory manifest."""

    bundle_id: str
    accepted: bool
    checks: tuple[FabricBundleCheck, ...]
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
class FabricBundleQueryResult:
    """Bounded query response over artifact or record projections."""

    bundle_id: str
    query: Mapping[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[Mapping[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FabricBundleDiff:
    """Structural comparison of two verified bundle manifests."""

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


def bundle_check(
    check_id: str,
    plane: FabricBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> FabricBundleCheck:
    """Create an addressed bundle check from its public fields."""

    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricBundleCheck(
        **body,
        content_address=content_hash(body, prefix="module-fabric-bundle-check"),
    )


__all__ = [
    "FabricBundle",
    "FabricBundleArtifact",
    "FabricBundleArtifactKind",
    "FabricBundleCheck",
    "FabricBundleCheckPlane",
    "FabricBundleDiff",
    "FabricBundleQueryResult",
    "FabricBundleState",
    "FabricBundleVerification",
    "MODULE_FABRIC_BUNDLE_ARTIFACT_PREFIX",
    "MODULE_FABRIC_BUNDLE_DEFAULT_LIMIT",
    "MODULE_FABRIC_BUNDLE_MANIFEST",
    "MODULE_FABRIC_BUNDLE_MAX_ARTIFACTS",
    "MODULE_FABRIC_BUNDLE_MAX_LIMIT",
    "MODULE_FABRIC_BUNDLE_VERSION",
    "bundle_check",
]

"""Contracts for the portable live capability-certification handoff.

The certification runtime is a repository-evidence surface over the complete
256-row catalog.  These contracts turn that runtime into a process-independent
directory without changing the source report.  The bundle retains row and
global checks, exact artifact addresses, and blocked diagnostics while
excluding private identifiers and execution-attribution metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

CAPABILITY_CERTIFICATION_BUNDLE_VERSION = "capability-certification-bundle-v1"
CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY = "public_repository_capability_certification"
CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST = "bundle.json"
CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX = "capability-certification-bundle-artifact"
CAPABILITY_CERTIFICATION_BUNDLE_CHECK_PREFIX = "capability-certification-bundle-check"
CAPABILITY_CERTIFICATION_BUNDLE_DEFAULT_LIMIT = 50
CAPABILITY_CERTIFICATION_BUNDLE_MAX_LIMIT = 500
CAPABILITY_CERTIFICATION_BUNDLE_MAX_ARTIFACTS = 32


class CertificationBundleState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class CertificationBundleArtifactKind(StrEnum):
    REPORT = "report"
    SUMMARY = "summary"
    CERTIFICATES = "certificates"
    CHECKS = "checks"
    DOMAINS = "domains"
    RUNTIME = "runtime"
    QUALITY = "quality"
    REPLAY = "replay"
    FAILURES = "failures"
    CATALOG = "catalog"
    OBSERVABILITY = "observability"
    MARKDOWN = "markdown"


class CertificationBundleCheckPlane(StrEnum):
    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    PUBLIC_BOUNDARY = "public_boundary"
    CLOSURE = "closure"
    CERTIFICATION = "certification"
    SCHEMA = "schema"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class CertificationBundleCheck:
    check_id: str
    plane: CertificationBundleCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("check_id", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address.startswith(f"{CAPABILITY_CERTIFICATION_BUNDLE_CHECK_PREFIX}:"):
            raise ValueError("certification bundle checks require bundle-check addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CertificationBundleArtifact:
    artifact_id: str
    relative_path: str
    media_type: str
    kind: CertificationBundleArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "relative_path", "media_type", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("certification artifact counts cannot be negative")
        if not self.content_address.startswith(f"{CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX}:"):
            raise ValueError("certification artifacts require bundle artifact addresses")

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
class CapabilityCertificationBundle:
    bundle_id: str
    version: str
    boundary: str
    report_id: str
    run_id: str
    catalog_address: str
    runtime_address: str
    state: CertificationBundleState
    accepted: bool
    artifacts: tuple[CertificationBundleArtifact, ...]
    checks: tuple[CertificationBundleCheck, ...]
    certificate_count: int
    domain_count: int
    total_checks: int
    passed_check_count: int
    failed_check_count: int
    warning_count: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "bundle_id",
            "version",
            "boundary",
            "report_id",
            "run_id",
            "catalog_address",
            "runtime_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.version != CAPABILITY_CERTIFICATION_BUNDLE_VERSION:
            raise ValueError("unsupported capability certification bundle version")
        if min(
            self.certificate_count,
            self.domain_count,
            self.total_checks,
            self.passed_check_count,
            self.failed_check_count,
            self.warning_count,
        ) < 0:
            raise ValueError("certification bundle counts cannot be negative")
        if len(self.artifacts) > CAPABILITY_CERTIFICATION_BUNDLE_MAX_ARTIFACTS:
            raise ValueError("capability certification artifact ceiling exceeded")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def ready(self) -> bool:
        return self.state is CertificationBundleState.READY and self.accepted

    def manifest_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return jsonable(
            {
                "bundle_id": self.bundle_id,
                "version": self.version,
                "boundary": self.boundary,
                "report_id": self.report_id,
                "run_id": self.run_id,
                "catalog_address": self.catalog_address,
                "runtime_address": self.runtime_address,
                "state": self.state,
                "accepted": self.accepted,
                "artifacts": tuple(item.to_dict(include_payload=include_payloads) for item in self.artifacts),
                "checks": tuple(item.to_dict() for item in self.checks),
                "certificate_count": self.certificate_count,
                "domain_count": self.domain_count,
                "total_checks": self.total_checks,
                "passed_check_count": self.passed_check_count,
                "failed_check_count": self.failed_check_count,
                "warning_count": self.warning_count,
                "artifact_count": self.artifact_count,
            }
        )

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return self.manifest_dict(include_payloads=include_payloads) | {
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CertificationBundleVerification:
    bundle_id: str
    accepted: bool
    checks: tuple[CertificationBundleCheck, ...]
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
class CertificationBundleQueryResult:
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
class CertificationBundleDiff:
    left_bundle_id: str
    right_bundle_id: str
    added_capability_ids: tuple[str, ...]
    removed_capability_ids: tuple[str, ...]
    changed_capability_ids: tuple[str, ...]
    unchanged_capability_ids: tuple[str, ...]
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    left_accepted: bool
    right_accepted: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def certification_bundle_check(
    check_id: str,
    plane: CertificationBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CertificationBundleCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CertificationBundleCheck(
        **body,
        content_address=content_hash(body, prefix=CAPABILITY_CERTIFICATION_BUNDLE_CHECK_PREFIX),
    )


__all__ = [
    "CAPABILITY_CERTIFICATION_BUNDLE_ARTIFACT_PREFIX",
    "CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY",
    "CAPABILITY_CERTIFICATION_BUNDLE_CHECK_PREFIX",
    "CAPABILITY_CERTIFICATION_BUNDLE_DEFAULT_LIMIT",
    "CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST",
    "CAPABILITY_CERTIFICATION_BUNDLE_MAX_ARTIFACTS",
    "CAPABILITY_CERTIFICATION_BUNDLE_MAX_LIMIT",
    "CAPABILITY_CERTIFICATION_BUNDLE_VERSION",
    "CapabilityCertificationBundle",
    "CertificationBundleArtifact",
    "CertificationBundleArtifactKind",
    "CertificationBundleCheck",
    "CertificationBundleCheckPlane",
    "CertificationBundleDiff",
    "CertificationBundleQueryResult",
    "CertificationBundleState",
    "CertificationBundleVerification",
    "certification_bundle_check",
]

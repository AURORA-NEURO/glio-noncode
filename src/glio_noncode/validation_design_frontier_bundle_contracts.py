"""Contracts for the portable D13 validation-design handoff.

The validation-design frontier already has a deep in-memory runtime. These
contracts make its public aggregate evidence portable: every artifact is
addressed by its exact UTF-8 bytes and every manifest assertion is retained so
an offline consumer can verify the handoff without importing the producer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty

VALIDATION_DESIGN_BUNDLE_VERSION = "validation-design-bundle-v1"
VALIDATION_DESIGN_BUNDLE_MANIFEST = "bundle.json"
VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX = "validation-design-bundle-artifact"
VALIDATION_DESIGN_BUNDLE_DEFAULT_LIMIT = 50
VALIDATION_DESIGN_BUNDLE_MAX_LIMIT = 500
VALIDATION_DESIGN_BUNDLE_MAX_ARTIFACTS = 32


class ValidationDesignBundleState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class ValidationDesignBundleArtifactKind(StrEnum):
    FIXTURE = "fixture"
    AUDIT = "audit"
    ADAPTERS = "adapters"
    SCHEMA = "schema"
    EVALUATION = "evaluation"
    METRICS = "metrics"
    POLICY = "policy"
    LINEAGE = "lineage"
    RECONCILIATION = "reconciliation"
    QUALITY = "quality"
    REPLAY = "replay"
    REVIEW = "review"
    HANDOFF = "handoff"
    INTEGRITY = "integrity"
    DEPTH = "depth"
    VALIDATION = "validation"
    EVIDENCE = "evidence"
    ACCESS = "access"
    FAILURE_INJECTION = "failure_injection"
    DIAGNOSTICS = "diagnostics"
    RELEASE = "release"
    SUMMARY = "summary"
    DATA_DICTIONARY = "data_dictionary"
    OBSERVABILITY = "observability"
    REPORT = "report"
    REVIEW_CSV = "review_csv"
    RUNTIME = "runtime"


class ValidationDesignBundleCheckPlane(StrEnum):
    MANIFEST = "manifest"
    ARTIFACT = "artifact"
    PUBLIC_BOUNDARY = "public_boundary"
    CLOSURE = "closure"
    RUNTIME = "runtime"
    SCHEMA = "schema"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleCheck:
    check_id: str
    plane: ValidationDesignBundleCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("check_id", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.content_address.startswith("validation-design-bundle-check:"):
            raise ValueError("validation-design bundle checks require bundle-check addresses")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleArtifact:
    artifact_id: str
    relative_path: str
    media_type: str
    kind: ValidationDesignBundleArtifactKind
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "relative_path", "media_type", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.byte_count < 0 or self.line_count < 0:
            raise ValueError("validation-design artifact counts cannot be negative")
        if not self.content_address.startswith(f"{VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX}:"):
            raise ValueError("validation-design artifacts require exact-byte addresses")

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
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
class ValidationDesignBundle:
    bundle_id: str
    version: str
    boundary: str
    fixture_id: str
    run_id: str
    state: ValidationDesignBundleState
    accepted: bool
    artifacts: tuple[ValidationDesignBundleArtifact, ...]
    checks: tuple[ValidationDesignBundleCheck, ...]
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
        if self.version != VALIDATION_DESIGN_BUNDLE_VERSION:
            raise ValueError("unsupported validation-design bundle version")
        if self.warning_count < 0:
            raise ValueError("validation-design warning count cannot be negative")
        if len(self.artifacts) > VALIDATION_DESIGN_BUNDLE_MAX_ARTIFACTS:
            raise ValueError("validation-design bundle artifact ceiling exceeded")

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
        return self.state is ValidationDesignBundleState.READY and self.accepted

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
        return self.manifest_dict(include_payloads=include_payloads) | {
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleVerification:
    bundle_id: str
    accepted: bool
    checks: tuple[ValidationDesignBundleCheck, ...]
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
class ValidationDesignBundleQueryResult:
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
class ValidationDesignBundleDiff:
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


def validation_design_bundle_check(
    check_id: str,
    plane: ValidationDesignBundleCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ValidationDesignBundleCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ValidationDesignBundleCheck(
        **body,
        content_address=content_hash(body, prefix="validation-design-bundle-check"),
    )


__all__ = [
    "VALIDATION_DESIGN_BUNDLE_ARTIFACT_PREFIX",
    "VALIDATION_DESIGN_BUNDLE_DEFAULT_LIMIT",
    "VALIDATION_DESIGN_BUNDLE_MANIFEST",
    "VALIDATION_DESIGN_BUNDLE_MAX_ARTIFACTS",
    "VALIDATION_DESIGN_BUNDLE_MAX_LIMIT",
    "VALIDATION_DESIGN_BUNDLE_VERSION",
    "ValidationDesignBundle",
    "ValidationDesignBundleArtifact",
    "ValidationDesignBundleArtifactKind",
    "ValidationDesignBundleCheck",
    "ValidationDesignBundleCheckPlane",
    "ValidationDesignBundleDiff",
    "ValidationDesignBundleQueryResult",
    "ValidationDesignBundleState",
    "ValidationDesignBundleVerification",
    "validation_design_bundle_check",
]

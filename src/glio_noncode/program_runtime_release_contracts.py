"""Contracts for the portable architecture-program release bundle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty


class ProgramReleaseState(StrEnum):
    """Publication state for a portable program release."""

    REVIEW = "review"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class ProgramArtifactKind(StrEnum):
    """Stable artifact roles in the offline release set."""

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


class ProgramReleaseCheckCategory(StrEnum):
    """Validation planes used by the release gate."""

    RUNTIME = "runtime"
    INVENTORY = "inventory"
    INTEGRITY = "integrity"
    PUBLIC_BOUNDARY = "public_boundary"
    REPLAY = "replay"
    FAILURE_CONTROL = "failure_control"
    PORTABILITY = "portability"


@dataclass(frozen=True, slots=True)
class ProgramReleaseArtifact:
    """Metadata for one text artifact without embedding its content."""

    artifact_id: str
    kind: ProgramArtifactKind
    filename: str
    media_type: str
    content_address: str
    byte_count: int
    line_count: int
    required: bool
    public_aggregate: bool

    def __post_init__(self) -> None:
        for field in ("artifact_id", "filename", "media_type", "content_address"):
            require_non_empty(str(getattr(self, field)), field)
        if self.byte_count < 1 or self.line_count < 1 or ":" not in self.content_address:
            raise ValueError("release artifacts require positive dimensions and an address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseCheck:
    """One addressed release assertion."""

    check_id: str
    category: ProgramReleaseCheckCategory
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramReleaseManifest:
    """Portable inventory that can be reopened without Python objects."""

    release_id: str
    runtime_address: str
    report_address: str
    artifact_count: int
    artifact_ids: tuple[str, ...]
    artifact_filenames: tuple[str, ...]
    state: ProgramReleaseState
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.release_id, "release_id")
        require_non_empty(self.runtime_address, "runtime_address")
        require_non_empty(self.report_address, "report_address")
        if self.artifact_count != len(self.artifact_ids) or self.artifact_count != len(
            self.artifact_filenames
        ):
            raise ValueError("manifest artifact count does not match its inventory")
        if len(set(self.artifact_ids)) != len(self.artifact_ids):
            raise ValueError("manifest artifact IDs must be unique")
        if len(set(self.artifact_filenames)) != len(self.artifact_filenames):
            raise ValueError("manifest artifact filenames must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ProgramReleaseManifest:
        return cls(
            release_id=str(value["release_id"]),
            runtime_address=str(value["runtime_address"]),
            report_address=str(value["report_address"]),
            artifact_count=int(value["artifact_count"]),
            artifact_ids=tuple(str(item) for item in value["artifact_ids"]),
            artifact_filenames=tuple(str(item) for item in value["artifact_filenames"]),
            state=ProgramReleaseState(value["state"]),
            content_address=str(value["content_address"]),
        )


@dataclass(frozen=True, slots=True)
class ProgramRelease:
    """Addressable release descriptor and its complete artifact inventory."""

    release_id: str
    runtime_address: str
    report_address: str
    manifest: ProgramReleaseManifest
    artifacts: tuple[ProgramReleaseArtifact, ...]
    checks: tuple[ProgramReleaseCheck, ...]
    state: ProgramReleaseState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is ProgramReleaseState.PUBLISHED

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "runtime_address": self.runtime_address,
            "report_address": self.report_address,
            "manifest": self.manifest.to_dict(),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "checks": [item.to_dict() for item in self.checks],
            "state": self.state.value,
            "accepted": self.accepted,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ProgramReleaseVerification:
    """Filesystem verification receipt for a reopened release directory."""

    root: str
    manifest_address: str
    checks: tuple[ProgramReleaseCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "manifest_address": self.manifest_address,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "content_address": self.content_address,
        }


def addressed(value: Any, prefix: str) -> str:
    """Return a stable semantic address for release metadata."""

    return content_hash(jsonable(value), prefix=prefix)


__all__ = [
    "ProgramArtifactKind",
    "ProgramRelease",
    "ProgramReleaseArtifact",
    "ProgramReleaseCheck",
    "ProgramReleaseCheckCategory",
    "ProgramReleaseManifest",
    "ProgramReleaseState",
    "ProgramReleaseVerification",
    "addressed",
]

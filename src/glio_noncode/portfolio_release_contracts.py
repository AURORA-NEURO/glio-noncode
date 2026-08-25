"""Typed contracts for repository-wide portfolio release packages.

The single-run, batch, and workspace release surfaces are intentionally
independent.  A portfolio handoff needs a fourth boundary: it must preserve
the identity and gate evidence for many runs without silently flattening their
different histories into one optimistic status.  This module contains only
immutable public contracts.  Assembly, filesystem I/O, and query behavior live
in the neighboring portfolio-release modules.

All addresses in these contracts identify either canonical JSON values or exact
UTF-8 artifact bytes.  Payloads are optional at serialization time so callers
can publish a compact manifest while still retaining a fully portable bundle in
memory or on disk.  No raw private subject identifiers are accepted by the
release boundary; callers must apply their source-specific public projection
before constructing an artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable

PORTFOLIO_RELEASE_VERSION = "portfolio-release-v1"
PORTFOLIO_RELEASE_MANIFEST = "release.json"
PORTFOLIO_RELEASE_ARTIFACT_PREFIX = "portfolio-release-artifact"
PORTFOLIO_RELEASE_CHECK_PREFIX = "portfolio-release-check"
PORTFOLIO_RELEASE_DEFAULT_MAX_RUNS = 25
PORTFOLIO_RELEASE_MAX_RUNS = 100


class PortfolioReleaseState(StrEnum):
    """Lifecycle state for a cross-run package."""

    READY = "ready"
    BLOCKED = "blocked"
    EMPTY = "empty"


class PortfolioArtifactKind(StrEnum):
    """Stable categories used by artifact queries and review projections."""

    PORTFOLIO = "portfolio"
    SUMMARY = "summary"
    REVIEW = "review"
    DOSSIER = "dossier"
    WORKSPACE = "workspace"
    EVENTS = "events"
    RELEASE_GATE = "release_gate"
    CSV = "csv"
    MARKDOWN = "markdown"
    MEMBER = "member"


@dataclass(frozen=True, slots=True)
class PortfolioReleaseCheck:
    """One explicit repository-wide release observation."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    scope: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "observed": jsonable(self.observed),
            "required": jsonable(self.required),
            "detail": self.detail,
            "scope": self.scope,
            "content_address": self.content_address,
        }

    @property
    def failed(self) -> bool:
        """Return whether this check contributes a release blocker."""

        return not self.passed


@dataclass(frozen=True, slots=True)
class PortfolioReleaseArtifact:
    """One exact-byte artifact in a namespaced portfolio directory."""

    artifact_id: str
    relative_path: str
    media_type: str
    kind: PortfolioArtifactKind
    member_run_id: str | None
    byte_count: int
    line_count: int
    content_address: str
    payload: str

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "kind": self.kind.value,
            "member_run_id": self.member_run_id,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload:
            body["payload"] = self.payload
        return body

    @property
    def is_json(self) -> bool:
        """Return whether the artifact is subject to JSON boundary checks."""

        return self.media_type == "application/json"


@dataclass(frozen=True, slots=True)
class PortfolioReleaseMember:
    """Public status and artifact index for one selected run."""

    run_id: str
    case_id: str
    dossier_address: str | None
    workspace_history_address: str | None
    dossier_release_id: str | None
    workspace_release_id: str | None
    dossier_state: str
    workspace_state: str
    state: PortfolioReleaseState
    accepted: bool
    artifact_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    @property
    def ready(self) -> bool:
        """Return whether this member is independently release-ready."""

        return self.accepted and self.state is PortfolioReleaseState.READY

    @property
    def artifact_count(self) -> int:
        """Return the number of artifacts assigned to this member."""

        return len(self.artifact_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_address": self.dossier_address,
            "workspace_history_address": self.workspace_history_address,
            "dossier_release_id": self.dossier_release_id,
            "workspace_release_id": self.workspace_release_id,
            "dossier_state": self.dossier_state,
            "workspace_state": self.workspace_state,
            "state": self.state.value,
            "accepted": self.accepted,
            "ready": self.ready,
            "artifact_count": self.artifact_count,
            "artifact_ids": list(self.artifact_ids),
            "failed_check_ids": list(self.failed_check_ids),
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseBundle:
    """Complete multi-run release package with compact and full projections."""

    release_id: str
    as_of: str
    selection: dict[str, Any]
    state: PortfolioReleaseState
    accepted: bool
    members: tuple[PortfolioReleaseMember, ...]
    artifacts: tuple[PortfolioReleaseArtifact, ...]
    checks: tuple[PortfolioReleaseCheck, ...]
    content_address: str

    @property
    def member_count(self) -> int:
        """Return the number of selected runs."""

        return len(self.members)

    @property
    def ready_member_count(self) -> int:
        """Return the number of members that pass their own release gates."""

        return sum(member.ready for member in self.members)

    @property
    def blocked_member_count(self) -> int:
        """Return the number of members that remain inspectable but blocked."""

        return sum(not member.ready for member in self.members)

    @property
    def artifact_count(self) -> int:
        """Return the total number of exact-byte artifacts."""

        return len(self.artifacts)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return stable identifiers for all failed package checks."""

        return tuple(item.check_id for item in self.checks if item.failed)

    @property
    def warning_count(self) -> int:
        """Return the number of member warnings, retaining duplicate-free rows."""

        return sum(len(member.warnings) for member in self.members)

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        """Serialize either the full portable package or its manifest."""

        return {
            "release_version": PORTFOLIO_RELEASE_VERSION,
            "release_id": self.release_id,
            "as_of": self.as_of,
            "selection": jsonable(self.selection),
            "state": self.state.value,
            "accepted": self.accepted,
            "member_count": self.member_count,
            "ready_member_count": self.ready_member_count,
            "blocked_member_count": self.blocked_member_count,
            "artifact_count": self.artifact_count,
            "warning_count": self.warning_count,
            "failed_check_ids": list(self.failed_check_ids),
            "members": [item.to_dict() for item in self.members],
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }

    def manifest_dict(self) -> dict[str, Any]:
        """Return the file-safe manifest without duplicating payloads."""

        return self.to_dict(include_payloads=False)


@dataclass(frozen=True, slots=True)
class PortfolioReleaseVerification:
    """Result of reopening and byte-verifying a portfolio directory."""

    path: str
    release_id: str
    accepted: bool
    manifest_version_valid: bool
    manifest_address_valid: bool
    public_boundary_valid: bool
    path_safety_valid: bool
    artifact_count: int
    verified_artifact_count: int
    member_count: int
    verified_member_count: int
    failed_artifact_ids: tuple[str, ...]
    failed_member_ids: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "release_id": self.release_id,
            "accepted": self.accepted,
            "manifest_version_valid": self.manifest_version_valid,
            "manifest_address_valid": self.manifest_address_valid,
            "public_boundary_valid": self.public_boundary_valid,
            "path_safety_valid": self.path_safety_valid,
            "artifact_count": self.artifact_count,
            "verified_artifact_count": self.verified_artifact_count,
            "member_count": self.member_count,
            "verified_member_count": self.verified_member_count,
            "failed_artifact_ids": list(self.failed_artifact_ids),
            "failed_member_ids": list(self.failed_member_ids),
            "unexpected_paths": list(self.unexpected_paths),
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseQueryResult:
    """Stable result for querying a manifest without rebuilding its source."""

    query: dict[str, Any]
    members: tuple[PortfolioReleaseMember, ...]
    artifacts: tuple[PortfolioReleaseArtifact, ...]
    total_members: int
    total_artifacts: int
    accepted: bool
    content_address: str

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "query": jsonable(self.query),
            "members": [item.to_dict() for item in self.members],
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "count": len(self.members),
            "total_members": self.total_members,
            "total_artifacts": self.total_artifacts,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class PortfolioReleaseDiff:
    """Address-based comparison of two portfolio manifests."""

    left_release_id: str
    right_release_id: str
    added_run_ids: tuple[str, ...]
    removed_run_ids: tuple[str, ...]
    common_run_ids: tuple[str, ...]
    changed_run_ids: tuple[str, ...]
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_release_id": self.left_release_id,
            "right_release_id": self.right_release_id,
            "added_run_ids": list(self.added_run_ids),
            "removed_run_ids": list(self.removed_run_ids),
            "common_run_ids": list(self.common_run_ids),
            "changed_run_ids": list(self.changed_run_ids),
            "added_artifact_ids": list(self.added_artifact_ids),
            "removed_artifact_ids": list(self.removed_artifact_ids),
            "changed_artifact_ids": list(self.changed_artifact_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def address_check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    *,
    scope: str = "portfolio",
) -> PortfolioReleaseCheck:
    """Create a content-addressed release check from public values."""

    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": jsonable(observed),
        "required": jsonable(required),
        "detail": str(detail),
        "scope": str(scope),
    }
    return PortfolioReleaseCheck(
        **body,
        content_address=content_hash(body, prefix=PORTFOLIO_RELEASE_CHECK_PREFIX),
    )


__all__ = [
    "PORTFOLIO_RELEASE_ARTIFACT_PREFIX",
    "PORTFOLIO_RELEASE_CHECK_PREFIX",
    "PORTFOLIO_RELEASE_DEFAULT_MAX_RUNS",
    "PORTFOLIO_RELEASE_MANIFEST",
    "PORTFOLIO_RELEASE_MAX_RUNS",
    "PORTFOLIO_RELEASE_VERSION",
    "PortfolioArtifactKind",
    "PortfolioReleaseArtifact",
    "PortfolioReleaseBundle",
    "PortfolioReleaseCheck",
    "PortfolioReleaseDiff",
    "PortfolioReleaseMember",
    "PortfolioReleaseQueryResult",
    "PortfolioReleaseState",
    "PortfolioReleaseVerification",
    "address_check",
]

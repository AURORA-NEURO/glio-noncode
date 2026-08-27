"""Typed contracts for comparing and releasing replication packets.

Packet verification answers whether one persisted packet is internally sound.
These contracts answer the adjacent operational question: what changed
between two sound packets, and is the candidate safe to release?  Every row
is content-addressed, bounded, and independent of the directories that held
the compared packets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ARTIFACT_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-artifact"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_CHECK_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-release"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_QUERY_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-runtime-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_BOUNDARY = (
    "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_"
    "diff_runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-runtime"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_STAGE_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-runtime-stage"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS = 8192
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES = 16


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState(StrEnum):
    """Relationship between the left and right packet boundaries."""

    MATCHED = "matched"
    EXTENDED = "extended"
    CHANGED = "changed"
    DIVERGED = "diverged"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction(StrEnum):
    """Action for one artifact or check identity."""

    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane(StrEnum):
    """Independent planes used by a packet diff safety gate."""

    FORMAT = "format"
    REFERENCE = "reference"
    ARTIFACT = "artifact"
    CHECK = "check"
    RELEASE = "release"
    PUBLIC = "public"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState(StrEnum):
    """Typed check state."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState(StrEnum):
    """Candidate release outcome."""

    PROMOTABLE = "promotable"
    HOLD = "hold"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind(StrEnum):
    """Ordered diff-runtime stages."""

    LOAD = "load"
    VERIFY_LEFT = "verify_left"
    VERIFY_RIGHT = "verify_right"
    COMPARE = "compare"
    RELEASE = "release"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState(StrEnum):
    """Stage outcome."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field)
    if ":" not in normalized:
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _optional_address(value: Any, field: str) -> None:
    if value is not None:
        _address(value, field)


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the supported bound")


def _ratio(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if value < 0 or value > 1:
        raise ValidationError(f"{field} must be between zero and one")


def _addresses(values: tuple[str, ...], field: str) -> None:
    _count(
        len(values),
        field,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,
    )
    if len(set(values)) != len(values):
        raise ValidationError(f"{field} must be unique")
    for value in values:
        _address(value, field)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact:
    """Comparison row for one artifact identity."""

    ordinal: int
    artifact_id: str
    action: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction
    left_address: str | None
    right_address: str | None
    left_byte_count: int
    right_byte_count: int
    required: bool
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "diff artifact ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,
        )
        _text(self.artifact_id, "diff artifact ID", 256)
        _optional_address(self.left_address, "left artifact address")
        _optional_address(self.right_address, "right artifact address")
        _count(self.left_byte_count, "left artifact byte count")
        _count(self.right_byte_count, "right artifact byte count")
        _text(self.detail, "diff artifact detail", 4096)
        _address(self.content_address, "diff artifact address")
        if not isinstance(
            self.action, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction
        ):
            raise ValidationError("diff artifact action is invalid")
        if not isinstance(self.required, bool) or not isinstance(self.accepted, bool):
            raise ValidationError("diff artifact flags must be boolean")
        if (
            self.action
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.ADDED
            and self.left_address is not None
        ):
            raise ValidationError("added artifact cannot have a left address")
        if (
            self.action
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
            and self.right_address is not None
        ):
            raise ValidationError("removed artifact cannot have a right address")
        if (
            self.action
            is not ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.ADDED
            and self.right_address is None
        ):
            raise ValidationError("existing artifact action requires a right address")
        if (
            self.required
            and self.action
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
            and self.accepted
        ):
            raise ValidationError("removed required artifact cannot be accepted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "artifact_id": self.artifact_id,
            "action": self.action,
            "left_address": self.left_address,
            "right_address": self.right_address,
            "left_byte_count": self.left_byte_count,
            "right_byte_count": self.right_byte_count,
            "required": self.required,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_artifact(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact,
) -> str:
    """Recompute an artifact diff row address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_ARTIFACT_PREFIX,
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck:
    """A release-relevant diff check."""

    check_id: str
    plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "diff check ID", 256)
        _text(self.detail, "diff check detail", 4096)
        _address(self.content_address, "diff check address")
        if not isinstance(
            self.plane, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane
        ):
            raise ValidationError("diff check plane is invalid")
        if not isinstance(
            self.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState
        ):
            raise ValidationError("diff check state is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("diff check passed flag must be boolean")
        if (
            self.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState.PASSED
            and not self.passed
        ):
            raise ValidationError("passed diff check must be accepted")
        if (
            self.state
            is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState.FAILED
            and self.passed
        ):
            raise ValidationError("failed diff check cannot be accepted")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck,
) -> str:
    """Recompute a diff check address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_CHECK_PREFIX,
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff:
    """Complete, path-free comparison of two packet manifests."""

    diff_id: str
    version: str
    boundary: str
    left_packet_address: str
    right_packet_address: str
    left_plan_address: str
    right_plan_address: str
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState
    artifacts: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact, ...]
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck, ...]
    artifact_count: int
    added_artifact_count: int
    removed_artifact_count: int
    changed_artifact_count: int
    unchanged_artifact_count: int
    check_count: int
    passed_count: int
    removed_required_count: int
    right_accepted: bool
    release_allowed: bool
    change_ratio: float
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_id, "packet diff ID", 512)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_VERSION
        ):
            raise ValidationError("packet diff version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BOUNDARY
        ):
            raise ValidationError("packet diff boundary is invalid")
        for value, field in (
            (self.left_packet_address, "left packet address"),
            (self.right_packet_address, "right packet address"),
            (self.left_plan_address, "left plan address"),
            (self.right_plan_address, "right plan address"),
            (self.content_address, "packet diff address"),
        ):
            _address(value, field)
        if not isinstance(
            self.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState
        ):
            raise ValidationError("packet diff state is invalid")
        for value, field in (
            (self.artifact_count, "artifact count"),
            (self.added_artifact_count, "added artifact count"),
            (self.removed_artifact_count, "removed artifact count"),
            (self.changed_artifact_count, "changed artifact count"),
            (self.unchanged_artifact_count, "unchanged artifact count"),
            (self.check_count, "check count"),
            (self.passed_count, "passed count"),
            (self.removed_required_count, "removed required count"),
        ):
            _count(
                value,
                field,
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,
            )
        _ratio(self.change_ratio, "change ratio")
        _text(self.detail, "packet diff detail", 8192)
        if self.artifact_count != len(self.artifacts) or self.check_count != len(self.checks):
            raise ValidationError("packet diff counts do not match rows")
        if self.passed_count != sum(item.passed for item in self.checks):
            raise ValidationError("packet diff passed count does not match checks")
        action_counts = {
            action: sum(item.action is action for item in self.artifacts)
            for action in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction
        }
        if (
            action_counts[
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.ADDED
            ]
            != self.added_artifact_count
            or action_counts[
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
            ]
            != self.removed_artifact_count
            or action_counts[
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.CHANGED
            ]
            != self.changed_artifact_count
            or action_counts[
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.UNCHANGED
            ]
            != self.unchanged_artifact_count
        ):
            raise ValidationError("packet diff artifact actions do not conserve")
        if self.accepted != (self.passed_count == self.check_count):
            raise ValidationError("packet diff acceptance does not match checks")
        if self.release_allowed and not (self.accepted and self.right_accepted):
            raise ValidationError("packet diff release cannot exceed acceptance")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "diff_address": self.content_address,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "left_plan_address": self.left_plan_address,
            "right_plan_address": self.right_plan_address,
            "state": self.state,
            "artifact_count": self.artifact_count,
            "added_artifact_count": self.added_artifact_count,
            "removed_artifact_count": self.removed_artifact_count,
            "changed_artifact_count": self.changed_artifact_count,
            "unchanged_artifact_count": self.unchanged_artifact_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "removed_required_count": self.removed_required_count,
            "right_accepted": self.right_accepted,
            "release_allowed": self.release_allowed,
            "change_ratio": self.change_ratio,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "left_plan_address": self.left_plan_address,
            "right_plan_address": self.right_plan_address,
            "state": self.state,
            "artifacts": tuple(item.to_dict() for item in self.artifacts),
            "checks": tuple(item.to_dict() for item in self.checks),
            "artifact_count": self.artifact_count,
            "added_artifact_count": self.added_artifact_count,
            "removed_artifact_count": self.removed_artifact_count,
            "changed_artifact_count": self.changed_artifact_count,
            "unchanged_artifact_count": self.unchanged_artifact_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "removed_required_count": self.removed_required_count,
            "right_accepted": self.right_accepted,
            "release_allowed": self.release_allowed,
            "change_ratio": self.change_ratio,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
) -> str:
    """Recompute a packet diff address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_PREFIX,
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease:
    """Release decision derived from an accepted packet diff."""

    release_id: str
    diff_address: str
    candidate_packet_address: str
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState
    checks: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck, ...]
    check_count: int
    passed_count: int
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.release_id, "release ID", 512)
        _address(self.diff_address, "release diff address")
        _address(self.candidate_packet_address, "candidate packet address")
        _address(self.content_address, "release address")
        _text(self.detail, "release detail", 4096)
        if not isinstance(
            self.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState
        ):
            raise ValidationError("release state is invalid")
        _count(
            self.check_count,
            "release check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,
        )
        _count(
            self.passed_count,
            "release passed count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS,
        )
        if self.check_count != len(self.checks) or self.passed_count != sum(
            item.passed for item in self.checks
        ):
            raise ValidationError("release checks do not conserve")
        if not isinstance(self.accepted, bool):
            raise ValidationError("release acceptance must be boolean")
        if self.accepted != (
            self.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE
            )
            and self.passed_count == self.check_count
        ):
            raise ValidationError("release state and acceptance disagree")

    def summary(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "release_address": self.content_address,
            "diff_address": self.diff_address,
            "candidate_packet_address": self.candidate_packet_address,
            "state": self.state,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "diff_address": self.diff_address,
            "candidate_packet_address": self.candidate_packet_address,
            "state": self.state,
            "checks": tuple(item.to_dict() for item in self.checks),
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
) -> str:
    """Recompute a release decision address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_PREFIX,
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage:
    """One ordered diff-runtime stage."""

    ordinal: int
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind
    state: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState
    artifact_address: str
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _count(
            self.ordinal,
            "diff runtime stage ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES,
        )
        if not isinstance(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind,
        ):
            raise ValidationError("diff runtime stage kind is invalid")
        if not isinstance(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState,
        ):
            raise ValidationError("diff runtime stage state is invalid")
        _address(self.artifact_address, "diff runtime artifact address")
        _text(self.detail, "diff runtime stage detail", 4096)
        _address(self.content_address, "diff runtime stage address")
        if not isinstance(self.accepted, bool):
            raise ValidationError("diff runtime stage acceptance must be boolean")
        if self.accepted != (
            self.state
            is not (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.BLOCKED
            )
        ):
            raise ValidationError("diff runtime stage state and acceptance disagree")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": self.state,
            "artifact_address": self.artifact_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage,
) -> str:
    """Recompute a runtime stage address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_STAGE_PREFIX,
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime:
    """Addressed runtime receipt for packet comparison and release."""

    diff_id: str
    version: str
    boundary: str
    left_packet_address: str
    right_packet_address: str
    diff_address: str
    release_address: str
    stages: tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStage, ...]
    stage_count: int
    completed_count: int
    skipped_count: int
    blocked_count: int
    accepted: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_id, "diff runtime ID", 512)
        if self.version != (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_VERSION
        ):
            raise ValidationError("diff runtime version is invalid")
        if self.boundary != (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_BOUNDARY
        ):
            raise ValidationError("diff runtime boundary is invalid")
        for value, field in (
            (self.left_packet_address, "runtime left packet address"),
            (self.right_packet_address, "runtime right packet address"),
            (self.diff_address, "runtime diff address"),
            (self.release_address, "runtime release address"),
            (self.content_address, "runtime address"),
        ):
            _address(value, field)
        _count(
            self.stage_count,
            "runtime stage count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES,
        )
        _count(
            self.completed_count,
            "runtime completed count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES,
        )
        _count(
            self.skipped_count,
            "runtime skipped count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES,
        )
        _count(
            self.blocked_count,
            "runtime blocked count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES,
        )
        _text(self.detail, "runtime detail", 8192)
        if self.stage_count != len(self.stages):
            raise ValidationError("runtime stage count does not conserve")
        if self.completed_count != sum(
            item.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.COMPLETED
            )
            for item in self.stages
        ):
            raise ValidationError("runtime completed count does not conserve")
        if self.skipped_count != sum(
            item.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.SKIPPED
            )
            for item in self.stages
        ):
            raise ValidationError("runtime skipped count does not conserve")
        if self.blocked_count != sum(
            item.state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState.BLOCKED
            )
            for item in self.stages
        ):
            raise ValidationError("runtime blocked count does not conserve")
        if not isinstance(self.accepted, bool) or self.accepted != (self.blocked_count == 0):
            raise ValidationError("runtime acceptance does not conserve")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "runtime_address": self.content_address,
            "diff_address": self.diff_address,
            "release_address": self.release_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "skipped_count": self.skipped_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "left_packet_address": self.left_packet_address,
            "right_packet_address": self.right_packet_address,
            "diff_address": self.diff_address,
            "release_address": self.release_address,
            "stages": tuple(item.to_dict() for item in self.stages),
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "skipped_count": self.skipped_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntime,
) -> str:
    """Recompute a diff-runtime receipt address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_PREFIX,
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_schema() -> dict[
    str, Any
]:
    """Describe the packet diff and release boundary."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_VERSION,
        "boundary": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BOUNDARY
        ),
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState
        ],
        "actions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction
        ],
        "planes": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane
        ],
        "release_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState
        ],
        "resources": ["summary", "artifacts", "checks", "release_checks"],
        "limits": {
            "max_rows": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_ROWS
            ),
            "max_query_limit": (
                MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_LIMIT
            ),
        },
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_capabilities() -> dict[
    str, Any
]:
    """Declare comparison, release, query, and runtime operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_VERSION,
        "operations": [
            "compare_packet_manifests",
            "classify_artifact_actions",
            "classify_check_actions",
            "build_release_decision",
            "verify_packet_diff",
            "verify_release_decision",
            "query_diff_summary",
            "query_diff_artifacts",
            "query_diff_checks",
            "export_diff_json",
            "export_diff_csv",
            "render_diff_markdown",
            "run_diff_runtime",
        ],
        "guarantees": [
            "content_addressed_rows",
            "artifact_action_conservation",
            "explicit_required_artifact_removal",
            "candidate_acceptance_gate",
            "regression_hold",
            "bounded_queries",
            "no_filesystem_paths",
            "no_private_or_attribution_fields",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_schema() -> (
    dict[str, Any]
):
    """Describe ordered diff-runtime stages."""

    return {
        "version": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_VERSION
        ),
        "boundary": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_BOUNDARY
        ),
        "stage_kinds": [
            item.value
            for item in (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageKind
            )
        ],
        "stage_states": [
            item.value
            for item in (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRuntimeStageState
            )
        ],
        "max_stages": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_MAX_STAGES
        ),
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    """Declare diff-runtime lifecycle guarantees."""

    return {
        "version": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RUNTIME_VERSION
        ),
        "operations": [
            "load_left_packet",
            "load_right_packet",
            "verify_left_packet",
            "verify_right_packet",
            "compare_boundaries",
            "evaluate_release",
            "close_runtime",
        ],
        "guarantees": [
            "ordered_stages",
            "blocked_stage_visibility",
            "complete_lifecycle_closure",
            "content_addressed_receipt",
            "no_input_paths_in_receipt",
        ],
    }

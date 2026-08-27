"""Typed contracts for release-window governance over packet-diff matrices.

The release-window layer is deliberately separate from packet construction and
packet comparison.  A matrix describes evidence collected from a set of
packet pairs; this module describes the bounded policy, the checks that policy
produces, the ordered runtime handoff, and the independent assurance receipt.
Every public object is content addressed from its public fields.  No path,
clock value, credential, person, model, or transport metadata is accepted into
these contracts.
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-v1"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_PREFIX = (
    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_POLICY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-policy"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_CHECK_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-check"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_STAGE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime-stage"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_FINDING_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-finding"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_QUERY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-query"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_QUERY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-query"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT = (
    512
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_CHECKS = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_FINDINGS = 64
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_STAGES = 16


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState(StrEnum):
    """Release-window outcomes in increasing order of concern."""

    PROMOTABLE = "promotable"
    HOLD = "hold"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity(
    StrEnum
):
    """Impact of a failed policy check."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind(
    StrEnum
):
    """Fixed-vocabulary policy checks for stable downstream filtering."""

    MATRIX_ACCEPTANCE = "matrix_acceptance"
    MINIMUM_ITEMS = "minimum_items"
    MINIMUM_SCORE = "minimum_score"
    HOLD_LIMIT = "hold_limit"
    BLOCKED_LIMIT = "blocked_limit"
    CHANGED_ARTIFACT_LIMIT = "changed_artifact_limit"
    REQUIRED_REMOVAL_LIMIT = "required_removal_limit"
    ALL_ACCEPTED = "all_accepted"
    ALL_RELEASE_READY = "all_release_ready"
    PUBLIC_BOUNDARY = "public_boundary"
    CONSERVATION = "conservation"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind(
    StrEnum
):
    """Ordered stages of a release-window evaluation."""

    LOAD = "load"
    VERIFY_MATRIX = "verify_matrix"
    RESOLVE_POLICY = "resolve_policy"
    EVALUATE = "evaluate"
    AUDIT = "audit"
    RELEASE = "release"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState(
    StrEnum
):
    """Stage outcomes used by the fail-closed runtime."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState(
    StrEnum
):
    """Independent assurance outcomes."""

    ACCEPTED = "accepted"
    HOLD = "hold"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity(
    StrEnum
):
    """Severity values for independent assurance findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str, maximum: int = 256) -> str:
    normalized = _text(value, field, maximum)
    if ":" not in normalized or normalized.startswith(":") or normalized.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _count(value: Any, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValidationError(f"{field} must be a ratio between zero and one")
    return float(value)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _public_boundary(value: Any) -> bool:
    """Reject identity and private transport keys recursively."""

    forbidden = {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "author",
        "author_id",
        "codex",
        "email",
        "hostname",
        "model",
        "openai",
        "private",
        "token",
        "user",
        "user_id",
        "username",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public_boundary(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public_boundary(item) for item in value)
    return True


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy:
    """Bounded thresholds used to decide whether a matrix may be promoted."""

    def __init__(
        self,
        policy_id: str,
        version: str,
        minimum_items: int,
        minimum_score: float,
        maximum_hold_count: int,
        maximum_blocked_count: int,
        maximum_changed_artifact_count: int,
        maximum_removed_required_count: int,
        require_all_accepted: bool,
        require_all_release_ready: bool,
        content_address: str,
    ) -> None:
        self.policy_id = policy_id
        self.version = version
        self.minimum_items = minimum_items
        self.minimum_score = minimum_score
        self.maximum_hold_count = maximum_hold_count
        self.maximum_blocked_count = maximum_blocked_count
        self.maximum_changed_artifact_count = maximum_changed_artifact_count
        self.maximum_removed_required_count = maximum_removed_required_count
        self.require_all_accepted = require_all_accepted
        self.require_all_release_ready = require_all_release_ready
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.policy_id, "release-window policy ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION
        ):
            raise ValidationError("release-window policy version is invalid")
        for value, field in (
            (self.minimum_items, "minimum items"),
            (self.maximum_hold_count, "maximum hold count"),
            (self.maximum_blocked_count, "maximum blocked count"),
            (self.maximum_changed_artifact_count, "maximum changed artifact count"),
            (self.maximum_removed_required_count, "maximum removed required count"),
        ):
            _count(value, field, 256)
        if self.minimum_items < 1:
            raise ValidationError("minimum items must be positive")
        _ratio(self.minimum_score, "minimum score")
        _bool(self.require_all_accepted, "require all accepted")
        _bool(self.require_all_release_ready, "require all release ready")
        _address(self.content_address, "release-window policy address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("release-window policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "minimum_items": self.minimum_items,
            "minimum_score": self.minimum_score,
            "maximum_hold_count": self.maximum_hold_count,
            "maximum_blocked_count": self.maximum_blocked_count,
            "maximum_changed_artifact_count": self.maximum_changed_artifact_count,
            "maximum_removed_required_count": self.maximum_removed_required_count,
            "require_all_accepted": self.require_all_accepted,
            "require_all_release_ready": self.require_all_release_ready,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
) -> str:
    """Compute the deterministic policy address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_POLICY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck:
    """One explicit policy observation and its remediation."""

    def __init__(
        self,
        ordinal: int,
        check_id: str,
        kind: str,
        severity: str,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.check_id = check_id
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "release-window check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_CHECKS,
        )
        _text(self.check_id, "release-window check ID", 256)
        if self.kind not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind
        }:
            raise ValidationError("release-window check kind is invalid")
        if self.severity not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity
        }:
            raise ValidationError("release-window check severity is invalid")
        _bool(self.passed, "release-window check passed")
        _text(self.detail, "release-window check detail", 4096)
        _text(self.remediation, "release-window check remediation", 4096)
        _address(self.content_address, "release-window check address")
        if not _public_boundary(self.observed) or not _public_boundary(self.expected):
            raise ValidationError("release-window check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "check_id": self.check_id,
            "kind": self.kind,
            "severity": self.severity,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck,
) -> str:
    """Compute a deterministic policy-check address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow:
    """Addressed aggregate decision for one matrix and one policy."""

    def __init__(
        self,
        window_id: str,
        version: str,
        boundary: str,
        batch_address: str,
        policy_address: str,
        state: str,
        release_ready: bool,
        item_count: int,
        accepted_count: int,
        release_ready_count: int,
        score: float,
        changed_artifact_count: int,
        removed_required_count: int,
        promotable_count: int,
        hold_count: int,
        release_blocked_count: int,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck, ...
        ],
        check_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.window_id = window_id
        self.version = version
        self.boundary = boundary
        self.batch_address = batch_address
        self.policy_address = policy_address
        self.state = state
        self.release_ready = release_ready
        self.item_count = item_count
        self.accepted_count = accepted_count
        self.release_ready_count = release_ready_count
        self.score = score
        self.changed_artifact_count = changed_artifact_count
        self.removed_required_count = removed_required_count
        self.promotable_count = promotable_count
        self.hold_count = hold_count
        self.release_blocked_count = release_blocked_count
        self.checks = checks
        self.check_count = check_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.window_id, "release-window ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION
        ):
            raise ValidationError("release-window version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_BOUNDARY
        ):
            raise ValidationError("release-window boundary is invalid")
        _address(self.batch_address, "release-window batch address")
        _address(self.policy_address, "release-window policy address")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState
        }:
            raise ValidationError("release-window state is invalid")
        _bool(self.release_ready, "release-window release-ready flag")
        _count(self.item_count, "release-window item count", 256)
        if self.item_count < 1:
            raise ValidationError("release-window item count must be positive")
        for value, field in (
            (self.accepted_count, "release-window accepted count"),
            (self.release_ready_count, "release-window release-ready count"),
            (self.promotable_count, "release-window promotable count"),
            (self.hold_count, "release-window hold count"),
            (self.release_blocked_count, "release-window blocked count"),
        ):
            _count(value, field, self.item_count)
        _count(self.changed_artifact_count, "release-window changed artifact count")
        _count(self.removed_required_count, "release-window required removal count")
        _ratio(self.score, "release-window score")
        if abs(self.score - self.release_ready_count / self.item_count) > 1e-12:
            raise ValidationError("release-window score does not conserve matrix values")
        if self.accepted_count > self.item_count or self.release_ready_count > self.item_count:
            raise ValidationError("release-window count exceeds item count")
        if self.check_count != len(self.checks) or not self.checks:
            raise ValidationError("release-window check count does not conserve")
        _count(
            self.check_count,
            "release-window check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_CHECKS,
        )
        if tuple(item.ordinal for item in self.checks) != tuple(range(self.check_count)):
            raise ValidationError("release-window check ordinals are not ordered")
        if any(
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_check(
                item
            )
            != item.content_address
            for item in self.checks
        ):
            raise ValidationError("release-window check address mismatch")
        expected_passed = sum(item.passed for item in self.checks)
        expected_warnings = sum(
            (not item.passed)
            and item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.WARNING
            for item in self.checks
        )
        expected_blockers = sum(
            (not item.passed)
            and item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER
            for item in self.checks
        )
        if self.passed_count != expected_passed:
            raise ValidationError("release-window passed count does not conserve")
        if self.warning_count != expected_warnings:
            raise ValidationError("release-window warning count does not conserve")
        if self.blocker_count != expected_blockers:
            raise ValidationError("release-window blocker count does not conserve")
        _count(self.passed_count, "release-window passed count", self.check_count)
        _count(self.warning_count, "release-window warning count", self.check_count)
        _count(self.blocker_count, "release-window blocker count", self.check_count)
        _bool(self.accepted, "release-window accepted")
        _text(self.detail, "release-window detail", 4096)
        _address(self.content_address, "release-window address")
        expected_state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.BLOCKED
            if self.blocker_count or not self.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.HOLD
            if self.warning_count
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.PROMOTABLE
        )
        if self.state != expected_state.value:
            raise ValidationError("release-window state does not follow checks")
        if self.release_ready != (
            self.accepted
            and self.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.PROMOTABLE
        ):
            raise ValidationError("release-window readiness does not conserve state")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("release-window crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "version": self.version,
            "boundary": self.boundary,
            "batch_address": self.batch_address,
            "policy_address": self.policy_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "item_count": self.item_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "score": self.score,
            "changed_artifact_count": self.changed_artifact_count,
            "removed_required_count": self.removed_required_count,
            "promotable_count": self.promotable_count,
            "hold_count": self.hold_count,
            "release_blocked_count": self.release_blocked_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary() | {"detail": self.detail}
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
) -> str:
    """Compute the deterministic release-window address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage:
    """One ordered runtime transition with an addressed result."""

    def __init__(
        self,
        ordinal: int,
        kind: str,
        state: str,
        artifact_address: str,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.state = state
        self.artifact_address = artifact_address
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "release-window runtime stage ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_STAGES,
        )
        if self.kind not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageKind
        }:
            raise ValidationError("release-window runtime stage kind is invalid")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState
        }:
            raise ValidationError("release-window runtime stage state is invalid")
        _address(self.artifact_address, "release-window runtime artifact address")
        _bool(self.accepted, "release-window runtime stage accepted")
        _text(self.detail, "release-window runtime stage detail", 2048)
        _address(self.content_address, "release-window runtime stage address")
        if self.accepted != (
            self.state
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.BLOCKED
        ):
            raise ValidationError("release-window runtime stage acceptance does not follow state")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("release-window runtime stage crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage,
) -> str:
    """Compute a runtime-stage address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_STAGE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime:
    """Addressed runtime handoff for policy evaluation and release."""

    def __init__(
        self,
        window_id: str,
        version: str,
        boundary: str,
        batch_address: str,
        policy_address: str,
        window_address: str,
        stages: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStage,
            ...,
        ],
        stage_count: int,
        completed_count: int,
        skipped_count: int,
        blocked_count: int,
        accepted: bool,
        state: str,
        release_ready: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.window_id = window_id
        self.version = version
        self.boundary = boundary
        self.batch_address = batch_address
        self.policy_address = policy_address
        self.window_address = window_address
        self.stages = stages
        self.stage_count = stage_count
        self.completed_count = completed_count
        self.skipped_count = skipped_count
        self.blocked_count = blocked_count
        self.accepted = accepted
        self.state = state
        self.release_ready = release_ready
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.window_id, "release-window runtime ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_VERSION
        ):
            raise ValidationError("release-window runtime version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_BOUNDARY
        ):
            raise ValidationError("release-window runtime boundary is invalid")
        for value, field in (
            (self.batch_address, "release-window runtime batch address"),
            (self.policy_address, "release-window runtime policy address"),
            (self.window_address, "release-window runtime window address"),
            (self.content_address, "release-window runtime address"),
        ):
            _address(value, field)
        if self.stage_count != len(self.stages) or self.stage_count < 1:
            raise ValidationError("release-window runtime stage count does not conserve")
        _count(
            self.stage_count,
            "release-window runtime stage count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_STAGES,
        )
        if tuple(item.ordinal for item in self.stages) != tuple(range(self.stage_count)):
            raise ValidationError("release-window runtime stages are not ordered")
        expected_completed = sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.COMPLETED
            for item in self.stages
        )
        expected_skipped = sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.SKIPPED
            for item in self.stages
        )
        expected_blocked = sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntimeStageState.BLOCKED
            for item in self.stages
        )
        if (self.completed_count, self.skipped_count, self.blocked_count) != (
            expected_completed,
            expected_skipped,
            expected_blocked,
        ):
            raise ValidationError("release-window runtime stage counts do not conserve")
        _count(self.completed_count, "release-window runtime completed count", self.stage_count)
        _count(self.skipped_count, "release-window runtime skipped count", self.stage_count)
        _count(self.blocked_count, "release-window runtime blocked count", self.stage_count)
        _bool(self.accepted, "release-window runtime accepted")
        if self.accepted != all(item.accepted for item in self.stages):
            raise ValidationError("release-window runtime acceptance does not conserve")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState
        }:
            raise ValidationError("release-window runtime state is invalid")
        _bool(self.release_ready, "release-window runtime release-ready flag")
        _text(self.detail, "release-window runtime detail", 4096)
        if not _public_boundary(self.to_dict()):
            raise ValidationError("release-window runtime crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "version": self.version,
            "boundary": self.boundary,
            "batch_address": self.batch_address,
            "policy_address": self.policy_address,
            "window_address": self.window_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "skipped_count": self.skipped_count,
            "blocked_count": self.blocked_count,
            "accepted": self.accepted,
            "state": self.state,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body = self.summary() | {"detail": self.detail}
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowRuntime,
) -> str:
    """Compute the deterministic runtime address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_RUNTIME_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding:
    """One independent assurance finding."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        plane: str,
        severity: str,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.plane = plane
        self.severity = severity
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "release-window assurance finding ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_FINDINGS,
        )
        _text(self.finding_id, "release-window assurance finding ID", 256)
        _text(self.plane, "release-window assurance plane", 128)
        if self.severity not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity
        }:
            raise ValidationError("release-window assurance severity is invalid")
        _bool(self.passed, "release-window assurance finding passed")
        _text(self.detail, "release-window assurance detail", 4096)
        _text(self.remediation, "release-window assurance remediation", 4096)
        _address(self.content_address, "release-window assurance finding address")
        if not _public_boundary(self.observed) or not _public_boundary(self.expected):
            raise ValidationError("release-window assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "plane": self.plane,
            "severity": self.severity,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_finding(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding,
) -> str:
    """Compute an independent finding address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_FINDING_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance:
    """Independent assurance aggregate for a release-window decision."""

    def __init__(
        self,
        assurance_id: str,
        version: str,
        boundary: str,
        window_address: str,
        runtime_address: str | None,
        state: str,
        release_ready: bool,
        findings: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceFinding,
            ...,
        ],
        finding_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        score: float,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.window_address = window_address
        self.runtime_address = runtime_address
        self.state = state
        self.release_ready = release_ready
        self.findings = findings
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.score = score
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "release-window assurance ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_VERSION
        ):
            raise ValidationError("release-window assurance version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_BOUNDARY
        ):
            raise ValidationError("release-window assurance boundary is invalid")
        _address(self.window_address, "release-window assurance window address")
        if self.runtime_address is not None:
            _address(self.runtime_address, "release-window assurance runtime address")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState
        }:
            raise ValidationError("release-window assurance state is invalid")
        _bool(self.release_ready, "release-window assurance release-ready flag")
        if self.finding_count != len(self.findings) or not self.findings:
            raise ValidationError("release-window assurance finding count does not conserve")
        _count(
            self.finding_count,
            "release-window assurance finding count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_FINDINGS,
        )
        if tuple(item.ordinal for item in self.findings) != tuple(range(self.finding_count)):
            raise ValidationError("release-window assurance findings are not ordered")
        if any(
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_finding(
                item
            )
            != item.content_address
            for item in self.findings
        ):
            raise ValidationError("release-window assurance finding address mismatch")
        expected_passed = sum(item.passed for item in self.findings)
        expected_warnings = sum(
            (not item.passed)
            and item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.WARNING
            for item in self.findings
        )
        expected_blockers = sum(
            (not item.passed)
            and item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceSeverity.BLOCKER
            for item in self.findings
        )
        if (self.passed_count, self.warning_count, self.blocker_count) != (
            expected_passed,
            expected_warnings,
            expected_blockers,
        ):
            raise ValidationError("release-window assurance counts do not conserve")
        _count(self.passed_count, "release-window assurance passed count", self.finding_count)
        _count(self.warning_count, "release-window assurance warning count", self.finding_count)
        _count(self.blocker_count, "release-window assurance blocker count", self.finding_count)
        _ratio(self.score, "release-window assurance score")
        if abs(self.score - self.passed_count / self.finding_count) > 1e-12:
            raise ValidationError("release-window assurance score does not conserve")
        _bool(self.accepted, "release-window assurance accepted")
        _text(self.detail, "release-window assurance detail", 4096)
        expected_state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.BLOCKED
            if self.blocker_count or not self.accepted
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.HOLD
            if self.warning_count
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.ACCEPTED
        )
        if self.state != expected_state.value:
            raise ValidationError("release-window assurance state does not follow findings")
        if self.release_ready != (
            self.accepted
            and self.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.ACCEPTED
        ):
            raise ValidationError("release-window assurance readiness does not conserve")
        _public_boundary(self.to_dict())
        if not _public_boundary(self.to_dict()):
            raise ValidationError("release-window assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "window_address": self.window_address,
            "runtime_address": self.runtime_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "score": self.score,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary() | {"detail": self.detail}
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssurance,
) -> str:
    """Compute the deterministic assurance address."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_ASSURANCE_PREFIX,
    )


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
    )
]

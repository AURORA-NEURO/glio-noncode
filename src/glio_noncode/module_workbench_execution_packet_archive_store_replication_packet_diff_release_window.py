"""Build and verify release-window decisions over packet-diff matrices.

This module applies a caller-declared, bounded policy to a verified matrix. It
does not copy packet payloads and it does not silently turn a held pair into a
promotion. Every policy observation is explicit, addressable, and suitable
for offline review.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_CHECK_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_POLICY_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_check,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy,
)
from .serialization import canonical_json


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


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
    if isinstance(value, (tuple, list)):
        return all(_public_boundary(item) for item in value)
    return True


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
    *,
    policy_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-policy"
    ),
    minimum_items: int = 1,
    minimum_score: float = 1.0,
    maximum_hold_count: int = 0,
    maximum_blocked_count: int = 0,
    maximum_changed_artifact_count: int = 0,
    maximum_removed_required_count: int = 0,
    require_all_accepted: bool = True,
    require_all_release_ready: bool = True,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy:
    """Create a deterministic policy with explicit release thresholds."""

    body = {
        "policy_id": _text(policy_id, "release-window policy ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
        "minimum_items": _count(minimum_items, "minimum items", 256),
        "minimum_score": _ratio(minimum_score, "minimum score"),
        "maximum_hold_count": _count(maximum_hold_count, "maximum hold count", 256),
        "maximum_blocked_count": _count(maximum_blocked_count, "maximum blocked count", 256),
        "maximum_changed_artifact_count": _count(
            maximum_changed_artifact_count, "maximum changed artifact count"
        ),
        "maximum_removed_required_count": _count(
            maximum_removed_required_count, "maximum removed required count"
        ),
        "require_all_accepted": _bool(require_all_accepted, "require all accepted"),
        "require_all_release_ready": _bool(require_all_release_ready, "require all release ready"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_POLICY_PREFIX
        + ":pending-policy",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            provisional
        ),
    )


def _check(
    ordinal: int,
    kind: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind,
    severity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    remediation: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck:
    body = {
        "ordinal": ordinal,
        "check_id": f"release-window-{ordinal}-{kind.value}",
        "kind": kind.value,
        "severity": severity.value,
        "passed": _bool(passed, "release-window check passed"),
        "observed": observed,
        "expected": expected,
        "detail": _text(detail, "release-window check detail", 4096),
        "remediation": _text(remediation, "release-window check remediation", 4096),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_CHECK_PREFIX
        + ":pending-check",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_check(
            provisional
        ),
    )


def _checks(
    batch: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
) -> tuple[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheck, ...]:
    """Evaluate all fixed-vocabulary policy checks in stable order."""

    changed_artifacts = sum(item.changed_artifact_count for item in batch.items)
    removed_required = sum(item.removed_required_count for item in batch.items)
    matrix_accepted = batch.accepted
    all_accepted = batch.accepted_count == batch.item_count
    all_release_ready = batch.release_ready_count == batch.item_count
    return (
        _check(
            0,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.MATRIX_ACCEPTANCE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            matrix_accepted,
            {"accepted": matrix_accepted},
            {"accepted": True},
            "the packet-diff matrix reports an accepted aggregate",
            "repair or rebuild every rejected packet pair before release",
        ),
        _check(
            1,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.MINIMUM_ITEMS,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            batch.item_count >= policy.minimum_items,
            {"item_count": batch.item_count},
            {"minimum_items": policy.minimum_items},
            "the release window contains the required number of packet pairs",
            "add verified packet pairs or lower the policy only through review",
        ),
        _check(
            2,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.MINIMUM_SCORE,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            batch.score >= policy.minimum_score,
            {"score": batch.score},
            {"minimum_score": policy.minimum_score},
            "release-ready pair coverage meets the declared score threshold",
            "resolve held or blocked packet pairs before release",
        ),
        _check(
            3,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.HOLD_LIMIT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            batch.hold_count <= policy.maximum_hold_count,
            {"hold_count": batch.hold_count},
            {"maximum_hold_count": policy.maximum_hold_count},
            "the number of held pairs is within the policy bound",
            "review held pairs and rebuild the window after resolution",
        ),
        _check(
            4,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.BLOCKED_LIMIT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            batch.release_blocked_count <= policy.maximum_blocked_count,
            {"blocked_count": batch.release_blocked_count},
            {"maximum_blocked_count": policy.maximum_blocked_count},
            "blocked pair count is within the policy bound",
            "remove blocked pairs or repair their verification failures",
        ),
        _check(
            5,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.CHANGED_ARTIFACT_LIMIT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            changed_artifacts <= policy.maximum_changed_artifact_count,
            {"changed_artifact_count": changed_artifacts},
            {"maximum_changed_artifact_count": policy.maximum_changed_artifact_count},
            "changed artifact content is within the declared release bound",
            "inspect changed artifact rows and obtain a newly verified baseline",
        ),
        _check(
            6,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.REQUIRED_REMOVAL_LIMIT,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            removed_required <= policy.maximum_removed_required_count,
            {"removed_required_count": removed_required},
            {"maximum_removed_required_count": policy.maximum_removed_required_count},
            "required artifact removals are within the declared release bound",
            "restore required artifacts or explicitly revise the policy",
        ),
        _check(
            7,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.ALL_ACCEPTED,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            all_accepted or not policy.require_all_accepted,
            {"accepted_count": batch.accepted_count, "item_count": batch.item_count},
            {"require_all_accepted": policy.require_all_accepted},
            "pair acceptance follows the policy requirement",
            "repair rejected pairs or choose a reviewed policy that permits them",
        ),
        _check(
            8,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.ALL_RELEASE_READY,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER
            if policy.require_all_release_ready
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.WARNING,
            all_release_ready,
            {
                "release_ready_count": batch.release_ready_count,
                "item_count": batch.item_count,
            },
            {"require_all_release_ready": policy.require_all_release_ready},
            "pair release readiness follows the policy requirement",
            "resolve every held pair before promotion, or record a reviewed exception",
        ),
        _check(
            9,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.PUBLIC_BOUNDARY,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            _public_boundary(batch.to_dict()) and _public_boundary(policy.to_dict()),
            {"path_free": True, "identity_free": True},
            {"path_free": True, "identity_free": True},
            "matrix and policy projections stay inside the public boundary",
            "remove private, identity, path, or transport fields before release",
        ),
        _check(
            10,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind.CONSERVATION,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER,
            batch.item_count == len(batch.items)
            and batch.accepted_count <= batch.item_count
            and batch.release_ready_count <= batch.item_count
            and abs(batch.score - batch.release_ready_count / batch.item_count) <= 1e-12,
            {
                "item_count": batch.item_count,
                "accepted_count": batch.accepted_count,
                "release_ready_count": batch.release_ready_count,
                "score": batch.score,
            },
            {"conserved": True},
            "matrix counts and readiness score are conserved before policy evaluation",
            "rebuild the matrix from verified pair outcomes",
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
    batch: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy
    | None = None,
    *,
    window_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow:
    """Build one addressed release-window decision from a verified matrix."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(batch)
    if policy is None:
        policy = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy()
    if not isinstance(
        policy,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy,
    ):
        raise ValidationError("release-window policy must be typed")
    policy._validate()
    window_id = _text(window_id, "release-window ID", 256)
    checks = _checks(batch, policy)
    blocker_count = sum(
        not item.passed
        and item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.BLOCKER.value
        for item in checks
    )
    warning_count = sum(
        not item.passed
        and item.severity
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity.WARNING.value
        for item in checks
    )
    passed_count = sum(item.passed for item in checks)
    state = (
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.BLOCKED
        if blocker_count
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.HOLD
        if warning_count
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.PROMOTABLE
    )
    body = {
        "window_id": window_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_BOUNDARY,
        "batch_address": batch.content_address,
        "policy_address": policy.content_address,
        "state": state.value,
        "release_ready": not blocker_count and not warning_count and batch.accepted,
        "item_count": batch.item_count,
        "accepted_count": batch.accepted_count,
        "release_ready_count": batch.release_ready_count,
        "score": batch.score,
        "changed_artifact_count": sum(item.changed_artifact_count for item in batch.items),
        "removed_required_count": sum(item.removed_required_count for item in batch.items),
        "promotable_count": batch.promotable_count,
        "hold_count": batch.hold_count,
        "release_blocked_count": batch.release_blocked_count,
        "checks": checks,
        "check_count": len(checks),
        "passed_count": passed_count,
        "warning_count": warning_count,
        "blocker_count": blocker_count,
        "accepted": batch.accepted,
        "detail": "release-window matrix policy evaluation completed",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_BOUNDARY
        + ":pending-window",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories(
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    *,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowPolicy
    | None = None,
    batch_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch"
    ),
    window_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow:
    """Load persisted packet pairs, build a matrix, then evaluate a policy."""

    batch = build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories(
        pairs, batch_id=batch_id
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        batch, policy, window_id=window_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow:
    """Verify checks, state conservation, and the aggregate address."""

    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    ):
        raise ValidationError("release-window verification requires a typed window")
    for item in value.checks:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_check(
                item
            )
            != item.content_address
        ):
            raise ValidationError("release-window check address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            value
        )
        != value.content_address
    ):
        raise ValidationError("release-window address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "window_id",
        "batch_address",
        "policy_address",
        "state",
        "release_ready",
        "item_count",
        "accepted_count",
        "release_ready_count",
        "score",
        "changed_artifact_count",
        "removed_required_count",
        "check_count",
        "passed_count",
        "warning_count",
        "blocker_count",
        "accepted",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.summary())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window",
        "",
        f"- window: `{value.window_id}`",
        f"- state: **{value.state}**",
        f"- release ready: `{str(value.release_ready).lower()}`",
        f"- pairs: `{value.item_count}`; score: `{value.score:.6f}`",
        f"- checks: `{value.passed_count}/{value.check_count}` passed; warnings: `{value.warning_count}`; blockers: `{value.blocker_count}`",
        f"- address: `{value.content_address}`",
        "",
        "## Policy checks",
        "",
        "| # | Kind | Severity | Passed | Observed | Expected | Detail |",
        "|---:|---|---|---|---|---|---|",
    ]
    for item in value.checks:
        lines.append(
            f"| {item.ordinal} | {item.kind} | {item.severity} | {str(item.passed).lower()} | "
            f"`{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` | {item.detail} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_schema() -> (
    dict[str, Any]
):
    """Describe the release-window aggregate contract."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_BOUNDARY,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState
        ],
        "check_kinds": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckKind
        ],
        "check_severities": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowCheckSeverity
        ],
        "conservation": [
            "matrix_counts",
            "policy_check_count",
            "passed_warning_blocker_counts",
            "score",
            "release_ready",
        ],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
        "limits": {
            "max_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_CHECKS,
            "max_query_limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_MAX_LIMIT,
        },
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_capabilities() -> (
    dict[str, Any]
):
    """List stable release-window operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_VERSION,
        "operations": [
            "build_policy",
            "build_from_matrix",
            "build_from_directories",
            "verify",
            "json",
            "csv",
            "markdown",
            "query",
            "runtime",
            "assurance",
        ],
        "policy_controls": [
            "minimum_items",
            "minimum_score",
            "maximum_hold_count",
            "maximum_blocked_count",
            "maximum_changed_artifact_count",
            "maximum_removed_required_count",
            "require_all_accepted",
            "require_all_release_ready",
        ],
        "projections": ["summary", "checks"],
        "bounded": True,
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
        "fail_closed": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window"
    )
]

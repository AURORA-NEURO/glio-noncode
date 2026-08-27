"""Compare, review, and release portable replication packets.

Packet directories are immutable review inputs.  This module never edits
either side of a comparison; it loads and verifies them, classifies every
artifact and check identity, then derives a separate release decision.  The
decision intentionally distinguishes a valid diff from a promotable diff:
changed or removed evidence can be described perfectly and still be held for
review.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
    load_module_workbench_execution_packet_archive_store_replication_packet,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_CHECK_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_artifact,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_check,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from .serialization import canonical_json


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


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field)
    if ":" not in normalized:
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the supported bound")


def _ratio(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 1:
        raise ValidationError(f"{field} must be between zero and one")


def _artifact_check(
    artifact_id: str,
    action: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction,
    left: Mapping[str, Any] | None,
    right: Mapping[str, Any] | None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact:
    left_address = left.get("content_address") if left else None
    right_address = right.get("content_address") if right else None
    left_bytes = int(left.get("byte_count", 0)) if left else 0
    right_bytes = int(right.get("byte_count", 0)) if right else 0
    required = bool((right or left or {}).get("required", False))
    right_accepted = bool((right or {}).get("accepted", False))
    if action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED:
        accepted = not required
        detail = "optional artifact removed" if accepted else "required artifact removed"
    elif action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.CHANGED:
        accepted = right_accepted
        detail = "artifact address or byte count changed"
    elif action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.ADDED:
        accepted = right_accepted
        detail = "artifact added to candidate packet"
    else:
        accepted = right_accepted
        detail = "artifact address and byte count are unchanged"
    body = {
        "ordinal": 0,
        "artifact_id": artifact_id,
        "action": action,
        "left_address": left_address,
        "right_address": right_address,
        "left_byte_count": left_bytes,
        "right_byte_count": right_bytes,
        "required": required,
        "accepted": accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_PREFIX
        + ":pending-artifact",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_artifact(
            provisional
        ),
    )


def _check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "state": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState.PASSED
        if passed
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheckState.FAILED,
        "passed": passed,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_CHECK_PREFIX
        + ":pending-check",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_check(
            provisional
        ),
    )


def _action(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None):
    if left is None:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.ADDED
    if right is None:
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
    if left.get("content_address") == right.get("content_address"):
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.UNCHANGED
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.CHANGED


def _packet_artifacts(
    packet: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
) -> dict[str, Mapping[str, Any]]:
    return {item.artifact_id: item.to_dict() for item in packet.artifacts}


def _packet_checks(
    packet: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
) -> dict[str, Mapping[str, Any]]:
    return {item.check_id: item.to_dict() for item in packet.checks}


def build_module_workbench_execution_packet_archive_store_replication_packet_diff(
    left: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
    right: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket,
    *,
    diff_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff:
    """Compare two typed, already-loaded packet manifests."""

    if not isinstance(left, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket):
        raise ValidationError("left packet diff input must be typed")
    if not isinstance(right, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacket):
        raise ValidationError("right packet diff input must be typed")
    left_artifacts = _packet_artifacts(left)
    right_artifacts = _packet_artifacts(right)
    rows: list[ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact] = []
    for ordinal, artifact_id in enumerate(sorted(set(left_artifacts) | set(right_artifacts))):
        row = _artifact_check(
            artifact_id,
            _action(left_artifacts.get(artifact_id), right_artifacts.get(artifact_id)),
            left_artifacts.get(artifact_id),
            right_artifacts.get(artifact_id),
        )
        rows.append(
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact(
                ordinal=ordinal,
                artifact_id=row.artifact_id,
                action=row.action,
                left_address=row.left_address,
                right_address=row.right_address,
                left_byte_count=row.left_byte_count,
                right_byte_count=row.right_byte_count,
                required=row.required,
                accepted=row.accepted,
                detail=row.detail,
                content_address="pending:diff-artifact",
            )
        )
        rows[-1] = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffArtifact(
            ordinal=ordinal,
            artifact_id=row.artifact_id,
            action=row.action,
            left_address=row.left_address,
            right_address=row.right_address,
            left_byte_count=row.left_byte_count,
            right_byte_count=row.right_byte_count,
            required=row.required,
            accepted=row.accepted,
            detail=row.detail,
            content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_artifact(
                rows[-1]
            ),
        )
    checks = (
        _check(
            "diff-format",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.FORMAT,
            left.version == right.version and left.boundary == right.boundary,
            {"left_version": left.version, "right_version": right.version},
            {"version": left.version, "boundary": left.boundary},
            "left and right packet formats use one published boundary",
        ),
        _check(
            "diff-reference",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.REFERENCE,
            bool(left.plan_address) and bool(right.plan_address),
            {"left_plan": left.plan_address, "right_plan": right.plan_address},
            "addressed plan references",
            "both packet sides reference an addressed replication plan",
        ),
        _check(
            "diff-candidate-acceptance",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            right.accepted,
            right.accepted,
            True,
            "candidate packet must be internally accepted",
        ),
        _check(
            "diff-artifact-actions",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.ARTIFACT,
            all(item.accepted for item in rows),
            tuple(item.action for item in rows),
            "accepted artifact actions",
            "artifact changes are classified without hidden conflicts",
        ),
        _check(
            "diff-required-removals",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            not any(
                item.required
                and item.action
                is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
                for item in rows
            ),
            sum(
                item.required
                and item.action
                is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
                for item in rows
            ),
            0,
            "required artifacts cannot disappear from a candidate packet",
        ),
        _check(
            "diff-public-boundary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.PUBLIC,
            _public_boundary({"left": left.to_dict(), "right": right.to_dict()}),
            "forbidden-key scan",
            "no private or attribution keys",
            "both packet manifests remain within the public boundary",
        ),
    )
    added = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.ADDED
        for item in rows
    )
    removed = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
        for item in rows
    )
    changed = sum(
        item.action is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.CHANGED
        for item in rows
    )
    unchanged = sum(
        item.action
        is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.UNCHANGED
        for item in rows
    )
    removed_required = sum(
        item.required
        and item.action
        is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.REMOVED
        for item in rows
    )
    if left.content_address == right.content_address:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.MATCHED
    elif removed_required or not right.accepted or not all(item.accepted for item in rows):
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.BLOCKED
    elif changed:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.CHANGED
    elif added and not removed:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.EXTENDED
    else:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.DIVERGED
    total = max(len(rows), 1)
    release_allowed = (
        all(item.passed for item in checks)
        and state
        in {
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.MATCHED,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.EXTENDED,
        }
        and not changed
    )
    body = {
        "diff_id": diff_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_VERSION,
        "boundary": (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_BOUNDARY
        ),
        "left_packet_address": left.content_address,
        "right_packet_address": right.content_address,
        "left_plan_address": left.plan_address,
        "right_plan_address": right.plan_address,
        "state": state,
        "artifacts": tuple(rows),
        "checks": checks,
        "artifact_count": len(rows),
        "added_artifact_count": added,
        "removed_artifact_count": removed,
        "changed_artifact_count": changed,
        "unchanged_artifact_count": unchanged,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "removed_required_count": removed_required,
        "right_accepted": right.accepted,
        "release_allowed": release_allowed,
        "change_ratio": (added + removed + changed) / total,
        "accepted": all(item.passed for item in checks),
        "detail": "packet boundaries compared with explicit artifact actions",
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_PREFIX
        + ":pending-diff",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
    *,
    release_id: str = (
        "glio-noncode-module-workbench-execution-archive-store-replication-packet-release"
    ),
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease:
    """Derive a promotable, held, or blocked release decision."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff(diff)
    checks = (
        _check(
            "release-diff-accepted",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            diff.accepted,
            diff.accepted,
            True,
            "diff must be structurally accepted",
        ),
        _check(
            "release-candidate-accepted",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            diff.right_accepted,
            diff.right_accepted,
            True,
            "candidate packet must be accepted",
        ),
        _check(
            "release-no-required-removal",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            diff.removed_required_count == 0,
            diff.removed_required_count,
            0,
            "required candidate evidence must remain present",
        ),
        _check(
            "release-no-content-change",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            diff.changed_artifact_count == 0,
            diff.changed_artifact_count,
            0,
            "changed artifact bytes require explicit review",
        ),
        _check(
            "release-state",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.RELEASE,
            diff.state
            in {
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.MATCHED,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.EXTENDED,
            },
            diff.state,
            "matched or extended",
            "only matched or append-only packet boundaries can release",
        ),
        _check(
            "release-public-boundary",
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffPlane.PUBLIC,
            _public_boundary(diff.to_dict()),
            "forbidden-key scan",
            "no private or attribution keys",
            "release decision remains public and identity-free",
        ),
    )
    passed = sum(item.passed for item in checks)
    if not diff.accepted:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.BLOCKED
    elif all(item.passed for item in checks):
        state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE
        )
    else:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.HOLD
    body = {
        "release_id": release_id,
        "diff_address": diff.content_address,
        "candidate_packet_address": diff.right_packet_address,
        "state": state,
        "checks": checks,
        "check_count": len(checks),
        "passed_count": passed,
        "accepted": state
        is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE,
        "detail": (
            "candidate packet is promotable"
            if state
            is (
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE
            )
            else "candidate packet release is held or blocked"
        ),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_PREFIX
        + ":pending-release",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
            provisional
        ),
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff:
    """Verify all nested diff rows and the aggregate address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff):
        raise ValidationError("packet diff verification requires a typed diff")
    for item in value.artifacts:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_artifact(
                item
            )
            != item.content_address
        ):
            raise ValidationError("packet diff artifact address mismatch")
    for item in value.checks:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_check(
                item
            )
            != item.content_address
        ):
            raise ValidationError("packet diff check address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff(value)
        != value.content_address
    ):
        raise ValidationError("packet diff address mismatch")
    return value


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease:
    """Verify a release decision and its check addresses."""

    if not isinstance(
        value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease
    ):
        raise ValidationError("packet diff release verification requires a typed release")
    for item in value.checks:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_check(
                item
            )
            != item.content_address
        ):
            raise ValidationError("packet diff release check address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
            value
        )
        != value.content_address
    ):
        raise ValidationError("packet diff release address mismatch")
    return value


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs(
    left_directory: str | Path,
    right_directory: str | Path,
    *,
    diff_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff:
    """Load and verify two packet directories before comparing them."""

    left, _ = load_module_workbench_execution_packet_archive_store_replication_packet(
        left_directory
    )
    right, _ = load_module_workbench_execution_packet_archive_store_replication_packet(
        right_directory
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff(
        left, right, diff_id=diff_id
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffRelease,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff(value)
    output = io.StringIO(newline="")
    fields = (
        "resource",
        "ordinal",
        "artifact_id",
        "action",
        "left_address",
        "right_address",
        "left_byte_count",
        "right_byte_count",
        "required",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.artifacts:
        writer.writerow({"resource": "artifact", **item.to_dict()})
    for ordinal, item in enumerate(value.checks):
        writer.writerow(
            {
                "resource": "check",
                "ordinal": ordinal,
                "artifact_id": item.check_id,
                "action": item.state,
                "required": None,
                "accepted": item.passed,
                "detail": item.detail,
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiff,
) -> str:
    """Render a diff with action-level review detail."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff(value)
    lines = [
        "# Archive Store Replication Packet Diff",
        "",
        f"- Diff: `{value.diff_id}`",
        f"- Address: `{value.content_address}`",
        f"- State: `{value.state}`",
        f"- Artifacts added/removed/changed/unchanged: "
        f"`{value.added_artifact_count}`/`{value.removed_artifact_count}`/"
        f"`{value.changed_artifact_count}`/`{value.unchanged_artifact_count}`",
        f"- Checks: `{value.passed_count}/{value.check_count}`",
        f"- Release allowed: `{str(value.release_allowed).lower()}`",
        "",
        "| Ordinal | Artifact | Action | Left | Right | Required | Accepted |",
        "|---:|---|---|---|---|---:|---:|",
    ]
    for item in value.artifacts:
        lines.append(
            f"| {item.ordinal} | `{item.artifact_id}` | `{item.action}` | "
            f"`{item.left_address or ''}` | `{item.right_address or ''}` | "
            f"{str(item.required).lower()} | {str(item.accepted).lower()} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_schema_document() -> (
    dict[str, Any]
):
    """Return a schema alias suitable for CLI/API documents."""

    from .module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (
        module_workbench_execution_packet_archive_store_replication_packet_diff_schema,
    )

    return module_workbench_execution_packet_archive_store_replication_packet_diff_schema()

"""Deterministic public comparisons for mission-plan releases.

This module compares only address-verified public receipts.  It explains how
workflow structure, decisions, and aggregate resources changed while keeping
the comparison free of internal routing and request metadata.  The result is
addressed and can be exported for review or used as a release gate.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import MissionPlanOfflineRelease, load_mission_plan_release
from .mission_runtime_public import (
    MissionPlanPublicReceipt,
    MissionPublicWorkflowStep,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_DIFF_VERSION = "mission-plan-release-diff-v1"
MISSION_PLAN_RELEASE_DIFF_SCHEMA_VERSION = "mission-plan-release-diff-schema-v1"
MISSION_PLAN_RELEASE_DIFF_CAPABILITIES_VERSION = "mission-plan-release-diff-capabilities-v1"


def _text(value: Any, field: str) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _step_address(step: MissionPublicWorkflowStep) -> str:
    return content_hash(step.to_dict(), prefix="mission-plan-release-step")


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseStepDiff:
    """One workflow-step comparison."""

    step_id: str
    left_address: str | None
    right_address: str | None
    left_kind: str | None
    right_kind: str | None
    changed: bool
    changed_fields: tuple[str, ...]
    left_step: MissionPublicWorkflowStep | None
    right_step: MissionPublicWorkflowStep | None
    content_address: str

    def __post_init__(self) -> None:
        _text(self.step_id, "step_diff.step_id")
        if not self.left_address and not self.right_address:
            raise ValidationError("step diff must contain a left or right step")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "step_id": self.step_id,
            "left_address": self.left_address,
            "right_address": self.right_address,
            "left_kind": self.left_kind,
            "right_kind": self.right_kind,
            "changed": self.changed,
            "changed_fields": list(self.changed_fields),
            "left_step": None if self.left_step is None else self.left_step.to_dict(),
            "right_step": None if self.right_step is None else self.right_step.to_dict(),
        }
        return body | {"content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseDiff:
    """Addressed comparison of two public mission-plan releases."""

    diff_version: str
    left_release_id: str
    right_release_id: str
    left_plan_id: str
    right_plan_id: str
    left_plan_address: str
    right_plan_address: str
    state_changed: bool
    decision_changed: bool
    workflow_changed: bool
    changed_fields: tuple[str, ...]
    added_step_ids: tuple[str, ...]
    removed_step_ids: tuple[str, ...]
    changed_step_ids: tuple[str, ...]
    unchanged_step_ids: tuple[str, ...]
    step_diffs: tuple[MissionPlanReleaseStepDiff, ...]
    resource_delta: Mapping[str, float]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.diff_version != MISSION_PLAN_RELEASE_DIFF_VERSION:
            raise ValidationError("mission plan release diff version is invalid")
        for field in (
            "left_release_id",
            "right_release_id",
            "left_plan_id",
            "right_plan_id",
            "left_plan_address",
            "right_plan_address",
        ):
            _text(getattr(self, field), f"diff.{field}")
        if len(self.added_step_ids) != len(set(self.added_step_ids)):
            raise ValidationError("diff added step IDs must be unique")
        if len(self.removed_step_ids) != len(set(self.removed_step_ids)):
            raise ValidationError("diff removed step IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "diff_version": self.diff_version,
            "left_release_id": self.left_release_id,
            "right_release_id": self.right_release_id,
            "left_plan_id": self.left_plan_id,
            "right_plan_id": self.right_plan_id,
            "left_plan_address": self.left_plan_address,
            "right_plan_address": self.right_plan_address,
            "state_changed": self.state_changed,
            "decision_changed": self.decision_changed,
            "workflow_changed": self.workflow_changed,
            "changed_fields": list(self.changed_fields),
            "added_step_ids": list(self.added_step_ids),
            "removed_step_ids": list(self.removed_step_ids),
            "changed_step_ids": list(self.changed_step_ids),
            "unchanged_step_ids": list(self.unchanged_step_ids),
            "step_diffs": [item.to_dict() for item in self.step_diffs],
            "resource_delta": dict(self.resource_delta),
            "accepted": self.accepted,
        }
        return body | {"content_address": self.content_address}


def _as_receipt(
    value: MissionPlanOfflineRelease | MissionPlanPublicReceipt | str | Path | Mapping[str, Any],
) -> tuple[str, MissionPlanPublicReceipt]:
    if isinstance(value, MissionPlanOfflineRelease):
        return value.release_id, value.receipt
    if isinstance(value, MissionPlanPublicReceipt):
        return f"plan-{value.plan_id}", value
    if isinstance(value, (str, Path)):
        offline = load_mission_plan_release(value)
        return offline.release_id, offline.receipt
    body = dict(value)
    if "receipt" in body:
        receipt_value = body.get("receipt")
        if not isinstance(receipt_value, Mapping):
            raise ValidationError("diff receipt field must be an object")
        return _text(body.get("release_id", "receipt-" + str(receipt_value.get("plan_id", ""))), "release_id"), MissionPlanPublicReceipt.from_mapping(receipt_value)
    return f"plan-{body.get('plan_id', '')}", MissionPlanPublicReceipt.from_mapping(body)


def _step_diff(
    step_id: str,
    left: MissionPublicWorkflowStep | None,
    right: MissionPublicWorkflowStep | None,
) -> MissionPlanReleaseStepDiff:
    left_body = None if left is None else left.to_dict()
    right_body = None if right is None else right.to_dict()
    changed_fields: tuple[str, ...] = ()
    if left is not None and right is not None:
        changed_fields = tuple(
            key for key in sorted(set(left_body or {}) | set(right_body or {}))
            if (left_body or {}).get(key) != (right_body or {}).get(key)
        )
    body = {
        "step_id": step_id,
        "left_address": None if left is None else _step_address(left),
        "right_address": None if right is None else _step_address(right),
        "left_kind": None if left is None else left.kind,
        "right_kind": None if right is None else right.kind,
        "changed": left_body != right_body,
        "changed_fields": changed_fields,
        "left_step": left,
        "right_step": right,
    }
    address_body = {
        key: (value.to_dict() if isinstance(value, MissionPublicWorkflowStep) else value)
        for key, value in body.items()
    }
    return MissionPlanReleaseStepDiff(
        **body,
        content_address=content_hash(address_body, prefix="mission-plan-release-step-diff"),
    )


def diff_mission_plan_releases(
    left: MissionPlanOfflineRelease | MissionPlanPublicReceipt | str | Path | Mapping[str, Any],
    right: MissionPlanOfflineRelease | MissionPlanPublicReceipt | str | Path | Mapping[str, Any],
) -> MissionPlanReleaseDiff:
    """Compare two verified releases or public receipt mappings."""

    left_release_id, left_receipt = _as_receipt(left)
    right_release_id, right_receipt = _as_receipt(right)
    left_steps = {step.step_id: step for step in left_receipt.steps}
    right_steps = {step.step_id: step for step in right_receipt.steps}
    all_ids = tuple(dict.fromkeys((*left_steps, *right_steps)))
    step_diffs = tuple(
        _step_diff(step_id, left_steps.get(step_id), right_steps.get(step_id))
        for step_id in all_ids
        if left_steps.get(step_id) is None
        or right_steps.get(step_id) is None
        or left_steps[step_id].to_dict() != right_steps[step_id].to_dict()
    )
    added = tuple(step_id for step_id in all_ids if step_id not in left_steps)
    removed = tuple(step_id for step_id in all_ids if step_id not in right_steps)
    changed = tuple(
        step_id
        for step_id in all_ids
        if step_id in left_steps
        and step_id in right_steps
        and left_steps[step_id].to_dict() != right_steps[step_id].to_dict()
    )
    unchanged = tuple(
        step_id
        for step_id in all_ids
        if step_id in left_steps
        and step_id in right_steps
        and left_steps[step_id].to_dict() == right_steps[step_id].to_dict()
    )
    left_body = left_receipt.to_dict()
    right_body = right_receipt.to_dict()
    compared_fields = (
        "mission_id",
        "state",
        "accepted",
        "decision",
        "abstained",
        "requires_human_review",
        "workflow_id",
        "step_count",
        "total_cpu",
        "peak_memory_gb",
        "total_storage_gb",
        "max_seconds",
        "selected_role_count",
        "selected_operation_count",
        "registry_address",
        "warning_count",
        "boundary_accepted",
    )
    changed_fields = tuple(
        field for field in compared_fields if left_body.get(field) != right_body.get(field)
    )
    resource_delta = {
        "step_count": float(right_receipt.step_count - left_receipt.step_count),
        "total_cpu": float(right_receipt.total_cpu - left_receipt.total_cpu),
        "peak_memory_gb": float(right_receipt.peak_memory_gb - left_receipt.peak_memory_gb),
        "total_storage_gb": float(right_receipt.total_storage_gb - left_receipt.total_storage_gb),
        "max_seconds": float(right_receipt.max_seconds - left_receipt.max_seconds),
    }
    body = {
        "diff_version": MISSION_PLAN_RELEASE_DIFF_VERSION,
        "left_release_id": left_release_id,
        "right_release_id": right_release_id,
        "left_plan_id": left_receipt.plan_id,
        "right_plan_id": right_receipt.plan_id,
        "left_plan_address": left_receipt.content_address,
        "right_plan_address": right_receipt.content_address,
        "state_changed": left_receipt.state != right_receipt.state,
        "decision_changed": left_receipt.decision != right_receipt.decision,
        "workflow_changed": bool(added or removed or changed),
        "changed_fields": changed_fields,
        "added_step_ids": added,
        "removed_step_ids": removed,
        "changed_step_ids": changed,
        "unchanged_step_ids": unchanged,
        "step_diffs": step_diffs,
        "resource_delta": resource_delta,
        "accepted": True,
    }
    address_body = jsonable(body)
    return MissionPlanReleaseDiff(
        **body,
        content_address=content_hash(address_body, prefix="mission-plan-release-diff"),
    )


def mission_plan_release_diff_json(diff: MissionPlanReleaseDiff) -> str:
    """Render a canonical diff JSON document."""

    return canonical_json(diff.to_dict()) + "\n"


def mission_plan_release_diff_csv(diff: MissionPlanReleaseDiff) -> str:
    """Render one deterministic row per changed or added/removed step."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "step_id",
            "change",
            "left_address",
            "right_address",
            "left_kind",
            "right_kind",
            "changed_fields",
        )
    )
    for item in diff.step_diffs:
        if item.left_address is None:
            change = "added"
        elif item.right_address is None:
            change = "removed"
        else:
            change = "changed"
        writer.writerow(
            (
                item.step_id,
                change,
                item.left_address,
                item.right_address,
                item.left_kind,
                item.right_kind,
                "|".join(item.changed_fields),
            )
        )
    return output.getvalue()


def mission_plan_release_diff_markdown(diff: MissionPlanReleaseDiff) -> str:
    """Render a human-readable public release comparison."""

    lines = [
        "# Mission plan release diff",
        "",
        f"- Left plan: `{diff.left_plan_id}`",
        f"- Right plan: `{diff.right_plan_id}`",
        f"- State changed: `{diff.state_changed}`",
        f"- Decision changed: `{diff.decision_changed}`",
        f"- Workflow changed: `{diff.workflow_changed}`",
        f"- Added steps: `{len(diff.added_step_ids)}`",
        f"- Removed steps: `{len(diff.removed_step_ids)}`",
        f"- Changed steps: `{len(diff.changed_step_ids)}`",
        "",
        "| Step | Change | Left kind | Right kind | Fields |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in diff.step_diffs:
        if item.left_address is None:
            change = "added"
        elif item.right_address is None:
            change = "removed"
        else:
            change = "changed"
        lines.append(
            f"| `{item.step_id}` | `{change}` | `{item.left_kind or 'none'}` | "
            f"`{item.right_kind or 'none'}` | `{', '.join(item.changed_fields) or 'none'}` |"
        )
    lines.extend(("", "Resource delta:", ""))
    for key, value in diff.resource_delta.items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def mission_plan_release_diff_export_payloads(diff: MissionPlanReleaseDiff) -> dict[str, str]:
    """Return deterministic JSON, Markdown, and CSV diff artifacts."""

    return {
        "mission-plan-release-diff.json": mission_plan_release_diff_json(diff),
        "mission-plan-release-diff.md": mission_plan_release_diff_markdown(diff),
        "mission-plan-release-diff.csv": mission_plan_release_diff_csv(diff),
    }


def mission_plan_release_diff_schema() -> dict[str, Any]:
    """Return the public comparison contract."""

    return {
        "version": MISSION_PLAN_RELEASE_DIFF_SCHEMA_VERSION,
        "diff_version": MISSION_PLAN_RELEASE_DIFF_VERSION,
        "type": "object",
        "step_diff_fields": [
            "step_id",
            "left_address",
            "right_address",
            "left_kind",
            "right_kind",
            "changed",
            "changed_fields",
            "left_step",
            "right_step",
            "content_address",
        ],
        "resource_delta_fields": [
            "step_count",
            "total_cpu",
            "peak_memory_gb",
            "total_storage_gb",
            "max_seconds",
        ],
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_diff_capabilities() -> dict[str, Any]:
    """Return operational comparison capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_DIFF_CAPABILITIES_VERSION,
        "verified_release_input": True,
        "public_receipt_input": True,
        "step_level_comparison": True,
        "aggregate_resource_delta": True,
        "state_and_decision_comparison": True,
        "content_addressed": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_DIFF_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_DIFF_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_DIFF_VERSION",
    "MissionPlanReleaseDiff",
    "MissionPlanReleaseStepDiff",
    "diff_mission_plan_releases",
    "mission_plan_release_diff_capabilities",
    "mission_plan_release_diff_csv",
    "mission_plan_release_diff_export_payloads",
    "mission_plan_release_diff_json",
    "mission_plan_release_diff_markdown",
    "mission_plan_release_diff_schema",
]

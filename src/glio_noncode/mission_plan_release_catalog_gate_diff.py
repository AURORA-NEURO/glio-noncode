"""Structural diffs for public mission-plan catalog-gate decisions.

Gate decisions are immutable projections, but release review often compares a
new decision with a previous decision.  This module keeps that comparison
public, deterministic, and failure-visible.  It compares addressed checks and
policy values without reopening planner state, executing handlers, or copying
private request metadata.  Added, removed, changed, and unchanged checks are
retained with their before/after addresses so a consumer can explain exactly
what changed between two handoff attempts.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGate,
    MissionPlanReleaseCatalogGateCheck,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_VERSION = "mission-plan-release-catalog-gate-diff-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_SCHEMA_VERSION = "mission-plan-release-catalog-gate-diff-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_CAPABILITIES_VERSION = "mission-plan-release-catalog-gate-diff-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_MAX_CHECKS = 64

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "email",
        "generated_by",
        "identity",
        "language",
        "model",
        "model_id",
        "patient",
        "producer",
        "programming_language",
        "raw_request",
        "request",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise ValidationError(f"{field} must be non-negative")
    return parsed


def _private_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child_path)
            paths.extend(_private_paths(child, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_private_paths(child, f"{path}[{index}]"))
        return tuple(paths)
    return ()


class MissionPlanReleaseCatalogGateDiffStatus(StrEnum):
    """Stable classification for one check identity across two gates."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateCheckDiff:
    """Addressed before/after comparison for one gate check."""

    check_id: str
    status: MissionPlanReleaseCatalogGateDiffStatus
    left_address: str | None
    right_address: str | None
    left_accepted: bool | None
    right_accepted: bool | None
    changed_fields: tuple[str, ...]
    left_check: MissionPlanReleaseCatalogGateCheck | None
    right_check: MissionPlanReleaseCatalogGateCheck | None
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "catalog_gate_check_diff.check_id", maximum=128)
        if not isinstance(self.status, MissionPlanReleaseCatalogGateDiffStatus):
            raise ValidationError("catalog gate check diff status is invalid")
        for field in ("left_address", "right_address", "content_address"):
            value = getattr(self, field)
            if value is not None:
                _text(value, f"catalog_gate_check_diff.{field}")
        for field in ("left_accepted", "right_accepted"):
            value = getattr(self, field)
            if value is not None:
                _bool(value, f"catalog_gate_check_diff.{field}")
        if tuple(self.changed_fields) != tuple(sorted(set(self.changed_fields))):
            raise ValidationError("catalog gate check diff fields must be unique and sorted")
        _text(self.content_address, "catalog_gate_check_diff.content_address")
        if self.status is MissionPlanReleaseCatalogGateDiffStatus.ADDED and self.right_check is None:
            raise ValidationError("added check diff requires a right check")
        if self.status is MissionPlanReleaseCatalogGateDiffStatus.REMOVED and self.left_check is None:
            raise ValidationError("removed check diff requires a left check")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateCheckDiff":
        body = _mapping(value, "catalog gate check diff")
        allowed = {
            "check_id",
            "status",
            "left_address",
            "right_address",
            "left_accepted",
            "right_accepted",
            "changed_fields",
            "left_check",
            "right_check",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate check diff contains unsupported fields: {sorted(unknown)}")
        try:
            status = MissionPlanReleaseCatalogGateDiffStatus(str(body.get("status")))
        except ValueError as exc:
            raise ValidationError("catalog gate check diff status is invalid") from exc
        raw_fields = body.get("changed_fields", ())
        if isinstance(raw_fields, (str, bytes)) or not isinstance(raw_fields, (list, tuple)):
            raise ValidationError("catalog gate check diff fields must be an array")
        fields = tuple(_text(item, "catalog_gate_check_diff.changed_fields", maximum=64) for item in raw_fields)
        left_raw = body.get("left_check")
        right_raw = body.get("right_check")
        diff = cls(
            check_id=_text(body.get("check_id"), "catalog_gate_check_diff.check_id", maximum=128),
            status=status,
            left_address=None if body.get("left_address") is None else _text(body.get("left_address"), "catalog_gate_check_diff.left_address"),
            right_address=None if body.get("right_address") is None else _text(body.get("right_address"), "catalog_gate_check_diff.right_address"),
            left_accepted=None if body.get("left_accepted") is None else _bool(body.get("left_accepted"), "catalog_gate_check_diff.left_accepted"),
            right_accepted=None if body.get("right_accepted") is None else _bool(body.get("right_accepted"), "catalog_gate_check_diff.right_accepted"),
            changed_fields=fields,
            left_check=None if left_raw is None else MissionPlanReleaseCatalogGateCheck.from_mapping(left_raw),
            right_check=None if right_raw is None else MissionPlanReleaseCatalogGateCheck.from_mapping(right_raw),
            content_address=_text(body.get("content_address"), "catalog_gate_check_diff.content_address"),
        )
        expected = {
            "check_id": diff.check_id,
            "status": diff.status,
            "left_address": diff.left_address,
            "right_address": diff.right_address,
            "left_accepted": diff.left_accepted,
            "right_accepted": diff.right_accepted,
            "changed_fields": diff.changed_fields,
            "left_check": diff.left_check,
            "right_check": diff.right_check,
        }
        if diff.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-check-diff"):
            raise ValidationError("catalog gate check diff content address does not reconcile")
        return diff

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateDiff:
    """Addressed structural comparison of two catalog-gate decisions."""

    diff_version: str
    catalog_id: str
    left_gate_address: str
    right_gate_address: str
    left_policy_address: str
    right_policy_address: str
    check_diffs: tuple[MissionPlanReleaseCatalogGateCheckDiff, ...]
    added_check_ids: tuple[str, ...]
    removed_check_ids: tuple[str, ...]
    changed_check_ids: tuple[str, ...]
    unchanged_check_ids: tuple[str, ...]
    acceptance_changed: bool
    policy_changed: bool
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.diff_version != MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_VERSION:
            raise ValidationError("catalog gate diff version is invalid")
        _text(self.catalog_id, "catalog_gate_diff.catalog_id", maximum=96)
        for field in (
            "left_gate_address",
            "right_gate_address",
            "left_policy_address",
            "right_policy_address",
            "content_address",
        ):
            _text(getattr(self, field), f"catalog_gate_diff.{field}")
        if len(self.check_diffs) > MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_MAX_CHECKS:
            raise ValidationError("catalog gate diff check count exceeds the bound")
        identifiers = tuple(item.check_id for item in self.check_diffs)
        if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(set(identifiers)):
            raise ValidationError("catalog gate diff checks must be sorted and unique")
        for field in ("added_check_ids", "removed_check_ids", "changed_check_ids", "unchanged_check_ids"):
            values = getattr(self, field)
            if tuple(values) != tuple(sorted(set(values))):
                raise ValidationError(f"catalog gate diff {field} must be sorted and unique")
        _bool(self.acceptance_changed, "catalog_gate_diff.acceptance_changed")
        _bool(self.policy_changed, "catalog_gate_diff.policy_changed")
        _bool(self.accepted, "catalog_gate_diff.accepted")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateDiff":
        body = _mapping(value, "mission plan release catalog gate diff")
        allowed = {
            "diff_version",
            "catalog_id",
            "left_gate_address",
            "right_gate_address",
            "left_policy_address",
            "right_policy_address",
            "check_count",
            "check_diffs",
            "added_check_ids",
            "removed_check_ids",
            "changed_check_ids",
            "unchanged_check_ids",
            "acceptance_changed",
            "policy_changed",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate diff contains unsupported fields: {sorted(unknown)}")
        raw_diffs = body.get("check_diffs", ())
        if not isinstance(raw_diffs, (list, tuple)):
            raise ValidationError("catalog gate diff check_diffs must be an array")
        check_diffs = tuple(MissionPlanReleaseCatalogGateCheckDiff.from_mapping(item) for item in raw_diffs)
        values: dict[str, tuple[str, ...]] = {}
        for field in ("added_check_ids", "removed_check_ids", "changed_check_ids", "unchanged_check_ids"):
            raw_values = body.get(field, ())
            if isinstance(raw_values, (str, bytes)) or not isinstance(raw_values, (list, tuple)):
                raise ValidationError(f"catalog gate diff {field} must be an array")
            values[field] = tuple(_text(item, f"catalog_gate_diff.{field}", maximum=128) for item in raw_values)
        diff = cls(
            diff_version=_text(body.get("diff_version"), "catalog_gate_diff.diff_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_gate_diff.catalog_id", maximum=96),
            left_gate_address=_text(body.get("left_gate_address"), "catalog_gate_diff.left_gate_address"),
            right_gate_address=_text(body.get("right_gate_address"), "catalog_gate_diff.right_gate_address"),
            left_policy_address=_text(body.get("left_policy_address"), "catalog_gate_diff.left_policy_address"),
            right_policy_address=_text(body.get("right_policy_address"), "catalog_gate_diff.right_policy_address"),
            check_diffs=check_diffs,
            added_check_ids=values["added_check_ids"],
            removed_check_ids=values["removed_check_ids"],
            changed_check_ids=values["changed_check_ids"],
            unchanged_check_ids=values["unchanged_check_ids"],
            acceptance_changed=_bool(body.get("acceptance_changed"), "catalog_gate_diff.acceptance_changed"),
            policy_changed=_bool(body.get("policy_changed"), "catalog_gate_diff.policy_changed"),
            accepted=_bool(body.get("accepted"), "catalog_gate_diff.accepted"),
            content_address=_text(body.get("content_address"), "catalog_gate_diff.content_address"),
        )
        if body.get("check_count") != len(diff.check_diffs):
            raise ValidationError("catalog gate diff check count does not reconcile")
        status_ids = {
            status: tuple(item.check_id for item in diff.check_diffs if item.status is status)
            for status in MissionPlanReleaseCatalogGateDiffStatus
        }
        for field, status in (
            ("added_check_ids", MissionPlanReleaseCatalogGateDiffStatus.ADDED),
            ("removed_check_ids", MissionPlanReleaseCatalogGateDiffStatus.REMOVED),
            ("changed_check_ids", MissionPlanReleaseCatalogGateDiffStatus.CHANGED),
            ("unchanged_check_ids", MissionPlanReleaseCatalogGateDiffStatus.UNCHANGED),
        ):
            if getattr(diff, field) != status_ids[status]:
                raise ValidationError(f"catalog gate diff {field} does not reconcile")
        expected = _diff_address_body(diff)
        if diff.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-diff"):
            raise ValidationError("catalog gate diff content address does not reconcile")
        if _private_paths(diff.to_dict()):
            raise ValidationError("catalog gate diff contains restricted metadata")
        return diff

    def to_dict(self) -> dict[str, Any]:
        body = {
            "diff_version": self.diff_version,
            "catalog_id": self.catalog_id,
            "left_gate_address": self.left_gate_address,
            "right_gate_address": self.right_gate_address,
            "left_policy_address": self.left_policy_address,
            "right_policy_address": self.right_policy_address,
            "check_count": len(self.check_diffs),
            "check_diffs": self.check_diffs,
            "added_check_ids": list(self.added_check_ids),
            "removed_check_ids": list(self.removed_check_ids),
            "changed_check_ids": list(self.changed_check_ids),
            "unchanged_check_ids": list(self.unchanged_check_ids),
            "acceptance_changed": self.acceptance_changed,
            "policy_changed": self.policy_changed,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _diff_address_body(diff: MissionPlanReleaseCatalogGateDiff) -> dict[str, Any]:
    return {
        "diff_version": diff.diff_version,
        "catalog_id": diff.catalog_id,
        "left_gate_address": diff.left_gate_address,
        "right_gate_address": diff.right_gate_address,
        "left_policy_address": diff.left_policy_address,
        "right_policy_address": diff.right_policy_address,
        "check_diffs": diff.check_diffs,
        "added_check_ids": diff.added_check_ids,
        "removed_check_ids": diff.removed_check_ids,
        "changed_check_ids": diff.changed_check_ids,
        "unchanged_check_ids": diff.unchanged_check_ids,
        "acceptance_changed": diff.acceptance_changed,
        "policy_changed": diff.policy_changed,
        "accepted": diff.accepted,
    }


def _as_gate(value: MissionPlanReleaseCatalogGate | Mapping[str, Any]) -> MissionPlanReleaseCatalogGate:
    if isinstance(value, MissionPlanReleaseCatalogGate):
        return value
    return MissionPlanReleaseCatalogGate.from_mapping(_mapping(value, "catalog gate diff gate"))


def _check_fields(left: MissionPlanReleaseCatalogGateCheck | None, right: MissionPlanReleaseCatalogGateCheck | None) -> tuple[str, ...]:
    if left is None or right is None:
        return ()
    fields = []
    for field in ("category", "accepted", "observed", "expected", "message", "content_address"):
        if getattr(left, field) != getattr(right, field):
            fields.append(field)
    return tuple(sorted(fields))


def diff_mission_plan_release_catalog_gates(
    left: MissionPlanReleaseCatalogGate | Mapping[str, Any],
    right: MissionPlanReleaseCatalogGate | Mapping[str, Any],
) -> MissionPlanReleaseCatalogGateDiff:
    """Compare two public catalog-gate decisions by stable check identity."""

    left_gate = _as_gate(left)
    right_gate = _as_gate(right)
    if left_gate.catalog_id != right_gate.catalog_id:
        raise ValidationError("catalog gate diff requires the same catalog ID")
    left_checks = {item.check_id: item for item in left_gate.checks}
    right_checks = {item.check_id: item for item in right_gate.checks}
    diffs: list[MissionPlanReleaseCatalogGateCheckDiff] = []
    for check_id in sorted(set(left_checks) | set(right_checks)):
        before = left_checks.get(check_id)
        after = right_checks.get(check_id)
        fields = _check_fields(before, after)
        if before is None:
            status = MissionPlanReleaseCatalogGateDiffStatus.ADDED
        elif after is None:
            status = MissionPlanReleaseCatalogGateDiffStatus.REMOVED
        elif fields:
            status = MissionPlanReleaseCatalogGateDiffStatus.CHANGED
        else:
            status = MissionPlanReleaseCatalogGateDiffStatus.UNCHANGED
        body = {
            "check_id": check_id,
            "status": status,
            "left_address": None if before is None else before.content_address,
            "right_address": None if after is None else after.content_address,
            "left_accepted": None if before is None else before.accepted,
            "right_accepted": None if after is None else after.accepted,
            "changed_fields": fields,
            "left_check": before,
            "right_check": after,
        }
        diffs.append(MissionPlanReleaseCatalogGateCheckDiff(**body, content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-check-diff")))
    by_status = {
        status: tuple(item.check_id for item in diffs if item.status is status)
        for status in MissionPlanReleaseCatalogGateDiffStatus
    }
    body = {
        "diff_version": MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_VERSION,
        "catalog_id": left_gate.catalog_id,
        "left_gate_address": left_gate.content_address,
        "right_gate_address": right_gate.content_address,
        "left_policy_address": left_gate.policy.content_address,
        "right_policy_address": right_gate.policy.content_address,
        "check_count": len(diffs),
        "check_diffs": tuple(diffs),
        "added_check_ids": by_status[MissionPlanReleaseCatalogGateDiffStatus.ADDED],
        "removed_check_ids": by_status[MissionPlanReleaseCatalogGateDiffStatus.REMOVED],
        "changed_check_ids": by_status[MissionPlanReleaseCatalogGateDiffStatus.CHANGED],
        "unchanged_check_ids": by_status[MissionPlanReleaseCatalogGateDiffStatus.UNCHANGED],
        "acceptance_changed": left_gate.accepted != right_gate.accepted,
        "policy_changed": left_gate.policy.content_address != right_gate.policy.content_address,
        "accepted": True,
    }
    if len(diffs) > MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_MAX_CHECKS:
        raise ValidationError("catalog gate diff check count exceeds the bound")
    address_body = {key: value for key, value in body.items() if key != "check_count"}
    return MissionPlanReleaseCatalogGateDiff(
        **address_body,
        content_address=content_hash(address_body, prefix="mission-plan-release-catalog-gate-diff"),
    )


def mission_plan_release_catalog_gate_diff_json(diff: MissionPlanReleaseCatalogGateDiff | Mapping[str, Any]) -> str:
    value = diff if isinstance(diff, MissionPlanReleaseCatalogGateDiff) else MissionPlanReleaseCatalogGateDiff.from_mapping(diff)
    return canonical_json(value.to_dict())


def mission_plan_release_catalog_gate_diff_csv(diff: MissionPlanReleaseCatalogGateDiff | Mapping[str, Any]) -> str:
    value = diff if isinstance(diff, MissionPlanReleaseCatalogGateDiff) else MissionPlanReleaseCatalogGateDiff.from_mapping(diff)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("check_id", "status", "left_address", "right_address", "left_accepted", "right_accepted", "changed_fields", "content_address"))
    for item in value.check_diffs:
        writer.writerow((item.check_id, item.status.value, item.left_address or "", item.right_address or "", "" if item.left_accepted is None else str(item.left_accepted).lower(), "" if item.right_accepted is None else str(item.right_accepted).lower(), canonical_json(item.changed_fields), item.content_address))
    return output.getvalue()


def mission_plan_release_catalog_gate_diff_markdown(diff: MissionPlanReleaseCatalogGateDiff | Mapping[str, Any]) -> str:
    value = diff if isinstance(diff, MissionPlanReleaseCatalogGateDiff) else MissionPlanReleaseCatalogGateDiff.from_mapping(diff)
    lines = [
        "# Mission plan release catalog gate diff",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Left gate: `{value.left_gate_address}`",
        f"- Right gate: `{value.right_gate_address}`",
        f"- Added: {len(value.added_check_ids)}",
        f"- Removed: {len(value.removed_check_ids)}",
        f"- Changed: {len(value.changed_check_ids)}",
        f"- Unchanged: {len(value.unchanged_check_ids)}",
        f"- Acceptance changed: {str(value.acceptance_changed).lower()}",
        f"- Policy changed: {str(value.policy_changed).lower()}",
        "",
        "| Check | Status | Left accepted | Right accepted | Changed fields |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.status.value}` | {item.left_accepted if item.left_accepted is not None else ''} | {item.right_accepted if item.right_accepted is not None else ''} | {', '.join(item.changed_fields)} |"
        for item in value.check_diffs
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_gate_diff_export_payloads(diff: MissionPlanReleaseCatalogGateDiff | Mapping[str, Any]) -> dict[str, str]:
    value = diff if isinstance(diff, MissionPlanReleaseCatalogGateDiff) else MissionPlanReleaseCatalogGateDiff.from_mapping(diff)
    return {
        "mission-plan-release-catalog-gate-diff.json": mission_plan_release_catalog_gate_diff_json(value),
        "mission-plan-release-catalog-gate-diff.csv": mission_plan_release_catalog_gate_diff_csv(value),
        "mission-plan-release-catalog-gate-diff.md": mission_plan_release_catalog_gate_diff_markdown(value),
    }


def mission_plan_release_catalog_gate_diff_schema() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_SCHEMA_VERSION,
        "diff_version": MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_VERSION,
        "max_checks": MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_MAX_CHECKS,
        "statuses": [item.value for item in MissionPlanReleaseCatalogGateDiffStatus],
        "check_fields": ["check_id", "status", "left_address", "right_address", "left_accepted", "right_accepted", "changed_fields", "content_address"],
        "result_fields": ["catalog_id", "check_diffs", "added_check_ids", "removed_check_ids", "changed_check_ids", "unchanged_check_ids", "acceptance_changed", "policy_changed", "content_address"],
        "timestamp_free": True,
        "read_only": True,
    }


def mission_plan_release_catalog_gate_diff_capabilities() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_CAPABILITIES_VERSION,
        "check_identity_comparison": True,
        "added_removed_changed_classification": True,
        "policy_address_comparison": True,
        "acceptance_transition": True,
        "failure_visibility": True,
        "strict_mapping_hydration": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "read_only": True,
        "timestamp_free": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "identity_metadata": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
        },
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_MAX_CHECKS",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_DIFF_VERSION",
    "MissionPlanReleaseCatalogGateCheckDiff",
    "MissionPlanReleaseCatalogGateDiff",
    "MissionPlanReleaseCatalogGateDiffStatus",
    "diff_mission_plan_release_catalog_gates",
    "mission_plan_release_catalog_gate_diff_capabilities",
    "mission_plan_release_catalog_gate_diff_csv",
    "mission_plan_release_catalog_gate_diff_export_payloads",
    "mission_plan_release_catalog_gate_diff_json",
    "mission_plan_release_catalog_gate_diff_markdown",
    "mission_plan_release_catalog_gate_diff_schema",
]

"""Contracts for comparing source-free packet review catalogs."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_VERSION = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_BOUNDARY = "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_PREFIX = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_CHANGE_PREFIX = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_PREFIX + "-change"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_CHECK_PREFIX = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_PREFIX + "-check"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_VERIFICATION_PREFIX = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_PREFIX + "-verification"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_QUERY_PREFIX = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_PREFIX + "-query"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES = 256
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHECKS = 16
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_LIMIT = 512


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind(StrEnum):
    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection(StrEnum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition(StrEnum):
    ADDED = "added"
    ACCEPTED_TO_BLOCKED = "accepted_to_blocked"
    BLOCKED_TO_ACCEPTED = "blocked_to_accepted"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane(StrEnum):
    INPUT = "input"
    CHANGES = "changes"
    ADDRESS = "address"
    PUBLIC = "public"


def _text(value: Any, field: str, maximum: int = 4096) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")


def _count(value: Any, field: str, maximum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds {maximum}")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange:
    """One packet identity classification and public field delta."""

    packet_id: str
    ordinal: int
    kind: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind
    direction: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection
    state_transition: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition
    previous_entry_address: str | None
    current_entry_address: str | None
    previous_packet_address: str | None
    current_packet_address: str | None
    previous_state: str | None
    current_state: str | None
    changed_fields: tuple[str, ...]
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "packet_id", 512)
        _count(self.ordinal, "ordinal", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES - 1)
        for field in ("previous_entry_address", "current_entry_address", "previous_packet_address", "current_packet_address", "previous_state", "current_state"):
            value = getattr(self, field)
            if value is not None:
                _text(value, field, 512)
        for field, enum_type in (("kind", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind), ("direction", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection), ("state_transition", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition)):
            if not isinstance(getattr(self, field), enum_type):
                raise ValidationError(f"packet catalog diff {field} is invalid")
        if not isinstance(self.changed_fields, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.changed_fields) or tuple(sorted(self.changed_fields)) != self.changed_fields or len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValidationError("packet catalog diff changed fields are invalid")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheck:
    """One independently replayable packet-catalog comparison check."""

    check_id: str
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.plane, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane):
            raise ValidationError("packet catalog diff check plane is invalid")
        if not isinstance(self.passed, bool):
            raise ValidationError("packet catalog diff check result is invalid")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff:
    """A deterministic comparison of two packet descriptor catalogs."""

    diff_id: str
    previous_catalog_address: str
    current_catalog_address: str
    previous_catalog_content_address: str
    current_catalog_content_address: str
    previous_catalog_state: str
    current_catalog_state: str
    changes: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange, ...]
    added_count: int
    changed_count: int
    removed_count: int
    unchanged_count: int
    direction: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection
    state_transition: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_id, "diff_id")
        for field in ("previous_catalog_address", "current_catalog_address", "previous_catalog_content_address", "current_catalog_content_address", "previous_catalog_state", "current_catalog_state", "content_address"):
            _text(getattr(self, field), field, 512)
        for field in ("added_count", "changed_count", "removed_count", "unchanged_count"):
            _count(getattr(self, field), field, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES)
        if len(self.changes) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES:
            raise ValidationError("packet catalog diff change limit exceeded")
        if tuple(item.ordinal for item in self.changes) != tuple(range(len(self.changes))) or len({item.packet_id for item in self.changes}) != len(self.changes):
            raise ValidationError("packet catalog diff changes are not ordered and unique")
        counts = {ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.ADDED: self.added_count, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.CHANGED: self.changed_count, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.REMOVED: self.removed_count, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.UNCHANGED: self.unchanged_count}
        for kind, count in counts.items():
            if sum(item.kind is kind for item in self.changes) != count:
                raise ValidationError(f"packet catalog diff {kind.value} count does not conserve")
        if not isinstance(self.direction, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection) or not isinstance(self.state_transition, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition):
            raise ValidationError("packet catalog diff aggregate state is invalid")
        if not isinstance(self.accepted, bool):
            raise ValidationError("packet catalog diff acceptance is invalid")

    def to_dict(self, *, include_changes: bool = True) -> dict[str, Any]:
        body = {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_BOUNDARY, "diff_id": self.diff_id, "previous_catalog_address": self.previous_catalog_address, "current_catalog_address": self.current_catalog_address, "previous_catalog_content_address": self.previous_catalog_content_address, "current_catalog_content_address": self.current_catalog_content_address, "previous_catalog_state": self.previous_catalog_state, "current_catalog_state": self.current_catalog_state, "change_count": len(self.changes), "added_count": self.added_count, "changed_count": self.changed_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "direction": self.direction, "state_transition": self.state_transition, "accepted": self.accepted, "content_address": self.content_address}
        if include_changes:
            body["changes"] = [item.to_dict() for item in self.changes]
        return body


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffVerification:
    """Bounded verification receipt for a packet-catalog comparison."""

    diff_id: str
    previous_catalog_address: str
    current_catalog_address: str
    change_count: int
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in ("diff_id", "previous_catalog_address", "current_catalog_address", "content_address"):
            _text(getattr(self, field), field, 512)
        _count(self.change_count, "change_count", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES)
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHECKS:
            raise ValidationError("packet catalog diff checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("packet catalog diff checks must be sorted and unique")
        if not isinstance(self.accepted, bool):
            raise ValidationError("packet catalog diff verification acceptance is invalid")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "previous_catalog_address": self.previous_catalog_address, "current_catalog_address": self.current_catalog_address, "change_count": self.change_count, "check_count": len(self.checks), "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "content_address": self.content_address}


def _address(value: Any, prefix: str) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=prefix)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_change(value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_CHANGE_PREFIX)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_check(value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheck) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_CHECK_PREFIX)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_verification(value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffVerification) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_VERIFICATION_PREFIX)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_PREFIX)


__all__ = [name for name in globals() if name.startswith("MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF") or name.startswith("ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff") or name.startswith("address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff")]

"""Typed contracts for source-free policy-set packet comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_VERSION = (
    "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-v1"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_BOUNDARY = (
    "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_CHANGES = 32
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_CHECKS = 12


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection(StrEnum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffStateTransition(StrEnum):
    ACCEPTED_TO_BLOCKED = "accepted_to_blocked"
    BLOCKED_TO_ACCEPTED = "blocked_to_accepted"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange:
    """One ordered field-level delta between two packets."""

    field_name: str
    previous: Any
    current: Any
    content_address: str

    def __post_init__(self) -> None:
        _text(self.field_name, "field_name", 256)
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body,
        prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-change",
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff:
    """A conserved, addressable comparison of two same-identity packets."""

    diff_id: str
    packet_id: str
    previous_packet_address: str
    current_packet_address: str
    previous_gate_address: str
    current_gate_address: str
    previous_audit_address: str
    current_audit_address: str
    previous_accepted: bool
    current_accepted: bool
    direction: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection
    state_transition: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffStateTransition
    changes: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "diff_id",
            "packet_id",
            "previous_packet_address",
            "current_packet_address",
            "previous_gate_address",
            "current_gate_address",
            "previous_audit_address",
            "current_audit_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if not isinstance(self.previous_accepted, bool) or not isinstance(
            self.current_accepted, bool
        ):
            raise ValidationError("packet diff acceptance values must be boolean")
        if not isinstance(
            self.direction, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection
        ):
            raise ValidationError("packet diff direction is invalid")
        if not isinstance(
            self.state_transition,
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffStateTransition,
        ):
            raise ValidationError("packet diff state transition is invalid")
        if (
            not isinstance(self.changes, tuple)
            or len(self.changes)
            > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_CHANGES
        ):
            raise ValidationError("packet diff changes are missing or excessive")
        fields = tuple(item.field_name for item in self.changes)
        if fields != tuple(sorted(fields)) or len(fields) != len(set(fields)):
            raise ValidationError("packet diff changes must be sorted and unique")

    @property
    def changed_count(self) -> int:
        return len(self.changes)

    @property
    def unchanged(self) -> bool:
        return not self.changes

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_VERSION,
            "boundary": (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_BOUNDARY
            ),
            "diff_id": self.diff_id,
            "packet_id": self.packet_id,
            "previous_packet_address": self.previous_packet_address,
            "current_packet_address": self.current_packet_address,
            "previous_gate_address": self.previous_gate_address,
            "current_gate_address": self.current_gate_address,
            "previous_audit_address": self.previous_audit_address,
            "current_audit_address": self.current_audit_address,
            "previous_accepted": self.previous_accepted,
            "current_accepted": self.current_accepted,
            "direction": self.direction,
            "state_transition": self.state_transition,
            "changed_count": self.changed_count,
            "changes": [item.to_dict() for item in self.changes],
            "content_address": self.content_address,
        }


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body,
        prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff",
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck:
    """One independently recomputable packet-diff invariant."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("packet diff check result must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_check(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body,
        prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-check",
    )


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification:
    """Verification receipt for a packet comparison."""

    diff_address: str
    previous_packet_address: str
    current_packet_address: str
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "diff_address",
            "previous_packet_address",
            "current_packet_address",
            "content_address",
        ):
            _text(getattr(self, field), field, 512)
        if (
            not isinstance(self.checks, tuple)
            or not self.checks
            or len(self.checks)
            > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_CHECKS
        ):
            raise ValidationError("packet diff verification checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("packet diff verification checks must be sorted and unique")
        if not isinstance(self.accepted, bool) or self.accepted != all(
            item.passed for item in self.checks
        ):
            raise ValidationError("packet diff verification acceptance does not conserve checks")

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_verification(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification,
) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(
        body,
        prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-verification",
    )


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_CHANGES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_CHECKS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_VERSION",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffStateTransition",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_check",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_verification",
]

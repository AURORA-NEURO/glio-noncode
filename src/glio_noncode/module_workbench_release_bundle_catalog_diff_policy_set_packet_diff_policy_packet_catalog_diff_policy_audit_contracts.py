"""Contracts for independently auditing packet catalog diff policy gates."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_VERSION = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-audit-v1"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_BOUNDARY = "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit"
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_MAX_CHECKS = 16
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_PREFIX = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-audit"


def _text(value: Any, field: str, maximum: int = 4096) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAuditCheck:
    """One independently recomputable catalog-diff gate invariant."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("catalog-diff policy audit check passed must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address", 512)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAudit:
    """Independent audit over one packet catalog diff policy gate."""

    policy_gate_address: str
    diff_address: str
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAuditCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_gate_address, "policy_gate_address", 512)
        _text(self.diff_address, "diff_address", 512)
        if not self.checks or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_MAX_CHECKS:
            raise ValidationError("catalog-diff policy audit checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("catalog-diff policy audit checks must be sorted and unique")
        if not isinstance(self.accepted, bool) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("catalog-diff policy audit acceptance does not conserve checks")
        _text(self.content_address, "content_address", 512)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_BOUNDARY, "policy_gate_address": self.policy_gate_address, "diff_address": self.diff_address, "check_count": len(self.checks), "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _address(value: Any, prefix: str) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=prefix)


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_check(value: Any) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_PREFIX + "-check")


def address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(value: Any) -> str:
    return _address(value, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT_PREFIX)


__all__ = [name for name in globals() if name.startswith("MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_AUDIT") or name.startswith("ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAudit") or name.startswith("address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit")]

"""Typed policy and gate contracts for release-bundle catalog diffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_VERSION = (
    "module-workbench-release-bundle-catalog-diff-policy-v1"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_BOUNDARY = (
    "public_aggregate_module_workbench_release_bundle_catalog_diff_policy"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_CHECKS = 16


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


def _count(value: Any, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")


def _choices(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not value:
        raise ValidationError(f"{field} must contain at least one choice")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValidationError(f"{field} contains an invalid choice")
    if result != tuple(sorted(result)) or len(result) != len(set(result)):
        raise ValidationError(f"{field} must be sorted and unique")
    return result


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicy:
    """Immutable admission thresholds for a catalog comparison."""

    policy_id: str
    maximum_added_count: int
    maximum_changed_count: int
    maximum_removed_count: int
    allowed_directions: tuple[str, ...]
    allowed_state_transitions: tuple[str, ...]
    require_accepted_catalogs: bool
    allow_unchanged: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_id, "policy_id")
        for field in ("maximum_added_count", "maximum_changed_count", "maximum_removed_count"):
            _count(getattr(self, field), field)
        _choices(self.allowed_directions, "allowed_directions")
        _choices(self.allowed_state_transitions, "allowed_state_transitions")
        if not isinstance(self.require_accepted_catalogs, bool):
            raise ValidationError("require_accepted_catalogs must be boolean")
        if not isinstance(self.allow_unchanged, bool):
            raise ValidationError("allow_unchanged must be boolean")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck:
    """One independently inspectable catalog-diff policy result."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id", 256)
        if not isinstance(self.passed, bool):
            raise ValidationError("policy check result must be boolean")
        _text(self.detail, "detail")
        _text(self.content_address, "content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate:
    """A conserved readiness decision over one catalog comparison."""

    diff_address: str
    policy: ModuleWorkbenchReleaseBundleCatalogDiffPolicy
    checks: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_address, "diff_address")
        if not isinstance(self.policy, ModuleWorkbenchReleaseBundleCatalogDiffPolicy):
            raise ValidationError("catalog-diff gate policy must be typed")
        _text(self.content_address, "content_address")
        if (
            not self.checks
            or len(self.checks) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_CHECKS
        ):
            raise ValidationError("catalog-diff gate checks are missing or excessive")
        ids = tuple(item.check_id for item in self.checks)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("catalog-diff gate checks must be sorted and unique")
        if self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("catalog-diff gate acceptance does not conserve checks")

    @property
    def policy_address(self) -> str:
        return self.policy.content_address

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(not item.passed for item in self.checks)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_VERSION,
            "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_BOUNDARY,
            "diff_address": self.diff_address,
            "policy": self.policy.to_dict(),
            "policy_address": self.policy_address,
            "check_count": len(self.checks),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _address(value: Any, prefix: str) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=prefix)


def address_module_workbench_release_bundle_catalog_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicy,
) -> str:
    return _address(value, "module-workbench-release-bundle-catalog-diff-policy")


def address_module_workbench_release_bundle_catalog_diff_policy_check(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck,
) -> str:
    return _address(value, "module-workbench-release-bundle-catalog-diff-policy-check")


def address_module_workbench_release_bundle_catalog_diff_policy_gate(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
) -> str:
    return _address(value, "module-workbench-release-bundle-catalog-diff-policy-gate")


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_CHECKS",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_VERSION",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicy",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate",
    "address_module_workbench_release_bundle_catalog_diff_policy",
    "address_module_workbench_release_bundle_catalog_diff_policy_check",
    "address_module_workbench_release_bundle_catalog_diff_policy_gate",
]

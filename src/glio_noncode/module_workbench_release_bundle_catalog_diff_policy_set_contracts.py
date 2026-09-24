"""Typed policy-set contracts for release-bundle catalog diffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicy,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
)
from .serialization import content_hash, jsonable

MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_VERSION = (
    "module-workbench-release-bundle-catalog-diff-policy-set-v1"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_BOUNDARY = (
    "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set"
)
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_LIMIT = 512
MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_POLICIES = 8


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds {maximum} characters")
    return value


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySet:
    """An ordered, immutable collection of alternative or conjunctive policies."""

    policy_set_id: str
    selection_mode: str
    policies: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicy, ...]
    content_address: str

    def __post_init__(self) -> None:
        _text(self.policy_set_id, "policy_set_id")
        if self.selection_mode not in {"all", "any"}:
            raise ValidationError("selection_mode must be 'all' or 'any'")
        if (
            not isinstance(self.policies, tuple)
            or not self.policies
            or len(self.policies)
            > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_POLICIES
        ):
            raise ValidationError("policy set must contain between one and eight policies")
        if any(
            not isinstance(item, ModuleWorkbenchReleaseBundleCatalogDiffPolicy)
            for item in self.policies
        ):
            raise ValidationError("policy set entries must be typed policies")
        ordered = tuple(sorted(self.policies, key=lambda item: item.policy_id))
        if ordered != self.policies:
            raise ValidationError("policy set policies must be sorted by policy_id")
        ids = tuple(item.policy_id for item in self.policies)
        addresses = tuple(item.content_address for item in self.policies)
        if len(ids) != len(set(ids)) or len(addresses) != len(set(addresses)):
            raise ValidationError("policy set policies must have unique identities")
        _text(self.content_address, "content_address")

    @property
    def policy_ids(self) -> tuple[str, ...]:
        return tuple(item.policy_id for item in self.policies)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate:
    """A source-free aggregate decision over every policy in a policy set."""

    diff_address: str
    policy_set: ModuleWorkbenchReleaseBundleCatalogDiffPolicySet
    gates: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.diff_address, "diff_address")
        if not isinstance(self.policy_set, ModuleWorkbenchReleaseBundleCatalogDiffPolicySet):
            raise ValidationError("policy-set gate policy_set must be typed")
        if (
            not isinstance(self.gates, tuple)
            or not self.gates
            or len(self.gates) != len(self.policy_set.policies)
        ):
            raise ValidationError("policy-set gate must contain one gate per policy")
        if any(
            not isinstance(item, ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate)
            for item in self.gates
        ):
            raise ValidationError("policy-set gate entries must be typed gates")
        ids = tuple(item.policy.policy_id for item in self.gates)
        if ids != self.policy_set.policy_ids:
            raise ValidationError("policy-set gates must follow the policy-set order")
        if any(item.diff_address != self.diff_address for item in self.gates):
            raise ValidationError("policy-set gates must compare the same diff")
        if not isinstance(self.accepted, bool):
            raise ValidationError("policy-set gate acceptance must be boolean")
        expected = all(item.accepted for item in self.gates)
        if self.policy_set.selection_mode == "any":
            expected = any(item.accepted for item in self.gates)
        if self.accepted != expected:
            raise ValidationError("policy-set gate acceptance does not conserve selection mode")
        _text(self.content_address, "content_address")

    @property
    def policy_set_address(self) -> str:
        return self.policy_set.content_address

    @property
    def passed_policy_count(self) -> int:
        return sum(item.accepted for item in self.gates)

    @property
    def failed_policy_count(self) -> int:
        return sum(not item.accepted for item in self.gates)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_VERSION,
            "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_BOUNDARY,
            "diff_address": self.diff_address,
            "policy_set": self.policy_set.to_dict(),
            "policy_set_address": self.policy_set_address,
            "policy_count": len(self.gates),
            "passed_policy_count": self.passed_policy_count,
            "failed_policy_count": self.failed_policy_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }
        body["gates"] = [item.to_dict(include_checks=include_checks) for item in self.gates]
        return body


def _address(value: Any, prefix: str) -> str:
    body = value.to_dict()
    body.pop("content_address", None)
    return content_hash(body, prefix=prefix)


def address_module_workbench_release_bundle_catalog_diff_policy_set(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySet,
) -> str:
    return _address(value, "module-workbench-release-bundle-catalog-diff-policy-set")


def address_module_workbench_release_bundle_catalog_diff_policy_set_gate(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
) -> str:
    return _address(value, "module-workbench-release-bundle-catalog-diff-policy-set-gate")


__all__ = [
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_BOUNDARY",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_DEFAULT_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_LIMIT",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_MAX_POLICIES",
    "MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_VERSION",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySet",
    "ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate",
    "address_module_workbench_release_bundle_catalog_diff_policy_set",
    "address_module_workbench_release_bundle_catalog_diff_policy_set_gate",
]

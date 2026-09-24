"""Typed contracts for source-free release-bundle diff policy gates."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff as diff_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy"
POLICY_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy"
CHECK_PREFIX = POLICY_PREFIX + "-check"
DEFAULT_POLICY_ID = POLICY_PREFIX
STATES = ("ready", "blocked")
POLICY_CHECK_IDS = (
    "policy-diff-address",
    "policy-diff-replay",
    "policy-added-budget",
    "policy-removed-budget",
    "policy-changed-budget",
    "policy-member-budget",
    "policy-resource-allowlist",
    "policy-change-allowlist",
    "policy-direction-allowlist",
    "policy-transition-allowlist",
    "policy-ready-requirement",
    "policy-change-requirement",
    "policy-unchanged-control",
)
POLICY_FIELDS = (
    "policy_id", "version", "boundary", "diff_address", "maximum_added", "maximum_removed", "maximum_changed",
    "maximum_member_changed", "allowed_resources", "allowed_changes", "allowed_directions", "allowed_transitions",
    "require_ready", "require_change", "allow_unchanged", "check_count", "passed_count", "failed_count", "accepted", "state", "checks", "content_address",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    result = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not result or len(set(result)) != len(result) or any(item not in allowed for item in result) or result != tuple(sorted(result, key=allowed.index)):
        raise ValidationError(f"{field} contains unsupported, duplicate, or unordered values")
    return result


def _public(value: Any) -> bool:
    return not _has_forbidden_key(value)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck:
    """One deterministic bundle-diff policy condition and retained evidence."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        check_id = _label(self.check_id, "release bundle diff policy check ID")
        if check_id not in POLICY_CHECK_IDS:
            raise ValidationError("release bundle diff policy check ID is unsupported")
        _bool(self.passed, "release bundle diff policy check result")
        _text(self.detail, "release bundle diff policy check detail", 2048)
        if not self.content_address.endswith(":pending"):
            _address(self.content_address, "release bundle diff policy check address", CHECK_PREFIX)
            if address_check(self) != self.content_address:
                raise ValidationError("release bundle diff policy check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck":
        if not isinstance(value, Mapping):
            raise ValidationError("release bundle diff policy check must be an object")
        _strict(value, set(CHECK_FIELDS), "release bundle diff policy check")
        return cls(*(value[field] for field in CHECK_FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy:
    """A source-free ready or blocked gate over one bundle diff."""

    policy_id: str
    version: str
    boundary: str
    diff_address: str
    maximum_added: int
    maximum_removed: int
    maximum_changed: int
    maximum_member_changed: int
    allowed_resources: tuple[str, ...]
    allowed_changes: tuple[str, ...]
    allowed_directions: tuple[str, ...]
    allowed_transitions: tuple[str, ...]
    require_ready: bool
    require_change: bool
    allow_unchanged: bool
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    state: str
    checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.policy_id, "release bundle diff policy ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release bundle diff policy version or boundary is not current")
        _address(self.diff_address, "release bundle diff policy diff address", diff_model.DIFF_PREFIX)
        for field in ("maximum_added", "maximum_removed", "maximum_changed", "maximum_member_changed"):
            _count(getattr(self, field), f"release bundle diff policy {field}", diff_model.MAX_ITEMS)
        _ordered_labels(self.allowed_resources, "release bundle diff policy resources", diff_model.RESOURCES)
        _ordered_labels(self.allowed_changes, "release bundle diff policy changes", diff_model.CHANGES)
        _ordered_labels(self.allowed_directions, "release bundle diff policy directions", diff_model.DIRECTIONS)
        _ordered_labels(self.allowed_transitions, "release bundle diff policy transitions", diff_model.STATE_TRANSITIONS)
        for field in ("require_ready", "require_change", "allow_unchanged", "accepted"):
            _bool(getattr(self, field), f"release bundle diff policy {field}")
        _label(self.state, "release bundle diff policy state")
        if self.state not in STATES:
            raise ValidationError("release bundle diff policy state is unsupported")
        if not isinstance(self.checks, tuple) or not self.checks or len(self.checks) > len(POLICY_CHECK_IDS) or any(not isinstance(item, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck) for item in self.checks):
            raise ValidationError("release bundle diff policy checks are invalid")
        _count(self.check_count, "release bundle diff policy check count", len(POLICY_CHECK_IDS))
        _count(self.passed_count, "release bundle diff policy passed count", len(POLICY_CHECK_IDS))
        _count(self.failed_count, "release bundle diff policy failed count", len(POLICY_CHECK_IDS))
        if self.check_count != len(self.checks) or self.check_count != len(POLICY_CHECK_IDS) or tuple(item.check_id for item in self.checks) != POLICY_CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("release bundle diff policy decision aggregates do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release bundle diff policy crosses the public boundary")
        if not self.content_address.endswith(":pending"):
            _address(self.content_address, "release bundle diff policy address", POLICY_PREFIX)
            if address_policy(self) != self.content_address:
                raise ValidationError("release bundle diff policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: tuple(item.to_dict() for item in self.checks) if field == "checks" else getattr(self, field) for field in POLICY_FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in POLICY_FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy":
        if not isinstance(value, Mapping):
            raise ValidationError("release bundle diff policy must be an object")
        _strict(value, set(POLICY_FIELDS), "release bundle diff policy")
        checks = tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck.from_mapping(item) for item in value["checks"])
        return cls(value["policy_id"], value["version"], value["boundary"], value["diff_address"], value["maximum_added"], value["maximum_removed"], value["maximum_changed"], value["maximum_member_changed"], tuple(value["allowed_resources"]), tuple(value["allowed_changes"]), tuple(value["allowed_directions"]), tuple(value["allowed_transitions"]), value["require_ready"], value["require_change"], value["allow_unchanged"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["state"], checks, value["content_address"])


def address_policy(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release bundle diff policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field in {"allowed_resources", "allowed_changes", "allowed_directions", "allowed_transitions", "checks"} else "boolean" if field in {"require_ready", "require_change", "allow_unchanged", "accepted"} else "integer" if field in {"maximum_added", "maximum_removed", "maximum_changed", "maximum_member_changed", "check_count", "passed_count", "failed_count"} else "string"} for field in POLICY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release bundle diff policy check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(POLICY_CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    operations = ("build_policy", "strict_policy", "release_policy", "verify_policy", "load_source_free", "query_checks", "export_json", "export_csv", "render_markdown", "write_atomic")
    return {"public": True, "independent": True, "source_free": True, "version": VERSION, "boundary": BOUNDARY, "states": list(STATES), "check_count": len(POLICY_CHECK_IDS), "operation_count": len(operations), "operations": list(operations), "profiles": ["strict", "release"], "resources": list(diff_model.RESOURCES), "directions": list(diff_model.DIRECTIONS), "transitions": list(diff_model.STATE_TRANSITIONS)}


__all__ = [
    "BOUNDARY", "CHECK_FIELDS", "CHECK_PREFIX", "DEFAULT_POLICY_ID", "POLICY_CHECK_IDS", "POLICY_FIELDS", "POLICY_PREFIX", "STATES", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicy", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyCheck", "address_check", "address_policy", "capabilities", "check_schema", "policy_schema",
]

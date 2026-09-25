"""Typed contracts for strict and release gates over module641 catalog diffs."""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .downloaded_data_review_packet_fixed_transport_catalog_diff_policy_641_ct import CHANGES, DIFF_PREFIX, DIRECTIONS, POSTURES, STATE_TRANSITIONS, VERSION as DIFF_VERSION
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

VERSION = DIFF_PREFIX + "-policy-v1"
BOUNDARY = "public_" + VERSION.replace("-", "_")
POLICY_PREFIX = DIFF_PREFIX + "-policy"
CHECK_PREFIX = POLICY_PREFIX + "-check"
DEFAULT_POLICY_ID = "module642-transport-catalog-diff-policy"
STATES = ("ready", "blocked")
POLICY_CHECK_IDS = ("policy-diff-address", "policy-diff-replay", "policy-added-budget", "policy-removed-budget", "policy-changed-budget", "policy-total-change-budget", "policy-change-allowlist", "policy-direction-allowlist", "policy-transition-allowlist", "policy-left-posture-allowlist", "policy-right-posture-allowlist", "policy-ready-requirement", "policy-change-requirement", "policy-required-changes", "policy-unchanged-control", "policy-public-boundary")
POLICY_FIELDS = ("policy_id", "version", "boundary", "diff_address", "maximum_added", "maximum_removed", "maximum_changed", "maximum_total_changes", "allowed_changes", "allowed_directions", "allowed_transitions", "allowed_left_postures", "allowed_right_postures", "required_changes", "require_ready", "require_change", "allow_unchanged", "check_count", "passed_count", "failed_count", "accepted", "state", "checks", "content_address")
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
MAX_LIMIT = 256
MAX_BUDGET = 512


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.endswith(":pending"):
        return value
    digest = value.rsplit(":", 1)[-1]
    if ":" not in value or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a canonical content address")
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
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _ordered_labels(value: Any, field: str, allowed: Sequence[str], *, allow_empty: bool = False) -> tuple[str, ...]:
    result = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if (not result and not allow_empty) or len(set(result)) != len(result) or any(item not in allowed for item in result) or result != tuple(sorted(result, key=allowed.index)):
        raise ValidationError(f"{field} contains unsupported, duplicate, or unordered values")
    return result


@dataclass(frozen=True)
class PolicyCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.check_id, "module642 check ID")
        if self.check_id not in POLICY_CHECK_IDS:
            raise ValidationError("module642 check ID is unsupported")
        _bool(self.passed, "module642 check result")
        _text(self.detail, "module642 check detail", 2048)
        _address(self.content_address, "module642 check address", CHECK_PREFIX)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("module642 check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PolicyCheck":
        if not isinstance(value, Mapping):
            raise ValidationError("module642 check must be an object")
        _strict(value, set(CHECK_FIELDS), "module642 check")
        return cls(*(value[field] for field in CHECK_FIELDS))


def address_check(value: PolicyCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class Policy:
    policy_id: str
    version: str
    boundary: str
    diff_address: str
    maximum_added: int
    maximum_removed: int
    maximum_changed: int
    maximum_total_changes: int
    allowed_changes: tuple[str, ...]
    allowed_directions: tuple[str, ...]
    allowed_transitions: tuple[str, ...]
    allowed_left_postures: tuple[str, ...]
    allowed_right_postures: tuple[str, ...]
    required_changes: tuple[str, ...]
    require_ready: bool
    require_change: bool
    allow_unchanged: bool
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    state: str
    checks: tuple[PolicyCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.policy_id, "module642 policy ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("module642 policy identity is not current")
        _address(self.diff_address, "module642 diff address", DIFF_PREFIX)
        for field in ("maximum_added", "maximum_removed", "maximum_changed", "maximum_total_changes"):
            _count(getattr(self, field), f"module642 {field}", MAX_BUDGET)
        _ordered_labels(self.allowed_changes, "module642 allowed changes", CHANGES)
        _ordered_labels(self.allowed_directions, "module642 allowed directions", DIRECTIONS)
        _ordered_labels(self.allowed_transitions, "module642 allowed transitions", STATE_TRANSITIONS)
        _ordered_labels(self.allowed_left_postures, "module642 allowed left postures", POSTURES)
        _ordered_labels(self.allowed_right_postures, "module642 allowed right postures", POSTURES)
        _ordered_labels(self.required_changes, "module642 required changes", CHANGES, allow_empty=True)
        for field in ("require_ready", "require_change", "allow_unchanged", "accepted"):
            _bool(getattr(self, field), f"module642 {field}")
        if self.state not in STATES or not isinstance(self.checks, tuple) or tuple(item.check_id for item in self.checks) != POLICY_CHECK_IDS:
            raise ValidationError("module642 policy state or checks are invalid")
        _count(self.check_count, "module642 check count", len(POLICY_CHECK_IDS))
        _count(self.passed_count, "module642 passed count", len(POLICY_CHECK_IDS))
        _count(self.failed_count, "module642 failed count", len(POLICY_CHECK_IDS))
        if self.check_count != len(self.checks) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("module642 policy aggregates do not replay")
        if _has_forbidden_key(self.to_dict()):
            raise ValidationError("module642 policy crosses the public boundary")
        _address(self.content_address, "module642 policy address", POLICY_PREFIX)
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("module642 policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: tuple(item.to_dict() for item in self.checks) if field == "checks" else getattr(self, field) for field in POLICY_FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in POLICY_FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Policy":
        if not isinstance(value, Mapping):
            raise ValidationError("module642 policy must be an object")
        _strict(value, set(POLICY_FIELDS), "module642 policy")
        return cls(value["policy_id"], value["version"], value["boundary"], value["diff_address"], value["maximum_added"], value["maximum_removed"], value["maximum_changed"], value["maximum_total_changes"], tuple(value["allowed_changes"]), tuple(value["allowed_directions"]), tuple(value["allowed_transitions"]), tuple(value["allowed_left_postures"]), tuple(value["allowed_right_postures"]), tuple(value["required_changes"]), value["require_ready"], value["require_change"], value["allow_unchanged"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["state"], tuple(PolicyCheck.from_mapping(item) for item in value["checks"]), value["content_address"])


def address_policy(value: Policy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module642 policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {field: {"type": "array" if field in {"allowed_changes", "allowed_directions", "allowed_transitions", "allowed_left_postures", "allowed_right_postures", "required_changes", "checks"} else "boolean" if field in {"require_ready", "require_change", "allow_unchanged", "accepted"} else "integer" if field in {"maximum_added", "maximum_removed", "maximum_changed", "maximum_total_changes", "check_count", "passed_count", "failed_count"} else "string"} for field in POLICY_FIELDS}}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module642 policy check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(POLICY_CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "source_free": True, "content_addressed": True, "states": STATES, "check_ids": POLICY_CHECK_IDS, "diff_version": DIFF_VERSION, "controls": ("budgets", "allowlists", "postures", "required_changes", "readiness", "unchanged"), "operations": ("build_policy", "strict_policy", "release_policy", "policy_json", "policy_csv", "render_policy_markdown", "query_policy", "verify_policy")}


__all__ = ["BOUNDARY", "CHECK_FIELDS", "CHECK_PREFIX", "DEFAULT_POLICY_ID", "POLICY_CHECK_IDS", "POLICY_FIELDS", "POLICY_PREFIX", "STATES", "VERSION", "Policy", "PolicyCheck", "address_check", "address_policy", "capabilities", "check_schema", "policy_schema"]

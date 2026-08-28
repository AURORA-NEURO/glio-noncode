"""Federate independently verified decision-assurance release registries.

This boundary is deliberately higher than a single release registry.  It
keeps each registry as an addressed member, prefixes every package projection
with its source registry identity, and computes aggregate readiness without
combining the underlying scientific records.  The federation is suitable for
reviewing several downloaded release windows, institutional workspaces, or
reproducible reruns as one transportable handoff.

The module includes:

* typed member and package rollups with cross-registry provenance;
* independent structural verification and policy evaluation;
* a five-stage fail-closed runtime closure;
* exact-byte eight-document persistence with regular-file and manifest checks;
* bounded JSON, CSV, Markdown, CLI/API-facing queries; and
* addressed federation-to-federation diffs with readiness directions.

Only public, path-free projections are persisted.  A source directory is an
input to admission and is never retained in a public object.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = registry_model.VERSION + "-federation-v1"
BOUNDARY = registry_model.BOUNDARY + "_federation"
PREFIX = registry_model.REGISTRY_PREFIX + "-federation"
MEMBER_PREFIX = PREFIX + "-member"
PACKAGE_PREFIX = PREFIX + "-package"
POLICY_PREFIX = PREFIX + "-policy"
CHECK_PREFIX = PREFIX + "-check"
VERIFICATION_PREFIX = PREFIX + "-verification"
POLICY_EVALUATION_PREFIX = PREFIX + "-policy-evaluation"
STAGE_PREFIX = PREFIX + "-stage"
RUNTIME_PREFIX = PREFIX + "-runtime"
QUERY_PREFIX = PREFIX + "-query"
DIFF_PREFIX = PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
DIFF_QUERY_PREFIX = DIFF_PREFIX + "-query"
MANIFEST_PREFIX = PREFIX + "-manifest"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"

MANIFEST_NAME = "manifest.json"
FEDERATION_NAME = "federation.json"
MEMBERS_NAME = "members.json"
PACKAGES_NAME = "packages.json"
POLICY_NAME = "policy.json"
VERIFICATION_NAME = "verification.json"
POLICY_EVALUATION_NAME = "policy-evaluation.json"
RUNTIME_NAME = "runtime.json"
FILES = (
    MANIFEST_NAME,
    FEDERATION_NAME,
    MEMBERS_NAME,
    PACKAGES_NAME,
    POLICY_NAME,
    VERIFICATION_NAME,
    POLICY_EVALUATION_NAME,
    RUNTIME_NAME,
)
DIFF_NAME = "diff.json"
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)

DEFAULT_FEDERATION_ID = "glio-noncode-decision-assurance-history-series-release-registry-federation"
DEFAULT_POLICY_ID = DEFAULT_FEDERATION_ID + "-policy"
DEFAULT_DIFF_ID = DEFAULT_FEDERATION_ID + "-diff"
MAX_REGISTRIES = 64
MAX_PACKAGES = 4096
MAX_CHECKS = 64
MAX_STAGES = 5
MAX_QUERY_ITEMS = 4096

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
)


class FederationState(StrEnum):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    EMPTY = "empty"


class FederationStageState(StrEnum):
    PASSED = "passed"
    HELD = "held"
    BLOCKED = "blocked"


class CheckSeverity(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _positive_count(value: Any, field: str, maximum: int) -> int:
    value = _count(value, field, maximum)
    if value < 1:
        raise ValidationError(f"{field} must be positive")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _mapping_sequence(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return tuple(_mapping(item, field) for item in value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields: {sorted(unknown)}")


def _required(value: Mapping[str, Any], required: set[str], field: str) -> None:
    missing = required - set(value)
    if missing:
        raise ValidationError(f"{field} is missing required fields: {sorted(missing)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _state(value: Any, field: str = "federation state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in FederationState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _diff_state(value: Any, field: str = "federation diff state") -> str:
    value = _text(value, field, 32)
    if value not in {"unchanged", "improved", "regressed", "changed"}:
        raise ValidationError(f"{field} is invalid")
    return value


def _stage_state(value: Any, field: str = "federation stage state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in FederationStageState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _severity(value: Any, field: str = "check severity") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in CheckSeverity}:
        raise ValidationError(f"{field} is invalid")
    return value


def _file_address(name: str, raw: bytes, *, prefix: str = PREFIX + "-file") -> str:
    return hash_bytes(raw, prefix=f"{prefix}-{name.removesuffix('.json')}")


def _require_regular_file(path: Path, field: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValidationError(f"{field} must be a regular file")


def _require_directory(path: Path, field: str) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ValidationError(f"{field} must be a regular directory")


def _read_json(path: Path, field: str) -> dict[str, Any]:
    _require_regular_file(path, field)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not valid UTF-8 JSON") from exc
    return dict(_mapping(value, field))


def _canonical_document(value: Mapping[str, Any]) -> bytes:
    return canonical_bytes(value)


def _derive_registry_state(value: registry_model.DecisionAssuranceHistorySeriesReleaseRegistry) -> str:
    registry_model.verify_decision_assurance_history_series_release_registry(value)
    if value.entry_count == 0:
        return FederationState.EMPTY.value
    if value.blocked_count:
        return FederationState.BLOCKED.value
    if value.hold_count:
        return FederationState.HELD.value
    return FederationState.READY.value


def _state_score(state: str, accepted: bool, release_ready: bool) -> tuple[int, int, int]:
    rank = {FederationState.EMPTY.value: 0, FederationState.BLOCKED.value: 0, FederationState.HELD.value: 1, FederationState.READY.value: 2}
    return rank[state], int(accepted), int(release_ready)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationMember:
    """A verified release registry admitted as one federation member."""

    def __init__(
        self,
        ordinal: int,
        registry_id: str,
        registry_address: str,
        entry_count: int,
        ready_count: int,
        hold_count: int,
        blocked_count: int,
        accepted_count: int,
        release_ready_count: int,
        state: str,
        content_address: str,
    ) -> None:
        self.ordinal, self.registry_id, self.registry_address = ordinal, registry_id, registry_address
        self.entry_count, self.ready_count, self.hold_count = entry_count, ready_count, hold_count
        self.blocked_count, self.accepted_count, self.release_ready_count = blocked_count, accepted_count, release_ready_count
        self.state, self.content_address = state, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "federation member ordinal", MAX_REGISTRIES - 1)
        _text(self.registry_id, "federation member registry ID", 256)
        _address(self.registry_address, "federation member registry address")
        for name, value in (
            ("entry", self.entry_count),
            ("ready", self.ready_count),
            ("hold", self.hold_count),
            ("blocked", self.blocked_count),
            ("accepted", self.accepted_count),
            ("release-ready", self.release_ready_count),
        ):
            _count(value, f"federation member {name} count", registry_model.MAX_ENTRIES)
        if self.ready_count + self.hold_count + self.blocked_count != self.entry_count:
            raise ValidationError("federation member state counts are not conserved")
        if self.accepted_count > self.entry_count or self.release_ready_count > self.accepted_count:
            raise ValidationError("federation member readiness counts are not conserved")
        _state(self.state)
        expected = FederationState.EMPTY.value if not self.entry_count else FederationState.BLOCKED.value if self.blocked_count else FederationState.HELD.value if self.hold_count else FederationState.READY.value
        if self.state != expected:
            raise ValidationError("federation member state does not match counts")
        _address(self.content_address, "federation member address")
        if not self.content_address.startswith("pending:") and address_federation_member(self) != self.content_address:
            raise ValidationError("federation member address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation member crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "registry_id": self.registry_id,
            "registry_address": self.registry_address,
            "entry_count": self.entry_count,
            "ready_count": self.ready_count,
            "hold_count": self.hold_count,
            "blocked_count": self.blocked_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "state": self.state,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary()


def address_federation_member(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationMember) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=MEMBER_PREFIX)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage:
    """A path-free package projection scoped by its source registry."""

    def __init__(
        self,
        ordinal: int,
        registry_id: str,
        package_id: str,
        release_id: str,
        registry_address: str,
        registry_entry_address: str,
        package_address: str,
        release_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        content_address: str,
    ) -> None:
        self.ordinal, self.registry_id = ordinal, registry_id
        self.package_id, self.release_id = package_id, release_id
        self.registry_address, self.registry_entry_address = registry_address, registry_entry_address
        self.package_address, self.release_address = package_address, release_address
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "federation package ordinal", MAX_PACKAGES - 1)
        _text(self.registry_id, "federation package registry ID", 256)
        _text(self.package_id, "federation package ID", 256)
        _text(self.release_id, "federation package release ID", 256)
        for field, value in (
            ("registry address", self.registry_address),
            ("registry entry address", self.registry_entry_address),
            ("package address", self.package_address),
            ("release address", self.release_address),
            ("package address", self.content_address),
        ):
            _address(value, f"federation {field}")
        _state(self.state)
        _bool(self.accepted, "federation package accepted")
        _bool(self.release_ready, "federation package release-ready")
        if self.state == FederationState.READY.value and (not self.accepted or not self.release_ready):
            raise ValidationError("ready federation package must be accepted and release-ready")
        if self.state == FederationState.BLOCKED.value and self.accepted:
            raise ValidationError("blocked federation package cannot be accepted")
        if self.release_ready and (not self.accepted or self.state != FederationState.READY.value):
            raise ValidationError("federation package readiness is inconsistent")
        if not self.content_address.startswith("pending:") and address_federation_package(self) != self.content_address:
            raise ValidationError("federation package address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation package crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "registry_id": self.registry_id,
            "package_id": self.package_id,
            "release_id": self.release_id,
            "registry_address": self.registry_address,
            "registry_entry_address": self.registry_entry_address,
            "package_address": self.package_address,
            "release_address": self.release_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }


def address_federation_package(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage) -> str:
    return content_hash(value.to_dict() | {"ordinal": None, "content_address": None}, prefix=PACKAGE_PREFIX)


class DecisionAssuranceHistorySeriesReleaseRegistryFederation:
    """The addressed aggregate of independently verified registries."""

    def __init__(
        self,
        federation_id: str,
        version: str,
        boundary: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        member_count: int,
        package_count: int,
        ready_count: int,
        hold_count: int,
        blocked_count: int,
        accepted_count: int,
        release_ready_count: int,
        members: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryFederationMember],
        packages: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage],
        content_address: str,
    ) -> None:
        self.federation_id, self.version, self.boundary = federation_id, version, boundary
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.member_count, self.package_count = member_count, package_count
        self.ready_count, self.hold_count, self.blocked_count = ready_count, hold_count, blocked_count
        self.accepted_count, self.release_ready_count = accepted_count, release_ready_count
        self.members, self.packages = tuple(members), tuple(packages)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.federation_id, "federation ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("federation contract is invalid")
        _state(self.state)
        _bool(self.accepted, "federation accepted")
        _bool(self.release_ready, "federation release-ready")
        _count(self.member_count, "federation member count", MAX_REGISTRIES)
        _count(self.package_count, "federation package count", MAX_PACKAGES)
        for name, value in (
            ("ready", self.ready_count),
            ("hold", self.hold_count),
            ("blocked", self.blocked_count),
            ("accepted", self.accepted_count),
            ("release-ready", self.release_ready_count),
        ):
            _count(value, f"federation {name} count", MAX_PACKAGES)
        if self.member_count != len(self.members) or self.package_count != len(self.packages):
            raise ValidationError("federation counts do not match projections")
        if self.ready_count + self.hold_count + self.blocked_count != self.package_count:
            raise ValidationError("federation package state counts are not conserved")
        if self.accepted_count > self.package_count or self.release_ready_count > self.accepted_count:
            raise ValidationError("federation readiness counts are not conserved")
        registry_ids, registry_addresses, member_addresses = set(), set(), set()
        for ordinal, member in enumerate(self.members):
            if not isinstance(member, DecisionAssuranceHistorySeriesReleaseRegistryFederationMember) or member.ordinal != ordinal:
                raise ValidationError("federation members must have contiguous ordinals")
            member._validate()
            if member.registry_id in registry_ids or member.registry_address in registry_addresses or member.content_address in member_addresses:
                raise ValidationError("federation members must be unique")
            registry_ids.add(member.registry_id)
            registry_addresses.add(member.registry_address)
            member_addresses.add(member.content_address)
        package_keys, package_addresses = set(), set()
        for ordinal, package in enumerate(self.packages):
            if not isinstance(package, DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage) or package.ordinal != ordinal:
                raise ValidationError("federation packages must have contiguous ordinals")
            package._validate()
            key = (package.registry_id, package.package_id)
            if key in package_keys or package.content_address in package_addresses:
                raise ValidationError("federation packages must be unique")
            if package.registry_id not in registry_ids:
                raise ValidationError("federation package references an unknown member")
            package_keys.add(key)
            package_addresses.add(package.content_address)
        if self.ready_count != sum(package.state == FederationState.READY.value for package in self.packages):
            raise ValidationError("federation ready count does not match packages")
        if self.hold_count != sum(package.state == FederationState.HELD.value for package in self.packages):
            raise ValidationError("federation hold count does not match packages")
        if self.blocked_count != sum(package.state == FederationState.BLOCKED.value for package in self.packages):
            raise ValidationError("federation blocked count does not match packages")
        if self.accepted_count != sum(package.accepted for package in self.packages):
            raise ValidationError("federation accepted count does not match packages")
        if self.release_ready_count != sum(package.release_ready for package in self.packages):
            raise ValidationError("federation release-ready count does not match packages")
        expected_state = FederationState.EMPTY.value if not self.member_count else FederationState.BLOCKED.value if self.blocked_count else FederationState.HELD.value if self.hold_count else FederationState.READY.value
        if self.state != expected_state:
            raise ValidationError("federation state does not match package projections")
        if self.release_ready and (self.state != FederationState.READY.value or self.release_ready_count != self.package_count):
            raise ValidationError("federation release-ready projection is inconsistent")
        if self.state == FederationState.READY.value and not self.accepted:
            raise ValidationError("ready federation must be accepted")
        if self.state == FederationState.BLOCKED.value and self.accepted:
            raise ValidationError("blocked federation cannot be accepted")
        _address(self.content_address, "federation address")
        if not self.content_address.startswith("pending:") and address_federation(self) != self.content_address:
            raise ValidationError("federation address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_id": self.federation_id,
            "version": self.version,
            "boundary": self.boundary,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "member_count": self.member_count,
            "package_count": self.package_count,
            "ready_count": self.ready_count,
            "hold_count": self.hold_count,
            "blocked_count": self.blocked_count,
            "accepted_count": self.accepted_count,
            "release_ready_count": self.release_ready_count,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {
            "members": [member.to_dict() for member in self.members],
            "packages": [package.to_dict() for package in self.packages],
        }


def address_federation(value: DecisionAssuranceHistorySeriesReleaseRegistryFederation) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=PREFIX)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy:
    """Bounded thresholds used to decide federation readiness."""

    def __init__(
        self,
        policy_id: str = DEFAULT_POLICY_ID,
        version: str = VERSION,
        boundary: str = BOUNDARY + "_policy",
        minimum_member_count: int = 1,
        minimum_package_count: int = 1,
        maximum_blocked_members: int = 0,
        maximum_held_members: int = MAX_REGISTRIES,
        require_all_release_ready: bool = True,
        allow_empty: bool = False,
        content_address: str = "pending:federation-policy",
    ) -> None:
        self.policy_id, self.version, self.boundary = policy_id, version, boundary
        self.minimum_member_count, self.minimum_package_count = minimum_member_count, minimum_package_count
        self.maximum_blocked_members, self.maximum_held_members = maximum_blocked_members, maximum_held_members
        self.require_all_release_ready, self.allow_empty = require_all_release_ready, allow_empty
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.policy_id, "federation policy ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY + "_policy":
            raise ValidationError("federation policy contract is invalid")
        _positive_count(self.minimum_member_count, "minimum federation member count", MAX_REGISTRIES)
        _positive_count(self.minimum_package_count, "minimum federation package count", MAX_PACKAGES)
        _count(self.maximum_blocked_members, "maximum blocked federation members", MAX_REGISTRIES)
        _count(self.maximum_held_members, "maximum held federation members", MAX_REGISTRIES)
        _bool(self.require_all_release_ready, "federation all-release-ready policy")
        _bool(self.allow_empty, "federation empty policy")
        _address(self.content_address, "federation policy address")
        if not self.content_address.startswith("pending:") and address_federation_policy(self) != self.content_address:
            raise ValidationError("federation policy address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "boundary": self.boundary,
            "minimum_member_count": self.minimum_member_count,
            "minimum_package_count": self.minimum_package_count,
            "maximum_blocked_members": self.maximum_blocked_members,
            "maximum_held_members": self.maximum_held_members,
            "require_all_release_ready": self.require_all_release_ready,
            "allow_empty": self.allow_empty,
            "content_address": self.content_address,
        }


def address_federation_policy(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_federation_policy(**overrides: Any) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy:
    body = {
        "policy_id": DEFAULT_POLICY_ID,
        "version": VERSION,
        "boundary": BOUNDARY + "_policy",
        "minimum_member_count": 1,
        "minimum_package_count": 1,
        "maximum_blocked_members": 0,
        "maximum_held_members": MAX_REGISTRIES,
        "require_all_release_ready": True,
        "allow_empty": False,
        "content_address": "pending:federation-policy",
    }
    body.update(overrides)
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy(**body)
    body["content_address"] = address_federation_policy(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy(**body)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck:
    """One independently recomputed structural or policy check."""

    def __init__(
        self,
        ordinal: int,
        check_id: str,
        severity: str,
        passed: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal, self.check_id, self.severity = ordinal, check_id, severity
        self.passed, self.detail, self.content_address = passed, detail, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "federation check ordinal", MAX_CHECKS - 1)
        _text(self.check_id, "federation check ID", 128)
        _severity(self.severity)
        _bool(self.passed, "federation check passed")
        _text(self.detail, "federation check detail", 1024)
        _address(self.content_address, "federation check address")
        if not self.content_address.startswith("pending:") and address_federation_check(self) != self.content_address:
            raise ValidationError("federation check address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "check_id": self.check_id,
            "severity": self.severity,
            "passed": self.passed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_federation_check(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def _make_check(ordinal: int, check_id: str, severity: str, passed: bool, detail: str) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck:
    body = {
        "ordinal": ordinal,
        "check_id": check_id,
        "severity": severity,
        "passed": passed,
        "detail": detail,
        "content_address": "pending:federation-check",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck(**body)
    body["content_address"] = address_federation_check(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck(**body)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification:
    """Independent structural verification for a federation projection."""

    def __init__(
        self,
        federation_address: str,
        member_count: int,
        package_count: int,
        check_count: int,
        passed_count: int,
        failed_count: int,
        required_failure_count: int,
        accepted: bool,
        checks: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck],
        content_address: str,
    ) -> None:
        self.federation_address = federation_address
        self.member_count, self.package_count = member_count, package_count
        self.check_count, self.passed_count, self.failed_count = check_count, passed_count, failed_count
        self.required_failure_count, self.accepted = required_failure_count, accepted
        self.checks, self.content_address = tuple(checks), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "federation verification federation address")
        _count(self.member_count, "federation verification member count", MAX_REGISTRIES)
        _count(self.package_count, "federation verification package count", MAX_PACKAGES)
        _count(self.check_count, "federation verification check count", MAX_CHECKS)
        for name, value in (("passed", self.passed_count), ("failed", self.failed_count), ("required failure", self.required_failure_count)):
            _count(value, f"federation verification {name} count", MAX_CHECKS)
        _bool(self.accepted, "federation verification accepted")
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.required_failure_count > self.failed_count:
            raise ValidationError("federation verification counts are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck) or check.ordinal != ordinal:
                raise ValidationError("federation verification checks must be contiguous")
        if self.passed_count != sum(check.passed for check in self.checks) or self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("federation verification check counts do not match")
        expected_required_failures = sum(not check.passed and check.severity == CheckSeverity.REQUIRED.value for check in self.checks)
        if expected_required_failures != self.required_failure_count or self.accepted != (self.required_failure_count == 0):
            raise ValidationError("federation verification acceptance is inconsistent")
        _address(self.content_address, "federation verification address")
        if not self.content_address.startswith("pending:") and address_federation_verification(self) != self.content_address:
            raise ValidationError("federation verification address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation verification crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_address": self.federation_address,
            "member_count": self.member_count,
            "package_count": self.package_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "required_failure_count": self.required_failure_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [check.to_dict() for check in self.checks]}


def address_federation_verification(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=VERIFICATION_PREFIX)


def _structural_checks(federation: DecisionAssuranceHistorySeriesReleaseRegistryFederation) -> tuple[DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck, ...]:
    member_ids = [member.registry_id for member in federation.members]
    member_addresses = [member.registry_address for member in federation.members]
    package_keys = [(package.registry_id, package.package_id) for package in federation.packages]
    package_addresses = [package.content_address for package in federation.packages]
    checks = (
        ("member-count-bounded", CheckSeverity.REQUIRED.value, federation.member_count <= MAX_REGISTRIES, "member count stays within the federation bound"),
        ("member-identities-unique", CheckSeverity.REQUIRED.value, len(member_ids) == len(set(member_ids)) and len(member_addresses) == len(set(member_addresses)), "member IDs and source registry addresses are unique"),
        ("package-identities-unique", CheckSeverity.REQUIRED.value, len(package_keys) == len(set(package_keys)) and len(package_addresses) == len(set(package_addresses)), "source-scoped package identities and package addresses are unique"),
        ("package-count-conserved", CheckSeverity.REQUIRED.value, federation.package_count == sum(member.entry_count for member in federation.members), "package count equals the sum of admitted member entries"),
        ("state-count-conserved", CheckSeverity.REQUIRED.value, federation.ready_count + federation.hold_count + federation.blocked_count == federation.package_count, "ready, held, and blocked package counts are conserved"),
        ("readiness-count-conserved", CheckSeverity.REQUIRED.value, federation.accepted_count <= federation.package_count and federation.release_ready_count <= federation.accepted_count, "accepted and release-ready counts are bounded"),
        ("public-projection-closed", CheckSeverity.REQUIRED.value, _public(federation.to_dict()), "federation projection contains only public transport fields"),
    )
    return tuple(_make_check(ordinal, check_id, severity, passed, detail) for ordinal, (check_id, severity, passed, detail) in enumerate(checks))


def build_federation_verification(federation: DecisionAssuranceHistorySeriesReleaseRegistryFederation) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification:
    verify_federation(federation)
    checks = _structural_checks(federation)
    body = {
        "federation_address": federation.content_address,
        "member_count": federation.member_count,
        "package_count": federation.package_count,
        "check_count": len(checks),
        "passed_count": sum(check.passed for check in checks),
        "failed_count": sum(not check.passed for check in checks),
        "required_failure_count": sum(not check.passed and check.severity == CheckSeverity.REQUIRED.value for check in checks),
        "accepted": sum(not check.passed and check.severity == CheckSeverity.REQUIRED.value for check in checks) == 0,
        "checks": checks,
        "content_address": "pending:federation-verification",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification(**body)
    body["content_address"] = address_federation_verification(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification(**body)


def verify_federation_verification(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification):
        raise ValidationError("federation verification requires a typed verification")
    value._validate()
    if address_federation_verification(value) != value.content_address:
        raise ValidationError("federation verification address mismatch")
    return value


class DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck:
    """A policy-specific check kept separate from structural verification."""

    def __init__(self, ordinal: int, check_id: str, severity: str, passed: bool, detail: str, content_address: str) -> None:
        self.ordinal, self.check_id, self.severity = ordinal, check_id, severity
        self.passed, self.detail, self.content_address = passed, detail, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "policy check ordinal", MAX_CHECKS - 1)
        _text(self.check_id, "policy check ID", 128)
        _severity(self.severity)
        _bool(self.passed, "policy check passed")
        _text(self.detail, "policy check detail", 1024)
        _address(self.content_address, "policy check address")
        if not self.content_address.startswith("pending:") and address_policy_check(self) != self.content_address:
            raise ValidationError("policy check address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("policy check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "check_id": self.check_id,
            "severity": self.severity,
            "passed": self.passed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_policy_check(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_EVALUATION_PREFIX + "-check")


def _make_policy_check(ordinal: int, check_id: str, severity: str, passed: bool, detail: str) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck:
    body = {
        "ordinal": ordinal,
        "check_id": check_id,
        "severity": severity,
        "passed": passed,
        "detail": detail,
        "content_address": "pending:policy-check",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck(**body)
    body["content_address"] = address_policy_check(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck(**body)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation:
    """Policy result kept separate from structural verification."""

    def __init__(
        self,
        federation_address: str,
        policy_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        check_count: int,
        passed_count: int,
        failed_count: int,
        required_failure_count: int,
        checks: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck],
        content_address: str,
    ) -> None:
        self.federation_address, self.policy_address = federation_address, policy_address
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.check_count, self.passed_count, self.failed_count = check_count, passed_count, failed_count
        self.required_failure_count = required_failure_count
        self.checks, self.content_address = tuple(checks), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "policy evaluation federation address")
        _address(self.policy_address, "policy evaluation policy address")
        _state(self.state, "policy evaluation state")
        _bool(self.accepted, "policy evaluation accepted")
        _bool(self.release_ready, "policy evaluation release-ready")
        _count(self.check_count, "policy evaluation check count", MAX_CHECKS)
        for name, value in (("passed", self.passed_count), ("failed", self.failed_count), ("required failure", self.required_failure_count)):
            _count(value, f"policy evaluation {name} count", MAX_CHECKS)
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.required_failure_count > self.failed_count:
            raise ValidationError("policy evaluation counts are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck) or check.ordinal != ordinal:
                raise ValidationError("policy evaluation checks must be contiguous")
        if self.passed_count != sum(check.passed for check in self.checks) or self.failed_count != sum(not check.passed for check in self.checks):
            raise ValidationError("policy evaluation check counts do not match")
        required = sum(not check.passed and check.severity == CheckSeverity.REQUIRED.value for check in self.checks)
        if required != self.required_failure_count or self.accepted != (required == 0):
            raise ValidationError("policy evaluation acceptance is inconsistent")
        if self.release_ready and (self.state != FederationState.READY.value or not self.accepted):
            raise ValidationError("policy evaluation readiness is inconsistent")
        if self.state == FederationState.READY.value and not self.release_ready:
            raise ValidationError("ready policy evaluation must be release-ready")
        if self.state == FederationState.BLOCKED.value and self.accepted:
            raise ValidationError("blocked policy evaluation cannot be accepted")
        _address(self.content_address, "policy evaluation address")
        if not self.content_address.startswith("pending:") and address_policy_evaluation(self) != self.content_address:
            raise ValidationError("policy evaluation address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("policy evaluation crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_address": self.federation_address,
            "policy_address": self.policy_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "required_failure_count": self.required_failure_count,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"checks": [check.to_dict() for check in self.checks]}


def address_policy_evaluation(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=POLICY_EVALUATION_PREFIX)


def _policy_checks(
    federation: DecisionAssuranceHistorySeriesReleaseRegistryFederation,
    policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy,
) -> tuple[DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck, ...]:
    blocked_members = sum(member.state == FederationState.BLOCKED.value for member in federation.members)
    held_members = sum(member.state == FederationState.HELD.value for member in federation.members)
    empty_allowed = federation.member_count > 0 or policy.allow_empty
    all_ready = federation.package_count > 0 and federation.release_ready_count == federation.package_count
    checks = (
        ("minimum-members", CheckSeverity.REQUIRED.value, federation.member_count >= policy.minimum_member_count or (not federation.member_count and policy.allow_empty), f"member count {federation.member_count} meets the configured minimum of {policy.minimum_member_count}"),
        ("minimum-packages", CheckSeverity.REQUIRED.value, federation.package_count >= policy.minimum_package_count or (not federation.package_count and policy.allow_empty), f"package count {federation.package_count} meets the configured minimum of {policy.minimum_package_count}"),
        ("blocked-member-budget", CheckSeverity.REQUIRED.value, blocked_members <= policy.maximum_blocked_members, f"blocked member count {blocked_members} is within the budget of {policy.maximum_blocked_members}"),
        ("blocked-state", CheckSeverity.REQUIRED.value, federation.blocked_count == 0, "blocked package projections cannot be promoted by federation policy"),
        ("held-member-budget", CheckSeverity.REQUIRED.value, held_members <= policy.maximum_held_members, f"held member count {held_members} is within the budget of {policy.maximum_held_members}"),
        ("empty-federation-policy", CheckSeverity.REQUIRED.value, empty_allowed, "empty federation is allowed by policy or the federation has members"),
        ("release-readiness", CheckSeverity.OPTIONAL.value, (not policy.require_all_release_ready) or all_ready, "all admitted packages are release-ready when required"),
    )
    return tuple(_make_policy_check(ordinal, check_id, severity, passed, detail) for ordinal, (check_id, severity, passed, detail) in enumerate(checks))


def build_policy_evaluation(
    federation: DecisionAssuranceHistorySeriesReleaseRegistryFederation,
    policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy,
) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation:
    verify_federation(federation)
    verify_federation_policy(policy)
    checks = _policy_checks(federation, policy)
    required_failure_count = sum(not check.passed and check.severity == CheckSeverity.REQUIRED.value for check in checks)
    state = FederationState.BLOCKED.value if required_failure_count else FederationState.EMPTY.value if not federation.member_count else FederationState.READY.value if (not policy.require_all_release_ready or federation.release_ready_count == federation.package_count) and federation.package_count else FederationState.HELD.value
    body = {
        "federation_address": federation.content_address,
        "policy_address": policy.content_address,
        "state": state,
        "accepted": required_failure_count == 0,
        "release_ready": required_failure_count == 0 and state == FederationState.READY.value,
        "check_count": len(checks),
        "passed_count": sum(check.passed for check in checks),
        "failed_count": sum(not check.passed for check in checks),
        "required_failure_count": required_failure_count,
        "checks": checks,
        "content_address": "pending:federation-policy-evaluation",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation(**body)
    body["content_address"] = address_policy_evaluation(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation(**body)


def verify_federation_policy(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy):
        raise ValidationError("federation policy requires a typed policy")
    value._validate()
    if address_federation_policy(value) != value.content_address:
        raise ValidationError("federation policy address mismatch")
    return value


def verify_policy_evaluation(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation):
        raise ValidationError("policy evaluation requires a typed evaluation")
    value._validate()
    if address_policy_evaluation(value) != value.content_address:
        raise ValidationError("policy evaluation address mismatch")
    return value


class DecisionAssuranceHistorySeriesReleaseRegistryFederationStage:
    """One ordered runtime stage with explicit input/output addresses."""

    def __init__(self, ordinal: int, stage_id: str, kind: str, state: str, accepted: bool, detail: str, input_address: str, output_address: str, content_address: str) -> None:
        self.ordinal, self.stage_id, self.kind = ordinal, stage_id, kind
        self.state, self.accepted, self.detail = state, accepted, detail
        self.input_address, self.output_address = input_address, output_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "federation stage ordinal", MAX_STAGES - 1)
        _text(self.stage_id, "federation stage ID", 128)
        _text(self.kind, "federation stage kind", 128)
        _stage_state(self.state)
        _bool(self.accepted, "federation stage accepted")
        _text(self.detail, "federation stage detail", 1024)
        _address(self.input_address, "federation stage input address")
        _address(self.output_address, "federation stage output address")
        _address(self.content_address, "federation stage address")
        if self.state == FederationStageState.PASSED.value and not self.accepted:
            raise ValidationError("passed federation stage must be accepted")
        if not self.content_address.startswith("pending:") and address_federation_stage(self) != self.content_address:
            raise ValidationError("federation stage address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation stage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "stage_id": self.stage_id,
            "kind": self.kind,
            "state": self.state,
            "accepted": self.accepted,
            "detail": self.detail,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "content_address": self.content_address,
        }


def address_federation_stage(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationStage) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=STAGE_PREFIX)


def _make_stage(ordinal: int, stage_id: str, kind: str, state: str, accepted: bool, detail: str, input_address: str, output_address: str) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationStage:
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "kind": kind,
        "state": state,
        "accepted": accepted,
        "detail": detail,
        "input_address": input_address,
        "output_address": output_address,
        "content_address": "pending:federation-stage",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationStage(**body)
    body["content_address"] = address_federation_stage(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationStage(**body)


class DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime:
    """Five-stage fail-closed federation closure."""

    def __init__(self, federation_address: str, policy_address: str, policy_evaluation_address: str, state: str, accepted: bool, release_ready: bool, stage_count: int, passed_count: int, held_count: int, blocked_count: int, stages: Sequence[DecisionAssuranceHistorySeriesReleaseRegistryFederationStage], content_address: str) -> None:
        self.federation_address, self.policy_address = federation_address, policy_address
        self.policy_evaluation_address = policy_evaluation_address
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.stage_count, self.passed_count, self.held_count, self.blocked_count = stage_count, passed_count, held_count, blocked_count
        self.stages, self.content_address = tuple(stages), content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "federation runtime federation address")
        _address(self.policy_address, "federation runtime policy address")
        _address(self.policy_evaluation_address, "federation runtime evaluation address")
        _state(self.state, "federation runtime state")
        _bool(self.accepted, "federation runtime accepted")
        _bool(self.release_ready, "federation runtime release-ready")
        _count(self.stage_count, "federation runtime stage count", MAX_STAGES)
        for name, value in (("passed", self.passed_count), ("held", self.held_count), ("blocked", self.blocked_count)):
            _count(value, f"federation runtime {name} stage count", MAX_STAGES)
        if self.stage_count != len(self.stages) or self.passed_count + self.held_count + self.blocked_count != self.stage_count:
            raise ValidationError("federation runtime stage counts are not conserved")
        for ordinal, stage in enumerate(self.stages):
            if not isinstance(stage, DecisionAssuranceHistorySeriesReleaseRegistryFederationStage) or stage.ordinal != ordinal:
                raise ValidationError("federation runtime stages must be contiguous")
        if self.passed_count != sum(stage.state == FederationStageState.PASSED.value for stage in self.stages) or self.held_count != sum(stage.state == FederationStageState.HELD.value for stage in self.stages) or self.blocked_count != sum(stage.state == FederationStageState.BLOCKED.value for stage in self.stages):
            raise ValidationError("federation runtime stage counts do not match")
        if self.state == FederationState.READY.value and (not self.accepted or not self.release_ready or self.blocked_count):
            raise ValidationError("ready federation runtime is inconsistent")
        if self.state == FederationState.BLOCKED.value and self.accepted:
            raise ValidationError("blocked federation runtime cannot be accepted")
        _address(self.content_address, "federation runtime address")
        if not self.content_address.startswith("pending:") and address_federation_runtime(self) != self.content_address:
            raise ValidationError("federation runtime address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation runtime crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "federation_address": self.federation_address,
            "policy_address": self.policy_address,
            "policy_evaluation_address": self.policy_evaluation_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "stage_count": self.stage_count,
            "passed_count": self.passed_count,
            "held_count": self.held_count,
            "blocked_count": self.blocked_count,
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"stages": [stage.to_dict() for stage in self.stages]}


def address_federation_runtime(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_federation_runtime(
    federation: DecisionAssuranceHistorySeriesReleaseRegistryFederation,
    policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy,
    verification: DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification,
    evaluation: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation,
) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime:
    verify_federation(federation)
    verify_federation_policy(policy)
    verify_federation_verification(verification)
    verify_policy_evaluation(evaluation)
    if verification.federation_address != federation.content_address or evaluation.federation_address != federation.content_address or evaluation.policy_address != policy.content_address:
        raise ValidationError("federation runtime inputs are not linked")
    final_state = (
        FederationState.BLOCKED.value
        if not verification.accepted or evaluation.state == FederationState.BLOCKED.value
        else FederationState.EMPTY.value
        if evaluation.state == FederationState.EMPTY.value
        else FederationState.HELD.value
        if evaluation.state == FederationState.HELD.value
        else FederationState.READY.value
    )
    final_accepted = verification.accepted and evaluation.accepted
    final_release_ready = final_accepted and evaluation.release_ready and final_state == FederationState.READY.value
    stage_specs = (
        ("admit-members", "member-admission", FederationStageState.PASSED.value, True, "source registries were admitted as addressed federation members", policy.content_address, federation.content_address),
        ("verify-structure", "structural-verification", FederationStageState.PASSED.value if verification.accepted else FederationStageState.BLOCKED.value, verification.accepted, "independent member, package, and conservation checks completed", federation.content_address, verification.content_address),
        ("evaluate-policy", "policy-evaluation", FederationStageState.PASSED.value if evaluation.state == FederationState.READY.value else FederationStageState.HELD.value if evaluation.state in {FederationState.HELD.value, FederationState.EMPTY.value} else FederationStageState.BLOCKED.value, evaluation.accepted, "configured federation policy was evaluated", verification.content_address, evaluation.content_address),
        ("aggregate-readiness", "readiness-aggregation", FederationStageState.PASSED.value if final_state == FederationState.READY.value else FederationStageState.HELD.value if final_state in {FederationState.HELD.value, FederationState.EMPTY.value} else FederationStageState.BLOCKED.value, final_accepted, "aggregate acceptance and release readiness were conserved", evaluation.content_address, federation.content_address),
        ("complete", "federation-closure", FederationStageState.PASSED.value if final_state == FederationState.READY.value else FederationStageState.HELD.value if final_state in {FederationState.HELD.value, FederationState.EMPTY.value} else FederationStageState.BLOCKED.value, final_accepted, "federation closure is ready for bounded downstream review", federation.content_address, federation.content_address),
    )
    stages = tuple(_make_stage(ordinal, stage_id, kind, state, accepted, detail, input_address, output_address) for ordinal, (stage_id, kind, state, accepted, detail, input_address, output_address) in enumerate(stage_specs))
    body = {
        "federation_address": federation.content_address,
        "policy_address": policy.content_address,
        "policy_evaluation_address": evaluation.content_address,
        "state": final_state,
        "accepted": final_accepted,
        "release_ready": final_release_ready,
        "stage_count": len(stages),
        "passed_count": sum(stage.state == FederationStageState.PASSED.value for stage in stages),
        "held_count": sum(stage.state == FederationStageState.HELD.value for stage in stages),
        "blocked_count": sum(stage.state == FederationStageState.BLOCKED.value for stage in stages),
        "stages": stages,
        "content_address": "pending:federation-runtime",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime(**body)
    body["content_address"] = address_federation_runtime(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime(**body)


def verify_federation_runtime(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime):
        raise ValidationError("federation runtime requires a typed runtime")
    value._validate()
    if address_federation_runtime(value) != value.content_address:
        raise ValidationError("federation runtime address mismatch")
    return value


class DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    """All addressed closure documents needed for offline federation review."""

    def __init__(
        self,
        federation: DecisionAssuranceHistorySeriesReleaseRegistryFederation,
        policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy,
        verification: DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification,
        policy_evaluation: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation,
        runtime: DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime,
    ) -> None:
        self.federation, self.policy, self.verification = federation, policy, verification
        self.policy_evaluation, self.runtime = policy_evaluation, runtime
        self._validate()

    def _validate(self) -> None:
        verify_federation(self.federation)
        verify_federation_policy(self.policy)
        verify_federation_verification(self.verification)
        verify_policy_evaluation(self.policy_evaluation)
        verify_federation_runtime(self.runtime)
        if self.verification.federation_address != self.federation.content_address:
            raise ValidationError("bundle verification is linked to a different federation")
        if self.policy_evaluation.federation_address != self.federation.content_address or self.policy_evaluation.policy_address != self.policy.content_address:
            raise ValidationError("bundle policy evaluation linkage is invalid")
        if self.runtime.federation_address != self.federation.content_address or self.runtime.policy_address != self.policy.content_address or self.runtime.policy_evaluation_address != self.policy_evaluation.content_address:
            raise ValidationError("bundle runtime linkage is invalid")
        if self.runtime.accepted != (self.verification.accepted and self.policy_evaluation.accepted):
            raise ValidationError("bundle runtime acceptance is not conserved")
        if self.runtime.release_ready != (self.policy_evaluation.release_ready and self.runtime.accepted):
            raise ValidationError("bundle runtime readiness is not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("federation bundle crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return self.federation.summary() | {
            "policy_address": self.policy.content_address,
            "verification_address": self.verification.content_address,
            "policy_evaluation_address": self.policy_evaluation.content_address,
            "runtime_address": self.runtime.content_address,
            "verification_accepted": self.verification.accepted,
            "policy_accepted": self.policy_evaluation.accepted,
            "runtime_state": self.runtime.state,
            "runtime_release_ready": self.runtime.release_ready,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "federation": self.federation.to_dict(),
            "policy": self.policy.to_dict(),
            "verification": self.verification.to_dict(),
            "policy_evaluation": self.policy_evaluation.to_dict(),
            "runtime": self.runtime.to_dict(),
        }


def _member_from_registry(ordinal: int, value: registry_model.DecisionAssuranceHistorySeriesReleaseRegistry) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationMember:
    body = {
        "ordinal": ordinal,
        "registry_id": value.registry_id,
        "registry_address": value.content_address,
        "entry_count": value.entry_count,
        "ready_count": value.ready_count,
        "hold_count": value.hold_count,
        "blocked_count": value.blocked_count,
        "accepted_count": value.accepted_count,
        "release_ready_count": value.release_ready_count,
        "state": _derive_registry_state(value),
        "content_address": "pending:federation-member",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationMember(**body)
    body["content_address"] = address_federation_member(provisional)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationMember(**body)


def _packages_from_registries(registries: Sequence[registry_model.DecisionAssuranceHistorySeriesReleaseRegistry]) -> tuple[DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage, ...]:
    ordered = sorted(registries, key=lambda item: (item.registry_id, item.content_address))
    packages: list[DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage] = []
    for value in ordered:
        for entry in value.entries:
            body = {
                "ordinal": len(packages),
                "registry_id": value.registry_id,
                "package_id": entry.package_id,
                "release_id": entry.release_id,
                "registry_address": value.content_address,
                "registry_entry_address": entry.content_address,
                "package_address": entry.package_address,
                "release_address": entry.release_address,
                "state": FederationState.HELD.value if entry.state == "hold" else entry.state,
                "accepted": entry.accepted,
                "release_ready": entry.release_ready,
                "content_address": "pending:federation-package",
            }
            provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage(**body)
            body["content_address"] = address_federation_package(provisional)
            packages.append(DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage(**body))
    return tuple(packages)


def verify_federation(value: DecisionAssuranceHistorySeriesReleaseRegistryFederation) -> DecisionAssuranceHistorySeriesReleaseRegistryFederation:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryFederation):
        raise ValidationError("federation verification requires a typed federation")
    value._validate()
    if address_federation(value) != value.content_address:
        raise ValidationError("federation address mismatch")
    return value


def build_federation(
    registries: Sequence[registry_model.DecisionAssuranceHistorySeriesReleaseRegistry],
    *,
    federation_id: str = DEFAULT_FEDERATION_ID,
    policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy | None = None,
) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    if not isinstance(registries, (list, tuple)):
        raise ValidationError("federation registries must be a sequence")
    policy = policy or default_federation_policy()
    verify_federation_policy(policy)
    if len(registries) > MAX_REGISTRIES:
        raise ValidationError("federation exceeds its registry bound")
    if not registries and not policy.allow_empty:
        raise ValidationError("federation requires one or more registries unless empty is allowed")
    verified: list[registry_model.DecisionAssuranceHistorySeriesReleaseRegistry] = []
    for value in registries:
        if not isinstance(value, registry_model.DecisionAssuranceHistorySeriesReleaseRegistry):
            raise ValidationError("federation members must be typed release registries")
        verified.append(registry_model.verify_decision_assurance_history_series_release_registry(value))
    ordered = sorted(verified, key=lambda item: (item.registry_id, item.content_address))
    if len({item.registry_id for item in ordered}) != len(ordered) or len({item.content_address for item in ordered}) != len(ordered):
        raise ValidationError("federation registry identities must be unique")
    members = tuple(_member_from_registry(ordinal, value) for ordinal, value in enumerate(ordered))
    packages = _packages_from_registries(ordered)
    state = FederationState.EMPTY.value if not packages else FederationState.BLOCKED.value if any(package.state == FederationState.BLOCKED.value for package in packages) else FederationState.HELD.value if any(package.state == FederationState.HELD.value for package in packages) else FederationState.READY.value
    body = {
        "federation_id": federation_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "state": state,
        "accepted": state != FederationState.BLOCKED.value,
        "release_ready": state == FederationState.READY.value and bool(packages),
        "member_count": len(members),
        "package_count": len(packages),
        "ready_count": sum(package.state == FederationState.READY.value for package in packages),
        "hold_count": sum(package.state == FederationState.HELD.value for package in packages),
        "blocked_count": sum(package.state == FederationState.BLOCKED.value for package in packages),
        "accepted_count": sum(package.accepted for package in packages),
        "release_ready_count": sum(package.release_ready for package in packages),
        "members": members,
        "packages": packages,
        "content_address": "pending:federation",
    }
    provisional = DecisionAssuranceHistorySeriesReleaseRegistryFederation(**body)
    body["content_address"] = address_federation(provisional)
    federation = DecisionAssuranceHistorySeriesReleaseRegistryFederation(**body)
    verification = build_federation_verification(federation)
    evaluation = build_policy_evaluation(federation, policy)
    runtime = build_federation_runtime(federation, policy, verification, evaluation)
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle(federation, policy, verification, evaluation, runtime)


def build_federation_from_directories(
    directories: Sequence[str | Path],
    *,
    federation_id: str = DEFAULT_FEDERATION_ID,
    policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy | None = None,
) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    if not isinstance(directories, (list, tuple)):
        raise ValidationError("federation registry directories must be a sequence")
    registries = tuple(registry_model.load_decision_assurance_history_series_release_registry(directory) for directory in directories)
    return build_federation(registries, federation_id=federation_id, policy=policy)


def discover_federation_registry_directories(
    root: str | Path,
    *,
    recursive: bool = False,
) -> tuple[Path, ...]:
    """Discover exact release-registry packages below a data root.

    Discovery is deliberately shallow by default: a downloaded-data root can
    contain readme files, checksums, and unrelated artifacts without changing
    the federation input set. Only directories with the exact source registry
    file set are admitted. Recursive mode is useful for exports grouped by
    institution or run, but still treats every exact registry directory as a
    single input and keeps the result deterministically sorted.
    """
    source = Path(root)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("federation discovery root must be a directory")
    candidates: list[Path] = []
    pending = [source]
    while pending:
        current = pending.pop(0)
        children = sorted(current.iterdir(), key=lambda item: item.name.casefold())
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir():
                child_names = {item.name for item in child.iterdir()}
                if child_names == set(registry_model.FILES):
                    candidates.append(child)
                elif recursive:
                    pending.append(child)
    unique = tuple(sorted(set(candidates), key=lambda item: str(item).casefold()))
    if len(unique) > MAX_REGISTRIES:
        raise ValidationError("federation discovery exceeds its registry bound")
    return unique


def build_federation_from_root(
    root: str | Path,
    *,
    federation_id: str = DEFAULT_FEDERATION_ID,
    policy: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy | None = None,
    recursive: bool = False,
) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    """Build a federation from exact registry packages found under ``root``."""
    directories = discover_federation_registry_directories(root, recursive=recursive)
    return build_federation_from_directories(
        directories,
        federation_id=federation_id,
        policy=policy,
    )


def inspect_federation_registry_root(
    root: str | Path,
    *,
    recursive: bool = False,
) -> dict[str, Any]:
    """Return a path-free admission preview for a downloaded-data root.

    The preview loads and independently verifies every discovered registry but
    emits only stable public summaries. It is safe to use as a preflight step
    before selecting a policy or creating a federation transport.
    """
    directories = discover_federation_registry_directories(root, recursive=recursive)
    registries = tuple(
        registry_model.load_decision_assurance_history_series_release_registry(directory)
        for directory in directories
    )
    ordered = tuple(sorted(registries, key=lambda item: (item.registry_id, item.content_address)))
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "candidate_count": len(ordered),
        "verified_count": len(ordered),
        "registries": [
            {
                "registry_id": value.registry_id,
                "registry_address": value.content_address,
                "entry_count": value.entry_count,
                "ready_count": value.ready_count,
                "hold_count": value.hold_count,
                "blocked_count": value.blocked_count,
                "accepted_count": value.accepted_count,
                "release_ready_count": value.release_ready_count,
            }
            for value in ordered
        ],
    }


def federation_member_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationMember:
    body = dict(_mapping(value, "federation member"))
    allowed = {"ordinal", "registry_id", "registry_address", "entry_count", "ready_count", "hold_count", "blocked_count", "accepted_count", "release_ready_count", "state", "content_address"}
    _strict(body, allowed, "federation member")
    _required(body, allowed, "federation member")
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationMember(**body)


def federation_package_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage:
    body = dict(_mapping(value, "federation package"))
    allowed = {"ordinal", "registry_id", "package_id", "release_id", "registry_address", "registry_entry_address", "package_address", "release_address", "state", "accepted", "release_ready", "content_address"}
    _strict(body, allowed, "federation package")
    _required(body, allowed, "federation package")
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage(**body)


def federation_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederation:
    body = dict(_mapping(value, "federation"))
    allowed = {"federation_id", "version", "boundary", "state", "accepted", "release_ready", "member_count", "package_count", "ready_count", "hold_count", "blocked_count", "accepted_count", "release_ready_count", "members", "packages", "content_address"}
    _strict(body, allowed, "federation")
    _required(body, allowed, "federation")
    body["members"] = tuple(federation_member_from_mapping(item) for item in _mapping_sequence(body["members"], "federation members"))
    body["packages"] = tuple(federation_package_from_mapping(item) for item in _mapping_sequence(body["packages"], "federation packages"))
    return verify_federation(DecisionAssuranceHistorySeriesReleaseRegistryFederation(**body))


def federation_policy_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy:
    body = dict(_mapping(value, "federation policy"))
    allowed = {"policy_id", "version", "boundary", "minimum_member_count", "minimum_package_count", "maximum_blocked_members", "maximum_held_members", "require_all_release_ready", "allow_empty", "content_address"}
    _strict(body, allowed, "federation policy")
    _required(body, allowed, "federation policy")
    return verify_federation_policy(DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy(**body))


def federation_check_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck:
    body = dict(_mapping(value, "federation check"))
    allowed = {"ordinal", "check_id", "severity", "passed", "detail", "content_address"}
    _strict(body, allowed, "federation check")
    _required(body, allowed, "federation check")
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck(**body)


def federation_verification_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification:
    body = dict(_mapping(value, "federation verification"))
    allowed = {"federation_address", "member_count", "package_count", "check_count", "passed_count", "failed_count", "required_failure_count", "accepted", "checks", "content_address"}
    _strict(body, allowed, "federation verification")
    _required(body, allowed, "federation verification")
    body["checks"] = tuple(federation_check_from_mapping(item) for item in _mapping_sequence(body["checks"], "federation checks"))
    return verify_federation_verification(DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification(**body))


def policy_check_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck:
    body = dict(_mapping(value, "federation policy check"))
    allowed = {"ordinal", "check_id", "severity", "passed", "detail", "content_address"}
    _strict(body, allowed, "federation policy check")
    _required(body, allowed, "federation policy check")
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck(**body)


def policy_evaluation_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation:
    body = dict(_mapping(value, "federation policy evaluation"))
    allowed = {"federation_address", "policy_address", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "required_failure_count", "checks", "content_address"}
    _strict(body, allowed, "federation policy evaluation")
    _required(body, allowed, "federation policy evaluation")
    body["checks"] = tuple(policy_check_from_mapping(item) for item in _mapping_sequence(body["checks"], "federation policy checks"))
    return verify_policy_evaluation(DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation(**body))


def federation_stage_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationStage:
    body = dict(_mapping(value, "federation stage"))
    allowed = {"ordinal", "stage_id", "kind", "state", "accepted", "detail", "input_address", "output_address", "content_address"}
    _strict(body, allowed, "federation stage")
    _required(body, allowed, "federation stage")
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationStage(**body)


def federation_runtime_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime:
    body = dict(_mapping(value, "federation runtime"))
    allowed = {"federation_address", "policy_address", "policy_evaluation_address", "state", "accepted", "release_ready", "stage_count", "passed_count", "held_count", "blocked_count", "stages", "content_address"}
    _strict(body, allowed, "federation runtime")
    _required(body, allowed, "federation runtime")
    body["stages"] = tuple(federation_stage_from_mapping(item) for item in _mapping_sequence(body["stages"], "federation stages"))
    return verify_federation_runtime(DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime(**body))


def federation_bundle_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    body = dict(_mapping(value, "federation bundle"))
    allowed = {"federation", "policy", "verification", "policy_evaluation", "runtime"}
    _strict(body, allowed, "federation bundle")
    _required(body, allowed, "federation bundle")
    return DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle(
        federation_from_mapping(body["federation"]),
        federation_policy_from_mapping(body["policy"]),
        federation_verification_from_mapping(body["verification"]),
        policy_evaluation_from_mapping(body["policy_evaluation"]),
        federation_runtime_from_mapping(body["runtime"]),
    )


def verify_federation_bundle(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle):
        raise ValidationError("federation bundle verification requires a typed bundle")
    value._validate()
    return value


def _bundle_documents(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> dict[str, bytes]:
    verify_federation_bundle(value)
    return {
        FEDERATION_NAME: _canonical_document(value.federation.to_dict()),
        MEMBERS_NAME: _canonical_document({"members": [member.to_dict() for member in value.federation.members]}),
        PACKAGES_NAME: _canonical_document({"packages": [package.to_dict() for package in value.federation.packages]}),
        POLICY_NAME: _canonical_document(value.policy.to_dict()),
        VERIFICATION_NAME: _canonical_document(value.verification.to_dict()),
        POLICY_EVALUATION_NAME: _canonical_document(value.policy_evaluation.to_dict()),
        RUNTIME_NAME: _canonical_document(value.runtime.to_dict()),
    }


def _manifest_body(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle, documents: Mapping[str, bytes]) -> dict[str, Any]:
    body = {
        "version": VERSION,
        "boundary": BOUNDARY,
        "federation_address": value.federation.content_address,
        "policy_address": value.policy.content_address,
        "verification_address": value.verification.content_address,
        "policy_evaluation_address": value.policy_evaluation.content_address,
        "runtime_address": value.runtime.content_address,
        "files": list(FILES),
        "artifact_count": len(FILES) - 1,
        "artifacts": [{"name": name, "bytes": len(documents[name]), "byte_address": _file_address(name, documents[name])} for name in FILES if name != MANIFEST_NAME],
        "content_address": "pending:federation-manifest",
    }
    provisional = dict(body)
    provisional["content_address"] = None
    body["content_address"] = content_hash(provisional, prefix=MANIFEST_PREFIX)
    return body


def _manifest_address(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body["content_address"] = None
    return content_hash(body, prefix=MANIFEST_PREFIX)


def write_federation(
    value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
    directory: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    documents = _bundle_documents(value)
    destination = Path(directory)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValidationError("federation destination must be a regular directory")
        if any(destination.iterdir()) and not overwrite:
            raise ValidationError("federation destination already exists")
    manifest = _manifest_body(value, documents)
    temporary = Path(tempfile.mkdtemp(prefix=".glio-fed-", dir=str(parent)))
    try:
        for name, raw in documents.items():
            (temporary / name).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_document(manifest))
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def _verify_manifest(directory: Path, manifest: Mapping[str, Any], value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle, documents: Mapping[str, bytes]) -> None:
    _strict(manifest, {"version", "boundary", "federation_address", "policy_address", "verification_address", "policy_evaluation_address", "runtime_address", "files", "artifact_count", "artifacts", "content_address"}, "federation manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or tuple(manifest["files"]) != FILES or manifest["artifact_count"] != len(FILES) - 1:
        raise ValidationError("federation manifest contract is invalid")
    if _manifest_address(manifest) != manifest["content_address"]:
        raise ValidationError("federation manifest address mismatch")
    if manifest["federation_address"] != value.federation.content_address or manifest["policy_address"] != value.policy.content_address or manifest["verification_address"] != value.verification.content_address or manifest["policy_evaluation_address"] != value.policy_evaluation.content_address or manifest["runtime_address"] != value.runtime.content_address:
        raise ValidationError("federation manifest linkage is invalid")
    artifacts = _mapping_sequence(manifest["artifacts"], "federation manifest artifacts")
    if len(artifacts) != len(FILES) - 1 or {str(item.get("name")) for item in artifacts} != set(FILES) - {MANIFEST_NAME}:
        raise ValidationError("federation manifest artifact set is invalid")
    for artifact in artifacts:
        _strict(artifact, {"name", "bytes", "byte_address"}, "federation manifest artifact")
        name = _text(artifact["name"], "federation artifact name", 128)
        if artifact["bytes"] != len(documents[name]) or _file_address(name, documents[name]) != artifact["byte_address"]:
            raise ValidationError(f"federation artifact receipt mismatch: {name}")
    if set(directory.iterdir()) != {directory / name for name in FILES}:
        raise ValidationError("federation directory contains an unexpected file set")


def load_federation(directory: str | Path) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    destination = Path(directory)
    _require_directory(destination, "federation directory")
    if {item.name for item in destination.iterdir()} != set(FILES):
        raise ValidationError("federation directory file set is invalid")
    documents: dict[str, bytes] = {}
    parsed: dict[str, dict[str, Any]] = {}
    for name in FILES:
        path = destination / name
        _require_regular_file(path, f"federation {name}")
        raw = path.read_bytes()
        value = _read_json(path, f"federation {name}")
        if raw != _canonical_document(value):
            raise ValidationError(f"federation {name} is not canonical JSON")
        documents[name] = raw
        parsed[name] = value
    federation = federation_from_mapping(parsed[FEDERATION_NAME])
    separate_members = tuple(federation_member_from_mapping(item) for item in _mapping_sequence(parsed[MEMBERS_NAME].get("members"), "federation members document"))
    separate_packages = tuple(federation_package_from_mapping(item) for item in _mapping_sequence(parsed[PACKAGES_NAME].get("packages"), "federation packages document"))
    if tuple(item.to_dict() for item in separate_members) != tuple(item.to_dict() for item in federation.members) or tuple(item.to_dict() for item in separate_packages) != tuple(item.to_dict() for item in federation.packages):
        raise ValidationError("federation split projections do not match federation document")
    bundle = DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle(
        federation,
        federation_policy_from_mapping(parsed[POLICY_NAME]),
        federation_verification_from_mapping(parsed[VERIFICATION_NAME]),
        policy_evaluation_from_mapping(parsed[POLICY_EVALUATION_NAME]),
        federation_runtime_from_mapping(parsed[RUNTIME_NAME]),
    )
    _verify_manifest(destination, parsed[MANIFEST_NAME], bundle, documents)
    return verify_federation_bundle(bundle)


def verify_federation_directory(directory: str | Path) -> DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle:
    return load_federation(directory)


def federation_json(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return canonical_json(value.to_dict())


def federation_verification_json(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification) -> str:
    verify_federation_verification(value)
    return canonical_json(value.to_dict())


def federation_policy_evaluation_json(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation) -> str:
    verify_policy_evaluation(value)
    return canonical_json(value.to_dict())


def federation_runtime_json(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime) -> str:
    verify_federation_runtime(value)
    return canonical_json(value.to_dict())


def federation_summary_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    """Render the one-row aggregate projection with stable field ordering."""
    verify_federation_bundle(value)
    summary = value.federation.summary()
    return _csv_text((summary,), tuple(summary))


def federation_verification_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text(
        (check.to_dict() for check in value.verification.checks),
        ("ordinal", "check_id", "severity", "passed", "detail", "content_address"),
    )


def federation_policy_evaluation_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text(
        (check.to_dict() for check in value.policy_evaluation.checks),
        ("ordinal", "check_id", "severity", "passed", "detail", "content_address"),
    )


def federation_runtime_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text(
        (stage.to_dict() for stage in value.runtime.stages),
        ("ordinal", "stage_id", "kind", "state", "accepted", "detail", "input_address", "output_address", "content_address"),
    )


def federation_export_documents(
    value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle,
) -> dict[str, str]:
    """Return every human-facing table projection without filesystem effects."""
    verify_federation_bundle(value)
    return {
        "summary.csv": federation_summary_csv(value),
        "members.csv": federation_members_csv(value),
        "packages.csv": federation_packages_csv(value),
        "verification.csv": federation_verification_csv(value),
        "policy-evaluation.csv": federation_policy_evaluation_csv(value),
        "runtime.csv": federation_runtime_csv(value),
        "review.md": render_federation_markdown(value),
    }


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=tuple(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def federation_members_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text([member.to_dict() for member in value.federation.members], ("ordinal", "registry_id", "registry_address", "entry_count", "ready_count", "hold_count", "blocked_count", "accepted_count", "release_ready_count", "state", "content_address"))


def federation_packages_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text([package.to_dict() for package in value.federation.packages], ("ordinal", "registry_id", "package_id", "release_id", "registry_address", "registry_entry_address", "package_address", "release_address", "state", "accepted", "release_ready", "content_address"))


def federation_checks_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text([check.to_dict() for check in value.verification.checks], ("ordinal", "check_id", "severity", "passed", "detail", "content_address"))


def federation_policy_checks_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text([check.to_dict() for check in value.policy_evaluation.checks], ("ordinal", "check_id", "severity", "passed", "detail", "content_address"))


def federation_stages_csv(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _csv_text([stage.to_dict() for stage in value.runtime.stages], ("ordinal", "stage_id", "kind", "state", "accepted", "detail", "input_address", "output_address", "content_address"))


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""] + [f"- **{key}:** {json.dumps(item, ensure_ascii=False, sort_keys=True)}" for key, item in summary.items()]
    if rows:
        fields = tuple(rows[0].keys())
        lines.extend(("", "## Items", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
        lines.extend("| " + " | ".join(json.dumps(row.get(field), ensure_ascii=False, sort_keys=True) for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_federation_markdown(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> str:
    verify_federation_bundle(value)
    return _markdown("Decision Assurance History Series Release Registry Federation", value.summary(), [package.to_dict() for package in value.federation.packages])


class FederationQuery:
    RESOURCES = ("summary", "members", "packages", "ready", "held", "blocked", "accepted", "release-ready", "verification-checks", "policy-checks", "stages")

    def __init__(self, resource: str = "summary", state: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> None:
        self.resource = _text(resource, "federation query resource", 40)
        if self.resource not in self.RESOURCES:
            raise ValidationError("federation query resource is invalid")
        self.state = None if state is None else _state(state, "federation query state")
        self.accepted = None if accepted is None else _bool(accepted, "federation query accepted")
        self.release_ready = None if release_ready is None else _bool(release_ready, "federation query release-ready")
        self.text = None if text is None else _text(text, "federation query text", 256)
        self.offset, self.limit = _count(offset, "federation query offset"), _count(limit, "federation query limit")
        if self.limit < 1:
            raise ValidationError("federation query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "text": self.text, "offset": self.offset, "limit": self.limit}


class FederationQueryResult:
    def __init__(self, federation_address: str, query: FederationQuery, total_count: int, returned_count: int, items: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.federation_address, self.query = federation_address, query
        self.total_count, self.returned_count, self.items = total_count, returned_count, tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.federation_address, "federation query federation address")
        if not isinstance(self.query, FederationQuery):
            raise ValidationError("federation query must be typed")
        _count(self.total_count, "federation query total count")
        _count(self.returned_count, "federation query returned count")
        if self.returned_count != len(self.items) or self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("federation query counts are invalid")
        _address(self.content_address, "federation query address")
        if not self.content_address.startswith("pending:") and address_federation_query(self) != self.content_address:
            raise ValidationError("federation query address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"federation_address": self.federation_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "content_address": self.content_address}


def address_federation_query(value: FederationQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _query_rows(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle, selected: FederationQuery) -> list[dict[str, Any]]:
    if selected.resource == "summary":
        rows = [value.summary()]
    elif selected.resource == "members":
        rows = [member.to_dict() for member in value.federation.members]
    elif selected.resource == "packages":
        rows = [package.to_dict() for package in value.federation.packages]
    elif selected.resource in {"ready", "held", "blocked", "accepted", "release-ready"}:
        rows = [package.to_dict() for package in value.federation.packages]
    elif selected.resource == "verification-checks":
        rows = [check.to_dict() for check in value.verification.checks]
    elif selected.resource == "policy-checks":
        rows = [check.to_dict() for check in value.policy_evaluation.checks]
    else:
        rows = [stage.to_dict() for stage in value.runtime.stages]
    if selected.resource in {"ready", "held", "blocked"}:
        rows = [row for row in rows if row.get("state") == selected.resource]
    elif selected.resource == "accepted":
        rows = [row for row in rows if row.get("accepted") is True]
    elif selected.resource == "release-ready":
        rows = [row for row in rows if row.get("release_ready") is True]
    if selected.state is not None:
        rows = [row for row in rows if row.get("state") == selected.state]
    if selected.accepted is not None:
        rows = [row for row in rows if row.get("accepted") is selected.accepted]
    if selected.release_ready is not None:
        rows = [row for row in rows if row.get("release_ready") is selected.release_ready]
    if selected.text:
        needle = selected.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    return rows


def query_federation(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle, query: FederationQuery | None = None, **kwargs: Any) -> FederationQueryResult:
    verify_federation_bundle(value)
    if query is not None and kwargs:
        raise ValidationError("federation query cannot combine typed query and keyword filters")
    selected = query or FederationQuery(**kwargs)
    rows = _query_rows(value, selected)
    total, page = len(rows), rows[selected.offset : selected.offset + selected.limit]
    body = {"federation_address": value.federation.content_address, "query": selected, "total_count": total, "returned_count": len(page), "items": page, "content_address": "pending:federation-query"}
    provisional = FederationQueryResult(**body)
    body["content_address"] = address_federation_query(provisional)
    return FederationQueryResult(**body)


def verify_federation_query(value: FederationQueryResult) -> FederationQueryResult:
    if not isinstance(value, FederationQueryResult):
        raise ValidationError("federation query verification requires a typed result")
    value._validate()
    if address_federation_query(value) != value.content_address:
        raise ValidationError("federation query address mismatch")
    return value


def federation_query_from_mapping(value: Mapping[str, Any]) -> FederationQueryResult:
    body = dict(_mapping(value, "federation query result"))
    allowed = {"federation_address", "query", "total_count", "returned_count", "items", "content_address"}
    _strict(body, allowed, "federation query result")
    _required(body, allowed, "federation query result")
    query_body = dict(_mapping(body["query"], "federation query"))
    query_allowed = {"resource", "state", "accepted", "release_ready", "text", "offset", "limit"}
    _strict(query_body, query_allowed, "federation query")
    _required(query_body, query_allowed, "federation query")
    body["query"] = FederationQuery(**query_body)
    body["items"] = tuple(_mapping_sequence(body["items"], "federation query items"))
    return verify_federation_query(FederationQueryResult(**body))


def federation_query_json(value: FederationQueryResult) -> str:
    verify_federation_query(value)
    return canonical_json(value.to_dict())


def federation_query_csv(value: FederationQueryResult) -> str:
    verify_federation_query(value)
    fields = tuple(value.items[0].keys()) if value.items else ("federation_address", "resource", "total_count", "returned_count")
    return _csv_text(value.items, fields)


def render_federation_query_markdown(value: FederationQueryResult) -> str:
    verify_federation_query(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Query", {"federation_address": value.federation_address, "resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


class FederationDiffItem:
    """One stable member/package transition between federations."""

    ACTIONS = ("added", "removed", "unchanged", "changed")
    DIRECTIONS = ("unchanged", "improved", "regressed", "changed")

    def __init__(self, ordinal: int, key: str, action: str, direction: str, baseline_value: Mapping[str, Any] | None, candidate_value: Mapping[str, Any] | None, detail: str, content_address: str) -> None:
        self.ordinal, self.key, self.action, self.direction = ordinal, key, action, direction
        self.baseline_value, self.candidate_value = (None if baseline_value is None else dict(baseline_value), None if candidate_value is None else dict(candidate_value))
        self.detail, self.content_address = detail, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "federation diff item ordinal", MAX_PACKAGES * 2 - 1)
        _text(self.key, "federation diff item key", 512)
        if self.action not in self.ACTIONS:
            raise ValidationError("federation diff item action is invalid")
        if self.direction not in self.DIRECTIONS:
            raise ValidationError("federation diff item direction is invalid")
        if self.action == "added" and (self.baseline_value is not None or self.candidate_value is None):
            raise ValidationError("added federation diff item shape is invalid")
        if self.action == "removed" and (self.baseline_value is None or self.candidate_value is not None):
            raise ValidationError("removed federation diff item shape is invalid")
        if self.action in {"unchanged", "changed"} and (self.baseline_value is None or self.candidate_value is None):
            raise ValidationError("matched federation diff item shape is invalid")
        if self.baseline_value is not None and not _public(self.baseline_value) or self.candidate_value is not None and not _public(self.candidate_value):
            raise ValidationError("federation diff item crosses the public boundary")
        _text(self.detail, "federation diff item detail", 1024)
        _address(self.content_address, "federation diff item address")
        if not self.content_address.startswith("pending:") and address_federation_diff_item(self) != self.content_address:
            raise ValidationError("federation diff item address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "key": self.key, "action": self.action, "direction": self.direction, "baseline_value": self.baseline_value, "candidate_value": self.candidate_value, "detail": self.detail, "content_address": self.content_address}


def address_federation_diff_item(value: FederationDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


def _diff_direction(action: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None) -> str:
    if action == "unchanged":
        return "unchanged"
    baseline_score = _state_score(str(baseline.get("state", FederationState.EMPTY.value)) if baseline else FederationState.EMPTY.value, bool(baseline and baseline.get("accepted")), bool(baseline and baseline.get("release_ready")))
    candidate_score = _state_score(str(candidate.get("state", FederationState.EMPTY.value)) if candidate else FederationState.EMPTY.value, bool(candidate and candidate.get("accepted")), bool(candidate and candidate.get("release_ready")))
    return "improved" if candidate_score > baseline_score else "regressed" if candidate_score < baseline_score else "changed"


def _make_diff_item(ordinal: int, key: str, action: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None) -> FederationDiffItem:
    body = {
        "ordinal": ordinal,
        "key": key,
        "action": action,
        "direction": _diff_direction(action, baseline, candidate),
        "baseline_value": baseline,
        "candidate_value": candidate,
        "detail": {"added": "member or package entered the federation", "removed": "member or package left the federation", "unchanged": "federation projection is identical", "changed": "federation projection changed"}[action],
        "content_address": "pending:federation-diff-item",
    }
    provisional = FederationDiffItem(**body)
    body["content_address"] = address_federation_diff_item(provisional)
    return FederationDiffItem(**body)


class FederationDiff:
    """Addressed comparison of two independently verified federation bundles."""

    def __init__(self, diff_id: str, version: str, boundary: str, baseline_address: str, candidate_address: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, state: str, accepted: bool, release_ready: bool, items: Sequence[FederationDiffItem], content_address: str) -> None:
        self.diff_id, self.version, self.boundary = diff_id, version, boundary
        self.baseline_address, self.candidate_address = baseline_address, candidate_address
        self.item_count, self.added_count, self.removed_count = item_count, added_count, removed_count
        self.unchanged_count, self.changed_count = unchanged_count, changed_count
        self.improved_count, self.regressed_count = improved_count, regressed_count
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.items, self.content_address = tuple(items), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "federation diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("federation diff contract is invalid")
        _address(self.baseline_address, "federation diff baseline address")
        _address(self.candidate_address, "federation diff candidate address")
        _count(self.item_count, "federation diff item count", MAX_PACKAGES * 2)
        for name, value in (("added", self.added_count), ("removed", self.removed_count), ("unchanged", self.unchanged_count), ("changed", self.changed_count), ("improved", self.improved_count), ("regressed", self.regressed_count)):
            _count(value, f"federation diff {name} count", MAX_PACKAGES * 2)
        _diff_state(self.state)
        _bool(self.accepted, "federation diff accepted")
        _bool(self.release_ready, "federation diff release-ready")
        if self.item_count != len(self.items) or self.added_count + self.removed_count + self.unchanged_count + self.changed_count != self.item_count or self.improved_count + self.regressed_count > self.item_count:
            raise ValidationError("federation diff counts are not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, FederationDiffItem) or item.ordinal != ordinal:
                raise ValidationError("federation diff items must be contiguous")
        if self.added_count != sum(item.action == "added" for item in self.items) or self.removed_count != sum(item.action == "removed" for item in self.items) or self.unchanged_count != sum(item.action == "unchanged" for item in self.items) or self.changed_count != sum(item.action == "changed" for item in self.items):
            raise ValidationError("federation diff action counts do not match")
        if self.improved_count != sum(item.direction == "improved" for item in self.items) or self.regressed_count != sum(item.direction == "regressed" for item in self.items):
            raise ValidationError("federation diff direction counts do not match")
        expected_state = "regressed" if self.regressed_count else "improved" if self.improved_count else "changed" if self.changed_count else "unchanged"
        if self.state != expected_state:
            raise ValidationError("federation diff state does not match items")
        if self.release_ready != (self.regressed_count == 0):
            raise ValidationError("federation diff readiness is inconsistent")
        _address(self.content_address, "federation diff address")
        if not self.content_address.startswith("pending:") and address_federation_diff(self) != self.content_address:
            raise ValidationError("federation diff address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"items": [item.to_dict() for item in self.items]}


def address_federation_diff(value: FederationDiff) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=DIFF_PREFIX)


def _federation_records(value: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle) -> dict[str, dict[str, Any]]:
    verify_federation_bundle(value)
    records: dict[str, dict[str, Any]] = {}
    for member in value.federation.members:
        body = member.to_dict()
        body.pop("ordinal", None)
        records[f"member:{member.registry_id}"] = body
    for package in value.federation.packages:
        body = package.to_dict()
        body.pop("ordinal", None)
        records[f"package:{package.registry_id}/{package.package_id}"] = body
    return records


def build_federation_diff(baseline: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle, candidate: DecisionAssuranceHistorySeriesReleaseRegistryFederationBundle, *, diff_id: str = DEFAULT_DIFF_ID) -> FederationDiff:
    verify_federation_bundle(baseline)
    verify_federation_bundle(candidate)
    left, right = _federation_records(baseline), _federation_records(candidate)
    items = []
    for ordinal, key in enumerate(sorted(set(left) | set(right))):
        action = "added" if key not in left else "removed" if key not in right else "unchanged" if left[key] == right[key] else "changed"
        items.append(_make_diff_item(ordinal, key, action, left.get(key), right.get(key)))
    items = tuple(items)
    improved = sum(item.direction == "improved" for item in items)
    regressed = sum(item.direction == "regressed" for item in items)
    changed = sum(item.direction == "changed" for item in items)
    state = "regressed" if regressed else "improved" if improved else "changed" if changed else "unchanged"
    body = {
        "diff_id": diff_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "baseline_address": baseline.federation.content_address,
        "candidate_address": candidate.federation.content_address,
        "item_count": len(items),
        "added_count": sum(item.action == "added" for item in items),
        "removed_count": sum(item.action == "removed" for item in items),
        "unchanged_count": sum(item.action == "unchanged" for item in items),
        "changed_count": sum(item.action == "changed" for item in items),
        "improved_count": improved,
        "regressed_count": regressed,
        "state": state,
        "accepted": True,
        "release_ready": regressed == 0,
        "items": items,
        "content_address": "pending:federation-diff",
    }
    provisional = FederationDiff(**body)
    body["content_address"] = address_federation_diff(provisional)
    return FederationDiff(**body)


def verify_federation_diff(value: FederationDiff) -> FederationDiff:
    if not isinstance(value, FederationDiff):
        raise ValidationError("federation diff requires a typed diff")
    value._validate()
    if address_federation_diff(value) != value.content_address:
        raise ValidationError("federation diff address mismatch")
    return value


class FederationDiffQuery:
    RESOURCES = ("summary", "items", "added", "removed", "unchanged", "changed", "improved", "regressed")

    def __init__(self, resource: str = "summary", action: str | None = None, direction: str | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> None:
        self.resource = _text(resource, "federation diff query resource", 32)
        if self.resource not in self.RESOURCES:
            raise ValidationError("federation diff query resource is invalid")
        self.action = None if action is None else _text(action, "federation diff query action", 32)
        self.direction = None if direction is None else _text(direction, "federation diff query direction", 32)
        if self.action is not None and self.action not in FederationDiffItem.ACTIONS:
            raise ValidationError("federation diff query action is invalid")
        if self.direction is not None and self.direction not in FederationDiffItem.DIRECTIONS:
            raise ValidationError("federation diff query direction is invalid")
        self.text = None if text is None else _text(text, "federation diff query text", 256)
        self.offset, self.limit = _count(offset, "federation diff query offset"), _count(limit, "federation diff query limit")
        if self.limit < 1:
            raise ValidationError("federation diff query limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "direction": self.direction, "text": self.text, "offset": self.offset, "limit": self.limit}


class FederationDiffQueryResult:
    def __init__(self, diff_address: str, query: FederationDiffQuery, total_count: int, returned_count: int, items: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.diff_address, self.query = diff_address, query
        self.total_count, self.returned_count, self.items = total_count, returned_count, tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "federation diff query diff address")
        if not isinstance(self.query, FederationDiffQuery):
            raise ValidationError("federation diff query must be typed")
        _count(self.total_count, "federation diff query total count", MAX_PACKAGES * 2)
        _count(self.returned_count, "federation diff query returned count", MAX_PACKAGES * 2)
        if self.returned_count != len(self.items) or self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("federation diff query counts are invalid")
        _address(self.content_address, "federation diff query address")
        if not self.content_address.startswith("pending:") and address_federation_diff_query(self) != self.content_address:
            raise ValidationError("federation diff query address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "content_address": self.content_address}


def address_federation_diff_query(value: FederationDiffQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_QUERY_PREFIX)


def query_federation_diff(value: FederationDiff, query: FederationDiffQuery | None = None, **kwargs: Any) -> FederationDiffQueryResult:
    verify_federation_diff(value)
    if query is not None and kwargs:
        raise ValidationError("federation diff query cannot combine typed query and keyword filters")
    selected = query or FederationDiffQuery(**kwargs)
    rows = [item.to_dict() for item in value.items]
    if selected.resource in {"added", "removed", "unchanged", "changed"}:
        rows = [row for row in rows if row["action"] == selected.resource]
    elif selected.resource in {"improved", "regressed"}:
        rows = [row for row in rows if row["direction"] == selected.resource]
    if selected.action is not None:
        rows = [row for row in rows if row["action"] == selected.action]
    if selected.direction is not None:
        rows = [row for row in rows if row["direction"] == selected.direction]
    if selected.text:
        needle = selected.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    if selected.resource == "summary":
        rows = [value.summary()]
    total, page = len(rows), rows[selected.offset : selected.offset + selected.limit]
    body = {"diff_address": value.content_address, "query": selected, "total_count": total, "returned_count": len(page), "items": page, "content_address": "pending:federation-diff-query"}
    provisional = FederationDiffQueryResult(**body)
    body["content_address"] = address_federation_diff_query(provisional)
    return FederationDiffQueryResult(**body)


def verify_federation_diff_query(value: FederationDiffQueryResult) -> FederationDiffQueryResult:
    if not isinstance(value, FederationDiffQueryResult):
        raise ValidationError("federation diff query verification requires a typed result")
    value._validate()
    if address_federation_diff_query(value) != value.content_address:
        raise ValidationError("federation diff query address mismatch")
    return value


def federation_diff_query_from_mapping(value: Mapping[str, Any]) -> FederationDiffQueryResult:
    body = dict(_mapping(value, "federation diff query result"))
    allowed = {"diff_address", "query", "total_count", "returned_count", "items", "content_address"}
    _strict(body, allowed, "federation diff query result")
    _required(body, allowed, "federation diff query result")
    query_body = dict(_mapping(body["query"], "federation diff query"))
    query_allowed = {"resource", "action", "direction", "text", "offset", "limit"}
    _strict(query_body, query_allowed, "federation diff query")
    _required(query_body, query_allowed, "federation diff query")
    body["query"] = FederationDiffQuery(**query_body)
    body["items"] = tuple(_mapping_sequence(body["items"], "federation diff query items"))
    return verify_federation_diff_query(FederationDiffQueryResult(**body))


def federation_diff_json(value: FederationDiff) -> str:
    verify_federation_diff(value)
    return canonical_json(value.to_dict())


def federation_diff_csv(value: FederationDiff) -> str:
    verify_federation_diff(value)
    return _csv_text([item.to_dict() for item in value.items], ("ordinal", "key", "action", "direction", "baseline_value", "candidate_value", "detail", "content_address"))


def federation_diff_query_json(value: FederationDiffQueryResult) -> str:
    verify_federation_diff_query(value)
    return canonical_json(value.to_dict())


def federation_diff_query_csv(value: FederationDiffQueryResult) -> str:
    verify_federation_diff_query(value)
    fields = tuple(value.items[0].keys()) if value.items else ("diff_address", "resource", "total_count", "returned_count")
    return _csv_text(value.items, fields)


def render_federation_diff_markdown(value: FederationDiff) -> str:
    verify_federation_diff(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Diff", value.summary(), [item.to_dict() for item in value.items])


def render_federation_diff_query_markdown(value: FederationDiffQueryResult) -> str:
    verify_federation_diff_query(value)
    return _markdown("Decision Assurance History Series Release Registry Federation Diff Query", {"diff_address": value.diff_address, "resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def federation_diff_item_from_mapping(value: Mapping[str, Any]) -> FederationDiffItem:
    body = dict(_mapping(value, "federation diff item"))
    allowed = {"ordinal", "key", "action", "direction", "baseline_value", "candidate_value", "detail", "content_address"}
    _strict(body, allowed, "federation diff item")
    _required(body, allowed, "federation diff item")
    return FederationDiffItem(**body)


def federation_diff_from_mapping(value: Mapping[str, Any]) -> FederationDiff:
    body = dict(_mapping(value, "federation diff"))
    allowed = {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "accepted", "release_ready", "items", "content_address"}
    _strict(body, allowed, "federation diff")
    _required(body, allowed, "federation diff")
    body["items"] = tuple(federation_diff_item_from_mapping(item) for item in _mapping_sequence(body["items"], "federation diff items"))
    return verify_federation_diff(FederationDiff(**body))


def _diff_manifest_body(value: FederationDiff, raw: bytes) -> dict[str, Any]:
    body = {
        "version": VERSION,
        "boundary": BOUNDARY + "_diff",
        "diff_address": value.content_address,
        "files": list(DIFF_FILES),
        "artifact_count": 1,
        "artifacts": [{"name": DIFF_NAME, "bytes": len(raw), "byte_address": _file_address(DIFF_NAME, raw, prefix=DIFF_PREFIX + "-file")}],
        "content_address": "pending:federation-diff-manifest",
    }
    body["content_address"] = content_hash(body | {"content_address": None}, prefix=DIFF_MANIFEST_PREFIX)
    return body


def _diff_manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value) | {"content_address": None}, prefix=DIFF_MANIFEST_PREFIX)


def write_federation_diff(value: FederationDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_federation_diff(value)
    raw = canonical_bytes(value.to_dict())
    destination = Path(directory)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValidationError("federation diff destination must be a regular directory")
        if any(destination.iterdir()) and not overwrite:
            raise ValidationError("federation diff destination already exists")
    temporary = Path(tempfile.mkdtemp(prefix=".glio-fdiff-", dir=str(parent)))
    try:
        (temporary / DIFF_NAME).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(_diff_manifest_body(value, raw)))
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def load_federation_diff(directory: str | Path) -> FederationDiff:
    destination = Path(directory)
    _require_directory(destination, "federation diff directory")
    if {item.name for item in destination.iterdir()} != set(DIFF_FILES):
        raise ValidationError("federation diff directory file set is invalid")
    manifest_path, diff_path = destination / MANIFEST_NAME, destination / DIFF_NAME
    _require_regular_file(manifest_path, "federation diff manifest")
    _require_regular_file(diff_path, "federation diff document")
    manifest_raw, diff_raw = manifest_path.read_bytes(), diff_path.read_bytes()
    manifest, body = _read_json(manifest_path, "federation diff manifest"), _read_json(diff_path, "federation diff document")
    if manifest_raw != canonical_bytes(manifest) or diff_raw != canonical_bytes(body):
        raise ValidationError("federation diff documents must use canonical JSON")
    _strict(manifest, {"version", "boundary", "diff_address", "files", "artifact_count", "artifacts", "content_address"}, "federation diff manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY + "_diff" or tuple(manifest["files"]) != DIFF_FILES or manifest["artifact_count"] != 1 or _diff_manifest_address(manifest) != manifest["content_address"]:
        raise ValidationError("federation diff manifest contract is invalid")
    value = federation_diff_from_mapping(body)
    if manifest["diff_address"] != value.content_address:
        raise ValidationError("federation diff manifest linkage is invalid")
    artifacts = _mapping_sequence(manifest["artifacts"], "federation diff artifacts")
    if len(artifacts) != 1:
        raise ValidationError("federation diff artifact set is invalid")
    artifact = artifacts[0]
    _strict(artifact, {"name", "bytes", "byte_address"}, "federation diff artifact")
    if artifact["name"] != DIFF_NAME or artifact["bytes"] != len(diff_raw) or _file_address(DIFF_NAME, diff_raw, prefix=DIFF_PREFIX + "-file") != artifact["byte_address"]:
        raise ValidationError("federation diff artifact receipt mismatch")
    return value


def verify_federation_diff_directory(directory: str | Path) -> FederationDiff:
    return load_federation_diff(directory)


def federation_member_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationMember",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "registry_id", "registry_address", "entry_count", "ready_count", "hold_count", "blocked_count", "accepted_count", "release_ready_count", "state", "content_address"],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_REGISTRIES - 1},
            "registry_id": {"type": "string"},
            "registry_address": {"type": "string"},
            "entry_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES},
            "ready_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES},
            "hold_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES},
            "blocked_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES},
            "accepted_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES},
            "release_ready_count": {"type": "integer", "minimum": 0, "maximum": registry_model.MAX_ENTRIES},
            "state": {"enum": list(FederationState)},
            "content_address": {"type": "string"},
        },
    }


def federation_package_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationPackage",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "registry_id", "package_id", "release_id", "registry_address", "registry_entry_address", "package_address", "release_address", "state", "accepted", "release_ready", "content_address"],
        "properties": {
            "ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES - 1},
            "registry_id": {"type": "string"},
            "package_id": {"type": "string"},
            "release_id": {"type": "string"},
            "registry_address": {"type": "string"},
            "registry_entry_address": {"type": "string"},
            "package_address": {"type": "string"},
            "release_address": {"type": "string"},
            "state": {"enum": list(FederationState)},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "content_address": {"type": "string"},
        },
    }


def federation_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederation",
        "type": "object",
        "additionalProperties": False,
        "required": ["federation_id", "version", "boundary", "state", "accepted", "release_ready", "member_count", "package_count", "ready_count", "hold_count", "blocked_count", "accepted_count", "release_ready_count", "members", "packages", "content_address"],
        "properties": {
            "federation_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY},
            "state": {"enum": list(FederationState)},
            "accepted": {"type": "boolean"},
            "release_ready": {"type": "boolean"},
            "member_count": {"type": "integer", "minimum": 0, "maximum": MAX_REGISTRIES},
            "package_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES},
            "ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES},
            "hold_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES},
            "blocked_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES},
            "accepted_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES},
            "release_ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES},
            "members": {"type": "array", "maxItems": MAX_REGISTRIES, "items": {"$ref": "#/$defs/member"}},
            "packages": {"type": "array", "maxItems": MAX_PACKAGES, "items": {"$ref": "#/$defs/package"}},
            "content_address": {"type": "string"},
        },
        "$defs": {"member": federation_member_schema(), "package": federation_package_schema()},
    }


def federation_policy_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicy",
        "type": "object",
        "additionalProperties": False,
        "required": ["policy_id", "version", "boundary", "minimum_member_count", "minimum_package_count", "maximum_blocked_members", "maximum_held_members", "require_all_release_ready", "allow_empty", "content_address"],
        "properties": {
            "policy_id": {"type": "string"},
            "version": {"const": VERSION},
            "boundary": {"const": BOUNDARY + "_policy"},
            "minimum_member_count": {"type": "integer", "minimum": 1, "maximum": MAX_REGISTRIES},
            "minimum_package_count": {"type": "integer", "minimum": 1, "maximum": MAX_PACKAGES},
            "maximum_blocked_members": {"type": "integer", "minimum": 0, "maximum": MAX_REGISTRIES},
            "maximum_held_members": {"type": "integer", "minimum": 0, "maximum": MAX_REGISTRIES},
            "require_all_release_ready": {"type": "boolean"},
            "allow_empty": {"type": "boolean"},
            "content_address": {"type": "string"},
        },
    }


def federation_check_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationCheck",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "check_id", "severity", "passed", "detail", "content_address"],
        "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS - 1}, "check_id": {"type": "string"}, "severity": {"enum": list(CheckSeverity)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "content_address": {"type": "string"}},
    }


def federation_verification_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationVerification",
        "type": "object",
        "additionalProperties": False,
        "required": ["federation_address", "member_count", "package_count", "check_count", "passed_count", "failed_count", "required_failure_count", "accepted", "checks", "content_address"],
        "properties": {"federation_address": {"type": "string"}, "member_count": {"type": "integer", "minimum": 0, "maximum": MAX_REGISTRIES}, "package_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES}, "check_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "required_failure_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "maxItems": MAX_CHECKS, "items": {"$ref": "#/$defs/check"}}, "content_address": {"type": "string"}},
        "$defs": {"check": federation_check_schema()},
    }


def federation_policy_check_schema() -> dict[str, Any]:
    return federation_check_schema() | {"title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyCheck"}


def federation_policy_evaluation_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationPolicyEvaluation",
        "type": "object",
        "additionalProperties": False,
        "required": ["federation_address", "policy_address", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "required_failure_count", "checks", "content_address"],
        "properties": {"federation_address": {"type": "string"}, "policy_address": {"type": "string"}, "state": {"enum": list(FederationState)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "required_failure_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "maxItems": MAX_CHECKS, "items": {"$ref": "#/$defs/check"}}, "content_address": {"type": "string"}},
        "$defs": {"check": federation_policy_check_schema()},
    }


def federation_stage_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationStage",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "stage_id", "kind", "state", "accepted", "detail", "input_address", "output_address", "content_address"],
        "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES - 1}, "stage_id": {"type": "string"}, "kind": {"type": "string"}, "state": {"enum": list(FederationStageState)}, "accepted": {"type": "boolean"}, "detail": {"type": "string"}, "input_address": {"type": "string"}, "output_address": {"type": "string"}, "content_address": {"type": "string"}},
    }


def federation_runtime_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DecisionAssuranceHistorySeriesReleaseRegistryFederationRuntime",
        "type": "object",
        "additionalProperties": False,
        "required": ["federation_address", "policy_address", "policy_evaluation_address", "state", "accepted", "release_ready", "stage_count", "passed_count", "held_count", "blocked_count", "stages", "content_address"],
        "properties": {"federation_address": {"type": "string"}, "policy_address": {"type": "string"}, "policy_evaluation_address": {"type": "string"}, "state": {"enum": list(FederationState)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "stage_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "held_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "blocked_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "stages": {"type": "array", "maxItems": MAX_STAGES, "items": {"$ref": "#/$defs/stage"}}, "content_address": {"type": "string"}},
        "$defs": {"stage": federation_stage_schema()},
    }


def federation_query_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationQuery",
        "type": "object",
        "additionalProperties": False,
        "required": ["resource", "state", "accepted", "release_ready", "text", "offset", "limit"],
        "properties": {"resource": {"enum": list(FederationQuery.RESOURCES)}, "state": {"enum": list(FederationState) + [None]}, "accepted": {"type": ["boolean", "null"]}, "release_ready": {"type": ["boolean", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}},
    }


def federation_diff_item_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationDiffItem",
        "type": "object",
        "additionalProperties": False,
        "required": ["ordinal", "key", "action", "direction", "baseline_value", "candidate_value", "detail", "content_address"],
        "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2 - 1}, "key": {"type": "string"}, "action": {"enum": list(FederationDiffItem.ACTIONS)}, "direction": {"enum": list(FederationDiffItem.DIRECTIONS)}, "baseline_value": {"type": ["object", "null"]}, "candidate_value": {"type": ["object", "null"]}, "detail": {"type": "string"}, "content_address": {"type": "string"}},
    }


def federation_diff_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationDiff",
        "type": "object",
        "additionalProperties": False,
        "required": ["diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "accepted", "release_ready", "items", "content_address"],
        "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "added_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "removed_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "unchanged_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "changed_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "improved_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "regressed_count": {"type": "integer", "minimum": 0, "maximum": MAX_PACKAGES * 2}, "state": {"enum": ["unchanged", "improved", "regressed", "changed"]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "items": {"type": "array", "maxItems": MAX_PACKAGES * 2, "items": {"$ref": "#/$defs/item"}}, "content_address": {"type": "string"}},
        "$defs": {"item": federation_diff_item_schema()},
    }


def federation_diff_query_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FederationDiffQuery",
        "type": "object",
        "additionalProperties": False,
        "required": ["resource", "action", "direction", "text", "offset", "limit"],
        "properties": {"resource": {"enum": list(FederationDiffQuery.RESOURCES)}, "action": {"enum": list(FederationDiffItem.ACTIONS) + [None]}, "direction": {"enum": list(FederationDiffItem.DIRECTIONS) + [None]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}},
    }


def federation_capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "admission": {"requires_verified_registries": True, "sort": "registry_id,registry_address then package ordinal", "source_paths_retained": False},
        "states": list(FederationState),
        "stage_states": list(FederationStageState),
        "checks": {"severities": list(CheckSeverity), "structural_count": 7, "policy_count": 7},
        "package": {"files": list(FILES), "manifest": MANIFEST_NAME, "federation": FEDERATION_NAME, "members": MEMBERS_NAME, "packages": PACKAGES_NAME, "policy": POLICY_NAME, "verification": VERIFICATION_NAME, "policy_evaluation": POLICY_EVALUATION_NAME, "runtime": RUNTIME_NAME},
        "diff": {"files": list(DIFF_FILES), "actions": list(FederationDiffItem.ACTIONS), "directions": list(FederationDiffItem.DIRECTIONS), "keys": ["member:<registry_id>", "package:<registry_id>/<package_id>"]},
        "queries": {"resources": list(FederationQuery.RESOURCES), "diff_resources": list(FederationDiffQuery.RESOURCES), "max_limit": MAX_QUERY_ITEMS},
        "limits": {"registries": MAX_REGISTRIES, "packages": MAX_PACKAGES, "checks": MAX_CHECKS, "stages": MAX_STAGES},
        "public_boundary": {"source_paths": False, "nested_payloads": False, "identity_free": True},
    }

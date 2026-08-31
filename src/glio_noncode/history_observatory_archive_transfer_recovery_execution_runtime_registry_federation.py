"""Deterministic federation of independently verified runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-federation-v1"
BOUNDARY = registry_model.BOUNDARY + "_federation"
FEDERATION_PREFIX = registry_model.REGISTRY_PREFIX + "-federation"
MEMBER_PREFIX = FEDERATION_PREFIX + "-member"
MEMBERS_PREFIX = FEDERATION_PREFIX + "-members"
ENTRY_PREFIX = FEDERATION_PREFIX + "-entry"
ENTRIES_PREFIX = FEDERATION_PREFIX + "-entries"
MANIFEST_PREFIX = FEDERATION_PREFIX + "-manifest"
SUMMARY_PREFIX = FEDERATION_PREFIX + "-summary"
DEFAULT_FEDERATION_ID = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation"
FILES = ("manifest.json", "federation.json", "members.json", "entries.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
MANIFEST_ARTIFACT_FILES = ("members.json", "entries.json", "summary.json")
MAX_MEMBERS = 64
MAX_ENTRIES = MAX_MEMBERS * registry_model.MAX_ENTRIES
MAX_FEDERATION_BYTES = 32 * 1024 * 1024
STATES = ("empty", "ready", "blocked", "mixed")
MEMBER_FIELDS = ("ordinal", "registry_id", "registry_address", "registry_version", "registry_boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "accepted", "content_address")
MEMBERS_FIELDS = ("members", "content_address")
ENTRY_FIELDS = ("ordinal", "member_ordinal", "registry_id", "registry_address", "runtime_id", "runtime_address", "execution_id", "execution_address", "execution_audit_address", "query_address", "query_audit_address", "state", "accepted", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("federation_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("federation_id", "member_count", "accepted_member_count", "ready_member_count", "empty_member_count", "blocked_member_count", "runtime_entry_count", "accepted_runtime_entry_count", "ready_runtime_entry_count", "blocked_runtime_entry_count", "state", "accepted", "content_address")
FEDERATION_FIELDS = ("federation_id", "version", "boundary", "member_count", "accepted_member_count", "ready_member_count", "empty_member_count", "blocked_member_count", "runtime_entry_count", "accepted_runtime_entry_count", "ready_runtime_entry_count", "blocked_runtime_entry_count", "state", "accepted", "manifest", "summary", "members", "entries", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"{field} must be a string-keyed object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("path", "payload", "agent", "language")):
                return False
            if not _public(item):
                return False
    elif isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return not isinstance(value, (bytes, bytearray, Path))


class RecoveryExecutionRuntimeRegistryFederationMember:
    """A public, source-scoped summary of one admitted runtime registry."""

    FIELDS = MEMBER_FIELDS

    def __init__(self, ordinal: int, registry_id: str, registry_address: str, registry_version: str, registry_boundary: str, entry_count: int, accepted_count: int, ready_count: int, blocked_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry federation member ordinal", MAX_MEMBERS, lower=1)
        self.registry_id = _label(registry_id, "runtime registry federation member registry ID")
        self.registry_address = _address(registry_address, "runtime registry federation member registry address", registry_model.REGISTRY_PREFIX)
        self.registry_version = _text(registry_version, "runtime registry federation member registry version", 1024)
        self.registry_boundary = _text(registry_boundary, "runtime registry federation member registry boundary", 1024)
        self.entry_count = _count(entry_count, "runtime registry federation member entry count", registry_model.MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "runtime registry federation member accepted count", registry_model.MAX_ENTRIES)
        self.ready_count = _count(ready_count, "runtime registry federation member ready count", registry_model.MAX_ENTRIES)
        self.blocked_count = _count(blocked_count, "runtime registry federation member blocked count", registry_model.MAX_ENTRIES)
        if state not in registry_model.STATES:
            raise ValidationError("runtime registry federation member state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry federation member acceptance")
        self.content_address = _address(content_address, "runtime registry federation member address", MEMBER_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.registry_version != registry_model.VERSION or self.registry_boundary != registry_model.BOUNDARY:
            raise ValidationError("runtime registry federation member source format is unsupported")
        if self.accepted_count + self.blocked_count != self.entry_count or self.ready_count + self.blocked_count != self.entry_count:
            raise ValidationError("runtime registry federation member counts do not conserve")
        expected_state = "empty" if self.entry_count == 0 else "blocked" if self.blocked_count else "ready"
        if self.state != expected_state or self.accepted != (self.blocked_count == 0):
            raise ValidationError("runtime registry federation member state does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry federation member crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_member(self) != self.content_address:
            raise ValidationError("runtime registry federation member address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationMember":
        value = _mapping(value, "runtime registry federation member")
        _strict(value, set(cls.FIELDS), "runtime registry federation member")
        return cls(*(value[field] for field in cls.FIELDS))


def address_member(value: RecoveryExecutionRuntimeRegistryFederationMember) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationMember):
        raise ValidationError("runtime registry federation member address requires a typed member")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


def member_from_registry(value: registry_model.RecoveryExecutionRuntimeRegistry, ordinal: int) -> RecoveryExecutionRuntimeRegistryFederationMember:
    if not isinstance(value, registry_model.RecoveryExecutionRuntimeRegistry):
        raise ValidationError("runtime registry federation member requires a typed registry")
    return RecoveryExecutionRuntimeRegistryFederationMember(ordinal, value.registry_id, value.content_address, value.version, value.boundary, value.entry_count, value.accepted_count, value.ready_count, value.blocked_count, value.state, value.accepted, MEMBER_PREFIX + ":pending")


class RecoveryExecutionRuntimeRegistryFederationMembers:
    """The addressed, ordered member collection."""

    FIELDS = MEMBERS_FIELDS

    def __init__(self, members: Sequence[RecoveryExecutionRuntimeRegistryFederationMember | Mapping[str, Any]], content_address: str) -> None:
        self.members = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationMember) else RecoveryExecutionRuntimeRegistryFederationMember.from_mapping(item) for item in _sequence(members, "runtime registry federation members", MAX_MEMBERS))
        self.content_address = _address(content_address, "runtime registry federation members address", MEMBERS_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.members) != tuple(range(1, len(self.members) + 1)):
            raise ValidationError("runtime registry federation members are not contiguous")
        if len({(item.registry_id, item.registry_address) for item in self.members}) != len(self.members):
            raise ValidationError("runtime registry federation member identities are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry federation members cross the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_members(self.members) != self.content_address:
            raise ValidationError("runtime registry federation members address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"members": [item.to_dict() for item in self.members], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationMembers":
        value = _mapping(value, "runtime registry federation members")
        _strict(value, set(cls.FIELDS), "runtime registry federation members")
        return cls(value["members"], value["content_address"])


def address_members(value: Sequence[RecoveryExecutionRuntimeRegistryFederationMember]) -> str:
    return content_hash([item.to_dict() for item in value], prefix=MEMBERS_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationEntry:
    """A flattened runtime receipt retaining its source registry identity."""

    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, member_ordinal: int, registry_id: str, registry_address: str, runtime_id: str, runtime_address: str, execution_id: str, execution_address: str, execution_audit_address: str, query_address: str, query_audit_address: str, state: str, accepted: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry federation entry ordinal", MAX_ENTRIES, lower=1)
        self.member_ordinal = _count(member_ordinal, "runtime registry federation entry member ordinal", MAX_MEMBERS, lower=1)
        self.registry_id = _label(registry_id, "runtime registry federation entry registry ID")
        self.registry_address = _address(registry_address, "runtime registry federation entry registry address", registry_model.REGISTRY_PREFIX)
        self.runtime_id = _label(runtime_id, "runtime registry federation entry runtime ID")
        self.runtime_address = _address(runtime_address, "runtime registry federation entry runtime address", registry_model.runtime_model.RUNTIME_PREFIX)
        self.execution_id = _label(execution_id, "runtime registry federation entry execution ID")
        self.execution_address = _address(execution_address, "runtime registry federation entry execution address")
        self.execution_audit_address = _address(execution_audit_address, "runtime registry federation entry execution audit address")
        self.query_address = _address(query_address, "runtime registry federation entry query address")
        self.query_audit_address = _address(query_audit_address, "runtime registry federation entry query audit address")
        if state not in registry_model.runtime_model.STATES:
            raise ValidationError("runtime registry federation entry state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry federation entry acceptance")
        self.content_address = _address(content_address, "runtime registry federation entry address", ENTRY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.accepted != (self.state == "ready"):
            raise ValidationError("runtime registry federation entry acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry federation entry crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("runtime registry federation entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationEntry":
        value = _mapping(value, "runtime registry federation entry")
        _strict(value, set(cls.FIELDS), "runtime registry federation entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RecoveryExecutionRuntimeRegistryFederationEntry) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationEntry):
        raise ValidationError("runtime registry federation entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def entries_from_registry(value: registry_model.RecoveryExecutionRuntimeRegistry, member_ordinal: int, ordinal: int) -> tuple[RecoveryExecutionRuntimeRegistryFederationEntry, ...]:
    if not isinstance(value, registry_model.RecoveryExecutionRuntimeRegistry):
        raise ValidationError("runtime registry federation entries require a typed registry")
    result: list[RecoveryExecutionRuntimeRegistryFederationEntry] = []
    for item in value.entries:
        result.append(RecoveryExecutionRuntimeRegistryFederationEntry(ordinal, member_ordinal, value.registry_id, value.content_address, item.runtime_id, item.runtime_address, item.execution_id, item.execution_address, item.execution_audit_address, item.query_address, item.query_audit_address, item.state, item.accepted, ENTRY_PREFIX + ":pending"))
        ordinal += 1
    return tuple(result)


class RecoveryExecutionRuntimeRegistryFederationEntries:
    """The addressed, ordered flattened runtime collection."""

    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[RecoveryExecutionRuntimeRegistryFederationEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationEntry) else RecoveryExecutionRuntimeRegistryFederationEntry.from_mapping(item) for item in _sequence(entries, "runtime registry federation entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "runtime registry federation entries address", ENTRIES_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("runtime registry federation entries are not contiguous")
        identities = {(item.registry_id, item.registry_address, item.runtime_id, item.runtime_address) for item in self.entries}
        if len(identities) != len(self.entries):
            raise ValidationError("runtime registry federation entry identities are not unique")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry federation entries cross the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("runtime registry federation entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationEntries":
        value = _mapping(value, "runtime registry federation entries")
        _strict(value, set(cls.FIELDS), "runtime registry federation entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[RecoveryExecutionRuntimeRegistryFederationEntry]) -> str:
    return content_hash([item.to_dict() for item in value], prefix=ENTRIES_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationManifest:
    """Manifest linking the three independently addressed federation artifacts."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, federation_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.federation_id = _label(federation_id, "runtime registry federation manifest ID")
        self.version = _text(version, "runtime registry federation manifest version", 1024)
        self.boundary = _text(boundary, "runtime registry federation manifest boundary", 1024)
        self.files = tuple(_label(item, "runtime registry federation manifest file") for item in _sequence(files, "runtime registry federation manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "runtime registry federation manifest artifact address") for item in _sequence(artifact_addresses, "runtime registry federation manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "runtime registry federation manifest address", MANIFEST_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("runtime registry federation manifest is invalid")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("runtime registry federation manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationManifest":
        value = _mapping(value, "runtime registry federation manifest")
        _strict(value, set(cls.FIELDS), "runtime registry federation manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: RecoveryExecutionRuntimeRegistryFederationManifest) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationManifest):
        raise ValidationError("runtime registry federation manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class RecoveryExecutionRuntimeRegistryFederationSummary:
    """Conserved member and flattened-runtime counts."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, federation_id: str, member_count: int, accepted_member_count: int, ready_member_count: int, empty_member_count: int, blocked_member_count: int, runtime_entry_count: int, accepted_runtime_entry_count: int, ready_runtime_entry_count: int, blocked_runtime_entry_count: int, state: str, accepted: bool, content_address: str) -> None:
        self.federation_id = _label(federation_id, "runtime registry federation summary ID")
        self.member_count = _count(member_count, "runtime registry federation summary member count", MAX_MEMBERS)
        self.accepted_member_count = _count(accepted_member_count, "runtime registry federation summary accepted member count", MAX_MEMBERS)
        self.ready_member_count = _count(ready_member_count, "runtime registry federation summary ready member count", MAX_MEMBERS)
        self.empty_member_count = _count(empty_member_count, "runtime registry federation summary empty member count", MAX_MEMBERS)
        self.blocked_member_count = _count(blocked_member_count, "runtime registry federation summary blocked member count", MAX_MEMBERS)
        self.runtime_entry_count = _count(runtime_entry_count, "runtime registry federation summary runtime entry count", MAX_ENTRIES)
        self.accepted_runtime_entry_count = _count(accepted_runtime_entry_count, "runtime registry federation summary accepted runtime entry count", MAX_ENTRIES)
        self.ready_runtime_entry_count = _count(ready_runtime_entry_count, "runtime registry federation summary ready runtime entry count", MAX_ENTRIES)
        self.blocked_runtime_entry_count = _count(blocked_runtime_entry_count, "runtime registry federation summary blocked runtime entry count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry federation summary state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry federation summary acceptance")
        self.content_address = _address(content_address, "runtime registry federation summary address", SUMMARY_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_member_count + self.blocked_member_count != self.member_count or self.ready_member_count + self.empty_member_count + self.blocked_member_count != self.member_count:
            raise ValidationError("runtime registry federation summary member counts do not conserve")
        if self.accepted_runtime_entry_count + self.blocked_runtime_entry_count != self.runtime_entry_count or self.ready_runtime_entry_count + self.blocked_runtime_entry_count != self.runtime_entry_count:
            raise ValidationError("runtime registry federation summary runtime counts do not conserve")
        if self.member_count == 0:
            expected_state = "empty"
        elif self.blocked_member_count:
            expected_state = "blocked"
        elif self.ready_member_count == self.member_count:
            expected_state = "ready"
        else:
            expected_state = "mixed"
        if self.state != expected_state or self.accepted != (self.blocked_member_count == 0):
            raise ValidationError("runtime registry federation summary state does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry federation summary crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("runtime registry federation summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationSummary":
        value = _mapping(value, "runtime registry federation summary")
        _strict(value, set(cls.FIELDS), "runtime registry federation summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: RecoveryExecutionRuntimeRegistryFederationSummary) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationSummary):
        raise ValidationError("runtime registry federation summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


def _state(members: Sequence[RecoveryExecutionRuntimeRegistryFederationMember]) -> str:
    if not members:
        return "empty"
    if any(item.state == "blocked" for item in members):
        return "blocked"
    return "ready" if all(item.state == "ready" for item in members) else "mixed"


class RecoveryExecutionRuntimeRegistryFederation:
    """A deterministic federation over verified runtime registries."""

    FIELDS = FEDERATION_FIELDS

    def __init__(self, federation_id: str, version: str, boundary: str, member_count: int, accepted_member_count: int, ready_member_count: int, empty_member_count: int, blocked_member_count: int, runtime_entry_count: int, accepted_runtime_entry_count: int, ready_runtime_entry_count: int, blocked_runtime_entry_count: int, state: str, accepted: bool, manifest: RecoveryExecutionRuntimeRegistryFederationManifest | Mapping[str, Any], summary: RecoveryExecutionRuntimeRegistryFederationSummary | Mapping[str, Any], members: Sequence[RecoveryExecutionRuntimeRegistryFederationMember | Mapping[str, Any]], entries: Sequence[RecoveryExecutionRuntimeRegistryFederationEntry | Mapping[str, Any]], content_address: str) -> None:
        self.federation_id = _label(federation_id, "runtime registry federation ID")
        self.version = _text(version, "runtime registry federation version", 1024)
        self.boundary = _text(boundary, "runtime registry federation boundary", 1024)
        self.member_count = _count(member_count, "runtime registry federation member count", MAX_MEMBERS)
        self.accepted_member_count = _count(accepted_member_count, "runtime registry federation accepted member count", MAX_MEMBERS)
        self.ready_member_count = _count(ready_member_count, "runtime registry federation ready member count", MAX_MEMBERS)
        self.empty_member_count = _count(empty_member_count, "runtime registry federation empty member count", MAX_MEMBERS)
        self.blocked_member_count = _count(blocked_member_count, "runtime registry federation blocked member count", MAX_MEMBERS)
        self.runtime_entry_count = _count(runtime_entry_count, "runtime registry federation runtime entry count", MAX_ENTRIES)
        self.accepted_runtime_entry_count = _count(accepted_runtime_entry_count, "runtime registry federation accepted runtime entry count", MAX_ENTRIES)
        self.ready_runtime_entry_count = _count(ready_runtime_entry_count, "runtime registry federation ready runtime entry count", MAX_ENTRIES)
        self.blocked_runtime_entry_count = _count(blocked_runtime_entry_count, "runtime registry federation blocked runtime entry count", MAX_ENTRIES)
        if state not in STATES:
            raise ValidationError("runtime registry federation state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime registry federation acceptance")
        self.manifest = manifest if isinstance(manifest, RecoveryExecutionRuntimeRegistryFederationManifest) else RecoveryExecutionRuntimeRegistryFederationManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, RecoveryExecutionRuntimeRegistryFederationSummary) else RecoveryExecutionRuntimeRegistryFederationSummary.from_mapping(summary)
        self.members = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationMember) else RecoveryExecutionRuntimeRegistryFederationMember.from_mapping(item) for item in _sequence(members, "runtime registry federation members", MAX_MEMBERS))
        self.entries = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationEntry) else RecoveryExecutionRuntimeRegistryFederationEntry.from_mapping(item) for item in _sequence(entries, "runtime registry federation entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "runtime registry federation address", FEDERATION_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY or self.member_count != len(self.members) or self.runtime_entry_count != len(self.entries):
            raise ValidationError("runtime registry federation version or counts do not replay")
        if tuple(item.ordinal for item in self.members) != tuple(range(1, len(self.members) + 1)) or tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("runtime registry federation ordinals are not contiguous")
        if self.accepted_member_count != sum(item.accepted for item in self.members) or self.ready_member_count != sum(item.state == "ready" for item in self.members) or self.empty_member_count != sum(item.state == "empty" for item in self.members) or self.blocked_member_count != sum(item.state == "blocked" for item in self.members):
            raise ValidationError("runtime registry federation member counts do not replay")
        if self.accepted_runtime_entry_count != sum(item.accepted for item in self.entries) or self.ready_runtime_entry_count != sum(item.state == "ready" for item in self.entries) or self.blocked_runtime_entry_count != sum(item.state == "blocked" for item in self.entries):
            raise ValidationError("runtime registry federation runtime counts do not replay")
        if self.state != _state(self.members) or self.accepted != (self.blocked_member_count == 0):
            raise ValidationError("runtime registry federation state does not replay")
        if self.manifest.federation_id != self.federation_id or self.manifest.version != self.version or self.manifest.boundary != self.boundary or self.manifest.files != FILES or tuple(self.manifest.artifact_addresses) != (address_members(self.members), address_entries(self.entries), self.summary.content_address):
            raise ValidationError("runtime registry federation manifest linkage does not replay")
        expected_summary = {field: getattr(self, field) for field in SUMMARY_FIELDS if field != "content_address"} | {"content_address": self.summary.content_address}
        if self.summary.to_dict() != expected_summary:
            raise ValidationError("runtime registry federation summary linkage does not replay")
        if self.members and any(item.member_ordinal > len(self.members) for item in self.entries):
            raise ValidationError("runtime registry federation entry member linkage does not replay")
        if any((item.registry_id, item.registry_address) != (self.members[item.member_ordinal - 1].registry_id, self.members[item.member_ordinal - 1].registry_address) for item in self.entries):
            raise ValidationError("runtime registry federation entry source linkage does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry federation crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_federation(self) != self.content_address:
            raise ValidationError("runtime registry federation address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"federation_id": self.federation_id, "version": self.version, "boundary": self.boundary, "member_count": self.member_count, "accepted_member_count": self.accepted_member_count, "ready_member_count": self.ready_member_count, "empty_member_count": self.empty_member_count, "blocked_member_count": self.blocked_member_count, "runtime_entry_count": self.runtime_entry_count, "accepted_runtime_entry_count": self.accepted_runtime_entry_count, "ready_runtime_entry_count": self.ready_runtime_entry_count, "blocked_runtime_entry_count": self.blocked_runtime_entry_count, "state": self.state, "accepted": self.accepted, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "members": [item.to_dict() for item in self.members], "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ("federation_id", "version", "boundary", "member_count", "accepted_member_count", "ready_member_count", "empty_member_count", "blocked_member_count", "runtime_entry_count", "accepted_runtime_entry_count", "ready_runtime_entry_count", "blocked_runtime_entry_count", "state", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederation":
        value = _mapping(value, "runtime registry federation")
        _strict(value, set(cls.FIELDS), "runtime registry federation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_federation(value: RecoveryExecutionRuntimeRegistryFederation) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederation):
        raise ValidationError("runtime registry federation address requires a typed federation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FEDERATION_PREFIX)


def build_federation(registries: Sequence[registry_model.RecoveryExecutionRuntimeRegistry], *, federation_id: str = DEFAULT_FEDERATION_ID) -> RecoveryExecutionRuntimeRegistryFederation:
    registries = tuple(registries)
    if len(registries) > MAX_MEMBERS:
        raise ValidationError("runtime registry federation exceeds its member bound")
    if any(not isinstance(item, registry_model.RecoveryExecutionRuntimeRegistry) for item in registries):
        raise ValidationError("runtime registry federation requires typed registries")
    ordered = tuple(sorted(registries, key=lambda item: (item.registry_id, item.content_address)))
    if len({(item.registry_id, item.content_address) for item in ordered}) != len(ordered):
        raise ValidationError("runtime registry federation rejects duplicate registry identities")
    members = tuple(member_from_registry(item, index) for index, item in enumerate(ordered, 1))
    members = tuple(RecoveryExecutionRuntimeRegistryFederationMember(item.ordinal, item.registry_id, item.registry_address, item.registry_version, item.registry_boundary, item.entry_count, item.accepted_count, item.ready_count, item.blocked_count, item.state, item.accepted, address_member(item)) for item in members)
    members_component = RecoveryExecutionRuntimeRegistryFederationMembers(members, address_members(members))
    entries_list: list[RecoveryExecutionRuntimeRegistryFederationEntry] = []
    for member, registry in zip(members, ordered):
        entries_list.extend(entries_from_registry(registry, member.ordinal, len(entries_list) + 1))
    entries = tuple(RecoveryExecutionRuntimeRegistryFederationEntry(item.ordinal, item.member_ordinal, item.registry_id, item.registry_address, item.runtime_id, item.runtime_address, item.execution_id, item.execution_address, item.execution_audit_address, item.query_address, item.query_audit_address, item.state, item.accepted, address_entry(item)) for item in entries_list)
    entries_component = RecoveryExecutionRuntimeRegistryFederationEntries(entries, address_entries(entries))
    state = _state(members)
    summary_values = (federation_id, len(members), sum(item.accepted for item in members), sum(item.state == "ready" for item in members), sum(item.state == "empty" for item in members), sum(item.state == "blocked" for item in members), len(entries), sum(item.accepted for item in entries), sum(item.state == "ready" for item in entries), sum(item.state == "blocked" for item in entries), state, sum(item.state == "blocked" for item in members) == 0)
    summary = RecoveryExecutionRuntimeRegistryFederationSummary(*summary_values, SUMMARY_PREFIX + ":pending")
    summary = RecoveryExecutionRuntimeRegistryFederationSummary(*summary_values, address_summary(summary))
    manifest_values = (federation_id, VERSION, BOUNDARY, FILES, (members_component.content_address, entries_component.content_address, summary.content_address))
    manifest = RecoveryExecutionRuntimeRegistryFederationManifest(*manifest_values, MANIFEST_PREFIX + ":pending")
    manifest = RecoveryExecutionRuntimeRegistryFederationManifest(*manifest_values, address_manifest(manifest))
    federation_values = (federation_id, VERSION, BOUNDARY, summary.member_count, summary.accepted_member_count, summary.ready_member_count, summary.empty_member_count, summary.blocked_member_count, summary.runtime_entry_count, summary.accepted_runtime_entry_count, summary.ready_runtime_entry_count, summary.blocked_runtime_entry_count, summary.state, summary.accepted, manifest, summary, members, entries)
    federation = RecoveryExecutionRuntimeRegistryFederation(*federation_values, FEDERATION_PREFIX + ":pending")
    return RecoveryExecutionRuntimeRegistryFederation(*federation_values, address_federation(federation))


def verify_federation(value: RecoveryExecutionRuntimeRegistryFederation) -> RecoveryExecutionRuntimeRegistryFederation:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederation):
        raise ValidationError("runtime registry federation verification requires a typed federation")
    return RecoveryExecutionRuntimeRegistryFederation.from_mapping(value.to_dict())


def federation_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederation:
    return RecoveryExecutionRuntimeRegistryFederation.from_mapping(value)


def federation_json(value: RecoveryExecutionRuntimeRegistryFederation) -> str:
    return canonical_json(verify_federation(value).to_dict())


def federation_csv(value: RecoveryExecutionRuntimeRegistryFederation) -> str:
    value = verify_federation(value)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("field", "value"))
    for field in ("federation_id", "version", "boundary", "member_count", "accepted_member_count", "ready_member_count", "empty_member_count", "blocked_member_count", "runtime_entry_count", "accepted_runtime_entry_count", "ready_runtime_entry_count", "blocked_runtime_entry_count", "state", "accepted", "content_address"):
        writer.writerow((field, json.dumps(getattr(value, field), ensure_ascii=False, sort_keys=True)))
    return output.getvalue()


def render_federation_markdown(value: RecoveryExecutionRuntimeRegistryFederation) -> str:
    value = verify_federation(value)
    lines = ["# Recovery Execution Runtime Registry Federation", "", f"- Federation: `{value.federation_id}`", f"- State: `{value.state}`", f"- Members: `{value.member_count}`", f"- Runtime entries: `{value.runtime_entry_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "## Members", "", "| ordinal | registry | state | accepted | entries | address |", "| ---: | --- | --- | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.registry_id}` | `{item.state}` | `{item.accepted}` | {item.entry_count} | `{item.registry_address}` |" for item in value.members)
    lines.extend(("", "## Runtime entries", "", "| ordinal | registry | runtime | state | accepted | address |", "| ---: | --- | --- | --- | --- | --- |"))
    lines.extend(f"| {item.ordinal} | `{item.registry_id}` | `{item.runtime_id}` | `{item.state}` | `{item.accepted}` | `{item.runtime_address}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def members_json(value: RecoveryExecutionRuntimeRegistryFederationMembers) -> str:
    return canonical_json(RecoveryExecutionRuntimeRegistryFederationMembers.from_mapping(value.to_dict()).to_dict())


def entries_json(value: RecoveryExecutionRuntimeRegistryFederationEntries) -> str:
    return canonical_json(RecoveryExecutionRuntimeRegistryFederationEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: RecoveryExecutionRuntimeRegistryFederationSummary) -> str:
    return canonical_json(RecoveryExecutionRuntimeRegistryFederationSummary.from_mapping(value.to_dict()).to_dict())


def manifest_json(value: RecoveryExecutionRuntimeRegistryFederationManifest) -> str:
    return canonical_json(RecoveryExecutionRuntimeRegistryFederationManifest.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_federation(value: RecoveryExecutionRuntimeRegistryFederation, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_federation(value)
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("runtime registry federation destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".recovery-execution-runtime-registry-federation-", dir=str(parent)))
    try:
        members = RecoveryExecutionRuntimeRegistryFederationMembers(value.members, address_members(value.members))
        entries = RecoveryExecutionRuntimeRegistryFederationEntries(value.entries, address_entries(value.entries))
        documents = {"manifest.json": value.manifest.to_dict(), "federation.json": value.to_dict(), "members.json": members.to_dict(), "entries.json": entries.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("runtime registry federation destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("runtime registry federation artifact is not valid JSON") from error
    return _mapping(value, "runtime registry federation artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("runtime registry federation artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("runtime registry federation artifact is not canonical")


def load_federation(destination: str | Path) -> RecoveryExecutionRuntimeRegistryFederation:
    destination = Path(destination)
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("runtime registry federation source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)):
        raise ValidationError("runtime registry federation directory must contain the exact file set")
    if any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("runtime registry federation directory may contain only regular files")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        _read_canonical(destination / name, document)
        if len(canonical_json(document).encode("utf-8")) > MAX_FEDERATION_BYTES:
            raise ValidationError("runtime registry federation artifact exceeds its size bound")
    value = federation_from_mapping(documents["federation.json"])
    manifest = RecoveryExecutionRuntimeRegistryFederationManifest.from_mapping(documents["manifest.json"])
    members = RecoveryExecutionRuntimeRegistryFederationMembers.from_mapping(documents["members.json"])
    entries = RecoveryExecutionRuntimeRegistryFederationEntries.from_mapping(documents["entries.json"])
    summary = RecoveryExecutionRuntimeRegistryFederationSummary.from_mapping(documents["summary.json"])
    if manifest.to_dict() != value.manifest.to_dict() or members.to_dict() != RecoveryExecutionRuntimeRegistryFederationMembers(value.members, address_members(value.members)).to_dict() or entries.to_dict() != RecoveryExecutionRuntimeRegistryFederationEntries(value.entries, address_entries(value.entries)).to_dict() or summary.to_dict() != value.summary.to_dict():
        raise ValidationError("runtime registry federation component documents do not replay federation.json")
    if tuple(manifest.artifact_addresses) != (members.content_address, entries.content_address, summary.content_address):
        raise ValidationError("runtime registry federation manifest artifact addresses do not replay")
    return value


def member_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationMember", "type": "object", "additionalProperties": False, "required": list(MEMBER_FIELDS), "properties": {field: {"type": ["integer", "string", "boolean"]} for field in MEMBER_FIELDS}}


def members_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationMembers", "type": "object", "additionalProperties": False, "required": list(MEMBERS_FIELDS), "properties": {"members": {"type": "array", "maxItems": MAX_MEMBERS, "items": member_schema()}, "content_address": {"type": "string"}}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationEntry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": ["integer", "string", "boolean"]} for field in ENTRY_FIELDS}}


def entries_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationEntries", "type": "object", "additionalProperties": False, "required": list(ENTRIES_FIELDS), "properties": {"entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"federation_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederationSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"federation_id": {"type": "string"}, "member_count": {"type": "integer", "minimum": 0}, "accepted_member_count": {"type": "integer", "minimum": 0}, "ready_member_count": {"type": "integer", "minimum": 0}, "empty_member_count": {"type": "integer", "minimum": 0}, "blocked_member_count": {"type": "integer", "minimum": 0}, "runtime_entry_count": {"type": "integer", "minimum": 0}, "accepted_runtime_entry_count": {"type": "integer", "minimum": 0}, "ready_runtime_entry_count": {"type": "integer", "minimum": 0}, "blocked_runtime_entry_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def federation_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {field: {"type": ["integer", "string", "boolean"]} for field in FEDERATION_FIELDS if field not in {"manifest", "summary", "members", "entries"}}
    properties.update({"manifest": manifest_schema(), "summary": summary_schema(), "members": {"type": "array", "maxItems": MAX_MEMBERS, "items": member_schema()}, "entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RecoveryExecutionRuntimeRegistryFederation", "type": "object", "additionalProperties": False, "required": list(FEDERATION_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "federation_prefix": FEDERATION_PREFIX, "member_prefix": MEMBER_PREFIX, "entry_prefix": ENTRY_PREFIX, "files": list(FILES), "states": list(STATES), "max_members": MAX_MEMBERS, "max_entries": MAX_ENTRIES, "operations": ["build_federation", "verify_federation", "federation_from_mapping", "persist_federation", "load_federation", "federation_json", "federation_csv", "render_federation_markdown"], "projections": ["source-scoped members", "flattened runtime entries", "state and count conservation"], "privacy": {"values": False, "source_paths": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "FEDERATION_PREFIX", "MEMBER_PREFIX", "MEMBERS_PREFIX", "ENTRY_PREFIX", "ENTRIES_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_FEDERATION_ID", "FILES", "ARTIFACT_FILES", "MAX_MEMBERS", "MAX_ENTRIES", "STATES", "MEMBER_FIELDS", "MEMBERS_FIELDS", "ENTRY_FIELDS", "ENTRIES_FIELDS", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "FEDERATION_FIELDS", "RecoveryExecutionRuntimeRegistryFederationMember", "RecoveryExecutionRuntimeRegistryFederationMembers", "RecoveryExecutionRuntimeRegistryFederationEntry", "RecoveryExecutionRuntimeRegistryFederationEntries", "RecoveryExecutionRuntimeRegistryFederationManifest", "RecoveryExecutionRuntimeRegistryFederationSummary", "RecoveryExecutionRuntimeRegistryFederation", "address_member", "address_members", "address_entry", "address_entries", "address_manifest", "address_summary", "address_federation", "member_from_registry", "entries_from_registry", "build_federation", "verify_federation", "federation_from_mapping", "federation_json", "federation_csv", "render_federation_markdown", "members_json", "entries_json", "summary_json", "manifest_json", "persist_federation", "load_federation", "member_schema", "members_schema", "entry_schema", "entries_schema", "manifest_schema", "summary_schema", "federation_schema", "capabilities"]

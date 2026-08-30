"""Deterministic admission registry for policy-review packages.

The registry retains only public package metadata and addressed package
receipts. It can aggregate verified handoffs from several downloaded-data
runs without importing source paths or source records into the registry
boundary. Empty, ready, review, and blocked states remain explicit.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry"
REGISTRY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
ENTRIES_PREFIX = REGISTRY_PREFIX + "-entries"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"
SUMMARY_PREFIX = REGISTRY_PREFIX + "-summary"
DEFAULT_REGISTRY_ID = REGISTRY_PREFIX
MANIFEST_ARTIFACT_FILES = ("entries.json", "summary.json")
FILES = ("manifest.json", "registry.json", "entries.json", "summary.json")
STATES = ("empty", "ready", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
ENTRY_FIELDS = ("ordinal", "package_id", "package_address", "package_version", "policy_id", "evaluation_id", "runtime_address", "policy_audit_address", "runtime_audit_address", "direction", "state", "decision", "accepted", "release_ready", "content_address")
ENTRIES_FIELDS = ("entries", "content_address")
MANIFEST_FIELDS = ("registry_id", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = ("registry_id", "entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "accepted", "release_ready", "content_address")
REGISTRY_FIELDS = ("registry_id", "version", "boundary", "entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "accepted", "release_ready", "manifest", "summary", "entries", "content_address")
MAX_ENTRIES = 256


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if any(char.isspace() for char in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _label(value, field)
    if ":" not in value or (prefix and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be an addressed public receipt")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded count")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry:
    FIELDS = ENTRY_FIELDS

    def __init__(self, ordinal: int, package_id: str, package_address: str, package_version: str, policy_id: str, evaluation_id: str, runtime_address: str, policy_audit_address: str, runtime_audit_address: str, direction: str, state: str, decision: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy package registry entry ordinal", MAX_ENTRIES, positive=True)
        self.package_id = _label(package_id, "policy package registry package ID")
        self.package_address = _address(package_address, "policy package registry package address", package_model.PACKAGE_PREFIX)
        self.package_version = _text(package_version, "policy package registry package version", 512)
        self.policy_id = _label(policy_id, "policy package registry policy ID")
        self.evaluation_id = _label(evaluation_id, "policy package registry evaluation ID")
        self.runtime_address = _address(runtime_address, "policy package registry runtime address")
        self.policy_audit_address = _address(policy_audit_address, "policy package registry policy audit address")
        self.runtime_audit_address = _address(runtime_audit_address, "policy package registry runtime audit address")
        self.direction = _label(direction, "policy package registry direction")
        self.state = _label(state, "policy package registry entry state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("policy package registry entry state is unsupported")
        self.decision = _label(decision, "policy package registry decision")
        if self.decision not in DECISIONS:
            raise ValidationError("policy package registry decision is unsupported")
        self.accepted = _bool(accepted, "policy package registry entry acceptance")
        self.release_ready = _bool(release_ready, "policy package registry entry release readiness")
        self.content_address = _address(content_address, "policy package registry entry address", ENTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("policy package registry entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("policy package registry entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry:
        value = _mapping(value, "policy package registry entry")
        _strict(value, set(cls.FIELDS), "policy package registry entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry):
        raise ValidationError("policy package registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def entry_from_package(value: package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry:
    if not isinstance(value, package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage):
        raise ValidationError("policy package registry entries require typed packages")
    body = {"ordinal": ordinal, "package_id": value.package_id, "package_address": value.content_address, "package_version": value.version, "policy_id": value.policy_id, "evaluation_id": value.evaluation_id, "runtime_address": value.runtime_address, "policy_audit_address": value.policy_audit_address, "runtime_audit_address": value.runtime_audit_address, "direction": value.direction, "state": value.state, "decision": value.decision, "accepted": value.accepted, "release_ready": value.release_ready, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry(**(body | {"content_address": address_entry(provisional)}))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries:
    FIELDS = ENTRIES_FIELDS

    def __init__(self, entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry.from_mapping(item) for item in _sequence(entries, "policy package registry entries", MAX_ENTRIES))
        self.content_address = _address(content_address, "policy package registry entries address", ENTRIES_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("policy package registry entries cross the public boundary")
        if not self.content_address.endswith(":pending") and address_entries(self.entries) != self.content_address:
            raise ValidationError("policy package registry entries address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries:
        value = _mapping(value, "policy package registry entries")
        _strict(value, set(cls.FIELDS), "policy package registry entries")
        return cls(value["entries"], value["content_address"])


def address_entries(value: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry]) -> str:
    typed = tuple(value)
    if any(not isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry) for item in typed):
        raise ValidationError("policy package registry entries address requires typed entries")
    return content_hash({"entries": [item.to_dict() for item in typed]}, prefix=ENTRIES_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest:
    FIELDS = MANIFEST_FIELDS

    def __init__(self, registry_id: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.registry_id = _label(registry_id, "policy package registry manifest registry ID")
        self.files = tuple(_label(item, "policy package registry manifest file") for item in _sequence(files, "policy package registry manifest files", len(FILES)))
        self.artifact_addresses = tuple(_address(item, "policy package registry manifest artifact address") for item in _sequence(artifact_addresses, "policy package registry manifest artifact addresses", len(MANIFEST_ARTIFACT_FILES)))
        self.content_address = _address(content_address, "policy package registry manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or len(self.artifact_addresses) != len(MANIFEST_ARTIFACT_FILES) or not _public(self.to_dict()):
            raise ValidationError("policy package registry manifest does not close the public file boundary")
        if not self.content_address.endswith(":pending") and address_manifest(self) != self.content_address:
            raise ValidationError("policy package registry manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest:
        value = _mapping(value, "policy package registry manifest")
        _strict(value, set(cls.FIELDS), "policy package registry manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest):
        raise ValidationError("policy package registry manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MANIFEST_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary:
    FIELDS = SUMMARY_FIELDS

    def __init__(self, registry_id: str, entry_count: int, accepted_count: int, release_ready_count: int, promote_count: int, hold_count: int, block_count: int, state: str, accepted: bool, release_ready: bool, content_address: str) -> None:
        self.registry_id = _label(registry_id, "policy package registry summary registry ID")
        self.entry_count = _count(entry_count, "policy package registry summary entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "policy package registry summary accepted count", MAX_ENTRIES)
        self.release_ready_count = _count(release_ready_count, "policy package registry summary release-ready count", MAX_ENTRIES)
        self.promote_count = _count(promote_count, "policy package registry summary promote count", MAX_ENTRIES)
        self.hold_count = _count(hold_count, "policy package registry summary hold count", MAX_ENTRIES)
        self.block_count = _count(block_count, "policy package registry summary block count", MAX_ENTRIES)
        self.state = _label(state, "policy package registry summary state")
        if self.state not in STATES:
            raise ValidationError("policy package registry summary state is unsupported")
        self.accepted = _bool(accepted, "policy package registry summary acceptance")
        self.release_ready = _bool(release_ready, "policy package registry summary release readiness")
        self.content_address = _address(content_address, "policy package registry summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count > self.entry_count or self.release_ready_count > self.entry_count or self.promote_count + self.hold_count + self.block_count != self.entry_count or not _public(self.to_dict()):
            raise ValidationError("policy package registry summary counts are inconsistent")
        if not self.content_address.endswith(":pending") and address_summary(self) != self.content_address:
            raise ValidationError("policy package registry summary address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary:
        value = _mapping(value, "policy package registry summary")
        _strict(value, set(cls.FIELDS), "policy package registry summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary):
        raise ValidationError("policy package registry summary address requires a typed summary")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SUMMARY_PREFIX)


def _state(entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry]) -> str:
    if not entries:
        return "empty"
    if any(not item.accepted or item.decision == "block" for item in entries):
        return "blocked"
    if all(item.release_ready for item in entries):
        return "ready"
    return "review"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry:
    FIELDS = REGISTRY_FIELDS

    def __init__(self, registry_id: str, version: str, boundary: str, entry_count: int, accepted_count: int, release_ready_count: int, promote_count: int, hold_count: int, block_count: int, state: str, accepted: bool, release_ready: bool, manifest: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest | Mapping[str, Any], summary: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary | Mapping[str, Any], entries: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry | Mapping[str, Any]], content_address: str) -> None:
        self.registry_id = _label(registry_id, "policy package registry ID")
        self.version = _text(version, "policy package registry version", 512)
        self.boundary = _text(boundary, "policy package registry boundary", 512)
        self.entries = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry.from_mapping(item) for item in _sequence(entries, "policy package registry entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "policy package registry entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "policy package registry accepted count", MAX_ENTRIES)
        self.release_ready_count = _count(release_ready_count, "policy package registry release-ready count", MAX_ENTRIES)
        self.promote_count = _count(promote_count, "policy package registry promote count", MAX_ENTRIES)
        self.hold_count = _count(hold_count, "policy package registry hold count", MAX_ENTRIES)
        self.block_count = _count(block_count, "policy package registry block count", MAX_ENTRIES)
        self.state = _label(state, "policy package registry state")
        if self.state not in STATES:
            raise ValidationError("policy package registry state is unsupported")
        self.accepted = _bool(accepted, "policy package registry acceptance")
        self.release_ready = _bool(release_ready, "policy package registry release readiness")
        self.manifest = manifest if isinstance(manifest, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest.from_mapping(manifest)
        self.summary = summary if isinstance(summary, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary.from_mapping(summary)
        self.content_address = _address(content_address, "policy package registry address", REGISTRY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        keys = tuple((item.package_id, item.package_address) for item in self.entries)
        expected_accepted = sum(item.accepted for item in self.entries)
        expected_ready = sum(item.release_ready for item in self.entries)
        expected_promote = sum(item.decision == "promote" for item in self.entries)
        expected_hold = sum(item.decision == "hold" for item in self.entries)
        expected_block = sum(item.decision == "block" for item in self.entries)
        expected_state = _state(self.entries)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("policy package registry version or boundary is not current")
        if self.entry_count != len(self.entries) or len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
            raise ValidationError("policy package registry entry identities are not unique or ordered")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("policy package registry entry ordinals do not replay")
        if (self.accepted_count, self.release_ready_count, self.promote_count, self.hold_count, self.block_count, self.state) != (expected_accepted, expected_ready, expected_promote, expected_hold, expected_block, expected_state):
            raise ValidationError("policy package registry counts or state do not replay")
        if self.accepted != (not self.entries or expected_accepted == self.entry_count) or self.release_ready != (bool(self.entries) and expected_ready == self.entry_count):
            raise ValidationError("policy package registry acceptance or readiness does not replay")
        if (self.manifest.registry_id, self.manifest.files, tuple(self.manifest.artifact_addresses)) != (self.registry_id, FILES, (address_entries(self.entries), self.summary.content_address)):
            raise ValidationError("policy package registry manifest does not replay")
        if (self.summary.registry_id, self.summary.entry_count, self.summary.accepted_count, self.summary.release_ready_count, self.summary.promote_count, self.summary.hold_count, self.summary.block_count, self.summary.state, self.summary.accepted, self.summary.release_ready) != (self.registry_id, self.entry_count, self.accepted_count, self.release_ready_count, self.promote_count, self.hold_count, self.block_count, self.state, self.accepted, self.release_ready):
            raise ValidationError("policy package registry summary does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("policy package registry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_registry(self) != self.content_address:
            raise ValidationError("policy package registry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "release_ready_count": self.release_ready_count, "promote_count": self.promote_count, "hold_count": self.hold_count, "block_count": self.block_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "manifest": self.manifest.to_dict(), "summary": self.summary.to_dict(), "entries": [item.to_dict() for item in self.entries], "content_address": self.content_address}

    def compact(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"manifest", "summary", "entries"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry:
        value = _mapping(value, "policy package registry")
        _strict(value, set(cls.FIELDS), "policy package registry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_registry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry):
        raise ValidationError("policy package registry address requires a typed registry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_PREFIX)


def build_registry(packages: Sequence[package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage], *, registry_id: str = DEFAULT_REGISTRY_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry:
    packages = tuple(_sequence(packages, "policy package registry packages", MAX_ENTRIES))
    if any(not isinstance(item, package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage) for item in packages):
        raise ValidationError("policy package registry requires typed packages")
    entries = tuple(entry_from_package(item, ordinal) for ordinal, item in enumerate(sorted(packages, key=lambda item: (item.package_id, item.content_address)), 1))
    counts = {"entry_count": len(entries), "accepted_count": sum(item.accepted for item in entries), "release_ready_count": sum(item.release_ready for item in entries), "promote_count": sum(item.decision == "promote" for item in entries), "hold_count": sum(item.decision == "hold" for item in entries), "block_count": sum(item.decision == "block" for item in entries)}
    state = _state(entries)
    accepted = not entries or counts["accepted_count"] == len(entries)
    release_ready = bool(entries) and counts["release_ready_count"] == len(entries)
    summary_body = {"registry_id": registry_id, **counts, "state": state, "accepted": accepted, "release_ready": release_ready, "content_address": SUMMARY_PREFIX + ":pending"}
    summary_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary(**summary_body)
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary(**(summary_body | {"content_address": address_summary(summary_provisional)}))
    entries_address = address_entries(entries)
    manifest_body = {"registry_id": registry_id, "files": FILES, "artifact_addresses": (entries_address, summary.content_address), "content_address": MANIFEST_PREFIX + ":pending"}
    manifest_provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest(**manifest_body)
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest(**(manifest_body | {"content_address": address_manifest(manifest_provisional)}))
    body = {"registry_id": registry_id, "version": VERSION, "boundary": BOUNDARY, **counts, "state": state, "accepted": accepted, "release_ready": release_ready, "manifest": manifest, "summary": summary, "entries": entries}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry(**body, content_address=REGISTRY_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry(**body, content_address=address_registry(provisional))


def registry_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry.from_mapping(value)


def registry_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry) -> str:
    return canonical_json(registry_from_mapping(value.to_dict()).to_dict())


def registry_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry) -> str:
    value = registry_from_mapping(value.to_dict())
    rows = ((field, value.to_dict()[field]) for field in ("registry_id", "version", "boundary", "entry_count", "accepted_count", "release_ready_count", "promote_count", "hold_count", "block_count", "state", "accepted", "release_ready", "content_address"))
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("field", "value"))
    for key, item in rows:
        writer.writerow((key, json.dumps(item, ensure_ascii=False, sort_keys=True)))
    return output.getvalue()


def render_registry_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry) -> str:
    value = registry_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry", "", f"- Registry: `{value.registry_id}`", f"- State: `{value.state}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}/{value.entry_count}`", f"- Release ready: `{value.release_ready_count}/{value.entry_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | package | decision | accepted | release ready | address |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.package_id}` | `{item.decision}` | `{item.accepted}` | `{item.release_ready}` | `{item.package_address}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entries_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries.from_mapping(value.to_dict()).to_dict())


def summary_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary.from_mapping(value.to_dict()).to_dict())


def _write(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_registry(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry):
        raise ValidationError("policy package registry persistence requires a typed registry")
    destination = Path(destination)
    if destination.exists() and (not destination.is_dir() or not overwrite):
        raise ValidationError("policy package registry destination exists or is not a directory")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-policy-package-registry-", dir=str(parent)))
    try:
        entries = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries(value.entries, address_entries(value.entries))
        documents = {"manifest.json": value.manifest.to_dict(), "registry.json": value.to_dict(), "entries.json": entries.to_dict(), "summary.json": value.summary.to_dict()}
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("policy package registry destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("policy package registry artifact is not valid JSON") from error
    return _mapping(value, "policy package registry artifact")


def _read_canonical(path: Path, value: Mapping[str, Any]) -> None:
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError("policy package registry artifact cannot be read") from error
    if actual != canonical_json(value):
        raise ValidationError("policy package registry artifact is not canonical")


def load_registry(destination: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry:
    destination = Path(destination)
    if not destination.is_dir():
        raise ValidationError("policy package registry destination must be a directory")
    names = tuple(sorted(path.name for path in destination.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("policy package registry directory does not contain the exact file set")
    raw = {name: _read_json(destination / name) for name in FILES}
    for name, value in raw.items():
        _read_canonical(destination / name, value)
    registry = registry_from_mapping(raw["registry.json"])
    entries = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries.from_mapping(raw["entries.json"])
    manifest = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest.from_mapping(raw["manifest.json"])
    summary = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary.from_mapping(raw["summary.json"])
    if entries.to_dict() != {"entries": [item.to_dict() for item in registry.entries], "content_address": address_entries(registry.entries)} or manifest.to_dict() != registry.manifest.to_dict() or summary.to_dict() != registry.summary.to_dict():
        raise ValidationError("policy package registry artifacts do not replay")
    return registry


def run_registry(packages: Sequence[package_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackage], *, registry_id: str = DEFAULT_REGISTRY_ID, destination: str | Path | None = None, overwrite: bool = False) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry:
    value = build_registry(packages, registry_id=registry_id)
    if destination is not None:
        persist_registry(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"registry_id": {"type": "string"}, "files": {"const": list(FILES)}, "artifact_addresses": {"type": "array", "items": {"type": "string"}, "minItems": len(MANIFEST_ARTIFACT_FILES), "maxItems": len(MANIFEST_ARTIFACT_FILES)}, "content_address": {"type": "string"}}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "package_version": {"type": "string"}, "policy_id": {"type": "string"}, "evaluation_id": {"type": "string"}, "runtime_address": {"type": "string"}, "policy_audit_address": {"type": "string"}, "runtime_audit_address": {"type": "string"}, "direction": {"type": "string"}, "state": {"enum": ["complete", "incomplete"]}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry summary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "release_ready_count": {"type": "integer", "minimum": 0}, "promote_count": {"type": "integer", "minimum": 0}, "hold_count": {"type": "integer", "minimum": 0}, "block_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "content_address": {"type": "string"}}}


def registry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry", "type": "object", "additionalProperties": False, "required": list(REGISTRY_FIELDS), "properties": {"registry_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "release_ready_count": {"type": "integer", "minimum": 0}, "promote_count": {"type": "integer", "minimum": 0}, "hold_count": {"type": "integer", "minimum": 0}, "block_count": {"type": "integer", "minimum": 0}, "state": {"enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "entries": {"type": "array"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": list(FILES), "manifest_artifact_files": list(MANIFEST_ARTIFACT_FILES), "max_entries": MAX_ENTRIES, "states": list(STATES), "decisions": list(DECISIONS), "features": ["deterministic package admission", "duplicate identity rejection", "accepted and readiness conservation", "empty ready review and blocked state folding", "exact four-file persistence", "canonical JSON and atomic writes", "bounded public metadata", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_REGISTRY_ID", "ENTRY_FIELDS", "ENTRIES_FIELDS", "ENTRY_PREFIX", "ENTRIES_PREFIX", "FILES", "MANIFEST_ARTIFACT_FILES", "MANIFEST_FIELDS", "MAX_ENTRIES", "REGISTRY_FIELDS", "REGISTRY_PREFIX", "STATES", "SUMMARY_FIELDS", "SUMMARY_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntries", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryManifest", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistrySummary", "address_entries", "address_entry", "address_manifest", "address_registry", "address_summary", "build_registry", "capabilities", "entries_json", "entry_from_package", "entry_schema", "load_registry", "manifest_schema", "persist_registry", "registry_csv", "registry_from_mapping", "registry_json", "registry_schema", "render_registry_markdown", "run_registry", "summary_json", "summary_schema"]

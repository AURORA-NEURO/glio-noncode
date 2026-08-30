"""Content-addressed registry for certificate-observatory archives.

The archive boundary protects one independently verified observatory package.
This module adds the next operational boundary: a bounded catalog of those
archives.  A registry does not merge package evidence and it never treats an
archive path as public data.  Entries retain only content addresses and
conserved summary counters, while the index groups different snapshots by
package identity for inspection and release operations.

The directory representation is deliberately closed.  It contains exactly
five canonical JSON members, is written through sibling staging, and reloads
only after every manifest link, member hash, index projection, and aggregate
counter replays.  The mapped form remains useful for APIs, but archive files
are the only accepted source for archive-backed entry construction.
"""

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

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = archive_model.VERSION + "-registry-v1"
BOUNDARY = archive_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = archive_model.ARCHIVE_PREFIX + "-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
GROUP_PREFIX = REGISTRY_PREFIX + "-package"
INDEX_PREFIX = REGISTRY_PREFIX + "-index"
ARTIFACT_PREFIX = REGISTRY_PREFIX + "-artifact"
MANIFEST_PREFIX = REGISTRY_PREFIX + "-manifest"

MANIFEST_NAME = "manifest.json"
REGISTRY_NAME = "registry.json"
ENTRIES_NAME = "entries.json"
METRICS_NAME = "metrics.json"
INDEX_NAME = "index.json"
FILES = (MANIFEST_NAME, REGISTRY_NAME, ENTRIES_NAME, METRICS_NAME, INDEX_NAME)

DEFAULT_REGISTRY_ID = "consensus-certificate-observatory-archive-registry"
DEFAULT_LIMIT = 50
MAX_ENTRIES = 128
MAX_QUERY_ITEMS = 4096
MAX_ARCHIVE_BYTES = archive_model.MAX_ARCHIVE_BYTES
MAX_TOTAL_ARCHIVE_BYTES = MAX_ENTRIES * MAX_ARCHIVE_BYTES


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return archive_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry:
    """A public summary for one verified archive snapshot."""

    FIELDS = (
        "entry_id",
        "archive_id",
        "archive_address",
        "package_id",
        "package_address",
        "archive_size",
        "accepted",
        "observation_count",
        "total_check_count",
        "total_failed_count",
        "alert_count",
        "content_address",
    )

    def __init__(
        self,
        entry_id: str,
        archive_id: str,
        archive_address: str,
        package_id: str,
        package_address: str,
        archive_size: int,
        accepted: bool,
        observation_count: int,
        total_check_count: int,
        total_failed_count: int,
        alert_count: int,
        content_address: str,
    ) -> None:
        self.entry_id = _label(entry_id, "registry entry ID")
        self.archive_id = _label(archive_id, "registry archive ID")
        self.archive_address = _address(archive_address, "registry archive address", archive_model.ARCHIVE_PREFIX)
        self.package_id = _label(package_id, "registry package ID")
        self.package_address = _address(package_address, "registry package address", package_model.PACKAGE_PREFIX)
        self.archive_size = _count(archive_size, "registry archive size", MAX_ARCHIVE_BYTES, positive=True)
        self.accepted = _bool(accepted, "registry entry acceptance")
        self.observation_count = _count(observation_count, "registry observation count", 65536, positive=True)
        self.total_check_count = _count(total_check_count, "registry check count", 2_000_000, positive=True)
        self.total_failed_count = _count(total_failed_count, "registry failed check count", self.total_check_count)
        self.alert_count = _count(alert_count, "registry alert count", 4096)
        self.content_address = _address(content_address, "registry entry content address", ENTRY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry entry content address")
        self._validate()

    def _validate(self) -> None:
        if self.total_failed_count > self.total_check_count:
            raise ValidationError("registry entry failed checks exceed checks")
        if not _public(self.to_dict()):
            raise ValidationError("registry entry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("registry entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"total_check_count", "total_failed_count"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry":
        value = _mapping(value, "registry entry")
        _strict(value, set(cls.FIELDS), "registry entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry):
        raise ValidationError("registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def _entry_from_archive(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive, entry_id: str, archive_size: int | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry:
    value = archive_model.verify_archive(value)
    package = value.package
    if package is None:
        raise ValidationError("registry entries require a byte-backed archive package")
    observatory = package.observatory
    report = package.report
    body = {
        "entry_id": entry_id,
        "archive_id": value.archive_id,
        "archive_address": value.content_address,
        "package_id": package.package_id,
        "package_address": package.content_address,
        "archive_size": value.archive_size if archive_size is None else archive_size,
        "accepted": observatory.accepted_count == observatory.observation_count,
        "observation_count": observatory.observation_count,
        "total_check_count": observatory.total_check_count,
        "total_failed_count": observatory.total_failed_count,
        "alert_count": report.alert_count,
    }
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry(**body, content_address=ENTRY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry(**body, content_address=address_entry(provisional))


def entry_from_archive(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive, *, entry_id: str | None = None, archive_size: int | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry:
    selected_id = value.archive_id if entry_id is None else entry_id
    return _entry_from_archive(value, selected_id, archive_size)


def entry_from_archive_file(source: str | Path, *, entry_id: str | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry:
    path = Path(source)
    if path.is_symlink() or not path.is_file():
        raise ValidationError("archive input must be a regular file")
    return entry_from_archive(archive_model.load_archive(path), entry_id=entry_id, archive_size=path.stat().st_size)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics:
    """Conserved counters derived solely from registry entries."""

    FIELDS = ("entry_count", "archive_bytes", "accepted_count", "held_count", "observation_count", "total_check_count", "total_failed_count", "alert_count", "unique_package_count")

    def __init__(self, values: Mapping[str, Any]) -> None:
        values = _mapping(values, "registry metrics")
        _strict(values, set(self.FIELDS), "registry metrics")
        self._values = {}
        for field in self.FIELDS:
            maximum = MAX_TOTAL_ARCHIVE_BYTES if field == "archive_bytes" else 2_000_000_000
            self._values[field] = _count(values[field], f"registry metric {field}", maximum)
            setattr(self, field, self._values[field])
        self._validate()

    def _validate(self) -> None:
        if self.accepted_count + self.held_count != self.entry_count:
            raise ValidationError("registry acceptance metrics are not conserved")
        if self.unique_package_count > self.entry_count:
            raise ValidationError("registry package cardinality exceeds entries")

    def to_dict(self) -> dict[str, Any]:
        return dict(self._values)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics":
        return cls(value)


def _metrics(entries: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics:
    package_ids = {entry.package_id for entry in entries}
    values = {
        "entry_count": len(entries),
        "archive_bytes": sum(entry.archive_size for entry in entries),
        "accepted_count": sum(entry.accepted for entry in entries),
        "held_count": sum(not entry.accepted for entry in entries),
        "observation_count": sum(entry.observation_count for entry in entries),
        "total_check_count": sum(entry.total_check_count for entry in entries),
        "total_failed_count": sum(entry.total_failed_count for entry in entries),
        "alert_count": sum(entry.alert_count for entry in entries),
        "unique_package_count": len(package_ids),
    }
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics(values)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup:
    """Index row grouping archive snapshots that contain one package."""

    FIELDS = ("package_id", "entry_ids", "archive_addresses", "accepted_count", "held_count", "content_address")

    def __init__(self, package_id: str, entry_ids: Sequence[str], archive_addresses: Sequence[str], accepted_count: int, held_count: int, content_address: str) -> None:
        self.package_id = _label(package_id, "registry package group ID")
        self.entry_ids = tuple(_label(item, "registry group entry ID") for item in _sequence(entry_ids, "registry group entry IDs", MAX_ENTRIES))
        self.archive_addresses = tuple(_address(item, "registry group archive address", archive_model.ARCHIVE_PREFIX) for item in _sequence(archive_addresses, "registry group archive addresses", MAX_ENTRIES))
        self.accepted_count = _count(accepted_count, "registry group accepted count", len(self.entry_ids))
        self.held_count = _count(held_count, "registry group held count", len(self.entry_ids))
        self.content_address = _address(content_address, "registry package group address", GROUP_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry package group address")
        self._validate()

    def _validate(self) -> None:
        if not self.entry_ids or len(self.entry_ids) != len(set(self.entry_ids)) or tuple(sorted(self.entry_ids)) != self.entry_ids:
            raise ValidationError("registry package group entry IDs must be unique and sorted")
        if len(self.archive_addresses) != len(self.entry_ids) or len(set(self.archive_addresses)) != len(self.archive_addresses):
            raise ValidationError("registry package group archive addresses are not conserved")
        if self.accepted_count + self.held_count != len(self.entry_ids):
            raise ValidationError("registry package group counters are not conserved")
        if not _public(self.to_dict()):
            raise ValidationError("registry package group crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_group(self) != self.content_address:
            raise ValidationError("registry package group address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup":
        value = _mapping(value, "registry package group")
        _strict(value, set(cls.FIELDS), "registry package group")
        return cls(*(value[field] for field in cls.FIELDS))


def address_group(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup):
        raise ValidationError("registry group address requires a typed group")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GROUP_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex:
    """Deterministic package-to-entry index for bounded lookups."""

    FIELDS = ("group_count", "groups", "content_address")

    def __init__(self, group_count: int, groups: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup], content_address: str) -> None:
        self.group_count = _count(group_count, "registry index group count", MAX_ENTRIES)
        self.groups = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup.from_mapping(item) for item in _sequence(groups, "registry index groups", MAX_ENTRIES))
        self.content_address = _address(content_address, "registry index address", INDEX_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry index address")
        self._validate()

    def _validate(self) -> None:
        if self.group_count != len(self.groups) or tuple(item.package_id for item in self.groups) != tuple(sorted(item.package_id for item in self.groups)) or len({item.package_id for item in self.groups}) != len(self.groups):
            raise ValidationError("registry index groups are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("registry index crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_index(self) != self.content_address:
            raise ValidationError("registry index address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"group_count": self.group_count, "groups": tuple(item.to_dict() for item in self.groups), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex":
        value = _mapping(value, "registry index")
        _strict(value, set(cls.FIELDS), "registry index")
        groups = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup.from_mapping(item) for item in _sequence(value["groups"], "registry index groups", MAX_ENTRIES))
        return cls(value["group_count"], groups, value["content_address"])


def address_index(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex):
        raise ValidationError("registry index address requires a typed index")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=INDEX_PREFIX)


def _build_index(entries: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex:
    grouped: dict[str, list[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.package_id, []).append(entry)
    groups = []
    for package_id in sorted(grouped):
        selected = sorted(grouped[package_id], key=lambda item: item.entry_id)
        provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup(package_id, tuple(item.entry_id for item in selected), tuple(item.archive_address for item in selected), sum(item.accepted for item in selected), sum(not item.accepted for item in selected), GROUP_PREFIX + ":pending")
        groups.append(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup(provisional.package_id, provisional.entry_ids, provisional.archive_addresses, provisional.accepted_count, provisional.held_count, address_group(provisional)))
    provisional_index = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex(len(groups), tuple(groups), INDEX_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex(provisional_index.group_count, provisional_index.groups, address_index(provisional_index))


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    """A bounded, persisted catalog of verified observatory archives."""

    FIELDS = ("registry_id", "version", "boundary", "entries", "entry_count", "metrics", "index", "content_address")

    def __init__(self, registry_id: str, version: str, boundary: str, entries: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry], entry_count: int, metrics: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics, index: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex, content_address: str) -> None:
        self.registry_id = _label(registry_id, "archive registry ID")
        self.version = _text(version, "archive registry version", 1024)
        self.boundary = _text(boundary, "archive registry boundary", 512)
        self.entries = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry.from_mapping(item) for item in _sequence(entries, "archive registry entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "archive registry entry count", MAX_ENTRIES, positive=True)
        self.metrics = metrics if isinstance(metrics, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics.from_mapping(metrics)
        self.index = index if isinstance(index, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex.from_mapping(index)
        self.content_address = _address(content_address, "archive registry content address", REGISTRY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "archive registry content address")
        self._validate()

    def _validate(self) -> None:
        if self.entry_count != len(self.entries) or not self.entries:
            raise ValidationError("archive registry must contain its exact non-empty entry count")
        if tuple(item.entry_id for item in self.entries) != tuple(sorted(item.entry_id for item in self.entries)):
            raise ValidationError("archive registry entries must be sorted")
        if len({item.entry_id for item in self.entries}) != self.entry_count or len({item.archive_id for item in self.entries}) != self.entry_count or len({item.archive_address for item in self.entries}) != self.entry_count:
            raise ValidationError("archive registry entry identities must be unique")
        derived_metrics = _metrics(self.entries)
        derived_index = _build_index(self.entries)
        if derived_metrics.to_dict() != self.metrics.to_dict() or derived_index.to_dict() != self.index.to_dict():
            raise ValidationError("archive registry projections do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive registry crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_registry(self) != self.content_address:
            raise ValidationError("archive registry content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entries": tuple(item.to_dict() for item in self.entries), "entry_count": self.entry_count, "metrics": self.metrics.to_dict(), "index": self.index.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "metrics": self.metrics.to_dict(), "index_address": self.index.content_address, "content_address": self.content_address}

    def entry(self, entry_id: str) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry:
        _label(entry_id, "registry entry ID")
        for item in self.entries:
            if item.entry_id == entry_id:
                return item
        raise ValidationError("registry entry was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry":
        value = _mapping(value, "archive registry")
        _strict(value, set(cls.FIELDS), "archive registry")
        entries = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry.from_mapping(item) for item in _sequence(value["entries"], "archive registry entries", MAX_ENTRIES))
        return cls(value["registry_id"], value["version"], value["boundary"], entries, value["entry_count"], RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics.from_mapping(value["metrics"]), RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex.from_mapping(value["index"]), value["content_address"])


def address_registry(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry):
        raise ValidationError("archive registry address requires a typed registry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_PREFIX)


def build_registry(entries: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry], *, registry_id: str = DEFAULT_REGISTRY_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    selected = tuple(sorted((item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry.from_mapping(item) for item in _sequence(entries, "archive registry entries", MAX_ENTRIES)), key=lambda item: item.entry_id))
    if not selected:
        raise ValidationError("archive registry requires at least one entry")
    metrics = _metrics(selected)
    index = _build_index(selected)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry(registry_id, VERSION, BOUNDARY, selected, len(selected), metrics, index, REGISTRY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry(provisional.registry_id, provisional.version, provisional.boundary, provisional.entries, provisional.entry_count, provisional.metrics, provisional.index, address_registry(provisional))


def build_registry_from_archives(values: Sequence[archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive], *, entry_ids: Sequence[str] | None = None, registry_id: str = DEFAULT_REGISTRY_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    archives = tuple(archive_model.verify_archive(item) for item in _sequence(values, "archive registry archives", MAX_ENTRIES))
    if not archives:
        raise ValidationError("archive registry requires at least one archive")
    selected_ids = tuple(item.archive_id for item in archives) if entry_ids is None else tuple(_label(item, "registry entry ID") for item in _sequence(entry_ids, "registry entry IDs", MAX_ENTRIES))
    if len(selected_ids) != len(archives):
        raise ValidationError("registry entry ID count must match archive count")
    return build_registry(tuple(entry_from_archive(item, entry_id=selected_ids[index]) for index, item in enumerate(archives)), registry_id=registry_id)


def build_registry_from_archive_files(sources: Sequence[str | Path], *, entry_ids: Sequence[str] | None = None, registry_id: str = DEFAULT_REGISTRY_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    paths = tuple(_sequence(sources, "archive registry source files", MAX_ENTRIES))
    if not paths:
        raise ValidationError("archive registry requires at least one archive file")
    selected_ids = None if entry_ids is None else tuple(entry_ids)
    if selected_ids is not None and len(selected_ids) != len(paths):
        raise ValidationError("registry entry ID count must match source count")
    entries = tuple(entry_from_archive_file(path, entry_id=None if selected_ids is None else selected_ids[index]) for index, path in enumerate(paths))
    return build_registry(entries, registry_id=registry_id)


def registry_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    return verify_registry(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry.from_mapping(value))


def verify_registry(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry):
        raise ValidationError("archive registry verification requires a typed registry")
    value._validate()
    if not value.content_address.endswith(":pending") and address_registry(value) != value.content_address:
        raise ValidationError("archive registry address verification failed")
    return value


def registry_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> str:
    return canonical_json(verify_registry(value).to_dict())


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARTIFACT_PREFIX)}


def _manifest(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, payload: Mapping[str, bytes]) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "registry_id": value.registry_id, "registry_address": value.content_address, "entry_count": value.entry_count, "files": FILES, "artifacts": tuple(_artifact(name, payload[name]) for name in FILES if name != MANIFEST_NAME)}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> dict[str, Any]:
    value = verify_registry(value)
    payload = _registry_payload(value)
    return _manifest(value, payload)


def _registry_payload(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> dict[str, bytes]:
    value = verify_registry(value)
    return {REGISTRY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes(tuple(item.to_dict() for item in value.entries)), METRICS_NAME: canonical_bytes(value.metrics.to_dict()), INDEX_NAME: canonical_bytes(value.index.to_dict())}


def registry_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> Mapping[str, bytes]:
    payload = _registry_payload(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value, payload)), **payload}


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("archive registry destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-observatory-archive-registry-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix="certificate-observatory-archive-registry-backup-", dir=str(destination.parent)))
            backup.rmdir()
            os.replace(destination, backup)
            try:
                os.replace(staging, destination)
            except Exception:
                os.replace(backup, destination)
                raise
            shutil.rmtree(backup)
        else:
            os.replace(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_registry(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), registry_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    path = Path(source)
    if path.is_symlink() or not path.is_dir():
        raise ValidationError("archive registry input must be a regular directory")
    names = tuple(item.name for item in path.iterdir())
    if set(names) != set(FILES) or len(names) != len(FILES):
        raise ValidationError("archive registry member set is not exact")
    result = {}
    for name in FILES:
        member = path / name
        if member.is_symlink() or not member.is_file():
            raise ValidationError("archive registry member must be a regular file")
        raw = member.read_bytes()
        if len(raw) > MAX_TOTAL_ARCHIVE_BYTES:
            raise ValidationError("archive registry member exceeds the size bound")
        result[name] = raw
    return result


def load_registry(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    raw = _read_directory(source)
    try:
        decoded = {name: json.loads(value.decode("utf-8")) for name, value in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("archive registry contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("archive registry contains non-canonical JSON")
    manifest = _mapping(decoded[MANIFEST_NAME], "archive registry manifest")
    _strict(manifest, {"version", "boundary", "registry_id", "registry_address", "entry_count", "files", "artifacts", "manifest_address"}, "archive registry manifest")
    if tuple(manifest["files"]) != FILES or manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("archive registry manifest does not replay")
    artifacts = _sequence(manifest["artifacts"], "archive registry artifacts", len(FILES) - 1)
    expected_names = tuple(name for name in FILES if name != MANIFEST_NAME)
    if tuple(_mapping(item, "archive registry artifact")["name"] for item in artifacts) != expected_names:
        raise ValidationError("archive registry artifact order is not exact")
    for item in artifacts:
        item = _mapping(item, "archive registry artifact")
        _strict(item, {"name", "size", "hash"}, "archive registry artifact")
        name = item["name"]
        if item["size"] != len(raw[name]) or item["hash"] != hash_bytes(raw[name], prefix=ARTIFACT_PREFIX):
            raise ValidationError("archive registry artifact receipt does not replay")
    value = registry_from_mapping(decoded[REGISTRY_NAME])
    if value.registry_id != manifest["registry_id"] or value.content_address != manifest["registry_address"] or value.entry_count != manifest["entry_count"]:
        raise ValidationError("archive registry manifest links do not replay")
    if raw[ENTRIES_NAME] != canonical_bytes(tuple(item.to_dict() for item in value.entries)) or raw[METRICS_NAME] != canonical_bytes(value.metrics.to_dict()) or raw[INDEX_NAME] != canonical_bytes(value.index.to_dict()):
        raise ValidationError("archive registry projections do not replay")
    return value


def verify_registry_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry:
    return load_registry(source)


def registry_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> str:
    value = verify_registry(value)
    stream = io.StringIO()
    fields = ("entry_id", "archive_id", "archive_address", "package_id", "package_address", "archive_size", "accepted", "observation_count", "total_check_count", "total_failed_count", "alert_count", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.entries:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_registry_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry) -> str:
    value = verify_registry(value)
    metrics = value.metrics
    lines = ["# Certificate Observatory Archive Registry", "", f"- Registry: `{value.registry_id}`", f"- Entries: `{value.entry_count}`", f"- Archives: `{metrics.archive_bytes}` bytes", f"- Accepted: `{metrics.accepted_count}`", f"- Held: `{metrics.held_count}`", f"- Packages: `{metrics.unique_package_count}`", f"- Address: `{value.content_address}`", "", "| entry | archive | package | accepted | observations | failed checks |", "| --- | --- | --- | ---: | ---: | ---: |"]
    lines.extend(f"| `{item.entry_id}` | `{item.archive_address}` | `{item.package_id}` | `{item.accepted}` | `{item.observation_count}` | `{item.total_failed_count}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry.FIELDS), "properties": {"entry_id": {"type": "string"}, "archive_id": {"type": "string"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "archive_size": {"type": "integer", "minimum": 1}, "accepted": {"type": "boolean"}, "observation_count": {"type": "integer", "minimum": 1}, "total_check_count": {"type": "integer", "minimum": 1}, "total_failed_count": {"type": "integer", "minimum": 0}, "alert_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + ENTRY_PREFIX + ":"}}}


def metrics_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics.FIELDS), "properties": {field: {"type": "integer", "minimum": 0} for field in RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics.FIELDS}}


def group_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup.FIELDS), "properties": {"package_id": {"type": "string"}, "entry_ids": {"type": "array", "items": {"type": "string"}}, "archive_addresses": {"type": "array", "items": {"type": "string"}}, "accepted_count": {"type": "integer", "minimum": 0}, "held_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + GROUP_PREFIX + ":"}}}


def index_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex.FIELDS), "properties": {"group_count": {"type": "integer", "minimum": 0}, "groups": {"type": "array", "items": group_schema()}, "content_address": {"type": "string", "pattern": "^" + INDEX_PREFIX + ":"}}}


def registry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry.FIELDS), "properties": {"registry_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "entries": {"type": "array", "items": entry_schema()}, "entry_count": {"type": "integer", "minimum": 1}, "metrics": metrics_schema(), "index": index_schema(), "content_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "registry_id", "registry_address", "entry_count", "files", "artifacts", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "registry_id": {"type": "string"}, "registry_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 1}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name", "size", "hash"], "properties": {"name": {"type": "string"}, "size": {"type": "integer", "minimum": 0}, "hash": {"type": "string"}}}}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "registry_prefix": REGISTRY_PREFIX, "entry_prefix": ENTRY_PREFIX, "group_prefix": GROUP_PREFIX, "index_prefix": INDEX_PREFIX, "files": FILES, "limits": {"max_entries": MAX_ENTRIES, "max_query_items": MAX_QUERY_ITEMS, "max_archive_bytes": MAX_ARCHIVE_BYTES, "max_total_archive_bytes": MAX_TOTAL_ARCHIVE_BYTES}, "features": ("verified archive ingestion", "package-group index", "conserved metrics", "content-addressed entries", "atomic five-file persistence", "canonical reload", "JSON CSV and Markdown exports"), "schemas": ("entry", "metrics", "group", "index", "manifest", "registry")}


__all__ = [
    "ARTIFACT_PREFIX",
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "DEFAULT_REGISTRY_ID",
    "ENTRY_PREFIX",
    "FILES",
    "GROUP_PREFIX",
    "INDEX_PREFIX",
    "MANIFEST_NAME",
    "MAX_ARCHIVE_BYTES",
    "MAX_ENTRIES",
    "MAX_QUERY_ITEMS",
    "REGISTRY_NAME",
    "REGISTRY_PREFIX",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryEntry",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryIndex",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryMetrics",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryPackageGroup",
    "VERSION",
    "address_entry",
    "address_group",
    "address_index",
    "address_registry",
    "build_registry",
    "build_registry_from_archive_files",
    "build_registry_from_archives",
    "capabilities",
    "entry_from_archive",
    "entry_from_archive_file",
    "entry_schema",
    "group_schema",
    "index_schema",
    "load_registry",
    "manifest_document",
    "manifest_schema",
    "metrics_schema",
    "registry_bytes",
    "registry_csv",
    "registry_from_mapping",
    "registry_json",
    "registry_schema",
    "render_registry_markdown",
    "verify_registry",
    "verify_registry_directory",
    "write_registry",
]

"""Durable registry and bounded inspection for persisted promotion packages.

The registry is an index of verified package directories. It records public
package receipts and release dispositions, never source paths, process state,
or private execution metadata. The index itself is content-addressed and can
be atomically persisted, reloaded, queried, and independently audited.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = package_model.VERSION + "-registry-v1"
BOUNDARY = package_model.BOUNDARY + "_registry"
REGISTRY_PREFIX = package_model.PACKAGE_PREFIX + "-registry"
ENTRY_PREFIX = REGISTRY_PREFIX + "-entry"
QUERY_PREFIX = REGISTRY_PREFIX + "-query"
AUDIT_PREFIX = REGISTRY_PREFIX + "-audit"
DEFAULT_REGISTRY_ID = "glio-noncode-catalog-promotion-package-registry"
MANIFEST_NAME = "manifest.json"
REGISTRY_NAME = "registry.json"
FILES = (MANIFEST_NAME, REGISTRY_NAME)
RESOURCES = ("summary", "entries", "accepted", "ready", "held", "addresses")
STATES = ("ready", "held", "blocked")
DECISIONS = ("promote", "hold", "block")
DEFAULT_LIMIT = 25
MAX_LIMIT = 100
MAX_ENTRIES = 256
MAX_TEXT = package_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "public-boundary", "entry-conservation", "unique-package-ids", "unique-package-addresses", "manifest-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if ":" in value or "/" in value or "\\" in value or any(character.isspace() for character in value):
        raise ValidationError(f"{field} must be a stable path-free label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public content address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be a boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return package_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry:
    """A path-free receipt for one verified persisted package."""

    FIELDS = ("ordinal", "package_id", "package_address", "state", "decision", "accepted", "release_ready", "package_audit_state", "package_audit_accepted", "artifact_count", "file_count", "check_count", "passed_count", "failed_count", "action_count", "content_address")

    def __init__(self, ordinal: int, package_id: str, package_address: str, state: str, decision: str, accepted: bool, release_ready: bool, package_audit_state: str, package_audit_accepted: bool, artifact_count: int, file_count: int, check_count: int, passed_count: int, failed_count: int, action_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "catalog promotion package registry entry ordinal", MAX_ENTRIES, positive=True)
        self.package_id = _label(package_id, "catalog promotion package registry entry package ID")
        self.package_address = _address(package_address, "catalog promotion package registry entry package address", package_model.PACKAGE_PREFIX)
        if state not in STATES or decision not in DECISIONS:
            raise ValidationError("catalog promotion package registry entry state or decision is unsupported")
        self.state = state
        self.decision = decision
        self.accepted = _bool(accepted, "catalog promotion package registry entry accepted")
        self.release_ready = _bool(release_ready, "catalog promotion package registry entry release ready")
        self.package_audit_state = _text(package_audit_state, "catalog promotion package registry entry audit state", 32)
        self.package_audit_accepted = _bool(package_audit_accepted, "catalog promotion package registry entry audit accepted")
        self.artifact_count = _count(artifact_count, "catalog promotion package registry entry artifact count", package_model.MAX_ARTIFACTS)
        self.file_count = _count(file_count, "catalog promotion package registry entry file count", len(package_model.FILES))
        self.check_count = _count(check_count, "catalog promotion package registry entry check count", 128)
        self.passed_count = _count(passed_count, "catalog promotion package registry entry passed count", self.check_count)
        self.failed_count = _count(failed_count, "catalog promotion package registry entry failed count", self.check_count)
        self.action_count = _count(action_count, "catalog promotion package registry entry action count", 128)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.passed_count + self.failed_count != self.check_count or self.passed_count > self.check_count or self.state != {"ready": "ready", "held": "held", "blocked": "blocked"}[self.state] or self.decision != {"ready": "promote", "held": "hold", "blocked": "block"}[self.state] or self.accepted != (self.state != "blocked") or self.release_ready != (self.state == "ready"):
            raise ValidationError("catalog promotion package registry entry disposition is not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry entry content address")
        elif address_entry(self) != self.content_address:
            raise ValidationError("catalog promotion package registry entry content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry:
        value = _mapping(value, "catalog promotion package registry entry")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry entry")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry entry is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry):
        raise ValidationError("catalog promotion package registry entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def _entry(ordinal: int, package: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry:
    package_model.verify_package(package)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry(ordinal, package.package_id, package.content_address, package.packet.state, package.packet.decision, package.packet.accepted, package.packet.release_ready, "complete", True, package.artifact_count, package.file_count, package.check_count, package.passed_count, package.failed_count, package.action_count, "pending:catalog-promotion-package-registry-entry")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry(ordinal, package.package_id, package.content_address, package.packet.state, package.packet.decision, package.packet.accepted, package.packet.release_ready, "complete", True, package.artifact_count, package.file_count, package.check_count, package.passed_count, package.failed_count, package.action_count, address_entry(provisional))


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    """A deterministic index of verified package receipts."""

    FIELDS = ("registry_id", "manifest", "entries", "entry_count", "accepted_count", "release_ready_count", "held_count", "blocked_count", "artifact_count", "file_count", "registry_address", "content_address")

    def __init__(self, registry_id: str, manifest: Mapping[str, Any], entries: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry], content_address: str) -> None:
        self.registry_id = _label(registry_id, "catalog promotion package registry ID")
        self.manifest = dict(_mapping(manifest, "catalog promotion package registry manifest"))
        self.entries = tuple(entries)
        self.content_address = content_address
        self._validate()

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def accepted_count(self) -> int:
        return sum(entry.accepted for entry in self.entries)

    @property
    def release_ready_count(self) -> int:
        return sum(entry.release_ready for entry in self.entries)

    @property
    def held_count(self) -> int:
        return sum(entry.state == "held" for entry in self.entries)

    @property
    def blocked_count(self) -> int:
        return sum(entry.state == "blocked" for entry in self.entries)

    @property
    def artifact_count(self) -> int:
        return sum(entry.artifact_count for entry in self.entries)

    @property
    def file_count(self) -> int:
        return sum(entry.file_count for entry in self.entries)

    def _validate(self) -> None:
        if not self.entries or len(self.entries) > MAX_ENTRIES or any(not isinstance(entry, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry) for entry in self.entries):
            raise ValidationError("catalog promotion package registry entries are outside their bound")
        if tuple(entry.ordinal for entry in self.entries) != tuple(range(1, len(self.entries) + 1)):
            raise ValidationError("catalog promotion package registry entry ordinals are not canonical")
        _strict(self.manifest, {"version", "boundary", "registry_id", "entry_count", "files", "manifest_address"}, "catalog promotion package registry manifest")
        if self.manifest.get("version") != VERSION or self.manifest.get("boundary") != BOUNDARY or self.manifest.get("registry_id") != self.registry_id or self.manifest.get("entry_count") != self.entry_count or tuple(self.manifest.get("files", ())) != FILES:
            raise ValidationError("catalog promotion package registry manifest is not conserved")
        if self.manifest.get("manifest_address") != address_manifest(self.manifest):
            raise ValidationError("catalog promotion package registry manifest address does not replay")
        if len({entry.package_id for entry in self.entries}) != self.entry_count or len({entry.package_address for entry in self.entries}) != self.entry_count:
            raise ValidationError("catalog promotion package registry package identities must be unique")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry content address")
        elif address_registry(self) != self.content_address:
            raise ValidationError("catalog promotion package registry content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_id": self.registry_id, "manifest": self.manifest, "entries": tuple(entry.to_dict() for entry in self.entries), "entry_count": self.entry_count, "accepted_count": self.accepted_count, "release_ready_count": self.release_ready_count, "held_count": self.held_count, "blocked_count": self.blocked_count, "artifact_count": self.artifact_count, "file_count": self.file_count, "registry_address": self.content_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"manifest", "entries"}}


def address_manifest(value: Mapping[str, Any]) -> str:
    value = _mapping(value, "catalog promotion package registry manifest")
    return content_hash(dict(value) | {"manifest_address": None}, prefix=REGISTRY_PREFIX + "-manifest")


def address_registry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry):
        raise ValidationError("catalog promotion package registry address requires a typed registry")
    return content_hash(value.to_dict() | {"registry_address": None, "content_address": None}, prefix=REGISTRY_PREFIX)


def _manifest(registry_id: str, entry_count: int) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "registry_id": registry_id, "entry_count": entry_count, "files": FILES}
    return body | {"manifest_address": address_manifest(body)}


def _build_from_entries(entries: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry], registry_id: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    entries = tuple(entries)
    manifest = _manifest(registry_id, len(entries))
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry(registry_id, manifest, entries, "pending:catalog-promotion-package-registry")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry(registry_id, manifest, entries, address_registry(provisional))


def build_registry(packages: Sequence[package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage], *, registry_id: str = DEFAULT_REGISTRY_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    if not isinstance(packages, (list, tuple)) or not packages or len(packages) > MAX_ENTRIES:
        raise ValidationError("catalog promotion package registry packages are outside their bound")
    registry_id = _label(registry_id, "catalog promotion package registry ID")
    return _build_from_entries(tuple(_entry(ordinal, package) for ordinal, package in enumerate(packages, 1)), registry_id)


def build_registry_from_directories(directories: Sequence[str | Path], *, registry_id: str = DEFAULT_REGISTRY_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    if not isinstance(directories, (list, tuple)) or not directories or len(directories) > MAX_ENTRIES:
        raise ValidationError("catalog promotion package registry directories are outside their bound")
    packages = tuple(package_model.load_package(directory) for directory in directories)
    return build_registry(packages, registry_id=registry_id)


def registry_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    value = _mapping(value, "catalog promotion package registry")
    _strict(value, set(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry.FIELDS), "catalog promotion package registry")
    missing = [field for field in RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry.FIELDS if field not in value]
    if missing:
        raise ValidationError(f"catalog promotion package registry is missing fields: {missing}")
    entries = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry.from_mapping(item) for item in _sequence(value["entries"], "catalog promotion package registry entries", MAX_ENTRIES))
    manifest = dict(_mapping(value["manifest"], "catalog promotion package registry manifest"))
    if isinstance(manifest.get("files"), list):
        manifest["files"] = tuple(manifest["files"])
    candidate = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry(value["registry_id"], manifest, entries, value["content_address"])
    expected = _build_from_entries(entries, value["registry_id"])
    if candidate.to_dict() != expected.to_dict():
        raise ValidationError("catalog promotion package registry mapping does not match its canonical projection")
    return expected


def registry_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> str:
    return canonical_json(verify_registry(value).to_dict())


def registry_manifest_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> str:
    return canonical_json(verify_registry(value).manifest)


def registry_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> str:
    value = verify_registry(value)
    fields = ("ordinal", "package_id", "package_address", "state", "decision", "accepted", "release_ready", "package_audit_state", "package_audit_accepted", "artifact_count", "file_count", "check_count", "passed_count", "failed_count", "action_count", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return output.getvalue()


def render_registry_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> str:
    value = verify_registry(value)
    summary = value.summary()
    lines = ["# Catalog Promotion Package Registry", "", f"- Registry: `{summary['registry_id']}`", f"- Entries: `{summary['entry_count']}`", f"- Accepted: `{summary['accepted_count']}`", f"- Release ready: `{summary['release_ready_count']}`", f"- Held: `{summary['held_count']}`", f"- Blocked: `{summary['blocked_count']}`", f"- Content address: `{summary['content_address']}`", "", "| ordinal | package | state | decision | accepted | ready | package address |", "| ---: | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {entry.ordinal} | `{entry.package_id}` | `{entry.state}` | `{entry.decision}` | `{entry.accepted}` | `{entry.release_ready}` | `{entry.package_address}` |" for entry in value.entries)
    return "\n".join(lines) + "\n"


def package_bytes(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> dict[str, bytes]:
    value = verify_registry(value)
    return {MANIFEST_NAME: canonical_bytes(value.manifest), REGISTRY_NAME: canonical_bytes(value.to_dict())}


def write_registry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_registry(value)
    destination = Path(directory)
    if destination.exists():
        if not destination.is_dir():
            raise ValidationError("catalog promotion package registry destination must be a directory")
        existing = tuple(sorted(item.name for item in destination.iterdir()))
        if not overwrite or existing != tuple(sorted(FILES)):
            raise ValidationError("catalog promotion package registry destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="registry-staging-", dir=str(destination.parent)))
        payload = package_bytes(value)
        for name, raw in payload.items():
            (staging / name).write_bytes(raw)
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
    return destination


def load_registry(directory: str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    directory = Path(directory)
    if not directory.is_dir():
        raise ValidationError("catalog promotion package registry directory does not exist")
    names = tuple(sorted(item.name for item in directory.iterdir()))
    if names != tuple(sorted(FILES)):
        raise ValidationError("catalog promotion package registry directory has an unexpected member set")
    manifest = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    if isinstance(manifest.get("files"), list):
        manifest["files"] = tuple(manifest["files"])
    value = registry_from_mapping(json.loads((directory / REGISTRY_NAME).read_text(encoding="utf-8")))
    if manifest != value.manifest:
        raise ValidationError("catalog promotion package registry manifest does not match the registry")
    payload = package_bytes(value)
    for name, raw in payload.items():
        if (directory / name).read_bytes() != raw:
            raise ValidationError(f"catalog promotion package registry member {name} does not match its canonical bytes")
    return value


def verify_registry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry | str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry:
    if isinstance(value, (str, Path)):
        return load_registry(value)
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry):
        raise ValidationError("catalog promotion package registry verification requires a typed registry or directory")
    value._validate()
    if address_registry(value) != value.content_address:
        raise ValidationError("catalog promotion package registry content address does not replay")
    return value


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery:
    """Bounded filters for registry entries."""

    FIELDS = ("resource", "state", "decision", "accepted", "release_ready", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", state: str | None = None, decision: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("catalog promotion package registry query resource is unsupported")
        self.resource = resource
        if state is not None and state not in STATES:
            raise ValidationError("catalog promotion package registry query state is unsupported")
        if decision is not None and decision not in DECISIONS:
            raise ValidationError("catalog promotion package registry query decision is unsupported")
        if accepted is not None and not isinstance(accepted, bool):
            raise ValidationError("catalog promotion package registry query accepted must be boolean or null")
        if release_ready is not None and not isinstance(release_ready, bool):
            raise ValidationError("catalog promotion package registry query release ready must be boolean or null")
        self.state = state
        self.decision = decision
        self.accepted = accepted
        self.release_ready = release_ready
        self.text = None if text is None else _text(text, "catalog promotion package registry query text", MAX_TEXT)
        self.offset = _count(offset, "catalog promotion package registry query offset", MAX_ENTRIES)
        self.limit = _count(limit, "catalog promotion package registry query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery:
        value = _mapping(value, "catalog promotion package registry query")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult:
    """Content-addressed page over registry projections."""

    FIELDS = ("registry_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, registry_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery, total_count: int, returned_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.registry_address = _address(registry_address, "catalog promotion package registry query registry address", REGISTRY_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery):
            raise ValidationError("catalog promotion package registry query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "catalog promotion package registry query total count", MAX_ENTRIES)
        self.returned_count = _count(returned_count, "catalog promotion package registry query returned count", MAX_ENTRIES)
        if self.returned_count != len(records) or self.returned_count > self.query.limit:
            raise ValidationError("catalog promotion package registry query returned count is invalid")
        self.records = tuple(dict(_mapping(record, "catalog promotion package registry query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry query content address")
        elif address_query(self) != self.content_address:
            raise ValidationError("catalog promotion package registry query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult:
        value = _mapping(value, "catalog promotion package registry query result")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry query result is missing fields: {missing}")
        records = _sequence(value["records"], "catalog promotion package registry query records", MAX_ENTRIES)
        return cls(value["registry_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery.from_mapping(value["query"]), value["total_count"], value["returned_count"], tuple(_mapping(record, "catalog promotion package registry query record") for record in records), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult):
        raise ValidationError("catalog promotion package registry query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _query_records(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "entries":
        candidates = tuple(entry.to_dict() for entry in value.entries)
    elif query.resource == "accepted":
        candidates = tuple(entry.to_dict() for entry in value.entries if entry.accepted)
    elif query.resource == "ready":
        candidates = tuple(entry.to_dict() for entry in value.entries if entry.release_ready)
    elif query.resource == "held":
        candidates = tuple(entry.to_dict() for entry in value.entries if entry.state == "held")
    else:
        candidates = tuple({"package_id": entry.package_id, "package_address": entry.package_address, "content_address": entry.content_address} for entry in value.entries)
    filtered = []
    for record in candidates:
        if query.state is not None and record.get("state") != query.state:
            continue
        if query.decision is not None and record.get("decision") != query.decision:
            continue
        if query.accepted is not None and record.get("accepted") != query.accepted:
            continue
        if query.release_ready is not None and record.get("release_ready") != query.release_ready:
            continue
        if query.text is not None and query.text.casefold() not in canonical_json(record).casefold():
            continue
        filtered.append(record)
    return tuple(filtered)


def query_registry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery | None = None, *, resource: str = "summary", state: str | None = None, decision: str | None = None, accepted: bool | None = None, release_ready: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult:
    value = verify_registry(value)
    selected = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery(resource, state, decision, accepted, release_ready, text, offset, limit) if query is None else query
    if not isinstance(selected, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery):
        raise ValidationError("catalog promotion package registry query requires a typed query")
    records = _query_records(value, selected)
    window = records[selected.offset:selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult(value.content_address, selected, len(records), len(window), window, "pending:catalog-promotion-package-registry-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult(value.content_address, selected, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult:
    return query_registry(registry_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult):
        raise ValidationError("catalog promotion package registry query verification requires a typed result")
    value._validate()
    if address_query(value) != value.content_address:
        raise ValidationError("catalog promotion package registry query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult) -> str:
    value = verify_query(value)
    fields = sorted({str(key) for record in value.records for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Catalog Promotion Package Registry Query", "", f"- Resource: `{value.query.resource}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` from offset `{value.query.offset}`", f"- Registry: `{value.registry_address}`", f"- Query address: `{value.content_address}`", ""]
    if not value.records:
        lines.append("No matching records.")
    else:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    return "\n".join(lines) + "\n"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck:
    """One independent registry assurance result."""

    FIELDS = ("ordinal", "check_id", "passed", "severity", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "catalog promotion package registry audit check ordinal", len(CHECK_IDS), positive=True)
        if check_id not in CHECK_IDS:
            raise ValidationError("catalog promotion package registry audit check ID is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "catalog promotion package registry audit check passed")
        self.severity = _text(severity, "catalog promotion package registry audit check severity", 32)
        self.detail = _text(detail, "catalog promotion package registry audit check detail", MAX_TEXT)
        self.evidence_address = _address(evidence_address, "catalog promotion package registry audit evidence address", REGISTRY_PREFIX)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry audit check content address")
        elif address_check(self) != self.content_address:
            raise ValidationError("catalog promotion package registry audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck:
        value = _mapping(value, "catalog promotion package registry audit check")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry audit check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry audit check is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck):
        raise ValidationError("catalog promotion package registry audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REGISTRY_PREFIX + "-check")


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit:
    """Independent assurance over registry conservation and public closure."""

    FIELDS = ("registry_address", "state", "accepted", "check_count", "passed_count", "failed_count", "failed_check_ids", "checks", "content_address")

    def __init__(self, registry_address: str, state: str, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck], content_address: str) -> None:
        self.registry_address = _address(registry_address, "catalog promotion package registry audit registry address", REGISTRY_PREFIX)
        if state not in ("complete", "incomplete"):
            raise ValidationError("catalog promotion package registry audit state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "catalog promotion package registry audit accepted")
        self.checks = tuple(checks)
        if len(self.checks) != len(CHECK_IDS):
            raise ValidationError("catalog promotion package registry audit check count is invalid")
        self.content_address = content_address
        self._validate()

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def failed_count(self) -> int:
        return self.check_count - self.passed_count

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def _validate(self) -> None:
        if tuple(check.ordinal for check in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS or self.accepted != (self.failed_count == 0) or self.state != ("complete" if self.accepted else "incomplete"):
            raise ValidationError("catalog promotion package registry audit checks are not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry audit content address")
        elif address_audit(self) != self.content_address:
            raise ValidationError("catalog promotion package registry audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "state": self.state, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "failed_check_ids": self.failed_check_ids, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit:
        value = _mapping(value, "catalog promotion package registry audit")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry audit")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry audit is missing fields: {missing}")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "catalog promotion package registry audit checks", len(CHECK_IDS)))
        return cls(value["registry_address"], value["state"], value["accepted"], checks, value["content_address"])


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit):
        raise ValidationError("catalog promotion package registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _audit_check(ordinal: int, check_id: str, passed: bool, detail: str, evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck:
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck(ordinal, check_id, passed, "blocking" if not passed else "informational", detail, evidence_address, "pending:catalog-promotion-package-registry-audit-check")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck(ordinal, check_id, passed, provisional.severity, detail, evidence_address, address_check(provisional))


def audit_registry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit:
    try:
        value = verify_registry(value)
    except ValidationError as exc:
        evidence = REGISTRY_PREFIX + ":invalid-registry"
        checks = tuple(_audit_check(ordinal, check_id, False, f"registry could not be verified: {exc}", evidence) for ordinal, check_id in enumerate(CHECK_IDS, 1))
        provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit(evidence, "incomplete", False, checks, "pending:catalog-promotion-package-registry-audit")
        return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit(evidence, "incomplete", False, checks, address_audit(provisional))
    unique_ids = len({entry.package_id for entry in value.entries}) == value.entry_count
    unique_addresses = len({entry.package_address for entry in value.entries}) == value.entry_count
    checks = (
        _audit_check(1, "exact-fields", set(value.to_dict()) == set(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry.FIELDS), "registry exposes exactly its declared public fields", value.content_address),
        _audit_check(2, "public-boundary", _public(value.to_dict()), "registry contains no private transport metadata", value.content_address),
        _audit_check(3, "entry-conservation", value.entry_count == len(value.entries) and value.entry_count <= MAX_ENTRIES, "entry count matches the bounded entry sequence", value.content_address),
        _audit_check(4, "unique-package-ids", unique_ids, "package IDs are unique within the registry", value.content_address),
        _audit_check(5, "unique-package-addresses", unique_addresses, "package addresses are unique within the registry", value.content_address),
        _audit_check(6, "manifest-conservation", value.manifest["entry_count"] == value.entry_count and tuple(value.manifest["files"]) == FILES, "manifest conserves the registry member contract", value.content_address),
        _audit_check(7, "content-address", address_registry(value) == value.content_address, "registry content address replays from public content", value.content_address),
        _audit_check(8, "mapping-round-trip", registry_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "registry mapping round trip is stable", value.content_address),
        _audit_check(9, "path-free", _public(value.to_dict()), "registry receipts remain path-free at the public boundary", value.content_address),
    )
    accepted = all(check.passed for check in checks)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit(value.content_address, "complete" if accepted else "incomplete", accepted, checks, "pending:catalog-promotion-package-registry-audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit(value.content_address, provisional.state, accepted, checks, address_audit(provisional))


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit):
        raise ValidationError("catalog promotion package registry audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("catalog promotion package registry audit content address does not replay")
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit:
    return verify_audit(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit.from_mapping(value))


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Catalog Promotion Package Registry Audit", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Registry: `{value.registry_address}`", f"- Content address: `{value.content_address}`", "", "| ordinal | check | passed | severity | detail |", "| ---: | --- | --- | --- | --- |"]
    for check in value.checks:
        detail = check.detail.replace("|", "\\|")
        lines.append(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | `{check.severity}` | {detail} |")
    return "\n".join(lines) + "\n"


def registry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry.FIELDS), "properties": {"registry_id": {"type": "string"}, "manifest": {"type": "object"}, "entries": {"type": "array", "maxItems": MAX_ENTRIES}, "entry_count": {"type": "integer", "minimum": 1, "maximum": MAX_ENTRIES}, "accepted_count": {"type": "integer"}, "release_ready_count": {"type": "integer"}, "held_count": {"type": "integer"}, "blocked_count": {"type": "integer"}, "artifact_count": {"type": "integer"}, "file_count": {"type": "integer"}, "registry_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ENTRIES}, "package_id": {"type": "string"}, "package_address": {"type": "string", "pattern": "^" + package_model.PACKAGE_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "decision": {"type": "string", "enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "package_audit_state": {"type": "string"}, "package_audit_accepted": {"type": "boolean"}, "artifact_count": {"type": "integer"}, "file_count": {"type": "integer"}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "action_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + ENTRY_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "registry_id", "entry_count", "files", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "registry_id": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 1, "maximum": MAX_ENTRIES}, "files": {"type": "array", "items": {"type": "string", "enum": list(FILES)}}, "manifest_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + "-manifest:"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "state": {"type": ["string", "null"], "enum": [*STATES, None]}, "decision": {"type": ["string", "null"], "enum": [*DECISIONS, None]}, "accepted": {"type": ["boolean", "null"]}, "release_ready": {"type": ["boolean", "null"]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult.FIELDS), "properties": {"registry_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "records": {"type": "array", "maxItems": MAX_ENTRIES}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def audit_check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(CHECK_IDS)}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "severity": {"type": "string"}, "detail": {"type": "string", "maxLength": MAX_TEXT}, "evidence_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + "-check:"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit.FIELDS), "properties": {"registry_address": {"type": "string", "pattern": "^" + REGISTRY_PREFIX + ":"}, "state": {"type": "string", "enum": ["complete", "incomplete"]}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "failed_check_ids": {"type": "array", "items": {"type": "string"}}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "registry_prefix": REGISTRY_PREFIX, "entry_prefix": ENTRY_PREFIX, "query_prefix": QUERY_PREFIX, "audit_prefix": AUDIT_PREFIX, "files": FILES, "resources": RESOURCES, "states": STATES, "decisions": DECISIONS, "check_ids": CHECK_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_entries": MAX_ENTRIES}, "features": ("verified package directory indexing", "path-free package receipts", "atomic registry persistence", "strict reload verification", "bounded state and disposition queries", "independent registry audit", "JSON CSV and Markdown exports", "content-addressed entry and result replay"), "schemas": ("manifest", "entry", "registry", "query", "query-result", "audit-check", "audit")}


__all__ = [
    "AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "DECISIONS", "DEFAULT_LIMIT", "DEFAULT_REGISTRY_ID", "ENTRY_PREFIX", "FILES", "MANIFEST_NAME", "MAX_ENTRIES", "MAX_LIMIT", "MAX_TEXT", "QUERY_PREFIX", "REGISTRY_NAME", "REGISTRY_PREFIX", "RESOURCES", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAudit", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryAuditCheck", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQuery", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryQueryResult",
    "address_audit", "address_check", "address_entry", "address_manifest", "address_query", "address_registry", "audit_check_schema", "audit_from_mapping", "audit_json", "audit_registry", "audit_schema", "build_registry", "build_registry_from_directories", "capabilities", "entry_schema", "load_registry", "manifest_schema", "package_bytes", "query_csv", "query_from_mapping", "query_json", "query_registry", "query_result_from_mapping", "query_result_schema", "query_schema", "registry_csv", "registry_from_mapping", "registry_json", "registry_manifest_json", "registry_schema", "render_audit_markdown", "render_query_markdown", "render_registry_markdown", "verify_audit", "verify_query", "verify_registry", "write_registry",
]

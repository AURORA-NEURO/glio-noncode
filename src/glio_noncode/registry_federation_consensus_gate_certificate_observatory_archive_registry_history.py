"""Append-only history of certificate-observatory archive registries."""

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

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit as audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = registry_model.VERSION + "-history-v1"
BOUNDARY = registry_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-history"
ENTRY_PREFIX = HISTORY_PREFIX + "-entry"
ARTIFACT_PREFIX = HISTORY_PREFIX + "-artifact"
MANIFEST_PREFIX = HISTORY_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
METRICS_NAME = "metrics.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME, METRICS_NAME)
DEFAULT_HISTORY_ID = "consensus-certificate-observatory-archive-registry-history"
MAX_ENTRIES = registry_model.MAX_ENTRIES
MAX_HISTORY_BYTES = MAX_ENTRIES * registry_model.MAX_TOTAL_ARCHIVE_BYTES


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a public address")
    if value and prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry:
    """One append-only registry snapshot and its transition counters."""

    FIELDS = ("ordinal", "snapshot_id", "registry_address", "audit_address", "entry_count", "accepted", "added_count", "removed_count", "changed_count", "predecessor_address", "content_address")

    def __init__(self, ordinal: int, snapshot_id: str, registry_address: str, audit_address: str, entry_count: int, accepted: bool, added_count: int, removed_count: int, changed_count: int, predecessor_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history entry ordinal", MAX_ENTRIES, positive=True)
        self.snapshot_id = _label(snapshot_id, "history snapshot ID")
        self.registry_address = _address(registry_address, "history registry address", registry_model.REGISTRY_PREFIX)
        self.audit_address = _address(audit_address, "history audit address", audit_model.AUDIT_PREFIX)
        self.entry_count = _count(entry_count, "history entry count", MAX_ENTRIES, positive=True)
        self.accepted = _bool(accepted, "history snapshot acceptance")
        self.added_count = _count(added_count, "history added count", registry_model.MAX_ENTRIES * 2)
        self.removed_count = _count(removed_count, "history removed count", registry_model.MAX_ENTRIES * 2)
        self.changed_count = _count(changed_count, "history changed count", registry_model.MAX_ENTRIES * 2)
        self.predecessor_address = _address(predecessor_address, "history predecessor address", registry_model.REGISTRY_PREFIX, required=False)
        self.content_address = _address(content_address, "history entry address", ENTRY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "history entry address")
        self._validate()

    def _validate(self) -> None:
        if self.ordinal == 1 and self.predecessor_address:
            raise ValidationError("first history entry cannot have a predecessor")
        if self.ordinal > 1 and not self.predecessor_address:
            raise ValidationError("later history entries require a predecessor")
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("history entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry":
        value = _mapping(value, "history entry")
        _strict(value, set(cls.FIELDS), "history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory:
    """Ordered, immutable sequence of registry snapshot references."""

    FIELDS = ("history_id", "version", "boundary", "entries", "entry_count", "transition_count", "first_registry_address", "latest_registry_address", "added_count", "removed_count", "changed_count", "content_address")

    def __init__(self, history_id: str, version: str, boundary: str, entries: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry], entry_count: int, transition_count: int, first_registry_address: str, latest_registry_address: str, added_count: int, removed_count: int, changed_count: int, content_address: str) -> None:
        self.history_id = _label(history_id, "archive registry history ID")
        self.version = _text(version, "archive registry history version", 1024)
        self.boundary = _text(boundary, "archive registry history boundary")
        self.entries = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry.from_mapping(item) for item in _sequence(entries, "archive registry history entries", MAX_ENTRIES))
        self.entry_count = _count(entry_count, "archive registry history entry count", MAX_ENTRIES, positive=True)
        self.transition_count = _count(transition_count, "archive registry history transition count", MAX_ENTRIES)
        self.first_registry_address = _address(first_registry_address, "history first registry address", registry_model.REGISTRY_PREFIX)
        self.latest_registry_address = _address(latest_registry_address, "history latest registry address", registry_model.REGISTRY_PREFIX)
        self.added_count = _count(added_count, "history total added count", MAX_ENTRIES * MAX_ENTRIES)
        self.removed_count = _count(removed_count, "history total removed count", MAX_ENTRIES * MAX_ENTRIES)
        self.changed_count = _count(changed_count, "history total changed count", MAX_ENTRIES * MAX_ENTRIES)
        self.content_address = _address(content_address, "archive registry history address", HISTORY_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "archive registry history address")
        self._validate()

    def _validate(self) -> None:
        if self.entry_count != len(self.entries) or not self.entries or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("history entries or ordinals are not exact")
        if len({item.snapshot_id for item in self.entries}) != self.entry_count or len({item.registry_address for item in self.entries}) != self.entry_count:
            raise ValidationError("history snapshot identities must be unique")
        if self.first_registry_address != self.entries[0].registry_address or self.latest_registry_address != self.entries[-1].registry_address:
            raise ValidationError("history boundary registry addresses do not replay")
        if self.transition_count != max(0, self.entry_count - 1) or self.added_count != sum(item.added_count for item in self.entries) or self.removed_count != sum(item.removed_count for item in self.entries) or self.changed_count != sum(item.changed_count for item in self.entries):
            raise ValidationError("history transition counters are not conserved")
        for previous, current in zip(self.entries, self.entries[1:]):
            if current.predecessor_address != previous.registry_address:
                raise ValidationError("history predecessor chain is not exact")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("archive registry history address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("archive registry history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "version": self.version, "boundary": self.boundary, "entries": tuple(item.to_dict() for item in self.entries), "entry_count": self.entry_count, "transition_count": self.transition_count, "first_registry_address": self.first_registry_address, "latest_registry_address": self.latest_registry_address, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory":
        value = _mapping(value, "archive registry history")
        _strict(value, set(cls.FIELDS), "archive registry history")
        entries = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry.from_mapping(item) for item in _sequence(value["entries"], "history entries", MAX_ENTRIES))
        return cls(value["history_id"], value["version"], value["boundary"], entries, value["entry_count"], value["transition_count"], value["first_registry_address"], value["latest_registry_address"], value["added_count"], value["removed_count"], value["changed_count"], value["content_address"])


def address_history(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory):
        raise ValidationError("history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _entry(ordinal: int, snapshot_id: str, registry: registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry, audit: audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryAudit, predecessor: str = "", counts: tuple[int, int, int] = (0, 0, 0)) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry:
    body = {"ordinal": ordinal, "snapshot_id": snapshot_id, "registry_address": registry.content_address, "audit_address": audit.content_address, "entry_count": registry.entry_count, "accepted": audit.accepted, "added_count": counts[0], "removed_count": counts[1], "changed_count": counts[2], "predecessor_address": predecessor}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry(**body, content_address=ENTRY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry(**body, content_address=address_entry(provisional))


def build_history(values: Sequence[registry_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistry], *, history_id: str = DEFAULT_HISTORY_ID, snapshot_ids: Sequence[str] | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory:
    registries = tuple(registry_model.verify_registry(item) for item in _sequence(values, "archive registry history registries", MAX_ENTRIES))
    if not registries:
        raise ValidationError("archive registry history requires at least one registry")
    selected_ids = tuple(_label(item, "history snapshot ID") for item in _sequence(snapshot_ids, "history snapshot IDs", MAX_ENTRIES)) if snapshot_ids is not None else tuple(f"snapshot-{index:03d}" for index in range(1, len(registries) + 1))
    if len(selected_ids) != len(registries) or len(set(selected_ids)) != len(selected_ids):
        raise ValidationError("history snapshot IDs must match and be unique")
    entries = []
    for index, registry in enumerate(registries):
        audit = audit_model.audit_registry(registry)
        counts = (0, 0, 0)
        predecessor = ""
        if index:
            transition = diff_model.build_diff(registries[index - 1], registry, diff_id=f"{history_id}-transition-{index:03d}")
            counts = (transition.added_count, transition.removed_count, transition.changed_count)
            predecessor = registries[index - 1].content_address
        entries.append(_entry(index + 1, selected_ids[index], registry, audit, predecessor, counts))
    body = {"history_id": history_id, "version": VERSION, "boundary": BOUNDARY, "entries": tuple(entries), "entry_count": len(entries), "transition_count": max(0, len(entries) - 1), "first_registry_address": entries[0].registry_address, "latest_registry_address": entries[-1].registry_address, "added_count": sum(item.added_count for item in entries), "removed_count": sum(item.removed_count for item in entries), "changed_count": sum(item.changed_count for item in entries)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory(**body, content_address=HISTORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory(**body, content_address=address_history(provisional))


def history_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory:
    return verify_history(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory.from_mapping(value))


def verify_history(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) or (not value.content_address.endswith(":pending") and address_history(value) != value.content_address):
        raise ValidationError("archive registry history is not valid")
    return value


def history_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def _payload(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> dict[str, bytes]:
    value = verify_history(value)
    return {HISTORY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes(tuple(item.to_dict() for item in value.entries)), METRICS_NAME: canonical_bytes({"entry_count": value.entry_count, "transition_count": value.transition_count, "added_count": value.added_count, "removed_count": value.removed_count, "changed_count": value.changed_count})}


def _manifest(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory, payload: Mapping[str, bytes]) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "history_address": value.content_address, "entry_count": value.entry_count, "files": FILES, "artifacts": tuple({"name": name, "size": len(payload[name]), "hash": hash_bytes(payload[name], prefix=ARTIFACT_PREFIX)} for name in (HISTORY_NAME, ENTRIES_NAME, METRICS_NAME))}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> dict[str, Any]:
    value = verify_history(value)
    payload = _payload(value)
    return _manifest(value, payload)


def history_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> Mapping[str, bytes]:
    payload = _payload(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value, payload)), **payload}


def _write_atomic(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("archive registry history destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-observatory-archive-registry-history-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix="certificate-observatory-archive-registry-history-backup-", dir=str(destination.parent)))
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


def write_history(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic(Path(destination), history_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    path = Path(source)
    if path.is_symlink() or not path.is_dir():
        raise ValidationError("history input must be a regular directory")
    names = tuple(item.name for item in path.iterdir())
    if set(names) != set(FILES) or len(names) != len(FILES):
        raise ValidationError("history member set is not exact")
    result = {}
    for name in FILES:
        member = path / name
        if member.is_symlink() or not member.is_file():
            raise ValidationError("history member must be a regular file")
        raw = member.read_bytes()
        if len(raw) > MAX_HISTORY_BYTES:
            raise ValidationError("history member exceeds the size bound")
        result[name] = raw
    return result


def load_history(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory:
    raw = _read_directory(source)
    try:
        decoded = {name: json.loads(value.decode("utf-8")) for name, value in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("history contains non-canonical JSON")
    manifest = _mapping(decoded[MANIFEST_NAME], "history manifest")
    _strict(manifest, {"version", "boundary", "history_id", "history_address", "entry_count", "files", "artifacts", "manifest_address"}, "history manifest")
    if tuple(manifest["files"]) != FILES or manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("history manifest does not replay")
    artifacts = _sequence(manifest["artifacts"], "history artifacts", 3)
    for item in artifacts:
        item = _mapping(item, "history artifact")
        _strict(item, {"name", "size", "hash"}, "history artifact")
        name = item["name"]
        if name not in (HISTORY_NAME, ENTRIES_NAME, METRICS_NAME) or item["size"] != len(raw[name]) or item["hash"] != hash_bytes(raw[name], prefix=ARTIFACT_PREFIX):
            raise ValidationError("history artifact does not replay")
    value = history_from_mapping(decoded[HISTORY_NAME])
    if value.history_id != manifest["history_id"] or value.content_address != manifest["history_address"] or value.entry_count != manifest["entry_count"]:
        raise ValidationError("history manifest links do not replay")
    expected_metrics = {"entry_count": value.entry_count, "transition_count": value.transition_count, "added_count": value.added_count, "removed_count": value.removed_count, "changed_count": value.changed_count}
    if raw[ENTRIES_NAME] != canonical_bytes(tuple(item.to_dict() for item in value.entries)) or raw[METRICS_NAME] != canonical_bytes(expected_metrics):
        raise ValidationError("history projections do not replay")
    return value


def verify_history_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory:
    return load_history(source)


def history_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> str:
    value = verify_history(value)
    stream = io.StringIO()
    fields = ("ordinal", "snapshot_id", "registry_address", "audit_address", "entry_count", "accepted", "added_count", "removed_count", "changed_count", "predecessor_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.entries:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_history_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory) -> str:
    value = verify_history(value)
    lines = ["# Certificate Observatory Archive Registry History", "", f"- History: `{value.history_id}`", f"- Snapshots: `{value.entry_count}`", f"- Transitions: `{value.transition_count}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Address: `{value.content_address}`", "", "| # | snapshot | registry | accepted | added | removed | changed |", "| ---: | --- | --- | ---: | ---: | ---: | ---: |"]
    lines.extend(f"| `{item.ordinal}` | `{item.snapshot_id}` | `{item.registry_address}` | `{str(item.accepted).lower()}` | `{item.added_count}` | `{item.removed_count}` | `{item.changed_count}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "snapshot_id": {"type": "string"}, "registry_address": {"type": "string"}, "audit_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 1}, "accepted": {"type": "boolean"}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "predecessor_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ENTRY_PREFIX + ":"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory.FIELDS), "properties": {"history_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "entries": {"type": "array", "items": entry_schema()}, "entry_count": {"type": "integer", "minimum": 1}, "transition_count": {"type": "integer", "minimum": 0}, "first_registry_address": {"type": "string"}, "latest_registry_address": {"type": "string"}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + HISTORY_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "history_id", "history_address", "entry_count", "files", "artifacts", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "history_id": {"type": "string"}, "history_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 1}, "files": {"const": list(FILES)}, "artifacts": {"type": "array"}, "manifest_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "files": FILES, "limits": {"max_snapshots": MAX_ENTRIES, "max_history_bytes": MAX_HISTORY_BYTES}, "features": ("append-only registry snapshots", "predecessor chain", "transition counters", "independent snapshot audits", "atomic four-file persistence", "canonical reload", "JSON CSV and Markdown exports"), "schemas": ("entry", "manifest", "history")}


__all__ = ["BOUNDARY", "DEFAULT_HISTORY_ID", "ENTRY_PREFIX", "FILES", "HISTORY_NAME", "HISTORY_PREFIX", "MAX_ENTRIES", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistory", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryHistoryEntry", "VERSION", "address_entry", "address_history", "build_history", "capabilities", "entry_schema", "history_bytes", "history_csv", "history_from_mapping", "history_json", "history_schema", "load_history", "manifest_document", "manifest_schema", "render_history_markdown", "verify_history", "verify_history_directory", "write_history"]

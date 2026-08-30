"""Deterministic ZIP transport for policy package registry observatories.

The observatory already has an exact five-file directory contract. This module
adds a single-file handoff boundary while preserving the same canonical JSON,
content addresses, nested artifact identities, and value-free public surface.
ZIP member order, timestamps, compression, permissions, and comments are
fixed, so equal observatories produce equal archive bytes.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import os
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = observatory_model.VERSION + "-archive-v1"
BOUNDARY = observatory_model.BOUNDARY + "_archive"
ARCHIVE_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-archive"
MANIFEST_PREFIX = ARCHIVE_PREFIX + "-manifest"
ARTIFACT_PREFIX = ARCHIVE_PREFIX + "-artifact"
PAYLOAD_PREFIX = "observatory/"
ARCHIVE_MANIFEST_NAME = "manifest.json"
ARCHIVE_PAYLOAD_FILES = tuple(PAYLOAD_PREFIX + name for name in observatory_model.FILES)
FILES = (ARCHIVE_MANIFEST_NAME, *ARCHIVE_PAYLOAD_FILES)
DEFAULT_ARCHIVE_ID = "policy-package-registry-observatory-archive"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} has an unsupported public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    private_markers = ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\")
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.casefold()
        return not any(marker in lowered for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


def _payload_name(name: str) -> str:
    if not isinstance(name, str) or not name.startswith(PAYLOAD_PREFIX):
        raise ValidationError("archive payload member is outside its namespace")
    if name.removeprefix(PAYLOAD_PREFIX) not in observatory_model.FILES:
        raise ValidationError("archive payload member is not an observatory file")
    return name


def _artifact(index: int, name: str, raw: bytes) -> dict[str, Any]:
    _count(index, "archive artifact index", len(observatory_model.FILES))
    _payload_name(name)
    return {"index": index, "name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARTIFACT_PREFIX)}


def _observatory_payload(value: observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory) -> dict[str, bytes]:
    value = observatory_model.observatory_from_mapping(value.to_dict())
    members = observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryMembers(value.members, observatory_model.address_members(value.members))
    transitions = observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTransitions(value.transitions, observatory_model.address_transitions(value.transitions))
    documents = {
        "manifest.json": value.manifest.to_dict(),
        "observatory.json": value.to_dict(),
        "members.json": members.to_dict(),
        "transitions.json": transitions.to_dict(),
        "summary.json": value.summary.to_dict(),
    }
    return {PAYLOAD_PREFIX + name: canonical_bytes(documents[name]) for name in observatory_model.FILES}


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact:
    """One byte receipt for a fixed observatory payload member."""

    FIELDS = ("index", "name", "size", "hash")

    def __init__(self, index: int, name: str, size: int, hash: str) -> None:
        self.index = _count(index, "archive artifact index", len(observatory_model.FILES))
        self.name = _payload_name(_text(name, "archive artifact name", 256))
        self.size = _count(size, "archive artifact size", MAX_ARCHIVE_BYTES, positive=True)
        self.hash = _address(hash, "archive artifact hash", ARTIFACT_PREFIX)
        if self.index >= len(observatory_model.FILES) or self.name != ARCHIVE_PAYLOAD_FILES[self.index]:
            raise ValidationError("archive artifact ordering is not exact")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "archive artifact")
        _strict(value, set(cls.FIELDS), "archive artifact")
        return cls(value["index"], value["name"], value["size"], value["hash"])


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    """Public archive envelope with optional verified ZIP payload bytes."""

    FIELDS = ("archive_id", "version", "boundary", "observatory_id", "observatory_address", "artifact_count", "files", "artifacts", "archive_size", "content_address")

    def __init__(self, archive_id: str, version: str, boundary: str, observatory_id: str, observatory_address: str, artifact_count: int, files: Sequence[str], artifacts: Sequence[Any], archive_size: int, content_address: str, payload: Mapping[str, bytes] | None = None, observatory: observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory | None = None) -> None:
        self.archive_id = _label(archive_id, "archive ID")
        self.version = _text(version, "archive version", 1024)
        self.boundary = _label(boundary, "archive boundary")
        self.observatory_id = _label(observatory_id, "archive observatory ID")
        self.observatory_address = _address(observatory_address, "archive observatory address", observatory_model.OBSERVATORY_PREFIX)
        self.artifact_count = _count(artifact_count, "archive artifact count", len(observatory_model.FILES), positive=True)
        self.files = tuple(_payload_name(_text(item, "archive file name", 256)) for item in _sequence(files, "archive files", len(observatory_model.FILES)))
        self.artifacts = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact.from_mapping(item) for item in _sequence(artifacts, "archive artifacts", len(observatory_model.FILES)))
        self.archive_size = _count(archive_size, "archive size", MAX_ARCHIVE_BYTES, positive=True)
        if isinstance(content_address, str) and content_address.startswith("pending:"):
            self.content_address = _text(content_address, "archive content address")
        else:
            self.content_address = _address(content_address, "archive content address", ARCHIVE_PREFIX)
        self._payload = dict(payload or {})
        self._observatory = observatory
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("archive version or boundary is unsupported")
        if self.artifact_count != len(observatory_model.FILES) or self.files != ARCHIVE_PAYLOAD_FILES or len(self.artifacts) != len(observatory_model.FILES) or tuple(item.index for item in self.artifacts) != tuple(range(len(observatory_model.FILES))) or tuple(item.name for item in self.artifacts) != ARCHIVE_PAYLOAD_FILES:
            raise ValidationError("archive member vocabulary is not exact")
        if sum(item.size for item in self.artifacts) <= 0:
            raise ValidationError("archive artifact sizes must be positive")
        if not _public(self.to_dict()):
            raise ValidationError("archive crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_archive(self) != self.content_address:
            raise ValidationError("archive content address does not replay")
        if self._observatory is not None:
            checked = observatory_model.observatory_from_mapping(self._observatory.to_dict())
            if checked.observatory_id != self.observatory_id or checked.content_address != self.observatory_address:
                raise ValidationError("archive observatory identity does not replay")
        if self._payload:
            if set(self._payload) != set(ARCHIVE_PAYLOAD_FILES):
                raise ValidationError("archive payload member set is incomplete")
            for item in self.artifacts:
                raw = self._payload[item.name]
                if len(raw) != item.size or hash_bytes(raw, prefix=ARTIFACT_PREFIX) != item.hash:
                    raise ValidationError("archive artifact receipt does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_id": self.archive_id, "version": self.version, "boundary": self.boundary, "observatory_id": self.observatory_id, "observatory_address": self.observatory_address, "artifact_count": self.artifact_count, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "archive_size": self.archive_size, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("archive_id", "version", "boundary", "observatory_id", "observatory_address", "artifact_count", "archive_size", "content_address")}

    def payload_bytes(self) -> Mapping[str, bytes]:
        if not self._payload:
            raise ValidationError("archive payload bytes are unavailable")
        return dict(self._payload)

    @property
    def observatory(self):
        return self._observatory


def address_archive(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive):
        raise ValidationError("archive address requires a typed archive")
    return content_hash(value.to_dict() | {"content_address": None, "archive_size": None}, prefix=ARCHIVE_PREFIX)


def build_archive(value: observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory, *, archive_id: str = DEFAULT_ARCHIVE_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    if not isinstance(value, observatory_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatory):
        raise ValidationError("archive builder requires a typed observatory")
    observatory = observatory_model.observatory_from_mapping(value.to_dict())
    payload = _observatory_payload(observatory)
    artifacts = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact(index, name, len(payload[name]), hash_bytes(payload[name], prefix=ARTIFACT_PREFIX)) for index, name in enumerate(ARCHIVE_PAYLOAD_FILES))
    body = {"archive_id": archive_id, "version": VERSION, "boundary": BOUNDARY, "observatory_id": observatory.observatory_id, "observatory_address": observatory.content_address, "artifact_count": len(ARCHIVE_PAYLOAD_FILES), "files": ARCHIVE_PAYLOAD_FILES, "artifacts": artifacts, "archive_size": 1}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive(**body, content_address="pending:archive", payload=payload, observatory=observatory)
    candidate = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive(**body, content_address=address_archive(provisional), payload=payload, observatory=observatory)
    actual_size = len(_zip_bytes_unchecked(candidate))
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive(**(body | {"archive_size": actual_size}), content_address=candidate.content_address, payload=payload, observatory=observatory)


def build_archive_from_directory(directory: str | Path, *, archive_id: str = DEFAULT_ARCHIVE_ID) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    return build_archive(observatory_model.load_observatory(directory), archive_id=archive_id)


def archive_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    value = _mapping(value, "observatory archive")
    _strict(value, set(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive.FIELDS), "observatory archive")
    artifacts = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact.from_mapping(item) for item in _sequence(value["artifacts"], "archive artifacts", len(observatory_model.FILES)))
    return verify_archive(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive(value["archive_id"], value["version"], value["boundary"], value["observatory_id"], value["observatory_address"], value["artifact_count"], _sequence(value["files"], "archive files", len(observatory_model.FILES)), artifacts, value["archive_size"], value["content_address"]))


def verify_archive(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive):
        raise ValidationError("archive verification requires a typed archive")
    value._validate()
    if not value.content_address.startswith("pending:") and address_archive(value) != value.content_address:
        raise ValidationError("archive address verification failed")
    return value


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    info.comment = b""
    return info


def _archive_manifest(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "archive_id": value.archive_id, "observatory_id": value.observatory_id, "observatory_address": value.observatory_address, "artifact_count": value.artifact_count, "files": value.files, "artifacts": tuple(item.to_dict() for item in value.artifacts), "archive_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> dict[str, Any]:
    return _archive_manifest(verify_archive(value))


def _zip_bytes_unchecked(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> bytes:
    payload = value.payload_bytes()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(ARCHIVE_MANIFEST_NAME), canonical_bytes(_archive_manifest(value)))
        for name in ARCHIVE_PAYLOAD_FILES:
            archive.writestr(_zip_info(name), payload[name])
        archive.comment = b""
    return stream.getvalue()


def archive_bytes(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> bytes:
    value = verify_archive(value)
    raw = _zip_bytes_unchecked(value)
    if len(raw) != value.archive_size:
        raise ValidationError("archive byte size does not replay")
    return raw


def archive_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> str:
    return canonical_json(archive_from_mapping(value.to_dict()).to_dict())


def _write_atomic_file(destination: Path, raw: bytes, *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("archive destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_file():
            raise ValidationError("archive destination must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".policy-package-registry-observatory-", suffix=".zip", dir=str(destination.parent))
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ValidationError("archive destination could not be written") from error
    return destination


def write_archive(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_file(Path(destination), archive_bytes(value), overwrite=overwrite)


def _regular_zip_member(info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or info.flag_bits & 0x1 or info.filename.startswith("/") or "\\" in info.filename or any(part in ("", ".", "..") for part in info.filename.split("/")):
        return False
    if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
        return False
    return True


def _read_archive_bytes(source: str | Path | bytes) -> tuple[dict[str, bytes], int]:
    close_stream = False
    if isinstance(source, bytes):
        physical_size = len(source)
        if physical_size > MAX_ARCHIVE_BYTES:
            raise ValidationError("archive exceeds the maximum byte bound")
        stream: Any = io.BytesIO(source)
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise ValidationError("archive input must be a regular file")
        physical_size = path.stat().st_size
        if physical_size > MAX_ARCHIVE_BYTES:
            raise ValidationError("archive exceeds the maximum byte bound")
        stream = path.open("rb")
        close_stream = True
    try:
        try:
            archive = zipfile.ZipFile(stream, "r")
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            raise ValidationError("archive input is not a valid ZIP") from error
        with archive:
            infos = archive.infolist()
            names = tuple(info.filename for info in infos)
            if archive.comment or names != FILES or any(not _regular_zip_member(info) for info in infos):
                raise ValidationError("archive member vocabulary or safety contract failed")
            if any(info.file_size > MAX_ARCHIVE_BYTES for info in infos) or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
                raise ValidationError("archive payload exceeds the maximum byte bound")
            raw = {name: archive.read(name) for name in FILES}
    finally:
        if close_stream:
            stream.close()
    return raw, physical_size


def _decode_canonical(raw: Mapping[str, bytes]) -> dict[str, Mapping[str, Any]]:
    decoded: dict[str, Mapping[str, Any]] = {}
    try:
        for name in FILES:
            value = json.loads(raw[name].decode("utf-8"))
            decoded[name] = _mapping(value, f"archive member {name}")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("archive contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("archive contains non-canonical JSON")
    return decoded


def load_archive(source: str | Path | bytes) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    raw, physical_size = _read_archive_bytes(source)
    decoded = _decode_canonical(raw)
    manifest = decoded[ARCHIVE_MANIFEST_NAME]
    manifest_fields = {"version", "boundary", "archive_id", "observatory_id", "observatory_address", "artifact_count", "files", "artifacts", "archive_address", "manifest_address"}
    _strict(manifest, manifest_fields, "archive manifest")
    if manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("archive manifest address does not replay")
    observatory = observatory_model.observatory_from_mapping(decoded[PAYLOAD_PREFIX + "observatory.json"])
    expected_payload = _observatory_payload(observatory)
    for name, expected in expected_payload.items():
        if raw[name] != expected:
            raise ValidationError("archive observatory projection does not replay")
    artifacts = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact.from_mapping(item) for item in _sequence(manifest["artifacts"], "archive artifacts", len(observatory_model.FILES)))
    value = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive(manifest["archive_id"], manifest["version"], manifest["boundary"], manifest["observatory_id"], manifest["observatory_address"], manifest["artifact_count"], _sequence(manifest["files"], "archive files", len(observatory_model.FILES)), artifacts, physical_size, manifest["archive_address"], payload={name: raw[name] for name in ARCHIVE_PAYLOAD_FILES}, observatory=observatory)
    if canonical_bytes(_archive_manifest(value)) != raw[ARCHIVE_MANIFEST_NAME]:
        raise ValidationError("archive manifest or address does not replay")
    return verify_archive(value)


def load_archive_bytes(raw: bytes) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    return load_archive(raw)


def verify_archive_file(source: str | Path) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive:
    return load_archive(source)


def archive_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> str:
    value = verify_archive(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("archive_id", "observatory_id", "observatory_address", "artifact_count", "archive_size", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.summary()[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_archive_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive) -> str:
    value = verify_archive(value)
    lines = ["# Policy Package Registry Observatory Archive", "", f"- Archive: `{value.archive_id}`", f"- Observatory: `{value.observatory_id}`", f"- Observatory address: `{value.observatory_address}`", f"- ZIP bytes: `{value.archive_size}`", f"- Address: `{value.content_address}`", "", "| index | member | bytes | receipt |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| `{item.index}` | `{item.name}` | `{item.size}` | `{item.hash}` |" for item in value.artifacts)
    return "\n".join(lines) + "\n"


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive artifact", "type": "object", "additionalProperties": False, "required": list(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact.FIELDS), "properties": {"index": {"type": "integer", "minimum": 0}, "name": {"type": "string", "enum": list(ARCHIVE_PAYLOAD_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "archive_id": {"type": "string"}, "observatory_id": {"type": "string"}, "observatory_address": {"type": "string", "pattern": "^" + observatory_model.OBSERVATORY_PREFIX + ":"}, "artifact_count": {"type": "integer", "const": len(ARCHIVE_PAYLOAD_FILES)}, "files": {"const": list(ARCHIVE_PAYLOAD_FILES)}, "artifacts": {"type": "array", "minItems": len(ARCHIVE_PAYLOAD_FILES), "maxItems": len(ARCHIVE_PAYLOAD_FILES), "items": artifact_schema()}, "archive_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive manifest", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "archive_id", "observatory_id", "observatory_address", "artifact_count", "files", "artifacts", "archive_size", "archive_address", "manifest_address"], "properties": fields}


def archive_schema() -> dict[str, Any]:
    fields = {"archive_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "observatory_id": {"type": "string"}, "observatory_address": {"type": "string", "pattern": "^" + observatory_model.OBSERVATORY_PREFIX + ":"}, "artifact_count": {"type": "integer", "const": len(ARCHIVE_PAYLOAD_FILES)}, "files": {"const": list(ARCHIVE_PAYLOAD_FILES)}, "artifacts": {"type": "array", "minItems": len(ARCHIVE_PAYLOAD_FILES), "maxItems": len(ARCHIVE_PAYLOAD_FILES), "items": artifact_schema()}, "archive_size": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive", "type": "object", "additionalProperties": False, "required": list(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive.FIELDS), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "archive_prefix": ARCHIVE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "files": list(FILES), "payload_files": list(ARCHIVE_PAYLOAD_FILES), "zip_epoch": ZIP_EPOCH, "max_archive_bytes": MAX_ARCHIVE_BYTES, "features": ["deterministic ZIP bytes", "exact five-file observatory embedding", "canonical manifest replay", "byte receipt verification", "atomic file replacement", "symlink traversal and encryption rejection", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["ARCHIVE_MANIFEST_NAME", "ARCHIVE_PAYLOAD_FILES", "ARCHIVE_PREFIX", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_ARCHIVE_ID", "FILES", "MANIFEST_PREFIX", "MAX_ARCHIVE_BYTES", "PAYLOAD_PREFIX", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchive", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveArtifact", "VERSION", "address_archive", "archive_bytes", "archive_csv", "archive_from_mapping", "archive_json", "archive_schema", "artifact_schema", "build_archive", "build_archive_from_directory", "capabilities", "load_archive", "load_archive_bytes", "manifest_document", "manifest_schema", "render_archive_markdown", "verify_archive", "verify_archive_file", "write_archive"]

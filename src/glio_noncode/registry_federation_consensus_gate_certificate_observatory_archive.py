"""Deterministic ZIP transport for certificate-observatory packages.

The certificate observatory package is already a verified directory contract.
This module adds a single-file boundary for object storage, downloads, and
offline handoff.  The ZIP is deterministic: member order, timestamps,
compression settings, permissions, and canonical JSON are fixed.  The archive
manifest addresses every nested package member, so a receiver can validate the
artifact without access to the producing directory.

The archive contains no local paths, attribution fields, credentials, or
transport metadata.  Its public projection is limited to bounded labels,
content addresses, byte sizes, and fixed vocabulary.  Loading is fail-closed
for duplicate members, traversal-like names, symlinks, non-canonical JSON,
manifest drift, and package projection drift.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import os
import shutil
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = package_model.VERSION + "-archive-v1"
BOUNDARY = package_model.BOUNDARY + "_archive"
ARCHIVE_PREFIX = package_model.PACKAGE_PREFIX + "-archive"
MANIFEST_PREFIX = ARCHIVE_PREFIX + "-manifest"
ARTIFACT_PREFIX = ARCHIVE_PREFIX + "-artifact"
PAYLOAD_PREFIX = "certificate-observatory/"
ARCHIVE_MANIFEST_NAME = "manifest.json"
ARCHIVE_PAYLOAD_FILES = tuple(PAYLOAD_PREFIX + name for name in package_model.FILES)
FILES = (ARCHIVE_MANIFEST_NAME, *ARCHIVE_PAYLOAD_FILES)
DEFAULT_ARCHIVE_ID = "consensus-certificate-observatory-archive"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_QUERY_ITEMS = 4096
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = True) -> str:
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
    value = _text(value, field, 2048)
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
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    private_markers = ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\")
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return not any(marker in lowered for marker in private_markers)
    return value is None or isinstance(value, (bool, int, float))


def _payload_name(name: str) -> str:
    if not isinstance(name, str) or not name.startswith(PAYLOAD_PREFIX):
        raise ValidationError("archive member is outside the payload namespace")
    if name.removeprefix(PAYLOAD_PREFIX) not in package_model.FILES:
        raise ValidationError("archive member is not a certificate observatory package file")
    return name


def _artifact(name: str, raw: bytes, index: int) -> dict[str, Any]:
    _payload_name(name)
    _count(index, "artifact index", len(package_model.FILES))
    return {"index": index, "name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARTIFACT_PREFIX)}


def _package_payload(value: package_model.RegistryFederationConsensusGateCertificateObservatoryPackage) -> dict[str, bytes]:
    package_model.verify_package(value)
    return {PAYLOAD_PREFIX + name: raw for name, raw in package_model.package_bytes(value).items()}


class RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact:
    """A public byte receipt for one archived package member."""

    FIELDS = ("index", "name", "size", "hash")

    def __init__(self, index: int, name: str, size: int, hash: str) -> None:
        self.index = _count(index, "archive artifact index", len(package_model.FILES) - 1)
        self.name = _payload_name(_text(name, "archive artifact name", 256))
        self.size = _count(size, "archive artifact size", MAX_ARCHIVE_BYTES)
        self.hash = _address(hash, "archive artifact hash", ARTIFACT_PREFIX)
        if self.index >= len(package_model.FILES) or self.name != ARCHIVE_PAYLOAD_FILES[self.index]:
            raise ValidationError("archive artifact ordering is not exact")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact":
        value = _mapping(value, "archive artifact")
        _strict(value, set(cls.FIELDS), "archive artifact")
        return cls(value["index"], value["name"], value["size"], value["hash"])


class RegistryFederationConsensusGateCertificateObservatoryArchive:
    """A content-addressed archive envelope with optional ZIP payload bytes."""

    FIELDS = ("archive_id", "version", "boundary", "package_id", "package_address", "artifact_count", "files", "artifacts", "archive_size", "content_address")

    def __init__(self, archive_id: str, version: str, boundary: str, package_id: str, package_address: str, artifact_count: int, files: Sequence[str], artifacts: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact], archive_size: int, content_address: str, payload: Mapping[str, bytes] | None = None, package: package_model.RegistryFederationConsensusGateCertificateObservatoryPackage | None = None) -> None:
        self.archive_id = _label(archive_id, "archive ID")
        self.version = _text(version, "archive version", 1024)
        self.boundary = _text(boundary, "archive boundary", 512)
        self.package_id = _label(package_id, "archive package ID")
        self.package_address = _address(package_address, "archive package address", package_model.PACKAGE_PREFIX)
        self.artifact_count = _count(artifact_count, "archive artifact count", len(package_model.FILES), positive=True)
        self.files = tuple(_payload_name(_text(item, "archive file name", 256)) for item in _sequence(files, "archive files", len(package_model.FILES)))
        self.artifacts = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact) else RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact.from_mapping(item) for item in _sequence(artifacts, "archive artifacts", len(package_model.FILES)))
        self.archive_size = _count(archive_size, "archive size", MAX_ARCHIVE_BYTES, positive=True)
        self.content_address = _address(content_address, "archive content address", ARCHIVE_PREFIX) if not str(content_address).startswith("pending:") else _text(content_address, "archive content address")
        self._payload = dict(payload or {})
        self._package = package
        self._validate()

    def _validate(self) -> None:
        if self.artifact_count != len(package_model.FILES) or self.files != ARCHIVE_PAYLOAD_FILES or len(self.artifacts) != len(package_model.FILES) or tuple(item.index for item in self.artifacts) != tuple(range(len(package_model.FILES))) or tuple(item.name for item in self.artifacts) != ARCHIVE_PAYLOAD_FILES:
            raise ValidationError("archive member vocabulary is not exact")
        if sum(item.size for item in self.artifacts) <= 0 or self.archive_size <= 0:
            raise ValidationError("archive size receipts must be positive")
        if not _public(self.to_dict()):
            raise ValidationError("archive crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_archive(self) != self.content_address:
            raise ValidationError("archive content address does not replay")
        if self._package is not None:
            package_model.verify_package(self._package)
            if self._package.package_id != self.package_id or self._package.content_address != self.package_address:
                raise ValidationError("archive package identity does not replay")
        if self._payload:
            if set(self._payload) != set(ARCHIVE_PAYLOAD_FILES):
                raise ValidationError("archive payload member set is incomplete")
            if sum(len(raw) for raw in self._payload.values()) != sum(item.size for item in self.artifacts):
                raise ValidationError("archive artifact sizes do not conserve payload bytes")
            for item in self.artifacts:
                raw = self._payload[item.name]
                if len(raw) != item.size or hash_bytes(raw, prefix=ARTIFACT_PREFIX) != item.hash:
                    raise ValidationError("archive artifact receipt does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_id": self.archive_id, "version": self.version, "boundary": self.boundary, "package_id": self.package_id, "package_address": self.package_address, "artifact_count": self.artifact_count, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "archive_size": self.archive_size, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("archive_id", "version", "boundary", "package_id", "package_address", "artifact_count", "archive_size", "content_address")}

    def payload_bytes(self) -> Mapping[str, bytes]:
        if not self._payload:
            raise ValidationError("archive payload bytes are unavailable")
        return dict(self._payload)

    @property
    def package(self) -> package_model.RegistryFederationConsensusGateCertificateObservatoryPackage | None:
        return self._package


def address_archive(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchive):
        raise ValidationError("archive address requires a typed archive")
    # The byte size is derived from the final ZIP representation.  Excluding
    # that redundant field from the logical address avoids a content-address /
    # compression-size feedback loop while the manifest still records and
    # independently audits the physical size.
    return content_hash(value.to_dict() | {"content_address": None, "archive_size": None}, prefix=ARCHIVE_PREFIX)


def build_archive(value: package_model.RegistryFederationConsensusGateCertificateObservatoryPackage | package_model.RegistryFederationConsensusGateCertificateObservatory, *, archive_id: str = DEFAULT_ARCHIVE_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    if isinstance(value, package_model.RegistryFederationConsensusGateCertificateObservatoryPackage):
        package = package_model.verify_package(value)
    elif isinstance(value, package_model.observatory_model.RegistryFederationConsensusGateCertificateObservatory):
        package = package_model.build_package(value)
    else:
        raise ValidationError("archive builder requires a certificate observatory package or observatory")
    payload = _package_payload(package)
    artifacts = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact(index, name, len(payload[name]), hash_bytes(payload[name], prefix=ARTIFACT_PREFIX)) for index, name in enumerate(ARCHIVE_PAYLOAD_FILES))
    body = {"archive_id": archive_id, "version": VERSION, "boundary": BOUNDARY, "package_id": package.package_id, "package_address": package.content_address, "artifact_count": len(ARCHIVE_PAYLOAD_FILES), "files": ARCHIVE_PAYLOAD_FILES, "artifacts": artifacts, "archive_size": 1}
    archive = None
    for _ in range(64):
        provisional = RegistryFederationConsensusGateCertificateObservatoryArchive(**body, content_address="pending:archive", payload=payload, package=package)
        candidate = RegistryFederationConsensusGateCertificateObservatoryArchive(**body, content_address=address_archive(provisional), payload=payload, package=package)
        actual_size = len(_zip_bytes_unchecked(candidate))
        archive = candidate
        if actual_size == candidate.archive_size:
            break
        body["archive_size"] = actual_size
    if archive is None or len(_zip_bytes_unchecked(archive)) != archive.archive_size:
        raise ValidationError("archive size and addressed manifest did not converge")
    return archive


def build_archive_from_directory(directory: str | Path, *, archive_id: str = DEFAULT_ARCHIVE_ID) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    return build_archive(package_model.load_package(Path(directory)), archive_id=archive_id)


def archive_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    value = _mapping(value, "certificate observatory archive")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchive.FIELDS), "certificate observatory archive")
    artifacts = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact.from_mapping(item) for item in _sequence(value["artifacts"], "archive artifacts", len(package_model.FILES)))
    return verify_archive(RegistryFederationConsensusGateCertificateObservatoryArchive(value["archive_id"], value["version"], value["boundary"], value["package_id"], value["package_address"], value["artifact_count"], _sequence(value["files"], "archive files", len(package_model.FILES)), artifacts, value["archive_size"], value["content_address"]))


def verify_archive(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchive):
        raise ValidationError("archive verification requires a typed archive")
    value._validate()
    if not value.content_address.startswith("pending:") and address_archive(value) != value.content_address:
        raise ValidationError("archive address verification failed")
    return value


def archive_json(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> str:
    return canonical_json(verify_archive(value).to_dict())


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    info.comment = b""
    return info


def _manifest(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "archive_id": value.archive_id, "package_id": value.package_id, "package_address": value.package_address, "artifact_count": value.artifact_count, "files": value.files, "artifacts": tuple(item.to_dict() for item in value.artifacts), "archive_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> dict[str, Any]:
    return _manifest(verify_archive(value))


def _zip_size(body: Mapping[str, Any], payload: Mapping[str, bytes]) -> int:
    artifacts = tuple(item.to_dict() if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact) else item for item in body["artifacts"])
    manifest_body = {"version": body["version"], "boundary": body["boundary"], "archive_id": body["archive_id"], "package_id": body["package_id"], "package_address": body["package_address"], "artifact_count": body["artifact_count"], "files": tuple(body["files"]), "artifacts": artifacts, "archive_address": ARCHIVE_PREFIX + ":" + "0" * 64}
    manifest = manifest_body | {"manifest_address": content_hash(manifest_body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(ARCHIVE_MANIFEST_NAME), canonical_bytes(manifest))
        for name in ARCHIVE_PAYLOAD_FILES:
            archive.writestr(_zip_info(name), payload[name])
    return len(stream.getvalue())


def _archive_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> bytes:
    value = verify_archive(value)
    raw = _zip_bytes_unchecked(value)
    if len(raw) != value.archive_size:
        raise ValidationError("archive byte size does not replay")
    return raw


def _zip_bytes_unchecked(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> bytes:
    payload = value.payload_bytes()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(ARCHIVE_MANIFEST_NAME), canonical_bytes(_manifest(value)))
        for name in ARCHIVE_PAYLOAD_FILES:
            archive.writestr(_zip_info(name), payload[name])
        archive.comment = b""
    return stream.getvalue()


def archive_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> bytes:
    return _archive_bytes(value)


def _write_atomic_file(destination: Path, raw: bytes, *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("archive destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_file():
            raise ValidationError("archive destination must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".certificate-observatory-archive-", suffix=".zip", dir=str(destination.parent))
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def write_archive(value: RegistryFederationConsensusGateCertificateObservatoryArchive, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_file(Path(destination), _archive_bytes(value), overwrite=overwrite)


def _regular_zip_member(info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or info.flag_bits & 0x1 or info.filename.startswith("/") or "\\" in info.filename or any(part in ("", ".", "..") for part in info.filename.split("/")):
        return False
    if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
        return False
    return True


def _package_from_payload(decoded: Mapping[str, Any], raw: Mapping[str, bytes]) -> package_model.RegistryFederationConsensusGateCertificateObservatoryPackage:
    package = package_model.package_from_mapping(decoded[PAYLOAD_PREFIX + package_model.PACKAGE_NAME])
    expected = package_model.package_bytes(package)
    for name in package_model.FILES:
        full = PAYLOAD_PREFIX + name
        if canonical_bytes(decoded[full]) != raw[full] or raw[full] != expected[name]:
            raise ValidationError("archive package projection does not replay")
    return package


def load_archive(source: str | Path | bytes) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    stream: io.BytesIO | Any
    close_stream = False
    physical_size = len(source) if isinstance(source, bytes) else None
    if isinstance(source, bytes):
        stream = io.BytesIO(source)
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise ValidationError("archive input must be a regular file")
        stream = path.open("rb")
        close_stream = True
        physical_size = path.stat().st_size
    try:
        try:
            archive = zipfile.ZipFile(stream, "r")
        except (OSError, zipfile.BadZipFile) as error:
            raise ValidationError("archive input is not a valid ZIP") from error
        with archive:
            if archive.comment or len(archive.infolist()) != len(FILES):
                raise ValidationError("archive has an unexpected member count or comment")
            infos = archive.infolist()
            names = tuple(info.filename for info in infos)
            if names != FILES or any(not _regular_zip_member(info) for info in infos):
                raise ValidationError("archive member vocabulary or safety contract failed")
            raw = {name: archive.read(name) for name in FILES}
    finally:
        if close_stream:
            stream.close()
    try:
        decoded = {name: json.loads(raw[name].decode("utf-8")) for name in FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("archive contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("archive contains non-canonical JSON")
    manifest = _mapping(decoded[ARCHIVE_MANIFEST_NAME], "archive manifest")
    _strict(manifest, {"version", "boundary", "archive_id", "package_id", "package_address", "artifact_count", "files", "artifacts", "archive_address", "manifest_address"}, "archive manifest")
    if manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("archive manifest address does not replay")
    package = _package_from_payload(decoded, raw)
    artifacts = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact.from_mapping(item) for item in _sequence(manifest["artifacts"], "archive artifacts", len(package_model.FILES)))
    value = RegistryFederationConsensusGateCertificateObservatoryArchive(manifest["archive_id"], manifest["version"], manifest["boundary"], manifest["package_id"], manifest["package_address"], manifest["artifact_count"], _sequence(manifest["files"], "archive files", len(package_model.FILES)), artifacts, int(physical_size or 0), manifest["archive_address"], payload={PAYLOAD_PREFIX + name: raw[PAYLOAD_PREFIX + name] for name in package_model.FILES}, package=package)
    if physical_size != value.archive_size:
        raise ValidationError("archive file size does not replay")
    if canonical_bytes(_manifest(value)) != raw[ARCHIVE_MANIFEST_NAME]:
        raise ValidationError("archive manifest or byte size does not replay")
    return verify_archive(value)


def load_archive_bytes(raw: bytes) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    return load_archive(raw)


def verify_archive_file(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchive:
    return load_archive(source)


def archive_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> str:
    value = verify_archive(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("archive_id", "package_id", "package_address", "artifact_count", "archive_size", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.summary())
    return stream.getvalue()


def render_archive_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchive) -> str:
    value = verify_archive(value)
    lines = ["# Certificate Observatory Archive", "", f"- Archive: `{value.archive_id}`", f"- Package: `{value.package_id}`", f"- Package address: `{value.package_address}`", f"- Members: `{value.artifact_count}`", f"- ZIP bytes: `{value.archive_size}`", f"- Address: `{value.content_address}`", "", "| index | member | bytes | receipt |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| `{item.index}` | `{item.name}` | `{item.size}` | `{item.hash}` |" for item in value.artifacts)
    return "\n".join(lines) + "\n"


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact.FIELDS), "properties": {"index": {"type": "integer", "minimum": 0}, "name": {"type": "string"}, "size": {"type": "integer", "minimum": 0}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "archive_id", "package_id", "package_address", "artifact_count", "files", "artifacts", "archive_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "archive_id": {"type": "string"}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "artifact_count": {"type": "integer"}, "files": {"type": "array"}, "artifacts": {"type": "array", "items": artifact_schema()}, "archive_address": {"type": "string"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def archive_schema() -> dict[str, Any]:
    fields = {"archive_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "artifact_count": {"type": "integer"}, "files": {"type": "array"}, "artifacts": {"type": "array", "items": artifact_schema()}, "archive_size": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchive.FIELDS), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "archive_prefix": ARCHIVE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "files": FILES, "payload_files": ARCHIVE_PAYLOAD_FILES, "features": ("deterministic ZIP bytes", "exact package projection embedding", "canonical manifest replay", "atomic file replacement", "symlink and traversal rejection", "path-free public envelope", "JSON CSV and Markdown exports"), "schemas": ("artifact", "manifest", "archive")}


__all__ = ["ARCHIVE_MANIFEST_NAME", "ARCHIVE_PAYLOAD_FILES", "ARCHIVE_PREFIX", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_ARCHIVE_ID", "FILES", "MANIFEST_PREFIX", "PAYLOAD_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchive", "RegistryFederationConsensusGateCertificateObservatoryArchiveArtifact", "VERSION", "address_archive", "archive_bytes", "archive_csv", "archive_from_mapping", "archive_json", "archive_schema", "artifact_schema", "build_archive", "build_archive_from_directory", "capabilities", "load_archive", "load_archive_bytes", "manifest_document", "manifest_schema", "render_archive_markdown", "verify_archive", "verify_archive_file", "write_archive"]

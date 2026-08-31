"""Deterministic ZIP transport for runtime-registry federations.

The federation boundary is already a complete five-file public contract.  This
module adds a single-file handoff without changing that contract: the nested
federation files are canonical JSON, the outer manifest is addressed, and
every embedded byte has a separately replayable receipt.  ZIP metadata is
fixed so equal federations produce byte-identical archives.

Only public projections cross the archive boundary.  The implementation keeps
the decoded federation and raw ZIP members private so the archive mapping
cannot accidentally grow into a source-data transport.
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

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = federation_model.VERSION + "-archive-v1"
BOUNDARY = federation_model.BOUNDARY + "_archive"
ARCHIVE_PREFIX = federation_model.FEDERATION_PREFIX + "-archive"
MANIFEST_PREFIX = ARCHIVE_PREFIX + "-manifest"
ARTIFACT_PREFIX = ARCHIVE_PREFIX + "-artifact"
ARCHIVE_MANIFEST_NAME = "manifest.json"
EMBEDDED_PREFIX = "federation/"
EMBEDDED_FILES = tuple(EMBEDDED_PREFIX + name for name in federation_model.FILES)
FILES = (ARCHIVE_MANIFEST_NAME, *EMBEDDED_FILES)
DEFAULT_ARCHIVE_ID = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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


def _embedded_name(name: Any) -> str:
    name = _text(name, "archive embedded file name", 256)
    if not name.startswith(EMBEDDED_PREFIX) or name not in EMBEDDED_FILES:
        raise ValidationError("archive embedded file is outside the exact federation namespace")
    return name


def _regular_zip_member(info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or info.flag_bits & 0x1 or info.filename.startswith("/") or "\\" in info.filename or any(part in ("", ".", "..") for part in info.filename.split("/")):
        return False
    if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
        return False
    return True


def _public(value: Any) -> bool:
    return federation_model._public(value)


def _embedded_federation(value: federation_model.RecoveryExecutionRuntimeRegistryFederation) -> dict[str, bytes]:
    federation = federation_model.federation_from_mapping(value.to_dict())
    members = federation_model.RecoveryExecutionRuntimeRegistryFederationMembers(federation.members, federation_model.address_members(federation.members))
    entries = federation_model.RecoveryExecutionRuntimeRegistryFederationEntries(federation.entries, federation_model.address_entries(federation.entries))
    documents = {
        "manifest.json": federation.manifest.to_dict(),
        "federation.json": federation.to_dict(),
        "members.json": members.to_dict(),
        "entries.json": entries.to_dict(),
        "summary.json": federation.summary.to_dict(),
    }
    return {EMBEDDED_PREFIX + name: canonical_bytes(documents[name]) for name in federation_model.FILES}


class RecoveryExecutionRuntimeRegistryFederationArchiveArtifact:
    """A byte receipt for one fixed embedded federation member."""

    FIELDS = ("index", "name", "size", "hash")

    def __init__(self, index: int, name: str, size: int, hash: str) -> None:
        self.index = _count(index, "archive artifact index", len(EMBEDDED_FILES))
        self.name = _embedded_name(name)
        self.size = _count(size, "archive artifact size", MAX_ARCHIVE_BYTES, positive=True)
        self.hash = _address(hash, "archive artifact hash", ARTIFACT_PREFIX)
        if self.index >= len(EMBEDDED_FILES) or self.name != EMBEDDED_FILES[self.index]:
            raise ValidationError("archive artifact ordering is not exact")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RecoveryExecutionRuntimeRegistryFederationArchiveArtifact":
        value = _mapping(value, "archive artifact")
        _strict(value, set(cls.FIELDS), "archive artifact")
        return cls(value["index"], value["name"], value["size"], value["hash"])


class RecoveryExecutionRuntimeRegistryFederationArchive:
    """A public, addressed envelope around a verified federation."""

    FIELDS = ("archive_id", "version", "boundary", "federation_id", "federation_address", "artifact_count", "files", "artifacts", "archive_size", "content_address")

    def __init__(self, archive_id: str, version: str, boundary: str, federation_id: str, federation_address: str, artifact_count: int, files: Sequence[str], artifacts: Sequence[Any], archive_size: int, content_address: str, raw: Mapping[str, bytes] | None = None, federation: federation_model.RecoveryExecutionRuntimeRegistryFederation | None = None) -> None:
        self.archive_id = _label(archive_id, "archive ID")
        self.version = _text(version, "archive version", 2048)
        self.boundary = _text(boundary, "archive boundary", 2048)
        self.federation_id = _label(federation_id, "archive federation ID")
        self.federation_address = _address(federation_address, "archive federation address", federation_model.FEDERATION_PREFIX)
        self.artifact_count = _count(artifact_count, "archive artifact count", len(EMBEDDED_FILES), positive=True)
        self.files = tuple(_embedded_name(item) for item in _sequence(files, "archive files", len(EMBEDDED_FILES)))
        self.artifacts = tuple(item if isinstance(item, RecoveryExecutionRuntimeRegistryFederationArchiveArtifact) else RecoveryExecutionRuntimeRegistryFederationArchiveArtifact.from_mapping(item) for item in _sequence(artifacts, "archive artifacts", len(EMBEDDED_FILES)))
        self.archive_size = _count(archive_size, "archive size", MAX_ARCHIVE_BYTES, positive=True)
        if isinstance(content_address, str) and content_address.startswith("pending:"):
            self.content_address = _text(content_address, "archive content address")
        else:
            self.content_address = _address(content_address, "archive content address", ARCHIVE_PREFIX)
        self._raw = dict(raw or {})
        self._federation = federation
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("archive version or boundary is unsupported")
        if self.artifact_count != len(EMBEDDED_FILES) or self.files != EMBEDDED_FILES or len(self.artifacts) != len(EMBEDDED_FILES) or tuple(item.index for item in self.artifacts) != tuple(range(len(EMBEDDED_FILES))) or tuple(item.name for item in self.artifacts) != EMBEDDED_FILES:
            raise ValidationError("archive embedded member vocabulary is not exact")
        if sum(item.size for item in self.artifacts) <= 0:
            raise ValidationError("archive artifact sizes must be positive")
        if not _public(self.to_dict()):
            raise ValidationError("archive crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_archive(self) != self.content_address:
            raise ValidationError("archive content address does not replay")
        if self._federation is not None:
            checked = federation_model.federation_from_mapping(self._federation.to_dict())
            if checked.federation_id != self.federation_id or checked.content_address != self.federation_address:
                raise ValidationError("archive federation identity does not replay")
        if self._raw:
            if set(self._raw) != set(EMBEDDED_FILES):
                raise ValidationError("archive embedded member set is incomplete")
            for item in self.artifacts:
                raw = self._raw[item.name]
                if len(raw) != item.size or hash_bytes(raw, prefix=ARTIFACT_PREFIX) != item.hash:
                    raise ValidationError("archive artifact receipt does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_id": self.archive_id, "version": self.version, "boundary": self.boundary, "federation_id": self.federation_id, "federation_address": self.federation_address, "artifact_count": self.artifact_count, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "archive_size": self.archive_size, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("archive_id", "version", "boundary", "federation_id", "federation_address", "artifact_count", "archive_size", "content_address")}

    def embedded_bytes(self) -> Mapping[str, bytes]:
        if not self._raw:
            raise ValidationError("archive embedded bytes are unavailable")
        return dict(self._raw)

    @property
    def federation(self) -> federation_model.RecoveryExecutionRuntimeRegistryFederation | None:
        return self._federation


def address_archive(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchive):
        raise ValidationError("archive address requires a typed archive")
    return content_hash(value.to_dict() | {"content_address": None, "archive_size": None}, prefix=ARCHIVE_PREFIX)


def _artifact(index: int, name: str, raw: bytes) -> RecoveryExecutionRuntimeRegistryFederationArchiveArtifact:
    return RecoveryExecutionRuntimeRegistryFederationArchiveArtifact(index, name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX))


def build_archive(value: federation_model.RecoveryExecutionRuntimeRegistryFederation, *, archive_id: str = DEFAULT_ARCHIVE_ID) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    if not isinstance(value, federation_model.RecoveryExecutionRuntimeRegistryFederation):
        raise ValidationError("archive builder requires a typed federation")
    federation = federation_model.federation_from_mapping(value.to_dict())
    raw = _embedded_federation(federation)
    artifacts = tuple(_artifact(index, name, raw[name]) for index, name in enumerate(EMBEDDED_FILES))
    body = {"archive_id": archive_id, "version": VERSION, "boundary": BOUNDARY, "federation_id": federation.federation_id, "federation_address": federation.content_address, "artifact_count": len(EMBEDDED_FILES), "files": EMBEDDED_FILES, "artifacts": artifacts, "archive_size": 1}
    provisional = RecoveryExecutionRuntimeRegistryFederationArchive(**body, content_address="pending:archive", raw=raw, federation=federation)
    candidate = RecoveryExecutionRuntimeRegistryFederationArchive(**body, content_address=address_archive(provisional), raw=raw, federation=federation)
    archive_size = len(_zip_bytes_unchecked(candidate))
    return RecoveryExecutionRuntimeRegistryFederationArchive(**(body | {"archive_size": archive_size}), content_address=candidate.content_address, raw=raw, federation=federation)


def build_archive_from_directory(directory: str | Path, *, archive_id: str = DEFAULT_ARCHIVE_ID) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    return build_archive(federation_model.load_federation(directory), archive_id=archive_id)


def archive_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    value = _mapping(value, "runtime registry federation archive")
    _strict(value, set(RecoveryExecutionRuntimeRegistryFederationArchive.FIELDS), "runtime registry federation archive")
    artifacts = tuple(RecoveryExecutionRuntimeRegistryFederationArchiveArtifact.from_mapping(item) for item in _sequence(value["artifacts"], "archive artifacts", len(EMBEDDED_FILES)))
    return verify_archive(RecoveryExecutionRuntimeRegistryFederationArchive(value["archive_id"], value["version"], value["boundary"], value["federation_id"], value["federation_address"], value["artifact_count"], value["files"], artifacts, value["archive_size"], value["content_address"]))


def verify_archive(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    if not isinstance(value, RecoveryExecutionRuntimeRegistryFederationArchive):
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


def _archive_manifest(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "archive_id": value.archive_id, "federation_id": value.federation_id, "federation_address": value.federation_address, "artifact_count": value.artifact_count, "files": value.files, "artifacts": tuple(item.to_dict() for item in value.artifacts), "archive_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> dict[str, Any]:
    return _archive_manifest(verify_archive(value))


def _zip_bytes_unchecked(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> bytes:
    raw = value.embedded_bytes()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(ARCHIVE_MANIFEST_NAME), canonical_bytes(_archive_manifest(value)))
        for name in EMBEDDED_FILES:
            archive.writestr(_zip_info(name), raw[name])
        archive.comment = b""
    return stream.getvalue()


def archive_bytes(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> bytes:
    value = verify_archive(value)
    raw = _zip_bytes_unchecked(value)
    if len(raw) != value.archive_size:
        raise ValidationError("archive byte size does not replay")
    return raw


def archive_json(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> str:
    return canonical_json(archive_from_mapping(value.to_dict()).to_dict())


def _write_atomic_file(destination: Path, raw: bytes, *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("archive destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_file():
            raise ValidationError("archive destination must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".runtime-registry-federation-", suffix=".zip", dir=str(destination.parent))
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ValidationError("archive destination could not be written") from error
    return destination


def write_archive(value: RecoveryExecutionRuntimeRegistryFederationArchive, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_file(Path(destination), archive_bytes(value), overwrite=overwrite)


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
                raise ValidationError("archive embedded bytes exceed the maximum bound")
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


def load_archive(source: str | Path | bytes) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    raw, physical_size = _read_archive_bytes(source)
    decoded = _decode_canonical(raw)
    manifest = decoded[ARCHIVE_MANIFEST_NAME]
    manifest_fields = {"version", "boundary", "archive_id", "federation_id", "federation_address", "artifact_count", "files", "artifacts", "archive_address", "manifest_address"}
    _strict(manifest, manifest_fields, "archive manifest")
    if manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("archive manifest address does not replay")
    federation = federation_model.federation_from_mapping(decoded[EMBEDDED_PREFIX + "federation.json"])
    expected = _embedded_federation(federation)
    for name, expected_raw in expected.items():
        if raw[name] != expected_raw:
            raise ValidationError("archive federation projection does not replay")
    artifacts = tuple(RecoveryExecutionRuntimeRegistryFederationArchiveArtifact.from_mapping(item) for item in _sequence(manifest["artifacts"], "archive artifacts", len(EMBEDDED_FILES)))
    value = RecoveryExecutionRuntimeRegistryFederationArchive(manifest["archive_id"], manifest["version"], manifest["boundary"], manifest["federation_id"], manifest["federation_address"], manifest["artifact_count"], manifest["files"], artifacts, physical_size, manifest["archive_address"], raw={name: raw[name] for name in EMBEDDED_FILES}, federation=federation)
    if canonical_bytes(_archive_manifest(value)) != raw[ARCHIVE_MANIFEST_NAME]:
        raise ValidationError("archive manifest or address does not replay")
    return verify_archive(value)


def load_archive_bytes(raw: bytes) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    return load_archive(raw)


def verify_archive_file(source: str | Path) -> RecoveryExecutionRuntimeRegistryFederationArchive:
    return load_archive(source)


def archive_csv(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> str:
    value = verify_archive(value)
    stream = io.StringIO(newline="")
    fields = ("archive_id", "federation_id", "federation_address", "artifact_count", "archive_size", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.summary()[field] for field in fields})
    return stream.getvalue()


def render_archive_markdown(value: RecoveryExecutionRuntimeRegistryFederationArchive) -> str:
    value = verify_archive(value)
    lines = ["# Runtime Registry Federation Archive", "", f"- Archive: `{value.archive_id}`", f"- Federation: `{value.federation_id}`", f"- Federation address: `{value.federation_address}`", f"- ZIP bytes: `{value.archive_size}`", f"- Address: `{value.content_address}`", "", "| index | embedded file | bytes | receipt |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| `{item.index}` | `{item.name}` | `{item.size}` | `{item.hash}` |" for item in value.artifacts)
    return "\n".join(lines) + "\n"


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive artifact", "type": "object", "additionalProperties": False, "required": list(RecoveryExecutionRuntimeRegistryFederationArchiveArtifact.FIELDS), "properties": {"index": {"type": "integer", "minimum": 0, "maximum": len(EMBEDDED_FILES) - 1}, "name": {"type": "string", "enum": list(EMBEDDED_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "archive_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "artifact_count": {"type": "integer", "const": len(EMBEDDED_FILES)}, "files": {"const": list(EMBEDDED_FILES)}, "artifacts": {"type": "array", "minItems": len(EMBEDDED_FILES), "maxItems": len(EMBEDDED_FILES), "items": artifact_schema()}, "archive_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive manifest", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def archive_schema() -> dict[str, Any]:
    fields = {"archive_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "federation_id": {"type": "string"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "artifact_count": {"type": "integer", "const": len(EMBEDDED_FILES)}, "files": {"const": list(EMBEDDED_FILES)}, "artifacts": {"type": "array", "minItems": len(EMBEDDED_FILES), "maxItems": len(EMBEDDED_FILES), "items": artifact_schema()}, "archive_size": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime registry federation archive", "type": "object", "additionalProperties": False, "required": list(RecoveryExecutionRuntimeRegistryFederationArchive.FIELDS), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "archive_prefix": ARCHIVE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "files": list(FILES), "embedded_files": list(EMBEDDED_FILES), "zip_epoch": ZIP_EPOCH, "max_archive_bytes": MAX_ARCHIVE_BYTES, "features": ["deterministic ZIP bytes", "exact five-file federation embedding", "canonical manifest replay", "byte receipt verification", "atomic file replacement", "traversal, symlink, encryption, and comment rejection", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "private_metadata": False}}


__all__ = ["ARCHIVE_MANIFEST_NAME", "ARCHIVE_PREFIX", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_ARCHIVE_ID", "EMBEDDED_FILES", "FILES", "MANIFEST_PREFIX", "MAX_ARCHIVE_BYTES", "RecoveryExecutionRuntimeRegistryFederationArchive", "RecoveryExecutionRuntimeRegistryFederationArchiveArtifact", "VERSION", "address_archive", "archive_bytes", "archive_csv", "archive_from_mapping", "archive_json", "archive_schema", "artifact_schema", "build_archive", "build_archive_from_directory", "capabilities", "load_archive", "load_archive_bytes", "manifest_document", "manifest_schema", "render_archive_markdown", "verify_archive", "verify_archive_file", "write_archive"]

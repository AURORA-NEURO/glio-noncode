"""Deterministic ZIP transport for execution-ledger registry history diffs."""

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

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = diff_model.VERSION + "-archive-v1"
BOUNDARY = diff_model.BOUNDARY + "_archive"
ARCHIVE_PREFIX = diff_model.DIFF_PREFIX + "-archive"
MANIFEST_PREFIX = ARCHIVE_PREFIX + "-manifest"
ARTIFACT_PREFIX = ARCHIVE_PREFIX + "-artifact"
ARCHIVE_MANIFEST_NAME = "manifest.json"
EMBEDDED_PREFIX = "history-diff/"
EMBEDDED_FILES = tuple(EMBEDDED_PREFIX + name for name in diff_model.FILES)
FILES = (ARCHIVE_MANIFEST_NAME, *EMBEDDED_FILES)
DEFAULT_ARCHIVE_ID = ARCHIVE_PREFIX
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = diff_model.MAX_DIFF_BYTES
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 512, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if value and (":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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


def _embedded_name(value: Any) -> str:
    value = _text(value, "history diff archive embedded member", 256)
    if not value.startswith(EMBEDDED_PREFIX) or value not in EMBEDDED_FILES:
        raise ValidationError("history diff archive member is outside the exact namespace")
    return value


def _regular_zip_member(info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or info.flag_bits & 0x1 or info.filename.startswith("/") or "\\" in info.filename:
        return False
    if any(part in ("", ".", "..") for part in info.filename.split("/")):
        return False
    if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
        return False
    return True


def _public(value: Any) -> bool:
    return diff_model._public(value)


def _embedded_diff(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff) -> dict[str, bytes]:
    checked = diff_model.verify_diff(value)
    items = diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffItems(checked.items, diff_model.address_items(checked.items))
    documents = {
        "manifest.json": checked.manifest.to_dict(),
        "diff.json": checked.to_dict(),
        "items.json": items.to_dict(),
        "summary.json": checked.summary.to_dict(),
    }
    return {EMBEDDED_PREFIX + name: canonical_bytes(documents[name]) for name in diff_model.FILES}


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact:
    """One ordered, addressed byte receipt for an embedded diff member."""

    FIELDS = ("index", "name", "size", "hash")

    def __init__(self, index: int, name: str, size: int, hash: str) -> None:
        self.index = _count(index, "history diff archive artifact index", len(EMBEDDED_FILES))
        self.name = _embedded_name(name)
        self.size = _count(size, "history diff archive artifact size", MAX_MEMBER_BYTES, lower=1)
        self.hash = _address(hash, "history diff archive artifact hash", ARTIFACT_PREFIX)
        if self.index >= len(EMBEDDED_FILES) or self.name != EMBEDDED_FILES[self.index]:
            raise ValidationError("history diff archive artifact order is not exact")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history diff archive artifact")
        _strict(value, set(cls.FIELDS), "history diff archive artifact")
        return cls(value["index"], value["name"], value["size"], value["hash"])


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive:
    """A public addressed envelope around one verified history diff."""

    FIELDS = ("archive_id", "version", "boundary", "diff_id", "diff_address", "artifact_count", "files", "artifacts", "archive_size", "content_address")

    def __init__(self, archive_id: str, version: str, boundary: str, diff_id: str, diff_address: str, artifact_count: int, files: Sequence[str], artifacts: Sequence[Mapping[str, Any] | ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact], archive_size: int, content_address: str, raw: Mapping[str, bytes] | None = None, diff: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff | None = None) -> None:
        self.archive_id = _label(archive_id, "history diff archive ID")
        self.version = _text(version, "history diff archive version", 2048)
        self.boundary = _text(boundary, "history diff archive boundary", 2048)
        self.diff_id = _label(diff_id, "history diff archive diff ID")
        self.diff_address = _address(diff_address, "history diff archive diff address", diff_model.DIFF_PREFIX)
        self.artifact_count = _count(artifact_count, "history diff archive artifact count", len(EMBEDDED_FILES), lower=1)
        self.files = tuple(_embedded_name(item) for item in _sequence(files, "history diff archive files", len(EMBEDDED_FILES)))
        self.artifacts = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact.from_mapping(item) for item in _sequence(artifacts, "history diff archive artifacts", len(EMBEDDED_FILES)))
        self.archive_size = _count(archive_size, "history diff archive size", MAX_ARCHIVE_BYTES, lower=1)
        self.content_address = _address(content_address, "history diff archive content address", ARCHIVE_PREFIX, allow_pending=True)
        self._raw = dict(raw or {})
        self._diff = diff
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff archive version or boundary is unsupported")
        if self.artifact_count != len(EMBEDDED_FILES) or self.files != EMBEDDED_FILES or len(self.artifacts) != len(EMBEDDED_FILES):
            raise ValidationError("history diff archive member vocabulary is not exact")
        if tuple(item.index for item in self.artifacts) != tuple(range(len(EMBEDDED_FILES))) or tuple(item.name for item in self.artifacts) != EMBEDDED_FILES:
            raise ValidationError("history diff archive artifact order is not exact")
        if sum(item.size for item in self.artifacts) <= 0:
            raise ValidationError("history diff archive artifact sizes must be positive")
        if not _public(self.to_dict()):
            raise ValidationError("history diff archive crosses its public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_archive(self) != self.content_address:
            raise ValidationError("history diff archive address does not replay")
        if self._diff is not None:
            checked = diff_model.verify_diff(self._diff)
            if checked.diff_id != self.diff_id or checked.content_address != self.diff_address:
                raise ValidationError("history diff archive nested identity does not replay")
        if self._raw:
            if set(self._raw) != set(EMBEDDED_FILES):
                raise ValidationError("history diff archive embedded member set is incomplete")
            for item in self.artifacts:
                raw = self._raw[item.name]
                if len(raw) != item.size or hash_bytes(raw, prefix=ARTIFACT_PREFIX) != item.hash:
                    raise ValidationError("history diff archive byte receipt does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_id": self.archive_id, "version": self.version, "boundary": self.boundary, "diff_id": self.diff_id, "diff_address": self.diff_address, "artifact_count": self.artifact_count, "files": self.files, "artifacts": tuple(item.to_dict() for item in self.artifacts), "archive_size": self.archive_size, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("archive_id", "version", "boundary", "diff_id", "diff_address", "artifact_count", "archive_size", "content_address")}

    def embedded_bytes(self) -> Mapping[str, bytes]:
        if not self._raw:
            raise ValidationError("history diff archive embedded bytes are unavailable")
        return dict(self._raw)

    @property
    def diff(self):
        return self._diff


def address_archive(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive):
        raise ValidationError("history diff archive address requires a typed archive")
    return content_hash(value.to_dict() | {"content_address": None, "archive_size": None}, prefix=ARCHIVE_PREFIX)


def _artifact(index: int, name: str, raw: bytes):
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact(index, name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX))


def build_archive(value: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiff, *, archive_id: str = DEFAULT_ARCHIVE_ID):
    checked = diff_model.verify_diff(value)
    raw = _embedded_diff(checked)
    artifacts = tuple(_artifact(index, name, raw[name]) for index, name in enumerate(EMBEDDED_FILES))
    body = {"archive_id": archive_id, "version": VERSION, "boundary": BOUNDARY, "diff_id": checked.diff_id, "diff_address": checked.content_address, "artifact_count": len(EMBEDDED_FILES), "files": EMBEDDED_FILES, "artifacts": artifacts, "archive_size": 1}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive(**body, content_address="pending:archive", raw=raw, diff=checked)
    content_address = address_archive(provisional)
    candidate = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive(**body, content_address=content_address, raw=raw, diff=checked)
    archive_size = len(_zip_bytes_unchecked(candidate))
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive(**(body | {"archive_size": archive_size}), content_address=content_address, raw=raw, diff=checked)


def build_archive_from_directory(directory: str | Path, *, archive_id: str = DEFAULT_ARCHIVE_ID):
    return build_archive(diff_model.load_diff(directory), archive_id=archive_id)


def archive_from_mapping(value: Mapping[str, Any]):
    value = _mapping(value, "history diff archive")
    _strict(value, set(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive.FIELDS), "history diff archive")
    artifacts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact.from_mapping(item) for item in _sequence(value["artifacts"], "history diff archive artifacts", len(EMBEDDED_FILES)))
    result = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive(value["archive_id"], value["version"], value["boundary"], value["diff_id"], value["diff_address"], value["artifact_count"], value["files"], artifacts, value["archive_size"], value["content_address"])
    return verify_archive(result)


def verify_archive(value):
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive):
        raise ValidationError("history diff archive verification requires a typed archive")
    value._validate()
    if not value.content_address.startswith("pending:") and not value.content_address.endswith(":pending") and address_archive(value) != value.content_address:
        raise ValidationError("history diff archive address verification failed")
    return value


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    info.comment = b""
    return info


def _archive_manifest(value) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "archive_id": value.archive_id, "diff_id": value.diff_id, "diff_address": value.diff_address, "artifact_count": value.artifact_count, "files": value.files, "artifacts": tuple(item.to_dict() for item in value.artifacts), "archive_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value):
    return _archive_manifest(verify_archive(value))


def _zip_bytes_unchecked(value) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(ARCHIVE_MANIFEST_NAME), canonical_bytes(_archive_manifest(value)))
        raw = value.embedded_bytes()
        for name in EMBEDDED_FILES:
            archive.writestr(_zip_info(name), raw[name])
        archive.comment = b""
    return stream.getvalue()


def archive_bytes(value) -> bytes:
    value = verify_archive(value)
    raw = _zip_bytes_unchecked(value)
    if len(raw) != value.archive_size:
        raise ValidationError("history diff archive byte size does not replay")
    return raw


def archive_json(value) -> str:
    return canonical_json(archive_from_mapping(value.to_dict()).to_dict())


def _write_atomic_file(destination: Path, raw: bytes, *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("history diff archive destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_file():
            raise ValidationError("history diff archive destination must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".history-diff-archive-", suffix=".zip", dir=str(destination.parent))
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, destination)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ValidationError("history diff archive destination could not be written") from error
    return destination


def write_archive(value, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_file(Path(destination), archive_bytes(value), overwrite=overwrite)


def _read_archive_bytes(source: str | Path | bytes) -> tuple[dict[str, bytes], int]:
    close_stream = False
    if isinstance(source, bytes):
        physical_size = len(source)
        if physical_size > MAX_ARCHIVE_BYTES:
            raise ValidationError("history diff archive exceeds the maximum byte bound")
        stream: Any = io.BytesIO(source)
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise ValidationError("history diff archive input must be a regular file")
        physical_size = path.stat().st_size
        if physical_size > MAX_ARCHIVE_BYTES:
            raise ValidationError("history diff archive exceeds the maximum byte bound")
        stream = path.open("rb")
        close_stream = True
    try:
        try:
            archive = zipfile.ZipFile(stream, "r")
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            raise ValidationError("history diff archive input is not a valid ZIP") from error
        with archive:
            infos = archive.infolist()
            names = tuple(info.filename for info in infos)
            if archive.comment or names != FILES or any(not _regular_zip_member(info) for info in infos):
                raise ValidationError("history diff archive member vocabulary or safety contract failed")
            if any(info.file_size > MAX_MEMBER_BYTES for info in infos) or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
                raise ValidationError("history diff archive embedded bytes exceed the maximum bound")
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
            decoded[name] = _mapping(value, f"history diff archive member {name}")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("history diff archive contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("history diff archive contains non-canonical JSON")
    return decoded


def load_archive(source: str | Path | bytes):
    raw, physical_size = _read_archive_bytes(source)
    decoded = _decode_canonical(raw)
    manifest = decoded[ARCHIVE_MANIFEST_NAME]
    manifest_fields = {"version", "boundary", "archive_id", "diff_id", "diff_address", "artifact_count", "files", "artifacts", "archive_address", "manifest_address"}
    _strict(manifest, manifest_fields, "history diff archive manifest")
    if manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("history diff archive manifest address does not replay")
    diff = diff_model.diff_from_mapping(decoded[EMBEDDED_PREFIX + "diff.json"])
    expected = _embedded_diff(diff)
    for name, expected_raw in expected.items():
        if raw[name] != expected_raw:
            raise ValidationError("history diff archive nested projection does not replay")
    artifacts = tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact.from_mapping(item) for item in _sequence(manifest["artifacts"], "history diff archive artifacts", len(EMBEDDED_FILES)))
    value = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive(manifest["archive_id"], manifest["version"], manifest["boundary"], manifest["diff_id"], manifest["diff_address"], manifest["artifact_count"], manifest["files"], artifacts, physical_size, manifest["archive_address"], raw={name: raw[name] for name in EMBEDDED_FILES}, diff=diff)
    if canonical_bytes(_archive_manifest(value)) != raw[ARCHIVE_MANIFEST_NAME]:
        raise ValidationError("history diff archive manifest or address does not replay")
    return verify_archive(value)


def load_archive_bytes(raw: bytes):
    return load_archive(raw)


def verify_archive_file(source: str | Path):
    return load_archive(source)


def archive_csv(value) -> str:
    value = verify_archive(value)
    fields = ("archive_id", "diff_id", "diff_address", "artifact_count", "archive_size", "content_address")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.summary()[field] for field in fields})
    return stream.getvalue()


def render_archive_markdown(value) -> str:
    value = verify_archive(value)
    lines = ["# Execution-ledger registry history diff archive", "", f"- Archive: `{value.archive_id}`", f"- Diff: `{value.diff_id}`", f"- Diff address: `{value.diff_address}`", f"- ZIP bytes: `{value.archive_size}`", f"- Address: `{value.content_address}`", "", "| index | embedded member | bytes | receipt |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| `{item.index}` | `{item.name}` | `{item.size}` | `{item.hash}` |" for item in value.artifacts)
    return "\n".join(lines) + "\n"


def artifact_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact", "type": "object", "additionalProperties": False, "required": list(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact.FIELDS), "properties": {"index": {"type": "integer", "minimum": 0, "maximum": len(EMBEDDED_FILES) - 1}, "name": {"type": "string", "enum": list(EMBEDDED_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "archive_id": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "artifact_count": {"type": "integer", "const": len(EMBEDDED_FILES)}, "files": {"const": list(EMBEDDED_FILES)}, "artifacts": {"type": "array", "minItems": len(EMBEDDED_FILES), "maxItems": len(EMBEDDED_FILES), "items": artifact_schema()}, "archive_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchiveManifest", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def archive_schema() -> dict[str, Any]:
    fields = {"archive_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "diff_id": {"type": "string"}, "diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "artifact_count": {"type": "integer", "const": len(EMBEDDED_FILES)}, "files": {"const": list(EMBEDDED_FILES)}, "artifacts": {"type": "array", "minItems": len(EMBEDDED_FILES), "maxItems": len(EMBEDDED_FILES), "items": artifact_schema()}, "archive_size": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + ARCHIVE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ExecutionLedgerRuntimeRegistryHistoryDiffArchive", "type": "object", "additionalProperties": False, "required": list(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive.FIELDS), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "archive_prefix": ARCHIVE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "artifact_prefix": ARTIFACT_PREFIX, "files": list(FILES), "embedded_files": list(EMBEDDED_FILES), "zip_epoch": ZIP_EPOCH, "max_archive_bytes": MAX_ARCHIVE_BYTES, "max_member_bytes": MAX_MEMBER_BYTES, "features": ["deterministic ZIP bytes", "exact four-file history-diff embedding", "canonical outer manifest", "per-member byte receipts", "atomic file replacement", "traversal, symlink, encryption, and comment rejection", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["ARCHIVE_MANIFEST_NAME", "ARCHIVE_PREFIX", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_ARCHIVE_ID", "EMBEDDED_FILES", "FILES", "MANIFEST_PREFIX", "MAX_ARCHIVE_BYTES", "MAX_MEMBER_BYTES", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchive", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryHistoryDiffArchiveArtifact", "VERSION", "address_archive", "archive_bytes", "archive_csv", "archive_from_mapping", "archive_json", "archive_schema", "artifact_schema", "build_archive", "build_archive_from_directory", "capabilities", "load_archive", "load_archive_bytes", "manifest_document", "manifest_schema", "render_archive_markdown", "verify_archive", "verify_archive_file", "write_archive"]

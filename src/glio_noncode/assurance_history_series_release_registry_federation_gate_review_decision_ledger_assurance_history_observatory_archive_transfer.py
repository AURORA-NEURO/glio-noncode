"""Resumable, deterministic chunk transport for verified observatory archives.

An archive ZIP is a convenient artifact for a filesystem, but a production
handoff often crosses object storage, upload APIs, or a constrained network.
This module adds a second transport boundary without making chunks a new
source of truth. A transfer manifest addresses the already-verified archive,
records every byte range, and records every chunk hash. A transfer can be
written as an exact directory, loaded fail-closed, queried while incomplete,
and reassembled only after every receipt and the nested archive contract have
been independently verified.

The public surface deliberately contains no paths, attribution metadata,
agent fields, language fields, or transport-local secrets. All JSON is
canonical, all chunk order is explicit, and equal archive bytes with equal
transfer options produce equal transfer bytes and directory contents.
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

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = archive_model.VERSION + "-transfer-v1"
BOUNDARY = archive_model.BOUNDARY + "_transfer"
TRANSFER_PREFIX = archive_model.ARCHIVE_PREFIX + "-transfer"
TRANSFER_QUERY_PREFIX = TRANSFER_PREFIX + "-query"
TRANSFER_CHUNK_PREFIX = TRANSFER_PREFIX + "-chunk"
TRANSFER_MANIFEST_PREFIX = TRANSFER_PREFIX + "-manifest"
TRANSFER_PROGRESS_PREFIX = TRANSFER_PREFIX + "-progress"
MANIFEST_NAME = "manifest.json"
CHUNK_PREFIX = "chunks/"
CHUNK_NAME_PREFIX = CHUNK_PREFIX + "chunk-"
CHUNK_SUFFIX = ".bin"
DEFAULT_TRANSFER_ID = "glio-noncode-assurance-history-observatory-archive-transfer"
DEFAULT_CHUNK_SIZE = 64 * 1024
MIN_CHUNK_SIZE = 256
MAX_CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNKS = 4096
MAX_TRANSFER_BYTES = 128 * 1024 * 1024
DEFAULT_LIMIT = 50
MAX_QUERY_ITEMS = min(MAX_CHUNKS, archive_model.MAX_QUERY_ITEMS * 8)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, *, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _public(value: Any) -> bool:
    return archive_model._public(value)


def _chunk_size(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_CHUNK_SIZE or value > MAX_CHUNK_SIZE:
        raise ValidationError(f"chunk size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")
    return value


def chunk_name(index: int) -> str:
    _count(index, "chunk index", MAX_CHUNKS - 1)
    return f"{CHUNK_NAME_PREFIX}{index:08d}{CHUNK_SUFFIX}"


class ArchiveChunk:
    """A public byte-range receipt within a transfer."""

    def __init__(self, index: int, offset: int, size: int, content_address: str) -> None:
        self.index = index
        self.offset = offset
        self.size = size
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.index, "chunk index", MAX_CHUNKS - 1)
        _count(self.offset, "chunk offset", MAX_TRANSFER_BYTES)
        _count(self.size, "chunk size", MAX_CHUNK_SIZE, positive=True)
        _address(self.content_address, "chunk content address", prefix=TRANSFER_CHUNK_PREFIX)
        if self.offset + self.size > MAX_TRANSFER_BYTES:
            raise ValidationError("chunk range exceeds the transfer byte bound")

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "offset": self.offset, "size": self.size, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ArchiveChunk":
        value = _mapping(value, "archive transfer chunk")
        _strict(value, {"index", "offset", "size", "content_address"}, "archive transfer chunk")
        return cls(value["index"], value["offset"], value["size"], value["content_address"])


class ArchiveTransfer:
    """A verified archive transfer manifest with optional chunk bytes."""

    def __init__(self, transfer_id: str, version: str, boundary: str, archive_address: str, archive_size: int, chunk_size: int, chunk_count: int, chunks: Sequence[ArchiveChunk], content_address: str, payload: Mapping[int, bytes] | None = None) -> None:
        self.transfer_id = transfer_id
        self.version = version
        self.boundary = boundary
        self.archive_address = archive_address
        self.archive_size = archive_size
        self.chunk_size = chunk_size
        self.chunk_count = chunk_count
        self.chunks = tuple(chunks)
        self.content_address = content_address
        self._payload = dict(payload or {})
        self._validate()

    def _validate(self) -> None:
        _text(self.transfer_id, "transfer ID")
        _text(self.version, "transfer version", 1024)
        _text(self.boundary, "transfer boundary", 512)
        _address(self.archive_address, "transfer archive address", prefix=archive_model.ARCHIVE_PREFIX)
        _count(self.archive_size, "archive size", MAX_TRANSFER_BYTES, positive=True)
        _chunk_size(self.chunk_size)
        _count(self.chunk_count, "chunk count", MAX_CHUNKS, positive=True)
        if self.chunk_count != len(self.chunks) or self.chunk_count != (self.archive_size + self.chunk_size - 1) // self.chunk_size:
            raise ValidationError("transfer chunk count is inconsistent with the byte range")
        expected_offset = 0
        for expected_index, chunk in enumerate(self.chunks):
            if not isinstance(chunk, ArchiveChunk) or chunk.index != expected_index or chunk.offset != expected_offset:
                raise ValidationError("transfer chunk ordering or offsets are invalid")
            if chunk.size != min(self.chunk_size, self.archive_size - expected_offset):
                raise ValidationError("transfer chunk size is inconsistent with the byte range")
            expected_offset += chunk.size
        if expected_offset != self.archive_size:
            raise ValidationError("transfer byte ranges do not conserve archive size")
        _address(self.content_address, "transfer content address")
        if not _public(self.to_dict()):
            raise ValidationError("transfer crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_transfer(self) != self.content_address:
            raise ValidationError("transfer content address mismatch")
        if self._payload:
            if set(self._payload) != set(range(self.chunk_count)):
                raise ValidationError("transfer payload chunks are incomplete")
            for chunk in self.chunks:
                raw = self._payload[chunk.index]
                if not isinstance(raw, bytes) or len(raw) != chunk.size or hash_bytes(raw, prefix=TRANSFER_CHUNK_PREFIX) != chunk.content_address:
                    raise ValidationError("transfer payload chunk receipt mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_id": self.transfer_id, "version": self.version, "boundary": self.boundary, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_size": self.chunk_size, "chunk_count": self.chunk_count, "chunks": tuple(chunk.to_dict() for chunk in self.chunks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("transfer_id", "version", "boundary", "archive_address", "archive_size", "chunk_size", "chunk_count", "content_address")}

    def payload_bytes(self) -> Mapping[int, bytes]:
        if not self._payload:
            raise ValidationError("transfer chunk bytes are unavailable")
        return dict(self._payload)


class TransferAssemblyProgress:
    """Addressed receipt for the current state of an incremental assembly."""

    def __init__(self, transfer_address: str, archive_address: str, archive_size: int, chunk_count: int, received_indices: Sequence[int], missing_indices: Sequence[int], received_bytes: int, complete: bool, content_address: str) -> None:
        self.transfer_address = transfer_address
        self.archive_address = archive_address
        self.archive_size = archive_size
        self.chunk_count = chunk_count
        self.received_indices = tuple(received_indices)
        self.missing_indices = tuple(missing_indices)
        self.received_bytes = received_bytes
        self.complete = complete
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.transfer_address, "progress transfer address", prefix=TRANSFER_PREFIX)
        _address(self.archive_address, "progress archive address", prefix=archive_model.ARCHIVE_PREFIX)
        _count(self.archive_size, "progress archive size", MAX_TRANSFER_BYTES, positive=True)
        _count(self.chunk_count, "progress chunk count", MAX_CHUNKS, positive=True)
        received = tuple(self.received_indices)
        missing = tuple(self.missing_indices)
        if received != tuple(sorted(received)) or missing != tuple(sorted(missing)) or set(received) & set(missing) or set(received) | set(missing) != set(range(self.chunk_count)):
            raise ValidationError("progress chunk index sets are inconsistent")
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= self.chunk_count for index in received + missing):
            raise ValidationError("progress chunk index is outside the transfer")
        _count(self.received_bytes, "progress received bytes", self.archive_size)
        if self.complete != (not missing) or (self.complete and self.received_bytes != self.archive_size):
            raise ValidationError("progress completion does not match received bytes")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "progress content address")
        else:
            _address(self.content_address, "progress content address", prefix=TRANSFER_PROGRESS_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_progress(self) != self.content_address):
            raise ValidationError("progress content address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_count": self.chunk_count, "received_indices": self.received_indices, "missing_indices": self.missing_indices, "received_bytes": self.received_bytes, "complete": self.complete, "content_address": self.content_address}


def address_progress(value: TransferAssemblyProgress) -> str:
    if not isinstance(value, TransferAssemblyProgress):
        raise ValidationError("progress address requires a typed progress receipt")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSFER_PROGRESS_PREFIX)


def _progress_from_parts(value: ArchiveTransfer, parts: Mapping[int, bytes]) -> TransferAssemblyProgress:
    received = tuple(sorted(parts))
    missing = tuple(index for index in range(value.chunk_count) if index not in parts)
    received_bytes = sum(len(raw) for raw in parts.values())
    provisional = TransferAssemblyProgress(value.content_address, value.archive_address, value.archive_size, value.chunk_count, received, missing, received_bytes, not missing, "pending:progress")
    return TransferAssemblyProgress(value.content_address, value.archive_address, value.archive_size, value.chunk_count, received, missing, received_bytes, not missing, address_progress(provisional))


class TransferAssembler:
    """Idempotent in-memory chunk receiver with addressed progress receipts."""

    def __init__(self, value: ArchiveTransfer) -> None:
        if not isinstance(value, ArchiveTransfer):
            raise ValidationError("assembler requires a typed transfer")
        value._validate()
        self.value = value
        self._parts: dict[int, bytes] = {}

    def add_chunk(self, index: int, raw: bytes) -> TransferAssemblyProgress:
        _count(index, "chunk index", self.value.chunk_count - 1)
        if not isinstance(raw, bytes):
            raise ValidationError("received chunk must be bytes")
        expected = self.value.chunks[index]
        if len(raw) != expected.size or address_chunk(raw) != expected.content_address:
            raise ValidationError("received chunk does not match its receipt")
        if index in self._parts and self._parts[index] != raw:
            raise ValidationError("received chunk conflicts with an existing chunk")
        self._parts[index] = raw
        return self.progress()

    def add_chunks(self, parts: Mapping[int, bytes]) -> TransferAssemblyProgress:
        if not isinstance(parts, Mapping):
            raise ValidationError("received chunks must be a mapping")
        for index in sorted(parts):
            self.add_chunk(index, parts[index])
        return self.progress()

    def received_indices(self) -> tuple[int, ...]:
        return tuple(sorted(self._parts))

    def missing_indices(self) -> tuple[int, ...]:
        return tuple(index for index in range(self.value.chunk_count) if index not in self._parts)

    def is_complete(self) -> bool:
        return not self.missing_indices()

    def progress(self) -> TransferAssemblyProgress:
        return _progress_from_parts(self.value, self._parts)

    def finalize(self) -> bytes:
        if not self.is_complete():
            raise ValidationError("transfer cannot be finalized while chunks are missing")
        return assemble_archive_bytes(self.value, self._parts)

    def write_partial(self, destination: str | Path, *, overwrite: bool = False) -> Path:
        return write_partial_transfer(self, destination, overwrite=overwrite)


def address_transfer(value: ArchiveTransfer) -> str:
    if not isinstance(value, ArchiveTransfer):
        raise ValidationError("transfer address requires a typed transfer")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSFER_PREFIX)


def address_chunk(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise ValidationError("chunk content must be non-empty bytes")
    return hash_bytes(raw, prefix=TRANSFER_CHUNK_PREFIX)


def _build_from_parts(raw: bytes, *, archive_value: archive_model.ObservatoryArchive, transfer_id: str | None, chunk_size: int) -> ArchiveTransfer:
    if not isinstance(raw, bytes):
        raise ValidationError("archive bytes must be bytes")
    if len(raw) == 0 or len(raw) > MAX_TRANSFER_BYTES:
        raise ValidationError("archive bytes are outside the transfer bound")
    chunk_size = _chunk_size(chunk_size)
    chunks_raw = {index: raw[offset:offset + chunk_size] for index, offset in enumerate(range(0, len(raw), chunk_size))}
    if len(chunks_raw) > MAX_CHUNKS:
        raise ValidationError("archive requires too many chunks")
    chunks = tuple(ArchiveChunk(index, index * chunk_size, len(part), address_chunk(part)) for index, part in chunks_raw.items())
    body = {"transfer_id": DEFAULT_TRANSFER_ID if transfer_id is None else _text(transfer_id, "transfer ID"), "version": VERSION, "boundary": BOUNDARY, "archive_address": archive_value.content_address, "archive_size": len(raw), "chunk_size": chunk_size, "chunk_count": len(chunks), "chunks": chunks}
    provisional = ArchiveTransfer(**body, content_address="pending:transfer", payload=chunks_raw)
    return ArchiveTransfer(**body, content_address=address_transfer(provisional), payload=chunks_raw)


def build_transfer(value: archive_model.ObservatoryArchive, *, transfer_id: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ArchiveTransfer:
    if not isinstance(value, archive_model.ObservatoryArchive):
        raise ValidationError("transfer builder requires a typed archive")
    archive_model.verify_archive(value)
    raw = archive_model.archive_bytes(value)
    return _build_from_parts(raw, archive_value=value, transfer_id=transfer_id, chunk_size=chunk_size)


def build_transfer_from_bytes(raw: bytes, *, transfer_id: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ArchiveTransfer:
    archive_value = archive_model.load_archive_bytes(raw)
    return _build_from_parts(raw, archive_value=archive_value, transfer_id=transfer_id, chunk_size=chunk_size)


def transfer_from_mapping(value: Mapping[str, Any]) -> ArchiveTransfer:
    value = _mapping(value, "archive transfer")
    _strict(value, {"transfer_id", "version", "boundary", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "content_address"}, "archive transfer")
    chunks = tuple(ArchiveChunk.from_mapping(item) for item in _sequence(value.get("chunks"), "archive transfer chunks", MAX_CHUNKS))
    return ArchiveTransfer(value["transfer_id"], value["version"], value["boundary"], value["archive_address"], value["archive_size"], value["chunk_size"], value["chunk_count"], chunks, value["content_address"])


def verify_transfer(value: ArchiveTransfer) -> ArchiveTransfer:
    if not isinstance(value, ArchiveTransfer):
        raise ValidationError("transfer verification requires a typed transfer")
    value._validate()
    if value._payload:
        raw = assemble_archive_bytes(value)
        nested = archive_model.verify_archive_bytes(raw)
        if nested.content_address != value.archive_address:
            raise ValidationError("transfer archive linkage is invalid")
    return value


def _manifest(value: ArchiveTransfer) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "transfer_id": value.transfer_id, "archive_address": value.archive_address, "archive_size": value.archive_size, "chunk_size": value.chunk_size, "chunk_count": value.chunk_count, "chunks": tuple(chunk.to_dict() for chunk in value.chunks), "transfer_address": value.content_address}
    body["manifest_address"] = content_hash(body | {"manifest_address": None}, prefix=TRANSFER_MANIFEST_PREFIX)
    return body


def manifest_document(value: ArchiveTransfer) -> dict[str, Any]:
    verify_transfer(value)
    return _manifest(value)


def manifest_json(value: ArchiveTransfer) -> str:
    return canonical_json(manifest_document(value))


def assemble_archive_bytes(value: ArchiveTransfer, chunks: Mapping[int, bytes] | None = None) -> bytes:
    if not isinstance(value, ArchiveTransfer):
        raise ValidationError("archive assembly requires a typed transfer")
    parts = dict(value.payload_bytes() if chunks is None else chunks)
    if set(parts) != set(range(value.chunk_count)):
        raise ValidationError("archive assembly requires every chunk")
    assembled = io.BytesIO()
    for chunk in value.chunks:
        raw = parts[chunk.index]
        if not isinstance(raw, bytes) or len(raw) != chunk.size or address_chunk(raw) != chunk.content_address:
            raise ValidationError("archive assembly found an invalid chunk")
        assembled.write(raw)
    raw = assembled.getvalue()
    if len(raw) != value.archive_size:
        raise ValidationError("archive assembly size does not match the manifest")
    nested = archive_model.verify_archive_bytes(raw)
    if nested.content_address != value.archive_address:
        raise ValidationError("archive assembly address does not match the manifest")
    return raw


def chunk_bytes(value: ArchiveTransfer, index: int) -> bytes:
    verify_transfer(value)
    _count(index, "chunk index", value.chunk_count - 1)
    return value.payload_bytes()[index]


def _expected_files(value: ArchiveTransfer) -> set[str]:
    return {MANIFEST_NAME, *(chunk_name(index) for index in range(value.chunk_count))}


def _validate_directory_shape(directory: Path, value: ArchiveTransfer) -> None:
    expected_files = _expected_files(value)
    expected_directories = {CHUNK_PREFIX.rstrip("/")}
    names = {item.relative_to(directory).as_posix() for item in directory.rglob("*")}
    if names != expected_files | expected_directories:
        raise ValidationError("transfer directory member set is invalid")
    for item in directory.rglob("*"):
        relative = item.relative_to(directory).as_posix()
        if item.is_symlink() or (relative in expected_files and not item.is_file()) or (relative in expected_directories and not item.is_dir()):
            raise ValidationError("transfer directory contains an invalid member")


def _write_atomic_directory(destination: Path, value: ArchiveTransfer, *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("transfer destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir():
            raise ValidationError("transfer destination is not an exact compatible directory")
        _validate_directory_shape(destination, value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-observatory-transfer-", dir=str(destination.parent)))
    try:
        (temporary / CHUNK_PREFIX.rstrip("/")).mkdir(parents=True, exist_ok=True)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(_manifest(value)))
        payload = value.payload_bytes()
        for index in range(value.chunk_count):
            (temporary / chunk_name(index)).write_bytes(payload[index])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_transfer(value: ArchiveTransfer, destination: str | Path, *, overwrite: bool = False) -> Path:
    verify_transfer(value)
    return _write_atomic_directory(Path(destination), value, overwrite=overwrite)


def _partial_expected_files(value: ArchiveTransfer, indices: Sequence[int]) -> set[str]:
    return {MANIFEST_NAME, CHUNK_PREFIX.rstrip("/"), *(chunk_name(index) for index in indices)}


def _validate_partial_directory_shape(directory: Path, value: ArchiveTransfer) -> tuple[int, ...]:
    chunk_directory = directory / CHUNK_PREFIX.rstrip("/")
    if chunk_directory.is_symlink() or not chunk_directory.is_dir():
        raise ValidationError("partial transfer chunk directory is missing")
    received: list[int] = []
    for item in chunk_directory.iterdir():
        if item.is_symlink() or not item.is_file():
            raise ValidationError("partial transfer contains a non-regular chunk")
        name = item.name
        if not name.startswith("chunk-") or not name.endswith(CHUNK_SUFFIX):
            raise ValidationError("partial transfer contains an unknown chunk name")
        selected = name.removeprefix("chunk-").removesuffix(CHUNK_SUFFIX)
        if not selected.isdigit() or chunk_name(int(selected)) != f"{CHUNK_PREFIX}{name}":
            raise ValidationError("partial transfer chunk name is not canonical")
        index = int(selected)
        if index >= value.chunk_count:
            raise ValidationError("partial transfer chunk index is outside the manifest")
        received.append(index)
    indices = tuple(sorted(received))
    expected = _partial_expected_files(value, indices)
    names = {item.relative_to(directory).as_posix() for item in directory.rglob("*")}
    if names != expected:
        raise ValidationError("partial transfer directory member set is invalid")
    for item in directory.rglob("*"):
        if item.is_symlink():
            raise ValidationError("partial transfer contains a symlink")
    return indices


def write_partial_transfer(assembler: TransferAssembler, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(assembler, TransferAssembler):
        raise ValidationError("partial transfer writer requires a transfer assembler")
    assembler.value._validate()
    target = Path(destination)
    if target.exists():
        if not overwrite:
            raise ValidationError("partial transfer destination exists; explicit overwrite is required")
        if target.is_symlink() or not target.is_dir():
            raise ValidationError("partial transfer destination must be a directory")
        existing, _ = _read_manifest(target)
        if existing.content_address != assembler.value.content_address:
            raise ValidationError("partial transfer destination belongs to another transfer")
        _validate_partial_directory_shape(target, existing)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-observatory-partial-", dir=str(target.parent)))
    try:
        (temporary / CHUNK_PREFIX.rstrip("/")).mkdir(parents=True, exist_ok=True)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(_manifest(assembler.value)))
        for index in assembler.received_indices():
            (temporary / chunk_name(index)).write_bytes(assembler._parts[index])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def _read_manifest(source: str | Path) -> tuple[ArchiveTransfer, Path]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("transfer input must be a regular directory")
    manifest_path = directory / MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValidationError("transfer manifest is missing")
    raw = manifest_path.read_bytes()
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("transfer manifest is invalid JSON") from error
    manifest = dict(_mapping(decoded, "transfer manifest"))
    if canonical_bytes(manifest) != raw:
        raise ValidationError("transfer manifest is not canonical JSON")
    _strict(manifest, {"version", "boundary", "transfer_id", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "transfer_address", "manifest_address"}, "transfer manifest")
    expected_manifest_address = content_hash(dict(manifest) | {"manifest_address": None}, prefix=TRANSFER_MANIFEST_PREFIX)
    if manifest.get("version") != VERSION or manifest.get("boundary") != BOUNDARY or manifest.get("manifest_address") != expected_manifest_address:
        raise ValidationError("transfer manifest contract is invalid")
    body = {"transfer_id": manifest["transfer_id"], "version": manifest["version"], "boundary": manifest["boundary"], "archive_address": manifest["archive_address"], "archive_size": manifest["archive_size"], "chunk_size": manifest["chunk_size"], "chunk_count": manifest["chunk_count"], "chunks": tuple(ArchiveChunk.from_mapping(item) for item in _sequence(manifest.get("chunks"), "transfer manifest chunks", MAX_CHUNKS))}
    provisional = ArchiveTransfer(**body, content_address="pending:transfer")
    if manifest.get("transfer_address") != address_transfer(provisional):
        raise ValidationError("transfer manifest address linkage is invalid")
    return ArchiveTransfer(**body, content_address=manifest["transfer_address"]), directory


def load_transfer(source: str | Path) -> ArchiveTransfer:
    value, directory = _read_manifest(source)
    _validate_directory_shape(directory, value)
    payload = {}
    for index, chunk in enumerate(value.chunks):
        raw = (directory / chunk_name(index)).read_bytes()
        if len(raw) != chunk.size or address_chunk(raw) != chunk.content_address:
            raise ValidationError("transfer chunk bytes are not addressed")
        payload[index] = raw
    loaded = ArchiveTransfer(value.transfer_id, value.version, value.boundary, value.archive_address, value.archive_size, value.chunk_size, value.chunk_count, value.chunks, value.content_address, payload=payload)
    verify_transfer(loaded)
    return loaded


def load_partial_transfer(source: str | Path) -> TransferAssembler:
    value, directory = _read_manifest(source)
    indices = _validate_partial_directory_shape(directory, value)
    assembler = TransferAssembler(value)
    assembler.add_chunks({index: (directory / chunk_name(index)).read_bytes() for index in indices})
    return assembler


def verify_partial_transfer(source: str | Path) -> TransferAssemblyProgress:
    return load_partial_transfer(source).progress()


def verify_transfer_directory(source: str | Path) -> ArchiveTransfer:
    return load_transfer(source)


class TransferQuery:
    """Bounded query over a transfer manifest and its chunk receipts."""

    RESOURCES = ("summary", "chunks", "missing", "progress")

    def __init__(self, resource: str = "summary", text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "transfer query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("transfer query resource is not supported")
        self.text = None if text is None else _text(text, "transfer query text", 512)
        self.offset = _count(offset, "transfer query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "transfer query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "text": self.text, "offset": self.offset, "limit": self.limit}


class TransferQueryResult:
    def __init__(self, transfer_address: str, query: TransferQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.transfer_address = transfer_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.transfer_address, "query transfer address", prefix=TRANSFER_PREFIX)
        _count(self.total_count, "query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("query result window is invalid")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "query content address")
        else:
            _address(self.content_address, "query content address", prefix=TRANSFER_QUERY_PREFIX)
        if not _public(self.to_dict()):
            raise ValidationError("transfer query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_transfer_query(self) != self.content_address:
            raise ValidationError("transfer query content address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_address": self.transfer_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}


def address_transfer_query(value: TransferQueryResult) -> str:
    if not isinstance(value, TransferQueryResult):
        raise ValidationError("transfer query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSFER_QUERY_PREFIX)


def _query_record_matches(record: Mapping[str, Any], text: str | None) -> bool:
    return text is None or text.lower() in canonical_json(record).lower()


def query_transfer(value: ArchiveTransfer, query: TransferQuery | None = None, *, resource: str = "summary", text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> TransferQueryResult:
    verify_transfer(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("transfer query accepts either a query object or keyword filters")
    query = query or TransferQuery(resource=resource, text=text, offset=offset, limit=limit)
    if query.resource == "summary":
        records = (value.summary(),)
    elif query.resource == "chunks":
        records = tuple(chunk.to_dict() for chunk in value.chunks)
    elif query.resource == "progress":
        records = (_progress_from_parts(value, value._payload).to_dict(),)
    else:
        records = () if value._payload else tuple(chunk.to_dict() for chunk in value.chunks)
    if query.text is not None:
        records = tuple(record for record in records if _query_record_matches(record, query.text))
    total_count = len(records)
    window = records[query.offset:query.offset + query.limit]
    provisional = TransferQueryResult(value.content_address, query, total_count, window, "pending:query")
    return TransferQueryResult(value.content_address, query, total_count, window, address_transfer_query(provisional))


def query_transfer_directory(source: str | Path, query: TransferQuery | None = None, **kwargs: Any) -> TransferQueryResult:
    return query_transfer(load_transfer(source), query, **kwargs)


def _csv_text(result: TransferQueryResult) -> str:
    output = io.StringIO()
    records = list(result.records)
    fieldnames = sorted({str(key) for record in records for key in record}) or ["content_address"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({key: canonical_json(record[key]) if isinstance(record.get(key), (dict, list, tuple)) else record.get(key, "") for key in fieldnames})
    return output.getvalue()


def transfer_json(value: ArchiveTransfer) -> str:
    verify_transfer(value)
    return canonical_json(value.to_dict())


def transfer_manifest_json(value: ArchiveTransfer) -> str:
    return manifest_json(value)


def transfer_query_json(value: TransferQueryResult) -> str:
    if not isinstance(value, TransferQueryResult):
        raise ValidationError("transfer query JSON requires a typed result")
    return canonical_json(value.to_dict())


def transfer_query_csv(value: TransferQueryResult) -> str:
    if not isinstance(value, TransferQueryResult):
        raise ValidationError("transfer query CSV requires a typed result")
    return _csv_text(value)


def render_transfer_markdown(value: ArchiveTransfer) -> str:
    verify_transfer(value)
    return "\n".join(("# Assurance history observatory archive transfer", "", f"- Transfer: `{value.transfer_id}`", f"- Archive: `{value.archive_address}`", f"- Size: `{value.archive_size}` bytes", f"- Chunks: `{value.chunk_count}` at `{value.chunk_size}` bytes", f"- Content address: `{value.content_address}`", ""))


def render_transfer_query_markdown(value: TransferQueryResult) -> str:
    if not isinstance(value, TransferQueryResult):
        raise ValidationError("transfer query Markdown requires a typed result")
    lines = ["# Assurance history observatory archive transfer query", "", f"- Resource: `{value.query.resource}`", f"- Returned: `{value.returned_count}` of `{value.total_count}`", f"- Content address: `{value.content_address}`", ""]
    if value.records:
        keys = sorted({str(key) for record in value.records for key in record})
        lines.extend(("| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"))
        lines.extend("| " + " | ".join(canonical_json(record.get(key, "")) if isinstance(record.get(key), (dict, list, tuple)) else str(record.get(key, "")) for key in keys) + " |" for record in value.records)
    return "\n".join(lines) + "\n"


def transfer_schema() -> dict[str, Any]:
    fields = {"transfer_id": {"type": "string", "minLength": 1, "maxLength": 512}, "version": {"type": "string", "minLength": 1, "maxLength": 1024}, "boundary": {"type": "string", "minLength": 1, "maxLength": 512}, "archive_address": {"type": "string", "pattern": "^glio-noncode-assurance-history-observatory-archive:"}, "archive_size": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSFER_BYTES}, "chunk_size": {"type": "integer", "minimum": MIN_CHUNK_SIZE, "maximum": MAX_CHUNK_SIZE}, "chunk_count": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNKS}, "chunks": {"type": "array", "minItems": 1, "maxItems": MAX_CHUNKS, "items": chunk_schema()}, "content_address": {"type": "string", "pattern": "^glio-noncode-assurance-history-observatory-archive-transfer:"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def chunk_schema() -> dict[str, Any]:
    fields = {"index": {"type": "integer", "minimum": 0, "maximum": MAX_CHUNKS - 1}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_TRANSFER_BYTES}, "size": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNK_SIZE}, "content_address": {"type": "string", "pattern": "^glio-noncode-assurance-history-observatory-archive-transfer-chunk:"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"type": "string", "minLength": 1, "maxLength": 1024}, "boundary": {"type": "string", "minLength": 1, "maxLength": 512}, "transfer_id": {"type": "string", "minLength": 1, "maxLength": 512}, "archive_address": {"type": "string"}, "archive_size": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSFER_BYTES}, "chunk_size": {"type": "integer", "minimum": MIN_CHUNK_SIZE, "maximum": MAX_CHUNK_SIZE}, "chunk_count": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNKS}, "chunks": {"type": "array", "minItems": 1, "maxItems": MAX_CHUNKS, "items": chunk_schema()}, "transfer_address": {"type": "string"}, "manifest_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def progress_schema() -> dict[str, Any]:
    fields = {"transfer_address": {"type": "string"}, "archive_address": {"type": "string"}, "archive_size": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSFER_BYTES}, "chunk_count": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNKS}, "received_indices": {"type": "array", "maxItems": MAX_CHUNKS, "items": {"type": "integer", "minimum": 0, "maximum": MAX_CHUNKS - 1}}, "missing_indices": {"type": "array", "maxItems": MAX_CHUNKS, "items": {"type": "integer", "minimum": 0, "maximum": MAX_CHUNKS - 1}}, "received_bytes": {"type": "integer", "minimum": 0, "maximum": MAX_TRANSFER_BYTES}, "complete": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^glio-noncode-assurance-history-observatory-archive-transfer-progress:"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(TransferQuery.RESOURCES)}, "text": {"anyOf": [{"type": "string", "maxLength": 512}, {"type": "null"}]}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    fields = {"transfer_address": {"type": "string"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object"}}, "content_address": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "manifest": MANIFEST_NAME, "chunk_prefix": CHUNK_PREFIX, "limits": {"min_chunk_size": MIN_CHUNK_SIZE, "max_chunk_size": MAX_CHUNK_SIZE, "max_chunks": MAX_CHUNKS, "max_transfer_bytes": MAX_TRANSFER_BYTES, "max_query_items": MAX_QUERY_ITEMS}, "features": ("verified archive byte anchoring", "deterministic byte-range receipts", "resumable exact-directory transfer", "idempotent incremental chunk ingestion", "addressed assembly progress receipts", "fail-closed chunk reassembly", "bounded summary chunk progress and missing queries", "canonical JSON CSV and Markdown projections"), "resources": TransferQuery.RESOURCES, "schemas": ("chunk", "transfer", "manifest", "progress", "query", "query-result")}


__all__ = [
    "BOUNDARY",
    "CHUNK_PREFIX",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_LIMIT",
    "DEFAULT_TRANSFER_ID",
    "MANIFEST_NAME",
    "MAX_CHUNK_SIZE",
    "MAX_CHUNKS",
    "MAX_QUERY_ITEMS",
    "MAX_TRANSFER_BYTES",
    "MIN_CHUNK_SIZE",
    "TRANSFER_CHUNK_PREFIX",
    "TRANSFER_MANIFEST_PREFIX",
    "TRANSFER_PROGRESS_PREFIX",
    "TRANSFER_PREFIX",
    "TRANSFER_QUERY_PREFIX",
    "VERSION",
    "ArchiveChunk",
    "ArchiveTransfer",
    "TransferAssemblyProgress",
    "TransferAssembler",
    "TransferQuery",
    "TransferQueryResult",
    "address_chunk",
    "address_transfer",
    "address_transfer_query",
    "address_progress",
    "assemble_archive_bytes",
    "build_transfer",
    "build_transfer_from_bytes",
    "capabilities",
    "chunk_bytes",
    "chunk_name",
    "chunk_schema",
    "load_transfer",
    "load_partial_transfer",
    "manifest_document",
    "manifest_json",
    "manifest_schema",
    "progress_schema",
    "query_schema",
    "query_result_schema",
    "query_transfer",
    "query_transfer_directory",
    "render_transfer_markdown",
    "render_transfer_query_markdown",
    "transfer_from_mapping",
    "transfer_json",
    "transfer_manifest_json",
    "transfer_query_csv",
    "transfer_query_json",
    "transfer_schema",
    "verify_transfer",
    "verify_partial_transfer",
    "verify_transfer_directory",
    "write_partial_transfer",
    "write_transfer",
]

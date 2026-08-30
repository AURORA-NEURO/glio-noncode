"""Resumable chunk transport for certificate-observatory archives.

ZIP files are convenient for disk but awkward for bounded uploads.  This
module splits the already addressed archive bytes into ordered chunks.  The
transfer manifest records the archive address, byte ranges, and per-chunk
receipts.  A receiver may persist a complete or partial set, inspect progress,
and finalize only after every byte receipt and the nested archive verifier
agree.  No operation mutates a source archive or guesses a missing chunk.
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
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = archive_model.VERSION + "-transfer-v1"
BOUNDARY = archive_model.BOUNDARY + "_transfer"
TRANSFER_PREFIX = archive_model.ARCHIVE_PREFIX + "-transfer"
CHUNK_PREFIX = TRANSFER_PREFIX + "-chunk"
MANIFEST_PREFIX = TRANSFER_PREFIX + "-manifest"
PROGRESS_PREFIX = TRANSFER_PREFIX + "-progress"
QUERY_PREFIX = TRANSFER_PREFIX + "-query"
MANIFEST_NAME = "manifest.json"
CHUNK_DIRECTORY = "chunks"
CHUNK_PREFIX_NAME = "chunk-"
CHUNK_SUFFIX = ".bin"
DEFAULT_TRANSFER_ID = "consensus-certificate-observatory-transfer"
DEFAULT_CHUNK_SIZE = 64 * 1024
MIN_CHUNK_SIZE = 256
MAX_CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNKS = 4096
MAX_TRANSFER_BYTES = 128 * 1024 * 1024
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


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
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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
    return archive_model._public(value)


def _chunk_size(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_CHUNK_SIZE or value > MAX_CHUNK_SIZE:
        raise ValidationError(f"chunk size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")
    return value


def chunk_name(index: int) -> str:
    _count(index, "chunk index", MAX_CHUNKS - 1)
    return f"{CHUNK_DIRECTORY}/{CHUNK_PREFIX_NAME}{index:08d}{CHUNK_SUFFIX}"


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk:
    """An addressed byte range in a transfer."""

    FIELDS = ("index", "offset", "size", "content_address")

    def __init__(self, index: int, offset: int, size: int, content_address: str) -> None:
        self.index = _count(index, "chunk index", MAX_CHUNKS - 1)
        self.offset = _count(offset, "chunk offset", MAX_TRANSFER_BYTES)
        self.size = _count(size, "chunk size", MAX_CHUNK_SIZE, positive=True)
        self.content_address = _address(content_address, "chunk address", CHUNK_PREFIX)
        if self.offset + self.size > MAX_TRANSFER_BYTES:
            raise ValidationError("chunk range exceeds transfer bound")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk":
        value = _mapping(value, "transfer chunk")
        _strict(value, set(cls.FIELDS), "transfer chunk")
        return cls(value["index"], value["offset"], value["size"], value["content_address"])


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    """A transfer manifest with optional in-memory chunk bytes."""

    FIELDS = ("transfer_id", "version", "boundary", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "content_address")

    def __init__(self, transfer_id: str, version: str, boundary: str, archive_address: str, archive_size: int, chunk_size: int, chunk_count: int, chunks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk], content_address: str, payload: Mapping[int, bytes] | None = None, archive: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive | None = None) -> None:
        self.transfer_id = _label(transfer_id, "transfer ID")
        self.version = _text(version, "transfer version", 1024)
        self.boundary = _text(boundary, "transfer boundary")
        self.archive_address = _address(archive_address, "transfer archive address", archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "transfer archive size", MAX_TRANSFER_BYTES, positive=True)
        self.chunk_size = _chunk_size(chunk_size)
        self.chunk_count = _count(chunk_count, "transfer chunk count", MAX_CHUNKS, positive=True)
        self.chunks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk) else RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk.from_mapping(item) for item in _sequence(chunks, "transfer chunks", MAX_CHUNKS))
        self.content_address = _address(content_address, "transfer content address") if not str(content_address).startswith("pending:") else _text(content_address, "transfer content address")
        self._payload = dict(payload or {})
        self._archive = archive
        self._validate()

    def _validate(self) -> None:
        expected_count = (self.archive_size + self.chunk_size - 1) // self.chunk_size
        if self.chunk_count != len(self.chunks) or self.chunk_count != expected_count or tuple(item.index for item in self.chunks) != tuple(range(self.chunk_count)):
            raise ValidationError("transfer chunk count or order is inconsistent")
        offset = 0
        for item in self.chunks:
            expected_size = min(self.chunk_size, self.archive_size - offset)
            if item.offset != offset or item.size != expected_size:
                raise ValidationError("transfer chunk range is not contiguous")
            offset += item.size
        if offset != self.archive_size or not _public(self.to_dict()):
            raise ValidationError("transfer range or public boundary failed")
        if not self.content_address.startswith("pending:") and address_transfer(self) != self.content_address:
            raise ValidationError("transfer content address does not replay")
        if self._archive is not None and self._archive.content_address != self.archive_address:
            raise ValidationError("transfer nested archive address does not replay")
        if self._payload:
            if set(self._payload) != set(range(self.chunk_count)):
                raise ValidationError("transfer payload chunk set is incomplete")
            for item in self.chunks:
                raw = self._payload[item.index]
                if not isinstance(raw, bytes) or len(raw) != item.size or hash_bytes(raw, prefix=CHUNK_PREFIX) != item.content_address:
                    raise ValidationError("transfer chunk receipt does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_id": self.transfer_id, "version": self.version, "boundary": self.boundary, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_size": self.chunk_size, "chunk_count": self.chunk_count, "chunks": tuple(item.to_dict() for item in self.chunks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("transfer_id", "version", "boundary", "archive_address", "archive_size", "chunk_size", "chunk_count", "content_address")}

    def payload_bytes(self) -> Mapping[int, bytes]:
        if not self._payload:
            raise ValidationError("transfer chunk bytes are unavailable")
        return dict(self._payload)

    @property
    def archive(self) -> archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive | None:
        return self._archive


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress:
    """An addressed progress snapshot for a complete or partial receiver."""

    FIELDS = ("transfer_address", "archive_address", "chunk_count", "received_indices", "missing_indices", "received_bytes", "complete", "content_address")

    def __init__(self, transfer_address: str, archive_address: str, chunk_count: int, received_indices: Sequence[int], missing_indices: Sequence[int], received_bytes: int, complete: bool, content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "progress transfer address", TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "progress archive address", archive_model.ARCHIVE_PREFIX)
        self.chunk_count = _count(chunk_count, "progress chunk count", MAX_CHUNKS, positive=True)
        self.received_indices = tuple(_count(item, "received chunk index", MAX_CHUNKS - 1) for item in _sequence(received_indices, "received indices", MAX_CHUNKS))
        self.missing_indices = tuple(_count(item, "missing chunk index", MAX_CHUNKS - 1) for item in _sequence(missing_indices, "missing indices", MAX_CHUNKS))
        self.received_bytes = _count(received_bytes, "received bytes", MAX_TRANSFER_BYTES)
        self.complete = bool(complete) if isinstance(complete, bool) else (_ for _ in ()).throw(ValidationError("progress completion must be boolean"))
        self.content_address = _address(content_address, "progress address", PROGRESS_PREFIX)
        if set(self.received_indices) & set(self.missing_indices) or set(self.received_indices) | set(self.missing_indices) != set(range(self.chunk_count)) or tuple(sorted(self.received_indices)) != self.received_indices or tuple(sorted(self.missing_indices)) != self.missing_indices or self.complete != (not self.missing_indices):
            raise ValidationError("progress index sets are not conserved")
        if not self.content_address.endswith(":pending") and address_progress(self) != self.content_address:
            raise ValidationError("progress address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress":
        value = _mapping(value, "transfer progress")
        _strict(value, set(cls.FIELDS), "transfer progress")
        return cls(*(value[field] for field in cls.FIELDS))


def address_chunk(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise ValidationError("chunk address requires non-empty bytes")
    return hash_bytes(raw, prefix=CHUNK_PREFIX)


def address_transfer(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer):
        raise ValidationError("transfer address requires a typed transfer")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSFER_PREFIX)


def address_progress(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress):
        raise ValidationError("progress address requires a typed progress")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PROGRESS_PREFIX)


def _progress(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, parts: Mapping[int, bytes]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress:
    received = tuple(sorted(parts))
    missing = tuple(index for index in range(value.chunk_count) if index not in parts)
    received_bytes = sum(len(parts[index]) for index in received)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress(value.content_address, value.archive_address, value.chunk_count, received, missing, received_bytes, not missing, PROGRESS_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress(provisional.transfer_address, provisional.archive_address, provisional.chunk_count, provisional.received_indices, provisional.missing_indices, provisional.received_bytes, provisional.complete, address_progress(provisional))


class TransferAssembler:
    """Incremental receiver that validates each chunk before retaining it."""

    def __init__(self, value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, parts: Mapping[int, bytes] | None = None) -> None:
        self.value = verify_transfer(value)
        self._parts: dict[int, bytes] = {}
        if parts:
            for index, raw in parts.items():
                self.add_chunk(index, raw)

    def add_chunk(self, index: int, raw: bytes) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress:
        _count(index, "chunk index", self.value.chunk_count - 1)
        if index in self._parts:
            raise ValidationError("received chunk has already been accepted")
        if not isinstance(raw, bytes) or len(raw) != self.value.chunks[index].size or address_chunk(raw) != self.value.chunks[index].content_address:
            raise ValidationError("received chunk does not match its declared range or address")
        self._parts[index] = raw
        return self.progress()

    def add_chunks(self, parts: Mapping[int, bytes]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress:
        for index in sorted(parts):
            self.add_chunk(index, parts[index])
        return self.progress()

    def received_indices(self) -> tuple[int, ...]:
        return tuple(sorted(self._parts))

    def missing_indices(self) -> tuple[int, ...]:
        return tuple(index for index in range(self.value.chunk_count) if index not in self._parts)

    def received_parts(self) -> Mapping[int, bytes]:
        return dict(self._parts)

    @property
    def complete(self) -> bool:
        return not self.missing_indices()

    def progress(self) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress:
        return _progress(self.value, self._parts)

    def finalize(self) -> bytes:
        progress = self.progress()
        if not progress.complete:
            raise ValidationError("transfer cannot finalize while chunks are missing")
        raw = b"".join(self._parts[index] for index in range(self.value.chunk_count))
        if len(raw) != self.value.archive_size:
            raise ValidationError("assembled bytes do not conserve archive size")
        archive = archive_model.load_archive_bytes(raw)
        if archive.content_address != self.value.archive_address:
            raise ValidationError("assembled archive address does not match transfer")
        return raw


def build_transfer(value: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive, *, transfer_id: str = DEFAULT_TRANSFER_ID, chunk_size: int = DEFAULT_CHUNK_SIZE) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    archive_model.verify_archive(value)
    raw = archive_model.archive_bytes(value)
    return build_transfer_from_bytes(raw, archive_address=value.content_address, transfer_id=transfer_id, chunk_size=chunk_size, archive=value)


def build_transfer_from_file(source: str | Path, *, transfer_id: str = DEFAULT_TRANSFER_ID, chunk_size: int = DEFAULT_CHUNK_SIZE) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    archive = archive_model.load_archive(source)
    return build_transfer(archive, transfer_id=transfer_id, chunk_size=chunk_size)


def build_transfer_from_bytes(raw: bytes, *, archive_address: str, transfer_id: str = DEFAULT_TRANSFER_ID, chunk_size: int = DEFAULT_CHUNK_SIZE, archive: archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_TRANSFER_BYTES:
        raise ValidationError("transfer bytes are outside the bounded archive size")
    _chunk_size(chunk_size)
    chunks: list[RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk] = []
    payload: dict[int, bytes] = {}
    for index, offset in enumerate(range(0, len(raw), chunk_size)):
        piece = raw[offset:offset + chunk_size]
        payload[index] = piece
        chunks.append(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk(index, offset, len(piece), address_chunk(piece)))
    body = {"transfer_id": transfer_id, "version": VERSION, "boundary": BOUNDARY, "archive_address": archive_address, "archive_size": len(raw), "chunk_size": chunk_size, "chunk_count": len(chunks), "chunks": tuple(chunks)}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer(**body, content_address="pending:transfer", payload=payload, archive=archive)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer(**body, content_address=address_transfer(provisional), payload=payload, archive=archive)


def transfer_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    value = _mapping(value, "archive transfer")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer.FIELDS), "archive transfer")
    chunks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk.from_mapping(item) for item in _sequence(value["chunks"], "transfer chunks", MAX_CHUNKS))
    return verify_transfer(RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer(value["transfer_id"], value["version"], value["boundary"], value["archive_address"], value["archive_size"], value["chunk_size"], value["chunk_count"], chunks, value["content_address"]))


def verify_transfer(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) or (not value.content_address.startswith("pending:") and address_transfer(value) != value.content_address):
        raise ValidationError("archive transfer is not valid")
    return value


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) -> dict[str, Any]:
    value = verify_transfer(value)
    body = {"version": VERSION, "boundary": BOUNDARY, "transfer_id": value.transfer_id, "archive_address": value.archive_address, "archive_size": value.archive_size, "chunk_size": value.chunk_size, "chunk_count": value.chunk_count, "chunks": tuple(item.to_dict() for item in value.chunks), "transfer_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) -> str:
    return canonical_json(manifest_document(value))


def assemble_archive_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, chunks: Mapping[int, bytes] | None = None) -> bytes:
    assembler = TransferAssembler(value, value._payload if chunks is None else chunks)
    return assembler.finalize()


def chunk_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, index: int) -> bytes:
    value = verify_transfer(value)
    if not value._payload or index not in value._payload:
        raise ValidationError("transfer chunk bytes are unavailable")
    return value._payload[index]


def _expected_files(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, indices: Sequence[int]) -> set[str]:
    return {MANIFEST_NAME, *(chunk_name(index) for index in indices)}


def _write_atomic_directory(destination: Path, value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, indices: Sequence[int], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("transfer destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-observatory-transfer-staging-", dir=str(destination.parent)))
    try:
        (staging / CHUNK_DIRECTORY).mkdir()
        (staging / MANIFEST_NAME).write_bytes(canonical_bytes(manifest_document(value)))
        for index in indices:
            (staging / chunk_name(index)).write_bytes(chunk_bytes(value, index))
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_transfer(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_transfer(value)
    if not value._payload:
        raise ValidationError("complete transfer bytes are unavailable")
    return _write_atomic_directory(Path(destination), value, range(value.chunk_count), overwrite=overwrite)


def write_partial_transfer(assembler: TransferAssembler, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(assembler, TransferAssembler):
        raise ValidationError("partial transfer writer requires an assembler")
    value = assembler.value
    if not assembler._parts:
        raise ValidationError("partial transfer must contain at least one received chunk")
    original = value._payload
    value._payload = dict(assembler._parts)
    try:
        return _write_atomic_directory(Path(destination), value, assembler.received_indices(), overwrite=overwrite)
    finally:
        value._payload = original


def _read_manifest(source: str | Path) -> tuple[Mapping[str, Any], Path]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir() or (directory / MANIFEST_NAME).is_symlink() or not (directory / MANIFEST_NAME).is_file():
        raise ValidationError("transfer source must contain a regular manifest")
    try:
        manifest = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("transfer manifest is not valid JSON") from error
    if canonical_bytes(manifest) != (directory / MANIFEST_NAME).read_bytes():
        raise ValidationError("transfer manifest is not canonical")
    return _mapping(manifest, "transfer manifest"), directory


def load_transfer(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    manifest, directory = _read_manifest(source)
    _strict(manifest, {"version", "boundary", "transfer_id", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "transfer_address", "manifest_address"}, "transfer manifest")
    if manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("transfer manifest address does not replay")
    chunks = tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk.from_mapping(item) for item in _sequence(manifest["chunks"], "transfer chunks", MAX_CHUNKS))
    value = RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer(manifest["transfer_id"], manifest["version"], manifest["boundary"], manifest["archive_address"], manifest["archive_size"], manifest["chunk_size"], manifest["chunk_count"], chunks, manifest["transfer_address"])
    files = {item.name for item in directory.iterdir() if item.name != CHUNK_DIRECTORY} | {f"{CHUNK_DIRECTORY}/{item.name}" for item in (directory / CHUNK_DIRECTORY).iterdir()} if (directory / CHUNK_DIRECTORY).is_dir() else {item.name for item in directory.iterdir() if item.name != CHUNK_DIRECTORY}
    expected = _expected_files(value, range(value.chunk_count))
    if files != expected:
        raise ValidationError("complete transfer directory has an unexpected member set")
    payload: dict[int, bytes] = {}
    for index in range(value.chunk_count):
        raw = (directory / chunk_name(index)).read_bytes()
        if len(raw) != value.chunks[index].size or address_chunk(raw) != value.chunks[index].content_address:
            raise ValidationError("transfer chunk receipt does not replay")
        payload[index] = raw
    value._payload = payload
    value._validate()
    return value


def load_partial_transfer(source: str | Path) -> TransferAssembler:
    manifest, directory = _read_manifest(source)
    _strict(manifest, {"version", "boundary", "transfer_id", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "transfer_address", "manifest_address"}, "transfer manifest")
    if manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("transfer manifest address does not replay")
    value = transfer_from_mapping({"transfer_id": manifest["transfer_id"], "version": manifest["version"], "boundary": manifest["boundary"], "archive_address": manifest["archive_address"], "archive_size": manifest["archive_size"], "chunk_size": manifest["chunk_size"], "chunk_count": manifest["chunk_count"], "chunks": manifest["chunks"], "content_address": manifest["transfer_address"]})
    parts: dict[int, bytes] = {}
    chunk_dir = directory / CHUNK_DIRECTORY
    if chunk_dir.exists() and (chunk_dir.is_symlink() or not chunk_dir.is_dir()):
        raise ValidationError("transfer chunk directory is unsafe")
    if chunk_dir.is_dir():
        for item in chunk_dir.iterdir():
            if item.is_symlink() or not item.is_file() or item.name not in {Path(chunk_name(index)).name for index in range(value.chunk_count)}:
                raise ValidationError("partial transfer contains an unexpected chunk")
            index = int(item.stem.removeprefix(CHUNK_PREFIX_NAME))
            parts[index] = item.read_bytes()
    expected = _expected_files(value, parts)
    actual = {item.name for item in directory.iterdir() if item.name != CHUNK_DIRECTORY}
    nested = {f"{CHUNK_DIRECTORY}/{item.name}" for item in chunk_dir.iterdir()} if chunk_dir.is_dir() else set()
    if actual | nested != expected:
        raise ValidationError("partial transfer member set does not replay")
    return TransferAssembler(value, parts)


def verify_transfer_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer:
    return load_transfer(source)


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery:
    FIELDS = ("resource", "text", "offset", "limit", "content_address")

    def __init__(self, resource: str = "summary", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, content_address: str = QUERY_PREFIX + ":pending") -> None:
        if resource not in ("summary", "chunks", "progress", "evidence"):
            raise ValidationError("transfer query resource is not declared")
        self.resource = resource
        self.text = _text(text, "transfer query text", 512, required=False)
        self.offset = _count(offset, "transfer query offset", 100000)
        self.limit = _count(limit, "transfer query limit", MAX_LIMIT, positive=True)
        self.content_address = _address(content_address, "transfer query address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_transfer_query(self) != self.content_address:
            raise ValidationError("transfer query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}


class RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult:
    FIELDS = ("query", "rows", "total", "matched", "returned", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery, rows: Sequence[Mapping[str, Any]], total: int, matched: int, returned: int, next_offset: int | None, truncated: bool, content_address: str = QUERY_PREFIX + "-result:pending") -> None:
        self.query = query
        self.rows = tuple(dict(_mapping(row, "transfer query row")) for row in rows)
        self.total, self.matched, self.returned = _count(total, "transfer total", MAX_CHUNKS + 8), _count(matched, "transfer matched", MAX_CHUNKS + 8), _count(returned, "transfer returned", MAX_LIMIT)
        self.next_offset = None if next_offset is None else _count(next_offset, "transfer next offset", 100000)
        self.truncated = _bool(truncated)
        if self.returned != len(self.rows) or self.returned > self.query.limit or self.truncated != (self.next_offset is not None):
            raise ValidationError("transfer query counters are not conserved")
        self.content_address = _address(content_address, "transfer query result address", QUERY_PREFIX + "-result")
        if not self.content_address.endswith(":pending") and address_transfer_query_result(self) != self.content_address:
            raise ValidationError("transfer query result address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "rows": self.rows, "total": self.total, "matched": self.matched, "returned": self.returned, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValidationError("value must be boolean")
    return value


def address_transfer_query(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def address_transfer_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")


def query_transfer(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer, *, resource: str = "summary", text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult:
    value = verify_transfer(value)
    pending = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery(resource, text, offset, limit)
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery(resource, text, offset, limit, address_transfer_query(pending))
    if resource == "summary":
        records = (value.summary() | {"resource": resource},)
    elif resource == "chunks":
        records = tuple(item.to_dict() | {"resource": resource} for item in value.chunks)
    elif resource == "progress":
        records = (_progress(value, value._payload).to_dict() | {"resource": resource},)
    else:
        records = tuple({"resource": resource, "index": item.index, "chunk_address": item.content_address, "archive_address": value.archive_address} for item in value.chunks)
    filtered = tuple(record for record in records if not query.text or query.text.lower() in canonical_json(record).lower())
    page = filtered[offset:offset + limit]
    next_offset = offset + len(page) if offset + len(page) < offset + len(filtered) else None
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult(query, page, len(records), len(filtered), len(page), next_offset, next_offset is not None)
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult(query, page, len(records), len(filtered), len(page), next_offset, next_offset is not None, address_transfer_query_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult:
    value = _mapping(value, "transfer query result")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult.FIELDS), "transfer query result")
    q = _mapping(value["query"], "transfer query")
    _strict(q, set(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery.FIELDS), "transfer query")
    query = RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery(q["resource"], q["text"], q["offset"], q["limit"], q["content_address"])
    return RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult(query, _sequence(value["rows"], "transfer query rows", MAX_LIMIT), value["total"], value["matched"], value["returned"], value["next_offset"], value["truncated"], value["content_address"])


def verify_query_result(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult) -> RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult) or (not value.content_address.endswith(":pending") and address_transfer_query_result(value) != value.content_address):
        raise ValidationError("transfer query result is not valid")
    return value


def transfer_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) -> str:
    return canonical_json(verify_transfer(value).to_dict())


def progress_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress) -> str:
    return canonical_json(value.to_dict())


def query_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("resource", "payload"), lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        writer.writerow({"resource": row.get("resource", value.query.resource), "payload": canonical_json(row)})
    return stream.getvalue()


def render_transfer_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer) -> str:
    value = verify_transfer(value)
    lines = ["# Certificate Observatory Archive Transfer", "", f"- Transfer: `{value.transfer_id}`", f"- Archive: `{value.archive_address}`", f"- Bytes: `{value.archive_size}`", f"- Chunk size: `{value.chunk_size}`", f"- Chunks: `{value.chunk_count}`", f"- Address: `{value.content_address}`", "", "| index | offset | bytes | receipt |", "| ---: | ---: | ---: | --- |"]
    lines.extend(f"| `{item.index}` | `{item.offset}` | `{item.size}` | `{item.content_address}` |" for item in value.chunks)
    return "\n".join(lines) + "\n"


def render_progress_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress) -> str:
    return "\n".join(["# Certificate Observatory Transfer Progress", "", f"- Complete: `{value.complete}`", f"- Received: `{len(value.received_indices)}`", f"- Missing: `{len(value.missing_indices)}`", f"- Bytes: `{value.received_bytes}`", f"- Address: `{value.content_address}`", ""])


def transfer_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer.FIELDS), "properties": {"transfer_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "archive_address": {"type": "string"}, "archive_size": {"type": "integer"}, "chunk_size": {"type": "integer"}, "chunk_count": {"type": "integer"}, "chunks": {"type": "array", "items": chunk_schema()}, "content_address": {"type": "string", "pattern": "^" + TRANSFER_PREFIX + ":"}}}


def chunk_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk.FIELDS), "properties": {"index": {"type": "integer"}, "offset": {"type": "integer"}, "size": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + CHUNK_PREFIX + ":"}}}


def progress_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress.FIELDS), "properties": {"transfer_address": {"type": "string"}, "archive_address": {"type": "string"}, "chunk_count": {"type": "integer"}, "received_indices": {"type": "array"}, "missing_indices": {"type": "array"}, "received_bytes": {"type": "integer"}, "complete": {"type": "boolean"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": ["summary", "chunks", "progress", "evidence"]}, "text": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}, "content_address": {"type": "string"}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult.FIELDS), "properties": {"query": query_schema(), "rows": {"type": "array"}, "total": {"type": "integer"}, "matched": {"type": "integer"}, "returned": {"type": "integer"}, "next_offset": {"type": ["integer", "null"]}, "truncated": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "transfer_prefix": TRANSFER_PREFIX, "chunk_prefix": CHUNK_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "progress_prefix": PROGRESS_PREFIX, "features": ("bounded chunking", "per-chunk content receipts", "atomic complete and partial directories", "incremental assembly", "nested archive verification", "progress projection", "bounded transfer queries", "JSON CSV and Markdown exports"), "schemas": ("chunk", "transfer", "progress", "query", "query-result")}


__all__ = ["BOUNDARY", "CHUNK_PREFIX", "DEFAULT_CHUNK_SIZE", "DEFAULT_LIMIT", "DEFAULT_TRANSFER_ID", "MANIFEST_NAME", "MANIFEST_PREFIX", "PROGRESS_PREFIX", "QUERY_PREFIX", "TRANSFER_PREFIX", "TransferAssembler", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransfer", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferChunk", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferProgress", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQuery", "RegistryFederationConsensusGateCertificateObservatoryArchiveTransferQueryResult", "address_chunk", "address_progress", "address_transfer", "address_transfer_query", "address_transfer_query_result", "assemble_archive_bytes", "build_transfer", "build_transfer_from_bytes", "build_transfer_from_file", "capabilities", "chunk_bytes", "chunk_name", "chunk_schema", "load_partial_transfer", "load_transfer", "manifest_document", "manifest_json", "progress_json", "progress_schema", "query_csv", "query_from_mapping", "query_json", "query_result_schema", "query_schema", "query_transfer", "render_progress_markdown", "render_transfer_markdown", "transfer_from_mapping", "transfer_json", "transfer_schema", "verify_query_result", "verify_transfer", "verify_transfer_directory", "write_partial_transfer", "write_transfer"]

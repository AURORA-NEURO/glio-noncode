"""Resumable byte-range transport for runtime-registry federation archives.

The transfer is deliberately downstream of the deterministic federation
archive. Its public manifest contains only addressed chunk geometry, while
chunk bytes remain private until an explicitly persisted receiver directory
or a verified in-memory assembler is used for reassembly.
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

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = archive_model.VERSION + "-transfer-v1"
BOUNDARY = archive_model.BOUNDARY + "_transfer"
TRANSFER_PREFIX = archive_model.ARCHIVE_PREFIX + "-transfer"
CHUNK_PREFIX = TRANSFER_PREFIX + "-chunk"
MANIFEST_PREFIX = TRANSFER_PREFIX + "-manifest"
PROGRESS_PREFIX = TRANSFER_PREFIX + "-progress"
TRANSFER_DIRECTORY_MANIFEST = "manifest.json"
CHUNK_DIRECTORY = "chunks"
CHUNK_NAME_PREFIX = CHUNK_DIRECTORY + "/chunk-"
CHUNK_SUFFIX = ".bin"
DEFAULT_TRANSFER_ID = "runtime-registry-federation-archive-transfer"
DEFAULT_CHUNK_SIZE = 1024
MIN_CHUNK_SIZE = 64
MAX_CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNKS = 4096
MAX_TRANSFER_BYTES = archive_model.MAX_ARCHIVE_BYTES
MAX_TEXT = 2048


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 8192)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or value.startswith(("/", "\\")) or "/" in value or "\\" in value or '"' in value:
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
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _chunk_size(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_CHUNK_SIZE or value > MAX_CHUNK_SIZE:
        raise ValidationError(f"chunk size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")
    return value


def _public(value: Any) -> bool:
    return archive_model._public(value)


def chunk_name(index: int) -> str:
    _count(index, "chunk index", MAX_CHUNKS - 1)
    return f"{CHUNK_NAME_PREFIX}{index:08d}{CHUNK_SUFFIX}"


class ArchiveTransferChunk:
    """One contiguous, addressed byte range in a transfer manifest."""

    FIELDS = ("index", "offset", "size", "content_address")

    def __init__(self, index: int, offset: int, size: int, content_address: str) -> None:
        self.index = _count(index, "chunk index", MAX_CHUNKS - 1)
        self.offset = _count(offset, "chunk offset", MAX_TRANSFER_BYTES)
        self.size = _count(size, "chunk size", MAX_CHUNK_SIZE, positive=True)
        self.content_address = _address(content_address, "chunk content address", CHUNK_PREFIX)
        if self.offset + self.size > MAX_TRANSFER_BYTES:
            raise ValidationError("chunk range exceeds the transfer bound")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ArchiveTransferChunk:
        value = _mapping(value, "archive transfer chunk")
        _strict(value, set(cls.FIELDS), "archive transfer chunk")
        return cls(value["index"], value["offset"], value["size"], value["content_address"])


class ArchiveTransfer:
    """A transfer manifest with optional private chunk payloads."""

    FIELDS = ("transfer_id", "version", "boundary", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "content_address")

    def __init__(self, transfer_id: str, version: str, boundary: str, archive_address: str, archive_size: int, chunk_size: int, chunk_count: int, chunks: Sequence[ArchiveTransferChunk], content_address: str, payload: Mapping[int, bytes] | None = None) -> None:
        self.transfer_id = _label(transfer_id, "transfer ID")
        self.version = _text(version, "transfer version", 2048)
        self.boundary = _text(boundary, "transfer boundary", 2048)
        self.archive_address = _address(archive_address, "transfer archive address", archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "archive size", MAX_TRANSFER_BYTES, positive=True)
        self.chunk_size = _chunk_size(chunk_size)
        self.chunk_count = _count(chunk_count, "chunk count", MAX_CHUNKS, positive=True)
        self.chunks = tuple(item if isinstance(item, ArchiveTransferChunk) else ArchiveTransferChunk.from_mapping(item) for item in _sequence(chunks, "transfer chunks", MAX_CHUNKS))
        self.content_address = _address(content_address, "transfer content address", TRANSFER_PREFIX, allow_pending=True)
        self._payload = dict(payload or {})
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("transfer version or boundary is not current")
        if self.chunk_count != len(self.chunks) or self.chunk_count != (self.archive_size + self.chunk_size - 1) // self.chunk_size:
            raise ValidationError("transfer chunk count is inconsistent with the byte range")
        expected_offset = 0
        for expected_index, chunk in enumerate(self.chunks):
            if chunk.index != expected_index or chunk.offset != expected_offset:
                raise ValidationError("transfer chunk ordering or offsets are invalid")
            expected_size = min(self.chunk_size, self.archive_size - expected_offset)
            if chunk.size != expected_size:
                raise ValidationError("transfer chunk size is inconsistent with the byte range")
            expected_offset += chunk.size
        if expected_offset != self.archive_size:
            raise ValidationError("transfer chunks do not conserve archive size")
        if not _public(self.to_dict()):
            raise ValidationError("transfer crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_transfer(self) != self.content_address:
            raise ValidationError("transfer content address does not replay")
        if self._payload:
            if set(self._payload) != set(range(self.chunk_count)):
                raise ValidationError("transfer payload is not complete")
            for chunk in self.chunks:
                raw = self._payload.get(chunk.index)
                if not isinstance(raw, bytes) or len(raw) != chunk.size or address_chunk(raw) != chunk.content_address:
                    raise ValidationError("transfer payload does not match chunk receipts")

    def to_dict(self) -> dict[str, Any]:
        return {"transfer_id": self.transfer_id, "version": self.version, "boundary": self.boundary, "archive_address": self.archive_address, "archive_size": self.archive_size, "chunk_size": self.chunk_size, "chunk_count": self.chunk_count, "chunks": tuple(chunk.to_dict() for chunk in self.chunks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "chunks"}

    def payload_bytes(self) -> Mapping[int, bytes]:
        if not self._payload:
            raise ValidationError("transfer chunk payload is unavailable")
        return dict(self._payload)


class TransferAssemblyProgress:
    """An addressed snapshot of received and missing chunk indices."""

    FIELDS = ("transfer_address", "archive_address", "archive_size", "chunk_count", "received_indices", "missing_indices", "received_bytes", "complete", "content_address")

    def __init__(self, transfer_address: str, archive_address: str, archive_size: int, chunk_count: int, received_indices: Sequence[int], missing_indices: Sequence[int], received_bytes: int, complete: bool, content_address: str) -> None:
        self.transfer_address = _address(transfer_address, "progress transfer address", TRANSFER_PREFIX)
        self.archive_address = _address(archive_address, "progress archive address", archive_model.ARCHIVE_PREFIX)
        self.archive_size = _count(archive_size, "progress archive size", MAX_TRANSFER_BYTES, positive=True)
        self.chunk_count = _count(chunk_count, "progress chunk count", MAX_CHUNKS, positive=True)
        self.received_indices = tuple(received_indices)
        self.missing_indices = tuple(missing_indices)
        self.received_bytes = _count(received_bytes, "progress received bytes", self.archive_size)
        if not isinstance(complete, bool):
            raise ValidationError("progress complete must be boolean")
        self.complete = complete
        self.content_address = _address(content_address, "progress content address", PROGRESS_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        received = tuple(self.received_indices)
        missing = tuple(self.missing_indices)
        valid = set(range(self.chunk_count))
        if received != tuple(sorted(received)) or missing != tuple(sorted(missing)) or set(received) & set(missing) or set(received) | set(missing) != valid:
            raise ValidationError("progress received and missing sets are inconsistent")
        if any(isinstance(index, bool) or not isinstance(index, int) or index not in valid for index in received + missing):
            raise ValidationError("progress index is outside the transfer")
        if self.complete != (not missing) or (self.complete and self.received_bytes != self.archive_size):
            raise ValidationError("progress completion does not match received bytes")
        if not _public(self.to_dict()):
            raise ValidationError("progress crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_progress(self) != self.content_address:
            raise ValidationError("progress content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()


def address_chunk(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw:
        raise ValidationError("chunk content must be non-empty bytes")
    return hash_bytes(raw, prefix=CHUNK_PREFIX)


def address_transfer(value: ArchiveTransfer) -> str:
    if not isinstance(value, ArchiveTransfer):
        raise ValidationError("transfer address requires a typed transfer")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TRANSFER_PREFIX)


def address_progress(value: TransferAssemblyProgress) -> str:
    if not isinstance(value, TransferAssemblyProgress):
        raise ValidationError("progress address requires a typed progress receipt")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PROGRESS_PREFIX)


def _progress_from_parts(value: ArchiveTransfer, parts: Mapping[int, bytes]) -> TransferAssemblyProgress:
    received = tuple(sorted(parts))
    missing = tuple(index for index in range(value.chunk_count) if index not in parts)
    received_bytes = sum(len(raw) for raw in parts.values())
    provisional = TransferAssemblyProgress(value.content_address, value.archive_address, value.archive_size, value.chunk_count, received, missing, received_bytes, not missing, "pending:progress")
    return TransferAssemblyProgress(value.content_address, value.archive_address, value.archive_size, value.chunk_count, received, missing, received_bytes, not missing, address_progress(provisional))


class TransferAssembler:
    """Idempotent receiver that accepts chunks in any arrival order."""

    def __init__(self, value: ArchiveTransfer) -> None:
        if not isinstance(value, ArchiveTransfer):
            raise ValidationError("assembler requires a typed transfer")
        verify_transfer(value)
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


def _build_from_parts(raw: bytes, archive_value: archive_model.RecoveryExecutionRuntimeRegistryFederationArchive, *, transfer_id: str | None, chunk_size: int) -> ArchiveTransfer:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_TRANSFER_BYTES:
        raise ValidationError("archive bytes are outside the transfer bound")
    chunk_size = _chunk_size(chunk_size)
    parts = {index: raw[offset:offset + chunk_size] for index, offset in enumerate(range(0, len(raw), chunk_size))}
    if len(parts) > MAX_CHUNKS:
        raise ValidationError("archive requires too many transfer chunks")
    chunks = tuple(ArchiveTransferChunk(index, index * chunk_size, len(part), address_chunk(part)) for index, part in parts.items())
    body = {"transfer_id": DEFAULT_TRANSFER_ID if transfer_id is None else _label(transfer_id, "transfer ID"), "version": VERSION, "boundary": BOUNDARY, "archive_address": archive_value.content_address, "archive_size": len(raw), "chunk_size": chunk_size, "chunk_count": len(chunks), "chunks": chunks}
    provisional = ArchiveTransfer(**body, content_address="pending:transfer", payload=parts)
    return ArchiveTransfer(**body, content_address=address_transfer(provisional), payload=parts)


def build_transfer(value: archive_model.RecoveryExecutionRuntimeRegistryFederationArchive, *, transfer_id: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ArchiveTransfer:
    if not isinstance(value, archive_model.RecoveryExecutionRuntimeRegistryFederationArchive):
        raise ValidationError("transfer builder requires a typed federation archive")
    archive_model.verify_archive(value)
    return _build_from_parts(archive_model.archive_bytes(value), value, transfer_id=transfer_id, chunk_size=chunk_size)


def build_transfer_from_bytes(raw: bytes, *, transfer_id: str | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> ArchiveTransfer:
    archive_value = archive_model.load_archive_bytes(raw)
    return _build_from_parts(raw, archive_value, transfer_id=transfer_id, chunk_size=chunk_size)


def transfer_from_mapping(value: Mapping[str, Any]) -> ArchiveTransfer:
    value = _mapping(value, "archive transfer")
    _strict(value, set(ArchiveTransfer.FIELDS), "archive transfer")
    chunks = tuple(ArchiveTransferChunk.from_mapping(item) for item in _sequence(value["chunks"], "transfer chunks", MAX_CHUNKS))
    return ArchiveTransfer(value["transfer_id"], value["version"], value["boundary"], value["archive_address"], value["archive_size"], value["chunk_size"], value["chunk_count"], chunks, value["content_address"])


def _assemble_parts(value: ArchiveTransfer, parts: Mapping[int, bytes]) -> bytes:
    if set(parts) != set(range(value.chunk_count)):
        raise ValidationError("archive assembly requires every transfer chunk")
    stream = io.BytesIO()
    for chunk in value.chunks:
        raw = parts.get(chunk.index)
        if not isinstance(raw, bytes) or len(raw) != chunk.size or address_chunk(raw) != chunk.content_address:
            raise ValidationError("archive assembly found an invalid chunk")
        stream.write(raw)
    raw = stream.getvalue()
    if len(raw) != value.archive_size:
        raise ValidationError("archive assembly size does not match the manifest")
    nested = archive_model.load_archive_bytes(raw)
    if nested.content_address != value.archive_address:
        raise ValidationError("archive assembly address does not match the manifest")
    return raw


def assemble_archive_bytes(value: ArchiveTransfer, parts: Mapping[int, bytes] | None = None) -> bytes:
    if not isinstance(value, ArchiveTransfer):
        raise ValidationError("archive assembly requires a typed transfer")
    verify_transfer(value)
    return _assemble_parts(value, value.payload_bytes() if parts is None else parts)


def verify_transfer(value: ArchiveTransfer) -> ArchiveTransfer:
    if not isinstance(value, ArchiveTransfer):
        raise ValidationError("transfer verification requires a typed transfer")
    value._validate()
    if value._payload:
        _assemble_parts(value, value.payload_bytes())
    return value


def _manifest(value: ArchiveTransfer) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "transfer_id": value.transfer_id, "archive_address": value.archive_address, "archive_size": value.archive_size, "chunk_size": value.chunk_size, "chunk_count": value.chunk_count, "chunks": tuple(chunk.to_dict() for chunk in value.chunks), "transfer_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def manifest_document(value: ArchiveTransfer) -> dict[str, Any]:
    return _manifest(verify_transfer(value))


def manifest_json(value: ArchiveTransfer) -> str:
    return canonical_json(manifest_document(value))


def transfer_json(value: ArchiveTransfer) -> str:
    return canonical_json(transfer_from_mapping(value.to_dict()).to_dict())


def _expected_names(value: ArchiveTransfer, *, indices: Sequence[int] | None = None) -> set[str]:
    selected = range(value.chunk_count) if indices is None else indices
    return {TRANSFER_DIRECTORY_MANIFEST, CHUNK_DIRECTORY, *(chunk_name(index) for index in selected)}


def _validate_chunk_directory(directory: Path, value: ArchiveTransfer, *, require_complete: bool) -> tuple[int, ...]:
    chunk_directory = directory / CHUNK_DIRECTORY
    if chunk_directory.is_symlink() or not chunk_directory.is_dir():
        raise ValidationError("transfer chunks directory is missing or unsafe")
    received: list[int] = []
    for item in chunk_directory.iterdir():
        if item.is_symlink() or not item.is_file() or not item.name.startswith("chunk-") or not item.name.endswith(CHUNK_SUFFIX):
            raise ValidationError("transfer contains an invalid chunk member")
        selected = item.name.removeprefix("chunk-").removesuffix(CHUNK_SUFFIX)
        if not selected.isdigit() or chunk_name(int(selected)) != f"{CHUNK_DIRECTORY}/{item.name}":
            raise ValidationError("transfer chunk name is not canonical")
        index = int(selected)
        if index >= value.chunk_count:
            raise ValidationError("transfer chunk index is outside the manifest")
        received.append(index)
    indices = tuple(sorted(received))
    expected = _expected_names(value, indices=range(value.chunk_count) if require_complete else indices)
    names = {item.relative_to(directory).as_posix() for item in directory.rglob("*")}
    if names != expected:
        raise ValidationError("transfer directory member set is invalid")
    if require_complete and indices != tuple(range(value.chunk_count)):
        raise ValidationError("complete transfer is missing chunks")
    return indices


def _write_atomic_directory(destination: Path, value: ArchiveTransfer, *, parts: Mapping[int, bytes], overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("transfer destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir():
            raise ValidationError("transfer destination must be a regular directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".runtime-registry-federation-transfer-", dir=str(destination.parent)))
    try:
        (temporary / CHUNK_DIRECTORY).mkdir()
        (temporary / TRANSFER_DIRECTORY_MANIFEST).write_bytes(canonical_bytes(_manifest(value)))
        for index in sorted(parts):
            (temporary / chunk_name(index)).write_bytes(parts[index])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_transfer(value: ArchiveTransfer, destination: str | Path, *, overwrite: bool = False) -> Path:
    verify_transfer(value)
    return _write_atomic_directory(Path(destination), value, parts=value.payload_bytes(), overwrite=overwrite)


def write_partial_transfer(assembler: TransferAssembler, destination: str | Path, *, overwrite: bool = False) -> Path:
    if not isinstance(assembler, TransferAssembler):
        raise ValidationError("partial transfer writer requires a transfer assembler")
    verify_transfer(assembler.value)
    return _write_atomic_directory(Path(destination), assembler.value, parts=assembler._parts, overwrite=overwrite)


def _read_manifest(directory: Path) -> ArchiveTransfer:
    manifest_path = directory / TRANSFER_DIRECTORY_MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValidationError("transfer manifest is missing or unsafe")
    raw = manifest_path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("transfer manifest is invalid JSON") from error
    if canonical_bytes(document) != raw:
        raise ValidationError("transfer manifest is not canonical JSON")
    document = _mapping(document, "transfer manifest")
    _strict(document, {"version", "boundary", "transfer_id", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "transfer_address", "manifest_address"}, "transfer manifest")
    expected_manifest = content_hash(dict(document) | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    if document["manifest_address"] != expected_manifest:
        raise ValidationError("transfer manifest address does not replay")
    value = transfer_from_mapping({field: document[field] for field in ArchiveTransfer.FIELDS if field != "content_address"} | {"content_address": document["transfer_address"]})
    if document["version"] != VERSION or document["boundary"] != BOUNDARY or document["transfer_address"] != value.content_address:
        raise ValidationError("transfer manifest contract is invalid")
    return value


def load_transfer(source: str | Path) -> ArchiveTransfer:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("transfer input must be a regular directory")
    value = _read_manifest(directory)
    indices = _validate_chunk_directory(directory, value, require_complete=True)
    parts = {index: (directory / chunk_name(index)).read_bytes() for index in indices}
    loaded = ArchiveTransfer(value.transfer_id, value.version, value.boundary, value.archive_address, value.archive_size, value.chunk_size, value.chunk_count, value.chunks, value.content_address, payload=parts)
    return verify_transfer(loaded)


def load_partial_transfer(source: str | Path) -> TransferAssembler:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("partial transfer input must be a regular directory")
    value = _read_manifest(directory)
    indices = _validate_chunk_directory(directory, value, require_complete=False)
    assembler = TransferAssembler(value)
    for index in indices:
        assembler.add_chunk(index, (directory / chunk_name(index)).read_bytes())
    return assembler


def verify_transfer_directory(source: str | Path) -> ArchiveTransfer:
    return load_transfer(source)


def verify_partial_transfer(source: str | Path) -> TransferAssemblyProgress:
    return load_partial_transfer(source).progress()


def assemble_transfer_directory(source: str | Path) -> bytes:
    value = load_transfer(source)
    return assemble_archive_bytes(value)


def transfer_csv(value: ArchiveTransfer) -> str:
    value = verify_transfer(value)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ArchiveTransferChunk.FIELDS, lineterminator="\n")
    writer.writeheader()
    for chunk in value.chunks:
        writer.writerow(chunk.to_dict())
    return stream.getvalue()


def render_transfer_markdown(value: ArchiveTransfer) -> str:
    value = verify_transfer(value)
    lines = ["# Runtime Registry Federation Archive Transfer", "", f"- Transfer: `{value.transfer_id}`", f"- Archive address: `{value.archive_address}`", f"- Bytes: `{value.archive_size}`", f"- Chunks: `{value.chunk_count}` at `{value.chunk_size}` bytes", f"- Address: `{value.content_address}`", "", "| index | offset | bytes | chunk address |", "| ---: | ---: | ---: | --- |"]
    lines.extend(f"| {chunk.index} | {chunk.offset} | {chunk.size} | {chunk.content_address} |" for chunk in value.chunks)
    return "\n".join(lines) + "\n"


def progress_json(value: TransferAssemblyProgress) -> str:
    if not isinstance(value, TransferAssemblyProgress):
        raise ValidationError("progress JSON requires a typed progress receipt")
    return canonical_json(value.to_dict())


def progress_csv(value: TransferAssemblyProgress) -> str:
    if not isinstance(value, TransferAssemblyProgress):
        raise ValidationError("progress CSV requires a typed progress receipt")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TransferAssemblyProgress.FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.to_dict())
    return stream.getvalue()


def render_progress_markdown(value: TransferAssemblyProgress) -> str:
    if not isinstance(value, TransferAssemblyProgress):
        raise ValidationError("progress Markdown requires a typed progress receipt")
    status = "complete" if value.complete else "partial"
    return "\n".join(("# Runtime Registry Federation Archive Transfer Progress", "", f"- Transfer address: `{value.transfer_address}`", f"- Status: `{status}`", f"- Received: `{len(value.received_indices)}/{value.chunk_count}` chunks", f"- Received bytes: `{value.received_bytes}/{value.archive_size}`", f"- Missing indices: `{', '.join(str(index) for index in value.missing_indices) or 'none'}`", f"- Address: `{value.content_address}`", ""))


def chunk_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime registry federation archive transfer chunk", "type": "object", "additionalProperties": False, "required": list(ArchiveTransferChunk.FIELDS), "properties": {"index": {"type": "integer", "minimum": 0, "maximum": MAX_CHUNKS - 1}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_TRANSFER_BYTES}, "size": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNK_SIZE}, "content_address": {"type": "string", "pattern": "^" + CHUNK_PREFIX + ":"}}}


def transfer_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime registry federation archive transfer", "type": "object", "additionalProperties": False, "required": list(ArchiveTransfer.FIELDS), "properties": {"transfer_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSFER_BYTES}, "chunk_size": {"type": "integer", "minimum": MIN_CHUNK_SIZE, "maximum": MAX_CHUNK_SIZE}, "chunk_count": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNKS}, "chunks": {"type": "array", "items": chunk_schema(), "minItems": 1, "maxItems": MAX_CHUNKS}, "content_address": {"type": "string", "pattern": "^" + TRANSFER_PREFIX + ":"}}}


def manifest_schema() -> dict[str, Any]:
    properties = transfer_schema()["properties"] | {"manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}, "transfer_address": {"type": "string", "pattern": "^" + TRANSFER_PREFIX + ":"}}
    required = [field for field in ArchiveTransfer.FIELDS if field != "content_address"] + ["transfer_address", "manifest_address"]
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime registry federation archive transfer manifest", "type": "object", "additionalProperties": False, "required": required, "properties": properties}


def progress_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Runtime registry federation archive transfer progress", "type": "object", "additionalProperties": False, "required": list(TransferAssemblyProgress.FIELDS), "properties": {"transfer_address": {"type": "string", "pattern": "^" + TRANSFER_PREFIX + ":"}, "archive_address": {"type": "string", "pattern": "^" + archive_model.ARCHIVE_PREFIX + ":"}, "archive_size": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSFER_BYTES}, "chunk_count": {"type": "integer", "minimum": 1, "maximum": MAX_CHUNKS}, "received_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "missing_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "received_bytes": {"type": "integer", "minimum": 0}, "complete": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + PROGRESS_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "transfer_prefix": TRANSFER_PREFIX, "chunk_prefix": CHUNK_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "progress_prefix": PROGRESS_PREFIX, "default_chunk_size": DEFAULT_CHUNK_SIZE, "min_chunk_size": MIN_CHUNK_SIZE, "max_chunk_size": MAX_CHUNK_SIZE, "max_chunks": MAX_CHUNKS, "max_transfer_bytes": MAX_TRANSFER_BYTES, "features": ["verified archive anchoring", "contiguous byte ranges", "addressed chunk receipts", "out-of-order assembly", "idempotent duplicate chunks", "atomic complete persistence", "atomic partial persistence", "fail-closed nested archive reassembly"], "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["ArchiveTransfer", "ArchiveTransferChunk", "BOUNDARY", "CHUNK_PREFIX", "DEFAULT_CHUNK_SIZE", "DEFAULT_TRANSFER_ID", "MANIFEST_PREFIX", "MAX_CHUNK_SIZE", "MAX_CHUNKS", "MAX_TRANSFER_BYTES", "MIN_CHUNK_SIZE", "PROGRESS_PREFIX", "TRANSFER_DIRECTORY_MANIFEST", "TRANSFER_PREFIX", "TransferAssemblyProgress", "TransferAssembler", "VERSION", "address_chunk", "address_progress", "address_transfer", "assemble_archive_bytes", "assemble_transfer_directory", "build_transfer", "build_transfer_from_bytes", "capabilities", "chunk_name", "chunk_schema", "load_partial_transfer", "load_transfer", "manifest_document", "manifest_json", "manifest_schema", "progress_csv", "progress_json", "progress_schema", "render_progress_markdown", "render_transfer_markdown", "transfer_csv", "transfer_from_mapping", "transfer_json", "transfer_schema", "verify_partial_transfer", "verify_transfer", "verify_transfer_directory", "write_partial_transfer", "write_transfer"]

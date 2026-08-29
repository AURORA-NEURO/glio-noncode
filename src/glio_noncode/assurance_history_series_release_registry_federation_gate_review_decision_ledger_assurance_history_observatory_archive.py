"""Deterministic offline archives for assurance-history observatories.

The observatory package is intentionally persisted as an exact directory. This
module adds a single-file transport boundary without changing the underlying
package authority. The archive contains one envelope manifest and the exact
five observatory package files beneath ``observatory/``. ZIP timestamps,
ordering, compression, and permissions are fixed so equal packages produce
equal archive bytes.

Archive loading is fail-closed. It rejects duplicate or unexpected ZIP names,
directories, symlinks, traversal-like names, encrypted members, non-canonical
JSON, byte-receipt drift, manifest drift, and payloads that cannot be loaded
by the independent observatory package verifier. Public projections retain
addresses and contract facts only; input paths and attribution metadata stay
outside the archive boundary.
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

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory as observatory_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = observatory_model.VERSION + "-archive-v1"
BOUNDARY = observatory_model.BOUNDARY + "_archive"
ARCHIVE_PREFIX = "glio-noncode-assurance-history-observatory-archive"
ARCHIVE_QUERY_PREFIX = ARCHIVE_PREFIX + "-query"
MANIFEST_PREFIX = ARCHIVE_PREFIX + "-manifest"
PAYLOAD_PREFIX = "observatory/"
ARCHIVE_MANIFEST_NAME = "manifest.json"
ARCHIVE_PAYLOAD_FILES = tuple(PAYLOAD_PREFIX + name for name in observatory_model.FILES)
FILES = (ARCHIVE_MANIFEST_NAME, *ARCHIVE_PAYLOAD_FILES)
DEFAULT_ARCHIVE_ID = "glio-noncode-assurance-history-observatory-archive"
DEFAULT_LIMIT = 50
MAX_FILES = len(observatory_model.FILES)
MAX_QUERY_ITEMS = observatory_model.MAX_QUERY_ITEMS
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} must be a public content address")
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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    private_markers = ("C:\\", "D:\\", "/Users/", "/home/", "\\Users\\", "\\home\\")

    def walk(node: Any) -> bool:
        if isinstance(node, Mapping):
            return all(str(key).lower() not in forbidden and walk(item) for key, item in node.items())
        if isinstance(node, (tuple, list)):
            return all(walk(item) for item in node)
        return not (isinstance(node, str) and any(marker in node for marker in private_markers))

    return walk(value)


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARCHIVE_PREFIX + "-artifact")}


def _payload_key(name: str) -> str:
    if not name.startswith(PAYLOAD_PREFIX):
        raise ValidationError("archive payload name is outside the payload prefix")
    selected = name.removeprefix(PAYLOAD_PREFIX)
    if selected not in observatory_model.FILES:
        raise ValidationError("archive payload name is not an observatory file")
    return selected


def _package_artifacts(package: observatory_model.ObservatoryPackage) -> dict[str, bytes]:
    value = package.observatory
    return {
        PAYLOAD_PREFIX + observatory_model.OBSERVATORY_NAME: canonical_bytes(value.to_dict()),
        PAYLOAD_PREFIX + observatory_model.MEMBERS_NAME: canonical_bytes({"version": observatory_model.VERSION, "boundary": observatory_model.BOUNDARY, "observatory_id": value.observatory_id, "member_count": value.member_count, "members": tuple(item.to_dict() for item in value.members)}),
        PAYLOAD_PREFIX + observatory_model.VERIFICATION_NAME: canonical_bytes(package.verification.to_dict()),
        PAYLOAD_PREFIX + observatory_model.METRICS_NAME: canonical_bytes(package.metrics),
        PAYLOAD_PREFIX + observatory_model.MANIFEST_NAME: _embedded_manifest_bytes(value, package),
    }


def _embedded_manifest_bytes(value: observatory_model.AssuranceHistoryObservatory, package: observatory_model.ObservatoryPackage) -> bytes:
    artifacts = {
        PAYLOAD_PREFIX + observatory_model.OBSERVATORY_NAME: canonical_bytes(value.to_dict()),
        PAYLOAD_PREFIX + observatory_model.MEMBERS_NAME: canonical_bytes({"version": observatory_model.VERSION, "boundary": observatory_model.BOUNDARY, "observatory_id": value.observatory_id, "member_count": value.member_count, "members": tuple(item.to_dict() for item in value.members)}),
        PAYLOAD_PREFIX + observatory_model.VERIFICATION_NAME: canonical_bytes(package.verification.to_dict()),
        PAYLOAD_PREFIX + observatory_model.METRICS_NAME: canonical_bytes(package.metrics),
    }
    body = {"version": observatory_model.VERSION, "boundary": observatory_model.BOUNDARY, "observatory_id": value.observatory_id, "observatory_address": value.content_address, "verification_address": package.verification.content_address, "artifact_count": 4, "files": tuple(observatory_model.FILES[1:]), "artifacts": tuple(observatory_model._artifact(name.removeprefix(PAYLOAD_PREFIX), raw) for name, raw in artifacts.items())}
    body["manifest_address"] = content_hash(body | {"manifest_address": None}, prefix=observatory_model.MANIFEST_PREFIX)
    return canonical_bytes(body)


def _read_package_artifacts(directory: Path) -> dict[str, bytes]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("observatory source must be a regular directory")
    package = observatory_model.load_package(directory)
    del package
    return {PAYLOAD_PREFIX + name: (directory / name).read_bytes() for name in observatory_model.FILES}


class ObservatoryArchive:
    """Public archive envelope with optional verified payload bytes."""

    def __init__(self, archive_id: str, version: str, boundary: str, observatory_id: str, observatory_address: str, verification_address: str, artifact_count: int, files: Sequence[str], artifacts: Sequence[Mapping[str, Any]], content_address: str, payload: Mapping[str, bytes] | None = None, package: observatory_model.ObservatoryPackage | None = None) -> None:
        self.archive_id = archive_id
        self.version = version
        self.boundary = boundary
        self.observatory_id = observatory_id
        self.observatory_address = observatory_address
        self.verification_address = verification_address
        self.artifact_count = artifact_count
        self.files = tuple(files)
        self.artifacts = tuple(dict(item) for item in artifacts)
        self.content_address = content_address
        self._payload = dict(payload or {})
        self._package = package
        self._validate()

    def _validate(self) -> None:
        _text(self.archive_id, "archive ID")
        _text(self.version, "archive version", 1024)
        _text(self.boundary, "archive boundary", 512)
        _text(self.observatory_id, "observatory ID")
        _address(self.observatory_address, "archive observatory address")
        _address(self.verification_address, "archive verification address")
        _count(self.artifact_count, "archive artifact count", MAX_FILES)
        if self.artifact_count != MAX_FILES or self.files != ARCHIVE_PAYLOAD_FILES or len(self.artifacts) != MAX_FILES:
            raise ValidationError("archive payload file contract is invalid")
        if tuple(item.get("name") for item in self.artifacts) != ARCHIVE_PAYLOAD_FILES:
            raise ValidationError("archive artifact ordering is invalid")
        for item in self.artifacts:
            _strict(item, {"name", "size", "hash"}, "archive artifact")
            _text(item["name"], "archive artifact name", 256)
            _count(item["size"], "archive artifact size", 32 * 1024 * 1024)
            _address(item["hash"], "archive artifact hash")
        _address(self.content_address, "archive content address")
        if not _public(self.to_dict()):
            raise ValidationError("archive crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_archive(self) != self.content_address:
            raise ValidationError("archive content address mismatch")
        if self._payload:
            if set(self._payload) != set(ARCHIVE_PAYLOAD_FILES):
                raise ValidationError("archive payload bytes are incomplete")
            for item in self.artifacts:
                if item != _artifact(item["name"], self._payload[item["name"]]):
                    raise ValidationError("archive payload artifact receipt mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_id": self.archive_id, "version": self.version, "boundary": self.boundary, "observatory_id": self.observatory_id, "observatory_address": self.observatory_address, "verification_address": self.verification_address, "artifact_count": self.artifact_count, "files": self.files, "artifacts": self.artifacts, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("archive_id", "version", "boundary", "observatory_id", "observatory_address", "verification_address", "artifact_count", "content_address")}

    def payload_bytes(self) -> Mapping[str, bytes]:
        if not self._payload:
            raise ValidationError("archive payload bytes are unavailable")
        return dict(self._payload)


def address_archive(value: ObservatoryArchive) -> str:
    if not isinstance(value, ObservatoryArchive):
        raise ValidationError("archive address requires a typed archive")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARCHIVE_PREFIX)


def build_archive(value: observatory_model.AssuranceHistoryObservatory, *, archive_id: str | None = None) -> ObservatoryArchive:
    if not isinstance(value, observatory_model.AssuranceHistoryObservatory):
        raise ValidationError("archive builder requires a typed observatory")
    package = observatory_model.package_from_values(value)
    payload = _package_artifacts(package)
    artifacts = tuple(_artifact(name, payload[name]) for name in ARCHIVE_PAYLOAD_FILES)
    body = {"archive_id": DEFAULT_ARCHIVE_ID if archive_id is None else _text(archive_id, "archive ID"), "version": VERSION, "boundary": BOUNDARY, "observatory_id": value.observatory_id, "observatory_address": value.content_address, "verification_address": package.verification.content_address, "artifact_count": MAX_FILES, "files": ARCHIVE_PAYLOAD_FILES, "artifacts": artifacts}
    provisional = ObservatoryArchive(**body, content_address="pending:archive", payload=payload, package=package)
    return ObservatoryArchive(**body, content_address=address_archive(provisional), payload=payload, package=package)


def build_archive_from_directory(directory: str | Path, *, archive_id: str | None = None) -> ObservatoryArchive:
    source = Path(directory)
    package = observatory_model.load_package(source)
    payload = _read_package_artifacts(source)
    value = package.observatory
    artifacts = tuple(_artifact(name, payload[name]) for name in ARCHIVE_PAYLOAD_FILES)
    body = {"archive_id": DEFAULT_ARCHIVE_ID if archive_id is None else _text(archive_id, "archive ID"), "version": VERSION, "boundary": BOUNDARY, "observatory_id": value.observatory_id, "observatory_address": value.content_address, "verification_address": package.verification.content_address, "artifact_count": MAX_FILES, "files": ARCHIVE_PAYLOAD_FILES, "artifacts": artifacts}
    provisional = ObservatoryArchive(**body, content_address="pending:archive", payload=payload, package=package)
    return ObservatoryArchive(**body, content_address=address_archive(provisional), payload=payload, package=package)


def archive_from_mapping(value: Mapping[str, Any]) -> ObservatoryArchive:
    value = _mapping(value, "observatory archive")
    _strict(value, {"archive_id", "version", "boundary", "observatory_id", "observatory_address", "verification_address", "artifact_count", "files", "artifacts", "content_address"}, "observatory archive")
    artifacts = _sequence(value.get("artifacts"), "archive artifacts", MAX_FILES)
    return ObservatoryArchive(archive_id=value["archive_id"], version=value["version"], boundary=value["boundary"], observatory_id=value["observatory_id"], observatory_address=value["observatory_address"], verification_address=value["verification_address"], artifact_count=value["artifact_count"], files=_sequence(value.get("files"), "archive files", MAX_FILES), artifacts=artifacts, content_address=value["content_address"])


def verify_archive(value: ObservatoryArchive) -> ObservatoryArchive:
    if not isinstance(value, ObservatoryArchive):
        raise ValidationError("archive verification requires a typed archive")
    value._validate()
    if value._package is not None:
        if value._package.observatory.content_address != value.observatory_address or value._package.verification.content_address != value.verification_address:
            raise ValidationError("archive package linkage is invalid")
        if value._package.observatory.observatory_id != value.observatory_id:
            raise ValidationError("archive package identity is invalid")
    return value


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    info.comment = b""
    return info


def _archive_manifest(value: ObservatoryArchive) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "archive_id": value.archive_id, "observatory_id": value.observatory_id, "observatory_address": value.observatory_address, "verification_address": value.verification_address, "artifact_count": MAX_FILES, "files": ARCHIVE_PAYLOAD_FILES, "artifacts": value.artifacts, "archive_address": value.content_address}
    body["manifest_address"] = content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    return body


def _archive_bytes(value: ObservatoryArchive) -> bytes:
    verify_archive(value)
    payload = value.payload_bytes()
    manifest = canonical_bytes(_archive_manifest(value))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(_zip_info(ARCHIVE_MANIFEST_NAME), manifest)
        for name in ARCHIVE_PAYLOAD_FILES:
            archive.writestr(_zip_info(name), payload[name])
        archive.comment = b""
    return stream.getvalue()


def archive_bytes(value: ObservatoryArchive) -> bytes:
    return _archive_bytes(value)


def _write_atomic_file(destination: Path, raw: bytes, *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("archive destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_file():
            raise ValidationError("archive destination must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".gnd-observatory-archive-", suffix=".zip", dir=str(destination.parent))
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def write_archive(value: ObservatoryArchive, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_file(Path(destination), _archive_bytes(value), overwrite=overwrite)


def _zip_member_regular(info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or info.flag_bits & 0x1:
        return False
    if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
        return False
    return True


def _read_archive(source: str | Path | bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    if isinstance(source, bytes):
        stream = io.BytesIO(source)
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise ValidationError("archive input must be a regular file")
        stream = path.open("rb")
    try:
        try:
            archive = zipfile.ZipFile(stream, mode="r")
        except (OSError, zipfile.BadZipFile) as error:
            raise ValidationError("archive input is not a valid ZIP") from error
        with archive:
            if archive.comment:
                raise ValidationError("archive comment is not permitted")
            infos = archive.infolist()
            if len(infos) != len(FILES) or len({info.filename for info in infos}) != len(infos) or {info.filename for info in infos} != set(FILES):
                raise ValidationError("archive member set is invalid")
            if any(not _zip_member_regular(info) for info in infos):
                raise ValidationError("archive contains a non-regular or encrypted member")
            raw_by_name = {info.filename: archive.read(info) for info in infos}
        try:
            manifest_value = json.loads(raw_by_name[ARCHIVE_MANIFEST_NAME].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValidationError("archive manifest is invalid JSON") from error
        manifest = dict(_mapping(manifest_value, "archive manifest"))
        if canonical_bytes(manifest) != raw_by_name[ARCHIVE_MANIFEST_NAME]:
            raise ValidationError("archive manifest is not canonical JSON")
        payload = {name: raw_by_name[name] for name in ARCHIVE_PAYLOAD_FILES}
        return manifest, payload
    finally:
        stream.close()


def _package_from_payload(payload: Mapping[str, bytes]) -> observatory_model.ObservatoryPackage:
    with tempfile.TemporaryDirectory(prefix="gnd-observatory-archive-load-") as temporary:
        directory = Path(temporary)
        for name in observatory_model.FILES:
            (directory / name).write_bytes(payload[PAYLOAD_PREFIX + name])
        return observatory_model.load_package(directory)


def _archive_from_manifest(manifest: Mapping[str, Any], payload: Mapping[str, bytes]) -> ObservatoryArchive:
    allowed = {"version", "boundary", "archive_id", "observatory_id", "observatory_address", "verification_address", "artifact_count", "files", "artifacts", "archive_address", "manifest_address"}
    _strict(manifest, allowed, "archive manifest")
    expected_manifest_address = content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    if manifest.get("version") != VERSION or manifest.get("boundary") != BOUNDARY or manifest.get("artifact_count") != MAX_FILES or tuple(manifest.get("files", ())) != ARCHIVE_PAYLOAD_FILES or manifest.get("manifest_address") != expected_manifest_address:
        raise ValidationError("archive manifest contract is invalid")
    artifacts = _sequence(manifest.get("artifacts"), "archive manifest artifacts", MAX_FILES)
    for item in artifacts:
        item = _mapping(item, "archive manifest artifact")
        name = item.get("name")
        if name not in payload or dict(item) != _artifact(name, payload[name]):
            raise ValidationError("archive artifact bytes are not addressed")
    package = _package_from_payload(payload)
    if manifest.get("observatory_id") != package.observatory.observatory_id or manifest.get("observatory_address") != package.observatory.content_address or manifest.get("verification_address") != package.verification.content_address:
        raise ValidationError("archive manifest linkage is invalid")
    body = {"archive_id": manifest["archive_id"], "version": manifest["version"], "boundary": manifest["boundary"], "observatory_id": manifest["observatory_id"], "observatory_address": manifest["observatory_address"], "verification_address": manifest["verification_address"], "artifact_count": manifest["artifact_count"], "files": tuple(manifest["files"]), "artifacts": tuple(dict(item) for item in artifacts)}
    provisional = ObservatoryArchive(**body, content_address="pending:archive", payload=payload, package=package)
    expected_address = address_archive(provisional)
    if manifest.get("archive_address") != expected_address:
        raise ValidationError("archive address linkage is invalid")
    return ObservatoryArchive(**body, content_address=expected_address, payload=payload, package=package)


def load_archive(source: str | Path | bytes) -> ObservatoryArchive:
    manifest, payload = _read_archive(source)
    return _archive_from_manifest(manifest, payload)


def load_archive_bytes(raw: bytes) -> ObservatoryArchive:
    if not isinstance(raw, bytes):
        raise ValidationError("archive bytes must be bytes")
    return load_archive(raw)


def load_archive_package(source: str | Path | bytes) -> observatory_model.ObservatoryPackage:
    value = load_archive(source)
    return value._package or _package_from_payload(value.payload_bytes())


def verify_archive_file(source: str | Path | bytes) -> ObservatoryArchive:
    return load_archive(source)


def verify_archive_bytes(raw: bytes) -> ObservatoryArchive:
    return load_archive_bytes(raw)


def manifest_document(value: ObservatoryArchive) -> dict[str, Any]:
    verify_archive(value)
    return _archive_manifest(value)


def manifest_json(value: ObservatoryArchive) -> str:
    return canonical_json(manifest_document(value))


def query_archive_bytes(raw: bytes, query: ArchiveQuery | None = None, **kwargs: Any) -> ArchiveQueryResult:
    return query_archive(load_archive_bytes(raw), query, **kwargs)


def extract_archive(source: str | Path, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = load_archive(source)
    payload = value.payload_bytes()
    target = Path(destination)
    if target.exists():
        if not overwrite:
            raise ValidationError("extraction destination exists; explicit overwrite is required")
        if target.is_symlink() or not target.is_dir() or any(item.is_symlink() for item in target.iterdir()) or {item.name for item in target.iterdir()} != set(observatory_model.FILES):
            raise ValidationError("extraction destination is not an exact compatible directory")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-observatory-extract-", dir=str(target.parent)))
    try:
        for name in observatory_model.FILES:
            (temporary / name).write_bytes(payload[PAYLOAD_PREFIX + name])
        observatory_model.load_package(temporary)
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


class ArchiveQuery:
    """Bounded query over an archive envelope and its verified package."""

    RESOURCES = ("summary", "files", "members", "checks", "failed", "required", "optional")

    def __init__(self, resource: str = "summary", severity: str | None = None, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "archive query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("archive query resource is not supported")
        self.severity = None if severity is None else observatory_model._severity(severity, "archive query severity")
        self.passed = None if passed is None else _bool(passed, "archive query passed")
        self.text = None if text is None else _text(text, "archive query text", 512)
        self.offset = _count(offset, "archive query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "archive query limit", MAX_QUERY_ITEMS, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "severity": self.severity, "passed": self.passed, "text": self.text, "offset": self.offset, "limit": self.limit}


class ArchiveQueryResult:
    def __init__(self, archive_address: str, query: ArchiveQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.archive_address = archive_address
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.archive_address, "archive query archive address")
        _count(self.total_count, "archive query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "archive query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.query.limit or self.returned_count > self.total_count:
            raise ValidationError("archive query window is invalid")
        _address(self.content_address, "archive query content address")
        if not _public(self.to_dict()):
            raise ValidationError("archive query crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_archive_query(self) != self.content_address:
            raise ValidationError("archive query content address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"archive_address": self.archive_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}


def address_archive_query(value: ArchiveQueryResult) -> str:
    if not isinstance(value, ArchiveQueryResult):
        raise ValidationError("archive query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARCHIVE_QUERY_PREFIX)


def _matches_archive_record(record: Mapping[str, Any], query: ArchiveQuery) -> bool:
    if query.severity is not None and record.get("severity") != query.severity:
        return False
    if query.passed is not None and record.get("passed") != query.passed:
        return False
    if query.resource == "failed" and record.get("passed"):
        return False
    if query.resource == "required" and record.get("severity") != "required":
        return False
    if query.resource == "optional" and record.get("severity") != "optional":
        return False
    return not query.text or query.text.lower() in canonical_json(record).lower()


def _archive_package(value: ObservatoryArchive) -> observatory_model.ObservatoryPackage:
    if value._package is not None:
        return value._package
    return _package_from_payload(value.payload_bytes())


def query_archive(value: ObservatoryArchive, query: ArchiveQuery | None = None, **kwargs: Any) -> ArchiveQueryResult:
    verify_archive(value)
    query = ArchiveQuery(**kwargs) if query is None else query
    if not isinstance(query, ArchiveQuery):
        raise ValidationError("archive query requires a typed query")
    package = _archive_package(value)
    if query.resource == "summary":
        records = (value.summary(),)
        total = 1
    elif query.resource == "files":
        matching = tuple(item for item in value.artifacts if not query.text or query.text.lower() in canonical_json(item).lower())
        total = len(matching)
        records = matching[query.offset : query.offset + query.limit]
    elif query.resource == "members":
        matching = tuple(item.summary() for item in package.observatory.members if not query.text or query.text.lower() in canonical_json(item.to_dict()).lower())
        total = len(matching)
        records = matching[query.offset : query.offset + query.limit]
    else:
        matching = tuple(check.to_dict() for check in package.verification.checks if _matches_archive_record(check.to_dict(), query))
        total = len(matching)
        records = matching[query.offset : query.offset + query.limit]
    body = {"archive_address": value.content_address, "query": query, "total_count": total, "records": records}
    provisional = ArchiveQueryResult(**body, content_address="pending:archive-query")
    return ArchiveQueryResult(**body, content_address=address_archive_query(provisional))


def archive_json(value: ObservatoryArchive) -> str:
    verify_archive(value)
    return canonical_json(value.to_dict())


def query_json(value: ArchiveQueryResult) -> str:
    if not isinstance(value, ArchiveQueryResult):
        raise ValidationError("archive query JSON requires a typed result")
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: canonical_json(row.get(field)) if isinstance(row.get(field), (dict, list, tuple)) else row.get(field) for field in fields})
    return stream.getvalue()


def archive_csv(value: ObservatoryArchive) -> str:
    return _csv_text((value.summary(),), tuple(value.summary()))


def query_csv(value: ArchiveQueryResult) -> str:
    if not isinstance(value, ArchiveQueryResult):
        raise ValidationError("archive query CSV requires a typed result")
    fields = tuple(value.records[0]) if value.records else ("archive_address", "query", "total_count", "returned_count", "content_address")
    return _csv_text(value.records, fields)


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", "", "| Field | Value |", "| --- | --- |"]
    lines.extend(f"| {key} | {canonical_json(value)} |" for key, value in summary.items())
    if rows:
        fields = tuple(rows[0])
        lines.extend(("", "## Records", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
        lines.extend("| " + " | ".join(canonical_json(row.get(field)) for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_markdown(value: ObservatoryArchive) -> str:
    verify_archive(value)
    return _markdown("Assurance history observatory archive", value.summary(), value.artifacts)


def render_query_markdown(value: ArchiveQueryResult) -> str:
    if not isinstance(value, ArchiveQueryResult):
        raise ValidationError("archive query Markdown requires a typed result")
    return _markdown("Assurance history observatory archive query", {key: item for key, item in value.to_dict().items() if key != "records"}, value.records)


def _string_schema(maximum: int = 512) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _address_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": r"^[^:]+:.+$", "maxLength": 2048}


def _integer_schema(maximum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": 0, "maximum": maximum}


def _enum_schema(enum_type: type) -> dict[str, Any]:
    return {"type": "string", "enum": [item.value for item in enum_type]}


def artifact_schema() -> dict[str, Any]:
    fields = {"name": _string_schema(256), "size": _integer_schema(32 * 1024 * 1024), "hash": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def archive_schema() -> dict[str, Any]:
    fields = {"archive_id": _string_schema(), "version": _string_schema(1024), "boundary": _string_schema(512), "observatory_id": _string_schema(), "observatory_address": _address_schema(), "verification_address": _address_schema(), "artifact_count": _integer_schema(MAX_FILES), "files": {"type": "array", "minItems": MAX_FILES, "maxItems": MAX_FILES, "items": _string_schema(256)}, "artifacts": {"type": "array", "minItems": MAX_FILES, "maxItems": MAX_FILES, "items": artifact_schema()}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(ArchiveQuery.RESOURCES)}, "severity": {"anyOf": [{"type": "string", "enum": [item.value for item in observatory_model.ObservatoryCheckSeverity]}, {"type": "null"}]}, "passed": {"anyOf": [{"type": "boolean"}, {"type": "null"}]}, "text": {"anyOf": [_string_schema(512), {"type": "null"}]}, "offset": _integer_schema(MAX_QUERY_ITEMS), "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_ITEMS}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    fields = {"archive_address": _address_schema(), "query": query_schema(), "total_count": _integer_schema(MAX_QUERY_ITEMS), "returned_count": _integer_schema(MAX_QUERY_ITEMS), "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object"}}, "content_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def manifest_schema() -> dict[str, Any]:
    fields = {"version": _string_schema(1024), "boundary": _string_schema(512), "archive_id": _string_schema(), "observatory_id": _string_schema(), "observatory_address": _address_schema(), "verification_address": _address_schema(), "artifact_count": _integer_schema(MAX_FILES), "files": {"type": "array", "minItems": MAX_FILES, "maxItems": MAX_FILES, "items": _string_schema(256)}, "artifacts": {"type": "array", "minItems": MAX_FILES, "maxItems": MAX_FILES, "items": artifact_schema()}, "archive_address": _address_schema(), "manifest_address": _address_schema()}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_files": observatory_model.FILES, "archive_files": FILES, "payload_prefix": PAYLOAD_PREFIX, "limits": {"max_files": MAX_FILES, "max_query_items": MAX_QUERY_ITEMS}, "features": ("fixed-order fixed-timestamp ZIP transport", "exact observatory payload preservation", "artifact byte receipts", "manifest and content-address linkage", "secure regular-file rehydration", "archive summary file member and verification queries", "byte-oriented loading and verification", "deterministic JSON CSV and Markdown projections"), "resources": ArchiveQuery.RESOURCES, "schemas": ("artifact", "archive", "manifest", "query", "query-result")}


__all__ = [
    "ARCHIVE_MANIFEST_NAME",
    "ARCHIVE_PAYLOAD_FILES",
    "ARCHIVE_PREFIX",
    "ARCHIVE_QUERY_PREFIX",
    "BOUNDARY",
    "DEFAULT_ARCHIVE_ID",
    "DEFAULT_LIMIT",
    "FILES",
    "MANIFEST_PREFIX",
    "MAX_FILES",
    "MAX_QUERY_ITEMS",
    "PAYLOAD_PREFIX",
    "VERSION",
    "ArchiveQuery",
    "ArchiveQueryResult",
    "ObservatoryArchive",
    "address_archive",
    "address_archive_query",
    "archive_bytes",
    "archive_csv",
    "archive_from_mapping",
    "archive_json",
    "manifest_document",
    "manifest_json",
    "manifest_schema",
    "archive_schema",
    "artifact_schema",
    "build_archive",
    "build_archive_from_directory",
    "capabilities",
    "extract_archive",
    "load_archive",
    "load_archive_bytes",
    "load_archive_package",
    "query_archive",
    "query_archive_bytes",
    "query_csv",
    "query_json",
    "query_result_schema",
    "query_schema",
    "render_markdown",
    "render_query_markdown",
    "verify_archive",
    "verify_archive_bytes",
    "verify_archive_file",
    "write_archive",
]

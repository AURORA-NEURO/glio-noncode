"""Build, verify, query, and safely unpack deterministic packet archives."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet import (
    load_module_workbench_execution_packet,
)
from .module_workbench_execution_packet_archive_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_ENTRY_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION,
    ModuleWorkbenchExecutionPacketArchive,
    ModuleWorkbenchExecutionPacketArchiveCheck,
    ModuleWorkbenchExecutionPacketArchiveCheckPlane,
    ModuleWorkbenchExecutionPacketArchiveEntry,
    ModuleWorkbenchExecutionPacketArchiveEntryKind,
    ModuleWorkbenchExecutionPacketArchiveState,
    ModuleWorkbenchExecutionPacketArchiveVerification,
    address_module_workbench_execution_packet_archive,
    address_module_workbench_execution_packet_archive_check,
    address_module_workbench_execution_packet_archive_entry,
    address_module_workbench_execution_packet_archive_verification,
)
from .module_workbench_execution_packet_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
    ModuleWorkbenchExecutionPacket,
    ModuleWorkbenchExecutionPacketArtifact,
    ModuleWorkbenchExecutionPacketArtifactKind,
    ModuleWorkbenchExecutionPacketCheck,
    ModuleWorkbenchExecutionPacketCheckPlane,
    ModuleWorkbenchExecutionPacketState,
)
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"


def _safe_path(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
    ):
        return False
    parts = tuple(value.split("/"))
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _line_count(payload: bytes) -> int:
    try:
        return len(payload.decode(_UTF8).splitlines())
    except UnicodeDecodeError:
        return 0


def _archive_check(
    check_id: str,
    plane: ModuleWorkbenchExecutionPacketArchiveCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_check(provisional),
    )


def _read_archive(value: bytes | bytearray | str | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, (str, Path)):
        try:
            return Path(value).read_bytes()
        except OSError as exc:
            raise ValidationError(f"cannot read packet archive: {exc}") from exc
    raise ValidationError("packet archive input must be bytes or a path")


def _packet(value: ModuleWorkbenchExecutionPacket | str | Path) -> ModuleWorkbenchExecutionPacket:
    if isinstance(value, ModuleWorkbenchExecutionPacket):
        if not value.accepted:
            raise ValidationError("cannot archive a blocked packet")
        return value
    return load_module_workbench_execution_packet(value)


def _zip_member(name: str, payload: bytes) -> zipfile.ZipInfo:
    if not _safe_path(name):
        raise ValidationError(f"unsafe packet archive member: {name}")
    info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.external_attr = 0
    info.extra = b""
    info.comment = b""
    if len(payload) > 0xFFFFFFFF:
        raise ValidationError("packet archive member is too large")
    return info


def _manifest_bytes(packet: ModuleWorkbenchExecutionPacket) -> bytes:
    return (canonical_json(packet.to_dict(include_payloads=False)) + "\n").encode(_UTF8)


def _members(packet: ModuleWorkbenchExecutionPacket) -> tuple[tuple[str, bytes, str, str], ...]:
    members: list[tuple[str, bytes, str, str]] = [
        (
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST,
            _manifest_bytes(packet),
            "application/json",
            "manifest",
        )
    ]
    for artifact in packet.artifacts:
        if artifact.payload is None:
            raise ValidationError(f"packet artifact has no payload: {artifact.artifact_id}")
        members.append(
            (
                artifact.relative_path,
                artifact.payload.encode(_UTF8),
                artifact.media_type,
                artifact.artifact_id,
            )
        )
    return tuple(members)


def _archive_bytes(packet: ModuleWorkbenchExecutionPacket) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as handle:
        for relative_path, payload, _, _ in _members(packet):
            handle.writestr(_zip_member(relative_path, payload), payload)
    return output.getvalue()


def _entry(
    ordinal: int,
    relative_path: str,
    payload: bytes,
    media_type: str,
    entry_id: str,
    kind: ModuleWorkbenchExecutionPacketArchiveEntryKind,
) -> ModuleWorkbenchExecutionPacketArchiveEntry:
    body = {
        "entry_id": entry_id,
        "relative_path": relative_path,
        "kind": kind,
        "media_type": media_type,
        "ordinal": ordinal,
        "byte_count": len(payload),
        "line_count": _line_count(payload),
        "content_address": hash_bytes(
            payload,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_ENTRY_PREFIX,
        ),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveEntry(**body)
    if address_module_workbench_execution_packet_archive_entry(provisional) == "":
        raise ValidationError("archive entry address cannot be empty")
    return provisional


def build_module_workbench_execution_packet_archive(
    value: ModuleWorkbenchExecutionPacket | str | Path,
    *,
    archive_id: str = "glio-noncode-module-workbench-execution-archive",
) -> ModuleWorkbenchExecutionPacketArchive:
    """Create deterministic ZIP_STORED bytes for an accepted packet."""

    if not isinstance(archive_id, str) or not archive_id.strip():
        raise ValidationError("packet archive ID is required")
    packet = _packet(value)
    archive_bytes = _archive_bytes(packet)
    entries = tuple(
        _entry(
            index,
            relative_path,
            payload,
            media_type,
            entry_id,
            ModuleWorkbenchExecutionPacketArchiveEntryKind.MANIFEST
            if index == 0
            else ModuleWorkbenchExecutionPacketArchiveEntryKind.ARTIFACT,
        )
        for index, (relative_path, payload, media_type, entry_id) in enumerate(_members(packet))
    )
    body = {
        "archive_id": archive_id,
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_BOUNDARY,
        "archive_format": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT,
        "packet_id": packet.packet_id,
        "packet_address": packet.content_address,
        "archive_address": hash_bytes(
            archive_bytes,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX,
        ),
        "archive_byte_count": len(archive_bytes),
        "payload_byte_count": sum(item.byte_count for item in entries),
        "entry_count": len(entries),
        "artifact_count": packet.artifact_count,
        "entries": entries,
        "state": ModuleWorkbenchExecutionPacketArchiveState.ACCEPTED,
        "accepted": True,
    }
    provisional = ModuleWorkbenchExecutionPacketArchive(
        **body,
        content_address="pending",
        archive_bytes=archive_bytes,
    )
    return ModuleWorkbenchExecutionPacketArchive(
        **body,
        content_address=address_module_workbench_execution_packet_archive(provisional),
        archive_bytes=archive_bytes,
    )


def module_workbench_execution_packet_archive_bytes(
    value: ModuleWorkbenchExecutionPacketArchive,
) -> bytes:
    """Return the exact binary archive after validating its descriptor."""

    verify_module_workbench_execution_packet_archive_value(value)
    return value.archive_bytes


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_module_workbench_execution_packet_archive(
    value: ModuleWorkbenchExecutionPacketArchive | ModuleWorkbenchExecutionPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchExecutionPacketArchive:
    """Write one exact archive file using atomic replacement."""

    archive = (
        value
        if isinstance(value, ModuleWorkbenchExecutionPacketArchive)
        else build_module_workbench_execution_packet_archive(value)
    )
    verify_module_workbench_execution_packet_archive_value(archive)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet archive destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet archive destination is not a file")
    _atomic_write(path, archive.archive_bytes)
    return archive


def _zip_infos(raw: bytes) -> tuple[zipfile.ZipInfo, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return tuple(handle.infolist())
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValidationError(f"cannot read packet archive ZIP: {exc}") from exc


def _read_members(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return {info.filename: handle.read(info) for info in handle.infolist()}
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read packet archive members: {exc}") from exc


def _manifest_payload(members: Mapping[str, bytes]) -> Mapping[str, Any] | None:
    payload = members.get(MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST)
    if payload is None:
        return None
    try:
        parsed = json.loads(payload.decode(_UTF8))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _entry_count_from_manifest(
    manifest: Mapping[str, Any] | None,
) -> tuple[int, int, tuple[str, ...]]:
    if manifest is None:
        return 0, 0, ()
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return 0, 0, ()
    paths = tuple(
        str(row.get("relative_path", ""))
        for row in raw_artifacts
        if isinstance(row, Mapping)
    )
    return len(paths) + 1, len(paths), paths


def _archive_verification(
    archive_id: str,
    packet_id: str,
    archive_address: str,
    entry_count: int,
    artifact_count: int,
    present_count: int,
    missing_count: int,
    checks: list[ModuleWorkbenchExecutionPacketArchiveCheck],
) -> ModuleWorkbenchExecutionPacketArchiveVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    if len(ordered) > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS:
        raise ValidationError("archive produced too many checks")
    body = {
        "archive_id": archive_id,
        "packet_id": packet_id,
        "archive_address": archive_address,
        "entry_count": entry_count,
        "artifact_count": artifact_count,
        "present_count": present_count,
        "missing_count": missing_count,
        "checks": ordered,
        "accepted": bool(ordered) and all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchExecutionPacketArchiveVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_verification(provisional),
    )


def verify_module_workbench_execution_packet_archive(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveVerification:
    """Verify ZIP structure, manifest, exact member bytes, packet links, and public scope."""

    raw = _read_archive(value)
    archive_address = hash_bytes(raw, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX)
    checks: list[ModuleWorkbenchExecutionPacketArchiveCheck] = []
    archive_id = "unavailable"
    packet_id = "unavailable"
    infos: tuple[zipfile.ZipInfo, ...] = ()
    members: dict[str, bytes] = {}
    try:
        infos = _zip_infos(raw)
        members = _read_members(raw)
        zip_ok = True
        zip_detail = "ZIP members are readable"
    except ValidationError as exc:
        zip_ok = False
        zip_detail = str(exc)
    checks.append(
        _archive_check(
            "zip-readable",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.ZIP,
            zip_ok,
            "readable" if zip_ok else "unreadable",
            "readable",
            zip_detail,
        )
    )
    names = tuple(info.filename for info in infos)
    duplicate_names = tuple(sorted(name for name in set(names) if names.count(name) > 1))
    checks.append(
        _archive_check(
            "unique-members",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.ZIP,
            not duplicate_names,
            duplicate_names,
            (),
            "archive member names are unique",
        )
    )
    unsafe_names = tuple(sorted(name for name in names if not _safe_path(name)))
    checks.append(
        _archive_check(
            "safe-paths",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.PATH,
            not unsafe_names,
            unsafe_names,
            (),
            "archive member paths are relative and traversal-free",
        )
    )
    special_names = tuple(
        sorted(
            info.filename
            for info in infos
            if info.is_dir()
            or (
                info.create_system == 3
                and stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)
            )
        )
    )
    checks.append(
        _archive_check(
            "regular-members",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.ZIP,
            not special_names,
            special_names,
            (),
            "archive contains regular files only",
        )
    )
    manifest = _manifest_payload(members) if zip_ok else None
    checks.append(
        _archive_check(
            "manifest-present",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.MANIFEST,
            manifest is not None,
            "present" if manifest is not None else "missing-or-invalid",
            "present",
            "archive has a readable JSON manifest",
        )
    )
    if manifest is not None:
        archive_id = str(manifest.get("archive_id", "unavailable"))
        packet_id = str(manifest.get("packet_id", "unavailable"))
    manifest_raw = members.get(MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST, b"")
    canonical_manifest = (
        manifest is not None
        and manifest_raw == (canonical_json(manifest) + "\n").encode(_UTF8)
    )
    checks.append(
        _archive_check(
            "manifest-canonical",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.MANIFEST,
            canonical_manifest,
            "canonical" if canonical_manifest else "non-canonical",
            "canonical",
            "manifest bytes are canonical UTF-8 JSON",
        )
    )
    declared_entry_count, artifact_count, declared_paths = _entry_count_from_manifest(manifest)
    expected_names = {MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST, *declared_paths}
    actual_names = set(names)
    missing_names = tuple(sorted(expected_names - actual_names))
    extra_names = tuple(sorted(actual_names - expected_names))
    checks.append(
        _archive_check(
            "declared-members",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.MANIFEST,
            bool(manifest is not None and not missing_names and not extra_names),
            {"missing": missing_names, "extra": extra_names},
            {"missing": (), "extra": ()},
            "archive members exactly match manifest declarations",
        )
    )
    byte_failures: list[str] = []
    line_failures: list[str] = []
    descriptor_failures: list[str] = []
    if manifest is not None and isinstance(manifest.get("artifacts"), list):
        for row in manifest["artifacts"]:
            if not isinstance(row, Mapping):
                descriptor_failures.append("invalid-row")
                continue
            relative_path = str(row.get("relative_path", ""))
            payload = members.get(relative_path)
            if payload is None:
                continue
            expected_bytes = row.get("byte_count")
            expected_lines = row.get("line_count")
            expected_address = str(row.get("content_address", ""))
            if expected_bytes != len(payload) or hash_bytes(
                payload,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_PREFIX,
            ) != expected_address:
                byte_failures.append(relative_path)
            if expected_lines != _line_count(payload):
                line_failures.append(relative_path)
            if not str(row.get("artifact_id", "")) or not str(row.get("kind", "")):
                descriptor_failures.append(relative_path)
    checks.append(
        _archive_check(
            "artifact-bytes",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.BYTES,
            not byte_failures,
            tuple(sorted(byte_failures)),
            (),
            "artifact byte counts and packet addresses match exact archive bytes",
        )
    )
    checks.append(
        _archive_check(
            "artifact-lines",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.BYTES,
            not line_failures,
            tuple(sorted(line_failures)),
            (),
            "artifact line counts match UTF-8 decoded members",
        )
    )
    checks.append(
        _archive_check(
            "artifact-descriptors",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.PACKET,
            not descriptor_failures,
            tuple(sorted(descriptor_failures)),
            (),
            "manifest artifact descriptors are complete",
        )
    )
    public_ok = manifest is not None and not _has_forbidden_key(manifest)
    if public_ok:
        for relative_path, payload in members.items():
            if relative_path.endswith(".json"):
                try:
                    public_ok = public_ok and not _has_forbidden_key(
                        json.loads(payload.decode(_UTF8))
                    )
                except (UnicodeDecodeError, json.JSONDecodeError):
                    public_ok = False
    checks.append(
        _archive_check(
            "public-boundary",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.PUBLIC,
            public_ok,
            "clean" if public_ok else "forbidden-or-invalid",
            "clean",
            "manifest and JSON members contain only public aggregate fields",
        )
    )
    packet_ok = False
    if manifest is not None:
        try:
            packet = _hydrate_packet(manifest, members)
            packet_ok = packet.accepted
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            packet = None
            packet_error = str(exc)
        else:
            packet_error = "accepted"
    else:
        packet = None
        packet_error = "manifest unavailable"
    checks.append(
        _archive_check(
            "packet-hydration",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.PACKET,
            packet_ok,
            packet_error,
            "accepted packet",
            "archive members restore the addressed typed packet",
        )
    )
    if packet is not None:
        address_ok = str(manifest.get("content_address")) == packet.content_address
        packet_state_ok = str(manifest.get("state")) == packet.state.value
    else:
        address_ok = False
        packet_state_ok = False
    checks.append(
        _archive_check(
            "packet-address",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.PACKET,
            address_ok,
            packet.content_address if packet is not None else "unavailable",
            str(manifest.get("content_address")) if manifest is not None else "addressed",
            "packet manifest content address is conserved",
        )
    )
    checks.append(
        _archive_check(
            "packet-state",
            ModuleWorkbenchExecutionPacketArchiveCheckPlane.PACKET,
            packet_state_ok,
            packet.state.value if packet is not None else "unavailable",
            str(manifest.get("state")) if manifest is not None else "accepted",
            "packet publication state is conserved",
        )
    )
    present_count = len(expected_names & actual_names)
    entry_count = max(declared_entry_count, len(actual_names))
    return _archive_verification(
        archive_id,
        packet_id,
        archive_address,
        entry_count,
        artifact_count,
        min(present_count, entry_count),
        max(entry_count - present_count, 0),
        checks,
    )


def verify_module_workbench_execution_packet_archive_value(
    value: ModuleWorkbenchExecutionPacketArchive,
) -> ModuleWorkbenchExecutionPacketArchive:
    """Verify a typed archive descriptor and exact binary address."""

    if not isinstance(value, ModuleWorkbenchExecutionPacketArchive):
        raise ValidationError("typed packet archive verification requires an archive")
    if (
        hash_bytes(value.archive_bytes, prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_PREFIX)
        != value.archive_address
    ):
        raise ValidationError("packet archive binary address mismatch")
    if address_module_workbench_execution_packet_archive(value) != value.content_address:
        raise ValidationError("packet archive descriptor address mismatch")
    return value


def _hydrate_packet(
    manifest: Mapping[str, Any],
    members: Mapping[str, bytes],
) -> ModuleWorkbenchExecutionPacket:
    raw_artifacts = manifest.get("artifacts")
    raw_checks = manifest.get("checks")
    if not isinstance(raw_artifacts, list) or not isinstance(raw_checks, list):
        raise ValidationError("packet archive manifest collections are invalid")
    artifacts: list[ModuleWorkbenchExecutionPacketArtifact] = []
    for row in raw_artifacts:
        if not isinstance(row, Mapping):
            raise ValidationError("packet archive artifact row is invalid")
        relative_path = str(row.get("relative_path", ""))
        payload = members.get(relative_path)
        if payload is None:
            raise ValidationError(f"packet archive artifact is missing: {relative_path}")
        artifacts.append(
            ModuleWorkbenchExecutionPacketArtifact(
                artifact_id=str(row.get("artifact_id", "")),
                relative_path=relative_path,
                media_type=str(row.get("media_type", "")),
                kind=ModuleWorkbenchExecutionPacketArtifactKind(str(row.get("kind"))),
                byte_count=int(row.get("byte_count")),
                line_count=int(row.get("line_count")),
                content_address=str(row.get("content_address", "")),
                payload=payload.decode(_UTF8),
            )
        )
    checks: list[ModuleWorkbenchExecutionPacketCheck] = []
    for row in raw_checks:
        if not isinstance(row, Mapping):
            raise ValidationError("packet archive check row is invalid")
        checks.append(
            ModuleWorkbenchExecutionPacketCheck(
                check_id=str(row.get("check_id", "")),
                plane=ModuleWorkbenchExecutionPacketCheckPlane(str(row.get("plane"))),
                passed=bool(row.get("passed")),
                observed=row.get("observed"),
                required=row.get("required"),
                detail=str(row.get("detail", "")),
                content_address=str(row.get("content_address", "")),
            )
        )
    return ModuleWorkbenchExecutionPacket(
        packet_id=str(manifest.get("packet_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        report_address=str(manifest.get("report_address", "")),
        portfolio_address=str(manifest.get("portfolio_address", "")),
        initial_ledger_address=str(manifest.get("initial_ledger_address", "")),
        ledger_address=str(manifest.get("ledger_address", "")),
        review_address=str(manifest.get("review_address", "")),
        audit_address=str(manifest.get("audit_address", "")),
        policy_address=str(manifest.get("policy_address", "")),
        gate_address=str(manifest.get("gate_address", "")),
        runtime_address=str(manifest.get("runtime_address", "")),
        state=ModuleWorkbenchExecutionPacketState(str(manifest.get("state"))),
        accepted=bool(manifest.get("accepted")),
        artifacts=tuple(artifacts),
        checks=tuple(checks),
        content_address=str(manifest.get("content_address", "")),
    )


def load_module_workbench_execution_packet_archive(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchExecutionPacket:
    """Load an accepted archive directly into a typed packet without source access."""

    verification = verify_module_workbench_execution_packet_archive(value)
    if not verification.accepted:
        raise ValidationError("cannot load a blocked packet archive")
    packet = _hydrate_packet(
        _manifest_payload(_read_members(_read_archive(value))) or {},
        _read_members(_read_archive(value)),
    )
    if not packet.accepted:
        raise ValidationError("packet archive restored a blocked packet")
    return packet


def unpack_module_workbench_execution_packet_archive(
    value: bytes | bytearray | str | Path,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Verify an archive and atomically materialize its members as a packet directory."""

    verification = verify_module_workbench_execution_packet_archive(value)
    if not verification.accepted:
        raise ValidationError("cannot unpack a blocked packet archive")
    root = Path(destination)
    if root.exists() and not root.is_dir():
        raise ValidationError("packet unpack destination is not a directory")
    if root.exists() and not allow_existing:
        raise ValidationError("packet unpack destination already exists")
    parent = root.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.", suffix=".tmp", dir=str(parent)))
    try:
        members = _read_members(_read_archive(value))
        for relative_path, payload in sorted(members.items()):
            if not _safe_path(relative_path):
                raise ValidationError(f"unsafe packet archive member: {relative_path}")
            path = staging.joinpath(*relative_path.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        if root.exists():
            shutil.rmtree(root)
        os.replace(staging, root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return root


def query_module_workbench_execution_packet_archive(
    value: ModuleWorkbenchExecutionPacketArchive | bytes | bytearray | str | Path,
    *,
    resource: str = "entries",
    entry_id: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return bounded archive entries or one summary row."""

    archive = (
        value
        if isinstance(value, ModuleWorkbenchExecutionPacketArchive)
        else build_module_workbench_execution_packet_archive(
            load_module_workbench_execution_packet_archive(value)
        )
    )
    verify_module_workbench_execution_packet_archive_value(archive)
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT:
        raise ValidationError("packet archive query paging is invalid")
    normalized = resource.casefold().strip()
    if normalized == "entries":
        rows = [item.to_dict() for item in archive.entries]
        if entry_id:
            rows = [row for row in rows if row.get("entry_id") == entry_id]
        if kind:
            rows = [row for row in rows if row.get("kind") == kind]
        index_used = "entry_id"
    elif normalized == "summary":
        rows = [archive.to_dict(include_entries=False)]
        index_used = "archive_id"
    else:
        raise ValidationError("packet archive resource must be entries or summary")
    if text:
        needle = text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    total = len(rows)
    body = {
        "archive_id": archive.archive_id,
        "archive_address": archive.archive_address,
        "resource": normalized,
        "query": {"entry_id": entry_id, "kind": kind, "text": text},
        "total": total,
        "offset": offset,
        "limit": limit,
        "index_used": index_used,
        "items": rows[offset : offset + limit],
        "accepted": archive.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-execution-packet-archive-query",
        )
    }


def module_workbench_execution_packet_archive_json(
    value: ModuleWorkbenchExecutionPacketArchive,
) -> str:
    """Return canonical archive descriptor JSON without binary bytes."""

    verify_module_workbench_execution_packet_archive_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_csv(
    value: ModuleWorkbenchExecutionPacketArchive,
) -> str:
    """Return one stable CSV row per archive entry."""

    verify_module_workbench_execution_packet_archive_value(value)
    fields = (
        "entry_id",
        "relative_path",
        "kind",
        "media_type",
        "ordinal",
        "byte_count",
        "line_count",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_markdown(
    value: ModuleWorkbenchExecutionPacketArchive,
) -> str:
    """Render the archive handoff and entry table for offline review."""

    verify_module_workbench_execution_packet_archive_value(value)
    lines = [
        "# Module Workbench Execution Packet Archive",
        "",
        f"- Archive: `{value.archive_id}`",
        f"- Packet: `{value.packet_id}`",
        f"- State: `{value.state.value}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Entries: `{value.entry_count}` (`{value.artifact_count}` artifacts)",
        f"- Payload bytes: `{value.payload_byte_count:,}`",
        f"- Archive bytes: `{value.archive_byte_count:,}`",
        f"- Address: `{value.archive_address}`",
        "",
        "| Ordinal | Entry | Kind | Bytes | Address |",
        "|---:|---|---|---:|---|",
    ]
    for entry in value.entries:
        lines.append(
            f"| {entry.ordinal} | `{entry.relative_path}` | `{entry.kind.value}` | "
            f"{entry.byte_count:,} | `{entry.content_address}` |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_schema() -> dict[str, Any]:
    """Describe archive format, entry limits, and safe extraction guarantees."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_BOUNDARY,
        "format": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT,
        "manifest": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST,
        "resources": ["entries", "summary"],
        "entry_kinds": [item.value for item in ModuleWorkbenchExecutionPacketArchiveEntryKind],
        "check_planes": [item.value for item in ModuleWorkbenchExecutionPacketArchiveCheckPlane],
        "states": [item.value for item in ModuleWorkbenchExecutionPacketArchiveState],
        "limits": {
            "max_entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_ENTRIES,
            "max_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_CHECKS,
            "max_query_limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MAX_LIMIT,
            "default_chunk_size": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
        },
        "inputs": ["typed_packet", "packet_directory", "archive_bytes", "archive_path"],
        "outputs": ["archive_bytes", "verification", "typed_packet", "packet_directory"],
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_capabilities() -> dict[str, Any]:
    """Declare deterministic archive and extraction operations."""

    operations = (
        "build_archive",
        "address_archive_bytes",
        "write_archive_atomically",
        "verify_zip_structure",
        "verify_manifest",
        "verify_safe_paths",
        "verify_regular_members",
        "verify_exact_member_bytes",
        "verify_packet_hydration",
        "verify_public_boundary",
        "load_packet_from_archive",
        "unpack_archive_atomically",
        "query_entries",
        "query_summary",
        "export_descriptor_json",
        "export_entry_csv",
        "export_markdown",
        "enforce_entry_limit",
        "retain_binary_address",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "offline": True,
        "atomic_writes": True,
        "safe_extraction": True,
        "identity_free": True,
    }


__all__ = [
    "build_module_workbench_execution_packet_archive",
    "load_module_workbench_execution_packet_archive",
    "module_workbench_execution_packet_archive_bytes",
    "module_workbench_execution_packet_archive_capabilities",
    "module_workbench_execution_packet_archive_csv",
    "module_workbench_execution_packet_archive_json",
    "module_workbench_execution_packet_archive_schema",
    "query_module_workbench_execution_packet_archive",
    "render_module_workbench_execution_packet_archive_markdown",
    "unpack_module_workbench_execution_packet_archive",
    "verify_module_workbench_execution_packet_archive",
    "verify_module_workbench_execution_packet_archive_value",
    "write_module_workbench_execution_packet_archive",
]

"""Build, verify, and query a source-free downloaded-data review packet."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from . import downloaded_data_catalog as _catalog
from . import downloaded_data_ingestion as _ingestion
from . import downloaded_data_ingestion_runtime as _ingestion_runtime
from . import downloaded_data_profile_contract_runtime as _contract_runtime
from . import downloaded_data_profile_contract_runtime_audit as _runtime_audit
from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .downloaded_data_review_packet_contracts import (
    BOUNDARY,
    FILE_NAMES,
    MANIFEST_PREFIX,
    MAX_PACKET_BYTES,
    MEDIA_TYPES,
    MEMBER_PREFIX,
    PACKET_PREFIX,
    PAYLOAD_NAMES,
    VERSION,
    ZIP_FORMAT,
    DownloadedDataReviewPacket,
    DownloadedDataReviewPacketManifest,
    DownloadedDataReviewPacketMember,
    address_manifest,
    address_member,
    address_member_bytes,
    capabilities,
    manifest_schema,
    packet_schema,
)
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"
_FIXED_ATTRIBUTES = 0o100644 << 16
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 256


def _safe_member(name: str) -> bool:
    return isinstance(name, str) and bool(name) and not name.startswith("/") and "\\" not in name and ":" not in name and "\x00" not in name and all(part not in {"", ".", ".."} for part in PurePosixPath(name).parts)


def _zip_member(name: str) -> zipfile.ZipInfo:
    if name not in FILE_NAMES:
        raise ValidationError("review packet member is outside the fixed file set")
    info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.external_attr = _FIXED_ATTRIBUTES
    info.extra = b""
    info.comment = b""
    return info


def _read_packet(value: bytes | bytearray | str | Path | DownloadedDataReviewPacket) -> bytes:
    if isinstance(value, DownloadedDataReviewPacket):
        raw = value.packet_bytes
    elif isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = read_bytes(value, field="downloaded data review packet", max_bytes=MAX_PACKET_BYTES)
    if len(raw) > MAX_PACKET_BYTES:
        raise ValidationError("downloaded data review packet exceeds its byte bound")
    return raw


def _parts(raw: bytes) -> tuple[tuple[zipfile.ZipInfo, bytes], ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r", allowZip64=False) as archive:
            return tuple((info, archive.read(info)) for info in archive.infolist())
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read downloaded data review packet ZIP: {exc}") from exc


def _payload_bytes(catalog: Any, runtime: Any, audit: Any) -> tuple[bytes, bytes, bytes, bytes]:
    catalog_value = _catalog.catalog_from_mapping(catalog.to_dict())
    runtime_value = _contract_runtime.runtime_from_mapping(runtime.to_dict())
    audit_value = _runtime_audit.audit_from_mapping(audit.to_dict())
    review = _review(catalog_value, runtime_value, audit_value)
    return (
        (canonical_json(catalog_value.to_dict()) + "\n").encode(_UTF8),
        (canonical_json(runtime_value.to_dict()) + "\n").encode(_UTF8),
        (canonical_json(audit_value.to_dict()) + "\n").encode(_UTF8),
        review.encode(_UTF8),
    )


def _member(path: str, payload: bytes) -> DownloadedDataReviewPacketMember:
    body = {
        "relative_path": path,
        "media_type": MEDIA_TYPES[path],
        "byte_count": len(payload),
        "byte_address": address_member_bytes(payload),
    }
    provisional = DownloadedDataReviewPacketMember(**body, content_address=MEMBER_PREFIX + ":pending")
    return DownloadedDataReviewPacketMember(**body, content_address=address_member(provisional))


def _review(catalog: Any, runtime: Any, audit: Any) -> str:
    return "\n".join(
        (
            "# Downloaded Data Review Packet",
            "",
            f"- Source archive: `{catalog.source_name}`",
            f"- Structured members: **{catalog.member_count}**",
            f"- Structured bytes: **{catalog.total_data_bytes}**",
            f"- JSON / delimited / YAML members: **{catalog.json_count} / {catalog.delimited_count} / {catalog.yaml_count}**",
            f"- Records profiled: **{runtime.record_count}**",
            f"- Members profiled: **{runtime.member_count}**",
            f"- Fields inferred: **{runtime.field_count}**",
            f"- Contract state: **{runtime.state}**",
            f"- Contract accepted: **{str(runtime.accepted).lower()}**",
            f"- Runtime audit: **{audit.passed_count}/{audit.check_count}**",
            "- Review packet is value-free after construction: **true**",
            "",
            "| component | address |",
            "| --- | --- |",
            f"| catalog | `{catalog.content_address}` |",
            f"| contract runtime | `{runtime.content_address}` |",
            f"| runtime audit | `{audit.content_address}` |",
            "",
            "The packet contains bounded structural metadata and contract evidence; it does not transport the source archive or record values.",
            "",
        )
    )


def _zip_bytes(payloads: tuple[tuple[str, bytes], ...]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, payload in payloads:
            archive.writestr(_zip_member(name), payload)
    return output.getvalue()


def build_packet(catalog: Any, runtime: Any, audit: Any, *, packet_id: str = PACKET_PREFIX) -> DownloadedDataReviewPacket:
    if not isinstance(catalog, _catalog.DownloadedDataCatalog) or not isinstance(runtime, _contract_runtime.DownloadedDataProfileContractRuntime) or not isinstance(audit, _runtime_audit.DownloadedDataProfileContractRuntimeAudit):
        raise ValidationError("downloaded data review packet requires typed catalog, contract runtime, and runtime audit")
    if not audit.accepted or not runtime.accepted:
        raise ValidationError("downloaded data review packet requires accepted contract evidence")
    payloads = _payload_bytes(catalog, runtime, audit)
    members = tuple(_member(path, payload) for path, payload in zip(PAYLOAD_NAMES, payloads, strict=True))
    manifest_body = {
        "packet_id": packet_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "catalog_address": catalog.content_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": audit.content_address,
        "members": members,
        "packet_format": ZIP_FORMAT,
    }
    provisional = DownloadedDataReviewPacketManifest(**manifest_body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataReviewPacketManifest(**manifest_body, content_address=address_manifest(provisional))
    manifest_bytes = (canonical_json(manifest.to_dict()) + "\n").encode(_UTF8)
    raw = _zip_bytes(((FILE_NAMES[0], manifest_bytes), *tuple(zip(PAYLOAD_NAMES, payloads, strict=True))))
    if len(raw) > MAX_PACKET_BYTES:
        raise ValidationError("downloaded data review packet exceeds its byte bound")
    packet = DownloadedDataReviewPacket(manifest=manifest, packet_bytes=raw, packet_address=hash_bytes(raw, prefix=PACKET_PREFIX))
    verify_packet(packet)
    return packet


def _selected_member_names(catalog: _catalog.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_from_download(source: str | Path | bytes, *, packet_id: str = PACKET_PREFIX) -> DownloadedDataReviewPacket:
    catalog = _catalog.build_catalog(source, catalog_id=packet_id + "-catalog")
    selected = _selected_member_names(catalog)
    ingestion = _ingestion_runtime.run_runtime(source, runtime_id=packet_id + "-ingestion", member_names=selected, resources=("summary",), record_limit=_ingestion.MAX_RECORDS, limit=1)
    runtime = _contract_runtime.run_runtime(ingestion.batch, runtime_id=packet_id + "-contract-runtime", profile_id=packet_id + "-contract-profile", resources=("summary", "types", "members", "fields", "issues"), limit=10_000)
    audit = _runtime_audit.audit_runtime(runtime)
    return build_packet(catalog, runtime, audit, packet_id=packet_id)


def _manifest_and_bodies(raw: bytes) -> tuple[DownloadedDataReviewPacketManifest, dict[str, bytes]]:
    parts = _parts(raw)
    names = tuple(info.filename for info, _payload in parts)
    if names != FILE_NAMES or any(not _safe_member(name) for name in names):
        raise ValidationError("review packet ZIP members are not the exact safe file set")
    if any(info.date_time != _ZIP_EPOCH or info.compress_type != zipfile.ZIP_STORED or info.external_attr != _FIXED_ATTRIBUTES for info, _payload in parts):
        raise ValidationError("review packet ZIP metadata is not deterministic")
    bodies = {info.filename: payload for info, payload in parts}
    parsed = _strict_json_loads(bodies[FILE_NAMES[0]].decode(_UTF8))
    if not isinstance(parsed, Mapping) or bodies[FILE_NAMES[0]] != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("review packet manifest is not canonical")
    members = tuple(DownloadedDataReviewPacketMember(**item) for item in parsed.get("members", ()))
    manifest = DownloadedDataReviewPacketManifest(packet_id=parsed.get("packet_id"), version=parsed.get("version"), boundary=parsed.get("boundary"), catalog_address=parsed.get("catalog_address"), runtime_address=parsed.get("runtime_address"), runtime_audit_address=parsed.get("runtime_audit_address"), members=members, packet_format=parsed.get("packet_format"), content_address=parsed.get("content_address"))
    if address_manifest(manifest) != manifest.content_address:
        raise ValidationError("review packet manifest address does not replay")
    for descriptor in members:
        payload = bodies[descriptor.relative_path]
        if descriptor.byte_count != len(payload) or descriptor.byte_address != address_member_bytes(payload) or descriptor.content_address != address_member(descriptor):
            raise ValidationError(f"review packet member does not replay: {descriptor.relative_path}")
    return manifest, bodies


def verify_packet(value: bytes | bytearray | str | Path | DownloadedDataReviewPacket) -> DownloadedDataReviewPacket:
    raw = _read_packet(value)
    manifest, bodies = _manifest_and_bodies(raw)
    catalog = _catalog.catalog_from_mapping(_strict_json_loads(bodies["catalog.json"].decode(_UTF8)))
    runtime = _contract_runtime.runtime_from_mapping(_strict_json_loads(bodies["contract-runtime.json"].decode(_UTF8)))
    audit = _runtime_audit.audit_from_mapping(_strict_json_loads(bodies["runtime-audit.json"].decode(_UTF8)))
    for path, value_bytes in (("catalog.json", bodies["catalog.json"]), ("contract-runtime.json", bodies["contract-runtime.json"]), ("runtime-audit.json", bodies["runtime-audit.json"])):
        if value_bytes != (canonical_json(_strict_json_loads(value_bytes.decode(_UTF8))) + "\n").encode(_UTF8):
            raise ValidationError(f"review packet payload is not canonical: {path}")
    if manifest.catalog_address != catalog.content_address or manifest.runtime_address != runtime.content_address or manifest.runtime_audit_address != audit.content_address:
        raise ValidationError("review packet component lineage does not replay")
    if not audit.accepted or not runtime.accepted:
        raise ValidationError("review packet component evidence is not accepted")
    if bodies["review.md"].decode(_UTF8) != _review(catalog, runtime, audit):
        raise ValidationError("review packet Markdown does not replay")
    packet = DownloadedDataReviewPacket(manifest=manifest, packet_bytes=raw, packet_address=hash_bytes(raw, prefix=PACKET_PREFIX))
    if isinstance(value, DownloadedDataReviewPacket) and value.to_dict() != packet.to_dict():
        raise ValidationError("typed review packet does not replay its bytes")
    return packet


def load_packet(value: bytes | bytearray | str | Path | DownloadedDataReviewPacket) -> tuple[Any, Any, Any, str]:
    packet = verify_packet(value)
    _, bodies = _manifest_and_bodies(packet.packet_bytes)
    return (
        _catalog.catalog_from_mapping(_strict_json_loads(bodies["catalog.json"].decode(_UTF8))),
        _contract_runtime.runtime_from_mapping(_strict_json_loads(bodies["contract-runtime.json"].decode(_UTF8))),
        _runtime_audit.audit_from_mapping(_strict_json_loads(bodies["runtime-audit.json"].decode(_UTF8))),
        bodies["review.md"].decode(_UTF8),
    )


def packet_json(value: Any) -> str:
    return canonical_json(verify_packet(value).to_dict()) + "\n"


def write_packet(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacket:
    packet = verify_packet(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("downloaded data review packet destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("downloaded data review packet destination is not a file")
    _validate_parent(path.parent, "downloaded data review packet destination")
    atomic_write_bytes(path, packet.packet_bytes, field="downloaded data review packet destination")
    return packet


def query_packet(value: Any, *, resource: str = "summary", offset: int = 0, limit: int = _DEFAULT_LIMIT) -> dict[str, Any]:
    if resource not in {"members", "summary", "catalog", "runtime", "audit", "review"} or offset < 0 or limit < 1 or limit > _MAX_LIMIT:
        raise ValidationError("downloaded data review packet query is invalid")
    packet = verify_packet(value)
    catalog, runtime, audit, review = load_packet(packet)
    if resource == "members":
        rows = [item.to_dict() for item in packet.manifest.members]
        result: Any = {"resource": resource, "total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}
    elif resource == "summary":
        result = {"resource": resource, "value": packet.to_dict()}
    elif resource == "catalog":
        result = {"resource": resource, "value": catalog.to_dict()}
    elif resource == "runtime":
        result = {"resource": resource, "value": runtime.to_dict()}
    elif resource == "audit":
        result = {"resource": resource, "value": audit.to_dict()}
    else:
        result = {"resource": resource, "value": review}
    return result | {"packet_address": packet.packet_address, "content_address": content_hash(result, prefix=PACKET_PREFIX + "-query")}


def packet_csv(value: Any, *, offset: int = 0, limit: int = _DEFAULT_LIMIT) -> str:
    result = query_packet(value, resource="members", offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    fields = ("relative_path", "media_type", "byte_count", "byte_address", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return stream.getvalue()


def render_packet_markdown(value: Any) -> str:
    catalog, runtime, audit, review = load_packet(value)
    return _review(catalog, runtime, audit) + "\n" + "## Transport\n\n" + f"- Packet: `{verify_packet(value).packet_address}`\n- Members: **{len(FILE_NAMES)}**\n"


__all__ = [
    "build_from_download", "build_packet", "capabilities", "load_packet", "manifest_schema", "packet_csv", "packet_json", "packet_schema", "query_packet", "render_packet_markdown", "verify_packet", "write_packet",
]

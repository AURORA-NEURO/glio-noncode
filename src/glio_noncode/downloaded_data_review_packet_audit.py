"""Independently audit downloaded-data review packet transport and lineage."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .downloaded_data_review_packet import (
    _UTF8,
    _manifest_and_bodies,
    _parts,
    _read_packet,
    _review,
    load_packet,
    verify_packet,
)
from .downloaded_data_review_packet_contracts import (
    BOUNDARY,
    FILE_NAMES,
    MEDIA_TYPES,
    MEMBER_PREFIX,
    PACKET_PREFIX,
    PAYLOAD_NAMES,
    VERSION,
    address_manifest,
    address_member,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

AUDIT_VERSION = VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY + "_audit"
AUDIT_PREFIX = PACKET_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address",
    "audit-canonical-bytes",
    "audit-count-conservation",
    "audit-fixed-metadata",
    "audit-lineage",
    "audit-manifest-address",
    "audit-member-addresses",
    "audit-member-descriptors",
    "audit-member-order",
    "audit-public-boundary",
    "audit-review-replay",
    "audit-source-free",
    "audit-transport-address",
    "audit-typed-replay",
)
_MAX_CHECKS = len(CHECK_IDS)
_MAX_JSON_BYTES = 16 * 1024 * 1024


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


class DownloadedDataReviewPacketAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "review packet audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("review packet audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("review packet audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "review packet audit check detail", 2048)
        self.content_address = _address(content_address, "review packet audit check address", AUDIT_CHECK_PREFIX) if not content_address.endswith(":pending") else content_address
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("review packet audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}


def address_check(value: DownloadedDataReviewPacketAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_CHECK_PREFIX)


class DownloadedDataReviewPacketAudit:
    FIELDS = ("packet_id", "packet_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, packet_id: str, packet_address: str, checks: tuple[DownloadedDataReviewPacketAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.packet_id = _label(packet_id, "review packet audit packet ID")
        self.packet_address = _address(packet_address, "review packet audit packet address", PACKET_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = _address(content_address, "review packet audit address", AUDIT_PREFIX) if not content_address.endswith(":pending") else content_address
        if self.check_count != len(self.checks) or self.check_count != _MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("review packet audit aggregates do not replay")
        if not content_address.endswith(":pending") and address_audit(self) != content_address:
            raise ValidationError("review packet audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"packet_id": self.packet_id, "packet_address": self.packet_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}


def address_audit(value: DownloadedDataReviewPacketAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    provisional = DownloadedDataReviewPacketAuditCheck(**body, content_address=AUDIT_CHECK_PREFIX + ":pending")
    return DownloadedDataReviewPacketAuditCheck(**body, content_address=address_check(provisional))


def _receipt(packet_id: str, packet_address: str, checks: tuple[DownloadedDataReviewPacketAuditCheck, ...]) -> DownloadedDataReviewPacketAudit:
    body = {"packet_id": packet_id or "unavailable", "packet_address": packet_address or PACKET_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks)}
    provisional = DownloadedDataReviewPacketAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataReviewPacketAudit(**body, content_address=address_audit(provisional))


def audit_packet(value: Any) -> DownloadedDataReviewPacketAudit:
    try:
        raw = _read_packet(value)
        packet = verify_packet(raw)
        manifest, bodies = _manifest_and_bodies(raw)
        parts = _parts(raw)
        catalog, runtime, runtime_audit, review = load_packet(packet)
        manifest_bytes = bodies["manifest.json"]
        canonical_payloads = all(bodies[name] == (canonical_json(_strict_json_loads(bodies[name].decode(_UTF8))) + "\n").encode(_UTF8) for name in ("catalog.json", "contract-runtime.json", "runtime-audit.json"))
        descriptor_replay = all(item.byte_count == len(bodies[item.relative_path]) and item.byte_address == hash_bytes(bodies[item.relative_path], prefix=MEMBER_PREFIX + "-bytes") and item.content_address == address_member(item) for item in manifest.members)
        checks = (
            _check("audit-address", True, "deferred", "replayable", "audit addresses are recomputable"),
            _check("audit-canonical-bytes", canonical_payloads and manifest_bytes == (canonical_json(_strict_json_loads(manifest_bytes.decode(_UTF8))) + "\n").encode(_UTF8), canonical_payloads, True, "all JSON members are canonical bytes"),
            _check("audit-count-conservation", len(manifest.members) == len(PAYLOAD_NAMES) and len(bodies) == len(FILE_NAMES), {"members": len(manifest.members), "files": len(bodies)}, {"members": len(PAYLOAD_NAMES), "files": len(FILE_NAMES)}, "manifest and ZIP counts conserve the fixed packet contract"),
            _check("audit-fixed-metadata", all(info.date_time == (1980, 1, 1, 0, 0, 0) and info.compress_type == zipfile.ZIP_STORED and info.external_attr == 0o100644 << 16 for info, _payload in parts), "fixed", "fixed", "ZIP metadata is deterministic"),
            _check("audit-lineage", manifest.catalog_address == catalog.content_address and manifest.runtime_address == runtime.content_address and manifest.runtime_audit_address == runtime_audit.content_address, "conserved", "conserved", "manifest component addresses agree with typed payloads"),
            _check("audit-manifest-address", address_manifest(manifest) == manifest.content_address, manifest.content_address, "replayable", "manifest address is independently recomputable"),
            _check("audit-member-addresses", descriptor_replay, "replayed" if descriptor_replay else "drift", "replayed", "member byte and content addresses replay"),
            _check("audit-member-descriptors", tuple(item.relative_path for item in manifest.members) == PAYLOAD_NAMES and tuple(item.media_type for item in manifest.members) == tuple(MEDIA_TYPES[name] for name in PAYLOAD_NAMES), tuple(item.relative_path for item in manifest.members), PAYLOAD_NAMES, "member descriptors retain the exact payload contract"),
            _check("audit-member-order", tuple(info.filename for info, _payload in parts) == FILE_NAMES, tuple(info.filename for info, _payload in parts), FILE_NAMES, "ZIP member order is canonical"),
            _check("audit-public-boundary", not _has_forbidden_key({"catalog": catalog.to_dict(), "runtime": runtime.to_dict(), "audit": runtime_audit.to_dict()}), "clean", "clean", "review packet evidence contains no forbidden public keys"),
            _check("audit-review-replay", review == _review(catalog, runtime, runtime_audit), "replayed" if review == _review(catalog, runtime, runtime_audit) else "drift", "replayed", "review Markdown regenerates exactly"),
            _check("audit-source-free", "source" not in packet.to_dict() and "packet_bytes" not in packet.to_dict(), "aggregate-only", "aggregate-only", "packet projection excludes source bytes and paths"),
            _check("audit-transport-address", hash_bytes(raw, prefix=PACKET_PREFIX) == packet.packet_address, packet.packet_address, "replayable", "packet byte address is deterministic"),
            _check("audit-typed-replay", packet.to_dict() == verify_packet(packet).to_dict(), True, True, "typed packet reload reproduces the same aggregate projection"),
        )
        return _receipt(manifest.packet_id, packet.packet_address, checks)
    except (KeyError, TypeError, UnicodeDecodeError, ValueError, ValidationError, zipfile.BadZipFile) as exc:
        return _receipt("unavailable", PACKET_PREFIX + ":" + "0" * 64, tuple(_check(item, item == "audit-address" and False, str(exc), "readable and canonical", "review packet audit input could not be loaded") for item in CHECK_IDS))


def verify_audit(value: Any) -> DownloadedDataReviewPacketAudit:
    if not isinstance(value, DownloadedDataReviewPacketAudit):
        raise ValidationError("downloaded data review packet audit verification requires a typed audit")
    for item in value.checks:
        if address_check(item) != item.content_address:
            raise ValidationError(f"review packet audit check address mismatch: {item.check_id}")
    if address_audit(value) != value.content_address:
        raise ValidationError("review packet audit address mismatch")
    return value


def _from_mapping(value: Mapping[str, Any]) -> DownloadedDataReviewPacketAudit:
    checks = tuple(DownloadedDataReviewPacketAuditCheck(item["check_id"], item["passed"], item.get("observed"), item.get("required"), item["detail"], item["content_address"]) for item in value["checks"])
    return verify_audit(DownloadedDataReviewPacketAudit(value["packet_id"], value["packet_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"]))


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketAudit:
    if isinstance(value, Mapping):
        return _from_mapping(value)
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="downloaded data review packet audit", max_bytes=_MAX_JSON_BYTES)
    parsed = _strict_json_loads(raw.decode(_UTF8))
    if not isinstance(parsed, Mapping) or raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("downloaded data review packet audit must be canonical JSON")
    return _from_mapping(parsed)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("downloaded data review packet audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("downloaded data review packet audit destination is not a file")
    _validate_parent(path.parent, "downloaded data review packet audit destination")
    atomic_write_bytes(path, audit_json(audit).encode(_UTF8), field="downloaded data review packet audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > 256:
        raise ValidationError("downloaded data review packet audit paging is invalid")
    audit = value if isinstance(value, DownloadedDataReviewPacketAudit) else load_audit(value)
    verify_audit(audit)
    rows = list(audit.checks)
    if passed is not None:
        rows = [item for item in rows if item.passed is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item.to_dict()).casefold()]
    body = {"packet_id": audit.packet_id, "packet_address": audit.packet_address, "audit_address": audit.content_address, "passed": passed, "text": text, "total": len(rows), "offset": offset, "limit": limit, "items": [item.to_dict() for item in rows[offset:offset + limit]], "accepted": audit.accepted}
    return body | {"content_address": content_hash(body, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(result["items"])
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = value if isinstance(value, DownloadedDataReviewPacketAudit) else load_audit(value)
    verify_audit(audit)
    lines = ["# Downloaded Data Review Packet Audit", "", f"- Packet: `{audit.packet_id}`", f"- Packet address: `{audit.packet_address}`", f"- Passed / failed: **{audit.passed_count} / {audit.failed_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet audit", "type": "object", "additionalProperties": False, "required": ["packet_id", "packet_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address"], "properties": {"packet_id": {"type": "string"}, "packet_address": {"type": "string"}, "checks": {"type": "array", "minItems": _MAX_CHECKS, "maxItems": _MAX_CHECKS}, "check_count": {"const": _MAX_CHECKS}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def check_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data review packet audit check",
        "type": "object",
        "additionalProperties": False,
        "required": ["check_id", "passed", "observed", "required", "detail", "content_address"],
        "properties": {
            "check_id": {"type": "string", "enum": list(CHECK_IDS)},
            "passed": {"type": "boolean"},
            "observed": {},
            "required": {},
            "detail": {"type": "string"},
            "content_address": {"type": "string"},
        },
    }


def capabilities_audit() -> dict[str, Any]:
    operations = ("audit_transport", "audit_manifest", "audit_members", "audit_lineage", "audit_payloads", "audit_review", "audit_public_boundary", "load_source_free", "query_checks", "export_json", "export_csv", "render_markdown")
    return {"public": True, "independent": True, "source_free": True, "version": AUDIT_VERSION, "check_count": _MAX_CHECKS, "operation_count": len(operations), "operations": list(operations), "deterministic": True}


__all__ = [
    "AUDIT_BOUNDARY", "AUDIT_CHECK_PREFIX", "AUDIT_PREFIX", "AUDIT_VERSION", "CHECK_IDS", "DownloadedDataReviewPacketAudit", "DownloadedDataReviewPacketAuditCheck", "address_audit", "address_check", "audit_csv", "audit_json", "audit_packet", "audit_schema", "capabilities_audit", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit",
]

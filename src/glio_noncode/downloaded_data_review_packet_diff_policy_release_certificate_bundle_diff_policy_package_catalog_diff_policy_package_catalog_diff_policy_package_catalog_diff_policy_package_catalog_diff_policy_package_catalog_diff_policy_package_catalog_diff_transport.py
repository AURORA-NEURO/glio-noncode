"""Build, verify, query, and persist deterministic policy-gated catalog diff transports."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from . import (
    downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff as diff_model,
)
from . import (
    downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy as policy_model,
)
from . import (
    downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_tr_ct as contract_model,
)
from . import (
    downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_gate_aud as policy_audit_model,
)
from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_tr_ct import (
    BOUNDARY,
    FILE_NAMES,
    MANIFEST_PREFIX,
    MAX_PACKAGE_BYTES,
    MEDIA_TYPES,
    PACKAGE_FORMAT,
    PACKAGE_PREFIX,
    PAYLOAD_NAMES,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember,
    address_manifest,
    address_member,
    address_member_bytes,
    capabilities,
    manifest_schema,
    package_schema,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"
_FIXED_ATTRIBUTES = 0o100644 << 16
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
MAX_LIMIT = 256
VERSION = contract_model.VERSION


def _safe_member(name: str) -> bool:
    return isinstance(name, str) and bool(name) and not name.startswith("/") and "\\" not in name and ":" not in name and "\x00" not in name and all(part not in {"", ".", ".."} for part in PurePosixPath(name).parts)


def _zip_member(name: str) -> zipfile.ZipInfo:
    if name not in FILE_NAMES:
        raise ValidationError("catalog diff policy transport member is outside the fixed file set")
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


def _parts(raw: bytes) -> tuple[tuple[zipfile.ZipInfo, bytes], ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r", allowZip64=False) as archive:
            return tuple((info, archive.read(info)) for info in archive.infolist())
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read catalog diff policy transport ZIP: {exc}") from exc


def _read_package(value: bytes | bytearray | str | Path | DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket) -> bytes:
    if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket):
        raw = value.package_bytes
    elif isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = read_bytes(value, field="catalog diff policy transport", max_bytes=MAX_PACKAGE_BYTES)
    if len(raw) > MAX_PACKAGE_BYTES:
        raise ValidationError("catalog diff policy transport exceeds its byte bound")
    return raw


def _review(diff: Any, policy: Any, audit: Any) -> str:
    return "\n".join((
        "# Downloaded Data Packet Catalog Diff Policy Packet", "",
        f"- Catalog diff: `{diff.content_address}`", f"- Policy: `{policy.content_address}`", f"- Policy state: **{policy.state}**",
        f"- Policy accepted: **{str(policy.accepted).lower()}**", f"- Policy checks: **{policy.passed_count}/{policy.check_count}**",
        f"- Added / removed / changed / unchanged: **{diff.added_count} / {diff.removed_count} / {diff.changed_count} / {diff.unchanged_count}**",
        f"- Direction: **{diff.direction}**", f"- State transition: **{diff.state_transition}**",
        f"- Independent policy audit: **{audit.passed_count}/{audit.check_count}**", f"- Audit accepted: **{str(audit.accepted).lower()}**",
        "- Source-free after construction: **true**", "", "| component | address |", "| --- | --- |",
        f"| catalog diff | `{diff.content_address}` |", f"| policy | `{policy.content_address}` |", f"| policy audit | `{audit.content_address}` |", "",
        "This packet carries source-free catalog comparison evidence, its applied gate, and an independent audit. It does not carry source archive bytes or record values.", "",
    ))


def _payload_bytes(diff: Any, policy: Any, audit: Any) -> tuple[bytes, bytes, bytes, bytes]:
    diff_value = diff_model.verify_diff(diff)
    policy_value = policy_model.verify_policy(policy)
    audit_value = policy_audit_model.verify_audit(audit)
    review = _review(diff_value, policy_value, audit_value)
    return ((diff_model.diff_json(diff_value)).encode(_UTF8), (policy_model.policy_json(policy_value)).encode(_UTF8), (policy_audit_model.audit_json(audit_value)).encode(_UTF8), review.encode(_UTF8))


def _member(path: str, payload: bytes) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember:
    body = {"relative_path": path, "media_type": MEDIA_TYPES[path], "byte_count": len(payload), "byte_address": address_member_bytes(payload)}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember(**body, content_address=PACKAGE_PREFIX + "-member:pending")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember(**body, content_address=address_member(provisional))


def _zip_bytes(payloads: tuple[tuple[str, bytes], ...]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, payload in payloads:
            archive.writestr(_zip_member(name), payload)
    return output.getvalue()


def build_package(diff: Any, policy: Any, audit: Any | None = None, *, package_id: str = PACKAGE_PREFIX) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket:
    diff_value = diff_model.verify_diff(diff)
    policy_value = policy_model.verify_policy(policy)
    if policy_value.diff_address != diff_value.content_address:
        raise ValidationError("catalog diff policy transport policy does not refer to the supplied diff")
    audit_value = policy_audit_model.audit_policy(policy_value, diff=diff_value) if audit is None else policy_audit_model.verify_audit(audit)
    if audit_value.policy_address != policy_value.content_address or not audit_value.accepted:
        raise ValidationError("catalog diff policy transport requires an accepted independent policy audit")
    payloads = _payload_bytes(diff_value, policy_value, audit_value)
    members = tuple(_member(path, payload) for path, payload in zip(PAYLOAD_NAMES, payloads, strict=True))
    body = {"package_id": package_id, "version": VERSION, "boundary": BOUNDARY, "diff_address": diff_value.content_address, "policy_address": policy_value.content_address, "audit_address": audit_value.content_address, "policy_state": policy_value.state, "policy_accepted": policy_value.accepted, "audit_accepted": audit_value.accepted, "members": members, "package_format": PACKAGE_FORMAT}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest(**body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest(**body, content_address=address_manifest(provisional))
    manifest_bytes = (canonical_json(manifest.to_dict()) + "\n").encode(_UTF8)
    raw = _zip_bytes(((FILE_NAMES[0], manifest_bytes), *tuple(zip(PAYLOAD_NAMES, payloads, strict=True))))
    if len(raw) > MAX_PACKAGE_BYTES:
        raise ValidationError("catalog diff policy transport exceeds its byte bound")
    package = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket(manifest=manifest, package_bytes=raw, package_address=hash_bytes(raw, prefix=PACKAGE_PREFIX))
    return verify_package(package)


def _manifest_and_bodies(raw: bytes) -> tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest, dict[str, bytes]]:
    parts = _parts(raw)
    names = tuple(info.filename for info, _payload in parts)
    if names != FILE_NAMES or any(not _safe_member(name) for name in names):
        raise ValidationError("catalog diff policy transport ZIP members are not the exact safe file set")
    if any(info.date_time != _ZIP_EPOCH or info.compress_type != zipfile.ZIP_STORED or info.external_attr != _FIXED_ATTRIBUTES or info.extra or info.comment for info, _payload in parts):
        raise ValidationError("catalog diff policy transport ZIP metadata is not deterministic")
    bodies = {info.filename: payload for info, payload in parts}
    parsed = _strict_json_loads(bodies[FILE_NAMES[0]].decode(_UTF8))
    if not isinstance(parsed, Mapping) or bodies[FILE_NAMES[0]] != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("catalog diff policy transport manifest is not canonical")
    members = tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketMember(**item) for item in parsed.get("members", ()))
    manifest = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacketManifest(package_id=parsed.get("package_id"), version=parsed.get("version"), boundary=parsed.get("boundary"), diff_address=parsed.get("diff_address"), policy_address=parsed.get("policy_address"), audit_address=parsed.get("audit_address"), policy_state=parsed.get("policy_state"), policy_accepted=parsed.get("policy_accepted"), audit_accepted=parsed.get("audit_accepted"), members=members, package_format=parsed.get("package_format"), content_address=parsed.get("content_address"))
    if address_manifest(manifest) != manifest.content_address:
        raise ValidationError("catalog diff policy transport manifest address does not replay")
    for descriptor in members:
        payload = bodies[descriptor.relative_path]
        if descriptor.byte_count != len(payload) or descriptor.byte_address != address_member_bytes(payload) or descriptor.content_address != address_member(descriptor):
            raise ValidationError(f"catalog diff policy transport member does not replay: {descriptor.relative_path}")
    canonical_raw = _zip_bytes(((FILE_NAMES[0], (canonical_json(manifest.to_dict()) + "\n").encode(_UTF8)), *tuple((name, bodies[name]) for name in PAYLOAD_NAMES)))
    if raw != canonical_raw:
        raise ValidationError("catalog diff policy transport ZIP bytes are not deterministic")
    return manifest, bodies


def verify_package(value: bytes | bytearray | str | Path | DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket:
    raw = _read_package(value)
    manifest, bodies = _manifest_and_bodies(raw)
    diff = diff_model.load_diff(_strict_json_loads(bodies["catalog-diff.json"].decode(_UTF8)))
    policy = policy_model.load_policy(_strict_json_loads(bodies["policy.json"].decode(_UTF8)))
    audit = policy_audit_model.load_audit(_strict_json_loads(bodies["policy-audit.json"].decode(_UTF8)))
    for path in ("catalog-diff.json", "policy.json", "policy-audit.json"):
        if bodies[path] != (canonical_json(_strict_json_loads(bodies[path].decode(_UTF8))) + "\n").encode(_UTF8):
            raise ValidationError(f"catalog diff policy transport payload is not canonical: {path}")
    if manifest.diff_address != diff.content_address or manifest.policy_address != policy.content_address or manifest.audit_address != audit.content_address or policy.diff_address != diff.content_address or audit.policy_address != policy.content_address:
        raise ValidationError("catalog diff policy transport lineage does not replay")
    if manifest.policy_state != policy.state or manifest.policy_accepted != policy.accepted or not manifest.audit_accepted or not audit.accepted:
        raise ValidationError("catalog diff policy transport decision evidence does not replay")
    if _has_forbidden_key({"manifest": manifest.to_dict(), "diff": diff.to_dict(), "policy": policy.to_dict(), "audit": audit.to_dict()}):
        raise ValidationError("catalog diff policy transport crosses the public boundary")
    if bodies["review.md"].decode(_UTF8) != _review(diff, policy, audit):
        raise ValidationError("catalog diff policy transport Markdown does not replay")
    package = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket(manifest=manifest, package_bytes=raw, package_address=hash_bytes(raw, prefix=PACKAGE_PREFIX))
    if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket) and value.to_dict() != package.to_dict():
        raise ValidationError("typed catalog diff policy transport does not replay its bytes")
    return package


def load_package(value: bytes | bytearray | str | Path | DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket) -> tuple[Any, Any, Any, str]:
    package = verify_package(value)
    _, bodies = _manifest_and_bodies(package.package_bytes)
    return (diff_model.load_diff(_strict_json_loads(bodies["catalog-diff.json"].decode(_UTF8))), policy_model.load_policy(_strict_json_loads(bodies["policy.json"].decode(_UTF8))), policy_audit_model.load_audit(_strict_json_loads(bodies["policy-audit.json"].decode(_UTF8))), bodies["review.md"].decode(_UTF8))


def package_json(value: Any) -> str:
    return canonical_json(verify_package(value).to_dict()) + "\n"


def write_package(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyReviewPacket:
    package = verify_package(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("catalog diff policy transport destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("catalog diff policy transport destination is not a file")
    _validate_parent(path.parent, "catalog diff policy transport destination")
    atomic_write_bytes(path, package.package_bytes, field="catalog diff policy transport destination")
    return package


def query_package(value: Any, *, resource: str = "summary", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    if resource not in {"summary", "members", "manifest", "diff", "policy", "audit", "review"} or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("catalog diff policy transport query is invalid")
    package = verify_package(value)
    diff, policy, audit, review = load_package(package)
    if resource == "summary":
        result: Any = {"resource": resource, "value": package.summary()}
    elif resource == "members":
        rows = [item.to_dict() for item in package.manifest.members]
        result = {"resource": resource, "total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}
    elif resource == "manifest":
        result = {"resource": resource, "value": package.manifest.to_dict()}
    elif resource == "diff":
        result = {"resource": resource, "value": diff.summary()}
    elif resource == "policy":
        result = {"resource": resource, "value": policy.summary()}
    elif resource == "audit":
        result = {"resource": resource, "value": audit.summary()}
    else:
        result = {"resource": resource, "value": review}
    return result | {"package_address": package.package_address, "content_address": content_hash(result, prefix=PACKAGE_PREFIX + "-query")}


def package_csv(value: Any, *, offset: int = 0, limit: int = 50) -> str:
    result = query_package(value, resource="members", offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("relative_path", "media_type", "byte_count", "byte_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return stream.getvalue()


def render_package_markdown(value: Any) -> str:
    package = verify_package(value)
    _diff, _policy, _audit, review = load_package(package)
    return review + "\n## Transport\n\n" + f"- Package: `{package.package_address}`\n- Members: **{len(FILE_NAMES)}**\n"


# Transport-named entry points keep the fixed ZIP surface explicit while retaining the
# proven package primitives for callers that already consume this module.
build_transport = build_package
load_transport = load_package
transport_json = package_json
write_transport = write_package
query_transport = query_package
transport_csv = package_csv
render_transport_markdown = render_package_markdown
verify_transport = verify_package
transport_schema = package_schema
transport_manifest_schema = manifest_schema
transport_capabilities = capabilities


__all__ = ["build_package", "build_transport", "capabilities", "load_package", "load_transport", "manifest_schema", "package_csv", "package_json", "package_schema", "query_package", "query_transport", "render_package_markdown", "render_transport_markdown", "transport_capabilities", "transport_csv", "transport_json", "transport_manifest_schema", "transport_schema", "verify_package", "verify_transport", "write_package", "write_transport"]

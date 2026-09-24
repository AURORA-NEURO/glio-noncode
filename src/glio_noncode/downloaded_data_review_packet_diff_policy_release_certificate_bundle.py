"""Build, verify, query, and persist complete downloaded-data release bundles."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from . import downloaded_data_review_packet_diff_policy_package as package_model
from . import downloaded_data_review_packet_diff_policy_release_certificate as certificate_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_audit as certificate_audit_model
from . import downloaded_data_review_packet_diff_policy_run as run_model
from . import downloaded_data_review_packet_diff_policy_run_audit as run_audit_model
from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_contracts import (
    BOUNDARY,
    BUNDLE_FORMAT,
    BUNDLE_PREFIX,
    FILE_NAMES,
    MANIFEST_PREFIX,
    MAX_BUNDLE_BYTES,
    MEDIA_TYPES,
    PAYLOAD_NAMES,
    VERSION,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember,
    address_manifest,
    address_member,
    address_member_bytes,
    bundle_schema,
    capabilities,
    manifest_schema,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"
_FIXED_ATTRIBUTES = 0o100644 << 16
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
MAX_LIMIT = 256
BUNDLE_RESOURCES = ("summary", "members", "manifest", "certificate", "certificate-audit", "run", "run-audit", "package", "review")


def _safe_member(name: str) -> bool:
    return isinstance(name, str) and bool(name) and not name.startswith("/") and "\\" not in name and ":" not in name and "\x00" not in name and all(part not in {"", ".", ".."} for part in PurePosixPath(name).parts)


def _zip_member(name: str) -> zipfile.ZipInfo:
    if name not in FILE_NAMES:
        raise ValidationError("release bundle member is outside the fixed file set")
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
        raise ValidationError(f"cannot read downloaded-data release bundle ZIP: {exc}") from exc


def _read_bundle(value: bytes | bytearray | str | Path | DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle) -> bytes:
    if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle):
        raw = value.bundle_bytes
    elif isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = read_bytes(value, field="downloaded-data release bundle", max_bytes=MAX_BUNDLE_BYTES)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValidationError("downloaded-data release bundle exceeds its byte bound")
    return raw


def _zip_bytes(payloads: tuple[tuple[str, bytes], ...]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, payload in payloads:
            archive.writestr(_zip_member(name), payload)
    return output.getvalue()


def _member(path: str, payload: bytes) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember:
    body = {"relative_path": path, "media_type": MEDIA_TYPES[path], "byte_count": len(payload), "byte_address": address_member_bytes(payload)}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember(**body, content_address=BUNDLE_PREFIX + "-member:pending")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember(**body, content_address=address_member(provisional))


def _review(certificate: Any, run: Any, package: Any, certificate_audit: Any, run_audit: Any) -> str:
    return "\n".join((
        "# Downloaded Data Release Certificate Bundle", "",
        f"- Certificate: `{certificate.content_address}`", f"- Release state: **{certificate.release_state}**", f"- Release eligible: **{str(certificate.release_eligible).lower()}**",
        f"- Run: `{run.content_address}`", f"- Package: `{package.package_address}` ({len(package.package_bytes)} bytes)", f"- Run audit: **{run_audit.passed_count}/{run_audit.check_count}**", f"- Certificate audit: **{certificate_audit.passed_count}/{certificate_audit.check_count}**",
        "- Source-free after construction: **true**", "", "| component | address | accepted |", "| --- | --- | --- |",
        f"| certificate | `{certificate.content_address}` | {str(certificate.release_eligible).lower()} |", f"| certificate audit | `{certificate_audit.content_address}` | {str(certificate_audit.accepted).lower()} |", f"| run | `{run.content_address}` | true |", f"| run audit | `{run_audit.content_address}` | {str(run_audit.accepted).lower()} |", f"| package | `{package.package_address}` | true |",
        "", "This deterministic bundle carries addressed release evidence and the portable review package. It does not carry source archive bytes or record values.", "",
    ))


def _payloads(certificate: Any, certificate_audit: Any, run: Any, run_audit: Any, package: Any) -> tuple[tuple[str, bytes], ...]:
    review = _review(certificate, run, package, certificate_audit, run_audit).encode(_UTF8)
    return (
        ("certificate.json", certificate_model.certificate_json(certificate).encode(_UTF8)),
        ("certificate-audit.json", certificate_audit_model.audit_json(certificate_audit).encode(_UTF8)),
        ("run.json", run_model.run_json(run).encode(_UTF8)),
        ("run-audit.json", run_audit_model.audit_json(run_audit).encode(_UTF8)),
        ("package.zip", package.package_bytes),
        ("review.md", review),
    )


def build_bundle(
    certificate: Any,
    package: Any,
    run: Any,
    run_audit: Any,
    certificate_audit: Any | None = None,
    *,
    bundle_id: str | None = None,
) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle:
    """Build one deterministic handoff containing the complete release chain."""

    package_value = package_model.verify_package(package)
    run_value = run_model.verify_run(run, package=package_value)
    run_audit_value = run_audit_model.verify_audit(run_audit)
    certificate_value = certificate_model.verify_certificate(certificate, run=run_value, package=package_value, run_audit=run_audit_value)
    computed_certificate_audit = certificate_audit_model.audit_certificate(certificate_value, run=run_value, package=package_value, run_audit=run_audit_value)
    if not computed_certificate_audit.accepted:
        raise ValidationError("release bundle requires an accepted independent certificate audit")
    if certificate_audit is None:
        certificate_audit_value = computed_certificate_audit
    else:
        certificate_audit_value = certificate_audit_model.verify_audit(certificate_audit)
        if canonical_json(certificate_audit_value.to_dict()) != canonical_json(computed_certificate_audit.to_dict()):
            raise ValidationError("supplied certificate audit does not replay the supplied release chain")
    bundle_id = bundle_id or certificate_value.certificate_id + "-bundle"
    if not isinstance(bundle_id, str) or not bundle_id or len(bundle_id) > 256 or bundle_id.strip() != bundle_id or any(char.isspace() for char in bundle_id) or "/" in bundle_id or "\\" in bundle_id or '"' in bundle_id:
        raise ValidationError("release bundle ID must be a compact label")
    payloads = _payloads(certificate_value, certificate_audit_value, run_value, run_audit_value, package_value)
    members = tuple(_member(path, payload) for path, payload in payloads)
    body = {"bundle_id": bundle_id, "version": VERSION, "boundary": BOUNDARY, "certificate_address": certificate_value.content_address, "certificate_audit_address": certificate_audit_value.content_address, "run_address": run_value.content_address, "run_audit_address": run_audit_value.content_address, "package_address": package_value.package_address, "package_byte_count": len(package_value.package_bytes), "release_state": certificate_value.release_state, "release_eligible": certificate_value.release_eligible, "members": members, "bundle_format": BUNDLE_FORMAT}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest(**body, content_address=MANIFEST_PREFIX + ":pending")
    manifest = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest(**body, content_address=address_manifest(provisional))
    manifest_bytes = (canonical_json(manifest.to_dict()) + "\n").encode(_UTF8)
    raw = _zip_bytes(((FILE_NAMES[0], manifest_bytes), *payloads))
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValidationError("downloaded-data release bundle exceeds its byte bound")
    bundle = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle(manifest=manifest, bundle_bytes=raw, bundle_address=hash_bytes(raw, prefix=BUNDLE_PREFIX))
    return verify_bundle(bundle)


def _manifest_and_bodies(raw: bytes) -> tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest, dict[str, bytes]]:
    parts = _parts(raw)
    names = tuple(info.filename for info, _payload in parts)
    if names != FILE_NAMES or any(not _safe_member(name) for name in names):
        raise ValidationError("release bundle ZIP members are not the exact safe file set")
    if any(info.date_time != _ZIP_EPOCH or info.compress_type != zipfile.ZIP_STORED or info.external_attr != _FIXED_ATTRIBUTES or info.extra or info.comment for info, _payload in parts):
        raise ValidationError("release bundle ZIP metadata is not deterministic")
    bodies = {info.filename: payload for info, payload in parts}
    parsed = _strict_json_loads(bodies[FILE_NAMES[0]].decode(_UTF8))
    if not isinstance(parsed, Mapping) or bodies[FILE_NAMES[0]] != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("release bundle manifest is not canonical")
    members = tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleMember(**item) for item in parsed.get("members", ()))
    manifest = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleManifest(bundle_id=parsed.get("bundle_id"), version=parsed.get("version"), boundary=parsed.get("boundary"), certificate_address=parsed.get("certificate_address"), certificate_audit_address=parsed.get("certificate_audit_address"), run_address=parsed.get("run_address"), run_audit_address=parsed.get("run_audit_address"), package_address=parsed.get("package_address"), package_byte_count=parsed.get("package_byte_count"), release_state=parsed.get("release_state"), release_eligible=parsed.get("release_eligible"), members=members, bundle_format=parsed.get("bundle_format"), content_address=parsed.get("content_address"))
    if address_manifest(manifest) != manifest.content_address:
        raise ValidationError("release bundle manifest address does not replay")
    for descriptor in members:
        payload = bodies[descriptor.relative_path]
        if descriptor.byte_count != len(payload) or descriptor.byte_address != address_member_bytes(payload) or descriptor.content_address != address_member(descriptor):
            raise ValidationError(f"release bundle member does not replay: {descriptor.relative_path}")
    canonical_raw = _zip_bytes(((FILE_NAMES[0], (canonical_json(manifest.to_dict()) + "\n").encode(_UTF8)), *tuple((name, bodies[name]) for name in PAYLOAD_NAMES)))
    if raw != canonical_raw:
        raise ValidationError("release bundle ZIP bytes are not the deterministic reconstruction")
    return manifest, bodies


def verify_bundle(value: bytes | bytearray | str | Path | DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle:
    raw = _read_bundle(value)
    manifest, bodies = _manifest_and_bodies(raw)
    certificate = certificate_model.load_certificate(_strict_json_loads(bodies["certificate.json"].decode(_UTF8)))
    certificate_audit = certificate_audit_model.load_audit(_strict_json_loads(bodies["certificate-audit.json"].decode(_UTF8)))
    run = run_model.load_run(_strict_json_loads(bodies["run.json"].decode(_UTF8)))
    run_audit = run_audit_model.load_audit(_strict_json_loads(bodies["run-audit.json"].decode(_UTF8)))
    package = package_model.verify_package(bodies["package.zip"])
    for path in ("certificate.json", "certificate-audit.json", "run.json", "run-audit.json"):
        if bodies[path] != (canonical_json(_strict_json_loads(bodies[path].decode(_UTF8))) + "\n").encode(_UTF8):
            raise ValidationError(f"release bundle payload is not canonical: {path}")
    if manifest.certificate_address != certificate.content_address or manifest.certificate_audit_address != certificate_audit.content_address or manifest.run_address != run.content_address or manifest.run_audit_address != run_audit.content_address or manifest.package_address != package.package_address or manifest.package_byte_count != len(package.package_bytes):
        raise ValidationError("release bundle component lineage does not replay")
    if manifest.release_state != certificate.release_state or manifest.release_eligible != certificate.release_eligible:
        raise ValidationError("release bundle decision does not replay")
    run_value = run_model.verify_run(run, package=package)
    certificate_model.verify_certificate(certificate, run=run_value, package=package, run_audit=run_audit)
    if not run_audit.accepted or not certificate_audit.accepted:
        raise ValidationError("release bundle requires accepted nested audits")
    computed_certificate_audit = certificate_audit_model.audit_certificate(certificate, run=run_value, package=package, run_audit=run_audit)
    if canonical_json(computed_certificate_audit.to_dict()) != canonical_json(certificate_audit.to_dict()):
        raise ValidationError("release bundle certificate audit does not replay")
    if _has_forbidden_key({"manifest": manifest.to_dict(), "certificate": certificate.to_dict(), "certificate_audit": certificate_audit.to_dict(), "run": run.to_dict(), "run_audit": run_audit.to_dict(), "package": package.to_dict()}):
        raise ValidationError("release bundle payload crosses the public boundary")
    if bodies["review.md"].decode(_UTF8) != _review(certificate, run, package, certificate_audit, run_audit):
        raise ValidationError("release bundle Markdown does not replay")
    bundle = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle(manifest=manifest, bundle_bytes=raw, bundle_address=hash_bytes(raw, prefix=BUNDLE_PREFIX))
    if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle) and value.to_dict() != bundle.to_dict():
        raise ValidationError("typed release bundle does not replay its bytes")
    return bundle


def load_bundle(value: bytes | bytearray | str | Path | DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle) -> tuple[Any, Any, Any, Any, Any, str]:
    bundle = verify_bundle(value)
    _, bodies = _manifest_and_bodies(bundle.bundle_bytes)
    return (
        certificate_model.load_certificate(_strict_json_loads(bodies["certificate.json"].decode(_UTF8))),
        certificate_audit_model.load_audit(_strict_json_loads(bodies["certificate-audit.json"].decode(_UTF8))),
        run_model.load_run(_strict_json_loads(bodies["run.json"].decode(_UTF8))),
        run_audit_model.load_audit(_strict_json_loads(bodies["run-audit.json"].decode(_UTF8))),
        package_model.verify_package(bodies["package.zip"]),
        bodies["review.md"].decode(_UTF8),
    )


def bundle_json(value: Any) -> str:
    return canonical_json(verify_bundle(value).to_dict()) + "\n"


def write_bundle(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundle:
    bundle = verify_bundle(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("downloaded-data release bundle destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("downloaded-data release bundle destination is not a file")
    _validate_parent(path.parent, "downloaded-data release bundle destination")
    atomic_write_bytes(path, bundle.bundle_bytes, field="downloaded-data release bundle destination")
    return bundle


def query_bundle(value: Any, *, resource: str = "summary", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    if resource not in BUNDLE_RESOURCES or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("downloaded-data release bundle query is invalid")
    bundle = verify_bundle(value)
    certificate, certificate_audit, run, run_audit, package, review = load_bundle(bundle)
    if resource == "summary":
        result: Any = {"resource": resource, "value": bundle.summary()}
    elif resource == "members":
        rows = [item.to_dict() for item in bundle.manifest.members]
        result = {"resource": resource, "total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}
    elif resource == "manifest":
        result = {"resource": resource, "value": bundle.manifest.to_dict()}
    elif resource == "certificate":
        result = {"resource": resource, "value": certificate.summary()}
    elif resource == "certificate-audit":
        result = {"resource": resource, "value": certificate_audit.summary()}
    elif resource == "run":
        result = {"resource": resource, "value": run.summary()}
    elif resource == "run-audit":
        result = {"resource": resource, "value": run_audit.summary()}
    elif resource == "package":
        result = {"resource": resource, "value": package.summary()}
    else:
        result = {"resource": resource, "value": review}
    return result | {"bundle_address": bundle.bundle_address, "content_address": content_hash(result, prefix=BUNDLE_PREFIX + "-query")}


def bundle_csv(value: Any, *, offset: int = 0, limit: int = 50) -> str:
    result = query_bundle(value, resource="members", offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("relative_path", "media_type", "byte_count", "byte_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return stream.getvalue()


def render_bundle_markdown(value: Any) -> str:
    bundle = verify_bundle(value)
    _certificate, _certificate_audit, _run, _run_audit, _package, review = load_bundle(bundle)
    return review + "\n## Transport\n\n" + f"- Bundle: `{bundle.bundle_address}`\n- Members: **{len(FILE_NAMES)}**\n"


__all__ = [
    "BUNDLE_RESOURCES", "build_bundle", "bundle_csv", "bundle_json", "bundle_schema", "capabilities", "load_bundle", "manifest_schema", "query_bundle", "render_bundle_markdown", "verify_bundle", "write_bundle",
]

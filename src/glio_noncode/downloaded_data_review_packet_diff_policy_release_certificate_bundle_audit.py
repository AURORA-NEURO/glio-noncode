"""Independent audit for deterministic downloaded-data release bundles."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle as bundle_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_audit as certificate_audit_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_contracts import (
    BOUNDARY,
    BUNDLE_PREFIX,
    FILE_NAMES,
    PAYLOAD_NAMES,
    VERSION,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY + "_audit"
AUDIT_PREFIX = BUNDLE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address", "audit-canonical", "audit-member-order", "audit-member-receipts", "audit-manifest-address",
    "audit-certificate-lineage", "audit-certificate-audit-lineage", "audit-run-lineage", "audit-run-audit-lineage",
    "audit-package-lineage", "audit-package-bytes", "audit-nested-audits", "audit-decision-state", "audit-review-replay",
    "audit-public-boundary", "audit-contents",
)
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "release bundle audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("release bundle audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("release bundle audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "release bundle audit detail", 2048)
        self.content_address = content_address
        if not content_address.endswith(":pending"):
            _address(content_address, "release bundle audit check address", CHECK_PREFIX)
            if address_check(self) != content_address:
                raise ValidationError("release bundle audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck":
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("release bundle audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit:
    FIELDS = ("bundle_id", "bundle_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, bundle_id: str, bundle_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.bundle_id = _label(bundle_id, "release bundle audit bundle ID")
        self.bundle_address = _address(bundle_address, "release bundle audit bundle address", BUNDLE_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("release bundle audit aggregates do not replay")
        if not content_address.endswith(":pending"):
            _address(content_address, "release bundle audit address", AUDIT_PREFIX)
            if address_audit(self) != content_address:
                raise ValidationError("release bundle audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"bundle_id": self.bundle_id, "bundle_address": self.bundle_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit":
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("release bundle audit fields are not exact")
        return cls(value["bundle_id"], value["bundle_address"], tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(bundle_id: str, bundle_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck, ...]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit:
    body = {"bundle_id": bundle_id or "unavailable", "bundle_address": bundle_address or BUNDLE_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_bundle(value: Any) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit:
    try:
        bundle = bundle_model.verify_bundle(value)
        manifest, bodies = bundle_model._manifest_and_bodies(bundle.bundle_bytes)
        certificate, certificate_audit, run, run_audit, package, review = bundle_model.load_bundle(bundle)
        recomputed_certificate_audit = certificate_audit_model.audit_certificate(certificate, run=run, package=package, run_audit=run_audit)
        member_receipts = all(item.byte_count == len(bodies[item.relative_path]) and item.byte_address == bundle_model.address_member_bytes(bodies[item.relative_path]) and item.content_address == bundle_model.address_member(item) for item in manifest.members)
        checks = (
            _check("audit-address", bundle_model.hash_bytes(bundle.bundle_bytes, prefix=BUNDLE_PREFIX) == bundle.bundle_address, bundle.bundle_address, "replayable", "bundle byte address replays"),
            _check("audit-canonical", bundle_model.bundle_json(bundle) == canonical_json(bundle.to_dict()) + "\n", "canonical", "canonical", "bundle JSON reload is canonical"),
            _check("audit-member-order", tuple(item.relative_path for item in manifest.members) == PAYLOAD_NAMES and tuple(info.filename for info, _payload in bundle_model._parts(bundle.bundle_bytes)) == FILE_NAMES, tuple(item.relative_path for item in manifest.members), FILE_NAMES[1:], "bundle member order is fixed"),
            _check("audit-member-receipts", member_receipts, "replayed" if member_receipts else "mismatch", "byte and content addresses replay", "member receipts replay"),
            _check("audit-manifest-address", bundle_model.address_manifest(manifest) == manifest.content_address, manifest.content_address, "replayable", "manifest address replays"),
            _check("audit-certificate-lineage", manifest.certificate_address == certificate.content_address, manifest.certificate_address, certificate.content_address, "certificate lineage replays"),
            _check("audit-certificate-audit-lineage", manifest.certificate_audit_address == certificate_audit.content_address, manifest.certificate_audit_address, certificate_audit.content_address, "certificate audit lineage replays"),
            _check("audit-run-lineage", manifest.run_address == run.content_address, manifest.run_address, run.content_address, "run lineage replays"),
            _check("audit-run-audit-lineage", manifest.run_audit_address == run_audit.content_address, manifest.run_audit_address, run_audit.content_address, "run audit lineage replays"),
            _check("audit-package-lineage", manifest.package_address == package.package_address and manifest.package_byte_count == len(package.package_bytes), {"address": manifest.package_address, "byte_count": manifest.package_byte_count}, {"address": package.package_address, "byte_count": len(package.package_bytes)}, "package lineage replays"),
            _check("audit-package-bytes", bodies["package.zip"] == package.package_bytes and package.package_address == bundle.manifest.package_address, len(bodies["package.zip"]), manifest.package_byte_count, "nested package bytes replay"),
            _check("audit-nested-audits", run_audit.accepted and certificate_audit.accepted and recomputed_certificate_audit.accepted and canonical_json(certificate_audit.to_dict()) == canonical_json(recomputed_certificate_audit.to_dict()), {"run_audit": run_audit.accepted, "certificate_audit": certificate_audit.accepted}, "accepted and recomputed", "nested audits are accepted and deterministic"),
            _check("audit-decision-state", manifest.release_state == certificate.release_state and manifest.release_eligible == certificate.release_eligible, {"state": manifest.release_state, "eligible": manifest.release_eligible}, {"state": certificate.release_state, "eligible": certificate.release_eligible}, "release decision is conserved"),
            _check("audit-review-replay", bodies["review.md"].decode("utf-8") == bundle_model._review(certificate, run, package, certificate_audit, run_audit), "replayed", "replayed", "review Markdown replays"),
            _check("audit-public-boundary", not _has_forbidden_key(bundle.to_dict()), "clean", "clean", "bundle receipt contains no prohibited public keys"),
            _check("audit-contents", not _has_forbidden_key({"certificate": certificate.to_dict(), "certificate_audit": certificate_audit.to_dict(), "run": run.to_dict(), "run_audit": run_audit.to_dict(), "package": package.to_dict()}), "clean", "clean", "nested contents remain inside the public boundary"),
        )
        return _receipt(manifest.bundle_id, bundle.bundle_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"release bundle audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", BUNDLE_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit:
    audit = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("release bundle audit address does not replay")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data release bundle audit", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("release bundle audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("release bundle audit destination is not a file")
    _validate_parent(path.parent, "release bundle audit destination")
    atomic_write_text(path, audit_json(audit), field="release bundle audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("release bundle audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("release bundle audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded Data Release Certificate Bundle Audit", "", f"- Bundle: `{audit.bundle_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release bundle audit check", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release certificate bundle audit", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleAudit.FIELDS), "properties": {"bundle_id": {"type": "string"}, "bundle_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "requires_nested_package": True, "content_addressed": True}


__all__ = ["AUDIT_PREFIX", "audit_bundle", "audit_csv", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

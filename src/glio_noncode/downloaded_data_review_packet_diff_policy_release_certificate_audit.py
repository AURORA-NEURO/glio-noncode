"""Independent audit for source-free downloaded-data release certificates."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate as certificate_model
from . import downloaded_data_review_packet_diff_policy_package as package_model
from . import downloaded_data_review_packet_diff_policy_run as run_model
from . import downloaded_data_review_packet_diff_policy_run_audit as run_audit_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_diff_policy_release_certificate_contracts import (
    BOUNDARY,
    CERTIFICATE_PREFIX,
    VERSION,
    DownloadedDataReviewPacketDiffPolicyReleaseCertificate,
    address_certificate,
    capabilities as certificate_capabilities,
)
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY + "_audit"
AUDIT_PREFIX = CERTIFICATE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address", "audit-canonical", "audit-identity", "audit-run-availability", "audit-run-lineage",
    "audit-package-availability", "audit-package-lineage", "audit-run-audit-availability", "audit-run-audit-lineage",
    "audit-policy-lineage", "audit-audit-recomputation", "audit-decision-replay", "audit-eligibility", "audit-byte-count", "audit-public-boundary",
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


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "release certificate audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("release certificate audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("release certificate audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "release certificate audit detail", 2048)
        self.content_address = content_address
        if not content_address.endswith(":pending"):
            _address(content_address, "release certificate audit check address", CHECK_PREFIX)
            if address_check(self) != content_address:
                raise ValidationError("release certificate audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck":
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("release certificate audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit:
    FIELDS = ("certificate_id", "certificate_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, certificate_id: str, certificate_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.certificate_id = _label(certificate_id, "release certificate audit certificate ID")
        self.certificate_address = _address(certificate_address, "release certificate audit certificate address", CERTIFICATE_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("release certificate audit aggregates do not replay")
        if not content_address.endswith(":pending"):
            _address(content_address, "release certificate audit address", AUDIT_PREFIX)
            if address_audit(self) != content_address:
                raise ValidationError("release certificate audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, "certificate_address": self.certificate_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit":
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("release certificate audit fields are not exact")
        return cls(value["certificate_id"], value["certificate_address"], tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(certificate_id: str, certificate_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck, ...]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit:
    body = {"certificate_id": certificate_id or "unavailable", "certificate_address": certificate_address or CERTIFICATE_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_certificate(value: Any, *, run: Any | None = None, package: Any | None = None, run_audit: Any | None = None) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit:
    try:
        certificate = certificate_model.verify_certificate(value)
        run_value = run_model.verify_run(run, package=package) if run is not None and package is not None else None
        package_value = package_model.verify_package(package) if package is not None else None
        recomputed = run_audit_model.audit_run(run_value, package=package_value) if run_value is not None and package_value is not None else None
        run_audit_value = run_audit_model.verify_audit(run_audit) if run_audit is not None else recomputed
        checks = (
            _check("audit-address", address_certificate(certificate) == certificate.content_address, certificate.content_address, "replayable", "certificate address replays"),
            _check("audit-canonical", certificate_model.certificate_json(certificate) == canonical_json(certificate.to_dict()) + "\n", "canonical", "canonical", "certificate JSON reload is canonical"),
            _check("audit-identity", certificate.version == certificate_model.VERSION and certificate.boundary == BOUNDARY, {"version": certificate.version, "boundary": certificate.boundary}, {"version": certificate_model.VERSION, "boundary": BOUNDARY}, "certificate identity is current"),
            _check("audit-run-availability", run_value is not None, "available" if run_value is not None else "missing", "available", "run receipt is supplied for independent lineage audit"),
            _check("audit-run-lineage", run_value is not None and certificate.run_id == run_value.run_id and certificate.run_address == run_value.content_address, {"run_id": certificate.run_id, "run_address": certificate.run_address}, "supplied run address and ID", "run lineage replays"),
            _check("audit-package-availability", package_value is not None, "available" if package_value is not None else "missing", "available", "portable package bytes are supplied for independent audit"),
            _check("audit-package-lineage", package_value is not None and certificate.package_address == package_value.package_address and certificate.package_byte_count == len(package_value.package_bytes), {"address": certificate.package_address, "byte_count": certificate.package_byte_count}, "supplied package address and bytes", "package lineage replays"),
            _check("audit-run-audit-availability", run_audit_value is not None, "available" if run_audit_value is not None else "missing", "available", "independent run audit is supplied"),
            _check("audit-run-audit-lineage", run_audit_value is not None and certificate.run_audit_address == run_audit_value.content_address and certificate.run_audit_accepted == run_audit_value.accepted, {"address": certificate.run_audit_address, "accepted": certificate.run_audit_accepted}, "supplied run audit address and acceptance", "run audit lineage replays"),
            _check("audit-policy-lineage", run_value is not None and certificate.policy_address == run_value.policy_address and certificate.policy_audit_address == run_value.policy_audit_address and certificate.package_audit_address == run_value.package_audit_address, {"policy": certificate.policy_address, "policy_audit": certificate.policy_audit_address, "package_audit": certificate.package_audit_address}, "run policy and audit addresses", "policy lineage replays"),
            _check("audit-audit-recomputation", recomputed is not None and run_audit_value is not None and canonical_json(recomputed.to_dict()) == canonical_json(run_audit_value.to_dict()), "recomputed" if recomputed is not None and run_audit_value is not None and canonical_json(recomputed.to_dict()) == canonical_json(run_audit_value.to_dict()) else "mismatch", "recomputed run audit", "independent run audit is deterministic"),
            _check("audit-decision-replay", certificate.release_eligible == (certificate.run_audit_accepted and certificate.policy_accepted and certificate.policy_audit_accepted and certificate.package_audit_accepted and certificate.policy_state == "ready"), certificate.release_eligible, "conjunctive accepted evidence", "release decision replays"),
            _check("audit-eligibility", certificate.release_eligible == (certificate.release_state == "ready"), {"eligible": certificate.release_eligible, "state": certificate.release_state}, "ready iff eligible", "release state replays eligibility"),
            _check("audit-byte-count", certificate.package_byte_count > 0, certificate.package_byte_count, "positive package byte count", "package byte count is retained"),
            _check("audit-public-boundary", not _has_forbidden_key(certificate.to_dict()), "clean", "clean", "certificate contains no prohibited public keys"),
        )
        return _receipt(certificate.certificate_id, certificate.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"release certificate audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", CERTIFICATE_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit:
    audit = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("release certificate audit address does not replay")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data release certificate audit", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("release certificate audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("release certificate audit destination is not a file")
    _validate_parent(path.parent, "release certificate audit destination")
    atomic_write_text(path, audit_json(audit), field="release certificate audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("release certificate audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("release certificate audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded Data Release Certificate Audit", "", f"- Certificate: `{audit.certificate_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release certificate audit check", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyReleaseCertificateAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release certificate audit", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyReleaseCertificateAudit.FIELDS), "properties": {"certificate_id": {"type": "string"}, "certificate_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "requires_run_package_and_audit": True, "source_free": True, "content_addressed": True}


__all__ = ["AUDIT_PREFIX", "audit_certificate", "audit_csv", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

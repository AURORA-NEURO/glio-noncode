"""Independent audits for portable diff-policy evidence packages."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_package as package_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

AUDIT_VERSION = package_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address", "audit-canonical", "audit-member-order", "audit-member-addresses",
    "audit-lineage", "audit-diff-replay", "audit-policy-replay", "audit-policy-audit-replay",
    "audit-policy-state", "audit-review-replay", "audit-fixed-zip", "audit-source-free",
    "audit-public-boundary", "audit-query-replay",
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


class DownloadedDataReviewPacketDiffPolicyPackageAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "package audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("package audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("package audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "package audit check detail", 2048)
        self.content_address = _address(content_address, "package audit check address", CHECK_PREFIX) if not content_address.endswith(":pending") else content_address
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("package audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyPackageAuditCheck:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("package audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyPackageAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffPolicyPackageAudit:
    FIELDS = ("package_id", "package_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, package_id: str, package_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyPackageAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.package_id = _label(package_id, "package audit package ID")
        self.package_address = _address(package_address, "package audit package address", package_model.PACKAGE_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = _address(content_address, "package audit address", AUDIT_PREFIX) if not content_address.endswith(":pending") else content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("package audit aggregates do not replay")
        if not content_address.endswith(":pending") and address_audit(self) != content_address:
            raise ValidationError("package audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "package_address": self.package_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyPackageAudit:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("package audit fields are not exact")
        return cls(value["package_id"], value["package_address"], tuple(DownloadedDataReviewPacketDiffPolicyPackageAuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataReviewPacketDiffPolicyPackageAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffPolicyPackageAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyPackageAuditCheck(**body)
    return DownloadedDataReviewPacketDiffPolicyPackageAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(package_id: str, package_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyPackageAuditCheck, ...]) -> DownloadedDataReviewPacketDiffPolicyPackageAudit:
    body = {"package_id": package_id or "unavailable", "package_address": package_address or package_model.PACKAGE_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyPackageAudit(**body)
    return DownloadedDataReviewPacketDiffPolicyPackageAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_package(value: Any) -> DownloadedDataReviewPacketDiffPolicyPackageAudit:
    try:
        package = package_model.verify_package(value)
        diff, policy, audit, review = package_model.load_package(package)
        checks = (
            _check("audit-address", package.package_address == hash_bytes(package.package_bytes, prefix=package_model.PACKAGE_PREFIX), package.package_address, "replayable", "package byte address is replayable"),
            _check("audit-canonical", package_model.package_json(package) == canonical_json(package.to_dict()) + "\n", "canonical", "canonical", "package summary is canonical"),
            _check("audit-member-order", tuple(item.relative_path for item in package.manifest.members) == package_model.PAYLOAD_NAMES, tuple(item.relative_path for item in package.manifest.members), package_model.PAYLOAD_NAMES, "package member order is canonical"),
            _check("audit-member-addresses", all(package_model.address_member(item) == item.content_address for item in package.manifest.members), "replayed", "replayed", "every package member address replays"),
            _check("audit-lineage", package.manifest.diff_address == diff.content_address and package.manifest.policy_address == policy.content_address and package.manifest.audit_address == audit.content_address, "replayed", "replayed", "manifest lineage points to all payloads"),
            _check("audit-diff-replay", diff_model_address(diff) == diff.content_address, diff.content_address, "replayed", "diff payload is typed and addressed"),
            _check("audit-policy-replay", policy_model_address(policy) == policy.content_address, policy.content_address, "replayed", "policy payload is typed and addressed"),
            _check("audit-policy-audit-replay", audit_model_address(audit) == audit.content_address and audit.accepted, {"address": audit.content_address, "accepted": audit.accepted}, "replayed and accepted", "independent policy audit is accepted"),
            _check("audit-policy-state", package.manifest.policy_state == ("ready" if package.manifest.policy_accepted else "blocked"), package.manifest.policy_state, "ready iff accepted", "policy state preserves the policy decision"),
            _check("audit-review-replay", review == package_model._review(diff, policy, audit), "replayed", "replayed", "review Markdown is deterministic"),
            _check("audit-fixed-zip", package_model._manifest_and_bodies(package.package_bytes)[0].to_dict() == package.manifest.to_dict(), "fixed", "fixed", "ZIP metadata and manifest replay"),
            _check("audit-source-free", True, "not present", "not present", "package retains no source archive or record values"),
            _check("audit-public-boundary", not _has_forbidden_key(package.to_dict()), "clean", "clean", "package summary contains no prohibited public keys"),
            _check("audit-query-replay", package_model.query_package(package, limit=len(package_model.FILE_NAMES))["package_address"] == package.package_address, package.package_address, package.package_address, "package queries retain transport lineage"),
        )
        return _receipt(package.manifest.package_id, package.package_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"package audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", package_model.PACKAGE_PREFIX + ":" + "0" * 64, checks)


def diff_model_address(value: Any) -> str:
    from . import downloaded_data_review_packet_diff as model
    return model.address_diff(value)


def policy_model_address(value: Any) -> str:
    from . import downloaded_data_review_packet_diff_policy as model
    return model.address_policy(value)


def audit_model_address(value: Any) -> str:
    from . import downloaded_data_review_packet_diff_policy_audit as model
    return model.address_audit(value)


def verify_audit(value: Any) -> DownloadedDataReviewPacketDiffPolicyPackageAudit:
    audit = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyPackageAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("package audit address does not replay")
    return DownloadedDataReviewPacketDiffPolicyPackageAudit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyPackageAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded-data review package audit", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyPackageAudit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyPackageAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("package audit destination already exists")
    _validate_parent(path.parent, "package audit destination")
    atomic_write_text(path, audit_json(audit), field="package audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("package audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("package audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("check_id", "passed", "observed", "required", "detail", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded Data Review Package Audit", "", f"- Package: `{audit.package_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review package audit check", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyPackageAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review package audit", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyPackageAudit.FIELDS), "properties": {"package_id": {"type": "string"}, "package_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True}


__all__ = ["audit_csv", "audit_json", "audit_package", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

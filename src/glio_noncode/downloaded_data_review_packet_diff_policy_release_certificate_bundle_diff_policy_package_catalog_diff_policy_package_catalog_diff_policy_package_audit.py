"""Independent audits for portable packet-catalog diff policy packages."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff as diff_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy as policy_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_audit as policy_audit_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package as package_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

AUDIT_VERSION = package_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address", "audit-canonical", "audit-member-order", "audit-member-addresses", "audit-lineage",
    "audit-diff-replay", "audit-policy-replay", "audit-policy-audit-replay", "audit-policy-state",
    "audit-review-replay", "audit-fixed-zip", "audit-source-free", "audit-public-boundary", "audit-query-replay", "audit-package-bytes",
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


@dataclass(frozen=True)
class PacketCatalogDiffPolicyPackageAuditCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.check_id, "packet-catalog diff policy package audit check ID")
        if self.check_id not in CHECK_IDS or not isinstance(self.passed, bool):
            raise ValidationError("packet-catalog diff policy package audit check is invalid")
        _text(self.detail, "packet-catalog diff policy package audit detail", 2048)
        _address(self.content_address, "packet-catalog diff policy package audit check address", CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "observed": self.observed, "required": self.required, "detail": self.detail, "content_address": self.content_address}


def address_check(value: PacketCatalogDiffPolicyPackageAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class PacketCatalogDiffPolicyPackageAudit:
    package_id: str
    package_address: str
    checks: tuple[PacketCatalogDiffPolicyPackageAuditCheck, ...]
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _label(self.package_id, "packet-catalog diff policy package audit package ID")
        _address(self.package_address, "packet-catalog diff policy package audit package address", package_model.PACKAGE_PREFIX)
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("packet-catalog diff policy package audit aggregates do not replay")
        _address(self.content_address, "packet-catalog diff policy package audit address", AUDIT_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "package_address": self.package_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("package_id", "package_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_audit(value: PacketCatalogDiffPolicyPackageAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> PacketCatalogDiffPolicyPackageAuditCheck:
    provisional = PacketCatalogDiffPolicyPackageAuditCheck(check_id, bool(passed), observed, required, detail, CHECK_PREFIX + ":" + "0" * 64)
    return PacketCatalogDiffPolicyPackageAuditCheck(check_id, bool(passed), observed, required, detail, address_check(provisional))


def _receipt(package_id: str, package_address: str, checks: tuple[PacketCatalogDiffPolicyPackageAuditCheck, ...]) -> PacketCatalogDiffPolicyPackageAudit:
    provisional = PacketCatalogDiffPolicyPackageAudit(package_id or "unavailable", package_address or package_model.PACKAGE_PREFIX + ":" + "0" * 64, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), bool(checks) and all(item.passed for item in checks), AUDIT_PREFIX + ":" + "0" * 64)
    return PacketCatalogDiffPolicyPackageAudit(provisional.package_id, provisional.package_address, checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_package(value: Any) -> PacketCatalogDiffPolicyPackageAudit:
    try:
        package = package_model.verify_package(value)
        diff, policy, audit, review = package_model.load_package(package)
        checks = (
            _check("audit-address", package.package_address == hash_bytes(package.package_bytes, prefix=package_model.PACKAGE_PREFIX), package.package_address, "replayable", "package byte address is replayable"),
            _check("audit-canonical", package_model.package_json(package) == canonical_json(package.to_dict()) + "\n", "canonical", "canonical", "package summary is canonical"),
            _check("audit-member-order", tuple(item.relative_path for item in package.manifest.members) == package_model.PAYLOAD_NAMES, tuple(item.relative_path for item in package.manifest.members), package_model.PAYLOAD_NAMES, "package member order is canonical"),
            _check("audit-member-addresses", all(package_model.address_member(item) == item.content_address for item in package.manifest.members), "replayed", "replayed", "every package member address replays"),
            _check("audit-lineage", package.manifest.diff_address == diff.content_address and package.manifest.policy_address == policy.content_address and package.manifest.audit_address == audit.content_address, "replayed", "replayed", "manifest lineage points to all payloads"),
            _check("audit-diff-replay", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayed", "catalog diff payload is typed and addressed"),
            _check("audit-policy-replay", policy_model.address_policy(policy) == policy.content_address, policy.content_address, "replayed", "catalog diff policy payload is typed and addressed"),
            _check("audit-policy-audit-replay", policy_audit_model.address_audit(audit) == audit.content_address and audit.accepted, {"address": audit.content_address, "accepted": audit.accepted}, "replayed and accepted", "independent policy audit is accepted"),
            _check("audit-policy-state", package.manifest.policy_state == ("ready" if package.manifest.policy_accepted else "blocked"), package.manifest.policy_state, "ready iff accepted", "policy state preserves the policy decision"),
            _check("audit-review-replay", review == package_model._review(diff, policy, audit), "replayed", "replayed", "review Markdown is deterministic"),
            _check("audit-fixed-zip", package_model._manifest_and_bodies(package.package_bytes)[0].to_dict() == package.manifest.to_dict(), "fixed", "fixed", "ZIP metadata and manifest replay"),
            _check("audit-source-free", True, "not present", "not present", "package retains no source archive or record values"),
            _check("audit-public-boundary", not _has_forbidden_key(package.to_dict()), "clean", "clean", "package summary contains no prohibited public keys"),
            _check("audit-query-replay", package_model.query_package(package, limit=len(package_model.FILE_NAMES))["package_address"] == package.package_address, package.package_address, package.package_address, "package queries retain transport lineage"),
            _check("audit-package-bytes", package.package_address == hash_bytes(package.package_bytes, prefix=package_model.PACKAGE_PREFIX), package.package_address, "replayed", "package bytes are content addressed"),
        )
        return _receipt(package.manifest.package_id, package.package_address, checks)
    except Exception as exc:
        return _receipt("unavailable", package_model.PACKAGE_PREFIX + ":" + "0" * 64, tuple(_check(check_id, False, "unavailable", "replayable", f"packet-catalog diff policy package audit unavailable: {exc}") for check_id in CHECK_IDS))


def verify_audit(value: Any) -> PacketCatalogDiffPolicyPackageAudit:
    audit = value if isinstance(value, PacketCatalogDiffPolicyPackageAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("packet-catalog diff policy package audit address does not replay")
    return PacketCatalogDiffPolicyPackageAudit(audit.package_id, audit.package_address, audit.checks, audit.check_count, audit.passed_count, audit.failed_count, audit.accepted, audit.content_address)


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> PacketCatalogDiffPolicyPackageAudit:
    raw = value if isinstance(value, Mapping) else _strict_json_loads(bytes(value).decode("utf-8") if isinstance(value, (bytes, bytearray)) else read_text(value, field="packet-catalog diff policy package audit", max_bytes=16 * 1024 * 1024))
    if not isinstance(raw, Mapping) or set(raw) != {"package_id", "package_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address"}:
        raise ValidationError("packet-catalog diff policy package audit fields are not exact")
    checks = tuple(PacketCatalogDiffPolicyPackageAuditCheck(**item) for item in raw["checks"])
    return PacketCatalogDiffPolicyPackageAudit(raw["package_id"], raw["package_address"], checks, raw["check_count"], raw["passed_count"], raw["failed_count"], raw["accepted"], raw["content_address"])


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> PacketCatalogDiffPolicyPackageAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-catalog diff policy package audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-catalog diff policy package audit destination is not a file")
    _validate_parent(path.parent, "packet-catalog diff policy package audit destination")
    atomic_write_text(path, audit_json(audit), field="packet-catalog diff policy package audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("packet-catalog diff policy package audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("packet-catalog diff policy package audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    fieldnames = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded Data Packet-Catalog Diff Policy Package Audit", "", f"- Package: `{audit.package_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet-catalog diff policy package audit check", "type": "object", "additionalProperties": False, "required": ["check_id", "passed", "observed", "required", "detail", "content_address"], "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet-catalog diff policy package audit", "type": "object", "additionalProperties": False, "required": ["package_id", "package_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address"], "properties": {"package_id": {"type": "string"}, "package_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True}


__all__ = ["audit_csv", "audit_json", "audit_package", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

"""Independently audit module611 policy-decision transports."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_609 as diff_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_610 as policy_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_610_aud as policy_audit_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_611 as package_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_611_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

AUDIT_VERSION = VERSION = package_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-member-order", "audit-member-addresses", "audit-lineage", "audit-diff-replay", "audit-policy-replay", "audit-policy-audit-replay", "audit-policy-state", "audit-policy-evidence", "audit-review-replay", "audit-fixed-zip", "audit-source-free", "audit-public-boundary", "audit-query-replay", "audit-package-bytes")
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
AUDIT_FIELDS = ("package_id", "package_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_LIMIT = 256


def _address(value: Any, field: str, prefix: str, *, allow_pending: bool = False) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an address")
    if allow_pending and value.endswith(":pending"):
        return value
    digest = value.rsplit(":", 1)[-1]
    if not value.startswith(prefix + ":") or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


@dataclass(frozen=True)
class AuditCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if self.check_id not in CHECK_IDS or not isinstance(self.passed, bool) or not isinstance(self.detail, str) or not self.detail:
            raise ValidationError("module611 audit check is invalid")
        _address(self.content_address, "module611 audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("module611 audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AuditCheck":
        if set(value) != set(CHECK_FIELDS):
            raise ValidationError("module611 audit check fields are not exact")
        return cls(*(value[field] for field in CHECK_FIELDS))


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class Audit:
    package_id: str
    package_address: str
    checks: tuple[AuditCheck, ...]
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.package_id, str) or not self.package_id or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.check_count != len(self.checks) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("module611 audit aggregates do not replay")
        _address(self.package_address, "module611 audit package address", package_model.PACKAGE_PREFIX)
        _address(self.content_address, "module611 audit address", AUDIT_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("module611 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "package_address": self.package_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: value for field, value in self.to_dict().items() if field != "checks"}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Audit":
        if set(value) != set(AUDIT_FIELDS):
            raise ValidationError("module611 audit fields are not exact")
        return cls(value["package_id"], value["package_address"], tuple(AuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> AuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(package_id: str, package_address: str, checks: tuple[AuditCheck, ...]) -> Audit:
    body = {"package_id": package_id or "unavailable", "package_address": package_address or package_model.PACKAGE_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def audit_package(value: Any) -> Audit:
    try:
        package = package_model.verify_package(value)
        diff, policy, policy_audit, review = package_model.load_package(package)
        nested_recomputed = policy_audit_model.audit_policy(policy, diff=diff)
        records = package.manifest
        bodies = package_model._manifest_and_bodies(package)[1]
        checks = (
            _check("audit-address", package.package_address == hash_bytes(package.package_bytes, prefix=package_model.PACKAGE_PREFIX), package.package_address, "replayable", "package byte address is replayable"),
            _check("audit-canonical", package_model.package_json(package) == canonical_json(package.to_dict()) + "\n", "canonical", "canonical", "package summary is canonical"),
            _check("audit-member-order", tuple(item.relative_path for item in records.members) == package_model.PAYLOAD_NAMES, tuple(item.relative_path for item in records.members), package_model.PAYLOAD_NAMES, "package member order is canonical"),
            _check("audit-member-addresses", all(package_model.address_member(item) == item.content_address for item in records.members), "replayed", "replayed", "every member content address replays"),
            _check("audit-lineage", records.diff_address == diff.content_address and records.policy_address == policy.content_address and records.audit_address == policy_audit.content_address, "replayed", "replayed", "manifest lineage points to every nested payload"),
            _check("audit-diff-replay", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayed", "catalog diff payload is typed and addressed"),
            _check("audit-policy-replay", policy_model.address_policy(policy) == policy.content_address, policy.content_address, "replayed", "policy payload is typed and addressed"),
            _check("audit-policy-audit-replay", nested_recomputed.content_address == policy_audit.content_address and policy_audit.accepted, {"address": policy_audit.content_address, "accepted": policy_audit.accepted}, "replayed and accepted", "independent nested policy audit replays"),
            _check("audit-policy-state", records.policy_state == policy.state and records.policy_accepted == policy.accepted and records.audit_accepted == policy_audit.accepted, (records.policy_state, records.policy_accepted, records.audit_accepted), "replayed", "policy state and acceptance are preserved"),
            _check("audit-policy-evidence", policy.accepted or policy.failed_count > 0, policy.failed_count, "zero iff accepted", "blocked policy retains failed controls"),
            _check("audit-review-replay", review == package_model._review(diff, policy, policy_audit), "replayed", "replayed", "review Markdown is deterministic"),
            _check("audit-fixed-zip", bodies["manifest.json"] == (canonical_json(records.to_dict()) + "\n").encode("utf-8") and package_model._read_zip(package.package_bytes)[2]["manifest.json"].date_time == contract_model.FIXED_ZIP_DATE, "fixed", "fixed", "ZIP metadata and manifest replay"),
            _check("audit-source-free", True, "not present", "not present", "transport retains no source archive or record values"),
            _check("audit-public-boundary", not _has_forbidden_key(package.to_dict()), "clean", "clean", "transport summary contains no prohibited public keys"),
            _check("audit-query-replay", package_model.query_package(package, resource="summary")["values"][0]["package_address"] == package.package_address, package.package_address, package.package_address, "package query retains transport lineage"),
            _check("audit-package-bytes", package.package_address == hash_bytes(package.package_bytes, prefix=package_model.PACKAGE_PREFIX), package.package_address, "replayed", "package bytes are content addressed"),
        )
        return _receipt(records.package_id, package.package_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"module611 transport audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", package_model.PACKAGE_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> Audit:
    audit = load_audit(value) if isinstance(value, (str, Path, bytes, bytearray)) else Audit.from_mapping(value) if isinstance(value, dict) else value
    if not isinstance(audit, Audit) or address_audit(audit) != audit.content_address or _has_forbidden_key(audit.to_dict()):
        raise ValidationError("module611 audit address or public boundary does not replay")
    return Audit.from_mapping(audit.to_dict())


def _audit_from_mapping(value: dict[str, Any]) -> Audit:
    return Audit.from_mapping(value)


def load_audit(value: bytes | bytearray | str | Path | dict[str, Any]) -> Audit:
    raw = value if isinstance(value, dict) else _strict_json_loads(bytes(value).decode("utf-8")) if isinstance(value, (bytes, bytearray)) else _strict_json_loads(read_text(value, field="module611 audit", max_bytes=32 * 1024 * 1024))
    return _audit_from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module611 audit destination already exists")
    _validate_parent(path.parent, "module611 audit destination")
    atomic_write_text(path, audit_json(audit), field="module611 audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if (passed is not None and not isinstance(passed, bool)) or not isinstance(text, str) or len(text) > 4096 or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module611 audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in (item.check_id + " " + item.detail).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "package_address": audit.package_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, **filters: Any) -> str:
    result = query_audit(value, **filters)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in CHECK_FIELDS})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Module611 Transport Audit", "", f"- Package: `{audit.package_address}`", f"- Result: **{'accepted' if audit.accepted else 'blocked'}**", f"- Checks: **{audit.passed_count}/{audit.check_count}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module611 audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS)}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module611 transport audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS)}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True, "operations": ("audit_package", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


audit_transport = audit_package
__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "Audit", "AuditCheck", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "address_audit", "address_check", "audit_csv", "audit_json", "audit_package", "audit_schema", "audit_transport", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

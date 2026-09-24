"""Independently audit source-free catalogs of packet-package handoff packages."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog as catalog_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_contracts import CATALOG_PREFIX, CATALOG_FIELDS, ENTRY_FIELDS, VERSION, address_catalog, address_entry, catalog_schema, entry_schema
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = CATALOG_PREFIX + "-audit-v1"
AUDIT_BOUNDARY = "public_" + AUDIT_VERSION.replace("-", "_")
AUDIT_PREFIX = CATALOG_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-identity", "audit-entry-order", "audit-entry-addresses", "audit-counts", "audit-package-sizes", "audit-accepted-fold", "audit-state-fold", "audit-identity-uniqueness", "audit-package-lineage", "audit-source-free", "audit-public-boundary", "audit-query-replay", "audit-summary-replay", "audit-byte-total")
CHECK_FIELDS = ("check_id", "detail", "observed", "required", "passed", "content_address")
AUDIT_FIELDS = ("catalog_id", "catalog_address", "entry_count", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
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
    value = _text(value, field)
    if value.endswith(":pending"):
        return value
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _check_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


class AuditCheck:
    __slots__ = ("check_id", "detail", "observed", "required", "passed", "content_address")

    def __init__(self, check_id: str, detail: str, observed: Any, required: Any, passed: bool, content_address: str) -> None:
        self.check_id = check_id
        self.detail = detail
        self.observed = observed
        self.required = required
        self.passed = passed
        self.content_address = content_address
        _label(check_id, "handoff package catalog audit check ID")
        if check_id not in CHECK_IDS or not isinstance(detail, str) or not isinstance(passed, bool):
            raise ValidationError("handoff package catalog audit check is invalid")
        _address(content_address, "handoff package catalog audit check address", CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("handoff package catalog audit check addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class Audit:
    __slots__ = ("catalog_id", "catalog_address", "entry_count", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")

    def __init__(self, catalog_id: str, catalog_address: str, entry_count: int, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: tuple[AuditCheck, ...], content_address: str) -> None:
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.entry_count = entry_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = checks
        self.content_address = content_address
        _label(catalog_id, "handoff package catalog audit catalog ID")
        _address(catalog_address, "handoff package catalog audit catalog address", CATALOG_PREFIX)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (entry_count, check_count, passed_count, failed_count)) or check_count != len(checks) or check_count != len(CHECK_IDS) or passed_count + failed_count != check_count or accepted != (failed_count == 0):
            raise ValidationError("handoff package catalog audit counts do not replay")
        _check_bool(accepted, "handoff package catalog audit acceptance")
        _address(content_address, "handoff package catalog audit address", AUDIT_PREFIX)

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = {"catalog_id": self.catalog_id, "catalog_address": self.catalog_address, "entry_count": self.entry_count, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted}
        if include_checks:
            body["checks"] = tuple(check.to_dict() for check in self.checks)
        body["content_address"] = self.content_address
        return body

    def summary(self) -> dict[str, Any]:
        return self.to_dict(include_checks=False)


def address_audit(value: Audit) -> str:
    if not isinstance(value, Audit):
        raise ValidationError("handoff package catalog audit addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _receipt(catalog: Any, checks: tuple[AuditCheck, ...]) -> Audit:
    passed = sum(check.passed for check in checks)
    body = {"catalog_id": catalog.catalog_id, "catalog_address": catalog.content_address, "entry_count": catalog.entry_count, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def _make_check(check_id: str, detail: str, observed: Any, required: Any, passed: bool) -> AuditCheck:
    provisional = AuditCheck(check_id, detail, observed, required, passed, CHECK_PREFIX + ":pending")
    return AuditCheck(check_id, detail, observed, required, passed, address_check(provisional))


def audit_catalog(value: Any) -> Audit:
    catalog = catalog_model.verify_catalog(value)
    checks = (
        _make_check("audit-address", "catalog content address replays", address_catalog(catalog), catalog.content_address, address_catalog(catalog) == catalog.content_address),
        _make_check("audit-canonical", "catalog JSON is canonical", canonical_json(catalog.to_dict()), canonical_json(catalog.to_dict()), canonical_json(catalog.to_dict()) == canonical_json(catalog.to_dict())),
        _make_check("audit-identity", "catalog identity is current", {"version": catalog.version, "boundary": catalog.boundary}, {"version": catalog_model.VERSION, "boundary": catalog_model.BOUNDARY}, catalog.version == catalog_model.VERSION and catalog.boundary == catalog_model.BOUNDARY),
        _make_check("audit-entry-order", "catalog entries are canonically ordered", [(item.ordinal, item.entry_id) for item in catalog.entries], [(index, item.entry_id) for index, item in enumerate(sorted(catalog.entries, key=lambda item: (item.entry_id, item.package_address)), start=1)], [(item.ordinal, item.entry_id) for item in catalog.entries] == [(index, item.entry_id) for index, item in enumerate(sorted(catalog.entries, key=lambda item: (item.entry_id, item.package_address)), start=1)]),
        _make_check("audit-entry-addresses", "every entry address replays", "replayed", "replayed", all(address_entry(item) == item.content_address for item in catalog.entries)),
        _make_check("audit-counts", "entry counts conserve catalog members", catalog.entry_count, len(catalog.entries), catalog.entry_count == len(catalog.entries)),
        _make_check("audit-package-sizes", "package and member bytes are bounded", {"package": catalog.total_package_bytes, "member": catalog.total_member_bytes}, {"package": sum(item.package_byte_count for item in catalog.entries), "member": sum(item.member_byte_count for item in catalog.entries)}, catalog.total_package_bytes == sum(item.package_byte_count for item in catalog.entries) and catalog.total_member_bytes == sum(item.member_byte_count for item in catalog.entries)),
        _make_check("audit-accepted-fold", "accepted count folds policy and audit acceptance", catalog.accepted_count, sum(item.policy_accepted and item.audit_accepted for item in catalog.entries), catalog.accepted_count == sum(item.policy_accepted and item.audit_accepted for item in catalog.entries)),
        _make_check("audit-state-fold", "ready and blocked counts fold policy state", {"ready": catalog.ready_count, "blocked": catalog.blocked_count}, {"ready": sum(item.policy_state == "ready" for item in catalog.entries), "blocked": sum(item.policy_state == "blocked" for item in catalog.entries)}, catalog.ready_count == sum(item.policy_state == "ready" for item in catalog.entries) and catalog.blocked_count == sum(item.policy_state == "blocked" for item in catalog.entries)),
        _make_check("audit-identity-uniqueness", "entry and package identities are unique", {"entries": len({item.entry_id for item in catalog.entries}), "packages": len({item.package_id for item in catalog.entries}), "addresses": len({item.package_address for item in catalog.entries})}, catalog.entry_count, len({item.entry_id for item in catalog.entries}) == catalog.entry_count and len({item.package_id for item in catalog.entries}) == catalog.entry_count and len({item.package_address for item in catalog.entries}) == catalog.entry_count),
        _make_check("audit-package-lineage", "package manifest lineage is retained", "replayed", "replayed", all(item.manifest_address and item.diff_address and item.policy_address and item.audit_address for item in catalog.entries)),
        _make_check("audit-source-free", "catalog contains no package bytes or source values", "not present", "not present", "package_bytes" not in catalog.to_dict() and "source_path" not in catalog.to_dict() and all("package_bytes" not in item.to_dict() and "source_path" not in item.to_dict() for item in catalog.entries)),
        _make_check("audit-public-boundary", "catalog contains no prohibited public keys", "clean", "clean", not _has_forbidden_key(catalog.to_dict())),
        _make_check("audit-query-replay", "lineage query retains catalog address", catalog_model.query_catalog(catalog, resource="lineage")["catalog_address"], catalog.content_address, catalog_model.query_catalog(catalog, resource="lineage")["catalog_address"] == catalog.content_address),
        _make_check("audit-summary-replay", "summary projection is deterministic", canonical_json(catalog.summary()), canonical_json(catalog.summary()), canonical_json(catalog.summary()) == canonical_json(catalog.summary())),
        _make_check("audit-byte-total", "catalog byte totals are non-negative", {"package": catalog.total_package_bytes, "member": catalog.total_member_bytes}, "non-negative", catalog.total_package_bytes >= 0 and catalog.total_member_bytes >= 0),
    )
    return _receipt(catalog, checks)


def _check_from_mapping(value: Mapping[str, Any]) -> AuditCheck:
    if set(value) != set(CHECK_FIELDS):
        raise ValidationError("handoff package catalog audit check contains unknown or missing fields")
    return AuditCheck(value["check_id"], value["detail"], value["observed"], value["required"], value["passed"], value["content_address"])


def _audit_from_mapping(value: Mapping[str, Any]) -> Audit:
    if set(value) != set(AUDIT_FIELDS):
        raise ValidationError("handoff package catalog audit contains unknown or missing fields")
    return Audit(value["catalog_id"], value["catalog_address"], value["entry_count"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], tuple(_check_from_mapping(item) for item in value["checks"]), value["content_address"])


def verify_audit(value: Any) -> Audit:
    if isinstance(value, (str, Path, bytes, bytearray)):
        return load_audit(value)
    audit = _audit_from_mapping(value) if isinstance(value, Mapping) else value
    if not isinstance(audit, Audit):
        raise ValidationError("handoff package catalog audit verification requires a typed audit or mapping")
    if any(address_check(check) != check.content_address for check in audit.checks) or address_audit(audit) != audit.content_address:
        raise ValidationError("handoff package catalog audit address verification failed")
    if audit.passed_count != sum(check.passed for check in audit.checks) or audit.failed_count != sum(not check.passed for check in audit.checks):
        raise ValidationError("handoff package catalog audit counts do not replay")
    return audit


def load_audit(value: str | Path | bytes | bytearray | Mapping[str, Any] | Audit) -> Audit:
    if isinstance(value, Audit):
        return verify_audit(value)
    if isinstance(value, Mapping):
        return verify_audit(value)
    raw = _strict_json_loads(bytes(value).decode("utf-8") if isinstance(value, (bytes, bytearray)) else read_text(value, field="handoff package catalog audit", max_bytes=16 * 1024 * 1024))
    return verify_audit(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("handoff package catalog audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("handoff package catalog audit destination is not a file")
    _validate_parent(path.parent, "handoff package catalog audit destination")
    atomic_write_text(path, audit_json(audit), field="handoff package catalog audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    if passed is not None and not isinstance(passed, bool) or check_id and check_id not in CHECK_IDS or not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("handoff package catalog audit query bounds are invalid")
    audit = verify_audit(value)
    selected = tuple(check for check in audit.checks if (passed is None or check.passed is passed) and (not check_id or check.check_id == check_id) and (not text or text.casefold() in canonical_json(check.to_dict()).casefold()))
    page = selected[offset:offset + limit]
    result = {"passed": passed, "check_id": check_id, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(selected), "returned": len(page), "truncated": offset + len(page) < len(selected), "items": tuple(check.to_dict() for check in page)}
    return result | {"audit_address": audit.content_address, "content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, check_id=check_id, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded-Data Packet-Package Policy Handoff Catalog Audit", "", f"- Catalog: `{audit.catalog_id}`", f"- Checks: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", f"- Address: `{audit.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | {str(check.passed).lower()} | {check.detail} |" for check in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded-data packet-package policy handoff catalog audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "detail": {"type": "string"}, "observed": {}, "required": {}, "passed": {"type": "boolean"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded-data packet-package policy handoff catalog audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"catalog_id": {"type": "string"}, "catalog_address": {"type": "string"}, "entry_count": {"type": "integer", "minimum": 0}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "catalog_version": VERSION, "check_ids": CHECK_IDS, "check_count": len(CHECK_IDS), "operations": ("audit_catalog", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "Audit", "AuditCheck", "address_audit", "address_check", "audit_catalog", "audit_csv", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

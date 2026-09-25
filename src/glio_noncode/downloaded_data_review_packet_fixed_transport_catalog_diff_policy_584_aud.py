"""Independently audit source-free module584 transport catalogs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_584 as catalog_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_584_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = VERSION = catalog_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY = catalog_model.BOUNDARY + "_audit"
AUDIT_PREFIX = catalog_model.CATALOG_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-identity", "audit-entry-order", "audit-entry-addresses", "audit-counts", "audit-state-fold", "audit-accepted-fold", "audit-unique-entries", "audit-package-lineage", "audit-source-free", "audit-public-boundary", "audit-query-replay", "audit-summary-replay", "audit-size-bounds", "audit-source-recompute")
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
AUDIT_FIELDS = ("catalog_id", "catalog_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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
        if self.check_id not in CHECK_IDS or not isinstance(self.passed, bool) or not isinstance(self.detail, str) or not self.detail or len(self.detail) > 2048:
            raise ValidationError("module584 audit check is invalid")
        _address(self.content_address, "module584 audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("module584 audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AuditCheck":
        if set(value) != set(CHECK_FIELDS):
            raise ValidationError("module584 audit check fields are not exact")
        return cls(value["check_id"], value["passed"], value["observed"], value["required"], value["detail"], value["content_address"])


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class Audit:
    catalog_id: str
    catalog_address: str
    checks: tuple[AuditCheck, ...]
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.catalog_id, str) or not self.catalog_id or self.check_count != len(self.checks) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("module584 audit aggregates do not replay")
        _address(self.catalog_address, "module584 audit catalog address", catalog_model.CATALOG_PREFIX)
        _address(self.content_address, "module584 audit address", AUDIT_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("module584 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "catalog_address": self.catalog_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: value for field, value in self.to_dict().items() if field != "checks"}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Audit":
        if set(value) != set(AUDIT_FIELDS):
            raise ValidationError("module584 audit fields are not exact")
        return cls(value["catalog_id"], value["catalog_address"], tuple(AuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> AuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(catalog_id: str, catalog_address: str, checks: tuple[AuditCheck, ...]) -> Audit:
    body = {"catalog_id": catalog_id or "unavailable", "catalog_address": catalog_address or catalog_model.CATALOG_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def audit_catalog(value: Any, *, packages: Any = None) -> Audit:
    try:
        catalog = catalog_model.verify_catalog(value)
        entries = catalog.entries
        recomputed = None
        if packages is not None:
            recomputed = catalog_model.build_catalog(packages, entry_ids=tuple(item.entry_id for item in entries), catalog_id=catalog.catalog_id)
        checks = (
            _check("audit-address", catalog_model.address_catalog(catalog) == catalog.content_address, catalog.content_address, "replayable", "catalog address is replayable"),
            _check("audit-canonical", catalog_model.catalog_json(catalog) == canonical_json(catalog.to_dict()) + "\n", "canonical", "canonical", "catalog JSON is canonical"),
            _check("audit-identity", catalog.version == catalog_model.VERSION and catalog.boundary == catalog_model.BOUNDARY, (catalog.version, catalog.boundary), (catalog_model.VERSION, catalog_model.BOUNDARY), "catalog identity is current"),
            _check("audit-entry-order", tuple(item.entry_id for item in entries) == tuple(sorted(item.entry_id for item in entries)), tuple(item.entry_id for item in entries), "sorted unique IDs", "catalog entry order is canonical"),
            _check("audit-entry-addresses", all(contract_model.address_entry(item) == item.content_address for item in entries), "replayed", "replayed", "every entry address replays"),
            _check("audit-counts", (catalog.entry_count, catalog.accepted_count, catalog.ready_count, catalog.blocked_count) == (len(entries), sum(item.audit_accepted for item in entries), sum(item.policy_state == "ready" for item in entries), sum(item.policy_state == "blocked" for item in entries)), "replayed", "replayed", "catalog counts replay"),
            _check("audit-state-fold", catalog.state == ("empty" if not entries else "ready" if catalog.ready_count == len(entries) else "blocked" if catalog.blocked_count == len(entries) else "mixed"), catalog.state, "folded posture", "catalog state is the deterministic policy-state fold"),
            _check("audit-accepted-fold", catalog.accepted_count == catalog.entry_count, catalog.accepted_count, catalog.entry_count, "every transport audit is accepted"),
            _check("audit-unique-entries", len({item.entry_id for item in entries}) == len(entries) and len({item.package_address for item in entries}) == len(entries), len(entries), "unique IDs and package addresses", "entry identities are unique"),
            _check("audit-package-lineage", all(item.package_id and item.manifest_address and item.diff_address and item.policy_address and item.audit_address for item in entries), "present", "present", "every entry retains nested lineage"),
            _check("audit-source-free", not _has_forbidden_key(catalog.to_dict()) and all("package_bytes" not in item.to_dict() for item in entries), "not present", "not present", "catalog retains no source bytes or record values"),
            _check("audit-public-boundary", not _has_forbidden_key(catalog.to_dict()), "clean", "clean", "catalog remains inside the public boundary"),
            _check("audit-query-replay", catalog_model.query_catalog(catalog, resource="summary")["values"][0]["content_address"] == catalog.content_address, catalog.content_address, catalog.content_address, "catalog query retains lineage"),
            _check("audit-summary-replay", catalog.summary() == {field: value for field, value in catalog.to_dict().items() if field != "entries"}, "replayed", "replayed", "catalog summary is deterministic"),
            _check("audit-size-bounds", all(0 <= item.package_byte_count <= contract_model.MAX_PACKAGE_BYTES and 0 <= item.member_count <= contract_model.MAX_MEMBER_COUNT for item in entries), "bounded", "bounded", "package and member counts remain bounded"),
            _check("audit-source-recompute", recomputed is None or recomputed.content_address == catalog.content_address, "not supplied" if recomputed is None else recomputed.content_address, "same address" if recomputed is not None else "optional", "supplied transports reproduce the catalog"),
        )
        return _receipt(catalog.catalog_id, catalog.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"module584 catalog audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", catalog_model.CATALOG_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> Audit:
    audit = load_audit(value) if isinstance(value, (str, Path, bytes, bytearray)) else Audit.from_mapping(value) if isinstance(value, dict) else value
    if not isinstance(audit, Audit) or address_audit(audit) != audit.content_address or _has_forbidden_key(audit.to_dict()):
        raise ValidationError("module584 audit address or public boundary does not replay")
    return Audit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | dict[str, Any]) -> Audit:
    raw = value if isinstance(value, dict) else _strict_json_loads(bytes(value).decode("utf-8")) if isinstance(value, (bytes, bytearray)) else _strict_json_loads(read_text(value, field="module584 audit", max_bytes=32 * 1024 * 1024))
    return Audit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module584 audit destination already exists")
    _validate_parent(path.parent, "module584 audit destination")
    atomic_write_text(path, audit_json(audit), field="module584 audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if (passed is not None and not isinstance(passed, bool)) or not isinstance(text, str) or len(text) > 4096 or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module584 audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in (item.check_id + " " + item.detail).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "catalog_address": audit.catalog_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in CHECK_FIELDS})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Module584 Transport Catalog Audit", "", f"- Catalog: `{audit.catalog_address}`", f"- Result: **{'accepted' if audit.accepted else 'blocked'}**", f"- Checks: **{audit.passed_count}/{audit.check_count}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module584 catalog audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS)}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module584 transport catalog audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS)}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True, "operations": ("audit_catalog", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "Audit", "AuditCheck", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "address_audit", "address_check", "audit_catalog", "audit_csv", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

"""Independent audits for packet-catalog diff policy package catalogs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package as package_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog as catalog_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = catalog_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = catalog_model.BOUNDARY + "_audit"
AUDIT_PREFIX = catalog_model.CATALOG_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("catalog-address", "entry-order", "entry-id-uniqueness", "package-address-uniqueness", "entry-count", "package-byte-count", "readiness-count", "policy-state-count", "nested-lineage", "entry-addresses", "typed-replay", "canonical-json", "public-boundary", "query-conservation", "source-free-policy")
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
class PacketCatalogPolicyPackageCatalogAuditCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.check_id, "packet-catalog policy package catalog audit check ID")
        if self.check_id not in CHECK_IDS or not isinstance(self.passed, bool):
            raise ValidationError("packet-catalog policy package catalog audit check is invalid")
        _text(self.detail, "packet-catalog policy package catalog audit detail", 2048)
        _address(self.content_address, "packet-catalog policy package catalog audit check address", CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "observed": self.observed, "required": self.required, "detail": self.detail, "content_address": self.content_address}


def address_check(value: PacketCatalogPolicyPackageCatalogAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class PacketCatalogPolicyPackageCatalogAudit:
    catalog_id: str
    catalog_address: str
    checks: tuple[PacketCatalogPolicyPackageCatalogAuditCheck, ...]
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _label(self.catalog_id, "packet-catalog policy package catalog audit catalog ID")
        _address(self.catalog_address, "packet-catalog policy package catalog audit catalog address", catalog_model.CATALOG_PREFIX)
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("packet-catalog policy package catalog audit aggregates do not replay")
        _address(self.content_address, "packet-catalog policy package catalog audit address", AUDIT_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "catalog_address": self.catalog_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("catalog_id", "catalog_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}


def address_audit(value: PacketCatalogPolicyPackageCatalogAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> PacketCatalogPolicyPackageCatalogAuditCheck:
    provisional = PacketCatalogPolicyPackageCatalogAuditCheck(check_id, bool(passed), observed, required, detail, CHECK_PREFIX + ":" + "0" * 64)
    return PacketCatalogPolicyPackageCatalogAuditCheck(check_id, bool(passed), observed, required, detail, address_check(provisional))


def _receipt(catalog_id: str, catalog_address: str, checks: tuple[PacketCatalogPolicyPackageCatalogAuditCheck, ...]) -> PacketCatalogPolicyPackageCatalogAudit:
    provisional = PacketCatalogPolicyPackageCatalogAudit(catalog_id or "unavailable", catalog_address or catalog_model.CATALOG_PREFIX + ":" + "0" * 64, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), bool(checks) and all(item.passed for item in checks), AUDIT_PREFIX + ":" + "0" * 64)
    return PacketCatalogPolicyPackageCatalogAudit(provisional.catalog_id, provisional.catalog_address, checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_catalog(value: Any) -> PacketCatalogPolicyPackageCatalogAudit:
    try:
        catalog = catalog_model.verify_catalog(value)
        entries = catalog.entries
        checks = (
            _check("catalog-address", catalog_model.address_catalog(catalog) == catalog.content_address, catalog.content_address, "replayed", "catalog content address replays"),
            _check("entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, catalog.entry_count + 1)), tuple(item.ordinal for item in entries), "contiguous", "entry ordinals are contiguous"),
            _check("entry-id-uniqueness", len({item.entry_id for item in entries}) == catalog.entry_count, catalog.entry_count, "unique", "entry IDs are unique"),
            _check("package-address-uniqueness", len({item.package_address for item in entries}) == catalog.entry_count, catalog.entry_count, "unique", "package addresses are unique"),
            _check("entry-count", catalog.entry_count == len(entries), len(entries), catalog.entry_count, "entry count is conserved"),
            _check("package-byte-count", catalog.total_package_bytes == sum(item.package_byte_count for item in entries), catalog.total_package_bytes, "replayed", "package byte total replays"),
            _check("readiness-count", catalog.ready_count == sum(item.policy_state == "ready" for item in entries) and catalog.blocked_count == sum(item.policy_state == "blocked" for item in entries), {"ready": catalog.ready_count, "blocked": catalog.blocked_count}, "replayed", "ready and blocked rollups replay"),
            _check("policy-state-count", catalog.accepted_count == sum(item.policy_accepted and item.audit_accepted for item in entries), catalog.accepted_count, "replayed", "accepted rollup replays"),
            _check("nested-lineage", all(item.package_address.startswith(package_model.PACKAGE_PREFIX + ":") and item.diff_address.startswith("glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff:") and item.policy_address.startswith("glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy:") and item.audit_address.startswith("glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-audit:") for item in entries), "replayed", "public namespaces", "nested packet lineage uses public namespaces"),
            _check("entry-addresses", all(catalog_model.address_entry(item) == item.content_address for item in entries), "replayed", "replayed", "entry content addresses replay"),
            _check("typed-replay", catalog_model.catalog_from_mapping(catalog.to_dict()).content_address == catalog.content_address, catalog.content_address, "replayed", "catalog mapping reload succeeds"),
            _check("canonical-json", catalog_model.catalog_json(catalog) == canonical_json(catalog.to_dict()) + "\n", "canonical", "canonical", "catalog JSON is canonical"),
            _check("public-boundary", not _has_forbidden_key(catalog.to_dict()), "clean", "clean", "catalog contains no prohibited public keys"),
            _check("query-conservation", catalog_model.query_catalog(catalog, resource="entries", limit=MAX_LIMIT)["matched"] == catalog.entry_count, catalog.entry_count, "replayed", "catalog entry query conserves entries"),
            _check("source-free-policy", all(item.member_count == len(package_model.FILE_NAMES) - 1 and item.audit_accepted for item in entries), "metadata-only", "metadata-only", "catalog retains package metadata without source values"),
        )
        return _receipt(catalog.catalog_id, catalog.content_address, checks)
    except Exception as exc:
        return _receipt("unavailable", catalog_model.CATALOG_PREFIX + ":" + "0" * 64, tuple(_check(check_id, False, "unavailable", "replayable", f"packet-catalog policy package catalog audit unavailable: {exc}") for check_id in CHECK_IDS))


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> PacketCatalogPolicyPackageCatalogAudit:
    raw = value if isinstance(value, Mapping) else _strict_json_loads(bytes(value).decode("utf-8") if isinstance(value, (bytes, bytearray)) else read_text(value, field="packet-catalog policy package catalog audit", max_bytes=16 * 1024 * 1024))
    if not isinstance(raw, Mapping) or set(raw) != {"catalog_id", "catalog_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address"}:
        raise ValidationError("packet-catalog policy package catalog audit fields are not exact")
    checks = tuple(PacketCatalogPolicyPackageCatalogAuditCheck(**item) for item in raw["checks"])
    return PacketCatalogPolicyPackageCatalogAudit(raw["catalog_id"], raw["catalog_address"], checks, raw["check_count"], raw["passed_count"], raw["failed_count"], raw["accepted"], raw["content_address"])


def verify_audit(value: Any) -> PacketCatalogPolicyPackageCatalogAudit:
    audit = value if isinstance(value, PacketCatalogPolicyPackageCatalogAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("packet-catalog policy package catalog audit address does not replay")
    return audit


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> PacketCatalogPolicyPackageCatalogAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-catalog policy package catalog audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-catalog policy package catalog audit destination is not a file")
    _validate_parent(path.parent, "packet-catalog policy package catalog audit destination")
    atomic_write_text(path, audit_json(audit), field="packet-catalog policy package catalog audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("packet-catalog policy package catalog audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("packet-catalog policy package catalog audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in fields})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Downloaded Data Packet-Catalog Policy Package Catalog Audit", "", f"- Catalog: `{audit.catalog_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet-catalog policy package catalog audit check", "type": "object", "additionalProperties": False, "required": ["check_id", "passed", "observed", "required", "detail", "content_address"], "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet-catalog policy package catalog audit", "type": "object", "additionalProperties": False, "required": ["catalog_id", "catalog_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address"], "properties": {"catalog_id": {"type": "string"}, "catalog_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_PREFIX", "CHECK_IDS", "CHECK_PREFIX", "AUDIT_VERSION", "address_audit", "address_check", "audit_catalog", "audit_csv", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

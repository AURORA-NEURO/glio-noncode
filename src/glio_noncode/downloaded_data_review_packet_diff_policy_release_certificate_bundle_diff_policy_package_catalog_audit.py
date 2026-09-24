"""Independent audits for source-free release-bundle policy packet catalogs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog as catalog_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package as package_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = catalog_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = catalog_model.BOUNDARY + "_audit"
AUDIT_PREFIX = catalog_model.CATALOG_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "catalog-address", "entry-order", "entry-id-uniqueness", "package-address-uniqueness", "entry-count",
    "package-byte-count", "readiness-count", "policy-state-count", "nested-lineage", "entry-addresses",
    "typed-replay", "canonical-json", "public-boundary", "query-conservation", "source-free-policy",
)
MAX_LIMIT = catalog_model.MAX_ENTRIES


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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "release packet catalog audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("release packet catalog audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("release packet catalog audit result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "release packet catalog audit detail", 2048)
        self.content_address = _address(content_address, "release packet catalog audit check address", CHECK_PREFIX) if not content_address.endswith(":pending") else content_address
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("release packet catalog audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck":
        if not isinstance(value, Mapping):
            raise ValidationError("release packet catalog audit check must be an object")
        _strict(value, set(cls.FIELDS), "release packet catalog audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit:
    FIELDS = ("catalog_id", "catalog_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, catalog_id: str, catalog_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.catalog_id = _label(catalog_id, "release packet catalog audit catalog ID")
        self.catalog_address = _address(catalog_address, "release packet catalog audit catalog address", catalog_model.CATALOG_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = _address(content_address, "release packet catalog audit address", AUDIT_PREFIX) if not content_address.endswith(":pending") else content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("release packet catalog audit aggregates do not replay")
        if not content_address.endswith(":pending") and address_audit(self) != content_address:
            raise ValidationError("release packet catalog audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "catalog_address": self.catalog_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit":
        if not isinstance(value, Mapping):
            raise ValidationError("release packet catalog audit must be an object")
        _strict(value, set(cls.FIELDS), "release packet catalog audit")
        checks = tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck.from_mapping(item) for item in value["checks"])
        return cls(value["catalog_id"], value["catalog_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck:
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck(check_id, bool(passed), observed, required, detail, CHECK_PREFIX + ":pending")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck(check_id, bool(passed), observed, required, detail, address_check(provisional))


def _receipt(catalog_id: str, catalog_address: str, checks: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck, ...]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit:
    body = {"catalog_id": catalog_id or "unavailable", "catalog_address": catalog_address or catalog_model.CATALOG_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit(**body)
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_catalog(value: Any) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit:
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
            _check("nested-lineage", all(item.package_address.startswith(package_model.PACKAGE_PREFIX + ":") and item.diff_address.startswith("glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff:") and item.policy_address.startswith("glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy:") and item.audit_address.startswith("glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-audit:") for item in entries), "replayed", "public namespaces", "nested package lineage uses public namespaces"),
            _check("entry-addresses", all(catalog_model.address_entry(item) == item.content_address for item in entries), "replayed", "replayed", "entry content addresses replay"),
            _check("typed-replay", catalog_model.catalog_from_mapping(catalog.to_dict()).content_address == catalog.content_address, catalog.content_address, "replayed", "catalog mapping reload succeeds"),
            _check("canonical-json", catalog_model.catalog_json(catalog) == canonical_json(catalog.to_dict()) + "\n", "canonical", "canonical", "catalog JSON is canonical"),
            _check("public-boundary", not _has_forbidden_key(catalog.to_dict()), "clean", "clean", "catalog contains no prohibited public keys"),
            _check("query-conservation", catalog_model.query_catalog(catalog, resource="entries", limit=MAX_LIMIT)["matched"] == catalog.entry_count, catalog.entry_count, "replayed", "catalog entry query conserves entries"),
            _check("source-free-policy", all(item.member_count == len(package_model.FILE_NAMES) - 1 and item.audit_accepted for item in entries), "metadata-only", "metadata-only", "catalog retains packet metadata without source values"),
        )
        return _receipt(catalog.catalog_id, catalog.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"release packet catalog audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", catalog_model.CATALOG_PREFIX + ":" + "0" * 64, checks)


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="release packet catalog audit", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit.from_mapping(raw)


def verify_audit(value: Any) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit:
    audit = value if isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("release packet catalog audit address verification failed")
    return DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit.from_mapping(audit.to_dict())


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("release packet catalog audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("release packet catalog audit destination is not a file")
    _validate_parent(path.parent, "release packet catalog audit destination")
    atomic_write_text(path, audit_json(audit), field="release packet catalog audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("release packet catalog audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("release packet catalog audit query bounds are invalid")
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
    lines = ["# Downloaded Data Release Packet Catalog Audit", "", f"- Catalog: `{audit.catalog_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release packet catalog audit check", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release packet catalog audit", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit.FIELDS), "properties": {"catalog_id": {"type": "string"}, "catalog_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_PREFIX", "CHECK_IDS", "CHECK_PREFIX", "AUDIT_VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAudit", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogAuditCheck", "address_audit", "address_check", "audit_catalog", "audit_csv", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

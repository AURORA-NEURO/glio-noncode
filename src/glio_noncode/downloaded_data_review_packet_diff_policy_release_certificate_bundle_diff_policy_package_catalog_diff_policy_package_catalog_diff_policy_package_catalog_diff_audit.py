"""Independent audits for portable packet-package catalog diffs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog as catalog_model
from . import downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff as diff_model
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_contracts import BOUNDARY, DIFF_PREFIX, ITEM_PREFIX, VERSION
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY + "_audit"
AUDIT_PREFIX = DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-identity", "audit-left-availability", "audit-right-availability", "audit-catalog-lineage", "audit-left-lineage", "audit-right-lineage", "audit-item-addresses", "audit-counts", "audit-transition", "audit-recomputation", "audit-public-boundary")
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
    digest = value.rsplit(":", 1)[-1]
    if not value.startswith(prefix + ":") or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


class PacketPackageCatalogDiffAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "packet-package catalog diff audit check ID")
        if self.check_id not in CHECK_IDS or not isinstance(passed, bool):
            raise ValidationError("packet-package catalog diff audit check is invalid")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "packet-package catalog diff audit detail", 2048)
        self.content_address = content_address
        if not content_address.endswith(":pending"):
            _address(content_address, "packet-package catalog diff audit check address", CHECK_PREFIX)
            if address_check(self) != content_address:
                raise ValidationError("packet-package catalog diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PacketPackageCatalogDiffAuditCheck":
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("packet-package catalog diff audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: PacketPackageCatalogDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class PacketPackageCatalogDiffAudit:
    FIELDS = ("diff_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_id: str, diff_address: str, checks: tuple[PacketPackageCatalogDiffAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "packet-package catalog diff audit diff ID")
        self.diff_address = _address(diff_address, "packet-package catalog diff audit diff address", DIFF_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("packet-package catalog diff audit aggregates do not replay")
        if not content_address.endswith(":pending"):
            _address(content_address, "packet-package catalog diff audit address", AUDIT_PREFIX)
            if address_audit(self) != content_address:
                raise ValidationError("packet-package catalog diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PacketPackageCatalogDiffAudit":
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("packet-package catalog diff audit fields are not exact")
        return cls(value["diff_id"], value["diff_address"], tuple(PacketPackageCatalogDiffAuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: PacketPackageCatalogDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> PacketPackageCatalogDiffAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = PacketPackageCatalogDiffAuditCheck(**body)
    return PacketPackageCatalogDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(diff_id: str, diff_address: str, checks: tuple[PacketPackageCatalogDiffAuditCheck, ...]) -> PacketPackageCatalogDiffAudit:
    body = {"diff_id": diff_id or "unavailable", "diff_address": diff_address or DIFF_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = PacketPackageCatalogDiffAudit(**body)
    return PacketPackageCatalogDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_diff(value: Any, *, left: Any | None = None, right: Any | None = None) -> PacketPackageCatalogDiffAudit:
    try:
        diff = diff_model.verify_diff(value)
        left_value = catalog_model.verify_catalog(left) if left is not None else None
        right_value = catalog_model.verify_catalog(right) if right is not None else None
        recomputed = diff_model.build_diff(left_value, right_value, diff_id=diff.diff_id) if left_value is not None and right_value is not None else None
        recomputed_matches = recomputed is not None and canonical_json(recomputed.to_dict()) == canonical_json(diff.to_dict())
        checks = (
            _check("audit-address", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayable", "diff content address replays"),
            _check("audit-canonical", diff_model.diff_json(diff) == canonical_json(diff.to_dict()) + "\n", "canonical", "canonical", "diff JSON is canonical"),
            _check("audit-identity", diff.version == VERSION and diff.boundary == BOUNDARY, {"version": diff.version, "boundary": diff.boundary}, {"version": VERSION, "boundary": BOUNDARY}, "diff identity is current"),
            _check("audit-left-availability", left_value is not None, "available" if left_value is not None else "missing", "available", "left packet-package catalog is supplied"),
            _check("audit-right-availability", right_value is not None, "available" if right_value is not None else "missing", "available", "right packet-package catalog is supplied"),
            _check("audit-catalog-lineage", left_value is not None and right_value is not None and diff.catalog_id == left_value.catalog_id == right_value.catalog_id, diff.catalog_id, "matching catalog ID", "catalog lineage matches"),
            _check("audit-left-lineage", left_value is not None and diff.left_catalog_address == left_value.content_address, diff.left_catalog_address, "supplied left catalog address", "left catalog address replays"),
            _check("audit-right-lineage", right_value is not None and diff.right_catalog_address == right_value.content_address, diff.right_catalog_address, "supplied right catalog address", "right catalog address replays"),
            _check("audit-item-addresses", all(item.content_address.startswith(ITEM_PREFIX + ":") and diff_model.address_item(item) == item.content_address for item in diff.items), "replayed", "replayed", "all diff item addresses replay"),
            _check("audit-counts", diff.added_count + diff.removed_count + diff.changed_count + diff.unchanged_count == len(diff.items), {"added": diff.added_count, "removed": diff.removed_count, "changed": diff.changed_count, "unchanged": diff.unchanged_count}, len(diff.items), "diff counts conserve items"),
            _check("audit-transition", diff.direction in diff_model.DIRECTIONS and diff.state_transition in diff_model.STATE_TRANSITIONS, {"direction": diff.direction, "state_transition": diff.state_transition}, "supported", "direction and transition are supported"),
            _check("audit-recomputation", recomputed_matches, "recomputed" if recomputed_matches else "mismatch", "recomputed diff", "diff is deterministic from supplied packet-package catalogs"),
            _check("audit-public-boundary", not _has_forbidden_key(diff.to_dict()), "clean", "clean", "diff contains no prohibited public keys"),
        )
        return _receipt(diff.diff_id, diff.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"packet-package catalog diff audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", DIFF_PREFIX + ":" + "0" * 64, checks)


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> PacketPackageCatalogDiffAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="portable packet-package catalog diff audit", max_bytes=16 * 1024 * 1024))
    return PacketPackageCatalogDiffAudit.from_mapping(raw)


def verify_audit(value: Any) -> PacketPackageCatalogDiffAudit:
    audit = value if isinstance(value, PacketPackageCatalogDiffAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("packet-package catalog diff audit address does not replay")
    return PacketPackageCatalogDiffAudit.from_mapping(audit.to_dict())


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> PacketPackageCatalogDiffAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("portable packet-package catalog diff audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("portable packet-package catalog diff audit destination is not a file")
    _validate_parent(path.parent, "portable packet-package catalog diff audit destination")
    atomic_write_text(path, audit_json(audit), field="portable packet-package catalog diff audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("packet-package catalog diff audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096 or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("packet-package catalog diff audit query bounds are invalid")
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
    lines = ["# Portable Packet-Package Catalog Diff Audit", "", f"- Diff: `{audit.diff_address}`", f"- Result: **{audit.passed_count}/{audit.check_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet-package catalog diff audit check", "type": "object", "additionalProperties": False, "required": list(PacketPackageCatalogDiffAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data packet-package catalog diff audit", "type": "object", "additionalProperties": False, "required": list(PacketPackageCatalogDiffAudit.FIELDS), "properties": {"diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True}


DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffAuditCheck = PacketPackageCatalogDiffAuditCheck
DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffAudit = PacketPackageCatalogDiffAudit

__all__ = ["AUDIT_BOUNDARY", "AUDIT_PREFIX", "CHECK_IDS", "CHECK_PREFIX", "AUDIT_VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffAudit", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

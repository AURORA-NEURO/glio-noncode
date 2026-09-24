"""Independent assurance checks for downloaded-data review packet diffs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_diff as diff_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = diff_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address",
    "audit-canonical-replay",
    "audit-count-conservation",
    "audit-item-addresses",
    "audit-item-order",
    "audit-lineage",
    "audit-packet-identity",
    "audit-packet-addresses",
    "audit-public-boundary",
    "audit-query-replay",
    "audit-resource-counts",
    "audit-source-free",
    "audit-transition-replay",
    "audit-typed-replay",
)
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


class DownloadedDataReviewPacketDiffAuditCheck:
    FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "review packet diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("review packet diff audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("review packet diff audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "review packet diff audit detail", 2048)
        self.content_address = _address(content_address, "review packet diff audit check address", CHECK_PREFIX) if not content_address.endswith(":pending") else content_address
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("review packet diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffAuditCheck:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("review packet diff audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataReviewPacketDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataReviewPacketDiffAudit:
    FIELDS = ("diff_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_id: str, diff_address: str, checks: tuple[DownloadedDataReviewPacketDiffAuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "review packet diff audit diff ID")
        self.diff_address = _address(diff_address, "review packet diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = _address(content_address, "review packet diff audit address", AUDIT_PREFIX) if not content_address.endswith(":pending") else content_address
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("review packet diff audit aggregates do not replay")
        if not content_address.endswith(":pending") and address_audit(self) != content_address:
            raise ValidationError("review packet diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataReviewPacketDiffAudit:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("review packet diff audit fields are not exact")
        checks = tuple(DownloadedDataReviewPacketDiffAuditCheck.from_mapping(item) for item in value["checks"])
        return cls(value["diff_id"], value["diff_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataReviewPacketDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> DownloadedDataReviewPacketDiffAuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffAuditCheck(**body)
    return DownloadedDataReviewPacketDiffAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(diff_id: str, diff_address: str, checks: tuple[DownloadedDataReviewPacketDiffAuditCheck, ...]) -> DownloadedDataReviewPacketDiffAudit:
    body = {"diff_id": diff_id or "unavailable", "diff_address": diff_address or diff_model.DIFF_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataReviewPacketDiffAudit(**body)
    return DownloadedDataReviewPacketDiffAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_diff(value: Any) -> DownloadedDataReviewPacketDiffAudit:
    try:
        diff = diff_model.verify_diff(value)
        checks = (
            _check("audit-address", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayable", "diff address is independently recomputable"),
            _check("audit-canonical-replay", diff_model.diff_json(diff) == diff_model.diff_json(diff_model.diff_from_mapping(_strict_json_loads(diff_model.diff_json(diff)))), "replayed", "replayed", "canonical diff JSON reconstructs the typed diff"),
            _check("audit-count-conservation", len(diff.items) == sum(getattr(diff, f"{resource[:-1]}_{change}_count") for resource in ("members", "fields", "types") for change in diff_model.CHANGES) + 1, len(diff.items), "resource totals plus runtime", "item count conserves all resources"),
            _check("audit-item-addresses", all(diff_model.address_item(item) == item.content_address for item in diff.items), "replayed", "replayed", "every item address replays"),
            _check("audit-item-order", tuple(item.ordinal for item in diff.items) == tuple(range(1, len(diff.items) + 1)), tuple(item.ordinal for item in diff.items), "contiguous", "item ordinals are contiguous"),
            _check("audit-lineage", (diff.left_catalog_address == diff.right_catalog_address and diff.left_runtime_address == diff.right_runtime_address) == (diff.left_packet_address == diff.right_packet_address), {"components_equal": diff.left_catalog_address == diff.right_catalog_address and diff.left_runtime_address == diff.right_runtime_address, "packets_equal": diff.left_packet_address == diff.right_packet_address}, "equal states agree", "component lineage is consistent with packet movement"),
            _check("audit-packet-identity", bool(diff.packet_id), diff.packet_id, "non-empty", "logical packet identity is retained"),
            _check("audit-packet-addresses", diff.left_packet_address.startswith(diff_model.packet_model.PACKET_PREFIX + ":") and diff.right_packet_address.startswith(diff_model.packet_model.PACKET_PREFIX + ":"), "namespaced", "namespaced", "both packet addresses remain in the packet namespace"),
            _check("audit-public-boundary", not _has_forbidden_key(diff.to_dict()), "clean", "clean", "diff evidence contains no prohibited public keys"),
            _check("audit-query-replay", diff_model.query_diff(diff, limit=diff_model.MAX_LIMIT)["matched"] == len(diff.items), len(diff.items), len(diff.items), "unfiltered bounded query conserves every item"),
            _check("audit-resource-counts", all(getattr(diff, f"{resource[:-1]}_{change}_count") == sum(item.resource == resource and item.change == change for item in diff.items) for resource in ("members", "fields", "types") for change in diff_model.CHANGES), "replayed", "replayed", "resource change counters replay"),
            _check("audit-source-free", "source" not in diff.to_dict() and "packet_bytes" not in diff.to_dict(), "aggregate-only", "aggregate-only", "diff excludes source bytes and paths"),
            _check("audit-transition-replay", all(item.change == ("added" if not item.left_snapshot else "removed" if not item.right_snapshot else "unchanged" if not item.changed_attributes else "changed") for item in diff.items), "replayed", "replayed", "every transition classification replays"),
            _check("audit-typed-replay", diff_model.diff_from_mapping(diff.to_dict()).content_address == diff.content_address, diff.content_address, "replayed", "typed diff reload and addressing replay"),
        )
        return _receipt(diff.diff_id, diff.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"diff audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", diff_model.DIFF_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> DownloadedDataReviewPacketDiffAudit:
    audit = value if isinstance(value, DownloadedDataReviewPacketDiffAudit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("review packet diff audit address does not replay")
    return DownloadedDataReviewPacketDiffAudit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> DownloadedDataReviewPacketDiffAudit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="downloaded data review packet diff audit", max_bytes=16 * 1024 * 1024))
    return DownloadedDataReviewPacketDiffAudit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> DownloadedDataReviewPacketDiffAudit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("review packet diff audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("review packet diff audit destination is not a file")
    _validate_parent(path.parent, "review packet diff audit destination")
    atomic_write_text(path, audit_json(audit), field="review packet diff audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("review packet diff audit passed filter must be boolean")
    if not isinstance(text, str) or len(text) > 4096:
        raise ValidationError("review packet diff audit text filter is invalid")
    if offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("review packet diff audit query bounds are invalid")
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
    lines = ["# Downloaded Data Review Packet Diff Audit", "", f"- Diff: `{audit.diff_id}`", f"- Passed / failed: **{audit.passed_count} / {audit.failed_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", f"- Audit address: `{audit.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet diff audit check", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffAuditCheck.FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet diff audit", "type": "object", "additionalProperties": False, "required": list(DownloadedDataReviewPacketDiffAudit.FIELDS), "properties": {"diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    operations = ("audit_diff", "verify_audit", "load_source_free", "query_checks", "export_json", "export_csv", "render_markdown", "write_atomic")
    return {"public": True, "independent": True, "source_free": True, "version": AUDIT_VERSION, "check_count": len(CHECK_IDS), "operation_count": len(operations), "operations": list(operations), "deterministic": True}


__all__ = [
    "AUDIT_BOUNDARY", "AUDIT_PREFIX", "AUDIT_VERSION", "CHECK_IDS", "CHECK_PREFIX", "DownloadedDataReviewPacketDiffAudit", "DownloadedDataReviewPacketDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit",
]

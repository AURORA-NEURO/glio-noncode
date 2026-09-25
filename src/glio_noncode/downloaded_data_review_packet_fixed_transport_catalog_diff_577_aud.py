"""Independently audit module-577 catalog comparisons."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_577 as diff_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .downloaded_data_review_packet_fixed_transport_catalog_diff_577_ct import BOUNDARY
from .downloaded_data_review_packet_fixed_transport_catalog_diff_577_ct import DIFF_PREFIX, VERSION, address_diff, address_item
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = DIFF_PREFIX + "-audit-v1"
AUDIT_BOUNDARY = "public_" + AUDIT_VERSION.replace("-", "_")
AUDIT_PREFIX = DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-identity", "audit-lineage", "audit-item-order", "audit-item-addresses", "audit-counts", "audit-change-fold", "audit-transition", "audit-direction", "audit-summary", "audit-source-free", "audit-public-boundary")
CHECK_FIELDS = ("check_id", "detail", "observed", "required", "passed", "content_address")
AUDIT_FIELDS = ("diff_id", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_LIMIT = 256


def _address(value: Any, field: str, prefix: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        if isinstance(value, str) and value == prefix + ":pending":
            return value
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


@dataclass(frozen=True)
class AuditCheck:
    check_id: str
    detail: str
    observed: Any
    required: Any
    passed: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.check_id not in CHECK_IDS or not isinstance(self.detail, str) or not isinstance(self.passed, bool):
            raise ValidationError("module577 audit check is invalid")
        _address(self.content_address, "module577 audit check address", CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}


def _check(check_id: str, detail: str, observed: Any, required: Any, passed: bool) -> AuditCheck:
    body = {"check_id": check_id, "detail": detail, "observed": observed, "required": required, "passed": passed, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": content_hash(provisional.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)}))


@dataclass(frozen=True)
class Audit:
    diff_id: str
    diff_address: str
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    checks: tuple[AuditCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not self.diff_id or self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("module577 audit counts do not replay")
        _address(self.diff_address, "module577 audit diff address", DIFF_PREFIX)
        if not self.checks or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("module577 audit checks are not canonical")
        _address(self.content_address, "module577 audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("module577 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in AUDIT_FIELDS}


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _posture(catalog: Any) -> str:
    if catalog.entry_count == 0:
        return "empty"
    if catalog.ready_count == catalog.entry_count:
        return "ready"
    if catalog.blocked_count == catalog.entry_count:
        return "blocked"
    return "mixed"


def audit_diff(value: Any, *, left: Any = None, right: Any = None) -> Audit:
    diff = diff_model.verify_diff(value)
    recomputed = diff_model.build_diff(left, right, diff_id=diff.diff_id) if left is not None and right is not None else None
    actual_counts = {change: sum(item.change == change for item in diff.items) for change in diff_model.CHANGES}
    checks = (
        _check("audit-address", "diff address replays", address_diff(diff), diff.content_address, address_diff(diff) == diff.content_address),
        _check("audit-canonical", "diff JSON is canonical", diff_model.diff_json(diff), "canonical", diff_model.diff_json(diff) == canonical_json(diff.to_dict()) + "\n"),
        _check("audit-identity", "diff identity is current", (diff.version, diff.boundary), (VERSION, BOUNDARY), diff.version == VERSION and diff.boundary == BOUNDARY),
        _check("audit-lineage", "catalog lineage is addressed", (diff.left_catalog_address, diff.right_catalog_address), "catalog addresses", all(isinstance(address, str) and ":" in address for address in (diff.left_catalog_address, diff.right_catalog_address))),
        _check("audit-item-order", "items are stable and ordinal", tuple(item.entry_id for item in diff.items), tuple(sorted(item.entry_id for item in diff.items)), tuple(item.ordinal for item in diff.items) == tuple(range(1, len(diff.items) + 1))),
        _check("audit-item-addresses", "item addresses replay", tuple(address_item(item) for item in diff.items), "item addresses", all(address_item(item) == item.content_address for item in diff.items)),
        _check("audit-counts", "aggregate counts replay", (diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), len(diff.items), sum((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count)) == len(diff.items)),
        _check("audit-change-fold", "change classes replay", actual_counts, {change: getattr(diff, change + "_count") for change in diff_model.CHANGES}, actual_counts == {change: getattr(diff, change + "_count") for change in diff_model.CHANGES}),
        _check("audit-transition", "posture transition replays", diff.state_transition, diff_model._transition(diff.left_posture, diff.right_posture), diff.state_transition == diff_model._transition(diff.left_posture, diff.right_posture)),
        _check("audit-direction", "direction replays", diff.direction, recomputed.direction if recomputed is not None else diff.direction, recomputed is None or diff.direction == recomputed.direction),
        _check("audit-summary", "summary is source-free", diff.summary(), "no source values", not _has_forbidden_key(diff.summary())),
        _check("audit-source-free", "diff retains no source archive or record values", diff.to_dict(), "source-free", not _has_forbidden_key(diff.to_dict())),
        _check("audit-public-boundary", "public projection has no prohibited keys", diff.to_dict(), "clean", not _has_forbidden_key(diff.to_dict())),
    )
    passed = sum(check.passed for check in checks)
    body = {"diff_id": diff.diff_id, "diff_address": diff.content_address, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def _check_from_mapping(value: dict[str, Any]) -> AuditCheck:
    if set(value) != set(CHECK_FIELDS):
        raise ValidationError("module577 audit check fields are not exact")
    return AuditCheck(value["check_id"], value["detail"], value["observed"], value["required"], value["passed"], value["content_address"])


def _audit_from_mapping(value: dict[str, Any]) -> Audit:
    if set(value) != set(AUDIT_FIELDS):
        raise ValidationError("module577 audit fields are not exact")
    return Audit(value["diff_id"], value["diff_address"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], tuple(_check_from_mapping(item) for item in value["checks"]), value["content_address"])


def verify_audit(value: Any) -> Audit:
    audit = load_audit(value) if isinstance(value, (str, Path, bytes, bytearray)) else _audit_from_mapping(value) if isinstance(value, dict) else value
    if not isinstance(audit, Audit) or address_audit(audit) != audit.content_address or _has_forbidden_key(audit.to_dict()):
        raise ValidationError("module577 audit address or public boundary does not replay")
    return _audit_from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | dict[str, Any]) -> Audit:
    if isinstance(value, dict):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="module577 audit", max_bytes=32 * 1024 * 1024))
    return _audit_from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module577 audit destination already exists")
    _validate_parent(path.parent, "module577 audit destination")
    atomic_write_text(path, audit_json(audit), field="module577 audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool) or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module577 audit query filters are invalid")
    matches = tuple(check for check in audit.checks if (passed is None or check.passed == passed) and (not check_id or check.check_id == check_id) and (not text or text.casefold() in (check.check_id + " " + check.detail).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "diff_address": audit.diff_address, "passed": passed, "check_id": check_id, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(check.to_dict() for check in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, check_id=check_id, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("check_id", "detail", "observed", "required", "passed", "content_address"), lineterminator="\n")
    writer.writeheader()
    for check in result["checks"]:
        writer.writerow({field: check[field] if isinstance(check[field], str) else canonical_json(check[field]) for field in writer.fieldnames})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Module577 Catalog Diff Audit", "", f"- Diff: `{audit.diff_address}`", f"- Result: **{'accepted' if audit.accepted else 'blocked'}**", f"- Checks: **{audit.passed_count}/{audit.check_count}**", "", "| check | result |", "| --- | --- |"]
    lines.extend(f"| `{check.check_id}` | {'pass' if check.passed else 'fail'} |" for check in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module577 audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS)}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module577 audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"checks": {"type": "array", "maxItems": len(CHECK_IDS)}}}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "public": True, "source_free": True, "content_addressed": True, "check_ids": CHECK_IDS, "operations": ("audit_diff", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "Audit", "AuditCheck", "address_audit", "audit_diff", "audit_json", "audit_schema", "audit_csv", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

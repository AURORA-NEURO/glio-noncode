"""Independently audit module617 longitudinal transport catalog diffs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_617 as diff_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_617_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = VERSION = diff_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-identity", "audit-item-order", "audit-item-addresses", "audit-item-semantics", "audit-counts", "audit-catalog-lineage", "audit-posture-transition", "audit-direction", "audit-summary", "audit-source-free", "audit-public-boundary", "audit-query-replay", "audit-snapshot-bounds", "audit-source-recompute")
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
AUDIT_FIELDS = ("diff_id", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
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
            raise ValidationError("module617 audit check is invalid")
        _address(self.content_address, "module617 audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("module617 audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AuditCheck":
        if set(value) != set(CHECK_FIELDS):
            raise ValidationError("module617 audit check fields are not exact")
        return cls(value["check_id"], value["passed"], value["observed"], value["required"], value["detail"], value["content_address"])


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


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
        if not isinstance(self.diff_id, str) or not self.diff_id or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.check_count != len(self.checks) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("module617 audit aggregates do not replay")
        _address(self.diff_address, "module617 audit diff address", diff_model.DIFF_PREFIX)
        _address(self.content_address, "module617 audit address", AUDIT_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("module617 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: value for field, value in self.to_dict().items() if field != "checks"}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Audit":
        if set(value) != set(AUDIT_FIELDS):
            raise ValidationError("module617 audit fields are not exact")
        return cls(value["diff_id"], value["diff_address"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], tuple(AuditCheck.from_mapping(item) for item in value["checks"]), value["content_address"])


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> AuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(diff_id: str, diff_address: str, checks: tuple[AuditCheck, ...]) -> Audit:
    body = {"diff_id": diff_id or "unavailable", "diff_address": diff_address or diff_model.DIFF_PREFIX + ":" + "0" * 64, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def _semantic_items(diff: Any) -> bool:
    for item in diff.items:
        fields = tuple(field for field in contract_model.SNAPSHOT_FIELDS if item.left_snapshot.get(field) != item.right_snapshot.get(field))
        expected = "added" if not item.left_snapshot else "removed" if not item.right_snapshot else "unchanged" if not fields else "changed"
        if fields != item.changed_fields or expected != item.change:
            return False
    return True


def _snapshot_bounds(diff: Any) -> bool:
    return all(len(item.left_snapshot) <= len(contract_model.SNAPSHOT_FIELDS) and len(item.right_snapshot) <= len(contract_model.SNAPSHOT_FIELDS) and not _has_forbidden_key(item.left_snapshot) and not _has_forbidden_key(item.right_snapshot) for item in diff.items)


def audit_diff(value: Any, *, left: Any = None, right: Any = None) -> Audit:
    try:
        diff = diff_model.verify_diff(value)
        recomputed = diff_model.build_diff(left, right, diff_id=diff.diff_id) if left is not None and right is not None else None
        query_replay = all(diff_model.query_diff(diff, change=change)["matched"] == sum(item.change == change for item in diff.items) for change in contract_model.CHANGES)
        checks = (
            _check("audit-address", diff_model.address_diff(diff) == diff.content_address, diff.content_address, "replayable", "diff address is replayable"),
            _check("audit-canonical", diff_model.diff_json(diff) == canonical_json(diff.to_dict()) + "\n", "canonical", "canonical", "diff JSON is canonical"),
            _check("audit-identity", diff.version == diff_model.VERSION and diff.boundary == diff_model.BOUNDARY, (diff.version, diff.boundary), (diff_model.VERSION, diff_model.BOUNDARY), "diff identity is current"),
            _check("audit-item-order", tuple(item.ordinal for item in diff.items) == tuple(range(1, len(diff.items) + 1)) and tuple(item.entry_id for item in diff.items) == tuple(sorted(item.entry_id for item in diff.items)), "canonical", "canonical", "item order and IDs are canonical"),
            _check("audit-item-addresses", all(contract_model.address_item(item) == item.content_address for item in diff.items), "replayed", "replayed", "every item address replays"),
            _check("audit-item-semantics", _semantic_items(diff), "replayed", "replayed", "classification and changed fields replay from snapshots"),
            _check("audit-counts", (diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count) == tuple(sum(item.change == change for item in diff.items) for change in contract_model.CHANGES), "replayed", "replayed", "classification counts replay"),
            _check("audit-catalog-lineage", diff.catalog_id and diff.left_catalog_address and diff.right_catalog_address, "present", "present", "both catalog addresses and identity are retained"),
            _check("audit-posture-transition", diff.state_transition == ("same-" + diff.left_posture if diff.left_posture == diff.right_posture else f"{diff.left_posture}-to-{diff.right_posture}"), diff.state_transition, "folded", "posture transition is deterministic"),
            _check("audit-direction", diff.direction in contract_model.DIRECTIONS, diff.direction, contract_model.DIRECTIONS, "direction is a supported posture comparison"),
            _check("audit-summary", diff.summary() == {field: diff.to_dict()[field] for field in contract_model.DIFF_FIELDS if field != "items"}, "replayed", "replayed", "diff summary is deterministic"),
            _check("audit-source-free", not _has_forbidden_key(diff.to_dict()) and all("source" not in item.to_dict() for item in diff.items), "not present", "not present", "diff retains no source archive or record values"),
            _check("audit-public-boundary", not _has_forbidden_key(diff.to_dict()), "clean", "clean", "diff remains inside the public boundary"),
            _check("audit-query-replay", query_replay, "replayed", "replayed", "change queries reproduce classification counts"),
            _check("audit-snapshot-bounds", _snapshot_bounds(diff), "bounded", "bounded", "snapshots remain bounded and public"),
            _check("audit-source-recompute", recomputed is None or recomputed.content_address == diff.content_address, "not supplied" if recomputed is None else recomputed.content_address, "same address" if recomputed is not None else "optional", "supplied catalogs reproduce the diff"),
        )
        return _receipt(diff.diff_id, diff.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"module617 diff audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", diff_model.DIFF_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> Audit:
    audit = load_audit(value) if isinstance(value, (str, Path, bytes, bytearray)) else Audit.from_mapping(value) if isinstance(value, dict) else value
    if not isinstance(audit, Audit) or address_audit(audit) != audit.content_address or _has_forbidden_key(audit.to_dict()):
        raise ValidationError("module617 audit address or public boundary does not replay")
    return Audit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | dict[str, Any]) -> Audit:
    raw = value if isinstance(value, dict) else _strict_json_loads(bytes(value).decode("utf-8")) if isinstance(value, (bytes, bytearray)) else _strict_json_loads(read_text(value, field="module617 audit", max_bytes=32 * 1024 * 1024))
    return Audit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module617 audit destination already exists")
    _validate_parent(path.parent, "module617 audit destination")
    atomic_write_text(path, audit_json(audit), field="module617 audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if (passed is not None and not isinstance(passed, bool)) or not isinstance(text, str) or len(text) > 4096 or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module617 audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in (item.check_id + " " + item.detail).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "diff_address": audit.diff_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
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
    lines = ["# Module617 Catalog Diff Audit", "", f"- Diff: `{audit.diff_address}`", f"- Result: **{'accepted' if audit.accepted else 'blocked'}**", f"- Checks: **{audit.passed_count}/{audit.check_count}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module617 diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS)}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module617 catalog diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS)}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True, "operations": ("audit_diff", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "Audit", "AuditCheck", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_json", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

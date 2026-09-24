"""Independently audit source-free fixed policy transport catalog diff policy decisions."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import (
    downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_tr_cat_diff as diff_model,
)
from . import (
    downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_tcp as policy_model,
)
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = policy_model.VERSION + "-audit-v1"
AUDIT_BOUNDARY = policy_model.BOUNDARY + "_audit"
AUDIT_PREFIX = policy_model.POLICY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "audit-address", "audit-canonical", "audit-check-addresses", "audit-check-order", "audit-controls", "audit-counts",
    "audit-diff-lineage", "audit-decision", "audit-policy-replay", "audit-public-boundary", "audit-query-replay",
    "audit-state", "audit-typed-replay", "audit-diff-recomputation", "audit-total-budget", "audit-required-changes",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
AUDIT_FIELDS = ("policy_id", "policy_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
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


class AuditCheck:
    """One independently recomputed handoff-catalog policy check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, required: Any, detail: str, content_address: str) -> None:
        self.check_id = _label(check_id, "fixed policy transport catalog diff policy audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("fixed policy transport catalog diff policy audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("fixed policy transport catalog diff policy audit check result must be boolean")
        self.passed = passed
        self.observed = observed
        self.required = required
        self.detail = _text(detail, "fixed policy transport catalog diff policy audit detail", 2048)
        self.content_address = content_address if content_address.endswith(":pending") else _address(content_address, "fixed policy transport catalog diff policy audit check address", CHECK_PREFIX)
        if not content_address.endswith(":pending") and address_check(self) != content_address:
            raise ValidationError("fixed policy transport catalog diff policy audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AuditCheck:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("fixed policy transport catalog diff policy audit check fields are not exact")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class Audit:
    """Independent accepted or rejected evidence for one handoff-catalog policy."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, policy_id: str, policy_address: str, checks: tuple[AuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "fixed policy transport catalog diff policy audit policy ID")
        self.policy_address = _address(policy_address, "fixed policy transport catalog diff policy audit policy address", policy_model.POLICY_PREFIX)
        self.checks = tuple(checks)
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.content_address = content_address if content_address.endswith(":pending") else _address(content_address, "fixed policy transport catalog diff policy audit address", AUDIT_PREFIX)
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("fixed policy transport catalog diff policy audit aggregates do not replay")
        if not content_address.endswith(":pending") and address_audit(self) != content_address:
            raise ValidationError("fixed policy transport catalog diff policy audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "policy_address": self.policy_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Audit:
        if not isinstance(value, Mapping) or set(value) != set(cls.FIELDS):
            raise ValidationError("fixed policy transport catalog diff policy audit fields are not exact")
        checks = tuple(AuditCheck.from_mapping(item) for item in value["checks"])
        return cls(value["policy_id"], value["policy_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> AuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def _receipt(policy_id: str, policy_address: str, checks: tuple[AuditCheck, ...]) -> Audit:
    body = {"policy_id": policy_id or "unavailable", "policy_address": policy_address or policy_model.POLICY_PREFIX + ":" + "0" * 64, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": bool(checks) and all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def audit_policy(value: Any, *, diff: Any | None = None) -> Audit:
    try:
        policy = policy_model.verify_policy(value)
        supplied_diff = diff_model.verify_diff(diff) if diff is not None else None
        recomputed = policy_model.build_policy(supplied_diff, policy_id=policy.policy_id, maximum_added=policy.maximum_added, maximum_removed=policy.maximum_removed, maximum_changed=policy.maximum_changed, maximum_total_changes=policy.maximum_total_changes, allowed_changes=policy.allowed_changes, allowed_directions=policy.allowed_directions, allowed_transitions=policy.allowed_transitions, allowed_left_postures=policy.allowed_left_postures, allowed_right_postures=policy.allowed_right_postures, required_changes=policy.required_changes, require_ready=policy.require_ready, require_change=policy.require_change, allow_unchanged=policy.allow_unchanged) if supplied_diff is not None else None
        observed_changes = tuple(sorted({item.change for item in supplied_diff.items}, key=diff_model.CHANGES.index)) if supplied_diff is not None else ()
        checks = (
            _check("audit-address", policy_model.address_policy(policy) == policy.content_address, policy.content_address, "replayable", "policy address is independently recomputable"),
            _check("audit-canonical", policy_model.policy_json(policy) == policy_model.policy_json(policy_model.policy_from_mapping(_strict_json_loads(policy_model.policy_json(policy)))), "replayed", "replayed", "replayed policy JSON reconstructs the typed policy"),
            _check("audit-check-addresses", all(policy_model.address_check(item) == item.content_address for item in policy.checks), "replayed", "replayed", "every policy check address replays"),
            _check("audit-check-order", tuple(item.check_id for item in policy.checks) == policy_model.POLICY_CHECK_IDS, tuple(item.check_id for item in policy.checks), policy_model.POLICY_CHECK_IDS, "policy check order is canonical"),
            _check("audit-controls", policy.allowed_changes == tuple(sorted(policy.allowed_changes, key=policy_model.diff_model.CHANGES.index)) and policy.allowed_directions == tuple(sorted(policy.allowed_directions, key=policy_model.diff_model.DIRECTIONS.index)) and policy.allowed_transitions == tuple(sorted(policy.allowed_transitions, key=policy_model.diff_model.STATE_TRANSITIONS.index)) and policy.allowed_left_postures == tuple(sorted(policy.allowed_left_postures, key=policy_model.diff_model.POSTURES.index)) and policy.allowed_right_postures == tuple(sorted(policy.allowed_right_postures, key=policy_model.diff_model.POSTURES.index)) and policy.required_changes == tuple(sorted(policy.required_changes, key=policy_model.diff_model.CHANGES.index)), "replayed", "bounded and ordered", "policy controls are bounded and canonical"),
            _check("audit-counts", policy.check_count == len(policy.checks) and policy.passed_count + policy.failed_count == policy.check_count, {"check_count": policy.check_count, "passed_count": policy.passed_count, "failed_count": policy.failed_count}, "conserved", "policy counters conserve checks"),
            _check("audit-diff-lineage", policy.diff_address.startswith(diff_model.DIFF_PREFIX + ":"), policy.diff_address, "diff namespace", "policy retains a fixed policy transport catalog diff lineage address"),
            _check("audit-decision", policy.accepted == (policy.failed_count == 0), policy.accepted, "failed_count == 0", "policy acceptance conserves failed checks"),
            _check("audit-policy-replay", policy_model.policy_from_mapping(policy.to_dict()).content_address == policy.content_address, policy.content_address, "replayed", "typed policy reload and address replay"),
            _check("audit-public-boundary", not _has_forbidden_key(policy.to_dict()), "clean", "clean", "policy evidence contains no prohibited public keys"),
            _check("audit-query-replay", policy_model.query_policy(policy, limit=policy_model.MAX_LIMIT)["matched"] == len(policy.checks), len(policy.checks), len(policy.checks), "unfiltered query conserves every policy check"),
            _check("audit-state", policy.state == ("ready" if policy.accepted else "blocked"), policy.state, "ready iff accepted", "policy state replays acceptance"),
            _check("audit-typed-replay", policy_model.verify_policy(policy.to_dict()).content_address == policy.content_address, policy.content_address, "replayed", "typed policy reload and addressing replay"),
            _check("audit-diff-recomputation", supplied_diff is None or canonical_json(recomputed.to_dict()) == canonical_json(policy.to_dict()), "not-supplied" if supplied_diff is None else recomputed.content_address, "optional" if supplied_diff is None else policy.content_address, "policy controls recompute the supplied fixed policy transport catalog diff decision"),
            _check("audit-total-budget", isinstance(policy.maximum_total_changes, int) and 0 <= policy.maximum_total_changes <= diff_model.MAX_ITEMS, policy.maximum_total_changes, "bounded", "total-change policy budget is bounded"),
            _check("audit-required-changes", all(item in diff_model.CHANGES for item in policy.required_changes) and policy.required_changes == tuple(sorted(policy.required_changes, key=diff_model.CHANGES.index)), observed_changes, policy.required_changes, "required change controls are canonical"),
        )
        return _receipt(policy.policy_id, policy.content_address, checks)
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"fixed policy transport catalog diff policy audit unavailable: {exc}") for check_id in CHECK_IDS)
        return _receipt("unavailable", policy_model.POLICY_PREFIX + ":" + "0" * 64, checks)


def verify_audit(value: Any) -> Audit:
    audit = value if isinstance(value, Audit) else load_audit(value)
    if address_audit(audit) != audit.content_address:
        raise ValidationError("fixed policy transport catalog diff policy audit address does not replay")
    return Audit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> Audit:
    if isinstance(value, Mapping):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="fixed policy transport catalog diff policy audit", max_bytes=16 * 1024 * 1024))
    return Audit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("fixed policy transport catalog diff policy audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("fixed policy transport catalog diff policy audit destination is not a file")
    _validate_parent(path.parent, "fixed policy transport catalog diff policy audit destination")
    atomic_write_text(path, audit_json(audit), field="fixed policy transport catalog diff policy audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("fixed policy transport catalog diff policy audit passed filter must be boolean")
    text = _text(text, "fixed policy transport catalog diff policy audit text filter") if text else ""
    if offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("fixed policy transport catalog diff policy audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in " ".join((item.check_id, item.detail, str(item.observed))).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
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
    lines = ["# Fixed Policy Transport Catalog Diff Policy Audit", "", f"- Policy: `{audit.policy_id}`", f"- Passed / failed: **{audit.passed_count} / {audit.failed_count}**", f"- Accepted: **{str(audit.accepted).lower()}**", f"- Address: `{audit.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data fixed policy transport catalog diff policy audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "required": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data fixed policy transport catalog diff policy audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"policy_id": {"type": "string"}, "policy_address": {"type": "string"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    operations = ("audit_policy", "verify_audit", "load_source_free", "query_checks", "export_json", "export_csv", "render_markdown", "write_atomic")
    return {"public": True, "independent": True, "source_free": True, "version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_count": len(CHECK_IDS), "operation_count": len(operations), "operations": list(operations)}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "Audit", "AuditCheck", "address_audit", "address_check", "audit_csv", "audit_json", "audit_policy", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]


# Transport-catalog names make the module-566 audit boundary explicit.
audit_transport_catalog_diff_policy = audit_policy

__all__ = sorted(set(__all__) | {"audit_transport_catalog_diff_policy"})

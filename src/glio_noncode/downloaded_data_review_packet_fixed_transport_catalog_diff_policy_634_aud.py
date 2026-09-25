"""Independently audit module634 catalog-diff policy decisions."""
# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_633 as diff_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_634 as policy_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_634_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = policy_model.POLICY_PREFIX + "-audit-v1"
AUDIT_BOUNDARY = "public_" + AUDIT_VERSION.replace("-", "_")
AUDIT_PREFIX = policy_model.POLICY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-diff-lineage", "audit-check-order", "audit-check-addresses", "audit-counts", "audit-state", "audit-budgets", "audit-change-allowlist", "audit-direction-transition", "audit-posture-allowlist", "audit-ready-control", "audit-change-control", "audit-required-changes", "audit-unchanged-control", "audit-public-boundary")
CHECK_FIELDS = ("check_id", "passed", "observed", "required", "detail", "content_address")
AUDIT_FIELDS = ("policy_id", "policy_address", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_LIMIT = 256


def _address(value: Any, field: str, prefix: str, *, allow_pending: bool = False) -> str:
    if allow_pending and isinstance(value, str) and value.endswith(":pending"):
        return value
    if not isinstance(value, str) or not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64 or any(char not in "0123456789abcdef" for char in value.rsplit(":", 1)[-1]):
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
            raise ValidationError("module634 audit check is invalid")
        _address(self.content_address, "module634 audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("module634 audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AuditCheck":
        if set(value) != set(CHECK_FIELDS):
            raise ValidationError("module634 audit check fields are not exact")
        return cls(*(value[field] for field in CHECK_FIELDS))


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


@dataclass(frozen=True)
class Audit:
    policy_id: str
    policy_address: str
    diff_address: str
    check_count: int
    passed_count: int
    failed_count: int
    accepted: bool
    checks: tuple[AuditCheck, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.check_count != len(self.checks) or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("module634 audit aggregates do not replay")
        _address(self.policy_address, "module634 audit policy address", policy_model.POLICY_PREFIX)
        _address(self.diff_address, "module634 audit diff address", diff_model.DIFF_PREFIX)
        _address(self.content_address, "module634 audit address", AUDIT_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("module634 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "policy_address": self.policy_address, "diff_address": self.diff_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: value for field, value in self.to_dict().items() if field != "checks"}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Audit":
        if set(value) != set(AUDIT_FIELDS):
            raise ValidationError("module634 audit fields are not exact")
        return cls(value["policy_id"], value["policy_address"], value["diff_address"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], tuple(AuditCheck.from_mapping(item) for item in value["checks"]), value["content_address"])


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> AuditCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_policy(value: Any, *, diff: Any = None) -> Audit:
    try:
        policy = policy_model.verify_policy(value)
        reference = diff_model.verify_diff(diff) if diff is not None else None
        actual = {item.check_id: item for item in policy.checks}
        recomputed = policy_model.build_policy(reference, policy_id=policy.policy_id, maximum_added=policy.maximum_added, maximum_removed=policy.maximum_removed, maximum_changed=policy.maximum_changed, maximum_total_changes=policy.maximum_total_changes, allowed_changes=policy.allowed_changes, allowed_directions=policy.allowed_directions, allowed_transitions=policy.allowed_transitions, allowed_left_postures=policy.allowed_left_postures, allowed_right_postures=policy.allowed_right_postures, required_changes=policy.required_changes, require_ready=policy.require_ready, require_change=policy.require_change, allow_unchanged=policy.allow_unchanged) if reference is not None else None
        expected_budgets = ("policy-added-budget", "policy-removed-budget", "policy-changed-budget", "policy-total-change-budget")
        checks = (
            _check("audit-address", policy_model.address_policy(policy) == policy.content_address, policy.content_address, "replayable", "policy address replays"),
            _check("audit-canonical", policy_model.policy_json(policy) == canonical_json(policy.to_dict()) + "\n", "canonical", "canonical", "policy JSON is canonical"),
            _check("audit-diff-lineage", reference is None or policy.diff_address == reference.content_address, policy.diff_address, reference.content_address if reference is not None else policy.diff_address, "policy diff lineage is addressed"),
            _check("audit-check-order", tuple(item.check_id for item in policy.checks) == policy_model.POLICY_CHECK_IDS, tuple(item.check_id for item in policy.checks), policy_model.POLICY_CHECK_IDS, "policy checks are canonical"),
            _check("audit-check-addresses", all(policy_model.address_check(item) == item.content_address for item in policy.checks), "replayed", "replayed", "policy check addresses replay"),
            _check("audit-counts", (policy.check_count, policy.passed_count, policy.failed_count) == (len(policy.checks), sum(item.passed for item in policy.checks), sum(not item.passed for item in policy.checks)), (policy.check_count, policy.passed_count, policy.failed_count), "replayed", "policy counts replay"),
            _check("audit-state", policy.state == ("ready" if policy.accepted else "blocked"), policy.state, "ready iff accepted", "policy state follows acceptance"),
            _check("audit-budgets", all(name in actual for name in expected_budgets), tuple(actual.get(name).passed for name in expected_budgets if name in actual), "four budget controls", "budget controls are retained"),
            _check("audit-change-allowlist", "policy-change-allowlist" in actual, actual.get("policy-change-allowlist").passed if "policy-change-allowlist" in actual else "missing", "recorded", "change allowlist control is retained"),
            _check("audit-direction-transition", all(name in actual for name in ("policy-direction-allowlist", "policy-transition-allowlist")), "recorded", "recorded", "direction and transition controls are retained"),
            _check("audit-posture-allowlist", all(name in actual for name in ("policy-left-posture-allowlist", "policy-right-posture-allowlist")), "recorded", "recorded", "posture controls are retained"),
            _check("audit-ready-control", "policy-ready-requirement" in actual, "recorded" if "policy-ready-requirement" in actual else "missing", "recorded", "readiness control is retained"),
            _check("audit-change-control", "policy-change-requirement" in actual, "recorded" if "policy-change-requirement" in actual else "missing", "recorded", "change control is retained"),
            _check("audit-required-changes", "policy-required-changes" in actual, "recorded" if "policy-required-changes" in actual else "missing", "recorded", "required-change control is retained"),
            _check("audit-unchanged-control", "policy-unchanged-control" in actual, "recorded" if "policy-unchanged-control" in actual else "missing", "recorded", "unchanged control is retained"),
            _check("audit-public-boundary", (recomputed is None or recomputed.content_address == policy.content_address) and not _has_forbidden_key(policy.to_dict()), (recomputed is None or recomputed.content_address == policy.content_address, _has_forbidden_key(policy.to_dict())), (True, False), "policy recomputation and public boundary are valid"),
        )
        body = {"policy_id": policy.policy_id, "policy_address": policy.content_address, "diff_address": policy.diff_address, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    except Exception as exc:
        checks = tuple(_check(check_id, False, "unavailable", "replayable", f"module634 policy audit unavailable: {exc}") for check_id in CHECK_IDS)
        body = {"policy_id": "unavailable", "policy_address": policy_model.POLICY_PREFIX + ":" + "0" * 64, "diff_address": diff_model.DIFF_PREFIX + ":" + "0" * 64, "check_count": len(checks), "passed_count": 0, "failed_count": len(checks), "accepted": False, "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def verify_audit(value: Any) -> Audit:
    audit = load_audit(value) if isinstance(value, (str, Path, bytes, bytearray)) else Audit.from_mapping(value) if isinstance(value, dict) else value
    if not isinstance(audit, Audit) or address_audit(audit) != audit.content_address or _has_forbidden_key(audit.to_dict()):
        raise ValidationError("module634 audit address or public boundary does not replay")
    return Audit.from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | dict[str, Any]) -> Audit:
    raw = value if isinstance(value, dict) else _strict_json_loads(bytes(value).decode("utf-8")) if isinstance(value, (bytes, bytearray)) else _strict_json_loads(read_text(value, field="module634 audit", max_bytes=32 * 1024 * 1024))
    return Audit.from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module634 audit destination already exists")
    _validate_parent(path.parent, "module634 audit destination")
    atomic_write_text(path, audit_json(audit), field="module634 audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if (passed is not None and not isinstance(passed, bool)) or not isinstance(text, str) or len(text) > 4096 or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module634 audit query bounds are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not text or text.casefold() in (item.check_id + " " + item.detail).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "policy_address": audit.policy_address, "passed": passed, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
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
    lines = ["# Module634 Catalog Diff Policy Audit", "", f"- Policy: `{audit.policy_address}`", f"- Result: **{'accepted' if audit.accepted else 'blocked'}**", f"- Checks: **{audit.passed_count}/{audit.check_count}**", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module634 audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS)}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module634 policy audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS)}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "check_ids": CHECK_IDS, "independent": True, "source_free": True, "content_addressed": True, "operations": ("audit_policy", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "Audit", "AuditCheck", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "address_audit", "address_check", "audit_csv", "audit_json", "audit_policy", "audit_schema", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

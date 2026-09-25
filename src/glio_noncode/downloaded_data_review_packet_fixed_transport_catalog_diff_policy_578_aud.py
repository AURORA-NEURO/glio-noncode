"""Independently audit module-578 policy decisions."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_577 as diff_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_578 as policy_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

AUDIT_VERSION = policy_model.POLICY_PREFIX + "-audit-v1"
AUDIT_BOUNDARY = "public_" + AUDIT_VERSION.replace("-", "_")
AUDIT_PREFIX = policy_model.POLICY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("audit-address", "audit-canonical", "audit-diff-lineage", "audit-check-order", "audit-check-addresses", "audit-counts", "audit-state", "audit-budgets", "audit-change-allowlist", "audit-direction-transition", "audit-posture-allowlist", "audit-ready-control", "audit-change-control", "audit-required-changes", "audit-unchanged-control", "audit-public-boundary")
CHECK_FIELDS = ("check_id", "detail", "observed", "required", "passed", "content_address")
AUDIT_FIELDS = ("policy_id", "policy_address", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_LIMIT = 256


def _address(value: Any, field: str, prefix: str) -> str:
    if isinstance(value, str) and value == prefix + ":pending":
        return value
    if not isinstance(value, str) or not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
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
            raise ValidationError("module578 audit check is invalid")
        _address(self.content_address, "module578 audit check address", CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CHECK_FIELDS}


def _check(check_id: str, detail: str, observed: Any, required: Any, passed: bool) -> AuditCheck:
    body = {"check_id": check_id, "detail": detail, "observed": observed, "required": required, "passed": passed, "content_address": CHECK_PREFIX + ":pending"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": content_hash(provisional.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)}))


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
        if not self.policy_id or self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("module578 audit aggregates do not replay")
        _address(self.policy_address, "module578 audit policy address", policy_model.POLICY_PREFIX)
        _address(self.diff_address, "module578 audit diff address", diff_model.DIFF_PREFIX)
        _address(self.content_address, "module578 audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("module578 audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "policy_address": self.policy_address, "diff_address": self.diff_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": tuple(item.to_dict() for item in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()


def address_audit(value: Audit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def audit_policy(value: Any, *, diff: Any = None) -> Audit:
    policy = policy_model.verify_policy(value)
    reference = diff_model.verify_diff(diff) if diff is not None else None
    actual = {item.check_id: item for item in policy.checks}
    recomputed = policy_model.build_policy(reference, policy_id=policy.policy_id, maximum_added=policy.maximum_added, maximum_removed=policy.maximum_removed, maximum_changed=policy.maximum_changed, maximum_total_changes=policy.maximum_total_changes, allowed_changes=policy.allowed_changes, allowed_directions=policy.allowed_directions, allowed_transitions=policy.allowed_transitions, allowed_left_postures=policy.allowed_left_postures, allowed_right_postures=policy.allowed_right_postures, required_changes=policy.required_changes, require_ready=policy.require_ready, require_change=policy.require_change, allow_unchanged=policy.allow_unchanged) if reference is not None else None
    checks = (
        _check("audit-address", "policy address replays", policy_model.address_policy(policy), policy.content_address, policy_model.address_policy(policy) == policy.content_address),
        _check("audit-canonical", "policy JSON is canonical", policy_model.policy_json(policy), "canonical", policy_model.policy_json(policy) == canonical_json(policy.to_dict()) + "\n"),
        _check("audit-diff-lineage", "policy diff lineage is addressed", policy.diff_address, reference.content_address if reference is not None else policy.diff_address, reference is None or policy.diff_address == reference.content_address),
        _check("audit-check-order", "policy checks are canonical", tuple(item.check_id for item in policy.checks), policy_model.POLICY_CHECK_IDS, tuple(item.check_id for item in policy.checks) == policy_model.POLICY_CHECK_IDS),
        _check("audit-check-addresses", "policy check addresses replay", tuple(policy_model.address_check(item) for item in policy.checks), "replayed", all(policy_model.address_check(item) == item.content_address for item in policy.checks)),
        _check("audit-counts", "policy counts replay", (policy.check_count, policy.passed_count, policy.failed_count), (len(policy.checks), sum(item.passed for item in policy.checks), sum(not item.passed for item in policy.checks)), policy.check_count == len(policy.checks) and policy.passed_count == sum(item.passed for item in policy.checks) and policy.failed_count == sum(not item.passed for item in policy.checks)),
        _check("audit-state", "policy state follows acceptance", policy.state, "ready iff accepted", policy.state == ("ready" if policy.accepted else "blocked")),
        _check("audit-budgets", "policy budget checks are present", tuple(actual[name].passed for name in ("policy-added-budget", "policy-removed-budget", "policy-changed-budget", "policy-total-change-budget")), "four budget controls", all(name in actual for name in ("policy-added-budget", "policy-removed-budget", "policy-changed-budget", "policy-total-change-budget"))),
        _check("audit-change-allowlist", "change allowlist control is present", actual["policy-change-allowlist"].passed, "recorded", "policy-change-allowlist" in actual),
        _check("audit-direction-transition", "direction and transition controls are present", (actual["policy-direction-allowlist"].passed, actual["policy-transition-allowlist"].passed), "recorded", "policy-direction-allowlist" in actual and "policy-transition-allowlist" in actual),
        _check("audit-posture-allowlist", "posture controls are present", (actual["policy-left-posture-allowlist"].passed, actual["policy-right-posture-allowlist"].passed), "recorded", "policy-left-posture-allowlist" in actual and "policy-right-posture-allowlist" in actual),
        _check("audit-ready-control", "readiness control is present", actual["policy-ready-requirement"].passed, "recorded", "policy-ready-requirement" in actual),
        _check("audit-change-control", "change control is present", actual["policy-change-requirement"].passed, "recorded", "policy-change-requirement" in actual),
        _check("audit-required-changes", "required-change control is present", actual["policy-required-changes"].passed, "recorded", "policy-required-changes" in actual),
        _check("audit-unchanged-control", "unchanged control is present", actual["policy-unchanged-control"].passed, "recorded", "policy-unchanged-control" in actual),
        _check("audit-public-boundary", "policy remains inside the public boundary", _has_forbidden_key(policy.to_dict()), False, not _has_forbidden_key(policy.to_dict())),
    )
    if recomputed is not None:
        checks = checks[:-1] + (_check("audit-public-boundary", "policy recomputation and public boundary are valid", recomputed.content_address == policy.content_address and not _has_forbidden_key(policy.to_dict()), policy.content_address, recomputed.content_address == policy.content_address and not _has_forbidden_key(policy.to_dict())),)
    passed = sum(item.passed for item in checks)
    body = {"policy_id": policy.policy_id, "policy_address": policy.content_address, "diff_address": policy.diff_address, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = Audit(**body)
    return Audit(**(body | {"content_address": address_audit(provisional)}))


def _check_from_mapping(value: dict[str, Any]) -> AuditCheck:
    if set(value) != set(CHECK_FIELDS):
        raise ValidationError("module578 audit check fields are not exact")
    return AuditCheck(value["check_id"], value["detail"], value["observed"], value["required"], value["passed"], value["content_address"])


def _audit_from_mapping(value: dict[str, Any]) -> Audit:
    if set(value) != set(AUDIT_FIELDS):
        raise ValidationError("module578 audit fields are not exact")
    return Audit(value["policy_id"], value["policy_address"], value["diff_address"], value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], tuple(_check_from_mapping(item) for item in value["checks"]), value["content_address"])


def verify_audit(value: Any) -> Audit:
    audit = load_audit(value) if isinstance(value, (str, Path, bytes, bytearray)) else _audit_from_mapping(value) if isinstance(value, dict) else value
    if not isinstance(audit, Audit) or address_audit(audit) != audit.content_address or _has_forbidden_key(audit.to_dict()):
        raise ValidationError("module578 audit address or public boundary does not replay")
    return _audit_from_mapping(audit.to_dict())


def load_audit(value: bytes | bytearray | str | Path | dict[str, Any]) -> Audit:
    if isinstance(value, dict):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        raw = _strict_json_loads(bytes(value).decode("utf-8"))
    else:
        raw = _strict_json_loads(read_text(value, field="module578 audit", max_bytes=32 * 1024 * 1024))
    return _audit_from_mapping(raw)


def audit_json(value: Any) -> str:
    return canonical_json(verify_audit(value).to_dict()) + "\n"


def write_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Audit:
    audit = verify_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module578 audit destination already exists")
    _validate_parent(path.parent, "module578 audit destination")
    atomic_write_text(path, audit_json(audit), field="module578 audit destination")
    return audit


def query_audit(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    audit = verify_audit(value)
    if passed is not None and not isinstance(passed, bool) or offset < 0 or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module578 audit query filters are invalid")
    matches = tuple(item for item in audit.checks if (passed is None or item.passed == passed) and (not check_id or item.check_id == check_id) and (not text or text.casefold() in (item.check_id + " " + item.detail).casefold()))
    selected = matches[offset:offset + limit]
    result = {"audit_address": audit.content_address, "policy_address": audit.policy_address, "passed": passed, "check_id": check_id, "text": text, "offset": offset, "limit": limit, "total": len(audit.checks), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "checks": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=AUDIT_PREFIX + "-query")}


def audit_csv(value: Any, *, passed: bool | None = None, check_id: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_audit(value, passed=passed, check_id=check_id, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in result["checks"]:
        writer.writerow({field: canonical_json(item[field]) if field in {"observed", "required"} else item[field] for field in CHECK_FIELDS})
    return stream.getvalue()


def render_audit_markdown(value: Any) -> str:
    audit = verify_audit(value)
    lines = ["# Module578 Catalog Diff Policy Audit", "", f"- Policy: `{audit.policy_address}`", f"- Result: **{'accepted' if audit.accepted else 'blocked'}**", f"- Checks: **{audit.passed_count}/{audit.check_count}**", "", "| check | result |", "| --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {'pass' if item.passed else 'fail'} |" for item in audit.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module578 audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS)}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module578 audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS)}


def capabilities() -> dict[str, Any]:
    return {"version": AUDIT_VERSION, "boundary": AUDIT_BOUNDARY, "public": True, "source_free": True, "content_addressed": True, "check_ids": CHECK_IDS, "operations": ("audit_policy", "audit_json", "audit_csv", "render_audit_markdown", "query_audit", "verify_audit")}


__all__ = ["AUDIT_BOUNDARY", "AUDIT_FIELDS", "AUDIT_PREFIX", "AUDIT_VERSION", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "Audit", "AuditCheck", "address_audit", "audit_policy", "audit_json", "audit_schema", "audit_csv", "capabilities", "check_schema", "load_audit", "query_audit", "render_audit_markdown", "verify_audit", "write_audit"]

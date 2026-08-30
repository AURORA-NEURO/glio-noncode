"""Independent assurance for compatibility remediation plans."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from . import downloaded_data_profile_contract_compatibility_audit as compatibility_audit_model
from . import downloaded_data_profile_contract_compatibility_remediation as remediation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "gate-linkage",
    "policy-linkage",
    "action-conservation",
    "action-order",
    "classification-replay",
    "priority-replay",
    "requiredness-replay",
    "state-decision",
    "acceptance-replay",
    "address-replay",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("plan_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


class DownloadedDataProfileContractCompatibilityRemediationAuditCheck:
    """One recomputed remediation-plan invariant."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "remediation audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "remediation audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("remediation audit check ID is unsupported")
        self.passed = _bool(passed, "remediation audit check result")
        self.detail = _text(detail, "remediation audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "remediation audit evidence address") for item in _sequence(evidence_addresses, "remediation audit evidence addresses", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("remediation audit checks require evidence")
        self.content_address = _address(content_address, "remediation audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("remediation audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("remediation audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationAuditCheck:
        value = _mapping(value, "remediation audit check")
        _strict(value, set(cls.FIELDS), "remediation audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationAudit:
    """Complete independent audit of one remediation plan."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, plan_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.plan_address = _address(plan_address, "remediation audit plan address", remediation_model.PLAN_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationAuditCheck.from_mapping(item) for item in _sequence(checks, "remediation audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "remediation audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "remediation audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "remediation audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "remediation audit acceptance")
        self.content_address = _address(content_address, "remediation audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("remediation audit checks are not canonical")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("remediation audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("remediation audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("remediation audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"plan_address": self.plan_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationAudit:
        value = _mapping(value, "remediation audit")
        _strict(value, set(cls.FIELDS), "remediation audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityRemediationAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationAuditCheck(ordinal, check_id, passed, detail, provisional.evidence_addresses, address_check(provisional))


def audit_plan(value: remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan) -> DownloadedDataProfileContractCompatibilityRemediationAudit:
    """Recompute every action, disposition, and nested compatibility receipt."""

    if not isinstance(value, remediation_model.DownloadedDataProfileContractCompatibilityRemediationPlan):
        raise ValidationError("remediation audit requires a typed plan")
    plan = value
    gate = plan.gate
    gate_audit = compatibility_audit_model.audit_gate(gate)
    expected_actions = tuple(remediation_model._action(item, ordinal, gate.content_address) for ordinal, item in enumerate(gate.findings, 1))
    expected_counts = tuple(sum(item.action == action for item in expected_actions) for action in remediation_model.ACTION_KINDS)
    expected_required = sum(item.required for item in expected_actions)
    expected_state = "blocked" if any(item.outcome == "breaking" for item in expected_actions) else "review" if expected_required else "clear"
    expected_decision = {"clear": "close", "review": "hold", "blocked": "block"}[expected_state]
    evidence = (plan.content_address, gate.content_address, gate.policy.content_address)
    checks = (
        _check(1, "version", plan.version == remediation_model.VERSION, "remediation plan uses the current version", evidence),
        _check(2, "boundary", plan.boundary == remediation_model.BOUNDARY, "remediation plan uses the public boundary", evidence),
        _check(3, "gate-linkage", plan.gate_id == gate.gate_id and plan.gate_address == gate.content_address, "plan gate identity and address replay", (plan.gate_address,)),
        _check(4, "policy-linkage", gate.policy.content_address == compatibility_model.address_policy(gate.policy), "compatibility policy address is retained by the gate", (gate.policy.content_address,)),
        _check(5, "action-conservation", plan.action_count == len(expected_actions) and plan.action_count == sum(expected_counts) and len(plan.actions) == plan.action_count, "remediation action count conservation", evidence),
        _check(6, "action-order", tuple(item.ordinal for item in plan.actions) == tuple(range(1, plan.action_count + 1)), "remediation action order is contiguous", tuple(item.content_address for item in plan.actions)[:8] or evidence),
        _check(7, "classification-replay", tuple(item.to_dict() for item in plan.actions) == tuple(item.to_dict() for item in expected_actions), "actions replay directly from compatibility findings", tuple(item.content_address for item in plan.actions)[:8] or evidence),
        _check(8, "priority-replay", all(item.priority == expected.priority and item.action == expected.action for item, expected in zip(plan.actions, expected_actions, strict=True)), "action kind and priority replay", tuple(item.content_address for item in plan.actions)[:8] or evidence),
        _check(9, "requiredness-replay", plan.required_action_count == expected_required and all(item.required == expected.required for item, expected in zip(plan.actions, expected_actions, strict=True)), "required action counts replay", evidence),
        _check(10, "state-decision", plan.state == expected_state and plan.decision == expected_decision, "plan state and decision replay", evidence),
        _check(11, "acceptance-replay", plan.accepted == (expected_state == "clear") and gate_audit.accepted, "plan acceptance requires a valid compatibility gate", (plan.content_address, gate_audit.content_address)),
        _check(12, "address-replay", remediation_model.address_plan(plan) == plan.content_address and all(remediation_model.address_action(item) == item.content_address for item in plan.actions), "plan and action addresses replay", evidence),
        _check(13, "public-boundary", _public(plan.to_dict()), "plan contains no forbidden public attribution keys", evidence),
        _check(14, "mapping-round-trip", remediation_model.plan_from_mapping(plan.to_dict()).content_address == plan.content_address, "mapping round-trip preserves the plan address", (plan.content_address,)),
    )
    body = {"plan_address": plan.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationAudit:
    return DownloadedDataProfileContractCompatibilityRemediationAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityRemediationAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityRemediationAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Audit", "", f"- Plan: `{value.plan_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"plan_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_plan", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationAudit", "DownloadedDataProfileContractCompatibilityRemediationAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_plan", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

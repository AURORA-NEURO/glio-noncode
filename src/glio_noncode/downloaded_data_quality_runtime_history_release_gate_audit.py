"""Independent audit of downloaded-data quality release gates."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_runtime_history_release_gate as gate_model
from . import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-audit-v1"
BOUNDARY = gate_model.BOUNDARY + "_audit"
AUDIT_PREFIX = gate_model.GATE_PREFIX + "-audit"
FINDING_PREFIX = AUDIT_PREFIX + "-finding"
MAX_CHECKS = 12
CHECK_IDS = (
    "history_link",
    "history_valid",
    "policy_address",
    "gate_check_count",
    "gate_check_ids",
    "check_addresses",
    "check_counters",
    "summary_link",
    "manifest_link",
    "readiness_replay",
    "history_metrics",
    "public_boundary",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("gate_id", "history_id", "gate_address", "history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _display(value: Any) -> str:
    return canonical_json(value)


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "release gate audit ordinal", MAX_CHECKS)
        if self.ordinal < 1:
            raise ValidationError("release gate audit ordinal must be positive")
        self.check_id = _label(check_id, "release gate audit check ID")
        self.passed = _bool(passed, "release gate audit check result")
        self.actual = _text(actual, "release gate audit actual")
        self.expected = _text(expected, "release gate audit expected")
        self.detail = _text(detail, "release gate audit detail")
        self.content_address = _address(content_address, "release gate audit finding address", FINDING_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not self.content_address.startswith("pending:") and content_hash(self.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX) != self.content_address:
            raise ValidationError("release gate audit finding address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AuditCheck:
        value = _mapping(value, "release gate audit check")
        _strict(value, set(cls.FIELDS), "release gate audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class GateAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, gate_id: str, history_id: str, gate_address: str, history_address: str, checks: tuple[AuditCheck, ...], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.gate_id = _label(gate_id, "release gate audit ID")
        self.history_id = _label(history_id, "release gate audit history ID")
        self.gate_address = _address(gate_address, "release gate audit gate address", gate_model.GATE_PREFIX)
        self.history_address = _address(history_address, "release gate audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(checks)
        self.check_count = _count(check_count, "release gate audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "release gate audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "release gate audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "release gate audit acceptance")
        self.content_address = _address(content_address, "release gate audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or self.check_count != len(self.checks):
            raise ValidationError("release gate audit check order does not replay")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("release gate audit counters do not replay")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("release gate audit check IDs do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("release gate audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "history_id": self.history_id, "gate_address": self.gate_address, "history_address": self.history_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> GateAudit:
        value = _mapping(value, "release gate audit")
        _strict(value, set(cls.FIELDS), "release gate audit")
        return cls(value["gate_id"], value["history_id"], value["gate_address"], value["history_address"], tuple(AuditCheck.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: GateAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    value = AuditCheck(ordinal, check_id, passed, _display(actual), _display(expected), detail, f"pending:{FINDING_PREFIX}")
    value.content_address = address_check(value)
    value._validate()
    return value


def audit_gate(gate: gate_model.ReleaseGate, history: Any) -> GateAudit:
    if not isinstance(gate, gate_model.ReleaseGate):
        raise ValidationError("release gate audit requires a typed gate")
    if not isinstance(history, history_model.DownloadedDataQualityDiffGateRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryDiffRuntimeRegistryHistoryDiffRuntimeRegistryHistory):
        raise ValidationError("release gate audit requires a typed history")
    gate_model.verify_gate(gate)
    history_model.verify_history(history)
    expected_summary = (
        gate.gate_id,
        gate.history_id,
        gate.history_address,
        gate_model.address_policy(gate.policy),
        gate.check_count,
        gate.passed_count,
        gate.failed_count,
        gate.release_ready,
        gate.state,
        gate.latest_state,
        gate.latest_accepted,
        gate.entry_count,
        gate.regressed_count,
        gate.blocked_count,
    )
    actual_summary = tuple(getattr(gate.summary, field) for field in gate_model.SUMMARY_FIELDS[:-1])
    checks = (
        _finding(1, "history_link", gate.history_id == history.history_id and gate.history_address == history.content_address, (gate.history_id, gate.history_address), (history.history_id, history.content_address), "gate must link the supplied history"),
        _finding(2, "history_valid", history.content_address.startswith(history_model.HISTORY_PREFIX + ":"), history.content_address, history_model.HISTORY_PREFIX, "history address must be canonical"),
        _finding(3, "policy_address", gate.policy.content_address == gate_model.address_policy(gate.policy), gate.policy.content_address, gate_model.address_policy(gate.policy), "policy address must replay"),
        _finding(4, "gate_check_count", gate.check_count == len(gate_model.CHECK_IDS), gate.check_count, len(gate_model.CHECK_IDS), "gate must contain the fixed check set"),
        _finding(5, "gate_check_ids", tuple(item.check_id for item in gate.checks) == gate_model.CHECK_IDS, tuple(item.check_id for item in gate.checks), gate_model.CHECK_IDS, "gate checks must be ordered and complete"),
        _finding(6, "check_addresses", all(item.content_address == gate_model.address_check(item) for item in gate.checks), "replayed", "canonical", "every gate check address must replay"),
        _finding(7, "check_counters", (gate.passed_count, gate.failed_count) == (sum(item.passed for item in gate.checks), sum(not item.passed for item in gate.checks)), (gate.passed_count, gate.failed_count), "derived counters", "gate counters must conserve checks"),
        _finding(8, "summary_link", actual_summary == expected_summary and gate.summary.content_address == gate_model.address_summary(gate.summary), actual_summary, expected_summary, "summary address and fields must replay"),
        _finding(9, "manifest_link", tuple(gate.manifest.artifact_addresses) == (gate_model.address_checks(gate.checks), gate.summary.content_address), gate.manifest.artifact_addresses, "checks and summary addresses", "manifest must link both component artifacts"),
        _finding(10, "readiness_replay", (gate.release_ready, gate.state) == (gate.failed_count == 0, "ready" if gate.failed_count == 0 else "blocked"), (gate.release_ready, gate.state), "derived readiness", "gate disposition must replay"),
        _finding(11, "history_metrics", (gate.entry_count, gate.regressed_count, gate.blocked_count) == (history.entry_count, history.regressed_count, history.latest_blocked_count), (gate.entry_count, gate.regressed_count, gate.blocked_count), (history.entry_count, history.regressed_count, history.latest_blocked_count), "gate metrics must link history summary"),
        _finding(12, "public_boundary", history_model._public(gate.to_dict()) and history_model._public(history.compact()), True, True, "audit output must remain value-only and path-free"),
    )
    passed = sum(item.passed for item in checks)
    result = GateAudit(gate.gate_id, history.history_id, gate.content_address, history.content_address, checks, len(checks), passed, len(checks) - passed, passed == len(checks), f"pending:{AUDIT_PREFIX}")
    result.content_address = address_audit(result)
    result._validate()
    return result


def audit_from_mapping(value: Mapping[str, Any]) -> GateAudit:
    return GateAudit.from_mapping(value)


def verify_audit(value: GateAudit) -> GateAudit:
    if not isinstance(value, GateAudit):
        raise ValidationError("release gate audit verification requires a typed audit")
    value._validate()
    return value


def audit_json(value: GateAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: GateAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: GateAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Release gate audit {value.gate_id}", "", f"- Accepted: {value.accepted}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| # | check | passed | actual | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.actual} | {item.expected} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "actual": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseGateAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"gate_id": {"type": "string"}, "history_id": {"type": "string"}, "gate_address": {"type": "string"}, "history_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "features": ("independent history linkage replay", "gate address replay", "policy and component linkage", "counter and readiness conservation", "path-free audit findings", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "FINDING_PREFIX", "MAX_CHECKS", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "AuditCheck", "GateAudit", "address_check", "address_audit", "audit_gate", "audit_from_mapping", "verify_audit", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]

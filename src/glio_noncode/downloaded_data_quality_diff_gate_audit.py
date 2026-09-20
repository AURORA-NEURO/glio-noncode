"""Independent conservation audit for downloaded-data quality gates."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-audit"
CHECK_IDS = ("exact-fields", "public-boundary", "diff-linkage", "policy-linkage", "finding-conservation", "finding-order", "outcome-conservation", "direction-conservation", "policy-thresholds", "audit-linkage", "query-linkage", "disposition", "nested-addresses", "content-address", "mapping-round-trip")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("gate_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    namespace, digest = value.split(":", 1)
    if not namespace or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValidationError(f"{field} must be a canonical content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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


class DownloadedDataQualityDiffGateAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality diff gate audit check ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "quality diff gate audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality diff gate audit check ID is unsupported")
        self.passed = _bool(passed, "quality diff gate audit check result")
        self.detail = _text(detail, "quality diff gate audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "quality diff gate audit evidence address") for item in _sequence(evidence_addresses, "quality diff gate audit evidence", 16))
        self.content_address = _address(content_address, "quality diff gate audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality diff gate audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality diff gate audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateAuditCheck":
        value = _mapping(value, "downloaded data quality diff gate audit check")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataQualityDiffGateAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, gate_address: str, checks: Sequence[DownloadedDataQualityDiffGateAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.gate_address = _address(gate_address, "quality diff gate audit gate address", gate_model.GATE_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateAuditCheck) else DownloadedDataQualityDiffGateAuditCheck.from_mapping(item) for item in _sequence(checks, "quality diff gate audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "quality diff gate audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "quality diff gate audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "quality diff gate audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "quality diff gate audit acceptance")
        self.content_address = _address(content_address, "quality diff gate audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality diff gate audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("quality diff gate audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality diff gate audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateAudit":
        value = _mapping(value, "downloaded data quality diff gate audit")
        _strict(value, set(cls.FIELDS), "downloaded data quality diff gate audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataQualityDiffGateAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataQualityDiffGateAuditCheck(**body, content_address=address_check(provisional))


def audit_gate(value: gate_model.DownloadedDataQualityDiffGate) -> DownloadedDataQualityDiffGateAudit:
    """Recompute quality-gate findings, policy counts, and disposition."""

    if not isinstance(value, gate_model.DownloadedDataQualityDiffGate):
        raise ValidationError("quality diff gate audit requires a typed gate")
    expected_findings = tuple(
        gate_model._classify_with_thresholds(item, policy=value.policy, diff=value.diff)
        for item in value.diff.items
    )
    actual_shapes = tuple((item.outcome, item.reason_codes) for item in value.findings)
    expected_shapes = expected_findings
    counts = {outcome: sum(item.outcome == outcome for item in value.findings) for outcome in gate_model.OUTCOMES}
    allowed = sum(item.direction in value.policy.allowed_directions for item in value.findings)
    hard_failure = counts["blocked"] > 0 or value.diff.regressed_count > value.policy.maximum_regressed or (value.policy.require_diff_audit and not value.diff_audit_accepted) or (value.policy.require_query_audit and not value.diff_query_audit_accepted)
    soft_failure = counts["review"] > 0 or value.diff.changed_count > value.policy.maximum_changed or value.diff.added_count > value.policy.maximum_added or value.diff.removed_count > value.policy.maximum_removed or (value.policy.require_complete_query and value.diff_query_truncated)
    expected_state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
    expected_decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[expected_state]
    evidence = (value.content_address, value.diff_address)
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(gate_model.GATE_FIELDS), "gate exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "gate and nested findings contain no forbidden attribution keys", evidence),
        _check(3, "diff-linkage", value.diff_id == value.diff.diff_id and value.diff_address == value.diff.content_address, "gate retains its diff identity and address", (value.diff_address,)),
        _check(4, "policy-linkage", value.policy.content_address.startswith(gate_model.POLICY_PREFIX + ":"), "gate retains its policy address", (value.policy.content_address,)),
        _check(5, "finding-conservation", len(value.findings) == value.finding_count == len(value.diff.items), "gate findings conserve every diff item", evidence),
        _check(6, "finding-order", tuple(item.ordinal for item in value.findings) == tuple(range(1, len(value.findings) + 1)), "gate finding ordinals are contiguous", evidence),
        _check(7, "outcome-conservation", (value.safe_count, value.review_count, value.blocked_count) == (counts["safe"], counts["review"], counts["blocked"]), "gate outcome counts replay", evidence),
        _check(8, "direction-conservation", value.allowed_direction_count == allowed and value.disallowed_direction_count == value.finding_count - allowed, "gate allowed-direction counts replay", evidence),
        _check(9, "policy-thresholds", actual_shapes == expected_shapes, "gate finding outcomes and reason codes replay policy classification", tuple(item.content_address for item in value.findings)),
        _check(10, "audit-linkage", value.diff_audit_address.startswith("glio-noncode-download-quality-diff-audit:") and isinstance(value.diff_audit_accepted, bool), "gate retains diff-audit linkage", (value.diff_audit_address,)),
        _check(11, "query-linkage", value.diff_query_address.startswith("glio-noncode-download-quality-diff-query:") and value.diff_query_audit_address.startswith("glio-noncode-download-quality-diff-query-audit:"), "gate retains query-audit linkage", (value.diff_query_address, value.diff_query_audit_address)),
        _check(12, "disposition", value.state == expected_state and value.decision == expected_decision and value.accepted == (expected_state == "eligible"), "gate state, decision, and acceptance replay", evidence),
        _check(13, "nested-addresses", all(item.diff_item_address in {diff_item.content_address for diff_item in value.diff.items} for item in value.findings) and all(gate_model.address_finding(item) == item.content_address for item in value.findings), "gate finding addresses and diff-item links replay", tuple(item.content_address for item in value.findings)),
        _check(14, "content-address", gate_model.address_gate(value) == value.content_address, "gate content address replays", (value.content_address,)),
        _check(15, "mapping-round-trip", gate_model.gate_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed gate mapping round-trips without projection drift", evidence),
    )
    body = {"gate_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataQualityDiffGateAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateAudit:
    return DownloadedDataQualityDiffGateAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateAudit) -> str:
    return canonical_json(DownloadedDataQualityDiffGateAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateAudit) -> str:
    value = DownloadedDataQualityDiffGateAudit.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateAudit) -> str:
    value = DownloadedDataQualityDiffGateAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate Audit", "", f"- Gate: `{value.gate_address}`", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"gate_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_gate", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataQualityDiffGateAudit", "DownloadedDataQualityDiffGateAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_gate", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

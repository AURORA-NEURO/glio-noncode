"""Independent replay audit for the downloaded-data compatibility gate."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility as compatibility_model
from . import downloaded_data_profile_contract_diff_audit as diff_audit_model
from . import downloaded_data_profile_contract_diff_query as diff_query_model
from . import downloaded_data_profile_contract_diff_query_audit as diff_query_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "diff-linkage",
    "policy-address",
    "finding-conservation",
    "finding-order",
    "classification-replay",
    "outcome-conservation",
    "diff-audit",
    "diff-query-audit",
    "query-completeness",
    "threshold-replay",
    "state-decision",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("gate_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
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


class DownloadedDataProfileContractCompatibilityAuditCheck:
    """One independently recomputed compatibility audit finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "compatibility audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "compatibility audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("compatibility audit check ID is unsupported")
        self.passed = _bool(passed, "compatibility audit check result")
        self.detail = _text(detail, "compatibility audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "compatibility audit evidence address") for item in _sequence(evidence_addresses, "compatibility audit evidence addresses", 16)}))
        if not self.evidence_addresses:
            raise ValidationError("compatibility audit checks require evidence")
        self.content_address = _address(content_address, "compatibility audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("compatibility audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("compatibility audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityAuditCheck:
        value = _mapping(value, "compatibility audit check")
        _strict(value, set(cls.FIELDS), "compatibility audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityAudit:
    """Complete independent audit of a compatibility gate."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, gate_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.gate_address = _address(gate_address, "compatibility audit gate address", compatibility_model.GATE_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityAuditCheck) else DownloadedDataProfileContractCompatibilityAuditCheck.from_mapping(item) for item in _sequence(checks, "compatibility audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "compatibility audit check count", MAX_CHECKS, positive=True)
        self.passed_count = _count(passed_count, "compatibility audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "compatibility audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "compatibility audit acceptance")
        self.content_address = _address(content_address, "compatibility audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("compatibility audit checks are not canonical")
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks):
            raise ValidationError("compatibility audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("compatibility audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("compatibility audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityAudit:
        value = _mapping(value, "compatibility audit")
        _strict(value, set(cls.FIELDS), "compatibility audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityAuditCheck:
    provisional = DownloadedDataProfileContractCompatibilityAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityAuditCheck(ordinal, check_id, passed, detail, provisional.evidence_addresses, address_check(provisional))


def audit_gate(value: compatibility_model.DownloadedDataProfileContractCompatibilityGate) -> DownloadedDataProfileContractCompatibilityAudit:
    """Recompute gate classifications and all nested source receipts."""

    if not isinstance(value, compatibility_model.DownloadedDataProfileContractCompatibilityGate):
        raise ValidationError("compatibility audit requires a typed gate")
    gate = value
    diff = gate.diff
    policy = gate.policy
    diff_audit = diff_audit_model.audit_diff(diff)
    diff_query = diff_query_model.query_diff(diff, resources=diff_query_model.RESOURCES, limit=min(diff_query_model.MAX_LIMIT, diff_query_model.MAX_TOTAL_COUNT))
    diff_query_audit = diff_query_audit_model.audit_query(diff_query)
    expected_findings = tuple(compatibility_model._finding(item, ordinal, policy.allowed_resources) for ordinal, item in enumerate(diff.items, 1))
    expected_counts = tuple(sum(item.outcome == outcome for item in expected_findings) for outcome in compatibility_model.OUTCOMES)
    expected_allowed = sum(item.outcome in policy.allowed_outcomes for item in expected_findings)
    hard_failure = expected_counts[2] > policy.maximum_breaking_findings or any(item.outcome == "breaking" and item.outcome not in policy.allowed_outcomes for item in expected_findings) or (policy.require_diff_audit and not diff_audit.accepted) or (policy.require_diff_query_audit and not diff_query_audit.accepted)
    soft_failure = expected_counts[1] > policy.maximum_review_findings or any(item.outcome == "review" and item.outcome not in policy.allowed_outcomes for item in expected_findings) or (policy.require_complete_diff_query and diff_query.truncated)
    expected_state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
    expected_decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[expected_state]
    evidence = (gate.content_address, diff.content_address, policy.content_address)
    checks = (
        _check(1, "version", gate.version == compatibility_model.VERSION, "compatibility gate uses the current version", evidence),
        _check(2, "boundary", gate.boundary == compatibility_model.BOUNDARY, "compatibility gate uses the public boundary", evidence),
        _check(3, "diff-linkage", gate.diff_id == diff.diff_id and gate.diff_address == diff.content_address, "gate diff identity and address replay", (gate.diff_address,)),
        _check(4, "policy-address", compatibility_model.address_policy(policy) == policy.content_address, "policy content address replays", (policy.content_address,)),
        _check(5, "finding-conservation", len(gate.findings) == len(diff.items) == gate.finding_count == len(expected_findings), "one compatibility finding is retained for every diff item", (gate.diff_address,)),
        _check(6, "finding-order", tuple(item.ordinal for item in gate.findings) == tuple(range(1, gate.finding_count + 1)) and tuple(item.content_address for item in gate.findings) == tuple(item.content_address for item in expected_findings), "finding order and addresses replay independently", tuple(item.content_address for item in gate.findings)[:8] or evidence),
        _check(7, "classification-replay", tuple(item.to_dict() for item in gate.findings) == tuple(item.to_dict() for item in expected_findings), "structural outcome and reason classification replays", tuple(item.content_address for item in gate.findings)[:8] or evidence),
        _check(8, "outcome-conservation", (gate.safe_count, gate.review_count, gate.breaking_count, gate.allowed_outcome_count, gate.disallowed_outcome_count) == (expected_counts[0], expected_counts[1], expected_counts[2], expected_allowed, len(expected_findings) - expected_allowed), "outcome counters conserve findings", evidence),
        _check(9, "diff-audit", gate.diff_audit_address == diff_audit.content_address and gate.diff_audit_accepted == diff_audit.accepted, "nested diff audit links and accepts", (gate.diff_audit_address,)),
        _check(10, "diff-query-audit", gate.diff_query_address == diff_query.content_address and gate.diff_query_audit_address == diff_query_audit.content_address and gate.diff_query_audit_accepted == diff_query_audit.accepted, "nested diff query audit links and accepts", (gate.diff_query_address, gate.diff_query_audit_address)),
        _check(11, "query-completeness", gate.diff_query_truncated == diff_query.truncated and ((not policy.require_complete_diff_query) or not diff_query.truncated), "diff query truncation follows policy", (gate.diff_query_address, policy.content_address)),
        _check(12, "threshold-replay", gate.state == expected_state and gate.decision == expected_decision and gate.accepted == (expected_state == "eligible"), "policy thresholds replay the disposition", (policy.content_address, gate.content_address)),
        _check(13, "state-decision", (gate.accepted, gate.state, gate.decision) == (expected_state == "eligible", expected_state, expected_decision), "state, decision, and acceptance agree", (gate.content_address,)),
        _check(14, "public-boundary", _public(gate.to_dict()), "gate and nested receipts remain value-free and public", evidence),
        _check(15, "mapping-round-trip", compatibility_model.compatibility_from_mapping(gate.to_dict()).to_dict() == gate.to_dict(), "gate mapping replay is lossless", (gate.content_address,)),
    )
    body = {"gate_address": gate.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileContractCompatibilityAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityAudit:
    return DownloadedDataProfileContractCompatibilityAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityAudit) -> str:
    return canonical_json(DownloadedDataProfileContractCompatibilityAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityAudit) -> str:
    value = DownloadedDataProfileContractCompatibilityAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Audit", "", f"- Gate: `{value.gate_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"gate_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "checks": CHECK_IDS, "operations": ("audit_gate", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityAudit", "DownloadedDataProfileContractCompatibilityAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_gate", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

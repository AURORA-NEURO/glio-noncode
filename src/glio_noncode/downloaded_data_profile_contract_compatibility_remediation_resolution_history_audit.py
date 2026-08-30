"""Independent assurance for remediation-resolution history ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "entry-order",
    "ancestry-links",
    "latest-linkage",
    "transition-replay",
    "transition-counts",
    "aggregate-replay",
    "resolution-addresses",
    "entry-addresses",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "history audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "history audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history audit check ID is unsupported")
        self.passed = _bool(passed, "history audit check result")
        self.detail = _text(detail, "history audit check detail", 1024)
        self.evidence_addresses = tuple(sorted({_address(item, "history audit evidence address") for item in _sequence(evidence_addresses, "history audit evidence addresses", 8)}))
        if not self.evidence_addresses:
            raise ValidationError("history audit checks require evidence")
        self.content_address = _address(content_address, "history audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck:
        value = _mapping(value, "history audit check")
        _strict(value, set(cls.FIELDS), "history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck):
        raise ValidationError("history audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, history_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_address = _address(history_address, "history audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck.from_mapping(item) for item in _sequence(checks, "history audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history audit acceptance")
        self.content_address = _address(content_address, "history audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)):
            raise ValidationError("history audit check order is not conserved")
        if tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("history audit checks are incomplete or unordered")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("history audit counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit:
        value = _mapping(value, "history audit")
        _strict(value, set(cls.FIELDS), "history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit):
        raise ValidationError("history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence) or (history_model.HISTORY_PREFIX + ":empty",), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _transition(current: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry, previous: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryEntry | None) -> str:
    if previous is None:
        return "initial"
    if current.required_open_count < previous.required_open_count:
        return "improved"
    if current.required_open_count > previous.required_open_count:
        return "regressed"
    ranks = {"clear": 0, "review": 1, "blocked": 2}
    if ranks[current.state] < ranks[previous.state]:
        return "improved"
    if ranks[current.state] > ranks[previous.state]:
        return "regressed"
    return "unchanged"


def audit_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit:
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistory):
        raise ValidationError("history audit requires a typed history")
    entries = value.entries
    expected_state = "empty" if not entries else "blocked" if entries[-1].state == "blocked" else "clear" if entries[-1].release_ready else "review"
    expected_decision = {"empty": "hold", "clear": "promote", "review": "hold", "blocked": "block"}[expected_state]
    replayed = tuple(_transition(item, entries[index - 1] if index else None) for index, item in enumerate(entries))
    checks = (
        _check(1, "version", value.version == history_model.VERSION, "history version is current", (value.content_address,)),
        _check(2, "boundary", value.boundary == history_model.BOUNDARY, "history boundary is public and value-free", (value.content_address,)),
        _check(3, "entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), "history entries retain append order", tuple(item.content_address for item in entries[:8]) or (value.content_address,)),
        _check(4, "ancestry-links", all(index == 0 or item.previous_resolution_address == entries[index - 1].resolution_address for index, item in enumerate(entries)), "each snapshot links to the immediately previous snapshot", tuple(item.content_address for item in entries[:8]) or (value.content_address,)),
        _check(5, "latest-linkage", (value.latest_resolution_address, value.latest_required_open_count) == ((entries[-1].resolution_address, entries[-1].required_open_count) if entries else ("", 0)), "latest snapshot linkage replays", (value.content_address,)),
        _check(6, "transition-replay", tuple(item.transition for item in entries) == replayed, "trend transitions replay from adjacent summaries", tuple(item.content_address for item in entries[:8]) or (value.content_address,)),
        _check(7, "transition-counts", tuple(sum(item.transition == transition for item in entries) for transition in history_model.TRANSITIONS) == (value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count), "transition totals are conserved", (value.content_address,)),
        _check(8, "aggregate-replay", (value.state, value.decision, value.accepted, value.release_ready) == (expected_state, expected_decision, expected_state == "clear", expected_state == "clear"), "latest state folds into the history disposition", (value.content_address,)),
        _check(9, "resolution-addresses", len({item.resolution_address for item in entries}) == len(entries) and all(item.resolution_address.startswith("glio-noncode-download-profile-contract-compatibility-remediation-resolution:") for item in entries), "resolution snapshots are unique addressed references", tuple(item.resolution_address for item in entries[:8]) or (value.content_address,)),
        _check(10, "entry-addresses", all(history_model.address_entry(item) == item.content_address for item in entries), "every history entry has a stable content address", tuple(item.content_address for item in entries[:8]) or (value.content_address,)),
        _check(11, "public-boundary", _public(value.to_dict()), "history contains no forbidden public metadata", (value.content_address,)),
        _check(12, "mapping-round-trip", history_model.history_from_mapping(value.to_dict()).content_address == value.content_address, "history mapping round-trips to the same address", (value.content_address,)),
    )
    passed = sum(item.passed for item in checks)
    body = {"history_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": passed, "failed_count": len(checks) - passed, "accepted": passed == len(checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(";".join(item.evidence_addresses) if field == "evidence_addresses" else item.to_dict()[field] for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Audit", "", f"- History: `{value.history_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"history_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_history", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": MAX_CHECKS}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAudit", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_history", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

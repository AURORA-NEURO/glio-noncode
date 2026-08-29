"""Independent audit for append-only consensus gate histories."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as gate_audit_model
from . import registry_federation_consensus_gate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
FINDING_PREFIX = history_model.HISTORY_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "entry-conservation", "ordinal-conservation", "counter-conservation", "history-address-vocabulary", "entry-addresses", "unique-history-evidence", "mapping-round-trip", "history-address", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = history_model.MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateHistoryAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history audit finding ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "history audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history audit check ID is unsupported")
        self.passed = _bool(passed, "history audit finding result")
        self.observed = _text(observed, "history audit observed value")
        self.expected = _text(expected, "history audit expected value")
        self.detail = _text(detail, "history audit detail", required=True)
        self.content_address = _address(content_address, "history audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("history audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateHistoryAuditFinding:
        value = _mapping(value, "history audit finding")
        _strict(value, set(cls.FIELDS), "history audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateHistoryAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusGateHistoryAuditFinding):
        raise ValidationError("history audit finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateHistoryAudit:
    FIELDS = ("history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, history_address: str, checks: Sequence[RegistryFederationConsensusGateHistoryAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_address = _address(history_address, "audited history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateHistoryAuditFinding) for item in self.checks):
            raise ValidationError("history audit checks must be typed")
        self.check_count = _count(check_count, "history audit check count", len(CHECK_IDS), positive=True)
        self.passed_count = _count(passed_count, "history audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "history audit failed count", self.check_count)
        self.accepted = _bool(accepted, "history audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("history audit counters are not conserved")
        self.content_address = _address(content_address, "history audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateHistoryAudit:
        value = _mapping(value, "consensus gate history audit")
        _strict(value, set(cls.FIELDS), "consensus gate history audit")
        return cls(value["history_address"], tuple(RegistryFederationConsensusGateHistoryAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateHistoryAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusGateHistoryAudit):
        raise ValidationError("history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateHistoryAuditFinding:
    provisional = RegistryFederationConsensusGateHistoryAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateHistoryAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_history(value: history_model.RegistryFederationConsensusGateHistory) -> RegistryFederationConsensusGateHistoryAudit:
    value = history_model.verify_history(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(history_model.RegistryFederationConsensusGateHistory.FIELDS), tuple(sorted(value.to_dict())), history_model.RegistryFederationConsensusGateHistory.FIELDS, "history fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "history is public and path-free"),
        _finding(3, "entry-conservation", len(value.entries) == value.entry_count, (len(value.entries), value.entry_count), "entry count", "entries match count"),
        _finding(4, "ordinal-conservation", tuple(item.ordinal for item in value.entries) == tuple(range(1, value.entry_count + 1)), tuple(item.ordinal for item in value.entries), tuple(range(1, value.entry_count + 1)), "entry ordinals are contiguous"),
        _finding(5, "counter-conservation", value.accepted_count == sum(item.accepted for item in value.entries) and value.review_count == sum(item.state == "review" for item in value.entries) and value.blocked_count == sum(item.state == "blocked" for item in value.entries), (value.accepted_count, value.review_count, value.blocked_count), "replayed history counters", "history counters replay"),
        _finding(6, "history-address-vocabulary", value.content_address.startswith(history_model.HISTORY_PREFIX + ":"), value.content_address, history_model.HISTORY_PREFIX + ":", "history address vocabulary is fixed"),
        _finding(7, "entry-addresses", all(history_model.address_entry(item) == item.content_address for item in value.entries), "replayed entry addresses", "stored entry addresses", "every entry address replays"),
        _finding(8, "unique-history-evidence", len({item.gate_address for item in value.entries}) == value.entry_count and len({item.audit_address for item in value.entries}) == value.entry_count and all(item.gate_address.startswith(gate_model.GATE_PREFIX + ":") and item.audit_address.startswith(gate_audit_model.AUDIT_PREFIX + ":") for item in value.entries), "unique gate and audit addresses", "unique gate and audit addresses", "entry evidence remains distinct"),
        _finding(9, "mapping-round-trip", history_model.history_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original history", "mapping conversion is lossless"),
        _finding(10, "history-address", history_model.address_history(value) == value.content_address, value.content_address, history_model.address_history(value), "history content address replays"),
        _finding(11, "content-address", value.content_address.startswith(history_model.HISTORY_PREFIX + ":"), value.content_address, history_model.HISTORY_PREFIX + ":", "history uses the history namespace"),
        _finding(12, "path-free", _public(value.to_dict()), True, True, "history contains no local paths or private execution text"),
    )
    provisional = RegistryFederationConsensusGateHistoryAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateHistoryAudit(provisional.history_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateHistoryAudit:
    return verify_audit(RegistryFederationConsensusGateHistoryAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateHistoryAudit) -> RegistryFederationConsensusGateHistoryAudit:
    if not isinstance(value, RegistryFederationConsensusGateHistoryAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("consensus gate history audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateHistoryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateHistoryAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateHistoryAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateHistoryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Consensus Gate History Audit", "", f"- History: `{value.history_address}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateHistoryAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateHistoryAudit.FIELDS), "properties": {"history_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent append-only history checks", "entry ordering and counter conservation", "history evidence verification", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateHistoryAudit", "RegistryFederationConsensusGateHistoryAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_history", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]

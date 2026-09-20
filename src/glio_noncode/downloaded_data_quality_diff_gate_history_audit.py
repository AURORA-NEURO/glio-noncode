"""Independent replay audit for downloaded-data quality diff gate history."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_quality_diff_gate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-quality-diff-gate-history-audit-v1"
BOUNDARY = "public_downloaded_data_quality_diff_gate_history_audit"
AUDIT_PREFIX = "glio-noncode-download-quality-diff-gate-history-audit"
CHECK_IDS = (
    "exact-fields", "public-boundary", "version-boundary", "entry-order",
    "gate-linkage", "snapshot-uniqueness", "ancestry", "head", "decision-counts",
    "entry-readiness", "transition-replay", "state", "history-acceptance",
    "nested-addresses", "content-address", "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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
    if not namespace or (digest != "initial" and (len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest))):
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


class DownloadedDataQualityDiffGateHistoryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "quality gate history audit check ordinal", len(CHECK_IDS), positive=True)
        self.check_id = _label(check_id, "quality gate history audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("quality gate history audit check ID is unsupported")
        self.passed = _bool(passed, "quality gate history audit result")
        self.detail = _text(detail, "quality gate history audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "quality gate history audit evidence address") for item in _sequence(evidence_addresses, "quality gate history audit evidence", 24))
        self.content_address = _address(content_address, "quality gate history audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "quality gate history audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("quality gate history audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("quality gate history audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateHistoryAuditCheck":
        value = _mapping(value, "quality gate history audit check")
        _strict(value, set(cls.FIELDS), "quality gate history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataQualityDiffGateHistoryAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataQualityDiffGateHistoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, history_address: str, checks: Sequence[DownloadedDataQualityDiffGateHistoryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_address = _address(history_address, "quality gate history audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataQualityDiffGateHistoryAuditCheck) else DownloadedDataQualityDiffGateHistoryAuditCheck.from_mapping(item) for item in _sequence(checks, "quality gate history audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "quality gate history audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "quality gate history audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "quality gate history audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "quality gate history audit acceptance")
        self.content_address = _address(content_address, "quality gate history audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "quality gate history audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("quality gate history audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("quality gate history audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DownloadedDataQualityDiffGateHistoryAudit":
        value = _mapping(value, "quality gate history audit")
        _strict(value, set(cls.FIELDS), "quality gate history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataQualityDiffGateHistoryAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataQualityDiffGateHistoryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:24]}
    provisional = DownloadedDataQualityDiffGateHistoryAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataQualityDiffGateHistoryAuditCheck(**body, content_address=address_check(provisional))


def _transition(previous: history_model.DownloadedDataQualityDiffGateHistoryEntry | None, current: history_model.DownloadedDataQualityDiffGateHistoryEntry) -> str:
    if previous is None:
        return "initial"
    previous_score = history_model.STATE_SCORE[previous.state]
    current_score = history_model.STATE_SCORE[current.state]
    if current_score > previous_score:
        return "improved"
    if current_score < previous_score:
        return "regressed"
    comparable = ("gate_id", "decision", "state", "accepted", "release_ready", "finding_count", "safe_count", "review_count", "blocked_count", "policy_address")
    return "unchanged" if all(getattr(previous, field) == getattr(current, field) for field in comparable) else "changed"


def audit_history(value: history_model.DownloadedDataQualityDiffGateHistory) -> DownloadedDataQualityDiffGateHistoryAudit:
    if not isinstance(value, history_model.DownloadedDataQualityDiffGateHistory):
        raise ValidationError("quality gate history audit requires a typed history")
    evidence = (value.content_address, value.head_address)
    entries = value.entries
    expected_transitions = tuple(_transition(None if index == 0 else entries[index - 1], entry) for index, entry in enumerate(entries))
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(history_model.HISTORY_FIELDS), "history exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "history and entries contain no forbidden attribution keys", evidence),
        _check(3, "version-boundary", value.version == history_model.VERSION and value.boundary == history_model.BOUNDARY, "history version and boundary are current", evidence),
        _check(4, "entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), "history entry ordinals are contiguous", evidence),
        _check(5, "gate-linkage", all(item.gate_id == value.gate_id for item in entries), "history entries retain the history gate identity", evidence),
        _check(6, "snapshot-uniqueness", len({item.snapshot_id for item in entries}) == len(entries), "history snapshot identities are unique", evidence),
        _check(7, "ancestry", (not entries or entries[0].previous_entry_address == history_model.INITIAL_HEAD) and all(item.previous_entry_address == entries[index - 1].content_address for index, item in enumerate(entries) if index > 0), "history entry ancestry is contiguous", tuple(item.content_address for item in entries)),
        _check(8, "head", value.head_address == (history_model.INITIAL_HEAD if not entries else entries[-1].content_address), "history head points to the latest entry", (value.head_address,)),
        _check(9, "decision-counts", (value.promote_count, value.hold_count, value.block_count, value.accepted_count, value.release_ready_count) == (sum(item.decision == "promote" for item in entries), sum(item.decision == "hold" for item in entries), sum(item.decision == "block" for item in entries), sum(item.accepted for item in entries), sum(item.release_ready for item in entries)), "history decision counters are conserved", evidence),
        _check(10, "entry-readiness", all(item.accepted == (item.decision == "promote") and item.release_ready == item.accepted for item in entries), "entry decision and readiness projections replay", tuple(item.content_address for item in entries)),
        _check(11, "transition-replay", tuple(item.transition for item in entries) == expected_transitions, "history transitions replay from adjacent snapshots", tuple(item.content_address for item in entries)),
        _check(12, "state", value.state == ("empty" if not entries else entries[-1].state), "history state follows the latest snapshot", evidence),
        _check(13, "history-acceptance", value.accepted == bool(entries) and value.release_ready == (False if not entries else entries[-1].release_ready), "history acceptance and latest readiness replay", evidence),
        _check(14, "nested-addresses", all(item.content_address.startswith(history_model.ENTRY_PREFIX + ":") for item in entries), "entry content addresses retain the history namespace", tuple(item.content_address for item in entries)),
        _check(15, "content-address", history_model.address_history(value) == value.content_address, "history content address replays", evidence),
        _check(16, "mapping-round-trip", history_model.history_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed history mapping round-trips without projection drift", evidence),
    )
    body = {"history_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataQualityDiffGateHistoryAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataQualityDiffGateHistoryAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataQualityDiffGateHistoryAudit:
    return DownloadedDataQualityDiffGateHistoryAudit.from_mapping(value)


def audit_json(value: DownloadedDataQualityDiffGateHistoryAudit) -> str:
    return canonical_json(DownloadedDataQualityDiffGateHistoryAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataQualityDiffGateHistoryAudit) -> str:
    value = DownloadedDataQualityDiffGateHistoryAudit.from_mapping(value.to_dict())
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataQualityDiffGateHistoryAudit) -> str:
    value = DownloadedDataQualityDiffGateHistoryAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Quality Diff Gate History Audit", "", f"- History: `{value.history_address}`", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", "", "| ordinal | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {item.ordinal} | {item.check_id} | {item.passed} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate history audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data quality diff gate history audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"history_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_history", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown")}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataQualityDiffGateHistoryAudit", "DownloadedDataQualityDiffGateHistoryAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_history", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]

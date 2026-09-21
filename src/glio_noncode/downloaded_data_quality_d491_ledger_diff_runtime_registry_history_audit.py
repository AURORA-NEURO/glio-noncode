"""Independent replay audit for D491 registry histories."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from . import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_history", "history_address", "entry_sequence", "transition_sequence", "counter_replay", "latest_replay", "summary_replay", "manifest_replay", "unique_snapshots", "unique_registry_addresses", "chain_replay", "registry_links", "artifact_addresses", "entry_addresses", "public_boundary", "canonical_history")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("history_id", "audit_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class AuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "ledger diff runtime registry history audit ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "ledger diff runtime registry history audit check ID")
        self.passed = _bool(passed, "ledger diff runtime registry history audit result")
        self.actual = _text(actual, "ledger diff runtime registry history audit actual", 32768)
        self.expected = _text(expected, "ledger diff runtime registry history audit expected", 32768)
        self.detail = _text(detail, "ledger diff runtime registry history audit detail", 4096)
        self.content_address = _address(content_address, "ledger diff runtime registry history audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("ledger diff runtime registry history audit check identity is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry history audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry history audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "ledger diff runtime registry history audit check")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck):
        raise ValidationError("ledger diff runtime registry history audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class HistoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, history_id: str, audit_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_id = _label(history_id, "ledger diff runtime registry history audit history ID")
        self.audit_address = _address(audit_address, "ledger diff runtime registry history audit address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, AuditCheck) else AuditCheck.from_mapping(_mapping(item, "ledger diff runtime registry history audit check")) for item in _sequence(checks, "ledger diff runtime registry history audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger diff runtime registry history audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "ledger diff runtime registry history audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "ledger diff runtime registry history audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "ledger diff runtime registry history audit acceptance")
        self.content_address = _address(content_address, "ledger diff runtime registry history audit content address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("ledger diff runtime registry history audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("ledger diff runtime registry history audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("ledger diff runtime registry history audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("ledger diff runtime registry history audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "audit_address": self.audit_address, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoryAudit":
        value = _mapping(value, "ledger diff runtime registry history audit")
        _strict(value, set(cls.FIELDS), "ledger diff runtime registry history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: HistoryAudit) -> str:
    if not isinstance(value, HistoryAudit):
        raise ValidationError("ledger diff runtime registry history audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}
    provisional = AuditCheck(**body)
    return AuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_history(value: history_model.RuntimeRegistryHistory, registries: Sequence[registry_model.RuntimeRegistry] | None = None) -> HistoryAudit:
    history_model.verify_history(value)
    supplied = None if registries is None else tuple(registries)
    if supplied is not None:
        if len(supplied) != value.entry_count:
            raise ValidationError("ledger diff runtime registry history audit inputs do not match entry count")
        for item in supplied:
            registry_model.verify_registry(item)
    identity = supplied is None or tuple((item.registry_id, item.content_address) for item in supplied) == tuple((entry.registry_id, entry.registry_address) for entry in value.entries)
    links = supplied is None or all(item.registry_id == entry.registry_id and item.content_address == entry.registry_address and item.state == entry.state and item.release_ready == entry.release_ready for item, entry in zip(supplied, value.entries, strict=True))
    chain = all(index == 1 or item.previous_address == value.entries[index - 2].content_address for index, item in enumerate(value.entries, 1))
    latest = value.entries[-1] if value.entries else None
    checks = (
        _finding(1, "typed_history", isinstance(value, history_model.RuntimeRegistryHistory), type(value).__name__, "RuntimeRegistryHistory", "the audited value must use the typed history model"),
        _finding(2, "history_address", value.content_address == history_model.address_history(value), value.content_address, history_model.address_history(value), "history address must replay"),
        _finding(3, "entry_sequence", tuple(item.ordinal for item in value.entries) == tuple(range(1, value.entry_count + 1)), [item.ordinal for item in value.entries], "contiguous entry ordinals", "history entries must preserve canonical order"),
        _finding(4, "transition_sequence", tuple(item.transition for item in value.entries), [item.transition for item in value.entries], "initial followed by valid transitions", "transition vocabulary must be retained"),
        _finding(5, "counter_replay", (value.initial_count, value.promoted_count, value.regressed_count, value.unchanged_count, value.changed_count) == tuple(sum(item.transition == transition for item in value.entries) for transition in history_model.TRANSITIONS), value.to_dict(), "replayed transition counters", "history counters must derive from entries"),
        _finding(6, "latest_replay", latest is None or (value.latest_state, value.latest_release_ready, value.latest_accepted) == (latest.state, latest.release_ready, latest.accepted_count == latest.entry_count), (value.latest_state, value.latest_release_ready, value.latest_accepted), "latest entry disposition", "latest state must derive from the history head"),
        _finding(7, "summary_replay", value.summary.content_address == history_model.address_summary(value.summary), value.summary.content_address, history_model.address_summary(value.summary), "summary address must replay"),
        _finding(8, "manifest_replay", value.manifest.content_address == history_model.address_manifest(value.manifest), value.manifest.content_address, history_model.address_manifest(value.manifest), "manifest address must replay"),
        _finding(9, "unique_snapshots", len({item.snapshot_id for item in value.entries}) == value.entry_count, [item.snapshot_id for item in value.entries], "unique snapshot IDs", "snapshot identities must remain unique"),
        _finding(10, "unique_registry_addresses", len({item.registry_address for item in value.entries}) == value.entry_count, [item.registry_address for item in value.entries], "unique registry addresses", "registry snapshots must remain unique"),
        _finding(11, "chain_replay", chain, [item.previous_address for item in value.entries], "predecessor address chain", "each snapshot must point to the prior head"),
        _finding(12, "registry_links", links, True, "supplied registry lineage", "supplied registries must match retained snapshots"),
        _finding(13, "artifact_addresses", value.manifest.artifact_addresses == (history_model.address_entries(value.entries), value.summary.content_address), value.manifest.artifact_addresses, "entries and summary addresses", "manifest artifacts must replay"),
        _finding(14, "entry_addresses", all(history_model.address_entry(item) == item.content_address for item in value.entries), True, "replayed entry addresses", "entry addresses must replay"),
        _finding(15, "public_boundary", _public(value.to_dict()), True, "public value", "history artifacts must contain no private records"),
        _finding(16, "canonical_history", canonical_json(value.to_dict()) == canonical_json(history_model.history_from_mapping(_strict_json_loads(history_model.history_json(value))).to_dict()), True, "canonical round-trip", "history serialization must be deterministic"),
    )
    provisional = HistoryAudit(value.history_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(provisional, address_audit)


def verify_audit(value: HistoryAudit) -> HistoryAudit:
    if not isinstance(value, HistoryAudit):
        raise ValidationError("ledger diff runtime registry history audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> HistoryAudit:
    return HistoryAudit.from_mapping(value)


def audit_json(value: HistoryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: HistoryAudit) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(item.to_dict() for item in verify_audit(value).checks)
    return output.getvalue()


def render_audit_markdown(value: HistoryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Ledger diff runtime registry history audit {value.history_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeRegistryHistoryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent D491 registry history replay", "ancestry and latest-state verification", "canonical address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "HistoryAudit", "address_check", "address_audit", "audit_history", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]

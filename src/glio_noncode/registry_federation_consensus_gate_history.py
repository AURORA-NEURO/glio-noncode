"""Append-only history of consensus release-gate decisions."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from . import registry_federation_consensus_gate_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = gate_model.VERSION + "-history-v1"
BOUNDARY = gate_model.BOUNDARY + "_history"
HISTORY_PREFIX = gate_model.GATE_PREFIX + "-history"
ENTRY_PREFIX = gate_model.GATE_PREFIX + "-history-entry"
MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME)
MAX_ENTRIES = 256
MAX_TEXT = gate_model.MAX_TEXT


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    addresses = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(addresses))


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


class RegistryFederationConsensusGateHistoryEntry:
    FIELDS = ("ordinal", "gate_id", "runtime_id", "gate_address", "audit_address", "state", "decision", "accepted", "check_count", "failed_count", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, gate_id: str, runtime_id: str, gate_address: str, audit_address: str, state: str, decision: str, accepted: bool, check_count: int, failed_count: int, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate history entry ordinal", MAX_ENTRIES, positive=True)
        self.gate_id = _label(gate_id, "history gate ID")
        self.runtime_id = _label(runtime_id, "history runtime ID")
        self.gate_address = _address(gate_address, "history gate address", gate_model.GATE_PREFIX)
        self.audit_address = _address(audit_address, "history audit address", audit_model.AUDIT_PREFIX)
        if state not in gate_model.GATE_STATES or decision not in gate_model.GATE_DECISIONS:
            raise ValidationError("history entry disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "history entry acceptance")
        self.check_count = _count(check_count, "history entry check count", gate_model.MAX_CHECKS, positive=True)
        self.failed_count = _count(failed_count, "history entry failed count", self.check_count)
        self.evidence_addresses = _addresses(evidence_addresses, "history entry evidence addresses", 8)
        if not self.evidence_addresses:
            raise ValidationError("history entries require evidence")
        self.content_address = _address(content_address, "history entry content address", ENTRY_PREFIX)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("history entry content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateHistoryEntry:
        value = _mapping(value, "gate history entry")
        _strict(value, set(cls.FIELDS), "gate history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryFederationConsensusGateHistoryEntry) -> str:
    if not isinstance(value, RegistryFederationConsensusGateHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class RegistryFederationConsensusGateHistory:
    FIELDS = ("history_id", "entries", "entry_count", "accepted_count", "review_count", "blocked_count", "content_address")

    def __init__(self, history_id: str, entries: Sequence[RegistryFederationConsensusGateHistoryEntry], entry_count: int, accepted_count: int, review_count: int, blocked_count: int, content_address: str) -> None:
        self.history_id = _label(history_id, "gate history ID")
        self.entries = tuple(entries)
        if len(self.entries) > MAX_ENTRIES or any(not isinstance(item, RegistryFederationConsensusGateHistoryEntry) for item in self.entries):
            raise ValidationError("gate history entries are outside the bound")
        self.entry_count = _count(entry_count, "gate history entry count", MAX_ENTRIES, positive=True)
        self.accepted_count = _count(accepted_count, "gate history accepted count", self.entry_count)
        self.review_count = _count(review_count, "gate history review count", self.entry_count)
        self.blocked_count = _count(blocked_count, "gate history blocked count", self.entry_count)
        if len(self.entries) != self.entry_count or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or self.accepted_count != sum(item.accepted for item in self.entries) or self.blocked_count != sum(item.state == "blocked" for item in self.entries) or self.review_count != sum(item.state == "review" for item in self.entries):
            raise ValidationError("gate history counters are not conserved")
        self.content_address = _address(content_address, "gate history content address", HISTORY_PREFIX)
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("gate history content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "entries": tuple(item.to_dict() for item in self.entries), "entry_count": self.entry_count, "accepted_count": self.accepted_count, "review_count": self.review_count, "blocked_count": self.blocked_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateHistory:
        value = _mapping(value, "consensus gate history")
        _strict(value, set(cls.FIELDS), "consensus gate history")
        return cls(value["history_id"], tuple(RegistryFederationConsensusGateHistoryEntry.from_mapping(item) for item in value["entries"]), value["entry_count"], value["accepted_count"], value["review_count"], value["blocked_count"], value["content_address"])


def address_history(value: RegistryFederationConsensusGateHistory) -> str:
    if not isinstance(value, RegistryFederationConsensusGateHistory):
        raise ValidationError("gate history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _entry(ordinal: int, gate: gate_model.RegistryFederationConsensusGate, audit: audit_model.RegistryFederationConsensusGateAudit) -> RegistryFederationConsensusGateHistoryEntry:
    evidence = (gate.content_address, audit.content_address, gate.runtime_address, gate.consensus_address)
    provisional = RegistryFederationConsensusGateHistoryEntry(ordinal, gate.gate_id, gate.runtime_id, gate.content_address, audit.content_address, gate.state, gate.decision, gate.accepted, gate.check_count, gate.failed_count, evidence, ENTRY_PREFIX + ":pending")
    return RegistryFederationConsensusGateHistoryEntry(provisional.ordinal, provisional.gate_id, provisional.runtime_id, provisional.gate_address, provisional.audit_address, provisional.state, provisional.decision, provisional.accepted, provisional.check_count, provisional.failed_count, provisional.evidence_addresses, address_entry(provisional))


def build_history(values: Sequence[tuple[gate_model.RegistryFederationConsensusGate, audit_model.RegistryFederationConsensusGateAudit]], *, history_id: str = "consensus-gate-history") -> RegistryFederationConsensusGateHistory:
    values = _sequence(values, "gate history values", MAX_ENTRIES)
    entries: list[RegistryFederationConsensusGateHistoryEntry] = []
    for gate, audit in values:
        gate = gate_model.verify_gate(gate)
        audit = audit_model.verify_audit(audit)
        if audit.gate_address != gate.content_address:
            raise ValidationError("gate history audit does not refer to gate")
        entries.append(_entry(len(entries) + 1, gate, audit))
    if not entries:
        raise ValidationError("gate history requires at least one entry")
    provisional = RegistryFederationConsensusGateHistory(history_id, tuple(entries), len(entries), sum(item.accepted for item in entries), sum(item.state == "review" for item in entries), sum(item.state == "blocked" for item in entries), HISTORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateHistory(provisional.history_id, provisional.entries, provisional.entry_count, provisional.accepted_count, provisional.review_count, provisional.blocked_count, address_history(provisional))


def append_history(value: RegistryFederationConsensusGateHistory, gate: gate_model.RegistryFederationConsensusGate, audit: audit_model.RegistryFederationConsensusGateAudit) -> RegistryFederationConsensusGateHistory:
    value = verify_history(value)
    if value.entry_count >= MAX_ENTRIES:
        raise ValidationError("gate history is at capacity")
    gate = gate_model.verify_gate(gate)
    audit = audit_model.verify_audit(audit)
    if audit.gate_address != gate.content_address:
        raise ValidationError("appended audit does not refer to gate")
    entry = _entry(value.entry_count + 1, gate, audit)
    entries = (*value.entries, entry)
    provisional = RegistryFederationConsensusGateHistory(value.history_id, entries, len(entries), sum(item.accepted for item in entries), sum(item.state == "review" for item in entries), sum(item.state == "blocked" for item in entries), HISTORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateHistory(provisional.history_id, provisional.entries, provisional.entry_count, provisional.accepted_count, provisional.review_count, provisional.blocked_count, address_history(provisional))


def history_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateHistory:
    return verify_history(RegistryFederationConsensusGateHistory.from_mapping(value))


def verify_history(value: RegistryFederationConsensusGateHistory) -> RegistryFederationConsensusGateHistory:
    if not isinstance(value, RegistryFederationConsensusGateHistory) or (not value.content_address.endswith(":pending") and address_history(value) != value.content_address):
        raise ValidationError("consensus gate history is not valid")
    return value


def history_json(value: RegistryFederationConsensusGateHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def history_csv(value: RegistryFederationConsensusGateHistory) -> str:
    value = verify_history(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateHistoryEntry.FIELDS, lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        row = entry.to_dict()
        row["evidence_addresses"] = "|".join(entry.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_history_markdown(value: RegistryFederationConsensusGateHistory) -> str:
    value = verify_history(value)
    lines = ["# Consensus Release Gate History", "", f"- History: `{value.history_id}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}`", f"- Review: `{value.review_count}`", f"- Blocked: `{value.blocked_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | gate | state | decision | accepted | failed |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.gate_id}` | `{item.state}` | `{item.decision}` | `{item.accepted}` | `{item.failed_count}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _manifest(value: RegistryFederationConsensusGateHistory) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "files": tuple(sorted(FILES)), "history_address": value.content_address, "entry_count": value.entry_count}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=HISTORY_PREFIX + "-manifest")}


def history_bytes(value: RegistryFederationConsensusGateHistory) -> dict[str, bytes]:
    value = verify_history(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), HISTORY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes(tuple(item.to_dict() for item in value.entries))}


def write_history(value: RegistryFederationConsensusGateHistory, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("gate history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="consensus-gate-history-staging-", dir=str(destination.parent)))
        for name, raw in history_bytes(value).items():
            (staging / name).write_bytes(raw)
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
    return destination


def load_history(directory: str | Path) -> RegistryFederationConsensusGateHistory:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("gate history directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("gate history member is not canonical JSON")
    value = history_from_mapping(decoded[HISTORY_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)) or canonical_bytes(decoded[ENTRIES_NAME]) != canonical_bytes(tuple(item.to_dict() for item in value.entries)):
        raise ValidationError("gate history projections do not replay")
    return value


def verify_history_directory(directory: str | Path) -> RegistryFederationConsensusGateHistory:
    return load_history(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "history_id", "files", "history_address", "entry_count", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "history_id": {"type": "string"}, "files": {"type": "array"}, "history_address": {"type": "string"}, "entry_count": {"type": "integer"}, "manifest_address": {"type": "string"}}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateHistoryEntry.FIELDS), "properties": {"ordinal": {"type": "integer"}, "gate_id": {"type": "string"}, "runtime_id": {"type": "string"}, "gate_address": {"type": "string"}, "audit_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateHistory.FIELDS), "properties": {"history_id": {"type": "string"}, "entries": {"type": "array", "items": entry_schema()}, "entry_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "review_count": {"type": "integer"}, "blocked_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + HISTORY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "files": FILES, "features": ("append-only gate history", "accepted review and blocked counters", "atomic three-file persistence", "canonical reload verification", "gate and audit evidence links", "JSON CSV and Markdown exports"), "limits": {"max_entries": MAX_ENTRIES}, "schemas": ("manifest", "entry", "history")}


__all__ = ["BOUNDARY", "ENTRIES_NAME", "ENTRY_PREFIX", "FILES", "HISTORY_NAME", "HISTORY_PREFIX", "MANIFEST_NAME", "MAX_ENTRIES", "RegistryFederationConsensusGateHistory", "RegistryFederationConsensusGateHistoryEntry", "VERSION", "address_entry", "address_history", "append_history", "build_history", "capabilities", "entry_schema", "history_bytes", "history_csv", "history_from_mapping", "history_json", "history_schema", "load_history", "manifest_schema", "render_history_markdown", "verify_history", "verify_history_directory", "write_history"]

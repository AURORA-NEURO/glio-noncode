"""Append-only history for consensus receipts."""

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

from . import registry_federation_consensus as consensus_model
from . import registry_federation_consensus_audit as audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = consensus_model.VERSION + "-history-v1"
BOUNDARY = consensus_model.BOUNDARY + "_history"
HISTORY_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-history"
ENTRY_PREFIX = registry_model.REGISTRY_PREFIX + "-consensus-history-entry"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
MANIFEST_NAME = "manifest.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME)
MAX_ENTRIES = consensus_model.MAX_PACKAGES * consensus_model.MAX_PEERS * 4
CHECK_IDS = ("exact-fields", "public-boundary", "entry-conservation", "ordinal-conservation", "counter-conservation", "latest-conservation", "address-conservation", "manifest-conservation", "projection-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = False) -> str:
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


class RegistryFederationConsensusHistoryEntry:
    FIELDS = ("ordinal", "consensus_id", "consensus_address", "federation_id", "state", "decision", "accepted", "selected_count", "action_count", "audit_address", "content_address")

    def __init__(self, ordinal: int, consensus_id: str, consensus_address: str, federation_id: str, state: str, decision: str, accepted: bool, selected_count: int, action_count: int, audit_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus history entry ordinal", MAX_ENTRIES, positive=True)
        self.consensus_id = _label(consensus_id, "history consensus ID")
        self.consensus_address = _address(consensus_address, "history consensus address", consensus_model.CONSENSUS_PREFIX)
        self.federation_id = _label(federation_id, "history federation ID")
        if state not in consensus_model.STATES or decision not in consensus_model.DECISIONS:
            raise ValidationError("history disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "history acceptance")
        self.selected_count = _count(selected_count, "history selected count", consensus_model.MAX_PACKAGES)
        self.action_count = _count(action_count, "history action count", consensus_model.MAX_ACTIONS)
        self.audit_address = _address(audit_address, "history audit address", audit_model.AUDIT_PREFIX)
        self.content_address = _address(content_address, "history entry content address", ENTRY_PREFIX)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("history entry content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "consensus_id": self.consensus_id, "consensus_address": self.consensus_address, "federation_id": self.federation_id, "state": self.state, "decision": self.decision, "accepted": self.accepted, "selected_count": self.selected_count, "action_count": self.action_count, "audit_address": self.audit_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusHistoryEntry:
        value = _mapping(value, "consensus history entry")
        _strict(value, set(cls.FIELDS), "consensus history entry")
        return cls(value["ordinal"], value["consensus_id"], value["consensus_address"], value["federation_id"], value["state"], value["decision"], value["accepted"], value["selected_count"], value["action_count"], value["audit_address"], value["content_address"])


def address_entry(value: RegistryFederationConsensusHistoryEntry) -> str:
    if not isinstance(value, RegistryFederationConsensusHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class RegistryFederationConsensusHistory:
    FIELDS = ("history_id", "entries", "entry_count", "accepted_count", "rejected_count", "review_count", "latest_consensus_address", "content_address")

    def __init__(self, history_id: str, entries: Sequence[RegistryFederationConsensusHistoryEntry], entry_count: int, accepted_count: int, rejected_count: int, review_count: int, latest_consensus_address: str, content_address: str) -> None:
        self.history_id = _label(history_id, "consensus history ID")
        self.entries = tuple(entries)
        self.entry_count = _count(entry_count, "history entry count", MAX_ENTRIES, positive=True)
        self.accepted_count = _count(accepted_count, "history accepted count", self.entry_count)
        self.rejected_count = _count(rejected_count, "history rejected count", self.entry_count)
        self.review_count = _count(review_count, "history review count", self.entry_count)
        self.latest_consensus_address = _address(latest_consensus_address, "history latest consensus address", consensus_model.CONSENSUS_PREFIX)
        self.content_address = _address(content_address, "history content address", HISTORY_PREFIX)
        if len(self.entries) != self.entry_count or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or self.accepted_count != sum(item.accepted for item in self.entries) or self.rejected_count != sum(item.decision == "reject" for item in self.entries) or self.review_count != sum(item.decision == "review" for item in self.entries) or self.entries[-1].consensus_address != self.latest_consensus_address:
            raise ValidationError("history counters or ordering are not conserved")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("history content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "entries": tuple(item.to_dict() for item in self.entries), "entry_count": self.entry_count, "accepted_count": self.accepted_count, "rejected_count": self.rejected_count, "review_count": self.review_count, "latest_consensus_address": self.latest_consensus_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusHistory:
        value = _mapping(value, "consensus history")
        _strict(value, set(cls.FIELDS), "consensus history")
        return cls(value["history_id"], tuple(RegistryFederationConsensusHistoryEntry.from_mapping(item) for item in value["entries"]), value["entry_count"], value["accepted_count"], value["rejected_count"], value["review_count"], value["latest_consensus_address"], value["content_address"])


def address_history(value: RegistryFederationConsensusHistory) -> str:
    if not isinstance(value, RegistryFederationConsensusHistory):
        raise ValidationError("history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def build_history(values: Sequence[tuple[consensus_model.RegistryFederationConsensus, audit_model.RegistryFederationConsensusAudit]], *, history_id: str = "consensus-history") -> RegistryFederationConsensusHistory:
    values = _sequence(values, "consensus history values", MAX_ENTRIES)
    if not values:
        raise ValidationError("consensus history requires at least one receipt")
    entries: list[RegistryFederationConsensusHistoryEntry] = []
    for ordinal, pair in enumerate(values, start=1):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValidationError("history values must contain consensus and audit pairs")
        consensus, audit = pair
        consensus = consensus_model.verify_consensus(consensus)
        audit = audit_model.verify_audit(audit)
        if audit.consensus_address != consensus.content_address:
            raise ValidationError("history audit does not match consensus")
        provisional = RegistryFederationConsensusHistoryEntry(ordinal, consensus.consensus_id, consensus.content_address, consensus.federation_id, consensus.state, consensus.decision, consensus.accepted, consensus.selected_count, consensus.action_count, audit.content_address, ENTRY_PREFIX + ":pending")
        entries.append(RegistryFederationConsensusHistoryEntry(provisional.ordinal, provisional.consensus_id, provisional.consensus_address, provisional.federation_id, provisional.state, provisional.decision, provisional.accepted, provisional.selected_count, provisional.action_count, provisional.audit_address, address_entry(provisional)))
    provisional = RegistryFederationConsensusHistory(history_id, tuple(entries), len(entries), sum(item.accepted for item in entries), sum(item.decision == "reject" for item in entries), sum(item.decision == "review" for item in entries), entries[-1].consensus_address, HISTORY_PREFIX + ":pending")
    return RegistryFederationConsensusHistory(provisional.history_id, provisional.entries, provisional.entry_count, provisional.accepted_count, provisional.rejected_count, provisional.review_count, provisional.latest_consensus_address, address_history(provisional))


def history_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusHistory:
    return verify_history(RegistryFederationConsensusHistory.from_mapping(value))


def verify_history(value: RegistryFederationConsensusHistory) -> RegistryFederationConsensusHistory:
    if not isinstance(value, RegistryFederationConsensusHistory) or (not value.content_address.endswith(":pending") and address_history(value) != value.content_address):
        raise ValidationError("consensus history is not valid")
    return value


def history_json(value: RegistryFederationConsensusHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def history_csv(value: RegistryFederationConsensusHistory) -> str:
    value = verify_history(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusHistoryEntry.FIELDS, lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        writer.writerow(entry.to_dict())
    return stream.getvalue()


def render_history_markdown(value: RegistryFederationConsensusHistory) -> str:
    value = verify_history(value)
    lines = ["# Consensus History", "", f"- History: `{value.history_id}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}`", f"- Rejected: `{value.rejected_count}`", f"- Review: `{value.review_count}`", "", "| ordinal | consensus | state | decision | accepted | selected | actions |", "| ---: | --- | --- | --- | --- | ---: | ---: |"]
    lines.extend(f"| {entry.ordinal} | `{entry.consensus_id}` | `{entry.state}` | `{entry.decision}` | `{entry.accepted}` | {entry.selected_count} | {entry.action_count} |" for entry in value.entries)
    return "\n".join(lines) + "\n"


def query_history(value: RegistryFederationConsensusHistory, *, decision: str = "", state: str = "", accepted: bool | None = None, offset: int = 0, limit: int = 100) -> tuple[RegistryFederationConsensusHistoryEntry, ...]:
    value = verify_history(value)
    if decision and decision not in consensus_model.DECISIONS or state and state not in consensus_model.STATES:
        raise ValidationError("history query disposition is unsupported")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValidationError("history query pagination is invalid")
    matched = tuple(item for item in value.entries if (not decision or item.decision == decision) and (not state or item.state == state) and (accepted is None or item.accepted == accepted))
    return matched[offset:offset + limit]


def _manifest(value: RegistryFederationConsensusHistory) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "entry_count": value.entry_count, "history_address": value.content_address, "files": tuple(sorted(FILES))}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=HISTORY_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationConsensusHistory) -> dict[str, bytes]:
    value = verify_history(value)
    entries = {"entries": tuple(item.to_dict() for item in value.entries), "content_address": content_hash({"entries": tuple(item.to_dict() for item in value.entries), "content_address": None}, prefix=ENTRY_PREFIX + "-document")}
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), HISTORY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes(entries)}


def write_history(value: RegistryFederationConsensusHistory, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="consensus-history-staging-", dir=str(destination.parent)))
        for name, raw in package_bytes(value).items():
            (staging / name).write_bytes(raw)
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
    return destination


def load_history(directory: str | Path) -> RegistryFederationConsensusHistory:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("history directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("history member is not canonical JSON")
    value = history_from_mapping(decoded[HISTORY_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)):
        raise ValidationError("history manifest does not replay")
    entries = {"entries": tuple(item.to_dict() for item in value.entries), "content_address": content_hash({"entries": tuple(item.to_dict() for item in value.entries), "content_address": None}, prefix=ENTRY_PREFIX + "-document")}
    if canonical_bytes(decoded[ENTRIES_NAME]) != canonical_bytes(entries):
        raise ValidationError("history entry projection does not replay")
    return value


def verify_history_directory(directory: str | Path) -> RegistryFederationConsensusHistory:
    return load_history(directory)


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusHistoryEntry.FIELDS), "properties": {"ordinal": {"type": "integer"}, "consensus_id": {"type": "string"}, "consensus_address": {"type": "string"}, "federation_id": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "selected_count": {"type": "integer"}, "action_count": {"type": "integer"}, "audit_address": {"type": "string"}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusHistory.FIELDS), "properties": {"history_id": {"type": "string"}, "entries": {"type": "array", "items": entry_schema()}, "entry_count": {"type": "integer"}, "accepted_count": {"type": "integer"}, "rejected_count": {"type": "integer"}, "review_count": {"type": "integer"}, "latest_consensus_address": {"type": "string"}, "content_address": {"type": "string"}}}


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "history_id", "entry_count", "history_address", "files", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "history_id": {"type": "string"}, "entry_count": {"type": "integer"}, "history_address": {"type": "string"}, "files": {"type": "array"}, "manifest_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "files": FILES, "check_ids": CHECK_IDS, "features": ("append-only consensus receipt timeline", "accepted rejected and review counters", "latest receipt pointer", "three-file atomic persistence", "canonical reload verification", "state decision and acceptance query", "JSON CSV and Markdown exports"), "schemas": ("manifest", "entry", "history")}


__all__ = ["BOUNDARY", "CHECK_IDS", "ENTRIES_NAME", "ENTRY_PREFIX", "FILES", "HISTORY_NAME", "HISTORY_PREFIX", "MANIFEST_NAME", "MAX_ENTRIES", "RegistryFederationConsensusHistory", "RegistryFederationConsensusHistoryEntry", "VERSION", "address_entry", "address_history", "build_history", "capabilities", "entry_schema", "history_csv", "history_from_mapping", "history_json", "history_schema", "load_history", "manifest_schema", "package_bytes", "query_history", "render_history_markdown", "verify_history", "verify_history_directory", "write_history"]

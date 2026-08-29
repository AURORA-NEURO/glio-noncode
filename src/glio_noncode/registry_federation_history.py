"""Append-only, address-linked history for federation release receipts."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from . import registry_federation_audit as audit_model
from . import registry_federation_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = federation_model.VERSION + "-history-v1"
BOUNDARY = federation_model.BOUNDARY + "_history"
HISTORY_PREFIX = federation_model.FEDERATION_PREFIX + "-history"
ENTRY_PREFIX = federation_model.FEDERATION_PREFIX + "-history-entry"
MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME)
MAX_ENTRIES = federation_model.MAX_PACKAGES
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = ("exact-fields", "public-boundary", "entry-conservation", "ordinal-conservation", "address-conservation", "counter-conservation", "manifest-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":"):
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
        return "agent" not in value.lower() and "/" not in value and "\\" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationHistoryEntry:
    FIELDS = ("ordinal", "federation_id", "federation_address", "state", "decision", "accepted", "audit_address", "gate_address", "content_address")

    def __init__(self, ordinal: int, federation_id: str, federation_address: str, state: str, decision: str, accepted: bool, audit_address: str, gate_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history entry ordinal", MAX_ENTRIES, positive=True)
        self.federation_id = _label(federation_id, "history entry federation ID")
        self.federation_address = _address(federation_address, "history entry federation address", federation_model.FEDERATION_PREFIX)
        if state not in federation_model.STATES or decision not in federation_model.DECISIONS:
            raise ValidationError("history entry disposition is unsupported")
        self.state = state
        self.decision = decision
        self.accepted = _bool(accepted, "history entry acceptance")
        self.audit_address = _address(audit_address, "history entry audit address", audit_model.AUDIT_PREFIX)
        self.gate_address = _address(gate_address, "history entry gate address", gate_model.GATE_PREFIX)
        self.content_address = _address(content_address, "history entry content address", ENTRY_PREFIX)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("history entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "federation_id": self.federation_id, "federation_address": self.federation_address, "state": self.state, "decision": self.decision, "accepted": self.accepted, "audit_address": self.audit_address, "gate_address": self.gate_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationHistoryEntry:
        value = _mapping(value, "history entry")
        _strict(value, set(cls.FIELDS), "history entry")
        return cls(value["ordinal"], value["federation_id"], value["federation_address"], value["state"], value["decision"], value["accepted"], value["audit_address"], value["gate_address"], value["content_address"])


def address_entry(value: RegistryFederationHistoryEntry) -> str:
    if not isinstance(value, RegistryFederationHistoryEntry):
        raise ValidationError("history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class RegistryFederationHistory:
    FIELDS = ("history_id", "entries", "entry_count", "accepted_count", "rejected_count", "review_count", "latest_federation_address", "content_address")

    def __init__(self, history_id: str, entries: Sequence[RegistryFederationHistoryEntry], entry_count: int, accepted_count: int, rejected_count: int, review_count: int, latest_federation_address: str, content_address: str) -> None:
        self.history_id = _label(history_id, "history ID")
        self.entries = tuple(entries)
        self.entry_count = _count(entry_count, "history entry count", MAX_ENTRIES, positive=True)
        self.accepted_count = _count(accepted_count, "history accepted count", self.entry_count)
        self.rejected_count = _count(rejected_count, "history rejected count", self.entry_count)
        self.review_count = _count(review_count, "history review count", self.entry_count)
        self.latest_federation_address = _address(latest_federation_address, "latest federation address", federation_model.FEDERATION_PREFIX)
        self.content_address = _address(content_address, "history content address", HISTORY_PREFIX)
        if len(self.entries) != self.entry_count or tuple(entry.ordinal for entry in self.entries) != tuple(range(1, self.entry_count + 1)) or self.accepted_count != sum(entry.accepted for entry in self.entries) or self.rejected_count != sum(entry.decision == "reject" for entry in self.entries) or self.review_count != sum(entry.decision == "review" for entry in self.entries) or self.entries[-1].federation_address != self.latest_federation_address:
            raise ValidationError("history counters or ordering are not conserved")
        if len({entry.federation_address for entry in self.entries}) != self.entry_count:
            raise ValidationError("history federation addresses must be unique")
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("history content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "entries": tuple(entry.to_dict() for entry in self.entries), "entry_count": self.entry_count, "accepted_count": self.accepted_count, "rejected_count": self.rejected_count, "review_count": self.review_count, "latest_federation_address": self.latest_federation_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationHistory:
        value = _mapping(value, "federation history")
        _strict(value, set(cls.FIELDS), "federation history")
        entries = tuple(value["entries"]) if isinstance(value["entries"], list) else value["entries"]
        return cls(value["history_id"], tuple(RegistryFederationHistoryEntry.from_mapping(item) for item in entries), value["entry_count"], value["accepted_count"], value["rejected_count"], value["review_count"], value["latest_federation_address"], value["content_address"])


def address_history(value: RegistryFederationHistory) -> str:
    if not isinstance(value, RegistryFederationHistory):
        raise ValidationError("history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def build_history(federations: Sequence[federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation], *, history_id: str = "federation-history") -> RegistryFederationHistory:
    federations = _sequence(federations, "history federations", MAX_ENTRIES)
    if not federations:
        raise ValidationError("history requires at least one federation")
    entries = []
    for ordinal, federation in enumerate(federations, start=1):
        federation = federation_model.verify_federation(federation)
        audit = audit_model.audit_federation(federation)
        gate = gate_model.evaluate_gate(federation, audit)
        provisional = RegistryFederationHistoryEntry(ordinal, federation.federation_id, federation.content_address, federation.state, federation.decision, federation.accepted, audit.content_address, gate.content_address, ENTRY_PREFIX + ":pending")
        entries.append(RegistryFederationHistoryEntry(provisional.ordinal, provisional.federation_id, provisional.federation_address, provisional.state, provisional.decision, provisional.accepted, provisional.audit_address, provisional.gate_address, address_entry(provisional)))
    provisional_history = RegistryFederationHistory(history_id, tuple(entries), len(entries), sum(entry.accepted for entry in entries), sum(entry.decision == "reject" for entry in entries), sum(entry.decision == "review" for entry in entries), entries[-1].federation_address, HISTORY_PREFIX + ":pending")
    return RegistryFederationHistory(provisional_history.history_id, provisional_history.entries, provisional_history.entry_count, provisional_history.accepted_count, provisional_history.rejected_count, provisional_history.review_count, provisional_history.latest_federation_address, address_history(provisional_history))


def history_from_mapping(value: Mapping[str, Any]) -> RegistryFederationHistory:
    return verify_history(RegistryFederationHistory.from_mapping(value))


def verify_history(value: RegistryFederationHistory) -> RegistryFederationHistory:
    if not isinstance(value, RegistryFederationHistory) or (not value.content_address.endswith(":pending") and address_history(value) != value.content_address):
        raise ValidationError("federation history is not valid")
    return value


def history_json(value: RegistryFederationHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def _manifest(value: RegistryFederationHistory) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "entry_count": value.entry_count, "files": tuple(sorted(FILES)), "history_address": value.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=HISTORY_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationHistory) -> dict[str, bytes]:
    value = verify_history(value)
    manifest = _manifest(value)
    entries = {"entries": tuple(entry.to_dict() for entry in value.entries), "content_address": content_hash({"entries": tuple(entry.to_dict() for entry in value.entries), "content_address": None}, prefix=ENTRY_PREFIX + "-document")}
    return {MANIFEST_NAME: canonical_bytes(manifest), HISTORY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes(entries)}


def write_history(value: RegistryFederationHistory, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="federation-history-staging-", dir=str(destination.parent)))
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


def load_history(directory: str | Path) -> RegistryFederationHistory:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("history directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("history member is not canonical JSON")
    value = history_from_mapping(decoded[HISTORY_NAME])
    if decoded[MANIFEST_NAME].get("history_address") != value.content_address or decoded[MANIFEST_NAME].get("history_id") != value.history_id:
        raise ValidationError("history manifest does not match history")
    if canonical_bytes(decoded[ENTRIES_NAME]) != package_bytes(value)[ENTRIES_NAME]:
        raise ValidationError("history entry projection does not replay")
    return value


def verify_history_directory(directory: str | Path) -> RegistryFederationHistory:
    return load_history(directory)


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationHistory.FIELDS), "properties": {"history_id": {"type": "string"}, "entries": {"type": "array"}, "entry_count": {"type": "integer", "minimum": 1}, "accepted_count": {"type": "integer", "minimum": 0}, "rejected_count": {"type": "integer", "minimum": 0}, "review_count": {"type": "integer", "minimum": 0}, "latest_federation_address": {"type": "string"}, "content_address": {"type": "string"}}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationHistoryEntry.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "federation_id": {"type": "string"}, "federation_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "audit_address": {"type": "string"}, "gate_address": {"type": "string"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "files": FILES, "check_ids": CHECK_IDS, "features": ("append-only federation receipts", "accepted/rejected/review counters", "latest receipt pointer", "three-file atomic persistence", "canonical reload verification", "JSON export"), "schemas": ("entry", "history")}


__all__ = ["BOUNDARY", "CHECK_IDS", "ENTRIES_NAME", "ENTRY_PREFIX", "FILES", "HISTORY_NAME", "HISTORY_PREFIX", "MANIFEST_NAME", "RegistryFederationHistory", "RegistryFederationHistoryEntry", "VERSION", "address_entry", "address_history", "build_history", "capabilities", "entry_schema", "history_from_mapping", "history_json", "history_schema", "load_history", "package_bytes", "verify_history", "verify_history_directory", "write_history"]

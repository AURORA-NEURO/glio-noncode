"""Append-only history of issued and withheld consensus gate certificates."""

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

from . import registry_federation_consensus_gate_certificate as certificate_model
from . import registry_federation_consensus_gate_certificate_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = certificate_model.VERSION + "-history-v1"
BOUNDARY = certificate_model.BOUNDARY + "_history"
HISTORY_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-history"
ENTRY_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-history-entry"
MANIFEST_NAME = "manifest.json"
HISTORY_NAME = "history.json"
ENTRIES_NAME = "entries.json"
FILES = (MANIFEST_NAME, HISTORY_NAME, ENTRIES_NAME)
MAX_ENTRIES = 256
MAX_TEXT = certificate_model.MAX_TEXT


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
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateHistoryEntry:
    """One immutable certificate transition in history order."""

    FIELDS = ("ordinal", "certificate_id", "runtime_id", "certificate_address", "audit_address", "state", "decision", "accepted", "check_count", "failed_count", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, certificate_id: str, runtime_id: str, certificate_address: str, audit_address: str, state: str, decision: str, accepted: bool, check_count: int, failed_count: int, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate history entry ordinal", MAX_ENTRIES, positive=True)
        self.certificate_id = _label(certificate_id, "history certificate ID")
        self.runtime_id = _label(runtime_id, "history runtime ID")
        self.certificate_address = _address(certificate_address, "history certificate address", certificate_model.CERTIFICATE_PREFIX)
        self.audit_address = _address(audit_address, "history certificate audit address", audit_model.AUDIT_PREFIX)
        if state not in certificate_model.CERTIFICATE_STATES or decision not in certificate_model.CERTIFICATE_DECISIONS:
            raise ValidationError("certificate history disposition is unsupported")
        self.state, self.decision = state, decision
        self.accepted = _bool(accepted, "certificate history acceptance")
        self.check_count = _count(check_count, "certificate history check count", certificate_model.MAX_CHECKS, positive=True)
        self.failed_count = _count(failed_count, "certificate history failed count", self.check_count)
        self.evidence_addresses = _addresses(evidence_addresses, "certificate history evidence addresses", certificate_model.MAX_EVIDENCE)
        if not self.evidence_addresses:
            raise ValidationError("certificate history entries require evidence")
        if self.accepted != (self.state == "issued" and self.decision == "promote" and self.failed_count == 0):
            raise ValidationError("certificate history acceptance does not conserve disposition")
        self.content_address = _address(content_address, "certificate history entry address", ENTRY_PREFIX)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("certificate history entry address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate history entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateHistoryEntry:
        value = _mapping(value, "certificate history entry")
        _strict(value, set(cls.FIELDS), "certificate history entry")
        return cls(*(value[field] for field in cls.FIELDS))


def address_entry(value: RegistryFederationConsensusGateCertificateHistoryEntry) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateHistoryEntry):
        raise ValidationError("certificate history entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


class RegistryFederationConsensusGateCertificateHistory:
    """Addressed ordered collection of certificate decisions."""

    FIELDS = ("history_id", "entries", "entry_count", "issued_count", "withheld_count", "content_address")

    def __init__(self, history_id: str, entries: Sequence[RegistryFederationConsensusGateCertificateHistoryEntry], entry_count: int, issued_count: int, withheld_count: int, content_address: str) -> None:
        self.history_id = _label(history_id, "certificate history ID")
        self.entries = tuple(entries)
        if len(self.entries) > MAX_ENTRIES or any(not isinstance(item, RegistryFederationConsensusGateCertificateHistoryEntry) for item in self.entries):
            raise ValidationError("certificate history entries are outside the bound")
        self.entry_count = _count(entry_count, "certificate history entry count", MAX_ENTRIES, positive=True)
        self.issued_count = _count(issued_count, "certificate history issued count", self.entry_count)
        self.withheld_count = _count(withheld_count, "certificate history withheld count", self.entry_count)
        if len(self.entries) != self.entry_count or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)) or self.issued_count != sum(item.state == "issued" for item in self.entries) or self.withheld_count != sum(item.state == "withheld" for item in self.entries):
            raise ValidationError("certificate history counters are not conserved")
        self.content_address = _address(content_address, "certificate history content address", HISTORY_PREFIX)
        if not self.content_address.endswith(":pending") and address_history(self) != self.content_address:
            raise ValidationError("certificate history content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate history crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"history_id": self.history_id, "entries": tuple(item.to_dict() for item in self.entries), "entry_count": self.entry_count, "issued_count": self.issued_count, "withheld_count": self.withheld_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "entries"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateHistory:
        value = _mapping(value, "certificate history")
        _strict(value, set(cls.FIELDS), "certificate history")
        return cls(value["history_id"], tuple(RegistryFederationConsensusGateCertificateHistoryEntry.from_mapping(item) for item in value["entries"]), value["entry_count"], value["issued_count"], value["withheld_count"], value["content_address"])


def address_history(value: RegistryFederationConsensusGateCertificateHistory) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateHistory):
        raise ValidationError("certificate history address requires a typed history")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=HISTORY_PREFIX)


def _entry(ordinal: int, certificate: certificate_model.RegistryFederationConsensusGateCertificate, audit: audit_model.RegistryFederationConsensusGateCertificateAudit) -> RegistryFederationConsensusGateCertificateHistoryEntry:
    evidence = (certificate.content_address, audit.content_address, certificate.runtime_address, certificate.gate_address, certificate.policy.content_address)
    provisional = RegistryFederationConsensusGateCertificateHistoryEntry(ordinal, certificate.certificate_id, certificate.runtime_id, certificate.content_address, audit.content_address, certificate.certificate_state, certificate.certificate_decision, certificate.accepted, certificate.check_count, certificate.failed_count, evidence, ENTRY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateHistoryEntry(provisional.ordinal, provisional.certificate_id, provisional.runtime_id, provisional.certificate_address, provisional.audit_address, provisional.state, provisional.decision, provisional.accepted, provisional.check_count, provisional.failed_count, provisional.evidence_addresses, address_entry(provisional))


def build_history(values: Sequence[tuple[certificate_model.RegistryFederationConsensusGateCertificate, audit_model.RegistryFederationConsensusGateCertificateAudit]], *, history_id: str = "consensus-certificate-history") -> RegistryFederationConsensusGateCertificateHistory:
    values = _sequence(values, "certificate history values", MAX_ENTRIES)
    entries: list[RegistryFederationConsensusGateCertificateHistoryEntry] = []
    for certificate, audit in values:
        certificate = certificate_model.verify_certificate(certificate)
        audit = audit_model.verify_audit(audit)
        if audit.certificate_address != certificate.content_address:
            raise ValidationError("certificate history audit does not refer to certificate")
        entries.append(_entry(len(entries) + 1, certificate, audit))
    if not entries:
        raise ValidationError("certificate history requires at least one entry")
    provisional = RegistryFederationConsensusGateCertificateHistory(history_id, tuple(entries), len(entries), sum(item.state == "issued" for item in entries), sum(item.state == "withheld" for item in entries), HISTORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateHistory(provisional.history_id, provisional.entries, provisional.entry_count, provisional.issued_count, provisional.withheld_count, address_history(provisional))


def append_history(value: RegistryFederationConsensusGateCertificateHistory, certificate: certificate_model.RegistryFederationConsensusGateCertificate, audit: audit_model.RegistryFederationConsensusGateCertificateAudit) -> RegistryFederationConsensusGateCertificateHistory:
    value = verify_history(value)
    if value.entry_count >= MAX_ENTRIES:
        raise ValidationError("certificate history is at capacity")
    certificate = certificate_model.verify_certificate(certificate)
    audit = audit_model.verify_audit(audit)
    if audit.certificate_address != certificate.content_address:
        raise ValidationError("appended audit does not refer to certificate")
    entry = _entry(value.entry_count + 1, certificate, audit)
    entries = (*value.entries, entry)
    provisional = RegistryFederationConsensusGateCertificateHistory(value.history_id, entries, len(entries), sum(item.state == "issued" for item in entries), sum(item.state == "withheld" for item in entries), HISTORY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateHistory(provisional.history_id, provisional.entries, provisional.entry_count, provisional.issued_count, provisional.withheld_count, address_history(provisional))


def history_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateHistory:
    return verify_history(RegistryFederationConsensusGateCertificateHistory.from_mapping(value))


def verify_history(value: RegistryFederationConsensusGateCertificateHistory) -> RegistryFederationConsensusGateCertificateHistory:
    if not isinstance(value, RegistryFederationConsensusGateCertificateHistory) or (not value.content_address.endswith(":pending") and address_history(value) != value.content_address):
        raise ValidationError("certificate history is not valid")
    return value


def history_json(value: RegistryFederationConsensusGateCertificateHistory) -> str:
    return canonical_json(verify_history(value).to_dict())


def history_csv(value: RegistryFederationConsensusGateCertificateHistory) -> str:
    value = verify_history(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateHistoryEntry.FIELDS, lineterminator="\n")
    writer.writeheader()
    for entry in value.entries:
        row = entry.to_dict()
        row["evidence_addresses"] = "|".join(entry.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_history_markdown(value: RegistryFederationConsensusGateCertificateHistory) -> str:
    value = verify_history(value)
    lines = ["# Consensus Release Certificate History", "", f"- History: `{value.history_id}`", f"- Entries: `{value.entry_count}`", f"- Issued: `{value.issued_count}`", f"- Withheld: `{value.withheld_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | certificate | state | decision | accepted | failed |", "| --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.ordinal}` | `{item.certificate_id}` | `{item.state}` | `{item.decision}` | `{item.accepted}` | `{item.failed_count}` |" for item in value.entries)
    return "\n".join(lines) + "\n"


def _manifest(value: RegistryFederationConsensusGateCertificateHistory) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "history_id": value.history_id, "files": tuple(sorted(FILES)), "history_address": value.content_address, "entry_count": value.entry_count}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=HISTORY_PREFIX + "-manifest")}


def history_bytes(value: RegistryFederationConsensusGateCertificateHistory) -> dict[str, bytes]:
    value = verify_history(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), HISTORY_NAME: canonical_bytes(value.to_dict()), ENTRIES_NAME: canonical_bytes(tuple(item.to_dict() for item in value.entries))}


def write_history(value: RegistryFederationConsensusGateCertificateHistory, directory: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_history(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("certificate history destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="consensus-certificate-history-staging-", dir=str(destination.parent)))
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


def load_history(directory: str | Path) -> RegistryFederationConsensusGateCertificateHistory:
    source = Path(directory)
    if not source.is_dir() or tuple(sorted(path.name for path in source.iterdir())) != tuple(sorted(FILES)):
        raise ValidationError("certificate history directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("certificate history member is not canonical JSON")
    value = history_from_mapping(decoded[HISTORY_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)) or canonical_bytes(decoded[ENTRIES_NAME]) != canonical_bytes(tuple(item.to_dict() for item in value.entries)):
        raise ValidationError("certificate history projections do not replay")
    return value


def verify_history_directory(directory: str | Path) -> RegistryFederationConsensusGateCertificateHistory:
    return load_history(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "history_id", "files", "history_address", "entry_count", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "history_id": {"type": "string"}, "files": {"type": "array"}, "history_address": {"type": "string"}, "entry_count": {"type": "integer"}, "manifest_address": {"type": "string"}}}


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateHistoryEntry.FIELDS), "properties": {"ordinal": {"type": "integer"}, "certificate_id": {"type": "string"}, "runtime_id": {"type": "string"}, "certificate_address": {"type": "string"}, "audit_address": {"type": "string"}, "state": {"type": "string"}, "decision": {"type": "string"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def history_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateHistory.FIELDS), "properties": {"history_id": {"type": "string"}, "entries": {"type": "array", "items": entry_schema()}, "entry_count": {"type": "integer"}, "issued_count": {"type": "integer"}, "withheld_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + HISTORY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "history_prefix": HISTORY_PREFIX, "entry_prefix": ENTRY_PREFIX, "files": FILES, "features": ("append-only certificate history", "issued and withheld counters", "atomic three-file persistence", "canonical reload verification", "certificate and audit evidence links", "JSON CSV and Markdown exports"), "limits": {"max_entries": MAX_ENTRIES}, "schemas": ("manifest", "entry", "history")}


__all__ = ["BOUNDARY", "ENTRIES_NAME", "ENTRY_PREFIX", "FILES", "HISTORY_NAME", "HISTORY_PREFIX", "MANIFEST_NAME", "MAX_ENTRIES", "RegistryFederationConsensusGateCertificateHistory", "RegistryFederationConsensusGateCertificateHistoryEntry", "VERSION", "address_entry", "address_history", "append_history", "build_history", "capabilities", "entry_schema", "history_bytes", "history_csv", "history_from_mapping", "history_json", "history_schema", "load_history", "manifest_schema", "render_history_markdown", "verify_history", "verify_history_directory", "write_history"]

"""Verified, path-free catalogs of persisted observability handoffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle as bundle_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = bundle_model.VERSION + "-catalog-v1"
BOUNDARY = bundle_model.BOUNDARY + "_catalog"
CATALOG_PREFIX = bundle_model.BUNDLE_PREFIX + "-catalog"
ENTRY_PREFIX = CATALOG_PREFIX + "-entry"
DEFAULT_CATALOG_ID = "glio-noncode-observability-bundle-catalog"
MAX_ENTRIES = 32
MAX_TEXT = 1024
STATES = ("ready", "held", "blocked")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str = "observability bundle catalog label") -> str:
    value = _text(value, field, 128)
    if any(character in value for character in ("/", "\\", "\x00")) or value.startswith("."):
        raise ValidationError(f"{field} must be a path-free public label")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return bundle_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry:
    """One verified handoff receipt in a catalog."""

    FIELDS = (
        "ordinal",
        "label",
        "bundle_address",
        "manifest_address",
        "pipeline_address",
        "pipeline_state",
        "pipeline_accepted",
        "observability_address",
        "observability_state",
        "audit_address",
        "audit_state",
        "audit_accepted",
        "query_addresses",
        "artifact_count",
        "content_address",
    )

    def __init__(self, ordinal: int, label: str, bundle_address: str, manifest_address: str, pipeline_address: str, pipeline_state: str, pipeline_accepted: bool, observability_address: str, observability_state: str, audit_address: str, audit_state: str, audit_accepted: bool, query_addresses: Sequence[str], artifact_count: int, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observability bundle catalog entry ordinal", MAX_ENTRIES, positive=True)
        self.label = _label(label)
        self.bundle_address = _address(bundle_address, "observability bundle catalog entry bundle address", bundle_model.BUNDLE_PREFIX)
        self.manifest_address = _address(manifest_address, "observability bundle catalog entry manifest address", bundle_model.MANIFEST_PREFIX)
        self.pipeline_address = _address(bundle_model._address(pipeline_address, "observability bundle catalog entry pipeline address", bundle_model.pipeline_model.PIPELINE_PREFIX), "observability bundle catalog entry pipeline address", bundle_model.pipeline_model.PIPELINE_PREFIX)
        self.pipeline_state = _text(pipeline_state, "observability bundle catalog entry pipeline state", 32)
        self.pipeline_accepted = _bool(pipeline_accepted, "observability bundle catalog entry pipeline acceptance")
        self.observability_address = _address(observability_address, "observability bundle catalog entry observability address", bundle_model.observability_model.OBSERVABILITY_PREFIX)
        self.observability_state = _text(observability_state, "observability bundle catalog entry observability state", 32)
        self.audit_address = _address(audit_address, "observability bundle catalog entry audit address", bundle_model.audit_model.AUDIT_PREFIX)
        self.audit_state = _text(audit_state, "observability bundle catalog entry audit state", 32)
        self.audit_accepted = _bool(audit_accepted, "observability bundle catalog entry audit acceptance")
        if not isinstance(query_addresses, tuple) or len(query_addresses) != len(bundle_model.QUERY_ARTIFACTS):
            raise ValidationError("observability bundle catalog entry query address count is invalid")
        query_prefixes = (bundle_model.query_model.QUERY_PREFIX,) * len(bundle_model.OBSERVABILITY_QUERY_ARTIFACTS) + (bundle_model.audit_query_model.QUERY_PREFIX,)
        self.query_addresses = tuple(_address(item, "observability bundle catalog entry query address", prefix) for item, prefix in zip(query_addresses, query_prefixes, strict=True))
        self.artifact_count = _count(artifact_count, "observability bundle catalog entry artifact count", len(bundle_model.ARTIFACT_FILES))
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.pipeline_state not in bundle_model.pipeline_model.STATES or self.observability_state not in bundle_model.pipeline_model.STATES or self.audit_state not in bundle_model.audit_model.STATES:
            raise ValidationError("observability bundle catalog entry state is unsupported")
        if self.artifact_count != len(bundle_model.ARTIFACT_FILES):
            raise ValidationError("observability bundle catalog entry artifact count is invalid")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog entry content address")
        else:
            _address(self.content_address, "observability bundle catalog entry content address", ENTRY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_entry(self) != self.content_address):
            raise ValidationError("observability bundle catalog entry address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "label": self.label, "bundle_address": self.bundle_address, "manifest_address": self.manifest_address, "pipeline_address": self.pipeline_address, "pipeline_state": self.pipeline_state, "pipeline_accepted": self.pipeline_accepted, "observability_address": self.observability_address, "observability_state": self.observability_state, "audit_address": self.audit_address, "audit_state": self.audit_state, "audit_accepted": self.audit_accepted, "query_addresses": self.query_addresses, "artifact_count": self.artifact_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry:
        value = _mapping(value, "observability bundle catalog entry")
        _strict(value, set(cls.FIELDS), "observability bundle catalog entry")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog entry is missing fields: {missing}")
        query_addresses = _sequence(value["query_addresses"], "observability bundle catalog entry query addresses", len(bundle_model.QUERY_ARTIFACTS))
        return cls(value["ordinal"], value["label"], value["bundle_address"], value["manifest_address"], value["pipeline_address"], value["pipeline_state"], value["pipeline_accepted"], value["observability_address"], value["observability_state"], value["audit_address"], value["audit_state"], value["audit_accepted"], query_addresses, value["artifact_count"], value["content_address"])


def address_entry(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry):
        raise ValidationError("observability bundle catalog entry address requires a typed entry")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


def _entry_from_bundle(label: str, ordinal: int, value: bundle_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundle) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry:
    if not isinstance(value, bundle_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundle):
        raise ValidationError("observability bundle catalog entry requires a typed bundle")
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry(ordinal, label, value.content_address, value.manifest_address, value.pipeline_address, value.pipeline_state, value.pipeline_accepted, value.observability_address, value.observability_state, value.audit_address, value.audit_state, value.audit_accepted, value.query_addresses, value.artifact_count, "pending:observability-bundle-catalog-entry")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry(provisional.ordinal, provisional.label, provisional.bundle_address, provisional.manifest_address, provisional.pipeline_address, provisional.pipeline_state, provisional.pipeline_accepted, provisional.observability_address, provisional.observability_state, provisional.audit_address, provisional.audit_state, provisional.audit_accepted, provisional.query_addresses, provisional.artifact_count, address_entry(provisional))


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    """A deterministic catalog of verified observability handoff receipts."""

    FIELDS = ("catalog_id", "entry_count", "accepted_count", "ready_count", "rejected_count", "entries", "content_address")

    def __init__(self, catalog_id: str, entry_count: int, accepted_count: int, ready_count: int, rejected_count: int, entries: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry], content_address: str) -> None:
        self.catalog_id = _label(catalog_id, "observability bundle catalog ID")
        self.entries = tuple(entries)
        self.entry_count = _count(entry_count, "observability bundle catalog entry count", MAX_ENTRIES)
        self.accepted_count = _count(accepted_count, "observability bundle catalog accepted count", MAX_ENTRIES)
        self.ready_count = _count(ready_count, "observability bundle catalog ready count", MAX_ENTRIES)
        self.rejected_count = _count(rejected_count, "observability bundle catalog rejected count", MAX_ENTRIES)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.entry_count != len(self.entries) or self.entry_count > MAX_ENTRIES:
            raise ValidationError("observability bundle catalog entry count is not conserved")
        if any(not isinstance(entry, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) for entry in self.entries):
            raise ValidationError("observability bundle catalog entries must be typed")
        if tuple(entry.ordinal for entry in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("observability bundle catalog entry ordinals are not canonical")
        if tuple(entry.label for entry in self.entries) != tuple(sorted(entry.label for entry in self.entries)) or len({entry.label for entry in self.entries}) != self.entry_count:
            raise ValidationError("observability bundle catalog labels are not unique and sorted")
        accepted = sum(entry.pipeline_accepted and entry.audit_accepted for entry in self.entries)
        ready = sum(entry.pipeline_accepted and entry.audit_accepted and entry.pipeline_state == "ready" and entry.observability_state == "ready" and entry.audit_state == "complete" for entry in self.entries)
        if self.accepted_count != accepted or self.ready_count != ready or self.rejected_count != self.entry_count - accepted:
            raise ValidationError("observability bundle catalog denominators are not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog content address")
        else:
            _address(self.content_address, "observability bundle catalog content address", CATALOG_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_catalog(self) != self.content_address):
            raise ValidationError("observability bundle catalog address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "ready_count": self.ready_count, "rejected_count": self.rejected_count, "entries": tuple(entry.to_dict() for entry in self.entries), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("catalog_id", "entry_count", "accepted_count", "ready_count", "rejected_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
        value = _mapping(value, "observability bundle catalog")
        _strict(value, set(cls.FIELDS), "observability bundle catalog")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog is missing fields: {missing}")
        entries = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry.from_mapping(item) for item in _sequence(value["entries"], "observability bundle catalog entries", MAX_ENTRIES))
        return cls(value["catalog_id"], value["entry_count"], value["accepted_count"], value["ready_count"], value["rejected_count"], entries, value["content_address"])


def address_catalog(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog):
        raise ValidationError("observability bundle catalog address requires a typed catalog")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CATALOG_PREFIX)


def _catalog(entries: Sequence[tuple[str, bundle_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundle]], catalog_id: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    if len(entries) > MAX_ENTRIES:
        raise ValidationError("observability bundle catalog exceeds its entry bound")
    normalized = sorted(((_label(label), value) for label, value in entries), key=lambda pair: pair[0])
    if len({label for label, _ in normalized}) != len(normalized):
        raise ValidationError("observability bundle catalog labels must be unique")
    typed_entries = tuple(_entry_from_bundle(label, ordinal, value) for ordinal, (label, value) in enumerate(normalized, start=1))
    accepted_count = sum(entry.pipeline_accepted and entry.audit_accepted for entry in typed_entries)
    ready_count = sum(entry.pipeline_accepted and entry.audit_accepted and entry.pipeline_state == "ready" and entry.observability_state == "ready" and entry.audit_state == "complete" for entry in typed_entries)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog(_label(catalog_id, "observability bundle catalog ID"), len(typed_entries), accepted_count, ready_count, len(typed_entries) - accepted_count, typed_entries, "pending:observability-bundle-catalog")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog(provisional.catalog_id, provisional.entry_count, provisional.accepted_count, provisional.ready_count, provisional.rejected_count, provisional.entries, address_catalog(provisional))


def build_catalog(entries: Sequence[tuple[str, bundle_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundle]], *, catalog_id: str = DEFAULT_CATALOG_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    if isinstance(entries, (str, bytes)):
        raise ValidationError("observability bundle catalog entries must be a sequence")
    return _catalog(tuple(entries), catalog_id)


def _source_entries(sources: Mapping[str, str | Path] | Sequence[tuple[str, str | Path]]) -> tuple[tuple[str, str | Path], ...]:
    if isinstance(sources, Mapping):
        values = tuple(sources.items())
    elif isinstance(sources, (str, bytes)) or not isinstance(sources, Sequence):
        raise ValidationError("observability bundle catalog sources must be a mapping or sequence")
    else:
        values = tuple(sources)
    if len(values) > MAX_ENTRIES:
        raise ValidationError("observability bundle catalog sources exceed their entry bound")
    normalized: list[tuple[str, str | Path]] = []
    for item in values:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes)) or len(item) != 2:
            raise ValidationError("observability bundle catalog source entries must contain label and directory")
        normalized.append((_label(item[0]), item[1]))
    return tuple(normalized)


def build_catalog_from_directories(sources: Mapping[str, str | Path] | Sequence[tuple[str, str | Path]], *, catalog_id: str = DEFAULT_CATALOG_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    values = _source_entries(sources)
    return _catalog(tuple((label, bundle_model.verify_bundle(source)) for label, source in values), catalog_id)


def catalog_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    return verify_catalog(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog.from_mapping(value))


def verify_catalog(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog):
        raise ValidationError("observability bundle catalog verification requires a typed catalog")
    if address_catalog(value) != value.content_address:
        raise ValidationError("observability bundle catalog content address does not replay")
    return value


def catalog_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog) -> str:
    return canonical_json(verify_catalog(value).to_dict())


def catalog_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog) -> str:
    value = verify_catalog(value)
    output = io.StringIO()
    fields = ("ordinal", "label", "bundle_address", "pipeline_state", "pipeline_accepted", "observability_state", "audit_state", "audit_accepted", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: entry.to_dict()[field] for field in fields} for entry in value.entries)
    return output.getvalue()


def render_catalog_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog) -> str:
    value = verify_catalog(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog", "", f"- Catalog: `{value.catalog_id}`", f"- Entries: `{value.entry_count}`", f"- Accepted: `{value.accepted_count}`", f"- Ready: `{value.ready_count}`", f"- Rejected: `{value.rejected_count}`", f"- Content address: `{value.content_address}`", "", "| ordinal | label | pipeline_state | pipeline_accepted | observability_state | audit_state | audit_accepted | bundle_address |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {entry.ordinal} | {entry.label} | {entry.pipeline_state} | {entry.pipeline_accepted} | {entry.observability_state} | {entry.audit_state} | {entry.audit_accepted} | {entry.bundle_address} |" for entry in value.entries)
    return "\n".join(lines) + "\n"


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ENTRIES}, "label": {"type": "string", "maxLength": 128}, "bundle_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + bundle_model.MANIFEST_PREFIX + ":"}, "pipeline_address": {"type": "string", "pattern": "^" + bundle_model.pipeline_model.PIPELINE_PREFIX + ":"}, "pipeline_state": {"type": "string", "enum": list(bundle_model.pipeline_model.STATES)}, "pipeline_accepted": {"type": "boolean"}, "observability_address": {"type": "string", "pattern": "^" + bundle_model.observability_model.OBSERVABILITY_PREFIX + ":"}, "observability_state": {"type": "string", "enum": list(bundle_model.pipeline_model.STATES)}, "audit_address": {"type": "string", "pattern": "^" + bundle_model.audit_model.AUDIT_PREFIX + ":"}, "audit_state": {"type": "string", "enum": list(bundle_model.audit_model.STATES)}, "audit_accepted": {"type": "boolean"}, "query_addresses": {"type": "array", "minItems": len(bundle_model.QUERY_ARTIFACTS), "maxItems": len(bundle_model.QUERY_ARTIFACTS), "items": {"type": "string"}}, "artifact_count": {"type": "integer", "const": len(bundle_model.ARTIFACT_FILES)}, "content_address": {"type": "string", "pattern": "^" + ENTRY_PREFIX + ":"}}}


def catalog_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog.FIELDS), "properties": {"catalog_id": {"type": "string", "maxLength": 128}, "entry_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "accepted_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "ready_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "rejected_count": {"type": "integer", "minimum": 0, "maximum": MAX_ENTRIES}, "entries": {"type": "array", "maxItems": MAX_ENTRIES, "items": entry_schema()}, "content_address": {"type": "string", "pattern": "^" + CATALOG_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "catalog_prefix": CATALOG_PREFIX, "entry_prefix": ENTRY_PREFIX, "states": STATES, "limits": {"max_entries": MAX_ENTRIES, "max_artifact_bytes": bundle_model.MAX_ARTIFACT_BYTES}, "features": ("strict verified nine-file handoff ingestion", "path-free labeled entries", "canonical label and ordinal ordering", "accepted ready and rejected denominators", "content-addressed entries and catalog", "mapping replay", "JSON CSV and Markdown exports"), "schemas": ("entry", "catalog")}


__all__ = [
    "BOUNDARY",
    "CATALOG_PREFIX",
    "DEFAULT_CATALOG_ID",
    "ENTRY_PREFIX",
    "MAX_ENTRIES",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry",
    "address_catalog",
    "address_entry",
    "build_catalog",
    "build_catalog_from_directories",
    "catalog_csv",
    "catalog_from_mapping",
    "catalog_json",
    "catalog_schema",
    "capabilities",
    "entry_schema",
    "render_catalog_markdown",
    "verify_catalog",
]

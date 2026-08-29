"""Durable observability handoffs for release-evidence pipeline receipts.

The ordinary release-evidence bundle preserves the pipeline and its three
operator query views.  This companion bundle preserves the derived
observability projection, all bounded event/metric views, and the independent
observability audit.  It is intentionally an exact-member, canonical-JSON
directory so an offline consumer can verify the operational evidence without
the source history directory or a running service.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability as observability_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit as audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query as audit_query_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query as query_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = pipeline_model.VERSION + "-observability-bundle-v1"
BOUNDARY = pipeline_model.BOUNDARY + "_observability_bundle"
BUNDLE_PREFIX = pipeline_model.PIPELINE_PREFIX + "-observability-bundle"
MANIFEST_PREFIX = BUNDLE_PREFIX + "-manifest"
FILES = (
    "manifest.json",
    "pipeline.json",
    "observability.json",
    "events-query.json",
    "metrics-query.json",
    "accepted-query.json",
    "rejected-query.json",
    "audit.json",
    "audit-checks-query.json",
)
MANIFEST_NAME, PIPELINE_NAME, OBSERVABILITY_NAME, EVENTS_NAME, METRICS_NAME, ACCEPTED_NAME, REJECTED_NAME, AUDIT_NAME, AUDIT_QUERY_NAME = FILES
ARTIFACT_FILES = FILES[1:]
OBSERVABILITY_QUERY_ARTIFACTS = (EVENTS_NAME, METRICS_NAME, ACCEPTED_NAME, REJECTED_NAME)
QUERY_ARTIFACTS = OBSERVABILITY_QUERY_ARTIFACTS + (AUDIT_QUERY_NAME,)
MAX_ARTIFACT_BYTES = 256 * 1024


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must contain at most {maximum} items")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return pipeline_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundle:
    """A path-free receipt for a complete observability handoff."""

    FIELDS = ("pipeline_address", "pipeline_state", "pipeline_accepted", "observability_address", "observability_state", "audit_address", "audit_state", "audit_accepted", "query_addresses", "artifact_count", "manifest_address", "content_address")

    def __init__(self, pipeline_address: str, pipeline_state: str, pipeline_accepted: bool, observability_address: str, observability_state: str, audit_address: str, audit_state: str, audit_accepted: bool, query_addresses: tuple[str, ...], artifact_count: int, manifest_address: str, content_address: str) -> None:
        self.pipeline_address = _address(pipeline_address, "release evidence observability bundle pipeline address", pipeline_model.PIPELINE_PREFIX)
        self.pipeline_state = _text(pipeline_state, "release evidence observability bundle pipeline state", 32)
        self.pipeline_accepted = _bool(pipeline_accepted, "release evidence observability bundle pipeline acceptance")
        self.observability_address = _address(observability_address, "release evidence observability bundle observability address", observability_model.OBSERVABILITY_PREFIX)
        self.observability_state = _text(observability_state, "release evidence observability bundle observability state", 32)
        self.audit_address = _address(audit_address, "release evidence observability bundle audit address", audit_model.AUDIT_PREFIX)
        self.audit_state = _text(audit_state, "release evidence observability bundle audit state", 32)
        self.audit_accepted = _bool(audit_accepted, "release evidence observability bundle audit acceptance")
        if not isinstance(query_addresses, tuple) or len(query_addresses) != len(QUERY_ARTIFACTS):
            raise ValidationError("release evidence observability bundle query address count is invalid")
        self.query_addresses = tuple(_address(item, "release evidence observability bundle query address", prefix) for item, prefix in zip(query_addresses, (query_model.QUERY_PREFIX,) * len(OBSERVABILITY_QUERY_ARTIFACTS) + (audit_query_model.QUERY_PREFIX,), strict=True))
        self.artifact_count = _count(artifact_count, "release evidence observability bundle artifact count", len(ARTIFACT_FILES))
        self.manifest_address = _address(manifest_address, "release evidence observability bundle manifest address", MANIFEST_PREFIX)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.pipeline_state not in pipeline_model.STATES or self.observability_state not in pipeline_model.STATES or self.audit_state not in audit_model.STATES or self.artifact_count != len(ARTIFACT_FILES):
            raise ValidationError("release evidence observability bundle state or artifact count is invalid")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability bundle content address")
        else:
            _address(self.content_address, "release evidence observability bundle content address", BUNDLE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_bundle(self) != self.content_address):
            raise ValidationError("release evidence observability bundle address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"pipeline_address": self.pipeline_address, "pipeline_state": self.pipeline_state, "pipeline_accepted": self.pipeline_accepted, "observability_address": self.observability_address, "observability_state": self.observability_state, "audit_address": self.audit_address, "audit_state": self.audit_state, "audit_accepted": self.audit_accepted, "query_addresses": self.query_addresses, "artifact_count": self.artifact_count, "manifest_address": self.manifest_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundle:
        value = _mapping(value, "release evidence observability bundle")
        _strict(value, set(cls.FIELDS), "release evidence observability bundle")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"release evidence observability bundle is missing fields: {missing}")
        addresses = _sequence(value["query_addresses"], "release evidence observability bundle query addresses", len(QUERY_ARTIFACTS))
        return cls(value["pipeline_address"], value["pipeline_state"], value["pipeline_accepted"], value["observability_address"], value["observability_state"], value["audit_address"], value["audit_state"], value["audit_accepted"], tuple(addresses), value["artifact_count"], value["manifest_address"], value["content_address"])


def address_bundle(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundle) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundle):
        raise ValidationError("release evidence observability bundle address requires a typed bundle")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=BUNDLE_PREFIX)


def _artifact(name: str, payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ValidationError("release evidence observability bundle artifact exceeds the declared byte limit")
    return {"name": name, "size": len(payload), "hash": hash_bytes(payload, prefix=BUNDLE_PREFIX + "-artifact")}


def _query_payload(observability: observability_model.RegistryHistoryReleaseEvidencePipelineObservability, audit: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityAudit) -> dict[str, bytes]:
    observability_results = tuple(query_model.query_observability(observability, resource=resource, limit=query_model.MAX_QUERY_ITEMS) for resource in ("events", "metrics", "accepted", "rejected"))
    audit_result = audit_query_model.query_audit(audit, resource="checks", limit=audit_query_model.MAX_QUERY_ITEMS)
    results = observability_results + (audit_result,)
    return {name: canonical_bytes(result.to_dict()) for name, result in zip(QUERY_ARTIFACTS, results, strict=True)}


def _manifest(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, observability: observability_model.RegistryHistoryReleaseEvidencePipelineObservability, audit: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityAudit, payload: Mapping[str, bytes]) -> dict[str, Any]:
    query_documents = [json.loads(payload[name].decode("utf-8")) for name in QUERY_ARTIFACTS]
    manifest = {"version": VERSION, "boundary": BOUNDARY, "pipeline_address": value.content_address, "observability_address": observability.content_address, "audit_address": audit.content_address, "audit_accepted": audit.accepted, "artifact_count": len(ARTIFACT_FILES), "files": ARTIFACT_FILES, "query_addresses": tuple(document["content_address"] for document in query_documents), "artifacts": tuple(_artifact(name, payload[name]) for name in ARTIFACT_FILES)}
    manifest["manifest_address"] = content_hash(manifest | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    return manifest


def bundle_bytes(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> Mapping[str, bytes]:
    pipeline_model.verify_pipeline(value)
    observability = observability_model.build_observability(value)
    observability_model.verify_observability(observability)
    audit = audit_model.audit_observability(observability)
    audit_model.verify_audit(audit)
    payload = {PIPELINE_NAME: canonical_bytes(value.to_dict()), OBSERVABILITY_NAME: canonical_bytes(observability.to_dict()), AUDIT_NAME: canonical_bytes(audit.to_dict())}
    payload.update(_query_payload(observability, audit))
    manifest = _manifest(value, observability, audit, payload)
    return {MANIFEST_NAME: canonical_bytes(manifest), **payload}


def build_bundle(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundle:
    payload = bundle_bytes(value)
    manifest = json.loads(payload[MANIFEST_NAME].decode("utf-8"))
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundle(value.content_address, value.state, value.accepted, manifest["observability_address"], value.state, manifest["audit_address"], "complete", manifest["audit_accepted"], tuple(manifest["query_addresses"]), len(ARTIFACT_FILES), manifest["manifest_address"], "pending:observability-bundle")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundle(**provisional.to_dict() | {"content_address": address_bundle(provisional)})


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("release evidence observability bundle destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir() or {item.name for item in destination.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
            raise ValidationError("release evidence observability bundle destination is not an exact compatible directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-release-evidence-observability-bundle-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (temporary / name).write_bytes(payload[name])
        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def write_bundle(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), bundle_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("release evidence observability bundle input must be a regular directory")
    members = tuple(directory.iterdir())
    if {item.name for item in members} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in members):
        raise ValidationError("release evidence observability bundle member set is invalid")
    return {name: (directory / name).read_bytes() for name in FILES}


def load_bundle(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundle:
    payload = _read_directory(source)
    try:
        documents = {name: json.loads(payload[name].decode("utf-8")) for name in FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("release evidence observability bundle contains invalid JSON") from error
    if any(len(payload[name]) > MAX_ARTIFACT_BYTES for name in FILES) or any(canonical_bytes(documents[name]) != payload[name] for name in FILES):
        raise ValidationError("release evidence observability bundle artifacts are not canonical or exceed the byte limit")
    manifest = _mapping(documents[MANIFEST_NAME], "release evidence observability bundle manifest")
    manifest_fields = {"version", "boundary", "pipeline_address", "observability_address", "audit_address", "audit_accepted", "artifact_count", "files", "query_addresses", "artifacts", "manifest_address"}
    _strict(manifest, manifest_fields, "release evidence observability bundle manifest")
    pipeline = pipeline_model.pipeline_from_mapping(_mapping(documents[PIPELINE_NAME], "release evidence observability bundle pipeline document"))
    observability = observability_model.observability_from_mapping(_mapping(documents[OBSERVABILITY_NAME], "release evidence observability bundle observability document"))
    audit = audit_model.audit_result_from_mapping(_mapping(documents[AUDIT_NAME], "release evidence observability bundle audit document"))
    for name in OBSERVABILITY_QUERY_ARTIFACTS:
        query_model.query_from_mapping(_mapping(documents[name], f"release evidence observability bundle {name} document"))
    audit_query_model.query_result_from_mapping(_mapping(documents[AUDIT_QUERY_NAME], "release evidence observability bundle audit query document"))
    pipeline_model.verify_pipeline(pipeline)
    observability_model.verify_observability(observability)
    audit_model.verify_audit(audit)
    expected = bundle_bytes(pipeline)
    if any(expected[name] != payload[name] for name in FILES) or observability.content_address != documents[OBSERVABILITY_NAME]["content_address"] or audit.content_address != documents[AUDIT_NAME]["content_address"]:
        raise ValidationError("release evidence observability bundle manifest, projections, queries, or linkage is invalid")
    return build_bundle(pipeline)


def verify_bundle(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundle:
    return load_bundle(source)


def bundle_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundle) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundle):
        raise ValidationError("release evidence observability bundle JSON requires a typed bundle")
    value._validate()
    return canonical_json(value.to_dict())


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "observability_address": {"type": "string", "pattern": "^" + observability_model.OBSERVABILITY_PREFIX + ":"}, "audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "audit_accepted": {"type": "boolean"}, "artifact_count": {"type": "integer", "const": len(ARTIFACT_FILES)}, "files": {"type": "array", "const": list(ARTIFACT_FILES)}, "query_addresses": {"type": "array", "minItems": len(QUERY_ARTIFACTS), "maxItems": len(QUERY_ARTIFACTS), "items": {"type": "string"}}, "artifacts": {"type": "array", "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES), "items": {"type": "object", "additionalProperties": False, "required": ["name", "size", "hash"], "properties": {"name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 0, "maximum": MAX_ARTIFACT_BYTES}, "hash": {"type": "string"}}}}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def bundle_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["manifest", "pipeline", "observability", "events_query", "metrics_query", "accepted_query", "rejected_query", "audit", "audit_checks_query"], "properties": {"manifest": manifest_schema(), "pipeline": pipeline_model.pipeline_schema(), "observability": observability_model.observability_schema(), "events_query": query_model.query_result_schema(), "metrics_query": query_model.query_result_schema(), "accepted_query": query_model.query_result_schema(), "rejected_query": query_model.query_result_schema(), "audit": audit_model.audit_schema(), "audit_checks_query": audit_query_model.query_result_schema()}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifact_files": ARTIFACT_FILES, "query_artifacts": QUERY_ARTIFACTS, "limits": {"max_artifact_bytes": MAX_ARTIFACT_BYTES, "artifact_count": len(ARTIFACT_FILES), "observability_queries": len(OBSERVABILITY_QUERY_ARTIFACTS), "audit_queries": 1}, "features": ("exact nine-file persistence", "canonical UTF-8 JSON", "atomic writes", "pipeline receipt capture", "observability projection capture", "event and metric query capture", "accepted and rejected event query capture", "independent observability audit capture", "audit check query capture", "rejected-pipeline diagnostic preservation", "artifact byte receipts", "manifest address replay", "safe bundle reload", "path-free public documents"), "schemas": ("bundle", "manifest")}


__all__ = [
    "ARTIFACT_FILES",
    "AUDIT_NAME",
    "AUDIT_QUERY_NAME",
    "BOUNDARY",
    "BUNDLE_PREFIX",
    "EVENTS_NAME",
    "FILES",
    "MANIFEST_NAME",
    "MANIFEST_PREFIX",
    "MAX_ARTIFACT_BYTES",
    "OBSERVABILITY_NAME",
    "OBSERVABILITY_QUERY_ARTIFACTS",
    "PIPELINE_NAME",
    "QUERY_ARTIFACTS",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundle",
    "address_bundle",
    "build_bundle",
    "bundle_bytes",
    "bundle_json",
    "bundle_schema",
    "capabilities",
    "load_bundle",
    "manifest_schema",
    "verify_bundle",
    "write_bundle",
]

"""Durable, replayable bundles for release-evidence pipeline handoffs.

The bundle captures a pipeline receipt and its three bounded query views in a
small exact-member directory.  Every file is canonical JSON, every artifact
has a byte receipt, and reload reconstructs the same content-addressed bundle
without retaining the source path.
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
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query as query_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = pipeline_model.VERSION + "-bundle-v1"
BOUNDARY = pipeline_model.BOUNDARY + "_bundle"
BUNDLE_PREFIX = pipeline_model.PIPELINE_PREFIX + "-bundle"
MANIFEST_PREFIX = BUNDLE_PREFIX + "-manifest"
FILES = ("manifest.json", "pipeline.json", "stages-query.json", "decisions-query.json", "evidence-query.json")
MANIFEST_NAME, PIPELINE_NAME, STAGES_NAME, DECISIONS_NAME, EVIDENCE_NAME = FILES
ARTIFACT_FILES = FILES[1:]
QUERY_ARTIFACTS = (STAGES_NAME, DECISIONS_NAME, EVIDENCE_NAME)
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return pipeline_model._public(value)


class RegistryHistoryReleaseEvidencePipelineBundle:
    """A path-free receipt for one durable evidence bundle."""

    def __init__(self, pipeline_address: str, pipeline_state: str, pipeline_accepted: bool, query_addresses: tuple[str, ...], artifact_count: int, manifest_address: str, content_address: str) -> None:
        self.pipeline_address = _address(pipeline_address, "release evidence bundle pipeline address", pipeline_model.PIPELINE_PREFIX)
        self.pipeline_state = _text(pipeline_state, "release evidence bundle pipeline state", 32)
        self.pipeline_accepted = _bool(pipeline_accepted, "release evidence bundle pipeline acceptance")
        if not isinstance(query_addresses, tuple):
            raise ValidationError("release evidence bundle query addresses must be a tuple")
        if len(query_addresses) != len(QUERY_ARTIFACTS):
            raise ValidationError("release evidence bundle query address count is invalid")
        self.query_addresses = tuple(_address(item, "release evidence bundle query address", query_model.QUERY_PREFIX) for item in query_addresses)
        self.artifact_count = _count(artifact_count, "release evidence bundle artifact count", len(ARTIFACT_FILES))
        self.manifest_address = _address(manifest_address, "release evidence bundle manifest address", MANIFEST_PREFIX)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.pipeline_state not in pipeline_model.STATES or self.artifact_count != len(ARTIFACT_FILES):
            raise ValidationError("release evidence bundle state or artifact count is invalid")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence bundle content address")
        else:
            _address(self.content_address, "release evidence bundle content address", BUNDLE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_bundle(self) != self.content_address):
            raise ValidationError("release evidence bundle address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"pipeline_address": self.pipeline_address, "pipeline_state": self.pipeline_state, "pipeline_accepted": self.pipeline_accepted, "query_addresses": self.query_addresses, "artifact_count": self.artifact_count, "manifest_address": self.manifest_address, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineBundle:
        value = _mapping(value, "release evidence bundle")
        _strict(value, {"pipeline_address", "pipeline_state", "pipeline_accepted", "query_addresses", "artifact_count", "manifest_address", "content_address"}, "release evidence bundle")
        addresses = value["query_addresses"]
        if isinstance(addresses, (str, bytes)) or not isinstance(addresses, (list, tuple)):
            raise ValidationError("release evidence bundle query addresses must be a sequence")
        return cls(value["pipeline_address"], value["pipeline_state"], value["pipeline_accepted"], tuple(addresses), value["artifact_count"], value["manifest_address"], value["content_address"])


def address_bundle(value: RegistryHistoryReleaseEvidencePipelineBundle) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundle):
        raise ValidationError("release evidence bundle address requires a typed bundle")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=BUNDLE_PREFIX)


def _artifact(name: str, payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ValidationError("release evidence bundle artifact exceeds the declared byte limit")
    return {"name": name, "size": len(payload), "hash": hash_bytes(payload, prefix=BUNDLE_PREFIX + "-artifact")}


def _query_payload(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> dict[str, bytes]:
    results = (
        query_model.query_pipeline(value, resource="stages", limit=query_model.MAX_QUERY_ITEMS),
        query_model.query_pipeline(value, resource="decisions", limit=query_model.MAX_QUERY_ITEMS),
        query_model.query_pipeline(value, resource="evidence", limit=query_model.MAX_QUERY_ITEMS),
    )
    names = QUERY_ARTIFACTS
    return {name: canonical_bytes(result.to_dict()) for name, result in zip(names, results, strict=True)}


def _manifest(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, payload: Mapping[str, bytes]) -> dict[str, Any]:
    query_documents = [json.loads(payload[name].decode("utf-8")) for name in QUERY_ARTIFACTS]
    manifest = {"version": VERSION, "boundary": BOUNDARY, "pipeline_address": value.content_address, "artifact_count": len(ARTIFACT_FILES), "files": ARTIFACT_FILES, "query_addresses": tuple(document["content_address"] for document in query_documents), "artifacts": tuple(_artifact(name, payload[name]) for name in ARTIFACT_FILES)}
    manifest["manifest_address"] = content_hash(manifest | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    return manifest


def bundle_bytes(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> Mapping[str, bytes]:
    pipeline_model.verify_pipeline(value)
    payload = {PIPELINE_NAME: canonical_bytes(value.to_dict())}
    payload.update(_query_payload(value))
    manifest = _manifest(value, payload)
    return {MANIFEST_NAME: canonical_bytes(manifest), **payload}


def build_bundle(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> RegistryHistoryReleaseEvidencePipelineBundle:
    payload = bundle_bytes(value)
    manifest = json.loads(payload[MANIFEST_NAME].decode("utf-8"))
    provisional = RegistryHistoryReleaseEvidencePipelineBundle(value.content_address, value.state, value.accepted, tuple(manifest["query_addresses"]), len(ARTIFACT_FILES), manifest["manifest_address"], "pending:bundle")
    return RegistryHistoryReleaseEvidencePipelineBundle(**provisional.to_dict() | {"content_address": address_bundle(provisional)})


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("release evidence bundle destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir() or {item.name for item in destination.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
            raise ValidationError("release evidence bundle destination is not an exact compatible directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-release-evidence-bundle-", dir=str(destination.parent)))
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
        raise ValidationError("release evidence bundle input must be a regular directory")
    members = tuple(directory.iterdir())
    if {item.name for item in members} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in members):
        raise ValidationError("release evidence bundle member set is invalid")
    return {name: (directory / name).read_bytes() for name in FILES}


def load_bundle(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineBundle:
    payload = _read_directory(source)
    try:
        documents = {name: json.loads(payload[name].decode("utf-8")) for name in FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("release evidence bundle contains invalid JSON") from error
    if any(len(payload[name]) > MAX_ARTIFACT_BYTES for name in FILES) or any(canonical_bytes(documents[name]) != payload[name] for name in FILES):
        raise ValidationError("release evidence bundle artifacts are not canonical or exceed the byte limit")
    manifest = _mapping(documents[MANIFEST_NAME], "release evidence bundle manifest")
    _strict(manifest, {"version", "boundary", "pipeline_address", "artifact_count", "files", "query_addresses", "artifacts", "manifest_address"}, "release evidence bundle manifest")
    pipeline = pipeline_model.pipeline_from_mapping(_mapping(documents[PIPELINE_NAME], "release evidence bundle pipeline document"))
    for name in QUERY_ARTIFACTS:
        query_model.query_result_from_mapping(_mapping(documents[name], f"release evidence bundle {name} document"))
    expected = bundle_bytes(pipeline)
    if any(expected[name] != payload[name] for name in FILES):
        raise ValidationError("release evidence bundle manifest, query views, or pipeline linkage is invalid")
    return build_bundle(pipeline)


def verify_bundle(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineBundle:
    return load_bundle(source)


def bundle_json(value: RegistryHistoryReleaseEvidencePipelineBundle) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineBundle):
        raise ValidationError("release evidence bundle JSON requires a typed bundle")
    value._validate()
    return canonical_json(value.to_dict())


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "pipeline_address", "artifact_count", "files", "query_addresses", "artifacts", "manifest_address"], "properties": {"version": {"const": VERSION, "type": "string"}, "boundary": {"const": BOUNDARY, "type": "string"}, "pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "artifact_count": {"const": len(ARTIFACT_FILES), "type": "integer"}, "files": {"const": list(ARTIFACT_FILES), "type": "array"}, "query_addresses": {"type": "array", "minItems": len(QUERY_ARTIFACTS), "maxItems": len(QUERY_ARTIFACTS), "items": {"type": "string", "pattern": "^" + query_model.QUERY_PREFIX + ":"}}, "artifacts": {"type": "array", "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES), "items": {"type": "object", "additionalProperties": False, "required": ["name", "size", "hash"], "properties": {"name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 0, "maximum": MAX_ARTIFACT_BYTES}, "hash": {"type": "string"}}}}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def bundle_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["manifest", "pipeline", "stages_query", "decisions_query", "evidence_query"], "properties": {"manifest": manifest_schema(), "pipeline": pipeline_model.pipeline_schema(), "stages_query": query_model.query_result_schema(), "decisions_query": query_model.query_result_schema(), "evidence_query": query_model.query_result_schema()}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifact_files": ARTIFACT_FILES, "limits": {"max_artifact_bytes": MAX_ARTIFACT_BYTES, "artifact_count": len(ARTIFACT_FILES)}, "features": ("exact five-file persistence", "canonical UTF-8 JSON", "atomic writes", "pipeline receipt capture", "stage decision and evidence query capture", "artifact byte receipts", "manifest address replay", "safe bundle reload", "path-free public documents"), "schemas": ("bundle", "manifest")}


__all__ = [
    "ARTIFACT_FILES",
    "BOUNDARY",
    "BUNDLE_PREFIX",
    "DECISIONS_NAME",
    "EVIDENCE_NAME",
    "FILES",
    "MANIFEST_NAME",
    "MANIFEST_PREFIX",
    "MAX_ARTIFACT_BYTES",
    "PIPELINE_NAME",
    "QUERY_ARTIFACTS",
    "STAGES_NAME",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineBundle",
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

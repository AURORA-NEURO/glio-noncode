"""Durable, replayable packages for registry-history release decisions.

The release gate is useful in memory, but a handoff needs an exact artifact
package that can be copied, verified, and reloaded independently of the
history directory.  This boundary stores only public JSON projections in
three files with canonical bytes and content-addressed receipts.  It never
stores the input path or mutable process metadata.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_bytes, content_hash, hash_bytes


VERSION = gate_model.VERSION + "-package-v1"
BOUNDARY = gate_model.BOUNDARY + "_package"
PACKAGE_PREFIX = gate_model.GATE_PREFIX + "-package"
MANIFEST_PREFIX = PACKAGE_PREFIX + "-manifest"
FILES = ("manifest.json", "policy.json", "gate.json")
MANIFEST_NAME, POLICY_NAME, GATE_NAME = FILES


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
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
    return gate_model._public(value)


def _artifact(name: str, payload: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(payload), "hash": hash_bytes(payload, prefix=PACKAGE_PREFIX + "-artifact")}


def _manifest(value: gate_model.RegistryHistoryReleaseGate, payload: Mapping[str, bytes]) -> dict[str, Any]:
    manifest = {"version": VERSION, "boundary": BOUNDARY, "gate_address": value.content_address, "policy_address": value.policy_address, "artifact_count": 2, "files": (POLICY_NAME, GATE_NAME), "artifacts": (_artifact(POLICY_NAME, payload[POLICY_NAME]), _artifact(GATE_NAME, payload[GATE_NAME]))}
    manifest["manifest_address"] = content_hash(manifest | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    return manifest


def package_bytes(value: gate_model.RegistryHistoryReleaseGate) -> Mapping[str, bytes]:
    gate_model.verify_gate(value)
    payload = {POLICY_NAME: canonical_bytes(value.policy.to_dict()), GATE_NAME: canonical_bytes(value.to_dict())}
    manifest = _manifest(value, payload)
    return {MANIFEST_NAME: canonical_bytes(manifest), POLICY_NAME: payload[POLICY_NAME], GATE_NAME: payload[GATE_NAME]}


def package_manifest_json(value: gate_model.RegistryHistoryReleaseGate) -> str:
    return package_bytes(value)[MANIFEST_NAME].decode("utf-8")


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("registry history release gate package destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir() or {item.name for item in destination.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
            raise ValidationError("registry history release gate package destination is not an exact compatible directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-history-release-gate-", dir=str(destination.parent)))
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


def write_package(value: gate_model.RegistryHistoryReleaseGate, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), package_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("registry history release gate package input must be a regular directory")
    members = tuple(directory.iterdir())
    if {item.name for item in members} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in members):
        raise ValidationError("registry history release gate package member set is invalid")
    return {name: (directory / name).read_bytes() for name in FILES}


def load_package(source: str | Path) -> gate_model.RegistryHistoryReleaseGate:
    payload = _read_directory(source)
    try:
        documents = {name: json.loads(payload[name].decode("utf-8")) for name in FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry history release gate package contains invalid JSON") from error
    if any(canonical_bytes(documents[name]) != payload[name] for name in FILES):
        raise ValidationError("registry history release gate package artifacts are not canonical")
    gate_value = gate_model.gate_from_mapping(_mapping(documents[GATE_NAME], "registry history release gate document"))
    policy = gate_model.RegistryHistoryReleasePolicy.from_mapping(_mapping(documents[POLICY_NAME], "registry history release gate policy document"))
    manifest = _mapping(documents[MANIFEST_NAME], "registry history release gate package manifest")
    _strict(manifest, {"version", "boundary", "gate_address", "policy_address", "artifact_count", "files", "artifacts", "manifest_address"}, "registry history release gate package manifest")
    expected_manifest = _manifest(gate_value, {POLICY_NAME: payload[POLICY_NAME], GATE_NAME: payload[GATE_NAME]})
    if canonical_bytes(manifest) != canonical_bytes(expected_manifest):
        raise ValidationError("registry history release gate package manifest or receipts are invalid")
    if policy.to_dict() != gate_value.policy.to_dict() or gate_value.policy_address != gate_model.address_policy(policy):
        raise ValidationError("registry history release gate package policy projection is not linked")
    return gate_value


def verify_package(source: str | Path) -> gate_model.RegistryHistoryReleaseGate:
    return load_package(source)


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["manifest", "policy", "gate"], "properties": {"manifest": {"type": "object"}, "policy": gate_model.policy_schema(), "gate": gate_model.gate_schema()}}


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"const": VERSION, "type": "string"}, "boundary": {"const": BOUNDARY, "type": "string"}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + gate_model.POLICY_PREFIX + ":"}, "artifact_count": {"const": 2, "type": "integer"}, "files": {"const": [POLICY_NAME, GATE_NAME], "type": "array"}, "artifacts": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "object", "additionalProperties": False, "required": ["name", "size", "hash"], "properties": {"name": {"type": "string", "enum": [POLICY_NAME, GATE_NAME]}, "size": {"type": "integer", "minimum": 0}, "hash": {"type": "string"}}}}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "files": FILES, "limits": {"max_artifacts": 2}, "features": ("exact three-file persistence", "canonical UTF-8 JSON", "atomic writes", "artifact byte receipts", "manifest address replay", "gate and policy projection linkage", "safe package reload", "path-free public documents"), "schemas": ("package", "manifest")}


__all__ = [
    "BOUNDARY",
    "FILES",
    "GATE_NAME",
    "MANIFEST_NAME",
    "MANIFEST_PREFIX",
    "PACKAGE_PREFIX",
    "POLICY_NAME",
    "VERSION",
    "capabilities",
    "load_package",
    "manifest_schema",
    "package_bytes",
    "package_manifest_json",
    "package_schema",
    "verify_package",
    "write_package",
]

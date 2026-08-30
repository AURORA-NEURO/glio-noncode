"""End-to-end runtime for building an archive registry from package inputs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit as audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_query as query_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_query_audit as query_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-runtime-v1"
BOUNDARY = registry_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = registry_model.REGISTRY_PREFIX + "-runtime"
DEFAULT_RUNTIME_ID = "consensus-certificate-observatory-archive-registry-runtime"
DEFAULT_LIMIT = query_model.DEFAULT_LIMIT


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime:
    """Path-free composition receipt for registry construction and inspection."""

    FIELDS = ("runtime_id", "version", "boundary", "input_count", "registry_address", "audit_address", "query_address", "registry_written", "accepted", "content_address")

    def __init__(self, runtime_id: str, version: str, boundary: str, input_count: int, registry_address: str, audit_address: str, query_address: str, registry_written: bool, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "registry runtime ID")
        self.version = _text(version, "registry runtime version", 1024)
        self.boundary = _text(boundary, "registry runtime boundary")
        self.input_count = _count(input_count, "registry runtime input count", registry_model.MAX_ENTRIES, positive=True)
        self.registry_address = _address(registry_address, "registry runtime registry address", registry_model.REGISTRY_PREFIX)
        self.audit_address = _address(audit_address, "registry runtime audit address", audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "registry runtime query address", query_model.RESULT_PREFIX)
        self.registry_written = _bool(registry_written, "registry runtime persistence")
        self.accepted = _bool(accepted, "registry runtime acceptance")
        self.content_address = _address(content_address, "registry runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "registry runtime address")
        self._validate()

    def _validate(self) -> None:
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("registry runtime address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("registry runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime":
        value = _mapping(value, "registry runtime")
        _strict(value, set(cls.FIELDS), "registry runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime):
        raise ValidationError("registry runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _load_archive_input(source: str | Path, *, archive_id: str | None = None) -> archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive:
    path = Path(source)
    if path.is_dir():
        package = package_model.load_package(path)
        selected_id = package.package_id + "-archive" if archive_id is None else archive_id
        return archive_model.build_archive(package, archive_id=selected_id)
    if path.is_file() and path.suffix.lower() == ".zip":
        archive = archive_model.load_archive(path)
        if archive_id is not None and archive.archive_id != archive_id:
            raise ValidationError("archive file identity does not match requested archive ID")
        return archive
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("registry runtime input is not a package directory, archive ZIP, or archive JSON") from error
    if not isinstance(raw, Mapping):
        raise ValidationError("registry runtime JSON input must be an object")
    if "artifact_count" in raw and "archive_id" in raw:
        archive = archive_model.archive_from_mapping(raw)
        if archive_id is not None and archive.archive_id != archive_id:
            raise ValidationError("archive JSON identity does not match requested archive ID")
        return archive
    if "package_id" in raw:
        return archive_model.build_archive(package_model.package_from_mapping(raw), archive_id=archive_id or str(raw["package_id"]) + "-archive")
    raise ValidationError("registry runtime JSON input is not an archive or package")


def load_archive_input(source: str | Path, *, archive_id: str | None = None) -> archive_model.RegistryFederationConsensusGateCertificateObservatoryArchive:
    """Load one package-shaped input and materialize its addressed archive."""

    return _load_archive_input(source, archive_id=archive_id)


def _selected_ids(values: Sequence[str | Path], entry_ids: Sequence[str] | None) -> tuple[str, ...]:
    if entry_ids is not None:
        selected = tuple(_label(item, "registry runtime entry ID") for item in _sequence(entry_ids, "registry runtime entry IDs", registry_model.MAX_ENTRIES))
        if len(selected) != len(values):
            raise ValidationError("registry runtime entry ID count must match input count")
        return selected
    return tuple(f"input-{index:03d}" for index in range(1, len(values) + 1))


def run_runtime(inputs: Sequence[str | Path], *, runtime_id: str = DEFAULT_RUNTIME_ID, registry_id: str = registry_model.DEFAULT_REGISTRY_ID, entry_ids: Sequence[str] | None = None, archive_ids: Sequence[str] | None = None, package_id: str | None = None, query_resources: Sequence[str] = query_model.DEFAULT_RESOURCES, package_filter: str = "", archive_filter: str = "", accepted: bool | None = None, text: str = "", offset: int = 0, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime:
    sources = tuple(_sequence(inputs, "registry runtime inputs", registry_model.MAX_ENTRIES))
    if not sources:
        raise ValidationError("registry runtime requires at least one input")
    selected_entry_ids = _selected_ids(sources, entry_ids)
    selected_archive_ids = None if archive_ids is None else tuple(_label(item, "registry runtime archive ID") for item in _sequence(archive_ids, "registry runtime archive IDs", registry_model.MAX_ENTRIES))
    if selected_archive_ids is not None and len(selected_archive_ids) != len(sources):
        raise ValidationError("registry runtime archive ID count must match input count")
    archives = tuple(load_archive_input(source, archive_id=None if selected_archive_ids is None else selected_archive_ids[index]) for index, source in enumerate(sources))
    registry = registry_model.build_registry_from_archives(archives, entry_ids=selected_entry_ids, registry_id=registry_id)
    audit = audit_model.audit_registry(registry)
    result = query_model.query_registry(registry, resources=query_resources, package_id=package_filter, archive_id=archive_filter, accepted=accepted, text=text, offset=offset, limit=limit)
    query_audit = query_audit_model.audit_query(result, registry)
    if destination is not None:
        registry_model.write_registry(registry, destination, overwrite=overwrite)
    persisted = destination is not None and Path(destination).is_dir()
    accepted_result = audit.accepted and query_audit.accepted and (destination is None or persisted)
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime(runtime_id, VERSION, BOUNDARY, len(sources), registry.content_address, audit.content_address, result.content_address, persisted, accepted_result, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime(provisional.runtime_id, provisional.version, provisional.boundary, provisional.input_count, provisional.registry_address, provisional.audit_address, provisional.query_address, provisional.registry_written, provisional.accepted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime.from_mapping(value)


def verify_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("registry runtime is not valid")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) -> str:
    value = verify_runtime(value)
    stream = io.StringIO()
    fields = ("runtime_id", "input_count", "registry_address", "audit_address", "query_address", "registry_written", "accepted", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_runtime_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime) -> str:
    value = verify_runtime(value)
    lines = ["# Certificate Observatory Archive Registry Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Inputs: `{value.input_count}`", f"- Registry: `{value.registry_address}`", f"- Audit: `{value.audit_address}`", f"- Query: `{value.query_address}`", f"- Persisted: `{value.registry_written}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", ""]
    return "\n".join(lines)


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "input_count": {"type": "integer", "minimum": 1}, "registry_address": {"type": "string"}, "audit_address": {"type": "string"}, "query_address": {"type": "string"}, "registry_written": {"type": "boolean"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "features": ("package and archive input loading", "multi-archive registry construction", "independent registry audit", "bounded registry query and audit", "optional atomic persistence", "path-free runtime receipt", "JSON CSV and Markdown exports"), "limits": {"max_inputs": registry_model.MAX_ENTRIES, "max_query_items": registry_model.MAX_QUERY_ITEMS}, "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "RUNTIME_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryRuntime", "VERSION", "address_runtime", "capabilities", "load_archive_input", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "render_runtime_markdown", "verify_runtime"]

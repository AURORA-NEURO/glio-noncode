"""End-to-end archive and transfer runtime for certificate observatories.

This runtime is the CI-facing composition point.  It loads one or more
downloaded observatory package inputs, builds the deterministic archive,
audits the archive, derives a bounded query and query audit, optionally writes
the ZIP, builds a resumable transfer, and optionally writes the complete
transfer directory.  The returned envelope is path-free and retains every
stage address needed to inspect the handoff later.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from . import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_audit as archive_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_query as query_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_query_audit as query_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer as transfer_model
from . import registry_federation_consensus_gate_certificate_observatory_archive_transfer_audit as transfer_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = transfer_model.VERSION + "-runtime-v1"
BOUNDARY = transfer_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = transfer_model.TRANSFER_PREFIX + "-runtime"
DEFAULT_RUNTIME_ID = "consensus-certificate-observatory-archive-runtime"
DEFAULT_LIMIT = query_model.DEFAULT_LIMIT


def _text(value: Any, field: str, maximum: int = 512, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong namespace")
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
    return archive_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime:
    """A path-free receipt for the composed archive lifecycle."""

    FIELDS = ("runtime_id", "version", "boundary", "input_count", "package_address", "archive_address", "archive_audit_address", "query_address", "query_audit_address", "transfer_address", "transfer_audit_address", "archive_written", "transfer_written", "accepted", "content_address")

    def __init__(self, runtime_id: str, version: str, boundary: str, input_count: int, package_address: str, archive_address: str, archive_audit_address: str, query_address: str, query_audit_address: str, transfer_address: str, transfer_audit_address: str, archive_written: bool, transfer_written: bool, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime ID")
        self.version = _text(version, "runtime version", 1024)
        self.boundary = _text(boundary, "runtime boundary")
        self.input_count = _count(input_count, "runtime input count", 256, positive=True)
        self.package_address = _address(package_address, "runtime package address", package_model.PACKAGE_PREFIX)
        self.archive_address = _address(archive_address, "runtime archive address", archive_model.ARCHIVE_PREFIX)
        self.archive_audit_address = _address(archive_audit_address, "runtime archive audit address", archive_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "runtime query address", query_model.RESULT_PREFIX)
        self.query_audit_address = _address(query_audit_address, "runtime query audit address", query_audit_model.AUDIT_PREFIX)
        self.transfer_address = _address(transfer_address, "runtime transfer address", transfer_model.TRANSFER_PREFIX)
        self.transfer_audit_address = _address(transfer_audit_address, "runtime transfer audit address", transfer_audit_model.AUDIT_PREFIX)
        self.archive_written = _bool(archive_written, "runtime archive persistence")
        self.transfer_written = _bool(transfer_written, "runtime transfer persistence")
        self.accepted = _bool(accepted, "runtime acceptance")
        self.content_address = _address(content_address, "runtime content address", RUNTIME_PREFIX)
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("runtime address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime":
        value = _mapping(value, "archive runtime")
        _strict(value, set(cls.FIELDS), "archive runtime")
        return cls(*(value[field] for field in cls.FIELDS))


def address_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime):
        raise ValidationError("runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _load_package_input(source: str | Path) -> package_model.RegistryFederationConsensusGateCertificateObservatoryPackage:
    path = Path(source)
    if path.is_dir():
        return package_model.load_package(path)
    if path.is_file() and path.suffix.lower() == ".zip":
        return archive_model.load_archive(path).package  # type: ignore[return-value]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("runtime input is not a readable package or observatory document") from error
    if not isinstance(raw, Mapping):
        raise ValidationError("runtime input JSON must be an object")
    if "package_id" in raw and "observatory" in raw:
        return package_model.package_from_mapping(raw)
    return package_model.build_package(observatory_model.observatory_from_mapping(raw))


def run_runtime(inputs: Sequence[str | Path], *, runtime_id: str = DEFAULT_RUNTIME_ID, archive_id: str = archive_model.DEFAULT_ARCHIVE_ID, transfer_id: str = transfer_model.DEFAULT_TRANSFER_ID, chunk_size: int = transfer_model.DEFAULT_CHUNK_SIZE, limit: int = DEFAULT_LIMIT, destination: str | Path | None = None, transfer_destination: str | Path | None = None) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime:
    sources = tuple(_sequence(inputs, "runtime inputs", 256))
    if not sources:
        raise ValidationError("archive runtime requires at least one input")
    packages = tuple(_load_package_input(source) for source in sources)
    first = packages[0]
    if any(package.content_address != first.content_address for package in packages[1:]):
        raise ValidationError("runtime inputs must identify one package address")
    archive = archive_model.build_archive(first, archive_id=archive_id)
    archive_audit = archive_audit_model.audit_archive(archive)
    query = query_model.query_archive(archive, resources=query_model.DEFAULT_RESOURCES, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    if destination is not None:
        archive_model.write_archive(archive, destination)
    transfer = transfer_model.build_transfer(archive, transfer_id=transfer_id, chunk_size=chunk_size)
    assembler = transfer_model.TransferAssembler(transfer, transfer._payload)
    transfer_audit = transfer_audit_model.audit_transfer(assembler)
    if transfer_destination is not None:
        transfer_model.write_transfer(transfer, transfer_destination)
    accepted = archive_audit.accepted and query_audit.accepted and transfer_audit.accepted and (destination is None or Path(destination).is_file()) and (transfer_destination is None or Path(transfer_destination).is_dir())
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime(runtime_id, VERSION, BOUNDARY, len(packages), first.content_address, archive.content_address, archive_audit.content_address, query.content_address, query_audit.content_address, transfer.content_address, transfer_audit.content_address, destination is not None, transfer_destination is not None, accepted, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime(provisional.runtime_id, provisional.version, provisional.boundary, provisional.input_count, provisional.package_address, provisional.archive_address, provisional.archive_audit_address, provisional.query_address, provisional.query_audit_address, provisional.transfer_address, provisional.transfer_audit_address, provisional.archive_written, provisional.transfer_written, provisional.accepted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime:
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime.from_mapping(value)


def verify_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("archive runtime is not valid")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) -> str:
    value = verify_runtime(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("runtime_id", "input_count", "package_address", "archive_address", "archive_audit_address", "query_address", "query_audit_address", "transfer_address", "transfer_audit_address", "archive_written", "transfer_written", "accepted", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerow({key: value.to_dict()[key] for key in writer.fieldnames})
    return stream.getvalue()


def render_runtime_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime) -> str:
    value = verify_runtime(value)
    lines = ["# Certificate Observatory Archive Runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Inputs: `{value.input_count}`", f"- Archive: `{value.archive_address}`", f"- Archive audit: `{value.archive_audit_address}`", f"- Query audit: `{value.query_audit_address}`", f"- Transfer: `{value.transfer_address}`", f"- Transfer audit: `{value.transfer_audit_address}`", f"- Archive written: `{value.archive_written}`", f"- Transfer written: `{value.transfer_written}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", ""]
    return "\n".join(lines)


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "input_count": {"type": "integer"}, "package_address": {"type": "string"}, "archive_address": {"type": "string"}, "archive_audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "transfer_address": {"type": "string"}, "transfer_audit_address": {"type": "string"}, "archive_written": {"type": "boolean"}, "transfer_written": {"type": "boolean"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "features": ("package and observatory input loading", "archive construction", "independent archive audit", "bounded archive query and audit", "resumable transfer construction", "transfer audit", "optional atomic persistence", "path-free runtime receipt", "JSON CSV and Markdown exports"), "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_RUNTIME_ID", "RUNTIME_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryArchiveRuntime", "VERSION", "address_runtime", "capabilities", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "render_runtime_markdown", "verify_runtime"]

"""End-to-end public release evidence pipeline for downloaded history data.

This orchestration boundary composes the independently testable history,
release-gate, package, package-audit, and certificate modules.  It returns a
compact path-free receipt suitable for a demo, dashboard, or handoff while
keeping the underlying artifacts independently verifiable.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package as package_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit as package_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate as certificate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = certificate_model.VERSION + "-pipeline-v1"
BOUNDARY = certificate_model.BOUNDARY + "_pipeline"
PIPELINE_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-pipeline"
STATES = ("ready", "held", "blocked")
PACKAGE_FILE_COUNT = len(package_model.FILES)


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
    return certificate_model._public(value)


class RegistryHistoryReleaseEvidencePipeline:
    """A path-free receipt for one complete release-evidence composition."""

    def __init__(
        self,
        history_id: str,
        history_address: str,
        snapshot_count: int,
        gate_address: str,
        gate_state: str,
        gate_accepted: bool,
        package_manifest_address: str,
        package_file_count: int,
        package_audit_address: str,
        package_audit_state: str,
        package_audit_accepted: bool,
        certificate_address: str,
        certificate_state: str,
        certificate_accepted: bool,
        accepted: bool,
        release_ready: bool,
        state: str,
        content_address: str,
    ) -> None:
        self.history_id = _text(history_id, "release evidence pipeline history ID")
        self.history_address = _address(history_address, "release evidence pipeline history address", history_model.HISTORY_PREFIX)
        self.snapshot_count = _count(snapshot_count, "release evidence pipeline snapshot count", history_model.MAX_SNAPSHOTS)
        self.gate_address = _address(gate_address, "release evidence pipeline gate address", gate_model.GATE_PREFIX)
        self.gate_state = _text(gate_state, "release evidence pipeline gate state", 32)
        self.gate_accepted = _bool(gate_accepted, "release evidence pipeline gate acceptance")
        self.package_manifest_address = _address(package_manifest_address, "release evidence pipeline manifest address", package_model.MANIFEST_PREFIX)
        self.package_file_count = _count(package_file_count, "release evidence pipeline package file count", PACKAGE_FILE_COUNT)
        self.package_audit_address = _address(package_audit_address, "release evidence pipeline package audit address", package_audit_model.AUDIT_PREFIX)
        self.package_audit_state = _text(package_audit_state, "release evidence pipeline package audit state", 32)
        self.package_audit_accepted = _bool(package_audit_accepted, "release evidence pipeline package audit acceptance")
        self.certificate_address = _address(certificate_address, "release evidence pipeline certificate address", certificate_model.CERTIFICATE_PREFIX)
        self.certificate_state = _text(certificate_state, "release evidence pipeline certificate state", 32)
        self.certificate_accepted = _bool(certificate_accepted, "release evidence pipeline certificate acceptance")
        self.accepted = _bool(accepted, "release evidence pipeline accepted")
        self.release_ready = _bool(release_ready, "release evidence pipeline release-ready")
        self.state = _text(state, "release evidence pipeline state", 32)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.gate_state not in gate_model.STATES or self.package_audit_state not in package_audit_model.STATES or self.certificate_state not in certificate_model.STATES or self.state not in STATES:
            raise ValidationError("release evidence pipeline state is invalid")
        if self.package_file_count != PACKAGE_FILE_COUNT:
            raise ValidationError("release evidence pipeline package file count is invalid")
        expected_accepted = self.gate_accepted and self.certificate_accepted
        expected_ready = self.gate_accepted and self.certificate_accepted
        expected_state = "ready" if expected_accepted else ("blocked" if self.gate_state == "blocked" or self.certificate_state == "blocked" else "held")
        if self.accepted != expected_accepted or self.release_ready != expected_ready or self.state != expected_state:
            raise ValidationError("release evidence pipeline decision is not composed from its stages")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence pipeline content address")
        else:
            _address(self.content_address, "release evidence pipeline content address", PIPELINE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_pipeline(self) != self.content_address):
            raise ValidationError("release evidence pipeline address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "history_address": self.history_address,
            "snapshot_count": self.snapshot_count,
            "gate_address": self.gate_address,
            "gate_state": self.gate_state,
            "gate_accepted": self.gate_accepted,
            "package_manifest_address": self.package_manifest_address,
            "package_file_count": self.package_file_count,
            "package_audit_address": self.package_audit_address,
            "package_audit_state": self.package_audit_state,
            "package_audit_accepted": self.package_audit_accepted,
            "certificate_address": self.certificate_address,
            "certificate_state": self.certificate_state,
            "certificate_accepted": self.certificate_accepted,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "state": self.state,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipeline:
        value = _mapping(value, "release evidence pipeline")
        fields = {"history_id", "history_address", "snapshot_count", "gate_address", "gate_state", "gate_accepted", "package_manifest_address", "package_file_count", "package_audit_address", "package_audit_state", "package_audit_accepted", "certificate_address", "certificate_state", "certificate_accepted", "accepted", "release_ready", "state", "content_address"}
        _strict(value, fields, "release evidence pipeline")
        return cls(**value)


def address_pipeline(value: RegistryHistoryReleaseEvidencePipeline) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipeline):
        raise ValidationError("release evidence pipeline address requires a typed pipeline")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PIPELINE_PREFIX)


def build_pipeline(history_directory: str | Path, package_destination: str | Path | None = None, *, overwrite: bool = False, policy: gate_model.RegistryHistoryReleasePolicy | None = None, certificate_policy: certificate_model.RegistryHistoryReleaseGatePackageAuditCertificatePolicy | None = None) -> RegistryHistoryReleaseEvidencePipeline:
    """Run history, gate, package, audit, and certificate stages in order."""

    history = history_model.load_history(history_directory)
    gate = gate_model.evaluate_history(history, policy)
    if package_destination is None:
        payload = package_model.package_bytes(gate)
        loaded_gate = gate
        manifest = json.loads(payload[package_model.MANIFEST_NAME].decode("utf-8"))
        package_audit = package_audit_model.audit_gate(loaded_gate)
    else:
        package_model.write_package(gate, package_destination, overwrite=overwrite)
        loaded_gate = package_model.load_package(package_destination)
        manifest = json.loads((Path(package_destination) / package_model.MANIFEST_NAME).read_text(encoding="utf-8"))
        package_audit = package_audit_model.audit_package_directory(package_destination)
    certificate = certificate_model.evaluate_audit(package_audit, certificate_policy)
    accepted = loaded_gate.accepted and certificate.accepted
    if accepted:
        state = "ready"
    elif loaded_gate.state == "blocked" or certificate.state == "blocked":
        state = "blocked"
    else:
        state = "held"
    provisional = RegistryHistoryReleaseEvidencePipeline(
        history_id=history.history_id,
        history_address=history.content_address,
        snapshot_count=history.snapshot_count,
        gate_address=loaded_gate.content_address,
        gate_state=loaded_gate.state,
        gate_accepted=loaded_gate.accepted,
        package_manifest_address=manifest["manifest_address"],
        package_file_count=len(package_model.FILES),
        package_audit_address=package_audit.content_address,
        package_audit_state=package_audit.state,
        package_audit_accepted=package_audit.accepted,
        certificate_address=certificate.content_address,
        certificate_state=certificate.state,
        certificate_accepted=certificate.accepted,
        accepted=accepted,
        release_ready=accepted,
        state=state,
        content_address="pending:pipeline",
    )
    return RegistryHistoryReleaseEvidencePipeline(**provisional.to_dict() | {"content_address": address_pipeline(provisional)})


def verify_pipeline(value: RegistryHistoryReleaseEvidencePipeline) -> RegistryHistoryReleaseEvidencePipeline:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipeline):
        raise ValidationError("release evidence pipeline verification requires a typed pipeline")
    value._validate()
    return value


def pipeline_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipeline:
    return RegistryHistoryReleaseEvidencePipeline.from_mapping(value)


def pipeline_json(value: RegistryHistoryReleaseEvidencePipeline) -> str:
    verify_pipeline(value)
    return canonical_json(value.to_dict())


def pipeline_schema() -> dict[str, Any]:
    fields = {"history_id": {"type": "string"}, "history_address": {"type": "string", "pattern": "^" + history_model.HISTORY_PREFIX + ":"}, "snapshot_count": {"type": "integer", "minimum": 0, "maximum": history_model.MAX_SNAPSHOTS}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "gate_state": {"type": "string", "enum": list(gate_model.STATES)}, "gate_accepted": {"type": "boolean"}, "package_manifest_address": {"type": "string", "pattern": "^" + package_model.MANIFEST_PREFIX + ":"}, "package_file_count": {"type": "integer", "const": PACKAGE_FILE_COUNT}, "package_audit_address": {"type": "string", "pattern": "^" + package_audit_model.AUDIT_PREFIX + ":"}, "package_audit_state": {"type": "string", "enum": list(package_audit_model.STATES)}, "package_audit_accepted": {"type": "boolean"}, "certificate_address": {"type": "string", "pattern": "^" + certificate_model.CERTIFICATE_PREFIX + ":"}, "certificate_state": {"type": "string", "enum": list(certificate_model.STATES)}, "certificate_accepted": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"type": "string", "enum": list(STATES)}, "content_address": {"type": "string", "pattern": "^" + PIPELINE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "states": STATES, "stages": ("history-load", "release-gate", "package", "package-audit", "release-certificate"), "limits": {"package_files": PACKAGE_FILE_COUNT}, "features": ("single-call downloaded-history orchestration", "optional durable package materialization", "independent package audit", "certificate composition", "path-free consolidated receipt", "content-address replay", "JSON export"), "schemas": ("pipeline",)}


__all__ = [
    "BOUNDARY",
    "PACKAGE_FILE_COUNT",
    "PIPELINE_PREFIX",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipeline",
    "address_pipeline",
    "build_pipeline",
    "capabilities",
    "pipeline_from_mapping",
    "pipeline_json",
    "pipeline_schema",
    "verify_pipeline",
]

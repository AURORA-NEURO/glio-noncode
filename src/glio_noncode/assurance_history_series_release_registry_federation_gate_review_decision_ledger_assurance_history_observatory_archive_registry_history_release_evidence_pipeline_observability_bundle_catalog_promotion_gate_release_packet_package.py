"""Durable, replayable packages for catalog promotion release handoffs.

The in-memory promotion release packet is intentionally small enough to move
between processes. This boundary gives it a durable transport envelope with
canonical JSON, a manifest, per-file byte receipts, atomic writes, strict
member validation, and independent reload verification. The package contains
only public gate, audit, packet, and action projections; source directories
and process metadata never cross the boundary.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as gate_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as packet_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes


VERSION = packet_model.VERSION + "-package-v1"
BOUNDARY = packet_model.BOUNDARY + "_package"
PACKAGE_PREFIX = packet_model.PACKET_PREFIX + "-package"
MANIFEST_PREFIX = PACKAGE_PREFIX + "-manifest"
ACTIONS_PREFIX = PACKAGE_PREFIX + "-actions"
DEFAULT_PACKAGE_ID = "glio-noncode-observability-bundle-catalog-promotion-release-package"
MANIFEST_NAME = "manifest.json"
GATE_NAME = "gate.json"
GATE_AUDIT_NAME = "gate-audit.json"
PACKET_NAME = "packet.json"
ACTIONS_NAME = "actions.json"
FILES = (MANIFEST_NAME, GATE_NAME, GATE_AUDIT_NAME, PACKET_NAME, ACTIONS_NAME)
ARTIFACT_FILES = tuple(sorted(FILES[1:]))
MAX_ARTIFACTS = len(ARTIFACT_FILES)
MAX_TEXT = 4096


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if ":" in value or "\\" in value or "/" in value or any(character.isspace() for character in value):
        raise ValidationError(f"{field} must be a stable path-free label")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an invalid public content address")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return gate_model._public(value)


def _artifact(name: str, payload: bytes) -> dict[str, Any]:
    return {"name": name, "bytes": len(payload), "byte_address": hash_bytes(payload, prefix=PACKAGE_PREFIX + "-artifact")}


def _actions_document(packet: packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket, content_address: str) -> dict[str, Any]:
    return {"packet_address": packet.content_address, "action_count": packet.action_count, "actions": tuple(action.to_dict() for action in packet.actions), "content_address": content_address}


def address_actions(value: Mapping[str, Any]) -> str:
    value = _mapping(value, "observability bundle catalog promotion package actions")
    return content_hash(dict(value) | {"content_address": None}, prefix=ACTIONS_PREFIX)


def _manifest(package_id: str, gate: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, gate_audit: gate_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit, packet: packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket, payload: Mapping[str, bytes]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "version": VERSION,
        "boundary": BOUNDARY,
        "package_id": package_id,
        "gate_address": gate.content_address,
        "gate_audit_address": gate_audit.content_address,
        "packet_address": packet.content_address,
        "actions_address": address_actions(json.loads(payload[ACTIONS_NAME].decode("utf-8"))),
        "artifact_count": MAX_ARTIFACTS,
        "files": ARTIFACT_FILES,
        "artifacts": tuple(_artifact(name, payload[name]) for name in ARTIFACT_FILES),
    }
    body["manifest_address"] = content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)
    return body


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage:
    """A verified five-file release handoff package."""

    FIELDS = ("package_id", "manifest_address", "actions_address", "gate_address", "gate_audit_address", "packet_address", "artifact_count", "file_count", "files", "manifest", "gate", "gate_audit", "packet", "actions", "content_address")

    def __init__(self, package_id: str, manifest: Mapping[str, Any], actions_document: Mapping[str, Any], gate: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, gate_audit: gate_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit, packet: packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket, content_address: str) -> None:
        self.package_id = _label(package_id, "observability bundle catalog promotion package ID")
        self.manifest = dict(_mapping(manifest, "observability bundle catalog promotion package manifest"))
        self.actions_document = dict(_mapping(actions_document, "observability bundle catalog promotion package actions document"))
        self.gate = gate
        self.gate_audit = gate_audit
        self.packet = packet
        self.content_address = content_address
        self._validate()

    @property
    def manifest_address(self) -> str:
        return _address(self.manifest.get("manifest_address"), "observability bundle catalog promotion package manifest address", MANIFEST_PREFIX)

    @property
    def actions_address(self) -> str:
        return _address(self.actions_document.get("content_address"), "observability bundle catalog promotion package actions address", ACTIONS_PREFIX)

    @property
    def gate_address(self) -> str:
        return self.gate.content_address

    @property
    def gate_audit_address(self) -> str:
        return self.gate_audit.content_address

    @property
    def packet_address(self) -> str:
        return self.packet.content_address

    @property
    def artifact_count(self) -> int:
        return _count(self.manifest.get("artifact_count"), "observability bundle catalog promotion package artifact count", MAX_ARTIFACTS)

    @property
    def check_count(self) -> int:
        return self.packet.check_count

    @property
    def passed_count(self) -> int:
        return self.packet.passed_count

    @property
    def failed_count(self) -> int:
        return self.packet.failed_count

    @property
    def action_count(self) -> int:
        return self.packet.action_count

    @property
    def file_count(self) -> int:
        return len(FILES)

    @property
    def files(self) -> tuple[str, ...]:
        return FILES

    @property
    def actions(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(_mapping(item, "observability bundle catalog promotion package action") for item in _sequence(self.actions_document.get("actions"), "observability bundle catalog promotion package actions", packet_model.MAX_ACTIONS))

    def _validate(self) -> None:
        if not isinstance(self.gate, gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) or not isinstance(self.gate_audit, gate_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit) or not isinstance(self.packet, packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket):
            raise ValidationError("observability bundle catalog promotion package documents must be typed")
        gate_model.verify_gate(self.gate)
        gate_audit_model.verify_audit(self.gate_audit)
        packet_model.verify_packet(self.packet)
        _strict(self.manifest, {"version", "boundary", "package_id", "gate_address", "gate_audit_address", "packet_address", "actions_address", "artifact_count", "files", "artifacts", "manifest_address"}, "observability bundle catalog promotion package manifest")
        _strict(self.actions_document, {"packet_address", "action_count", "actions", "content_address"}, "observability bundle catalog promotion package actions document")
        if self.manifest.get("version") != VERSION or self.manifest.get("boundary") != BOUNDARY or self.manifest.get("package_id") != self.package_id:
            raise ValidationError("observability bundle catalog promotion package manifest identity is invalid")
        if self.manifest.get("gate_address") != self.gate_address or self.manifest.get("gate_audit_address") != self.gate_audit_address or self.manifest.get("packet_address") != self.packet_address or self.manifest.get("actions_address") != self.actions_address:
            raise ValidationError("observability bundle catalog promotion package linkage is invalid")
        if self.gate_audit.gate_address != self.gate_address or self.packet.gate_address != self.gate_address or self.packet.gate_audit_address != self.gate_audit_address:
            raise ValidationError("observability bundle catalog promotion package nested linkage is invalid")
        if self.actions_document.get("packet_address") != self.packet_address or self.actions_document.get("action_count") != self.packet.action_count or tuple(self.actions) != tuple(action.to_dict() for action in self.packet.actions):
            raise ValidationError("observability bundle catalog promotion package action projection is invalid")
        if tuple(self.manifest.get("files", ())) != ARTIFACT_FILES or self.artifact_count != MAX_ARTIFACTS or len(tuple(self.manifest.get("artifacts", ()))) != MAX_ARTIFACTS:
            raise ValidationError("observability bundle catalog promotion package artifact inventory is invalid")
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog promotion package crosses the public boundary")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package content address")
        elif address_package(self) != self.content_address:
            raise ValidationError("observability bundle catalog promotion package content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "manifest_address": self.manifest_address, "actions_address": self.actions_address, "gate_address": self.gate_address, "gate_audit_address": self.gate_audit_address, "packet_address": self.packet_address, "artifact_count": self.artifact_count, "file_count": self.file_count, "files": self.files, "manifest": self.manifest, "gate": self.gate.to_dict(), "gate_audit": self.gate_audit.to_dict(), "packet": self.packet.to_dict(), "actions": self.actions, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "manifest_address": self.manifest_address, "actions_address": self.actions_address, "gate_address": self.gate_address, "gate_audit_address": self.gate_audit_address, "packet_address": self.packet_address, "artifact_count": self.artifact_count, "file_count": self.file_count, "files": self.files, "state": self.packet.state, "decision": self.packet.decision, "accepted": self.packet.accepted, "release_ready": self.packet.release_ready, "check_count": self.packet.check_count, "passed_count": self.packet.passed_count, "failed_count": self.packet.failed_count, "action_count": self.packet.action_count, "content_address": self.content_address}


def address_package(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage):
        raise ValidationError("observability bundle catalog promotion package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def _payload(gate: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, gate_audit: gate_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit, packet: packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket, actions_document: Mapping[str, Any]) -> dict[str, bytes]:
    return {GATE_NAME: canonical_bytes(gate.to_dict()), GATE_AUDIT_NAME: canonical_bytes(gate_audit.to_dict()), PACKET_NAME: canonical_bytes(packet.to_dict()), ACTIONS_NAME: canonical_bytes(actions_document)}


def build_package(gate: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, gate_audit: gate_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit, packet: packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket, *, package_id: str = DEFAULT_PACKAGE_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage:
    if not isinstance(gate, gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate) or not isinstance(gate_audit, gate_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateAudit) or not isinstance(packet, packet_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket):
        raise ValidationError("observability bundle catalog promotion package requires typed gate, audit, and packet")
    gate_model.verify_gate(gate)
    gate_audit_model.verify_audit(gate_audit)
    packet_model.verify_packet(packet)
    if gate_audit.gate_address != gate.content_address or packet.gate_address != gate.content_address or packet.gate_audit_address != gate_audit.content_address:
        raise ValidationError("observability bundle catalog promotion package inputs are not linked")
    package_id = _label(package_id, "observability bundle catalog promotion package ID")
    actions_provisional = _actions_document(packet, "pending:observability-bundle-catalog-promotion-package-actions")
    actions_document = _actions_document(packet, address_actions(actions_provisional))
    payload = _payload(gate, gate_audit, packet, actions_document)
    manifest = _manifest(package_id, gate, gate_audit, packet, payload)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage(package_id, manifest, actions_document, gate, gate_audit, packet, "pending:observability-bundle-catalog-promotion-package")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage(package_id, manifest, actions_document, gate, gate_audit, packet, address_package(provisional))


def package_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage:
    value = _mapping(value, "observability bundle catalog promotion package")
    _strict(value, set(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage.FIELDS), "observability bundle catalog promotion package")
    missing = [field for field in RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage.FIELDS if field not in value]
    if missing:
        raise ValidationError(f"observability bundle catalog promotion package is missing fields: {missing}")
    gate = gate_model.gate_from_mapping(_mapping(value["gate"], "observability bundle catalog promotion package gate"))
    gate_audit = gate_audit_model.audit_from_mapping(_mapping(value["gate_audit"], "observability bundle catalog promotion package gate audit"))
    packet = packet_model.packet_from_mapping(_mapping(value["packet"], "observability bundle catalog promotion package packet"))
    manifest = dict(_mapping(value["manifest"], "observability bundle catalog promotion package manifest"))
    if isinstance(manifest.get("files"), list):
        manifest["files"] = tuple(manifest["files"])
    if isinstance(manifest.get("artifacts"), list):
        manifest["artifacts"] = tuple(dict(item) for item in manifest["artifacts"])
    actions_document = _actions_document(packet, value["actions_address"])
    candidate = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage(value["package_id"], manifest, actions_document, gate, gate_audit, packet, value["content_address"])
    expected = build_package(gate, gate_audit, packet, package_id=value["package_id"])
    if candidate.to_dict() != expected.to_dict():
        raise ValidationError("observability bundle catalog promotion package mapping does not match its canonical projection")
    return expected


def package_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> str:
    return canonical_json(verify_package(value).to_dict())


def package_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> str:
    value = verify_package(value)
    fields = ("name", "bytes", "byte_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for artifact in value.manifest["artifacts"]:
        writer.writerow({field: artifact[field] for field in fields})
    return output.getvalue()


def render_package_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> str:
    value = verify_package(value)
    lines = ["# Assurance History Observatory Catalog Promotion Package", "", f"- Package: `{value.package_id}`", f"- Decision: `{value.packet.decision}`", f"- State: `{value.packet.state}`", f"- Release ready: `{value.packet.release_ready}`", f"- Checks: `{value.packet.passed_count}/{value.packet.check_count}` passed", f"- Actions: `{value.packet.action_count}`", f"- Artifacts: `{value.artifact_count}`", f"- Content address: `{value.content_address}`", "", "| name | bytes | byte address |", "| --- | ---: | --- |"]
    for artifact in value.manifest["artifacts"]:
        lines.append(f"| `{artifact['name']}` | {artifact['bytes']} | `{artifact['byte_address']}` |" )
    return "\n".join(lines) + "\n"


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists():
        if not overwrite:
            raise ValidationError("observability bundle catalog promotion package destination exists; explicit overwrite is required")
        if destination.is_symlink() or not destination.is_dir() or {item.name for item in destination.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in destination.iterdir()):
            raise ValidationError("observability bundle catalog promotion package destination is not an exact compatible directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gnd-observability-package-", dir=str(destination.parent)))
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


def package_bytes(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> Mapping[str, bytes]:
    value = verify_package(value)
    payload = _payload(value.gate, value.gate_audit, value.packet, value.actions_document)
    return {MANIFEST_NAME: canonical_bytes(value.manifest), **payload}


def package_manifest_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> str:
    return package_bytes(value)[MANIFEST_NAME].decode("utf-8")


def write_package(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), package_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    directory = Path(source)
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("observability bundle catalog promotion package input must be a regular directory")
    members = tuple(directory.iterdir())
    if {item.name for item in members} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in members):
        raise ValidationError("observability bundle catalog promotion package member set is invalid")
    return {name: (directory / name).read_bytes() for name in FILES}


def load_package(source: str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage:
    payload = _read_directory(source)
    try:
        documents = {name: json.loads(payload[name].decode("utf-8")) for name in FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("observability bundle catalog promotion package contains invalid JSON") from error
    if any(canonical_bytes(documents[name]) != payload[name] for name in FILES):
        raise ValidationError("observability bundle catalog promotion package artifacts are not canonical")
    manifest = _mapping(documents[MANIFEST_NAME], "observability bundle catalog promotion package manifest")
    gate = gate_model.gate_from_mapping(_mapping(documents[GATE_NAME], "observability bundle catalog promotion package gate"))
    gate_audit = gate_audit_model.audit_from_mapping(_mapping(documents[GATE_AUDIT_NAME], "observability bundle catalog promotion package gate audit"))
    packet = packet_model.packet_from_mapping(_mapping(documents[PACKET_NAME], "observability bundle catalog promotion package packet"))
    actions_document = _mapping(documents[ACTIONS_NAME], "observability bundle catalog promotion package actions")
    expected = build_package(gate, gate_audit, packet, package_id=manifest.get("package_id"))
    if canonical_bytes(manifest) != canonical_bytes(expected.manifest) or canonical_bytes(actions_document) != canonical_bytes(expected.actions_document) or expected.to_dict()["content_address"] != address_package(expected):
        raise ValidationError("observability bundle catalog promotion package manifest or linkage receipts are invalid")
    expected_payload = package_bytes(expected)
    if any(expected_payload[name] != payload[name] for name in FILES):
        raise ValidationError("observability bundle catalog promotion package bytes do not replay")
    return expected


def verify_package(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage | str | Path) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage:
    if isinstance(value, (str, Path)):
        return load_package(value)
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage):
        raise ValidationError("observability bundle catalog promotion package verification requires a typed package or directory")
    value._validate()
    if address_package(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion package content address does not replay")
    return value


def manifest_schema() -> dict[str, Any]:
    fields = {"version": {"const": VERSION, "type": "string"}, "boundary": {"const": BOUNDARY, "type": "string"}, "package_id": {"type": "string", "maxLength": 256}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "gate_audit_address": {"type": "string", "pattern": "^" + gate_audit_model.AUDIT_PREFIX + ":"}, "packet_address": {"type": "string", "pattern": "^" + packet_model.PACKET_PREFIX + ":"}, "actions_address": {"type": "string", "pattern": "^" + ACTIONS_PREFIX + ":"}, "artifact_count": {"const": MAX_ARTIFACTS, "type": "integer"}, "files": {"const": list(ARTIFACT_FILES), "type": "array"}, "artifacts": {"type": "array", "minItems": MAX_ARTIFACTS, "maxItems": MAX_ARTIFACTS, "items": {"type": "object", "additionalProperties": False, "required": ["name", "bytes", "byte_address"], "properties": {"name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "bytes": {"type": "integer", "minimum": 0}, "byte_address": {"type": "string"}}}}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def actions_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["packet_address", "action_count", "actions", "content_address"], "properties": {"packet_address": {"type": "string", "pattern": "^" + packet_model.PACKET_PREFIX + ":"}, "action_count": {"type": "integer", "minimum": 0, "maximum": packet_model.MAX_ACTIONS}, "actions": {"type": "array", "maxItems": packet_model.MAX_ACTIONS, "items": packet_model.action_schema()}, "content_address": {"type": "string", "pattern": "^" + ACTIONS_PREFIX + ":"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage.FIELDS), "properties": {"package_id": {"type": "string", "maxLength": 256}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}, "actions_address": {"type": "string", "pattern": "^" + ACTIONS_PREFIX + ":"}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "gate_audit_address": {"type": "string", "pattern": "^" + gate_audit_model.AUDIT_PREFIX + ":"}, "packet_address": {"type": "string", "pattern": "^" + packet_model.PACKET_PREFIX + ":"}, "artifact_count": {"const": MAX_ARTIFACTS, "type": "integer"}, "file_count": {"const": len(FILES), "type": "integer"}, "files": {"const": list(FILES), "type": "array"}, "manifest": manifest_schema(), "gate": gate_model.gate_schema(), "gate_audit": gate_audit_model.audit_schema(), "packet": packet_model.packet_schema(), "actions": {"type": "array", "maxItems": packet_model.MAX_ACTIONS, "items": packet_model.action_schema()}, "content_address": {"type": "string", "pattern": "^" + PACKAGE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_prefix": PACKAGE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "actions_prefix": ACTIONS_PREFIX, "files": FILES, "artifact_files": ARTIFACT_FILES, "limits": {"max_artifacts": MAX_ARTIFACTS, "max_actions": packet_model.MAX_ACTIONS}, "features": ("exact five-file persistence", "canonical UTF-8 JSON", "atomic writes", "manifest and action receipts", "per-artifact byte addressing", "strict member-set validation", "nested gate audit packet verification", "safe package reload", "path-free public documents", "JSON CSV and Markdown exports"), "schemas": ("manifest", "actions", "package")}


__all__ = [
    "ACTIONS_NAME", "ACTIONS_PREFIX", "ARTIFACT_FILES", "BOUNDARY", "DEFAULT_PACKAGE_ID", "FILES", "GATE_AUDIT_NAME", "GATE_NAME", "MANIFEST_NAME", "MANIFEST_PREFIX", "MAX_ARTIFACTS", "PACKAGE_PREFIX", "PACKET_NAME", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage",
    "actions_schema", "address_actions", "address_package", "build_package", "capabilities", "load_package", "manifest_schema", "package_bytes", "package_csv", "package_from_mapping", "package_json", "package_manifest_json", "package_schema", "render_package_markdown", "verify_package", "write_package",
]

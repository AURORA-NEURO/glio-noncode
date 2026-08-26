"""Portable exact-byte packets for public mission-plan catalog gates.

The gate and runtime are useful in memory, but release review also needs a
closed directory that can be transported to another machine.  This module
packages the catalog, policy decision, aggregate report, semantic audit, and
runtime into a fixed set of UTF-8 artifacts with a manifest.  Verification is
byte-oriented and reconstructs every addressed JSON projection before an
offline loader exposes it.

The packet is a research handoff only.  It never contains workflow payloads,
raw requests, routing identifiers, attribution, language, model, producer,
identity, or subject metadata, and it never executes a handler.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    MissionPlanReleaseCatalogBundle,
    MissionPlanReleaseCatalogOffline,
    load_mission_plan_release_catalog,
)
from .mission_plan_release_catalog_audit import (
    MissionPlanReleaseCatalogAudit,
    build_mission_plan_release_catalog_audit,
)
from .mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGate,
    MissionPlanReleaseCatalogGatePolicy,
    build_mission_plan_release_catalog_gate,
)
from .mission_plan_release_catalog_gate_runtime import (
    MissionPlanReleaseCatalogGateRuntime,
    run_mission_plan_release_catalog_gate_runtime,
)
from .mission_plan_release_catalog_report import (
    MissionPlanReleaseCatalogReport,
    build_mission_plan_release_catalog_report,
)
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_VERSION = "mission-plan-release-catalog-gate-packet-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_SCHEMA_VERSION = "mission-plan-release-catalog-gate-packet-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_CAPABILITIES_VERSION = "mission-plan-release-catalog-gate-packet-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MANIFEST_FILE = "manifest.json"
MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MAX_ARTIFACTS = 16
MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS = frozenset(
    {
        "catalog-gate-audit.json",
        "catalog-gate-policy.json",
        "catalog-gate-report.json",
        "catalog-gate-runtime.json",
        "catalog-gate-summary.json",
        "catalog-gate.json",
        "manifest.json",
        "mission-plan-release-catalog.json",
    }
)

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "email",
        "generated_by",
        "identity",
        "language",
        "model",
        "model_id",
        "patient",
        "producer",
        "programming_language",
        "raw_request",
        "request",
        "secret",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _private_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child_path)
            paths.extend(_private_paths(child, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_private_paths(child, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _safe_filename(value: Any, field: str) -> str:
    filename = _text(value, field, maximum=180)
    path = Path(filename)
    if path.name != filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ValidationError(f"{field} must be a plain filename")
    return filename


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGatePacketArtifact:
    """One exact-byte packet artifact."""

    artifact_id: str
    filename: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: bytes

    def __post_init__(self) -> None:
        _text(self.artifact_id, "catalog_gate_packet_artifact.artifact_id", maximum=128)
        _safe_filename(self.filename, "catalog_gate_packet_artifact.filename")
        _text(self.media_type, "catalog_gate_packet_artifact.media_type", maximum=96)
        if self.byte_count != len(self.payload) or self.byte_count < 0:
            raise ValidationError("catalog gate packet artifact byte count does not reconcile")
        if self.line_count != self.payload.count(b"\n"):
            raise ValidationError("catalog gate packet artifact line count does not reconcile")
        if hash_bytes(self.payload, prefix="mission-plan-release-catalog-gate-packet-artifact") != self.content_address:
            raise ValidationError("catalog gate packet artifact content address does not reconcile")

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload:
            body["content"] = self.payload.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGatePacket:
    """Complete in-memory portable catalog-gate packet."""

    catalog: MissionPlanReleaseCatalog
    gate: MissionPlanReleaseCatalogGate
    report: MissionPlanReleaseCatalogReport
    audit: MissionPlanReleaseCatalogAudit
    runtime: MissionPlanReleaseCatalogGateRuntime
    artifacts: tuple[MissionPlanReleaseCatalogGatePacketArtifact, ...]
    manifest: Mapping[str, Any]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.content_address, "catalog_gate_packet.content_address")
        names = tuple(item.filename for item in self.artifacts)
        if len(names) > MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MAX_ARTIFACTS:
            raise ValidationError("catalog gate packet artifact count exceeds the bound")
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValidationError("catalog gate packet artifacts must be unique and sorted")
        if set(names) != set(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS):
            raise ValidationError("catalog gate packet artifact set does not close")
        _text(self.manifest.get("manifest_address"), "catalog_gate_packet.manifest_address")

    @property
    def packet_id(self) -> str:
        return str(self.manifest.get("packet_id", self.catalog.catalog_id))

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return jsonable(
            {
                "packet_version": MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_VERSION,
                "packet_id": self.packet_id,
                "catalog": self.catalog.to_dict(),
                "gate": self.gate.to_dict(),
                "report": self.report.to_dict(),
                "audit": self.audit.to_dict(),
                "runtime": self.runtime.to_dict(),
                "artifacts": tuple(item.to_dict(include_payload=include_payloads) for item in self.artifacts),
                "manifest": dict(self.manifest),
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGatePacketVerification:
    """Independent packet filesystem verification result."""

    packet_id: str
    manifest_address_valid: bool
    catalog_address_valid: bool
    gate_address_valid: bool
    report_address_valid: bool
    audit_address_valid: bool
    runtime_address_valid: bool
    summary_address_valid: bool
    artifact_set_valid: bool
    exact_bytes: bool
    public_boundary_valid: bool
    missing_files: tuple[str, ...]
    unexpected_files: tuple[str, ...]
    tampered_files: tuple[str, ...]
    artifact_count: int
    verified_artifact_count: int
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.packet_id, "catalog_gate_packet_verification.packet_id", maximum=120)
        for field in (
            "manifest_address_valid",
            "catalog_address_valid",
            "gate_address_valid",
            "report_address_valid",
            "audit_address_valid",
            "runtime_address_valid",
            "summary_address_valid",
            "artifact_set_valid",
            "exact_bytes",
            "public_boundary_valid",
            "accepted",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValidationError(f"packet verification {field} must be boolean")
        for field in ("artifact_count", "verified_artifact_count"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"packet verification {field} must be non-negative")
        _text(self.content_address, "catalog_gate_packet_verification.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGatePacketOffline:
    """Verified offline packet projection."""

    catalog: MissionPlanReleaseCatalog
    gate: MissionPlanReleaseCatalogGate
    report: MissionPlanReleaseCatalogReport
    audit: MissionPlanReleaseCatalogAudit
    runtime: MissionPlanReleaseCatalogGateRuntime
    manifest: Mapping[str, Any]
    verification: MissionPlanReleaseCatalogGatePacketVerification
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if not self.verification.accepted or not self.accepted:
            raise ValidationError("offline catalog gate packet must be verified and accepted")
        _text(self.content_address, "catalog_gate_packet_offline.content_address")

    @property
    def packet_id(self) -> str:
        return str(self.manifest["packet_id"])

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "packet_id": self.packet_id,
                "catalog": self.catalog.to_dict(),
                "gate": self.gate.to_dict(),
                "report": self.report.to_dict(),
                "audit": self.audit.to_dict(),
                "runtime": self.runtime.to_dict(),
                "manifest": dict(self.manifest),
                "verification": self.verification.to_dict(),
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


def _artifact(artifact_id: str, filename: str, media_type: str, payload: bytes) -> MissionPlanReleaseCatalogGatePacketArtifact:
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"catalog gate packet artifact is not UTF-8: {filename}") from exc
    return MissionPlanReleaseCatalogGatePacketArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=media_type,
        byte_count=len(payload),
        line_count=payload.count(b"\n"),
        content_address=hash_bytes(payload, prefix="mission-plan-release-catalog-gate-packet-artifact"),
        payload=payload,
    )


def _as_catalog(value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path) -> MissionPlanReleaseCatalog:
    if isinstance(value, MissionPlanReleaseCatalog):
        return value
    if isinstance(value, MissionPlanReleaseCatalogBundle):
        return value.catalog
    if isinstance(value, MissionPlanReleaseCatalogOffline):
        return value.catalog
    if isinstance(value, (str, Path)):
        return load_mission_plan_release_catalog(value).catalog
    body = _mapping(value, "catalog gate packet source")
    if isinstance(body.get("catalog"), Mapping):
        body = _mapping(body["catalog"], "catalog gate packet catalog")
    return MissionPlanReleaseCatalog.from_mapping(body)


def _json_payload(value: Mapping[str, Any]) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def build_mission_plan_release_catalog_gate_packet(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
    policy: MissionPlanReleaseCatalogGatePolicy | Mapping[str, Any] | None = None,
    *,
    packet_id: str | None = None,
) -> MissionPlanReleaseCatalogGatePacket:
    """Build a closed, exact-byte packet for a catalog-gate decision."""

    catalog = _as_catalog(value)
    gate = build_mission_plan_release_catalog_gate(catalog, policy)
    report = build_mission_plan_release_catalog_report(catalog)
    audit = build_mission_plan_release_catalog_audit(catalog)
    runtime = run_mission_plan_release_catalog_gate_runtime(catalog, gate.policy)
    selected_id = _text(packet_id or f"{catalog.catalog_id}-gate-packet", "packet_id", maximum=120)
    payloads = {
        "mission-plan-release-catalog.json": _json_payload(catalog.to_dict()),
        "catalog-gate.json": _json_payload(gate.to_dict()),
        "catalog-gate-policy.json": _json_payload(gate.policy.to_dict() | {"policy_address": gate.policy.content_address}),
        "catalog-gate-report.json": _json_payload(report.to_dict()),
        "catalog-gate-audit.json": _json_payload(audit.to_dict()),
        "catalog-gate-runtime.json": _json_payload(runtime.to_dict()),
    }
    artifacts = tuple(
        _artifact(filename.replace(".", "-"), filename, "application/json", payload)
        for filename, payload in sorted(payloads.items())
    )
    summary_body: dict[str, Any] = {
        "summary_version": "mission-plan-release-catalog-gate-packet-summary-v1",
        "packet_id": selected_id,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "gate_address": gate.content_address,
        "report_address": report.content_address,
        "audit_address": audit.content_address,
        "runtime_address": runtime.content_address,
        "artifact_names": [item.filename for item in artifacts] + ["catalog-gate-summary.json", "manifest.json"],
        "artifact_count": len(artifacts) + 2,
        "accepted": gate.accepted and runtime.accepted and report.accepted and audit.accepted,
    }
    summary_body["content_address"] = content_hash(
        {key: value for key, value in summary_body.items() if key != "content_address"},
        prefix="mission-plan-release-catalog-gate-packet-summary",
    )
    summary_artifact = _artifact("catalog-gate-summary", "catalog-gate-summary.json", "application/json", _json_payload(summary_body))
    artifacts = tuple(sorted(artifacts + (summary_artifact,), key=lambda item: item.filename))
    manifest_body: dict[str, Any] = {
        "manifest_version": MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_VERSION,
        "packet_id": selected_id,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "gate_address": gate.content_address,
        "report_address": report.content_address,
        "audit_address": audit.content_address,
        "runtime_address": runtime.content_address,
        "summary_address": summary_body["content_address"],
        "artifact_count": len(artifacts) + 1,
        "artifacts": [item.to_dict() for item in artifacts],
        "accepted": summary_body["accepted"],
    }
    manifest_body["manifest_address"] = content_hash(
        manifest_body,
        prefix="mission-plan-release-catalog-gate-packet-manifest",
    )
    manifest_artifact = _artifact("catalog-gate-manifest", MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MANIFEST_FILE, "application/json", _json_payload(manifest_body))
    artifacts = tuple(sorted(artifacts + (manifest_artifact,), key=lambda item: item.filename))
    accepted = bool(manifest_body["accepted"])
    packet_body = {
        "catalog": catalog,
        "gate": gate,
        "report": report,
        "audit": audit,
        "runtime": runtime,
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "manifest": manifest_body,
        "accepted": accepted,
    }
    return MissionPlanReleaseCatalogGatePacket(
        catalog=catalog,
        gate=gate,
        report=report,
        audit=audit,
        runtime=runtime,
        artifacts=artifacts,
        manifest=manifest_body,
        accepted=accepted,
        content_address=content_hash(packet_body, prefix="mission-plan-release-catalog-gate-packet"),
    )


def write_mission_plan_release_catalog_gate_packet(
    value: MissionPlanReleaseCatalogGatePacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write the packet artifacts as exact UTF-8 bytes."""

    if not isinstance(value, MissionPlanReleaseCatalogGatePacket):
        raise ValidationError("catalog gate packet writer requires a packet")
    root = Path(destination)
    if root.exists():
        if not root.is_dir():
            raise ValidationError("catalog gate packet destination must be a directory")
        if tuple(root.iterdir()) and not allow_existing:
            raise ValidationError("catalog gate packet destination is not empty")
    else:
        root.mkdir(parents=True, exist_ok=False)
    for artifact in value.artifacts:
        (root / artifact.filename).write_bytes(artifact.payload)
    return root


def verify_mission_plan_release_catalog_gate_packet(destination: str | Path) -> MissionPlanReleaseCatalogGatePacketVerification:
    """Verify packet names, exact bytes, addresses, and public boundary."""

    root = Path(destination)
    if not root.exists() or not root.is_dir():
        raise ValidationError("catalog gate packet destination must be an existing directory")
    files = tuple(sorted(item.name for item in root.iterdir() if item.is_file()))
    missing = tuple(sorted(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS - set(files)))
    unexpected = tuple(sorted(set(files) - MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS))
    tampered: list[str] = []
    verified_count = 0
    packet_id = "unknown"
    artifact_count = 0
    manifest_address_valid = catalog_address_valid = gate_address_valid = report_address_valid = False
    audit_address_valid = runtime_address_valid = summary_address_valid = False
    public_boundary_valid = True
    exact_bytes = not missing and not unexpected
    try:
        manifest = json.loads((root / MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MANIFEST_FILE).read_text(encoding="utf-8"))
        packet_id = _text(manifest.get("packet_id"), "packet.packet_id", maximum=120)
        public_boundary_valid = not bool(_private_paths(manifest))
        manifest_address_valid = manifest.get("manifest_address") == content_hash(
            {key: value for key, value in manifest.items() if key != "manifest_address"},
            prefix="mission-plan-release-catalog-gate-packet-manifest",
        )
        metadata = {item["filename"]: item for item in manifest.get("artifacts", ())}
        artifact_count = int(manifest.get("artifact_count", 0))
        for filename in sorted(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS - {"manifest.json"}):
            path = root / filename
            if not path.exists():
                continue
            payload = path.read_bytes()
            item = metadata.get(filename)
            actual = hash_bytes(payload, prefix="mission-plan-release-catalog-gate-packet-artifact")
            if not isinstance(item, Mapping) or item.get("content_address") != actual or item.get("byte_count") != len(payload):
                tampered.append(filename)
            else:
                verified_count += 1
            if filename.endswith(".json"):
                public_boundary_valid = public_boundary_valid and not bool(_private_paths(json.loads(payload.decode("utf-8"))))
        catalog = MissionPlanReleaseCatalog.from_mapping(json.loads((root / "mission-plan-release-catalog.json").read_text(encoding="utf-8")))
        gate = MissionPlanReleaseCatalogGate.from_mapping(json.loads((root / "catalog-gate.json").read_text(encoding="utf-8")))
        report = MissionPlanReleaseCatalogReport.from_mapping(json.loads((root / "catalog-gate-report.json").read_text(encoding="utf-8")))
        runtime = MissionPlanReleaseCatalogGateRuntime.from_mapping(json.loads((root / "catalog-gate-runtime.json").read_text(encoding="utf-8")))
        catalog_address_valid = manifest.get("catalog_address") == catalog.content_address
        gate_address_valid = manifest.get("gate_address") == gate.content_address
        report_address_valid = manifest.get("report_address") == report.content_address
        runtime_address_valid = manifest.get("runtime_address") == runtime.content_address
        audit_payload = json.loads((root / "catalog-gate-audit.json").read_text(encoding="utf-8"))
        audit_address_valid = audit_payload.get("catalog_address") == catalog.content_address and audit_payload.get("accepted") is True
        summary = json.loads((root / "catalog-gate-summary.json").read_text(encoding="utf-8"))
        summary_address_valid = summary.get("content_address") == content_hash(
            {key: value for key, value in summary.items() if key != "content_address"},
            prefix="mission-plan-release-catalog-gate-packet-summary",
        ) and summary.get("content_address") == manifest.get("summary_address")
        public_boundary_valid = public_boundary_valid and not bool(_private_paths({"catalog": catalog.to_dict(), "gate": gate.to_dict(), "report": report.to_dict(), "runtime": runtime.to_dict()}))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
        exact_bytes = False
        if "manifest.json" not in tampered:
            tampered.append("manifest.json")
    tampered = sorted(set(tampered))
    accepted = bool(
        manifest_address_valid
        and catalog_address_valid
        and gate_address_valid
        and report_address_valid
        and audit_address_valid
        and runtime_address_valid
        and summary_address_valid
        and not missing
        and not unexpected
        and not tampered
        and exact_bytes
        and public_boundary_valid
        and artifact_count == len(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS)
        and verified_count == len(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS) - 1
    )
    body = {
        "packet_id": packet_id,
        "manifest_address_valid": manifest_address_valid,
        "catalog_address_valid": catalog_address_valid,
        "gate_address_valid": gate_address_valid,
        "report_address_valid": report_address_valid,
        "audit_address_valid": audit_address_valid,
        "runtime_address_valid": runtime_address_valid,
        "summary_address_valid": summary_address_valid,
        "artifact_set_valid": not missing and not unexpected,
        "exact_bytes": exact_bytes,
        "public_boundary_valid": public_boundary_valid,
        "missing_files": missing,
        "unexpected_files": unexpected,
        "tampered_files": tuple(tampered),
        "artifact_count": artifact_count,
        "verified_artifact_count": verified_count,
        "accepted": accepted,
    }
    return MissionPlanReleaseCatalogGatePacketVerification(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-packet-verification"),
    )


def load_mission_plan_release_catalog_gate_packet(destination: str | Path) -> MissionPlanReleaseCatalogGatePacketOffline:
    """Verify and hydrate a packet without its original builder."""

    verification = verify_mission_plan_release_catalog_gate_packet(destination)
    if not verification.accepted:
        raise ValidationError("catalog gate packet verification failed: " + canonical_json(verification.to_dict()))
    root = Path(destination)
    catalog = MissionPlanReleaseCatalog.from_mapping(json.loads((root / "mission-plan-release-catalog.json").read_text(encoding="utf-8")))
    gate = MissionPlanReleaseCatalogGate.from_mapping(json.loads((root / "catalog-gate.json").read_text(encoding="utf-8")))
    report = MissionPlanReleaseCatalogReport.from_mapping(json.loads((root / "catalog-gate-report.json").read_text(encoding="utf-8")))
    runtime = MissionPlanReleaseCatalogGateRuntime.from_mapping(json.loads((root / "catalog-gate-runtime.json").read_text(encoding="utf-8")))
    audit = MissionPlanReleaseCatalogAudit.from_mapping(json.loads((root / "catalog-gate-audit.json").read_text(encoding="utf-8")))
    manifest = json.loads((root / MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MANIFEST_FILE).read_text(encoding="utf-8"))
    body = {"catalog": catalog, "gate": gate, "report": report, "audit": audit, "runtime": runtime, "manifest": manifest, "verification": verification, "accepted": True}
    return MissionPlanReleaseCatalogGatePacketOffline(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-packet-offline"),
    )


def mission_plan_release_catalog_gate_packet_schema() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_SCHEMA_VERSION,
        "packet_version": MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_VERSION,
        "required_files": sorted(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS),
        "max_artifacts": MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MAX_ARTIFACTS,
        "exact_utf8_bytes": True,
        "offline_hydration": True,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "identity_metadata": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
        },
    }


def mission_plan_release_catalog_gate_packet_capabilities() -> dict[str, Any]:
    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_CAPABILITIES_VERSION,
        "exact_byte_materialization": True,
        "manifest_address_reconstruction": True,
        "artifact_address_reconstruction": True,
        "offline_hydration": True,
        "tamper_detection": True,
        "missing_file_detection": True,
        "unexpected_file_detection": True,
        "public_boundary_audit": True,
        "read_only_verification": True,
        "timestamp_free": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "json_export": True,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "attribution": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
            "identity_metadata": False,
        },
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MANIFEST_FILE",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_MAX_ARTIFACTS",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_VERSION",
    "MissionPlanReleaseCatalogGatePacket",
    "MissionPlanReleaseCatalogGatePacketArtifact",
    "MissionPlanReleaseCatalogGatePacketOffline",
    "MissionPlanReleaseCatalogGatePacketVerification",
    "build_mission_plan_release_catalog_gate_packet",
    "load_mission_plan_release_catalog_gate_packet",
    "mission_plan_release_catalog_gate_packet_capabilities",
    "mission_plan_release_catalog_gate_packet_schema",
    "verify_mission_plan_release_catalog_gate_packet",
    "write_mission_plan_release_catalog_gate_packet",
]

"""Portable exact-byte handoffs for registry-store promotion decisions.

The store packet preserves operational state; the gate packet preserves the
decision over that state.  The packet is intentionally fixed and small: one
addressed gate projection, its check ledger, policy, summary, schema, and
capabilities, followed by an addressed manifest.  Every write is atomic and
every load is gated by exact-byte verification.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_registry_store_gate import (
    release_assurance_attestation_registry_store_gate_capabilities,
    release_assurance_attestation_registry_store_gate_schema,
)
from .release_assurance_attestation_registry_store_gate_contracts import (
    ReleaseAssuranceAttestationRegistryStoreGate,
)
from .release_assurance_attestation_registry_store_gate_packet_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_BOUNDARY,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_VERSION,
    ReleaseAssuranceAttestationRegistryStoreGatePacket,
    ReleaseAssuranceAttestationRegistryStoreGatePacketArtifact,
    ReleaseAssuranceAttestationRegistryStoreGatePacketManifest,
    ReleaseAssuranceAttestationRegistryStoreGatePacketOffline,
    ReleaseAssuranceAttestationRegistryStoreGatePacketVerification,
)
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
)
from .serialization import canonical_json, content_hash


def _as_gate(
    gate: ReleaseAssuranceAttestationRegistryStoreGate | Mapping[str, Any],
) -> ReleaseAssuranceAttestationRegistryStoreGate:
    if isinstance(gate, ReleaseAssuranceAttestationRegistryStoreGate):
        return gate
    return ReleaseAssuranceAttestationRegistryStoreGate.from_mapping(gate)


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    role: str,
    source_address: str,
    content: bytes,
) -> ReleaseAssuranceAttestationRegistryStoreGatePacketArtifact:
    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("gate packet artifact identity is required")
    if not isinstance(content, bytes):
        raise ValidationError("gate packet artifact content must be bytes")
    return ReleaseAssuranceAttestationRegistryStoreGatePacketArtifact(
        artifact_id=artifact_id,
        relative_path=path,
        media_type=media_type,
        role=role,
        source_address=source_address,
        byte_count=len(content),
        line_count=line_count(content),
        content_address=artifact_address(content),
        content=content,
    )


def _csv_bytes(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> bytes:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(tuple(headers))
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _summary(gate: ReleaseAssuranceAttestationRegistryStoreGate) -> dict[str, Any]:
    return {
        "gate_id": gate.gate_id,
        "gate_address": gate.content_address,
        "store_id": gate.store_id,
        "registry_id": gate.registry_id,
        "baseline_store_address": gate.baseline_store_address,
        "candidate_store_address": gate.candidate_store_address,
        "state": gate.state,
        "decision": gate.decision,
        "check_count": gate.check_count,
        "passed_check_count": gate.passed_check_count,
        "failed_check_ids": gate.failed_check_ids,
        "critical_failure_count": gate.critical_failure_count,
        "packet_verified": gate.packet_verified,
        "accepted": gate.accepted,
    }


def _payloads(
    gate: ReleaseAssuranceAttestationRegistryStoreGate,
) -> tuple[tuple[str, str, str, str, bytes], ...]:
    checks = _csv_bytes(
        (
            "check_id",
            "category",
            "severity",
            "passed",
            "observed",
            "expected",
            "detail",
            "content_address",
        ),
        (
            (
                item.check_id,
                item.category,
                item.severity.value,
                str(item.passed).lower(),
                canonical_json(item.observed),
                canonical_json(item.expected),
                item.detail,
                item.content_address,
            )
            for item in gate.checks
        ),
    )
    return (
        (
            "gate-json",
            "gate/gate.json",
            "application/json",
            "gate",
            canonical_payload(gate.to_dict()),
        ),
        (
            "checks-csv",
            "gate/checks.csv",
            "text/csv",
            "checks",
            checks,
        ),
        (
            "policy-json",
            "gate/policy.json",
            "application/json",
            "policy",
            canonical_payload(gate.policy.to_dict()),
        ),
        (
            "summary-json",
            "gate/summary.json",
            "application/json",
            "summary",
            canonical_payload(_summary(gate)),
        ),
        (
            "schema-json",
            "gate/schema.json",
            "application/json",
            "schema",
            canonical_payload(release_assurance_attestation_registry_store_gate_schema()),
        ),
        (
            "capabilities-json",
            "gate/capabilities.json",
            "application/json",
            "capabilities",
            canonical_payload(release_assurance_attestation_registry_store_gate_capabilities()),
        ),
    )


def release_assurance_attestation_registry_store_gate_packet_artifact_payloads(
    gate: ReleaseAssuranceAttestationRegistryStoreGate | Mapping[str, Any],
) -> dict[str, bytes]:
    """Return exact payload bytes keyed by the fixed artifact IDs."""

    selected = _as_gate(gate)
    return {
        artifact_id: content
        for artifact_id, _path, _media_type, _role, content in _payloads(selected)
    }


def build_release_assurance_attestation_registry_store_gate_packet(
    gate: ReleaseAssuranceAttestationRegistryStoreGate | Mapping[str, Any],
    *,
    packet_id: str = "glio-noncode-release-assurance-attestation-registry-store-gate-packet",
) -> ReleaseAssuranceAttestationRegistryStoreGatePacket:
    """Build the fixed six-payload plus manifest gate packet."""

    selected = _as_gate(gate)
    if not packet_id.strip():
        raise ValidationError("gate packet ID must not be empty")
    values = _payloads(selected)
    if len(values) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT:
        raise ValidationError("gate packet payload denominator is not closed")
    artifacts = tuple(
        _artifact(artifact_id, path, media_type, role, selected.content_address, content)
        for artifact_id, path, media_type, role, content in values
    )
    if (
        tuple(item.artifact_id for item in artifacts)
        != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS
    ):
        raise ValidationError("gate packet payload IDs are not closed")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    source_addresses = (
        ("gate", selected.content_address),
        ("store", selected.candidate_store_address),
    )
    accepted = selected.accepted and all(item.required for item in artifacts)
    manifest_body = {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "gate_id": selected.gate_id,
        "store_id": selected.store_id,
        "registry_id": selected.registry_id,
        "gate_address": selected.content_address,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "source_addresses": source_addresses,
        "accepted": accepted,
    }
    manifest = ReleaseAssuranceAttestationRegistryStoreGatePacketManifest(
        **manifest_body,
        content_address=content_hash(
            manifest_body,
            prefix="release-assurance-attestation-registry-store-gate-manifest",
        ),
    )
    body = {
        "packet_id": packet_id,
        "gate_id": selected.gate_id,
        "store_id": selected.store_id,
        "registry_id": selected.registry_id,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryStoreGatePacket(
        packet_id=packet_id,
        gate_id=selected.gate_id,
        store_id=selected.store_id,
        registry_id=selected.registry_id,
        artifacts=artifacts,
        manifest=manifest,
        accepted=accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-packet",
        ),
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def write_release_assurance_attestation_registry_store_gate_packet(
    packet: ReleaseAssuranceAttestationRegistryStoreGatePacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write all gate packet payloads with atomic sibling replacement."""

    if not isinstance(packet, ReleaseAssuranceAttestationRegistryStoreGatePacket):
        raise ValidationError("gate packet writer requires a typed packet")
    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("gate packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("gate packet destination is not empty")
    for artifact in packet.artifacts:
        _atomic_write(root / safe_relative_path(artifact.relative_path), artifact.content)
    _atomic_write(
        root / "manifest.json",
        (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8"),
    )
    return root


def _read_manifest(
    directory: str | Path,
) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
    root = Path(directory)
    path = root / "manifest.json"
    if not path.is_file() or path.is_symlink():
        return root, {}, ("manifest.json",)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return root, {}, ("manifest.json",)
    if not isinstance(value, dict):
        return root, {}, ("manifest.json",)
    body = {
        key: value.get(key)
        for key in (
            "version",
            "schema_version",
            "packet_id",
            "gate_id",
            "store_id",
            "registry_id",
            "gate_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "source_addresses",
            "accepted",
        )
    }
    drift: list[str] = []
    if value.get("content_address") != content_hash(
        body,
        prefix="release-assurance-attestation-registry-store-gate-manifest",
    ):
        drift.append("manifest.content_address")
    if value.get("version") != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_VERSION:
        drift.append("manifest.version")
    if (
        value.get("schema_version")
        != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION
    ):
        drift.append("manifest.schema_version")
    try:
        ReleaseAssuranceAttestationRegistryStoreGatePacketManifest.from_mapping(value)
    except ValidationError:
        drift.append("manifest.contract")
    return root, value, tuple(drift)


def _empty_verification(
    root: Path,
) -> ReleaseAssuranceAttestationRegistryStoreGatePacketVerification:
    body = {
        "directory": str(root),
        "packet_id": "",
        "gate_id": "",
        "store_id": "",
        "registry_id": "",
        "checked_artifact_count": 0,
        "missing_paths": ("manifest.json",),
        "unexpected_paths": (),
        "unsafe_paths": (),
        "tampered_paths": (),
        "duplicate_paths": (),
        "manifest_drift": (),
        "boundary_violations": (),
        "accepted": False,
    }
    return ReleaseAssuranceAttestationRegistryStoreGatePacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-verification",
        ),
    )


def _listed(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = manifest.get("artifacts", ())
    if not isinstance(rows, list):
        return ()
    return tuple(item for item in rows if isinstance(item, dict))


def _symlinked(root: Path, relative_path: str) -> bool:
    if root.is_symlink():
        return True
    current = root
    for part in Path(relative_path).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _text_boundary(payload: bytes) -> tuple[str, ...]:
    try:
        text = payload.decode("utf-8").casefold()
    except UnicodeDecodeError:
        return ("$invalid-utf8",)
    return tuple(
        f"$text:{token}"
        for token in (
            "agent",
            "assistant",
            "author",
            "email",
            "language",
            "model",
            "patient",
            "producer",
            "subject",
        )
        if token in text
    )


def _manifest_count(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc


def verify_release_assurance_attestation_registry_store_gate_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationRegistryStoreGatePacketVerification:
    """Verify exact bytes, fixed paths, gate identity, and public boundaries."""

    root, manifest, manifest_drift = _read_manifest(directory)
    if not manifest:
        return _empty_verification(root)
    missing: list[str] = []
    unexpected: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    duplicate_paths: list[str] = []
    boundary: list[str] = []
    expected_paths: list[str] = []
    artifact_ids: list[str] = []
    listed = _listed(manifest)
    try:
        payload_count = _manifest_count(
            manifest.get("payload_artifact_count"),
            "manifest.payload_artifact_count",
        )
        artifact_count = _manifest_count(
            manifest.get("artifact_count"),
            "manifest.artifact_count",
        )
    except ValidationError:
        payload_count = -1
        artifact_count = -1
        manifest_drift = (*manifest_drift, "manifest.counts")
    if len(listed) != payload_count:
        manifest_drift = (*manifest_drift, "manifest.payload_artifact_count")
    if artifact_count != len(listed) + 1:
        manifest_drift = (*manifest_drift, "manifest.artifact_count")
    if len(listed) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT:
        manifest_drift = (*manifest_drift, "manifest.payload_denominator")
    if len(listed) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_MAX_ARTIFACTS:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
    gate_payload: Mapping[str, Any] | None = None
    for item in listed:
        artifact_id = str(item.get("artifact_id", ""))
        path_text = str(item.get("relative_path", ""))
        if artifact_id in artifact_ids:
            manifest_drift = (*manifest_drift, f"manifest.duplicate_artifact_id:{artifact_id}")
        artifact_ids.append(artifact_id)
        try:
            path = safe_relative_path(path_text)
        except ValidationError:
            unsafe.append(path_text)
            continue
        if path in expected_paths:
            duplicate_paths.append(path)
            manifest_drift = (*manifest_drift, f"manifest.duplicate_path:{path}")
        expected_paths.append(path)
        target = root / path
        if _symlinked(root, path):
            unsafe.append(path)
            continue
        if not target.is_file():
            missing.append(path)
            continue
        try:
            payload = target.read_bytes()
        except OSError:
            tampered.append(path)
            continue
        try:
            expected_bytes = int(item.get("byte_count", -1))
            expected_lines = int(item.get("line_count", -1))
        except (TypeError, ValueError, OverflowError):
            expected_bytes = -1
            expected_lines = -1
            manifest_drift = (*manifest_drift, f"manifest.counts:{path}")
        if (
            len(payload) != expected_bytes
            or line_count(payload) != expected_lines
            or artifact_address(payload) != item.get("content_address")
        ):
            tampered.append(path)
        if item.get("media_type") == "application/json":
            try:
                decoded = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{path}:{value}" for value in forbidden_keys(decoded))
                if artifact_id == "gate-json" and isinstance(decoded, Mapping):
                    gate_payload = decoded
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        else:
            boundary.extend(f"{path}:{value}" for value in _text_boundary(payload))
    if tuple(artifact_ids) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS:
        manifest_drift = (*manifest_drift, "manifest.payload_ids")
    gate_ok = False
    if gate_payload is not None:
        try:
            gate = ReleaseAssuranceAttestationRegistryStoreGate.from_mapping(gate_payload)
            gate_ok = (
                gate.gate_id == str(manifest.get("gate_id", ""))
                and gate.store_id == str(manifest.get("store_id", ""))
                and gate.registry_id == str(manifest.get("registry_id", ""))
                and gate.content_address == str(manifest.get("gate_address", ""))
                and gate.accepted == bool(manifest.get("accepted", False))
            )
            if not gate_ok:
                manifest_drift = (*manifest_drift, "manifest.gate_identity")
        except ValidationError:
            tampered.append("gate/gate.json")
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    unexpected.extend(
        path for path in actual_paths if path not in sorted((*expected_paths, "manifest.json"))
    )
    accepted = (
        bool(manifest.get("accepted"))
        and str(manifest.get("packet_id", ""))
        and str(manifest.get("gate_id", ""))
        and str(manifest.get("store_id", ""))
        and str(manifest.get("registry_id", ""))
        and len(listed) == RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT
        and tuple(artifact_ids)
        == RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS
        and gate_ok
        and not any(
            (
                missing,
                unexpected,
                unsafe,
                tampered,
                duplicate_paths,
                boundary,
                manifest_drift,
            )
        )
    )
    body = {
        "directory": str(root),
        "packet_id": str(manifest.get("packet_id", "")),
        "gate_id": str(manifest.get("gate_id", "")),
        "store_id": str(manifest.get("store_id", "")),
        "registry_id": str(manifest.get("registry_id", "")),
        "checked_artifact_count": len(listed),
        "missing_paths": tuple(sorted(set(missing))),
        "unexpected_paths": tuple(sorted(set(unexpected))),
        "unsafe_paths": tuple(sorted(set(unsafe))),
        "tampered_paths": tuple(sorted(set(tampered))),
        "duplicate_paths": tuple(sorted(set(duplicate_paths))),
        "manifest_drift": tuple(sorted(set(manifest_drift))),
        "boundary_violations": tuple(sorted(set(boundary))),
        "accepted": bool(accepted),
    }
    return ReleaseAssuranceAttestationRegistryStoreGatePacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-verification",
        ),
    )


def load_release_assurance_attestation_registry_store_gate_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationRegistryStoreGatePacketOffline:
    """Hydrate the gate only after verification succeeds."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_release_assurance_attestation_registry_store_gate_packet(root)
    if not verification.accepted:
        raise ValidationError("gate packet is not accepted")
    path = root / "gate" / "gate.json"
    try:
        gate_payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("gate packet gate payload is not valid JSON") from exc
    gate = ReleaseAssuranceAttestationRegistryStoreGate.from_mapping(gate_payload)
    if gate.gate_id != manifest.get("gate_id"):
        raise ValidationError("gate packet gate ID does not reconcile")
    if gate.store_id != manifest.get("store_id") or gate.registry_id != manifest.get("registry_id"):
        raise ValidationError("gate packet source identity does not reconcile")
    if gate.content_address != manifest.get("gate_address"):
        raise ValidationError("gate packet gate address does not reconcile")
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "gate": gate.to_dict(),
        "manifest": manifest,
        "verification": verification.to_dict(),
    }
    return ReleaseAssuranceAttestationRegistryStoreGatePacketOffline(
        packet_id=str(manifest.get("packet_id", "")),
        gate=gate,
        manifest=manifest,
        verification=verification,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-offline",
        ),
    )


def release_assurance_attestation_registry_store_gate_packet_capabilities() -> dict[str, Any]:
    """Describe the portable gate-packet feature set."""

    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION,
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_BOUNDARY,
        "gate_boundary": "public_longitudinal_release_registry_store_gate",
        "fixed_payload_count": True,
        "manifest_address": True,
        "atomic_write": True,
        "exact_byte_verification": True,
        "safe_path_verification": True,
        "symlink_rejection": True,
        "duplicate_path_detection": True,
        "unexpected_file_detection": True,
        "tamper_detection": True,
        "gate_identity_verification": True,
        "boundary_scan": True,
        "offline_hydration": True,
        "source_payloads": False,
        "timestamp_free": True,
        "payload_ids": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS,
        "payload_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT,
    }


def release_assurance_attestation_registry_store_gate_packet_schema() -> dict[str, Any]:
    """Return the public contract for gate-packet metadata and verification."""

    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_SCHEMA_VERSION,
        "type": "object",
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_BOUNDARY,
        "required": (
            "packet_id",
            "gate_id",
            "store_id",
            "registry_id",
            "artifacts",
            "manifest",
            "accepted",
            "content_address",
        ),
        "payload_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT,
        "payload_ids": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS,
        "artifact_roles": (
            "gate",
            "checks",
            "policy",
            "summary",
            "schema",
            "capabilities",
        ),
        "manifest": {
            "type": "object",
            "required": (
                "version",
                "schema_version",
                "packet_id",
                "gate_id",
                "store_id",
                "registry_id",
                "gate_address",
                "artifact_count",
                "payload_artifact_count",
                "artifacts",
                "source_addresses",
                "accepted",
                "content_address",
            ),
        },
        "verification": {
            "exact_bytes": True,
            "content_addresses": True,
            "gate_identity": True,
            "safe_paths": True,
            "public_boundary": True,
        },
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("build_release_assurance_attestation_registry_store_gate_packet")
    or name.startswith("write_release_assurance_attestation_registry_store_gate_packet")
    or name.startswith("verify_release_assurance_attestation_registry_store_gate_packet")
    or name.startswith("load_release_assurance_attestation_registry_store_gate_packet")
    or name.startswith("release_assurance_attestation_registry_store_gate_packet_")
    or name.startswith("ReleaseAssuranceAttestationRegistryStoreGatePacket")
]

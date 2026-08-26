"""Exact-byte offline packet support for attestation registries.

The registry itself is useful in memory, but release review also needs a
portable artifact that can be copied to an isolated environment.  This
module materializes a fixed packet, writes it atomically, verifies every path
and byte address, and hydrates the registry only after verification succeeds.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_registry import (
    release_assurance_attestation_registry_capabilities,
    release_assurance_attestation_registry_json,
    release_assurance_attestation_registry_schema,
)
from .release_assurance_attestation_registry_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
    ReleaseAssuranceAttestationRegistry,
    ReleaseAssuranceAttestationRegistryOffline,
    ReleaseAssuranceAttestationRegistryPacket,
    ReleaseAssuranceAttestationRegistryPacketArtifact,
    ReleaseAssuranceAttestationRegistryPacketManifest,
    ReleaseAssuranceAttestationRegistryPacketVerification,
)
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
)
from .serialization import canonical_json, content_hash


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    role: str,
    source_address: str,
    content: bytes,
) -> ReleaseAssuranceAttestationRegistryPacketArtifact:
    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("registry packet artifact identity is required")
    if not isinstance(content, bytes):
        raise ValidationError("registry packet artifact content must be bytes")
    return ReleaseAssuranceAttestationRegistryPacketArtifact(
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


def _payloads(
    registry: ReleaseAssuranceAttestationRegistry,
) -> tuple[tuple[str, str, str, str, bytes], ...]:
    entries_csv = _csv_bytes(
        (
            "ordinal",
            "entry_id",
            "attestation_id",
            "bundle_id",
            "run_id",
            "attestation_address",
            "previous_entry_address",
            "transition",
            "accepted",
            "component_count",
            "check_count",
            "passed_check_count",
            "overall_percent",
            "content_address",
        ),
        (
            (
                item.ordinal,
                item.entry_id,
                item.attestation_id,
                item.bundle_id,
                item.run_id,
                item.attestation_address,
                item.previous_entry_address,
                item.transition.value,
                str(item.accepted).lower(),
                item.component_count,
                item.check_count,
                item.passed_check_count,
                item.overall_percent,
                item.content_address,
            )
            for item in registry.entries
        ),
    )
    transitions_csv = _csv_bytes(
        (
            "ordinal",
            "transition_id",
            "from_entry_address",
            "to_entry_address",
            "from_attestation_address",
            "to_attestation_address",
            "state",
            "changed_summary_fields",
            "accepted",
            "content_address",
        ),
        (
            (
                item.ordinal,
                item.transition_id,
                item.from_entry_address,
                item.to_entry_address,
                item.from_attestation_address,
                item.to_attestation_address,
                item.state.value,
                "|".join(item.changed_summary_fields),
                str(item.accepted).lower(),
                item.content_address,
            )
            for item in registry.transitions
        ),
    )
    summary = {
        "registry_id": registry.registry_id,
        "registry_address": registry.content_address,
        "head_address": registry.head_address,
        "entry_count": registry.entry_count,
        "transition_count": registry.transition_count,
        "accepted_entry_count": registry.accepted_entry_count,
        "blocked_entry_count": registry.blocked_entry_count,
        "accepted": registry.accepted,
    }
    capabilities = release_assurance_attestation_registry_capabilities()
    return (
        (
            "registry-json",
            "registry/registry.json",
            "application/json",
            "registry",
            release_assurance_attestation_registry_json(registry).encode("utf-8"),
        ),
        (
            "entries-csv",
            "registry/entries.csv",
            "text/csv",
            "entries",
            entries_csv,
        ),
        (
            "transitions-csv",
            "registry/transitions.csv",
            "text/csv",
            "transitions",
            transitions_csv,
        ),
        (
            "summary-json",
            "registry/summary.json",
            "application/json",
            "summary",
            canonical_payload(summary),
        ),
        (
            "schema-json",
            "registry/schema.json",
            "application/json",
            "schema",
            canonical_payload(release_assurance_attestation_registry_schema()),
        ),
        (
            "capabilities-json",
            "registry/capabilities.json",
            "application/json",
            "capabilities",
            canonical_payload(capabilities),
        ),
    )


def release_assurance_attestation_registry_packet_artifact_payloads(
    registry: ReleaseAssuranceAttestationRegistry,
) -> dict[str, bytes]:
    """Return exact payload bytes keyed by stable artifact identifier."""

    return {
        artifact_id: content for artifact_id, _path, _media, _role, content in _payloads(registry)
    }


def _manifest_body(
    manifest: ReleaseAssuranceAttestationRegistryPacketManifest,
) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "schema_version": manifest.schema_version,
        "packet_id": manifest.packet_id,
        "registry_id": manifest.registry_id,
        "artifact_count": manifest.artifact_count,
        "payload_artifact_count": manifest.payload_artifact_count,
        "artifacts": manifest.artifacts,
        "source_addresses": manifest.source_addresses,
        "accepted": manifest.accepted,
    }


def build_release_assurance_attestation_registry_packet(
    registry: ReleaseAssuranceAttestationRegistry,
    *,
    packet_id: str = "glio-noncode-release-assurance-attestation-registry-packet",
) -> ReleaseAssuranceAttestationRegistryPacket:
    """Build a fixed six-payload plus manifest registry packet."""

    if not isinstance(registry, ReleaseAssuranceAttestationRegistry):
        raise ValidationError("registry packet requires a typed registry")
    if registry.entry_count > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES:
        raise ValidationError("registry packet entry denominator is not closed")
    if not packet_id.strip():
        raise ValidationError("registry packet ID must not be empty")
    values = _payloads(registry)
    artifacts = tuple(
        _artifact(artifact_id, path, media, role, registry.content_address, content)
        for artifact_id, path, media, role, content in values
    )
    if len(artifacts) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT:
        raise ValidationError("registry packet payload denominator is not closed")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    source_addresses = (
        ("registry", registry.content_address),
        ("head", registry.head_address),
    )
    accepted = registry.accepted and all(item.required for item in artifacts)
    manifest_body = {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
        "packet_id": packet_id,
        "registry_id": registry.registry_id,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "source_addresses": source_addresses,
        "accepted": accepted,
    }
    manifest = ReleaseAssuranceAttestationRegistryPacketManifest(
        **manifest_body,
        content_address=content_hash(
            manifest_body,
            prefix="release-assurance-attestation-registry-manifest",
        ),
    )
    body = {
        "packet_id": packet_id,
        "registry_id": registry.registry_id,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryPacket(
        packet_id=packet_id,
        registry_id=registry.registry_id,
        artifacts=artifacts,
        manifest=manifest,
        accepted=accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-packet",
        ),
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
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


def write_release_assurance_attestation_registry_packet(
    packet: ReleaseAssuranceAttestationRegistryPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write packet bytes atomically, requiring explicit overwrite consent."""

    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("registry packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("registry packet destination is not empty")
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
            "registry_id",
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
        prefix="release-assurance-attestation-registry-manifest",
    ):
        drift.append("manifest.content_address")
    if value.get("version") != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    return root, value, tuple(drift)


def _empty_verification(
    root: Path,
) -> ReleaseAssuranceAttestationRegistryPacketVerification:
    body = {
        "directory": str(root),
        "packet_id": "",
        "registry_id": "",
        "checked_artifact_count": 0,
        "missing_paths": ("manifest.json",),
        "unexpected_paths": (),
        "unsafe_paths": (),
        "tampered_paths": (),
        "manifest_drift": (),
        "boundary_violations": (),
        "accepted": False,
    }
    return ReleaseAssuranceAttestationRegistryPacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-verification",
        ),
    )


def _listed(manifest: dict[str, Any]) -> tuple[dict[str, Any], ...]:
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


def verify_release_assurance_attestation_registry_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationRegistryPacketVerification:
    """Verify manifest closure, exact bytes, safe paths, and public content."""

    root, manifest, manifest_drift = _read_manifest(directory)
    if not manifest:
        return _empty_verification(root)
    missing: list[str] = []
    unexpected: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    expected_paths: list[str] = []
    artifact_ids: list[str] = []
    listed = _listed(manifest)
    try:
        payload_count = int(manifest.get("payload_artifact_count", -1))
        artifact_count = int(manifest.get("artifact_count", -1))
    except (TypeError, ValueError, OverflowError):
        payload_count = -1
        artifact_count = -1
        manifest_drift = (*manifest_drift, "manifest.counts")
    if len(listed) != payload_count:
        manifest_drift = (*manifest_drift, "manifest.payload_artifact_count")
    if artifact_count != len(listed) + 1:
        manifest_drift = (*manifest_drift, "manifest.artifact_count")
    if len(listed) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT:
        manifest_drift = (*manifest_drift, "manifest.payload_denominator")
    if len(listed) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
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
        if (
            len(payload) != int(item.get("byte_count", -1))
            or line_count(payload) != int(item.get("line_count", -1))
            or artifact_address(payload) != item.get("content_address")
        ):
            tampered.append(path)
        if item.get("media_type") == "application/json":
            try:
                decoded = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{path}:{value}" for value in forbidden_keys(decoded))
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        else:
            boundary.extend(f"{path}:{value}" for value in _text_boundary(payload))
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
        and len(listed) == RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT
        and not any((missing, unexpected, unsafe, tampered, boundary, manifest_drift))
    )
    body = {
        "directory": str(root),
        "packet_id": str(manifest.get("packet_id", "")),
        "registry_id": str(manifest.get("registry_id", "")),
        "checked_artifact_count": len(listed),
        "missing_paths": tuple(sorted(set(missing))),
        "unexpected_paths": tuple(sorted(set(unexpected))),
        "unsafe_paths": tuple(sorted(set(unsafe))),
        "tampered_paths": tuple(sorted(set(tampered))),
        "manifest_drift": tuple(sorted(set(manifest_drift))),
        "boundary_violations": tuple(sorted(set(boundary))),
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryPacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-verification",
        ),
    )


def load_release_assurance_attestation_registry_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationRegistryOffline:
    """Hydrate a registry only after the exact-byte packet is accepted."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_release_assurance_attestation_registry_packet(root)
    if not verification.accepted:
        raise ValidationError("registry packet is not accepted")
    path = root / "registry" / "registry.json"
    try:
        registry = ReleaseAssuranceAttestationRegistry.from_mapping(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("registry packet registry payload is invalid") from exc
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "registry": registry,
        "manifest": manifest,
        "verification": verification,
    }
    return ReleaseAssuranceAttestationRegistryOffline(
        packet_id=body["packet_id"],
        registry=registry,
        manifest=manifest,
        verification=verification,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-offline",
        ),
    )


def release_assurance_attestation_registry_packet_schema() -> dict[str, Any]:
    """Describe the fixed registry packet layout."""

    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
        "payload_artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT,
        "artifact_count_including_manifest": (
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_ARTIFACT_COUNT
        ),
        "required_paths": [
            "registry/registry.json",
            "registry/entries.csv",
            "registry/transitions.csv",
            "registry/summary.json",
            "registry/schema.json",
            "registry/capabilities.json",
            "manifest.json",
        ],
        "exact_bytes": True,
        "atomic_write": True,
        "offline_hydration": True,
        "public_boundary": True,
    }


def release_assurance_attestation_registry_packet_capabilities() -> dict[str, Any]:
    """Describe portable registry packet guarantees."""

    return {
        "version": "release-assurance-attestation-registry-packet-capabilities-v1",
        "fixed_payload_count": True,
        "manifest_address": True,
        "exact_byte_verification": True,
        "symlink_rejection": True,
        "unexpected_file_detection": True,
        "tamper_detection": True,
        "boundary_scan": True,
        "offline_hydration": True,
        "source_payloads": False,
        "timestamp_free": True,
    }


__all__ = [
    "build_release_assurance_attestation_registry_packet",
    "load_release_assurance_attestation_registry_packet",
    "release_assurance_attestation_registry_packet_artifact_payloads",
    "release_assurance_attestation_registry_packet_capabilities",
    "release_assurance_attestation_registry_packet_schema",
    "verify_release_assurance_attestation_registry_packet",
    "write_release_assurance_attestation_registry_packet",
]

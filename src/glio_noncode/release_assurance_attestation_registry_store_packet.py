"""Portable exact-byte handoffs for the attestation registry store.

This packet layer makes the operational store durable without coupling it to a
database or a deployment platform.  A packet is a fixed set of UTF-8 files
plus a manifest.  The writer uses atomic sibling replacement; the verifier
checks every byte, path, count, address, manifest field, and public-boundary
rule; and hydration is refused until all checks pass.
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
from .release_assurance_attestation_registry_store import (
    audit_release_assurance_attestation_registry_store,
    release_assurance_attestation_registry_store_capabilities,
    release_assurance_attestation_registry_store_json,
    release_assurance_attestation_registry_store_operations_csv,
    release_assurance_attestation_registry_store_schema,
    verify_release_assurance_attestation_registry_store,
)
from .release_assurance_attestation_registry_store_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY,
    ReleaseAssuranceAttestationRegistryStore,
)
from .release_assurance_attestation_registry_store_packet_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_BOUNDARY,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_MAX_ARTIFACTS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_SCHEMA_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_VERSION,
    ReleaseAssuranceAttestationRegistryStorePacket,
    ReleaseAssuranceAttestationRegistryStorePacketArtifact,
    ReleaseAssuranceAttestationRegistryStorePacketManifest,
    ReleaseAssuranceAttestationRegistryStorePacketOffline,
    ReleaseAssuranceAttestationRegistryStorePacketVerification,
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
) -> ReleaseAssuranceAttestationRegistryStorePacketArtifact:
    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("store packet artifact identity is required")
    if not isinstance(content, bytes):
        raise ValidationError("store packet artifact content must be bytes")
    return ReleaseAssuranceAttestationRegistryStorePacketArtifact(
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


def _summary(store: ReleaseAssuranceAttestationRegistryStore) -> dict[str, Any]:
    return {
        "store_id": store.store_id,
        "store_address": store.content_address,
        "registry_id": store.registry.registry_id,
        "registry_address": store.registry.content_address,
        "head_address": store.head_address,
        "entry_count": store.registry.entry_count,
        "accepted_entry_count": store.registry.accepted_entry_count,
        "blocked_entry_count": store.registry.blocked_entry_count,
        "operation_count": store.operation_count,
        "append_count": store.append_count,
        "rejection_count": store.rejection_count,
        "idempotent_count": store.idempotent_count,
        "accepted": store.accepted,
    }


def _payloads(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> tuple[tuple[str, str, str, str, bytes], ...]:
    audit = audit_release_assurance_attestation_registry_store(store)
    return (
        (
            "store-json",
            "store/store.json",
            "application/json",
            "store",
            release_assurance_attestation_registry_store_json(store).encode("utf-8"),
        ),
        (
            "operations-csv",
            "store/operations.csv",
            "text/csv",
            "operations",
            release_assurance_attestation_registry_store_operations_csv(store),
        ),
        (
            "policy-json",
            "store/policy.json",
            "application/json",
            "policy",
            canonical_payload(store.policy.to_dict()),
        ),
        (
            "head-json",
            "store/head.json",
            "application/json",
            "head",
            canonical_payload(store.head.to_dict()),
        ),
        (
            "audit-json",
            "store/audit.json",
            "application/json",
            "audit",
            canonical_payload(audit.to_dict()),
        ),
        (
            "summary-json",
            "store/summary.json",
            "application/json",
            "summary",
            canonical_payload(_summary(store)),
        ),
        (
            "schema-json",
            "store/schema.json",
            "application/json",
            "schema",
            canonical_payload(release_assurance_attestation_registry_store_schema()),
        ),
        (
            "capabilities-json",
            "store/capabilities.json",
            "application/json",
            "capabilities",
            canonical_payload(release_assurance_attestation_registry_store_capabilities()),
        ),
    )


def release_assurance_attestation_registry_store_packet_artifact_payloads(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> dict[str, bytes]:
    """Return exact payload bytes keyed by fixed artifact ID."""

    return {
        artifact_id: content for artifact_id, _path, _media_type, _role, content in _payloads(store)
    }


def _manifest_body(
    manifest: ReleaseAssuranceAttestationRegistryStorePacketManifest,
) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "schema_version": manifest.schema_version,
        "packet_id": manifest.packet_id,
        "store_id": manifest.store_id,
        "registry_id": manifest.registry_id,
        "artifact_count": manifest.artifact_count,
        "payload_artifact_count": manifest.payload_artifact_count,
        "artifacts": manifest.artifacts,
        "source_addresses": manifest.source_addresses,
        "accepted": manifest.accepted,
    }


def build_release_assurance_attestation_registry_store_packet(
    store: ReleaseAssuranceAttestationRegistryStore,
    *,
    packet_id: str = "glio-noncode-release-assurance-attestation-registry-store-packet",
) -> ReleaseAssuranceAttestationRegistryStorePacket:
    """Build the fixed eight-payload plus manifest store packet."""

    if not isinstance(store, ReleaseAssuranceAttestationRegistryStore):
        raise ValidationError("store packet requires a typed store")
    if not packet_id.strip():
        raise ValidationError("store packet ID must not be empty")
    values = _payloads(store)
    if len(values) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT:
        raise ValidationError("store packet payload denominator is not closed")
    artifacts = tuple(
        _artifact(artifact_id, path, media_type, role, store.content_address, content)
        for artifact_id, path, media_type, role, content in values
    )
    if (
        tuple(item.artifact_id for item in artifacts)
        != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS
    ):
        raise ValidationError("store packet payload IDs are not closed")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    source_addresses = (
        ("store", store.content_address),
        ("registry", store.registry.content_address),
        ("head", store.head_address),
    )
    accepted = store.accepted and all(item.required for item in artifacts)
    manifest_body = {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "store_id": store.store_id,
        "registry_id": store.registry.registry_id,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "source_addresses": source_addresses,
        "accepted": accepted,
    }
    manifest = ReleaseAssuranceAttestationRegistryStorePacketManifest(
        **manifest_body,
        content_address=content_hash(
            manifest_body,
            prefix="release-assurance-attestation-registry-store-manifest",
        ),
    )
    body = {
        "packet_id": packet_id,
        "store_id": store.store_id,
        "registry_id": store.registry.registry_id,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryStorePacket(
        packet_id=packet_id,
        store_id=store.store_id,
        registry_id=store.registry.registry_id,
        artifacts=artifacts,
        manifest=manifest,
        accepted=accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-packet",
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


def write_release_assurance_attestation_registry_store_packet(
    packet: ReleaseAssuranceAttestationRegistryStorePacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write packet payloads atomically into a controlled directory."""

    if not isinstance(packet, ReleaseAssuranceAttestationRegistryStorePacket):
        raise ValidationError("store packet writer requires a typed packet")
    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("store packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("store packet destination is not empty")
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
            "store_id",
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
        prefix="release-assurance-attestation-registry-store-manifest",
    ):
        drift.append("manifest.content_address")
    if value.get("version") != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_VERSION:
        drift.append("manifest.version")
    if (
        value.get("schema_version")
        != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_SCHEMA_VERSION
    ):
        drift.append("manifest.schema_version")
    return root, value, tuple(drift)


def _empty_verification(
    root: Path,
) -> ReleaseAssuranceAttestationRegistryStorePacketVerification:
    body = {
        "directory": str(root),
        "packet_id": "",
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
    return ReleaseAssuranceAttestationRegistryStorePacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-verification",
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


def verify_release_assurance_attestation_registry_store_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationRegistryStorePacketVerification:
    """Verify packet closure, exact bytes, addresses, and public boundaries."""

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
    if len(listed) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT:
        manifest_drift = (*manifest_drift, "manifest.payload_denominator")
    if len(listed) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_MAX_ARTIFACTS:
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
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        else:
            boundary.extend(f"{path}:{value}" for value in _text_boundary(payload))
    if tuple(artifact_ids) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS:
        manifest_drift = (*manifest_drift, "manifest.payload_ids")
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
        and str(manifest.get("store_id", ""))
        and str(manifest.get("registry_id", ""))
        and len(listed) == RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT
        and tuple(artifact_ids) == RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS
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
    return ReleaseAssuranceAttestationRegistryStorePacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-verification",
        ),
    )


def load_release_assurance_attestation_registry_store_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationRegistryStorePacketOffline:
    """Hydrate a store only after exact-byte verification succeeds."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_release_assurance_attestation_registry_store_packet(root)
    if not verification.accepted:
        raise ValidationError("store packet is not accepted")
    path = root / "store" / "store.json"
    try:
        store_payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("store packet store payload is not valid JSON") from exc
    store = ReleaseAssuranceAttestationRegistryStore.from_mapping(store_payload)
    if store.store_id != manifest.get("store_id"):
        raise ValidationError("store packet store ID does not reconcile")
    if store.registry.registry_id != manifest.get("registry_id"):
        raise ValidationError("store packet registry ID does not reconcile")
    audit = verify_release_assurance_attestation_registry_store(store)
    if not audit.accepted:
        raise ValidationError("store packet store audit is not accepted")
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "store": store.to_dict(),
        "manifest": manifest,
        "verification": verification.to_dict(),
    }
    return ReleaseAssuranceAttestationRegistryStorePacketOffline(
        packet_id=str(manifest.get("packet_id", "")),
        store=store,
        manifest=manifest,
        verification=verification,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-offline",
        ),
    )


def release_assurance_attestation_registry_store_packet_capabilities() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_SCHEMA_VERSION,
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_BOUNDARY,
        "store_boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY,
        "fixed_payload_count": True,
        "manifest_address": True,
        "atomic_write": True,
        "exact_byte_verification": True,
        "safe_path_verification": True,
        "symlink_rejection": True,
        "duplicate_path_detection": True,
        "unexpected_file_detection": True,
        "tamper_detection": True,
        "boundary_scan": True,
        "offline_hydration": True,
        "source_payloads": False,
        "timestamp_free": True,
        "payload_ids": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS,
        "payload_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_ARTIFACT_COUNT,
    }


def release_assurance_attestation_registry_store_packet_schema() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_SCHEMA_VERSION,
        "type": "object",
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_BOUNDARY,
        "required": (
            "packet_id",
            "store_id",
            "registry_id",
            "artifacts",
            "manifest",
            "accepted",
            "content_address",
        ),
        "payload_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_ARTIFACT_COUNT,
        "payload_ids": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS,
        "artifact_roles": (
            "store",
            "operations",
            "policy",
            "head",
            "audit",
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
                "store_id",
                "registry_id",
                "artifact_count",
                "payload_artifact_count",
                "artifacts",
                "source_addresses",
                "accepted",
                "content_address",
            ),
        },
        "verification": {
            "checks": (
                "safe_relative_paths",
                "symlinks",
                "exact_bytes",
                "content_addresses",
                "manifest_closure",
                "public_boundary",
                "unexpected_files",
                "offline_hydration",
            )
        },
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("build_release_assurance_attestation_registry_store_packet")
    or name.startswith("write_release_assurance_attestation_registry_store_packet")
    or name.startswith("verify_release_assurance_attestation_registry_store_packet")
    or name.startswith("load_release_assurance_attestation_registry_store_packet")
    or name.startswith("release_assurance_attestation_registry_store_packet_")
    or name.startswith("ReleaseAssuranceAttestationRegistryStorePacket")
]

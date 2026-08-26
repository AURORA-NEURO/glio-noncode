"""Fixed artifact packets for offline storage-catalog review."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
)
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash
from .storage_catalog import (
    _as_catalog,
    build_storage_catalog,
    storage_catalog_capabilities,
    storage_catalog_entries_csv,
    storage_catalog_indexes_csv,
    storage_catalog_json,
    storage_catalog_schema,
)
from .storage_catalog_contracts import StorageCatalog
from .storage_catalog_observability import (
    _as_observability,
    build_storage_catalog_observability,
    storage_catalog_observability_events_csv,
    storage_catalog_observability_json,
    storage_catalog_observability_metrics_csv,
)
from .storage_catalog_observability_contracts import StorageCatalogObservability
from .storage_catalog_packet_contracts import (
    STORAGE_CATALOG_PACKET_ARTIFACT_COUNT,
    STORAGE_CATALOG_PACKET_BOUNDARY,
    STORAGE_CATALOG_PACKET_MAX_ARTIFACTS,
    STORAGE_CATALOG_PACKET_PAYLOAD_COUNT,
    STORAGE_CATALOG_PACKET_PAYLOAD_IDS,
    STORAGE_CATALOG_PACKET_SCHEMA_VERSION,
    STORAGE_CATALOG_PACKET_VERSION,
    StorageCatalogPacket,
    StorageCatalogPacketArtifact,
    StorageCatalogPacketManifest,
    StorageCatalogPacketOffline,
    StorageCatalogPacketVerification,
)

_EXPECTED_ARTIFACTS = {
    "catalog-json": ("catalog/catalog.json", "application/json", "catalog"),
    "entries-csv": ("catalog/entries.csv", "text/csv", "entries"),
    "indexes-csv": ("catalog/indexes.csv", "text/csv", "indexes"),
    "summary-json": ("catalog/summary.json", "application/json", "summary"),
    "schema-json": ("catalog/schema.json", "application/json", "schema"),
    "capabilities-json": ("catalog/capabilities.json", "application/json", "capabilities"),
    "observability-json": ("catalog/observability.json", "application/json", "observability"),
    "events-csv": ("catalog/events.csv", "text/csv", "events"),
    "metrics-csv": ("catalog/metrics.csv", "text/csv", "metrics"),
    "boundary-json": ("catalog/boundary.json", "application/json", "boundary"),
}


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    role: str,
    source_address: str,
    payload: bytes,
) -> StorageCatalogPacketArtifact:
    path = safe_relative_path(relative_path)
    if not isinstance(payload, bytes):
        raise ValidationError("catalog packet artifact content must be bytes")
    return StorageCatalogPacketArtifact(
        artifact_id=artifact_id,
        relative_path=path,
        media_type=media_type,
        role=role,
        source_address=source_address,
        byte_count=len(payload),
        line_count=line_count(payload),
        content_address=artifact_address(payload),
        content=payload,
    )


def _catalog_source(value: StorageCatalog | CaseRuntime | Mapping[str, Any]) -> StorageCatalog:
    if isinstance(value, CaseRuntime):
        return build_storage_catalog(value)
    return _as_catalog(value)


def _observability_source(
    value: StorageCatalogObservability | Mapping[str, Any] | None, catalog: StorageCatalog
) -> StorageCatalogObservability:
    if value is None:
        return build_storage_catalog_observability(catalog)
    return _as_observability(value)


def _summary(catalog: StorageCatalog, observability: StorageCatalogObservability) -> dict[str, Any]:
    return {
        "catalog_address": catalog.content_address,
        "observability_address": observability.content_address,
        "root": catalog.root,
        "entry_count": catalog.entry_count,
        "object_count": catalog.object_count,
        "missing_count": catalog.missing_count,
        "run_count": catalog.run_count,
        "batch_count": catalog.batch_count,
        "unexpected_count": catalog.unexpected_count,
        "index_row_count": catalog.index_row_count,
        "event_count": observability.event_count,
        "metric_count": observability.metric_count,
        "accepted": catalog.accepted and observability.accepted,
    }


def _boundary(
    catalog: StorageCatalog, observability: StorageCatalogObservability
) -> dict[str, Any]:
    return {
        "boundary": STORAGE_CATALOG_PACKET_BOUNDARY,
        "catalog_boundary": catalog.boundary,
        "observability_boundary": observability.boundary,
        "address_only": True,
        "payload_exposure": False,
        "source_object_bytes": False,
        "timestamp_free": True,
        "mutation": False,
        "catalog_address": catalog.content_address,
        "observability_address": observability.content_address,
    }


def _payloads(
    catalog: StorageCatalog, observability: StorageCatalogObservability
) -> tuple[tuple[str, str, str, str, bytes], ...]:
    return (
        (
            "catalog-json",
            "catalog/catalog.json",
            "application/json",
            "catalog",
            (storage_catalog_json(catalog) + "\n").encode("utf-8"),
        ),
        (
            "entries-csv",
            "catalog/entries.csv",
            "text/csv",
            "entries",
            storage_catalog_entries_csv(catalog).encode("utf-8"),
        ),
        (
            "indexes-csv",
            "catalog/indexes.csv",
            "text/csv",
            "indexes",
            storage_catalog_indexes_csv(catalog).encode("utf-8"),
        ),
        (
            "summary-json",
            "catalog/summary.json",
            "application/json",
            "summary",
            canonical_payload(_summary(catalog, observability)),
        ),
        (
            "schema-json",
            "catalog/schema.json",
            "application/json",
            "schema",
            canonical_payload(storage_catalog_schema()),
        ),
        (
            "capabilities-json",
            "catalog/capabilities.json",
            "application/json",
            "capabilities",
            canonical_payload(storage_catalog_capabilities()),
        ),
        (
            "observability-json",
            "catalog/observability.json",
            "application/json",
            "observability",
            (storage_catalog_observability_json(observability) + "\n").encode("utf-8"),
        ),
        (
            "events-csv",
            "catalog/events.csv",
            "text/csv",
            "events",
            storage_catalog_observability_events_csv(observability).encode("utf-8"),
        ),
        (
            "metrics-csv",
            "catalog/metrics.csv",
            "text/csv",
            "metrics",
            storage_catalog_observability_metrics_csv(observability).encode("utf-8"),
        ),
        (
            "boundary-json",
            "catalog/boundary.json",
            "application/json",
            "boundary",
            canonical_payload(_boundary(catalog, observability)),
        ),
    )


def storage_catalog_packet_artifact_payloads(
    source: StorageCatalog | CaseRuntime | Mapping[str, Any],
    *,
    observability: StorageCatalogObservability | Mapping[str, Any] | None = None,
) -> dict[str, bytes]:
    """Return exact fixed packet bytes keyed by artifact identifier."""

    catalog = _catalog_source(source)
    selected_observability = _observability_source(observability, catalog)
    return {
        artifact_id: payload
        for artifact_id, _path, _media, _role, payload in _payloads(catalog, selected_observability)
    }


def build_storage_catalog_packet(
    source: StorageCatalog | CaseRuntime | Mapping[str, Any],
    *,
    packet_id: str = "glio-noncode-storage-catalog-packet",
    observability: StorageCatalogObservability | Mapping[str, Any] | None = None,
) -> StorageCatalogPacket:
    """Build a fixed ten-artifact packet without copying source object bytes."""

    catalog = _catalog_source(source)
    selected_observability = _observability_source(observability, catalog)
    packet_id = _text(packet_id, "catalog packet ID", maximum=220)
    values = _payloads(catalog, selected_observability)
    if (
        len(values) != STORAGE_CATALOG_PACKET_PAYLOAD_COUNT
        or tuple(item[0] for item in values) != STORAGE_CATALOG_PACKET_PAYLOAD_IDS
    ):
        raise ValidationError("catalog packet payload denominator is not closed")
    artifacts = tuple(
        _artifact(artifact_id, path, media_type, role, catalog.content_address, payload)
        for artifact_id, path, media_type, role, payload in values
    )
    metadata = tuple(item.metadata_dict() for item in artifacts)
    manifest_body = {
        "version": STORAGE_CATALOG_PACKET_VERSION,
        "schema_version": STORAGE_CATALOG_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "catalog_address": catalog.content_address,
        "observability_address": selected_observability.content_address,
        "artifact_count": STORAGE_CATALOG_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "accepted": catalog.accepted and selected_observability.accepted,
    }
    manifest = StorageCatalogPacketManifest(
        **manifest_body,
        content_address=content_hash(manifest_body, prefix="storage-catalog-packet-manifest"),
    )
    packet_body = {
        "packet_id": packet_id,
        "catalog_address": catalog.content_address,
        "observability_address": selected_observability.content_address,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": manifest.accepted,
    }
    return StorageCatalogPacket(
        packet_id=packet_id,
        catalog_address=catalog.content_address,
        observability_address=selected_observability.content_address,
        artifacts=artifacts,
        manifest=manifest,
        accepted=manifest.accepted,
        content_address=content_hash(packet_body, prefix="storage-catalog-packet"),
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


def write_storage_catalog_packet(
    packet: StorageCatalogPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Atomically write the fixed packet files into an empty directory."""

    if not isinstance(packet, StorageCatalogPacket):
        raise ValidationError("catalog packet writer requires a typed packet")
    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("catalog packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("catalog packet destination is not empty")
    for artifact in packet.artifacts:
        _atomic_write(root / safe_relative_path(artifact.relative_path), artifact.content)
    _atomic_write(
        root / "manifest.json", (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    )
    return root


def _read_manifest(directory: str | Path) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
    root = Path(directory)
    path = root / "manifest.json"
    if not path.is_file() or path.is_symlink():
        return root, {}, ("manifest.json",)
    try:
        raw_bytes = path.read_bytes()
        value = json.loads(raw_bytes.decode("utf-8"))
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
            "catalog_address",
            "observability_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "accepted",
        )
    }
    drift: list[str] = []
    if raw_bytes != (canonical_json(value) + "\n").encode("utf-8"):
        drift.append("manifest.canonical_bytes")
    if value.get("content_address") != content_hash(body, prefix="storage-catalog-packet-manifest"):
        drift.append("manifest.content_address")
    try:
        StorageCatalogPacketManifest.from_mapping(value)
    except ValidationError:
        drift.append("manifest.contract")
    if value.get("version") != STORAGE_CATALOG_PACKET_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != STORAGE_CATALOG_PACKET_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    return root, value, tuple(sorted(set(drift)))


def _empty_verification(root: Path) -> StorageCatalogPacketVerification:
    body = {
        "directory": str(root),
        "packet_id": "",
        "catalog_address": "",
        "observability_address": "",
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
    return StorageCatalogPacketVerification(
        **body, content_address=content_hash(body, prefix="storage-catalog-packet-verification")
    )


def _listed(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    values = manifest.get("artifacts", ())
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, dict))


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
            "identity",
            "language",
            "model",
            "patient",
            "producer",
            "subject",
        )
        if token in text
    )


def verify_storage_catalog_packet(directory: str | Path) -> StorageCatalogPacketVerification:
    """Verify exact bytes, fixed paths, source identities, and public boundaries."""

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
        payload_count = int(manifest.get("payload_artifact_count"))
        artifact_count = int(manifest.get("artifact_count"))
    except (TypeError, ValueError, OverflowError):
        payload_count = -1
        artifact_count = -1
        manifest_drift = (*manifest_drift, "manifest.counts")
    if len(listed) != payload_count or artifact_count != len(listed) + 1:
        manifest_drift = (*manifest_drift, "manifest.artifact_counts")
    if len(listed) != STORAGE_CATALOG_PACKET_PAYLOAD_COUNT:
        manifest_drift = (*manifest_drift, "manifest.payload_denominator")
    if len(listed) > STORAGE_CATALOG_PACKET_MAX_ARTIFACTS:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
    catalog_payload: Mapping[str, Any] | None = None
    observability_payload: Mapping[str, Any] | None = None
    for item in listed:
        artifact_id = str(item.get("artifact_id", ""))
        relative = str(item.get("relative_path", ""))
        if artifact_id in artifact_ids:
            manifest_drift = (*manifest_drift, f"manifest.duplicate_artifact_id:{artifact_id}")
        artifact_ids.append(artifact_id)
        expected_descriptor = _EXPECTED_ARTIFACTS.get(artifact_id)
        if expected_descriptor is None:
            manifest_drift = (*manifest_drift, f"manifest.unknown_artifact_id:{artifact_id}")
        elif (
            relative,
            str(item.get("media_type", "")),
            str(item.get("role", "")),
        ) != expected_descriptor:
            manifest_drift = (*manifest_drift, f"manifest.artifact_contract:{artifact_id}")
        try:
            path = safe_relative_path(relative)
        except ValidationError:
            unsafe.append(relative)
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
        media_type = str(item.get("media_type", ""))
        if media_type == "application/json":
            try:
                decoded = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{path}:{violation}" for violation in forbidden_keys(decoded))
                if artifact_id == "catalog-json" and isinstance(decoded, Mapping):
                    catalog_payload = decoded
                if artifact_id == "observability-json" and isinstance(decoded, Mapping):
                    observability_payload = decoded
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        else:
            boundary.extend(f"{path}:{value}" for value in _text_boundary(payload))
    if tuple(artifact_ids) != STORAGE_CATALOG_PACKET_PAYLOAD_IDS:
        manifest_drift = (*manifest_drift, "manifest.payload_ids")
    catalog_ok = False
    observability_ok = False
    catalog_address = str(manifest.get("catalog_address", ""))
    observability_address = str(manifest.get("observability_address", ""))
    if catalog_payload is not None:
        try:
            catalog = StorageCatalog.from_mapping(catalog_payload)
            catalog_ok = catalog.content_address == catalog_address
            if not catalog_ok:
                manifest_drift = (*manifest_drift, "manifest.catalog_identity")
        except ValidationError:
            tampered.append("catalog/catalog.json")
    if observability_payload is not None:
        try:
            observability = StorageCatalogObservability.from_mapping(observability_payload)
            observability_ok = (
                observability.content_address == observability_address
                and observability.catalog_address == catalog_address
            )
            if not observability_ok:
                manifest_drift = (*manifest_drift, "manifest.observability_identity")
        except ValidationError:
            tampered.append("catalog/observability.json")
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    unexpected.extend(
        path for path in actual_paths if path not in sorted((*expected_paths, "manifest.json"))
    )
    accepted = bool(
        manifest.get("accepted")
        and str(manifest.get("packet_id", ""))
        and catalog_address
        and observability_address
        and len(listed) == STORAGE_CATALOG_PACKET_PAYLOAD_COUNT
        and tuple(artifact_ids) == STORAGE_CATALOG_PACKET_PAYLOAD_IDS
        and catalog_ok
        and observability_ok
        and not any(
            (missing, unexpected, unsafe, tampered, duplicate_paths, boundary, manifest_drift)
        )
    )
    body = {
        "directory": str(root),
        "packet_id": str(manifest.get("packet_id", "")),
        "catalog_address": catalog_address,
        "observability_address": observability_address,
        "checked_artifact_count": len(listed),
        "missing_paths": tuple(sorted(set(missing))),
        "unexpected_paths": tuple(sorted(set(unexpected))),
        "unsafe_paths": tuple(sorted(set(unsafe))),
        "tampered_paths": tuple(sorted(set(tampered))),
        "duplicate_paths": tuple(sorted(set(duplicate_paths))),
        "manifest_drift": tuple(sorted(set(manifest_drift))),
        "boundary_violations": tuple(sorted(set(boundary))),
        "accepted": accepted,
    }
    return StorageCatalogPacketVerification(
        **body, content_address=content_hash(body, prefix="storage-catalog-packet-verification")
    )


def load_storage_catalog_packet(directory: str | Path) -> StorageCatalogPacketOffline:
    """Hydrate the catalog and observations only after strict verification."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_storage_catalog_packet(root)
    if not verification.accepted:
        raise ValidationError("storage catalog packet is not accepted")
    try:
        catalog_payload = json.loads(
            (root / "catalog" / "catalog.json").read_text(encoding="utf-8")
        )
        observability_payload = json.loads(
            (root / "catalog" / "observability.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("storage catalog packet JSON payload is not valid") from exc
    catalog = StorageCatalog.from_mapping(catalog_payload)
    observability = StorageCatalogObservability.from_mapping(observability_payload)
    if (catalog.content_address, observability.content_address) != (
        manifest.get("catalog_address"),
        manifest.get("observability_address"),
    ):
        raise ValidationError("storage catalog packet source identity does not reconcile")
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "catalog": catalog.to_dict(),
        "observability": observability.to_dict(),
        "manifest": manifest,
        "verification": verification.to_dict(),
    }
    return StorageCatalogPacketOffline(
        packet_id=str(manifest.get("packet_id", "")),
        catalog=catalog,
        observability=observability,
        manifest=manifest,
        verification=verification,
        content_address=content_hash(body, prefix="storage-catalog-packet-offline"),
    )


def storage_catalog_packet_json(
    packet: StorageCatalogPacket, *, include_content: bool = False
) -> str:
    if not isinstance(packet, StorageCatalogPacket):
        raise ValidationError("storage catalog packet JSON requires a typed packet")
    return canonical_json(packet.to_dict(include_content=include_content))


def storage_catalog_packet_capabilities() -> dict[str, Any]:
    return {
        "version": STORAGE_CATALOG_PACKET_VERSION,
        "schema_version": STORAGE_CATALOG_PACKET_SCHEMA_VERSION,
        "boundary": STORAGE_CATALOG_PACKET_BOUNDARY,
        "fixed_payload_count": True,
        "manifest_address": True,
        "atomic_write": True,
        "exact_byte_verification": True,
        "safe_path_verification": True,
        "symlink_rejection": True,
        "duplicate_path_detection": True,
        "unexpected_file_detection": True,
        "tamper_detection": True,
        "catalog_identity_verification": True,
        "observability_identity_verification": True,
        "boundary_scan": True,
        "offline_hydration": True,
        "source_payloads": False,
        "timestamp_free": True,
        "payload_ids": STORAGE_CATALOG_PACKET_PAYLOAD_IDS,
        "payload_count": STORAGE_CATALOG_PACKET_PAYLOAD_COUNT,
        "artifact_count": STORAGE_CATALOG_PACKET_ARTIFACT_COUNT,
    }


def storage_catalog_packet_schema() -> dict[str, Any]:
    return {
        "version": STORAGE_CATALOG_PACKET_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_CATALOG_PACKET_BOUNDARY,
        "required": (
            "packet_id",
            "catalog_address",
            "observability_address",
            "artifacts",
            "manifest",
            "accepted",
            "content_address",
        ),
        "payload_count": STORAGE_CATALOG_PACKET_PAYLOAD_COUNT,
        "artifact_count": STORAGE_CATALOG_PACKET_ARTIFACT_COUNT,
        "payload_ids": STORAGE_CATALOG_PACKET_PAYLOAD_IDS,
        "artifact_roles": (
            "catalog",
            "entries",
            "indexes",
            "summary",
            "schema",
            "capabilities",
            "observability",
            "events",
            "metrics",
            "boundary",
        ),
        "manifest_required": (
            "version",
            "schema_version",
            "packet_id",
            "catalog_address",
            "observability_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "accepted",
            "content_address",
        ),
        "verification": {
            "exact_bytes": True,
            "content_addresses": True,
            "catalog_identity": True,
            "observability_identity": True,
            "safe_paths": True,
            "unexpected_paths": True,
            "public_boundary": True,
        },
        "source_payloads": False,
        "timestamp_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_CATALOG_PACKET")
    or name.startswith("StorageCatalogPacket")
    or name.startswith("build_storage_catalog_packet")
    or name.startswith("load_storage_catalog_packet")
    or name.startswith("storage_catalog_packet")
    or name.startswith("verify_storage_catalog_packet")
    or name.startswith("write_storage_catalog_packet")
]

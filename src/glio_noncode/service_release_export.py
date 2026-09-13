"""Exact-byte export and filesystem verification for service releases."""

from __future__ import annotations

from pathlib import Path

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash
from .service_release_bundle import service_release_artifact_payloads
from .service_release_contracts import (
    SERVICE_RELEASE_EXPORT_VERSION,
    ServiceReleaseExportArtifact,
    ServiceReleaseExportManifest,
    ServiceReleaseExportPacket,
    ServiceReleaseExportVerification,
    ServiceReleaseRuntimeReport,
)
from .service_release_support import artifact_address, forbidden_keys, safe_relative_path
from .service_surface import ServiceSurfaceSnapshot


def build_service_release_export(
    runtime: ServiceReleaseRuntimeReport,
    source_snapshot: ServiceSurfaceSnapshot | None = None,
) -> ServiceReleaseExportPacket:
    """Build an exact-byte packet from a verified runtime and source snapshot."""

    source = source_snapshot or __import__(
        "glio_noncode.service_surface", fromlist=["build_service_surface_snapshot"]
    ).build_service_surface_snapshot()
    payloads = service_release_artifact_payloads(source)
    artifacts: list[ServiceReleaseExportArtifact] = []
    for metadata in runtime.snapshot.artifacts:
        payload = payloads.get(metadata.artifact_id)
        if payload is None:
            raise ValidationError(f"missing service release payload: {metadata.artifact_id}")
        artifact = ServiceReleaseExportArtifact(
            relative_path=metadata.relative_path,
            media_type=metadata.media_type,
            byte_count=len(payload),
            content_address=artifact_address(payload),
            content=payload,
        )
        if artifact.byte_count != metadata.byte_count or artifact.content_address != metadata.content_address:
            raise ValidationError(f"service release artifact metadata drift: {metadata.artifact_id}")
        artifacts.append(artifact)
    manifest_body = {
        "version": SERVICE_RELEASE_EXPORT_VERSION,
        "bundle_id": runtime.snapshot.bundle_id,
        "artifact_count": len(artifacts),
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "accepted": runtime.accepted,
    }
    manifest = ServiceReleaseExportManifest(
        **manifest_body,
        content_address=content_hash(manifest_body, prefix="service-release-export-manifest"),
    )
    body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "manifest": manifest.to_dict(),
        "accepted": runtime.accepted,
    }
    return ServiceReleaseExportPacket(
        runtime.snapshot.bundle_id,
        tuple(artifacts),
        manifest,
        runtime.accepted,
        content_hash(body, prefix="service-release-export"),
    )


def write_service_release_export(packet: ServiceReleaseExportPacket, destination: str | Path) -> Path:
    """Write a release packet under a dedicated destination directory."""

    root = Path(destination)
    _validate_parent(root.parent, "service release export")
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise ValidationError("service release export destination must be a regular directory")
    root.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        path = root / safe_relative_path(artifact.relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(
            path,
            artifact.content,
            field=f"service release artifact {artifact.relative_path}",
        )
    manifest_path = root / "manifest.json"
    manifest_payload = (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    atomic_write_bytes(manifest_path, manifest_payload, field="service release manifest")
    return root


def verify_service_release_export(directory: str | Path) -> ServiceReleaseExportVerification:
    """Verify paths, bytes, manifest address, and public boundary on disk."""

    root = Path(directory)
    missing: list[str] = []
    unexpected: list[str] = []
    duplicate: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    manifest_path = root / "manifest.json"
    if (
        root.is_symlink()
        or not root.is_dir()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
    ):
        missing.append("manifest.json")
        body = {"directory": str(root), "checked_artifact_count": 0,
                "missing_paths": tuple(missing), "unexpected_paths": tuple(unexpected),
                "duplicate_paths": tuple(duplicate), "unsafe_paths": tuple(unsafe),
                "tampered_paths": tuple(tampered), "boundary_violations": tuple(boundary),
                "accepted": False}
        return ServiceReleaseExportVerification(
            "", 0, tuple(missing), tuple(unexpected), tuple(duplicate), tuple(unsafe),
            tuple(tampered), tuple(boundary), False,
            content_hash(body, prefix="service-release-export-verification"),
        )
    try:
        manifest = _strict_json_loads(read_text(manifest_path, field="service release manifest"))
    except (OSError, UnicodeError, ValueError, ValidationError):
        tampered.append("manifest.json")
        manifest = {}
    listed = manifest.get("artifacts", ()) if isinstance(manifest, dict) else ()
    expected_paths: list[str] = []
    for item in listed if isinstance(listed, list) else ():
        if not isinstance(item, dict):
            tampered.append("manifest.artifacts")
            continue
        path_text = str(item.get("relative_path", ""))
        try:
            path = safe_relative_path(path_text)
        except ValidationError:
            unsafe.append(path_text)
            continue
        if path in expected_paths:
            duplicate.append(path)
        expected_paths.append(path)
        target = root / path
        if target.is_symlink() or not target.is_file():
            missing.append(path)
            continue
        try:
            payload = read_bytes(target, field=f"service release artifact {path}")
        except (OSError, ValidationError):
            tampered.append(path)
            continue
        if len(payload) != int(item.get("byte_count", -1)) or artifact_address(payload) != item.get("content_address"):
            tampered.append(path)
        try:
            decoded = _strict_json_loads(payload.decode("utf-8")) if item.get("media_type") == "application/json" else None
            boundary.extend(forbidden_keys(decoded))
        except (UnicodeError, ValueError):
            tampered.append(path)
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )
    expected_with_manifest = sorted((*expected_paths, "manifest.json"))
    unexpected.extend(path for path in actual_paths if path not in expected_with_manifest)
    accepted = bool(manifest) and not any((missing, unexpected, duplicate, unsafe, tampered, boundary))
    body = {
        "bundle_id": str(manifest.get("bundle_id", "")) if isinstance(manifest, dict) else "",
        "checked_artifact_count": len(expected_paths),
        "missing_paths": tuple(sorted(missing)),
        "unexpected_paths": tuple(sorted(unexpected)),
        "duplicate_paths": tuple(sorted(duplicate)),
        "unsafe_paths": tuple(sorted(unsafe)),
        "tampered_paths": tuple(sorted(tampered)),
        "boundary_violations": tuple(sorted(set(boundary))),
        "accepted": accepted,
    }
    return ServiceReleaseExportVerification(
        body["bundle_id"], body["checked_artifact_count"], body["missing_paths"],
        body["unexpected_paths"], body["duplicate_paths"], body["unsafe_paths"],
        body["tampered_paths"], body["boundary_violations"], accepted,
        content_hash(body, prefix="service-release-export-verification"),
    )


__all__ = [
    "build_service_release_export",
    "verify_service_release_export",
    "write_service_release_export",
]

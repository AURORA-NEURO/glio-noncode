"""Exact-byte export and filesystem verification for release assurance."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import ValidationError
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_EXPORT_VERSION,
    ReleaseAssuranceExportArtifact,
    ReleaseAssuranceExportManifest,
    ReleaseAssuranceExportPacket,
    ReleaseAssuranceExportVerification,
    ReleaseAssuranceRuntimeReport,
)
from .release_assurance_schema import release_assurance_schema
from .release_assurance_summary import release_assurance_status
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    csv_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
)
from .serialization import canonical_json, content_hash


def _artifact_values(runtime: ReleaseAssuranceRuntimeReport):
    snapshot = runtime.snapshot
    return (
        ("runtime-json", "runtime/release-assurance.json", "application/json", runtime.to_dict()),
        ("status-json", "runtime/status.json", "application/json", release_assurance_status(snapshot)),
        ("summary-json", "assurance/summary.json", "application/json", runtime.summary.to_dict()),
        ("domains-csv", "assurance/domains.csv", "text/csv", [item.to_dict() for item in snapshot.domains]),
        ("checks-csv", "assurance/checks.csv", "text/csv", [item.to_dict() for item in snapshot.checks]),
        ("evidence-csv", "assurance/evidence.csv", "text/csv", [item.to_dict() for item in snapshot.evidence]),
        ("observability-json", "assurance/observability.json", "application/json", runtime.observability.to_dict()),
        ("plan-json", "assurance/plan.json", "application/json", runtime.plan.to_dict()),
        ("views-json", "assurance/views.json", "application/json", runtime.views.to_dict()),
        ("schema-json", "assurance/schema.json", "application/json", release_assurance_schema()),
    )


def _payload(value, media_type: str) -> bytes:
    if media_type == "text/csv":
        return csv_payload(value)
    return canonical_payload(value)


def release_assurance_artifact_payloads(runtime: ReleaseAssuranceRuntimeReport) -> dict[str, bytes]:
    """Return the exact bytes behind every release-assurance artifact."""

    return {
        artifact_id: _payload(value, media_type)
        for artifact_id, _path, media_type, value in _artifact_values(runtime)
    }


def build_release_assurance_export(
    runtime: ReleaseAssuranceRuntimeReport,
) -> ReleaseAssuranceExportPacket:
    """Build a ten-artifact exact-byte packet from a verified runtime."""

    payloads = release_assurance_artifact_payloads(runtime)
    artifacts: list[ReleaseAssuranceExportArtifact] = []
    for artifact_id, relative_path, media_type, _value in _artifact_values(runtime):
        payload = payloads[artifact_id]
        artifact = ReleaseAssuranceExportArtifact(
            relative_path=safe_relative_path(relative_path),
            media_type=media_type,
            byte_count=len(payload),
            line_count=line_count(payload),
            content_address=artifact_address(payload),
            content=payload,
        )
        artifacts.append(artifact)
    if len(artifacts) != RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT:
        raise ValidationError("release-assurance export denominator is not closed")
    manifest_body = {
        "version": RELEASE_ASSURANCE_EXPORT_VERSION,
        "bundle_id": runtime.snapshot.bundle_id,
        "artifact_count": len(artifacts),
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "accepted": runtime.accepted,
    }
    manifest = ReleaseAssuranceExportManifest(
        **manifest_body,
        content_address=content_hash(manifest_body, prefix="release-assurance-export-manifest"),
    )
    body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "manifest": manifest.to_dict(),
        "accepted": runtime.accepted,
    }
    return ReleaseAssuranceExportPacket(
        runtime.snapshot.bundle_id,
        tuple(artifacts),
        manifest,
        runtime.accepted,
        content_hash(body, prefix="release-assurance-export"),
    )


def write_release_assurance_export(
    packet: ReleaseAssuranceExportPacket,
    destination: str | Path,
) -> Path:
    """Write an exact-byte packet under a dedicated directory."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        path = root / safe_relative_path(artifact.relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact.content)
    (root / "manifest.json").write_bytes(
        (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    )
    return root


def verify_release_assurance_export(
    directory: str | Path,
) -> ReleaseAssuranceExportVerification:
    """Verify paths, bytes, manifest closure, and public boundary on disk."""

    root = Path(directory)
    missing: list[str] = []
    unexpected: list[str] = []
    duplicate: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    manifest_path = root / "manifest.json"
    manifest: dict[str, object] = {}
    if not manifest_path.is_file():
        missing.append("manifest.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            tampered.append("manifest.json")
    expected_paths: list[str] = []
    listed = manifest.get("artifacts", ()) if isinstance(manifest, dict) else ()
    for item in listed if isinstance(listed, list) else ():
        if not isinstance(item, dict):
            tampered.append("manifest.artifacts")
            continue
        raw_path = str(item.get("relative_path", ""))
        try:
            path = safe_relative_path(raw_path)
        except ValidationError:
            unsafe.append(raw_path)
            continue
        if path in expected_paths:
            duplicate.append(path)
        expected_paths.append(path)
        target = root / path
        if not target.is_file():
            missing.append(path)
            continue
        try:
            payload = target.read_bytes()
        except OSError:
            tampered.append(path)
            continue
        if len(payload) != int(item.get("byte_count", -1)) or artifact_address(payload) != item.get("content_address"):
            tampered.append(path)
        try:
            if item.get("media_type") == "application/json":
                boundary.extend(forbidden_keys(json.loads(payload.decode("utf-8"))))
        except (UnicodeError, json.JSONDecodeError):
            tampered.append(path)
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )
    unexpected.extend(path for path in actual_paths if path not in sorted((*expected_paths, "manifest.json")))
    accepted = bool(manifest) and not any((missing, unexpected, duplicate, unsafe, tampered, boundary))
    body = {
        "bundle_id": str(manifest.get("bundle_id", "")),
        "checked_artifact_count": len(expected_paths),
        "missing_paths": tuple(sorted(missing)),
        "unexpected_paths": tuple(sorted(unexpected)),
        "duplicate_paths": tuple(sorted(duplicate)),
        "unsafe_paths": tuple(sorted(unsafe)),
        "tampered_paths": tuple(sorted(tampered)),
        "boundary_violations": tuple(sorted(set(boundary))),
        "accepted": accepted,
    }
    return ReleaseAssuranceExportVerification(
        body["bundle_id"], body["checked_artifact_count"], body["missing_paths"],
        body["unexpected_paths"], body["duplicate_paths"], body["unsafe_paths"],
        body["tampered_paths"], body["boundary_violations"], accepted,
        content_hash(body, prefix="release-assurance-export-verification"),
    )


__all__ = [
    "build_release_assurance_export",
    "release_assurance_artifact_payloads",
    "verify_release_assurance_export",
    "write_release_assurance_export",
]

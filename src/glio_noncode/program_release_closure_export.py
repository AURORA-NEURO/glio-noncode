"""Exact-byte export and verification for the aggregate release closure."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .program_release_closure_boundary import validate_program_release_closure_boundary
from .program_release_closure_contracts import (
    ProgramReleaseExportArtifact,
    ProgramReleaseExportManifest,
    ProgramReleaseExportPacket,
    ProgramReleaseExportVerification,
    ProgramReleaseRuntimeReport,
)
from .program_release_closure_support import artifact_address, canonical_payload, safe_relative_path
from .serialization import canonical_json, content_hash

PROGRAM_RELEASE_EXPORT_MEDIA_TYPE = "application/json"
PROGRAM_RELEASE_EXPORT_MANIFEST_PATH = "manifest.json"


def _payload(value: Any) -> bytes:
    return canonical_payload(value)


def _artifact(relative_path: str, value: Any) -> ProgramReleaseExportArtifact:
    path = safe_relative_path(relative_path)
    content = _payload(value)
    return ProgramReleaseExportArtifact(
        path, PROGRAM_RELEASE_EXPORT_MEDIA_TYPE, len(content), artifact_address(content), content
    )


def _artifact_values(report: ProgramReleaseRuntimeReport) -> tuple[tuple[str, Any], ...]:
    return (
        ("snapshot.json", report.snapshot),
        ("domains.json", report.snapshot.domains),
        ("artifacts.json", report.snapshot.artifacts),
        ("dependencies.json", report.snapshot.dependencies),
        ("gates.json", report.snapshot.gates),
        ("boundary.json", validate_program_release_closure_boundary(report.snapshot)),
        ("indexes.json", report.indexes),
        ("reconciliation.json", report.reconciliation),
        ("summary.json", report.summary),
        ("certification.json", report.certification),
        ("observability.json", report.observability),
        ("graph.json", report.graph),
        ("failures.json", report.failures),
        ("plan.json", report.plan),
        ("runtime.json", report),
    )


def build_program_release_export(report: ProgramReleaseRuntimeReport) -> ProgramReleaseExportPacket:
    """Build fifteen independently addressed JSON artifacts."""

    artifacts = tuple(_artifact(path, value) for path, value in _artifact_values(report))
    inventory = tuple(item.to_dict() for item in artifacts)
    manifest_body = {
        "version": "program-release-closure-export-v1",
        "bundle_id": report.snapshot.bundle_id,
        "artifact_count": len(artifacts),
        "artifacts": inventory,
        "accepted": report.accepted,
    }
    manifest = ProgramReleaseExportManifest(
        manifest_body["version"],
        report.snapshot.bundle_id,
        len(artifacts),
        inventory,
        report.accepted,
        content_hash(manifest_body, prefix="program-release-export-manifest"),
    )
    body = {
        "bundle_id": report.snapshot.bundle_id,
        "artifacts": inventory,
        "manifest": manifest,
        "accepted": report.accepted,
    }
    return ProgramReleaseExportPacket(
        report.snapshot.bundle_id,
        artifacts,
        manifest,
        report.accepted,
        content_hash(body, prefix="program-release-export"),
    )


def write_program_release_export(
    packet: ProgramReleaseExportPacket, destination: str | Path
) -> Path:
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        path = root / PurePosixPath(safe_relative_path(artifact.relative_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact.content)
    (root / PROGRAM_RELEASE_EXPORT_MANIFEST_PATH).write_text(
        canonical_json(packet.manifest) + "\n", encoding="utf-8"
    )
    return root


def verify_program_release_export(
    packet: ProgramReleaseExportPacket, destination: str | Path
) -> ProgramReleaseExportVerification:
    root = Path(destination)
    if not root.is_dir():
        raise ValidationError("program release export directory is missing")
    expected = {safe_relative_path(item.relative_path): item for item in packet.artifacts}
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.name != PROGRAM_RELEASE_EXPORT_MANIFEST_PATH
    }
    missing = tuple(sorted(set(expected) - set(actual)))
    unexpected = tuple(sorted(set(actual) - set(expected)))
    changed: list[str] = []
    for relative_path in sorted(set(expected) & set(actual)):
        payload = actual[relative_path].read_bytes()
        if (
            payload != expected[relative_path].content
            or artifact_address(payload) != expected[relative_path].content_address
        ):
            changed.append(relative_path)
    accepted = packet.accepted and not missing and not unexpected and not changed
    body = {
        "bundle_id": packet.bundle_id,
        "checked_artifact_count": len(expected),
        "missing_paths": missing,
        "changed_paths": tuple(changed),
        "unexpected_paths": unexpected,
        "accepted": accepted,
    }
    return ProgramReleaseExportVerification(
        packet.bundle_id,
        len(expected),
        missing,
        tuple(changed),
        unexpected,
        accepted,
        content_hash(body, prefix="program-release-export-verification"),
    )


def read_program_release_export_manifest(destination: str | Path) -> dict[str, Any]:
    root = Path(destination)
    path = root / PROGRAM_RELEASE_EXPORT_MANIFEST_PATH
    if not path.is_file():
        raise ValidationError("program release export manifest is missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError("program release export manifest must be an object")
    return value


def verify_program_release_export_directory(
    destination: str | Path,
) -> ProgramReleaseExportVerification:
    """Verify an export using only its manifest and exact bytes on disk."""

    root = Path(destination)
    manifest = read_program_release_export_manifest(root)
    values = manifest.get("artifacts", ())
    expected = {
        safe_relative_path(str(item["relative_path"])): item
        for item in values
        if isinstance(item, dict)
    }
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.name != PROGRAM_RELEASE_EXPORT_MANIFEST_PATH
    }
    missing = tuple(sorted(set(expected) - set(actual)))
    unexpected = tuple(sorted(set(actual) - set(expected)))
    changed: list[str] = []
    for relative_path in sorted(set(expected) & set(actual)):
        payload = actual[relative_path].read_bytes()
        if int(expected[relative_path].get("byte_count", -1)) != len(payload) or str(
            expected[relative_path].get("content_address", "")
        ) != artifact_address(payload):
            changed.append(relative_path)
    accepted = (
        bool(manifest.get("accepted"))
        and not missing
        and not unexpected
        and not changed
        and len(expected) == int(manifest.get("artifact_count", -1))
    )
    body = {
        "bundle_id": str(manifest.get("bundle_id", "")),
        "checked_artifact_count": len(expected),
        "missing_paths": missing,
        "changed_paths": tuple(changed),
        "unexpected_paths": unexpected,
        "accepted": accepted,
    }
    return ProgramReleaseExportVerification(
        body["bundle_id"],
        body["checked_artifact_count"],
        missing,
        tuple(changed),
        unexpected,
        accepted,
        content_hash(body, prefix="program-release-export-verification"),
    )


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE_EXPORT")
    or name.startswith("build_program_release")
    or name.startswith("write_program_release")
    or name.startswith("verify_program_release")
    or name.startswith("read_program_release")
    or name.startswith("ProgramRelease")
]

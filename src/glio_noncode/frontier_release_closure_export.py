"""Exact-byte export packet for the cross-domain D13-D16 release."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT,
    FrontierReleaseExportArtifact,
    FrontierReleaseExportManifest,
    FrontierReleaseExportPacket,
    FrontierReleaseExportVerification,
)
from .frontier_release_closure_contracts import FrontierReleaseRuntimeReport
from .frontier_release_closure_support import safe_relative_path
from .serialization import canonical_json, hash_bytes, jsonable


def _value(value: Any) -> Any:
    return value.to_dict() if hasattr(value, "to_dict") else value


def _json_artifact(relative_path: str, value: Any) -> FrontierReleaseExportArtifact:
    content = (canonical_json(jsonable(_value(value))) + "\n").encode("utf-8")
    return FrontierReleaseExportArtifact(
        relative_path=relative_path,
        media_type="application/json",
        byte_count=len(content),
        content_address=hash_bytes(content, prefix="frontier-release-export"),
        content=content,
    )


def build_frontier_release_export(
    runtime: FrontierReleaseRuntimeReport,
) -> FrontierReleaseExportPacket:
    values = (
        ("domains.json", runtime.snapshot.domains),
        ("artifacts.json", runtime.snapshot.artifacts),
        ("dependencies.json", runtime.snapshot.dependencies),
        ("gates.json", runtime.snapshot.gates),
        ("boundary.json", runtime.boundary),
        ("indexes.json", runtime.indexes),
        ("reconciliation.json", runtime.reconciliation),
        ("summary.json", runtime.summary),
        ("certification.json", runtime.certification),
        ("observability.json", runtime.observability),
        ("graph.json", runtime.graph),
        ("plan.json", runtime.plan),
        ("runtime.json", runtime),
    )
    artifacts = tuple(_json_artifact(path, value) for path, value in values)
    accepted = bool(
        runtime.accepted
        and len(artifacts) == FRONTIER_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT
        and all(item.byte_count == len(item.content) for item in artifacts)
    )
    manifest_body = {
        "version": "frontier-release-export-v1",
        "bundle_id": runtime.snapshot.bundle_id,
        "artifact_count": len(artifacts),
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "accepted": accepted,
    }
    manifest = FrontierReleaseExportManifest(
        **manifest_body,
        content_address=hash_bytes(
            canonical_json(manifest_body).encode("utf-8"),
            prefix="frontier-release-export-manifest",
        ),
    )
    body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "artifacts": artifacts,
        "manifest": manifest,
        "accepted": manifest.accepted,
    }
    content_body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "manifest": manifest.to_dict(),
        "accepted": manifest.accepted,
    }
    return FrontierReleaseExportPacket(
        **body,
        content_address=hash_bytes(
            canonical_json(content_body).encode("utf-8"),
            prefix="frontier-release-export-packet",
        ),
    )


def write_frontier_release_export(
    packet: FrontierReleaseExportPacket,
    destination: str | Path,
) -> Path:
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        if not safe_relative_path(artifact.relative_path):
            raise ValueError(f"unsafe frontier release export path: {artifact.relative_path}")
        target = root / artifact.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.content)
    (root / "manifest.json").write_bytes(
        (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    )
    return root


def verify_frontier_release_export(
    packet: FrontierReleaseExportPacket,
    destination: str | Path,
) -> FrontierReleaseExportVerification:
    root = Path(destination)
    expected = {item.relative_path: item for item in packet.artifacts}
    actual = (
        {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if root.exists()
        else {}
    )
    missing = set(expected) - set(actual)
    manifest_path = root / "manifest.json"
    expected_manifest = (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    if not manifest_path.is_file():
        missing.add("manifest.json")
    unexpected = set(actual) - set(expected)
    changed = {
        path
        for path in set(expected) & set(actual)
        if actual[path].read_bytes() != expected[path].content
    }
    if manifest_path.is_file() and manifest_path.read_bytes() != expected_manifest:
        changed.add("manifest.json")
    body = {
        "bundle_id": packet.bundle_id,
        "checked_artifact_count": len(actual),
        "missing_paths": tuple(sorted(missing)),
        "changed_paths": tuple(sorted(changed)),
        "unexpected_paths": tuple(sorted(unexpected)),
        "accepted": not missing and not changed and not unexpected and len(actual) == len(expected),
    }
    return FrontierReleaseExportVerification(
        **body,
        content_address=hash_bytes(
            canonical_json(body).encode("utf-8"),
            prefix="frontier-release-export-verification",
        ),
    )


__all__ = [
    "build_frontier_release_export",
    "verify_frontier_release_export",
    "write_frontier_release_export",
]

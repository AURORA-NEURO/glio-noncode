"""Durable, independently verifiable service-release registry handoffs.

The service-release registry already exposes a useful in-memory snapshot and a
small exact-byte export.  This module adds the operational boundary needed by
offline consumers: stable artifact identity, a versioned manifest, atomic
persistence, fail-closed verification, bounded metadata queries, address-only
diffs, and deterministic replay receipts.  The handoff contains aggregate
service projections only; it never copies source case records or attribution
metadata.
"""

from __future__ import annotations

import json
import os
import tempfile
import csv
import io
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash
from .service_release_contracts import (
    SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT,
    SERVICE_RELEASE_HANDOFF_MAX_ARTIFACTS,
    SERVICE_RELEASE_HANDOFF_RESOURCE_NAMES,
    SERVICE_RELEASE_HANDOFF_SCHEMA_VERSION,
    SERVICE_RELEASE_HANDOFF_VERSION,
    ServiceReleaseHandoffArtifact,
    ServiceReleaseHandoffDiff,
    ServiceReleaseHandoffInspection,
    ServiceReleaseHandoffManifest,
    ServiceReleaseHandoffPacket,
    ServiceReleaseHandoffQueryResult,
    ServiceReleaseHandoffState,
    ServiceReleaseHandoffVerification,
    ServiceReleaseRuntimeReport,
)
from .service_release_export import build_service_release_export
from .service_release_support import (
    artifact_address,
    forbidden_keys,
    line_count,
    safe_relative_path,
    text_matches,
)
from .service_surface import ServiceSurfaceSnapshot

_MEDIA_TYPES = frozenset({"application/json", "text/csv", "text/markdown"})
def _json_bytes(value: Any) -> bytes:
    """Encode one public JSON projection with a terminal newline."""

    return (canonical_json(value) + "\n").encode("utf-8")


def _artifact_values(
    runtime: ServiceReleaseRuntimeReport,
    source_snapshot: ServiceSurfaceSnapshot | None = None,
) -> tuple[ServiceReleaseHandoffArtifact, ...]:
    """Convert the established export packet into addressed handoff artifacts."""

    export = build_service_release_export(runtime, source_snapshot)
    metadata_by_path = {item.relative_path: item for item in runtime.snapshot.artifacts}
    artifacts: list[ServiceReleaseHandoffArtifact] = []
    for item in export.artifacts:
        metadata = metadata_by_path.get(item.relative_path)
        if metadata is None:
            raise ValidationError(f"service-release handoff metadata is missing: {item.relative_path}")
        path = safe_relative_path(item.relative_path)
        if item.media_type not in _MEDIA_TYPES:
            raise ValidationError(f"unsupported service-release handoff media type: {item.media_type}")
        artifacts.append(
            ServiceReleaseHandoffArtifact(
                artifact_id=metadata.artifact_id,
                surface_id=metadata.surface_id,
                relative_path=path,
                media_type=item.media_type,
                source_address=metadata.source_address,
                byte_count=len(item.content),
                line_count=line_count(item.content),
                content_address=artifact_address(item.content),
                required=True,
                content=item.content,
            )
        )
    return tuple(artifacts)


def service_release_handoff_artifact_payloads(
    runtime: ServiceReleaseRuntimeReport,
    source_snapshot: ServiceSurfaceSnapshot | None = None,
) -> dict[str, bytes]:
    """Return exact artifact bytes keyed by the stable service artifact ID."""

    return {
        item.artifact_id: item.content
        for item in _artifact_values(runtime, source_snapshot)
    }


def _manifest_body(manifest: ServiceReleaseHandoffManifest) -> dict[str, Any]:
    """Return the manifest fields covered by its content address."""

    return {
        "version": manifest.version,
        "schema_version": manifest.schema_version,
        "bundle_id": manifest.bundle_id,
        "run_id": manifest.run_id,
        "artifact_count": manifest.artifact_count,
        "required_artifact_count": manifest.required_artifact_count,
        "artifacts": manifest.artifacts,
        "source_addresses": manifest.source_addresses,
        "accepted": manifest.accepted,
    }


def build_service_release_handoff(
    runtime: ServiceReleaseRuntimeReport,
    source_snapshot: ServiceSurfaceSnapshot | None = None,
) -> ServiceReleaseHandoffPacket:
    """Build the closed thirteen-artifact service-release handoff."""

    artifacts = _artifact_values(runtime, source_snapshot)
    if len(artifacts) != SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT:
        raise ValidationError("service-release handoff artifact denominator is not closed")
    if len(artifacts) > SERVICE_RELEASE_HANDOFF_MAX_ARTIFACTS:
        raise ValidationError("service-release handoff exceeds its maximum artifact budget")
    if len({item.artifact_id for item in artifacts}) != len(artifacts):
        raise ValidationError("service-release handoff artifact identifiers are not unique")
    if len({item.relative_path for item in artifacts}) != len(artifacts):
        raise ValidationError("service-release handoff artifact paths are not unique")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    source_addresses = (
        ("snapshot", runtime.snapshot.content_address),
        ("runtime", runtime.content_address),
        ("service", runtime.snapshot.service_address),
    )
    accepted = runtime.accepted and all(item.required for item in artifacts)
    manifest_body = {
        "version": SERVICE_RELEASE_HANDOFF_VERSION,
        "schema_version": SERVICE_RELEASE_HANDOFF_SCHEMA_VERSION,
        "bundle_id": runtime.snapshot.bundle_id,
        "run_id": runtime.run_id,
        "artifact_count": len(artifacts),
        "required_artifact_count": sum(item.required for item in artifacts),
        "artifacts": metadata,
        "source_addresses": source_addresses,
        "accepted": accepted,
    }
    manifest = ServiceReleaseHandoffManifest(
        **manifest_body,
        content_address=content_hash(
            manifest_body,
            prefix="service-release-handoff-manifest",
        ),
    )
    packet_body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "run_id": runtime.run_id,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": accepted,
    }
    return ServiceReleaseHandoffPacket(
        runtime.snapshot.bundle_id,
        runtime.run_id,
        artifacts,
        manifest,
        accepted,
        content_hash(packet_body, prefix="service-release-handoff"),
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write through a sibling temporary file and atomically replace the target."""

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


def write_service_release_handoff(
    packet: ServiceReleaseHandoffPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Persist a handoff without deleting an existing destination."""

    root = Path(destination)
    if root.is_symlink():
        raise ValidationError("service-release handoff destination cannot be a symlink")
    if root.exists() and not root.is_dir():
        raise ValidationError("service-release handoff destination is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    existing = tuple(path for path in root.rglob("*") if path.is_file() or path.is_symlink())
    if existing and not allow_existing:
        raise ValidationError("service-release handoff destination is not empty")
    for artifact in packet.artifacts:
        target = root / Path(*PurePosixPath(safe_relative_path(artifact.relative_path)).parts)
        _atomic_write(target, artifact.content)
    _atomic_write(root / "manifest.json", _json_bytes(packet.manifest.to_dict()))
    return root


def _empty_verification(
    directory: Path,
    state: ServiceReleaseHandoffState,
) -> ServiceReleaseHandoffVerification:
    """Return a stable failure when no manifest can be decoded."""

    body = {
        "directory": str(directory),
        "state": state,
        "bundle_id": "",
        "run_id": "",
        "checked_artifact_count": 0,
        "missing_paths": ("manifest.json",),
        "unexpected_paths": (),
        "duplicate_paths": (),
        "unsafe_paths": (),
        "tampered_paths": (),
        "boundary_violations": (),
        "manifest_drift": (),
        "accepted": False,
    }
    return ServiceReleaseHandoffVerification(
        **body,
        content_address=content_hash(body, prefix="service-release-handoff-verification"),
    )


def _read_manifest(
    directory: str | Path,
) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
    """Read and address-check a handoff manifest without reading artifacts."""

    root = Path(directory)
    if root.is_symlink():
        return root, {}, ("directory.symlink",)
    path = root / "manifest.json"
    if not path.is_file() or path.is_symlink():
        return root, {}, ("manifest.json",)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return root, {}, ("manifest.json",)
    if not isinstance(value, dict):
        return root, {}, ("manifest.json",)
    drift: list[str] = []
    expected_address = content_hash(
        {
            key: value.get(key)
            for key in (
                "version",
                "schema_version",
                "bundle_id",
                "run_id",
                "artifact_count",
                "required_artifact_count",
                "artifacts",
                "source_addresses",
                "accepted",
            )
        },
        prefix="service-release-handoff-manifest",
    )
    if value.get("content_address") != expected_address:
        drift.append("manifest.content_address")
    if value.get("version") != SERVICE_RELEASE_HANDOFF_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != SERVICE_RELEASE_HANDOFF_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    return root, value, tuple(drift)


def inspect_service_release_handoff(
    directory: str | Path,
) -> ServiceReleaseHandoffInspection:
    """Inspect manifest metadata without loading artifact bytes."""

    root, manifest, drift = _read_manifest(directory)
    if not manifest:
        body = {
            "directory": str(root),
            "state": ServiceReleaseHandoffState.MISSING,
            "bundle_id": "",
            "run_id": "",
            "artifact_count": 0,
            "required_artifact_count": 0,
            "artifact_ids": (),
            "accepted": False,
        }
        return ServiceReleaseHandoffInspection(
            **body,
            content_address=content_hash(body, prefix="service-release-handoff-inspection"),
        )
    artifacts = manifest.get("artifacts", ())
    artifact_ids = tuple(
        str(item.get("artifact_id", ""))
        for item in artifacts
        if isinstance(item, dict)
    ) if isinstance(artifacts, list) else ()
    accepted = bool(manifest.get("accepted")) and not drift
    body = {
        "directory": str(root),
        "state": ServiceReleaseHandoffState.INSPECTED,
        "bundle_id": str(manifest.get("bundle_id", "")),
        "run_id": str(manifest.get("run_id", "")),
        "artifact_count": int(manifest.get("artifact_count", 0)),
        "required_artifact_count": int(manifest.get("required_artifact_count", 0)),
        "artifact_ids": artifact_ids,
        "accepted": accepted,
    }
    return ServiceReleaseHandoffInspection(
        **body,
        content_address=content_hash(
            body | {"manifest_drift": drift},
            prefix="service-release-handoff-inspection",
        ),
    )


def _text_boundary(payload: bytes, media_type: str) -> tuple[str, ...]:
    """Check human-readable column names without rejecting domain vocabulary."""

    try:
        text = payload.decode("utf-8").casefold()
    except UnicodeDecodeError:
        return ("$invalid-utf8",)
    if media_type == "text/csv":
        rows = csv.reader(io.StringIO(text))
        headers = next(rows, ())
    else:
        headers = ()
        for line in text.splitlines():
            if line.startswith("|") and not line.replace("|", "").replace("-", "").strip():
                continue
            if line.startswith("|"):
                headers = tuple(part.strip() for part in line.strip("|").split("|"))
                break
    return tuple(f"$header:{item}" for item in forbidden_keys({header: None for header in headers}) if item)


def _listed_artifacts(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return well-typed manifest rows for verification and queries."""

    value = manifest.get("artifacts", ())
    return tuple(item for item in value if isinstance(item, dict)) if isinstance(value, list) else ()


def _path_has_symlink(root: Path, relative_path: str) -> bool:
    """Reject symlinked parents as well as symlinked artifact files."""

    current = root
    if current.is_symlink():
        return True
    for part in Path(relative_path).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def verify_service_release_handoff(
    directory: str | Path,
) -> ServiceReleaseHandoffVerification:
    """Verify manifest closure, exact bytes, paths, and public boundary."""

    root, manifest, manifest_drift = _read_manifest(directory)
    if not manifest:
        return _empty_verification(root, ServiceReleaseHandoffState.MISSING)
    missing: list[str] = []
    unexpected: list[str] = []
    duplicate: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    expected_paths: list[str] = []
    artifact_ids: list[str] = []
    listed = _listed_artifacts(manifest)
    if len(listed) != int(manifest.get("artifact_count", -1)):
        manifest_drift = (*manifest_drift, "manifest.artifact_count")
    if len(listed) != SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT:
        manifest_drift = (*manifest_drift, "manifest.closed_artifact_count")
    if len(listed) > SERVICE_RELEASE_HANDOFF_MAX_ARTIFACTS:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
    for item in listed:
        artifact_id = str(item.get("artifact_id", ""))
        path_text = str(item.get("relative_path", ""))
        if not artifact_id:
            manifest_drift = (*manifest_drift, "artifact.missing_id")
        if artifact_id in artifact_ids:
            duplicate.append(f"artifact_id:{artifact_id}")
        artifact_ids.append(artifact_id)
        media_type = str(item.get("media_type", ""))
        if media_type not in _MEDIA_TYPES:
            manifest_drift = (*manifest_drift, f"artifact.media_type:{artifact_id}")
        if not str(item.get("surface_id", "")) or not str(item.get("source_address", "")):
            manifest_drift = (*manifest_drift, f"artifact.metadata:{artifact_id}")
        try:
            path = safe_relative_path(path_text)
        except ValidationError:
            unsafe.append(path_text)
            continue
        if path in expected_paths:
            duplicate.append(path)
        expected_paths.append(path)
        target = root / Path(*PurePosixPath(path).parts)
        if _path_has_symlink(root, path):
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
        if len(payload) != int(item.get("byte_count", -1)):
            tampered.append(path)
        if artifact_address(payload) != item.get("content_address"):
            tampered.append(path)
        if line_count(payload) != int(item.get("line_count", -1)):
            tampered.append(path)
        if media_type == "application/json":
            try:
                boundary.extend(forbidden_keys(json.loads(payload.decode("utf-8"))))
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        elif media_type in {"text/csv", "text/markdown"}:
            boundary.extend(
                f"{path}:{value}"
                for value in _text_boundary(payload, media_type)
            )
    if len(artifact_ids) != len(set(artifact_ids)):
        manifest_drift = (*manifest_drift, "manifest.artifact_ids")
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    unexpected.extend(
        path
        for path in actual_paths
        if path not in sorted((*expected_paths, "manifest.json"))
    )
    required_count = sum(bool(item.get("required", False)) for item in listed)
    if required_count != int(manifest.get("required_artifact_count", -1)):
        manifest_drift = (*manifest_drift, "manifest.required_artifact_count")
    accepted = bool(manifest.get("accepted")) and not any(
        (missing, unexpected, duplicate, unsafe, tampered, boundary, manifest_drift)
    )
    body = {
        "directory": str(root),
        "state": ServiceReleaseHandoffState.READY if accepted else ServiceReleaseHandoffState.BLOCKED,
        "bundle_id": str(manifest.get("bundle_id", "")),
        "run_id": str(manifest.get("run_id", "")),
        "checked_artifact_count": len(listed),
        "missing_paths": tuple(sorted(set(missing))),
        "unexpected_paths": tuple(sorted(set(unexpected))),
        "duplicate_paths": tuple(sorted(set(duplicate))),
        "unsafe_paths": tuple(sorted(set(unsafe))),
        "tampered_paths": tuple(sorted(set(tampered))),
        "boundary_violations": tuple(sorted(set(boundary))),
        "manifest_drift": tuple(sorted(set(manifest_drift))),
        "accepted": accepted,
    }
    return ServiceReleaseHandoffVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="service-release-handoff-verification",
        ),
    )


def _manifest_items(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return deterministic artifact metadata rows."""

    return tuple(sorted(_listed_artifacts(manifest), key=lambda item: str(item.get("artifact_id", ""))))


def query_service_release_handoff(
    directory: str | Path,
    *,
    resource: str = "artifacts",
    artifact_id: str | None = None,
    surface_id: str | None = None,
    media_type: str | None = None,
    required_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ServiceReleaseHandoffQueryResult:
    """Query verified handoff metadata without rebuilding the registry."""

    if resource not in SERVICE_RELEASE_HANDOFF_RESOURCE_NAMES:
        raise ValidationError(f"unsupported service-release handoff resource: {resource}")
    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("service-release handoff pagination is outside its contract")
    root, manifest, _drift = _read_manifest(directory)
    verification = verify_service_release_handoff(root)
    if resource == "artifacts":
        rows: Iterable[dict[str, Any]] = _manifest_items(manifest)
        if artifact_id:
            rows = (item for item in rows if item.get("artifact_id") == artifact_id)
        if surface_id:
            rows = (item for item in rows if item.get("surface_id") == surface_id)
        if media_type:
            rows = (item for item in rows if item.get("media_type") == media_type)
        if required_only:
            rows = (item for item in rows if bool(item.get("required")))
        if text:
            rows = (item for item in rows if text_matches(item, text))
    elif resource == "manifest":
        rows = (manifest,)
    else:
        rows = ({
            "directory": str(root),
            "bundle_id": verification.bundle_id,
            "run_id": verification.run_id,
            "state": verification.state,
            "accepted": verification.accepted,
            "verification_address": verification.content_address,
        },)
    materialized = tuple(rows)
    page = materialized[offset : offset + limit]
    body = {
        "directory": str(root),
        "resource": resource,
        "total": len(materialized),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": verification.accepted,
    }
    return ServiceReleaseHandoffQueryResult(
        str(root),
        resource,
        len(materialized),
        offset,
        limit,
        page,
        verification.accepted,
        content_hash(body, prefix="service-release-handoff-query"),
    )


def diff_service_release_handoffs(
    left_directory: str | Path,
    right_directory: str | Path,
) -> ServiceReleaseHandoffDiff:
    """Compare two verified handoffs by artifact content address."""

    left_root, left_manifest, _left_drift = _read_manifest(left_directory)
    right_root, right_manifest, _right_drift = _read_manifest(right_directory)
    left_verification = verify_service_release_handoff(left_root)
    right_verification = verify_service_release_handoff(right_root)
    left_rows = {str(item.get("artifact_id")): item for item in _listed_artifacts(left_manifest)}
    right_rows = {str(item.get("artifact_id")): item for item in _listed_artifacts(right_manifest)}
    shared = sorted(set(left_rows) & set(right_rows))
    added = tuple(sorted(set(right_rows) - set(left_rows)))
    removed = tuple(sorted(set(left_rows) - set(right_rows)))
    changed = tuple(
        item
        for item in shared
        if left_rows[item].get("content_address") != right_rows[item].get("content_address")
    )
    unchanged = tuple(item for item in shared if item not in changed)
    left_address = str(left_manifest.get("content_address", ""))
    right_address = str(right_manifest.get("content_address", ""))
    body = {
        "left_directory": str(left_root),
        "right_directory": str(right_root),
        "left_manifest_address": left_address,
        "right_manifest_address": right_address,
        "added_artifact_ids": added,
        "removed_artifact_ids": removed,
        "changed_artifact_ids": changed,
        "unchanged_artifact_ids": unchanged,
        "identical": left_address == right_address,
        "accepted": left_verification.accepted and right_verification.accepted,
    }
    return ServiceReleaseHandoffDiff(
        **body,
        content_address=content_hash(body, prefix="service-release-handoff-diff"),
    )


def replay_service_release_handoff(directory: str | Path) -> dict[str, Any]:
    """Verify the same directory twice and return a deterministic receipt."""

    first = verify_service_release_handoff(directory)
    second = verify_service_release_handoff(directory)
    deterministic = first.content_address == second.content_address
    body = {
        "directory": str(directory),
        "first_address": first.content_address,
        "second_address": second.content_address,
        "deterministic": deterministic,
        "accepted": first.accepted and second.accepted and deterministic,
    }
    return body | {"content_address": content_hash(body, prefix="service-release-handoff-replay")}


def service_release_handoff_status(directory: str | Path) -> dict[str, Any]:
    """Return compact status without exposing artifact bytes."""

    verification = verify_service_release_handoff(directory)
    return {
        "directory": verification.directory,
        "bundle_id": verification.bundle_id,
        "run_id": verification.run_id,
        "state": verification.state,
        "accepted": verification.accepted,
        "checked_artifact_count": verification.checked_artifact_count,
        "missing_count": len(verification.missing_paths),
        "unexpected_count": len(verification.unexpected_paths),
        "tampered_count": len(verification.tampered_paths),
        "content_address": verification.content_address,
    }


__all__ = [
    "build_service_release_handoff",
    "diff_service_release_handoffs",
    "inspect_service_release_handoff",
    "query_service_release_handoff",
    "replay_service_release_handoff",
    "service_release_handoff_artifact_payloads",
    "service_release_handoff_status",
    "verify_service_release_handoff",
    "write_service_release_handoff",
]

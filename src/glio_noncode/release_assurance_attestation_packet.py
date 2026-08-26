"""Exact-byte portable packet for the final release attestation."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation import (
    release_assurance_attestation_json,
    release_assurance_attestation_schema,
)
from .release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_MAX_PACKET_ARTIFACTS,
    RELEASE_ASSURANCE_ATTESTATION_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_PACKET_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationOffline,
    ReleaseAssuranceAttestationPacket,
    ReleaseAssuranceAttestationPacketArtifact,
    ReleaseAssuranceAttestationPacketManifest,
    ReleaseAssuranceAttestationPacketVerification,
    ReleaseAssuranceAttestationRuntimeReport,
    ReleaseAssuranceAttestationRuntimeState,
)
from .release_assurance_attestation_runtime import release_assurance_attestation_runtime_json
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
) -> ReleaseAssuranceAttestationPacketArtifact:
    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("attestation packet artifact identity is required")
    if not isinstance(content, bytes):
        raise ValidationError("attestation packet artifact content must be bytes")
    return ReleaseAssuranceAttestationPacketArtifact(
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


def _payloads(
    runtime: ReleaseAssuranceAttestationRuntimeReport,
) -> tuple[tuple[str, str, str, str, bytes], ...]:
    attestation = runtime.attestation
    components_output = [
        (
            "component_id",
            "title",
            "state",
            "observed_count",
            "expected_count",
            "readiness_percent",
            "accepted",
            "source_address",
            "content_address",
        ),
        *[
            (
                item.component_id,
                item.title,
                item.state,
                item.observed_count,
                item.expected_count,
                item.readiness_percent,
                item.accepted,
                item.source_address,
                item.content_address,
            )
            for item in attestation.components
        ],
    ]
    checks_output = [
        (
            "check_id",
            "component_id",
            "category",
            "passed",
            "observed",
            "expected",
            "detail",
            "content_address",
        ),
        *[
            (
                item.check_id,
                item.component_id,
                item.category,
                item.passed,
                item.observed,
                item.expected,
                item.detail,
                item.content_address,
            )
            for item in attestation.checks
        ],
    ]
    import csv
    from io import StringIO

    component_buffer = StringIO()
    csv.writer(component_buffer, lineterminator="\n").writerows(components_output)
    check_buffer = StringIO()
    csv.writer(check_buffer, lineterminator="\n").writerows(checks_output)
    summary = {
        "attestation_id": attestation.attestation_id,
        "bundle_id": attestation.bundle_id,
        "run_id": attestation.run_id,
        "attestation_address": attestation.content_address,
        "runtime_address": runtime.content_address,
        "component_count": attestation.component_count,
        "check_count": attestation.check_count,
        "passed_check_count": attestation.passed_check_count,
        "overall_percent": attestation.overall_percent,
        "accepted": runtime.accepted,
    }
    return (
        (
            "attestation-json",
            "attestation/attestation.json",
            "application/json",
            "attestation",
            release_assurance_attestation_json(attestation).encode("utf-8"),
        ),
        (
            "runtime-json",
            "runtime/runtime.json",
            "application/json",
            "runtime",
            release_assurance_attestation_runtime_json(runtime).encode("utf-8"),
        ),
        (
            "components-csv",
            "attestation/components.csv",
            "text/csv",
            "components",
            component_buffer.getvalue().encode("utf-8"),
        ),
        (
            "checks-csv",
            "attestation/checks.csv",
            "text/csv",
            "checks",
            check_buffer.getvalue().encode("utf-8"),
        ),
        (
            "summary-json",
            "attestation/summary.json",
            "application/json",
            "summary",
            canonical_payload(summary),
        ),
        (
            "policy-json",
            "attestation/policy.json",
            "application/json",
            "policy",
            canonical_payload(attestation.policy.to_dict()),
        ),
        (
            "schema-json",
            "attestation/schema.json",
            "application/json",
            "schema",
            canonical_payload(release_assurance_attestation_schema()),
        ),
    )


def release_assurance_attestation_packet_artifact_payloads(
    runtime: ReleaseAssuranceAttestationRuntimeReport,
) -> dict[str, bytes]:
    """Return the exact bytes used by each packet payload artifact."""

    return {
        artifact_id: content for artifact_id, _path, _media, _role, content in _payloads(runtime)
    }


def _manifest_body(manifest: ReleaseAssuranceAttestationPacketManifest) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "schema_version": manifest.schema_version,
        "packet_id": manifest.packet_id,
        "bundle_id": manifest.bundle_id,
        "run_id": manifest.run_id,
        "artifact_count": manifest.artifact_count,
        "payload_artifact_count": manifest.payload_artifact_count,
        "artifacts": manifest.artifacts,
        "source_addresses": manifest.source_addresses,
        "accepted": manifest.accepted,
    }


def build_release_assurance_attestation_packet(
    runtime: ReleaseAssuranceAttestationRuntimeReport,
    *,
    packet_id: str = "glio-noncode-release-assurance-attestation-packet",
) -> ReleaseAssuranceAttestationPacket:
    """Build a closed seven-payload plus manifest packet."""

    values = _payloads(runtime)
    artifacts = tuple(
        _artifact(artifact_id, path, media, role, runtime.attestation.content_address, content)
        for artifact_id, path, media, role, content in values
    )
    if len(artifacts) != RELEASE_ASSURANCE_ATTESTATION_PACKET_PAYLOAD_COUNT:
        raise ValidationError("attestation packet payload denominator is not closed")
    if len(artifacts) > RELEASE_ASSURANCE_ATTESTATION_MAX_PACKET_ARTIFACTS:
        raise ValidationError("attestation packet exceeds its artifact limit")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    source_addresses = (
        ("attestation", runtime.attestation.content_address),
        ("runtime", runtime.content_address),
        ("replay", runtime.replay.content_address),
    )
    accepted = runtime.accepted and all(item.required for item in artifacts)
    manifest_body = {
        "version": RELEASE_ASSURANCE_ATTESTATION_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
        "packet_id": packet_id,
        "bundle_id": runtime.attestation.bundle_id,
        "run_id": runtime.run_id,
        "artifact_count": RELEASE_ASSURANCE_ATTESTATION_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "source_addresses": source_addresses,
        "accepted": accepted,
    }
    manifest = ReleaseAssuranceAttestationPacketManifest(
        **manifest_body,
        content_address=content_hash(
            manifest_body, prefix="release-assurance-attestation-manifest"
        ),
    )
    body = {
        "packet_id": packet_id,
        "bundle_id": runtime.attestation.bundle_id,
        "run_id": runtime.run_id,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationPacket(
        packet_id,
        runtime.attestation.bundle_id,
        runtime.run_id,
        artifacts,
        manifest,
        accepted,
        content_hash(body, prefix="release-assurance-attestation-packet"),
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


def write_release_assurance_attestation_packet(
    packet: ReleaseAssuranceAttestationPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write exact bytes with atomic replacement and explicit overwrite opt-in."""

    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("attestation packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("attestation packet destination is not empty")
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
            "bundle_id",
            "run_id",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "source_addresses",
            "accepted",
        )
    }
    drift = []
    if value.get("content_address") != content_hash(
        body, prefix="release-assurance-attestation-manifest"
    ):
        drift.append("manifest.content_address")
    if value.get("version") != RELEASE_ASSURANCE_ATTESTATION_PACKET_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    return root, value, tuple(drift)


def _empty_verification(root: Path) -> ReleaseAssuranceAttestationPacketVerification:
    body = {
        "directory": str(root),
        "state": ReleaseAssuranceAttestationRuntimeState.BLOCKED,
        "packet_id": "",
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
    return ReleaseAssuranceAttestationPacketVerification(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-verification"),
    )


def _listed(manifest: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = manifest.get("artifacts", ())
    return tuple(item for item in rows if isinstance(item, dict)) if isinstance(rows, list) else ()


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


def verify_release_assurance_attestation_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationPacketVerification:
    """Verify exact paths, bytes, manifest closure, and public metadata."""

    root, manifest, manifest_drift = _read_manifest(directory)
    if not manifest:
        return _empty_verification(root)
    missing: list[str] = []
    unexpected: list[str] = []
    duplicate: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    expected_paths: list[str] = []
    artifact_ids: list[str] = []
    listed = _listed(manifest)
    if len(listed) != int(manifest.get("payload_artifact_count", -1)):
        manifest_drift = (*manifest_drift, "manifest.payload_artifact_count")
    if int(manifest.get("artifact_count", -1)) != len(listed) + 1:
        manifest_drift = (*manifest_drift, "manifest.artifact_count")
    if len(listed) > RELEASE_ASSURANCE_ATTESTATION_MAX_PACKET_ARTIFACTS:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
    for item in listed:
        artifact_id = str(item.get("artifact_id", ""))
        path_text = str(item.get("relative_path", ""))
        if artifact_id in artifact_ids:
            duplicate.append(f"artifact_id:{artifact_id}")
        artifact_ids.append(artifact_id)
        try:
            path = safe_relative_path(path_text)
        except ValidationError:
            unsafe.append(path_text)
            continue
        if path in expected_paths:
            duplicate.append(path)
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
                boundary.extend(forbidden_keys(json.loads(payload.decode("utf-8"))))
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
        and len(listed) == RELEASE_ASSURANCE_ATTESTATION_PACKET_PAYLOAD_COUNT
        and not any((missing, unexpected, duplicate, unsafe, tampered, boundary, manifest_drift))
    )
    body = {
        "directory": str(root),
        "state": ReleaseAssuranceAttestationRuntimeState.READY
        if accepted
        else ReleaseAssuranceAttestationRuntimeState.BLOCKED,
        "packet_id": str(manifest.get("packet_id", "")),
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
    return ReleaseAssuranceAttestationPacketVerification(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-verification"),
    )


def load_release_assurance_attestation_packet(
    directory: str | Path,
) -> ReleaseAssuranceAttestationOffline:
    """Hydrate the typed attestation only after offline packet verification."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_release_assurance_attestation_packet(root)
    if not verification.accepted:
        raise ValidationError("attestation packet is not accepted")
    path = root / "attestation" / "attestation.json"
    try:
        attestation = ReleaseAssuranceAttestation.from_mapping(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("attestation packet attestation payload is invalid") from exc
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "attestation": attestation,
        "manifest": manifest,
        "verification": verification,
    }
    return ReleaseAssuranceAttestationOffline(
        body["packet_id"],
        attestation,
        manifest,
        verification,
        content_hash(body, prefix="release-assurance-attestation-offline"),
    )


def release_assurance_attestation_packet_schema() -> dict[str, Any]:
    """Describe the packet closure and artifact layout."""

    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_PACKET_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION,
        "payload_artifact_count": RELEASE_ASSURANCE_ATTESTATION_PACKET_PAYLOAD_COUNT,
        "artifact_count_including_manifest": RELEASE_ASSURANCE_ATTESTATION_PACKET_ARTIFACT_COUNT,
        "required_paths": [
            "attestation/attestation.json",
            "runtime/runtime.json",
            "attestation/components.csv",
            "attestation/checks.csv",
            "attestation/summary.json",
            "attestation/policy.json",
            "attestation/schema.json",
            "manifest.json",
        ],
        "exact_bytes": True,
        "atomic_write": True,
        "offline_hydration": True,
        "public_boundary": True,
    }


def release_assurance_attestation_packet_capabilities() -> dict[str, Any]:
    """Return packet operations and safety guarantees."""

    return {
        "version": "release-assurance-attestation-packet-capabilities-v1",
        "build": True,
        "write": True,
        "verify": True,
        "load": True,
        "exact_byte_hashes": True,
        "manifest_closure": True,
        "symlink_rejection": True,
        "tamper_detection": True,
        "unexpected_file_detection": True,
        "strict_overwrite_opt_in": True,
        "source_payloads": False,
        "workflow_execution": False,
        "clinical_authorization": False,
        "public_boundary": True,
    }


__all__ = [
    "build_release_assurance_attestation_packet",
    "load_release_assurance_attestation_packet",
    "release_assurance_attestation_packet_artifact_payloads",
    "release_assurance_attestation_packet_capabilities",
    "release_assurance_attestation_packet_schema",
    "verify_release_assurance_attestation_packet",
    "write_release_assurance_attestation_packet",
]

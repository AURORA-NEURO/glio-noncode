"""Portable exact-byte handoffs for storage maintenance plans.

The packet is intentionally small and fixed. It carries a strict plan, an
action ledger, aggregate summary, schema, and capability declaration, followed
by one manifest. Writers use atomic sibling replacement. Verifiers inspect
every listed byte and path, reject unsafe or unexpected entries, rehydrate the
plan contract, and scan JSON payloads for prohibited public metadata before an
offline consumer can trust the handoff.
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
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
)
from .serialization import canonical_json, content_hash
from .storage_maintenance import (
    storage_maintenance_capabilities,
    storage_maintenance_csv,
    storage_maintenance_json,
    storage_maintenance_schema,
)
from .storage_maintenance_contracts import StorageMaintenancePlan
from .storage_maintenance_observability import (
    StorageMaintenanceObservability,
    build_storage_maintenance_observability,
    storage_maintenance_observability_json,
)
from .storage_maintenance_packet_contracts import (
    STORAGE_MAINTENANCE_PACKET_ARTIFACT_COUNT,
    STORAGE_MAINTENANCE_PACKET_BOUNDARY,
    STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS,
    STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT,
    STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS,
    STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION,
    STORAGE_MAINTENANCE_PACKET_VERSION,
    StorageMaintenancePacket,
    StorageMaintenancePacketArtifact,
    StorageMaintenancePacketManifest,
    StorageMaintenancePacketOffline,
    StorageMaintenancePacketVerification,
)
from .storage_maintenance_review import (
    StorageMaintenanceReviewQueue,
    build_storage_maintenance_review_queue,
    storage_maintenance_review_json,
)


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    role: str,
    source_address: str,
    content: bytes,
) -> StorageMaintenancePacketArtifact:
    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("maintenance packet artifact metadata is incomplete")
    if not isinstance(content, bytes):
        raise ValidationError("maintenance packet artifact content must be bytes")
    return StorageMaintenancePacketArtifact(
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


def _summary(plan: StorageMaintenancePlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "audit_address": plan.audit_address,
        "state": plan.state.value,
        "object_count": plan.object_count,
        "orphan_count": plan.orphan_count,
        "missing_count": plan.missing_count,
        "invalid_count": plan.invalid_count,
        "unexpected_count": plan.unexpected_count,
        "run_count": plan.run_count,
        "batch_count": plan.batch_count,
        "action_count": plan.action_count,
        "critical_action_count": plan.critical_action_count,
        "reversible_action_count": plan.reversible_action_count,
        "requires_review": plan.requires_review,
        "audit_accepted": plan.audit_accepted,
        "safe_to_apply": plan.safe_to_apply,
        "accepted": plan.accepted,
    }


def _payloads(plan: StorageMaintenancePlan) -> tuple[tuple[str, str, str, str, bytes], ...]:
    observability = build_storage_maintenance_observability(plan)
    review_queue = build_storage_maintenance_review_queue(plan)
    return (
        (
            "plan-json",
            "maintenance/plan.json",
            "application/json",
            "plan",
            (storage_maintenance_json(plan) + "\n").encode("utf-8"),
        ),
        (
            "actions-csv",
            "maintenance/actions.csv",
            "text/csv",
            "actions",
            storage_maintenance_csv(plan).encode("utf-8"),
        ),
        (
            "summary-json",
            "maintenance/summary.json",
            "application/json",
            "summary",
            canonical_payload(_summary(plan)),
        ),
        (
            "schema-json",
            "maintenance/schema.json",
            "application/json",
            "schema",
            canonical_payload(storage_maintenance_schema()),
        ),
        (
            "capabilities-json",
            "maintenance/capabilities.json",
            "application/json",
            "capabilities",
            canonical_payload(storage_maintenance_capabilities()),
        ),
        (
            "observability-json",
            "maintenance/observability.json",
            "application/json",
            "observability",
            (storage_maintenance_observability_json(observability) + "\n").encode("utf-8"),
        ),
        (
            "review-queue-json",
            "maintenance/review-queue.json",
            "application/json",
            "review",
            (storage_maintenance_review_json(review_queue) + "\n").encode("utf-8"),
        ),
    )


def storage_maintenance_packet_artifact_payloads(
    plan: StorageMaintenancePlan,
) -> dict[str, bytes]:
    """Return the exact fixed payload bytes keyed by artifact ID."""

    return {artifact_id: content for artifact_id, _path, _media, _role, content in _payloads(plan)}


def _manifest_body(manifest: StorageMaintenancePacketManifest) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "schema_version": manifest.schema_version,
        "packet_id": manifest.packet_id,
        "plan_id": manifest.plan_id,
        "plan_address": manifest.plan_address,
        "artifact_count": manifest.artifact_count,
        "payload_artifact_count": manifest.payload_artifact_count,
        "artifacts": manifest.artifacts,
        "accepted": manifest.accepted,
    }


def build_storage_maintenance_packet(
    plan: StorageMaintenancePlan,
    *,
    packet_id: str = "glio-noncode-storage-maintenance-packet",
) -> StorageMaintenancePacket:
    """Build the fixed plan packet without copying source object payloads."""

    if not isinstance(plan, StorageMaintenancePlan):
        raise ValidationError("storage maintenance packet requires a typed plan")
    if not packet_id.strip():
        raise ValidationError("storage maintenance packet ID must not be empty")
    values = _payloads(plan)
    if len(values) != STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT:
        raise ValidationError("storage maintenance packet payload denominator is not closed")
    artifacts = tuple(
        _artifact(artifact_id, path, media_type, role, plan.content_address, content)
        for artifact_id, path, media_type, role, content in values
    )
    if tuple(item.artifact_id for item in artifacts) != STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS:
        raise ValidationError("storage maintenance packet payload IDs are not closed")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    manifest_body = {
        "version": STORAGE_MAINTENANCE_PACKET_VERSION,
        "schema_version": STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "artifact_count": STORAGE_MAINTENANCE_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "accepted": plan.accepted,
    }
    manifest = StorageMaintenancePacketManifest(
        **manifest_body,
        content_address=content_hash(
            manifest_body,
            prefix="storage-maintenance-packet-manifest",
        ),
    )
    body = {
        "packet_id": packet_id,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": plan.accepted,
    }
    return StorageMaintenancePacket(
        packet_id=packet_id,
        plan_id=plan.plan_id,
        plan_address=plan.content_address,
        artifacts=artifacts,
        manifest=manifest,
        accepted=plan.accepted,
        content_address=content_hash(body, prefix="storage-maintenance-packet"),
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


def write_storage_maintenance_packet(
    packet: StorageMaintenancePacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write the fixed payload set and manifest with atomic file replacement."""

    if not isinstance(packet, StorageMaintenancePacket):
        raise ValidationError("storage maintenance packet writer requires a typed packet")
    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("storage maintenance packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("storage maintenance packet destination is not empty")
    for artifact in packet.artifacts:
        _atomic_write(root / safe_relative_path(artifact.relative_path), artifact.content)
    _atomic_write(
        root / "manifest.json",
        (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8"),
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
            "plan_id",
            "plan_address",
            "artifact_count",
            "payload_artifact_count",
            "artifacts",
            "accepted",
        )
    }
    drift: list[str] = []
    if value.get("content_address") != content_hash(
        body,
        prefix="storage-maintenance-packet-manifest",
    ):
        drift.append("manifest.content_address")
    if value.get("version") != STORAGE_MAINTENANCE_PACKET_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    try:
        StorageMaintenancePacketManifest.from_mapping(value)
    except ValidationError:
        drift.append("manifest.contract")
    return root, value, tuple(drift)


def _empty_verification(root: Path) -> StorageMaintenancePacketVerification:
    body = {
        "directory": str(root),
        "packet_id": "",
        "plan_id": "",
        "plan_address": "",
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
    return StorageMaintenancePacketVerification(
        **body,
        content_address=content_hash(
            body,
            prefix="storage-maintenance-packet-verification",
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


def verify_storage_maintenance_packet(
    directory: str | Path,
) -> StorageMaintenancePacketVerification:
    """Verify exact bytes, fixed paths, plan identity, and public boundaries."""

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
    if len(listed) != payload_count:
        manifest_drift = (*manifest_drift, "manifest.payload_artifact_count")
    if artifact_count != len(listed) + 1:
        manifest_drift = (*manifest_drift, "manifest.artifact_count")
    if len(listed) != STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT:
        manifest_drift = (*manifest_drift, "manifest.payload_denominator")
    if len(listed) > STORAGE_MAINTENANCE_PACKET_MAX_ARTIFACTS:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
    plan_payload: Mapping[str, Any] | None = None
    observability_payload: Mapping[str, Any] | None = None
    review_payload: Mapping[str, Any] | None = None
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
                if artifact_id == "plan-json" and isinstance(decoded, Mapping):
                    plan_payload = decoded
                if artifact_id == "observability-json" and isinstance(decoded, Mapping):
                    observability_payload = decoded
                if artifact_id == "review-queue-json" and isinstance(decoded, Mapping):
                    review_payload = decoded
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        else:
            boundary.extend(f"{path}:{value}" for value in _text_boundary(payload))
    if tuple(artifact_ids) != STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS:
        manifest_drift = (*manifest_drift, "manifest.payload_ids")
    plan_ok = False
    if plan_payload is not None:
        try:
            plan = StorageMaintenancePlan.from_mapping(plan_payload)
            plan_ok = (
                plan.plan_id == str(manifest.get("plan_id", ""))
                and plan.content_address == str(manifest.get("plan_address", ""))
                and plan.accepted == bool(manifest.get("accepted", False))
            )
            if not plan_ok:
                manifest_drift = (*manifest_drift, "manifest.plan_identity")
        except ValidationError:
            tampered.append("maintenance/plan.json")
    if observability_payload is not None:
        try:
            observability = StorageMaintenanceObservability.from_mapping(observability_payload)
            if observability.plan_address != str(manifest.get("plan_address", "")):
                manifest_drift = (*manifest_drift, "manifest.observability_identity")
        except ValidationError:
            tampered.append("maintenance/observability.json")
    if review_payload is not None:
        try:
            review_queue = StorageMaintenanceReviewQueue.from_mapping(review_payload)
            if review_queue.plan_address != str(manifest.get("plan_address", "")):
                manifest_drift = (*manifest_drift, "manifest.review_identity")
        except ValidationError:
            tampered.append("maintenance/review-queue.json")
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
        and str(manifest.get("plan_id", ""))
        and str(manifest.get("plan_address", ""))
        and len(listed) == STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT
        and tuple(artifact_ids) == STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS
        and plan_ok
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
        "plan_id": str(manifest.get("plan_id", "")),
        "plan_address": str(manifest.get("plan_address", "")),
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
    return StorageMaintenancePacketVerification(
        **body,
        content_address=content_hash(body, prefix="storage-maintenance-packet-verification"),
    )


def load_storage_maintenance_packet(
    directory: str | Path,
) -> StorageMaintenancePacketOffline:
    """Hydrate the plan only after exact-byte verification succeeds."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_storage_maintenance_packet(root)
    if not verification.accepted:
        raise ValidationError("storage maintenance packet is not accepted")
    try:
        payload = json.loads((root / "maintenance" / "plan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("storage maintenance packet plan payload is not valid JSON") from exc
    plan = StorageMaintenancePlan.from_mapping(payload)
    if plan.plan_id != manifest.get("plan_id") or plan.content_address != manifest.get(
        "plan_address"
    ):
        raise ValidationError("storage maintenance packet plan identity does not reconcile")
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "plan": plan.to_dict(),
        "manifest": manifest,
        "verification": verification.to_dict(),
    }
    return StorageMaintenancePacketOffline(
        packet_id=str(manifest.get("packet_id", "")),
        plan=plan,
        manifest=manifest,
        verification=verification,
        content_address=content_hash(body, prefix="storage-maintenance-packet-offline"),
    )


def storage_maintenance_packet_json(
    packet: StorageMaintenancePacket,
    *,
    include_content: bool = False,
) -> str:
    """Serialize packet metadata, optionally including UTF-8 payload text."""

    if not isinstance(packet, StorageMaintenancePacket):
        raise ValidationError("storage maintenance packet JSON requires a typed packet")
    return canonical_json(packet.to_dict(include_content=include_content))


def storage_maintenance_packet_capabilities() -> dict[str, Any]:
    """Describe the portable maintenance packet boundary."""

    return {
        "version": STORAGE_MAINTENANCE_PACKET_VERSION,
        "schema_version": STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION,
        "boundary": STORAGE_MAINTENANCE_PACKET_BOUNDARY,
        "maintenance_boundary": "public_storage_maintenance",
        "fixed_payload_count": True,
        "manifest_address": True,
        "atomic_write": True,
        "exact_byte_verification": True,
        "safe_path_verification": True,
        "symlink_rejection": True,
        "duplicate_path_detection": True,
        "unexpected_file_detection": True,
        "tamper_detection": True,
        "plan_identity_verification": True,
        "boundary_scan": True,
        "offline_hydration": True,
        "source_payloads": False,
        "timestamp_free": True,
        "payload_ids": STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS,
        "payload_count": STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT,
        "artifact_count": STORAGE_MAINTENANCE_PACKET_ARTIFACT_COUNT,
    }


def storage_maintenance_packet_schema() -> dict[str, Any]:
    """Return the closed public packet schema and verifier guarantees."""

    return {
        "version": STORAGE_MAINTENANCE_PACKET_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_MAINTENANCE_PACKET_BOUNDARY,
        "required": (
            "packet_id",
            "plan_id",
            "plan_address",
            "artifacts",
            "manifest",
            "accepted",
            "content_address",
        ),
        "payload_count": STORAGE_MAINTENANCE_PACKET_PAYLOAD_COUNT,
        "artifact_count": STORAGE_MAINTENANCE_PACKET_ARTIFACT_COUNT,
        "payload_ids": STORAGE_MAINTENANCE_PACKET_PAYLOAD_IDS,
        "artifact_roles": (
            "plan",
            "actions",
            "summary",
            "schema",
            "capabilities",
            "observability",
            "review",
        ),
        "manifest": {
            "type": "object",
            "required": (
                "version",
                "schema_version",
                "packet_id",
                "plan_id",
                "plan_address",
                "artifact_count",
                "payload_artifact_count",
                "artifacts",
                "accepted",
                "content_address",
            ),
        },
        "verification": {
            "exact_bytes": True,
            "content_addresses": True,
            "plan_identity": True,
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
    if name.startswith("build_storage_maintenance_packet")
    or name.startswith("load_storage_maintenance_packet")
    or name.startswith("storage_maintenance_packet")
    or name.startswith("verify_storage_maintenance_packet")
    or name.startswith("write_storage_maintenance_packet")
    or name.startswith("StorageMaintenancePacket")
]

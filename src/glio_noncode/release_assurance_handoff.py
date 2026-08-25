"""Durable, verifiable, and queryable release-assurance handoffs.

The in-memory release-assurance runtime proves the source planes. This module
turns that proof into a portable directory that can be copied, inspected,
queried, compared, and verified without rebuilding the source checkout. The
handoff contains aggregate projections and exact bytes only; it never stores a
case record or a private source payload.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_catalog import build_release_assurance_catalog
from .release_assurance_checkpoint import build_release_assurance_checkpoint
from .release_assurance_compliance import audit_release_assurance_compliance
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_HANDOFF_MAX_ARTIFACTS,
    RELEASE_ASSURANCE_HANDOFF_RESOURCE_NAMES,
    RELEASE_ASSURANCE_HANDOFF_SCHEMA_VERSION,
    RELEASE_ASSURANCE_HANDOFF_VERSION,
    ReleaseAssuranceHandoffArtifact,
    ReleaseAssuranceHandoffDiff,
    ReleaseAssuranceHandoffInspection,
    ReleaseAssuranceHandoffManifest,
    ReleaseAssuranceHandoffPacket,
    ReleaseAssuranceHandoffQueryResult,
    ReleaseAssuranceHandoffState,
    ReleaseAssuranceHandoffVerification,
    ReleaseAssuranceRuntimeReport,
)
from .release_assurance_history import build_release_assurance_history
from .release_assurance_operations import build_release_assurance_operations
from .release_assurance_performance import audit_release_assurance_performance
from .release_assurance_reconciliation import reconcile_release_assurance
from .release_assurance_reports import render_release_assurance_report_markdown
from .release_assurance_review import build_release_assurance_review_queue
from .release_assurance_schema import release_assurance_schema
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    csv_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
    text_matches,
)
from .release_assurance_summary import release_assurance_status
from .release_assurance_thresholds import evaluate_release_assurance_thresholds
from .serialization import canonical_json, content_hash

_TEXT_PRIVATE_TOKENS = (
    "agent",
    "assistant",
    "author",
    "email",
    "language",
    "model",
    "patient",
    "subject",
    "participant",
    "individual",
    "phone",
    "user",
)


def _json_bytes(value: Any) -> bytes:
    """Encode one public JSON projection with a terminal newline."""

    return canonical_payload(value)


def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode one public CSV projection using shared boundary rules."""

    return csv_payload(rows)


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    role: str,
    source_address: str,
    payload: bytes,
    *,
    required: bool = True,
) -> ReleaseAssuranceHandoffArtifact:
    """Create one addressable artifact after validating its path and bytes."""

    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("handoff artifact identity, role, and source are required")
    if not isinstance(payload, bytes):
        raise ValidationError("handoff artifact payload must be bytes")
    return ReleaseAssuranceHandoffArtifact(
        artifact_id=artifact_id,
        relative_path=path,
        media_type=media_type,
        role=role,
        source_address=source_address,
        byte_count=len(payload),
        line_count=line_count(payload),
        content_address=artifact_address(payload),
        required=required,
        content=payload,
    )


def _artifact_values(runtime: ReleaseAssuranceRuntimeReport) -> tuple[tuple[str, str, str, str, str, bytes], ...]:
    """Materialize every handoff artifact from one already-verified runtime."""

    snapshot = runtime.snapshot
    reconciliation = reconcile_release_assurance(snapshot)
    catalog = build_release_assurance_catalog(snapshot, runtime)
    compliance = audit_release_assurance_compliance(snapshot, runtime=runtime)
    performance = audit_release_assurance_performance(snapshot, runtime=runtime)
    operations = build_release_assurance_operations(snapshot, runtime)
    checkpoint = build_release_assurance_checkpoint(runtime)
    review = build_release_assurance_review_queue(runtime)
    history = build_release_assurance_history(runtime, review_queue=review)
    thresholds = evaluate_release_assurance_thresholds(snapshot, runtime=runtime)
    return (
        ("snapshot-json", "assurance/snapshot.json", "application/json", "source-snapshot", snapshot.content_address, _json_bytes(snapshot.to_dict())),
        ("runtime-json", "runtime/release-assurance.json", "application/json", "runtime", runtime.content_address, _json_bytes(runtime.to_dict())),
        ("status-json", "runtime/status.json", "application/json", "status", snapshot.content_address, _json_bytes(release_assurance_status(snapshot))),
        ("summary-json", "assurance/summary.json", "application/json", "summary", runtime.summary.content_address, _json_bytes(runtime.summary.to_dict())),
        ("reconciliation-json", "assurance/reconciliation.json", "application/json", "reconciliation", reconciliation.content_address, _json_bytes(reconciliation.to_dict())),
        ("catalog-json", "assurance/catalog.json", "application/json", "catalog", catalog.content_address, _json_bytes(catalog.to_dict())),
        ("compliance-json", "assurance/compliance.json", "application/json", "compliance", compliance.content_address, _json_bytes(compliance.to_dict())),
        ("performance-json", "assurance/performance.json", "application/json", "performance", performance.content_address, _json_bytes(performance.to_dict())),
        ("operations-json", "assurance/operations.json", "application/json", "operations", operations.content_address, _json_bytes(operations.to_dict())),
        ("checkpoint-json", "assurance/checkpoint.json", "application/json", "checkpoint", checkpoint.content_address, _json_bytes(checkpoint.to_dict())),
        ("review-json", "assurance/review.json", "application/json", "review", review.content_address, _json_bytes(review.to_dict())),
        ("history-json", "assurance/history.json", "application/json", "history", history.content_address, _json_bytes(history.to_dict())),
        ("thresholds-json", "assurance/thresholds.json", "application/json", "thresholds", thresholds.content_address, _json_bytes(thresholds.to_dict())),
        ("observability-json", "assurance/observability.json", "application/json", "observability", runtime.observability.content_address, _json_bytes(runtime.observability.to_dict())),
        ("plan-json", "assurance/plan.json", "application/json", "plan", runtime.plan.content_address, _json_bytes(runtime.plan.to_dict())),
        ("views-json", "assurance/views.json", "application/json", "views", runtime.views.content_address, _json_bytes(runtime.views.to_dict())),
        ("schema-json", "assurance/schema.json", "application/json", "schema", content_hash(release_assurance_schema(), prefix="release-assurance-schema"), _json_bytes(release_assurance_schema())),
        ("report-markdown", "reports/release-assurance.md", "text/markdown", "report", runtime.content_address, render_release_assurance_report_markdown(runtime)),
        ("history-csv", "reports/history.csv", "text/csv", "history-table", history.content_address, _csv_bytes(item.to_dict() for item in history.events)),
    )


def release_assurance_handoff_artifact_payloads(
    runtime: ReleaseAssuranceRuntimeReport,
) -> dict[str, bytes]:
    """Return exact payload bytes keyed by stable artifact identifier."""

    return {
        artifact_id: payload
        for artifact_id, _path, _media, _role, _source, payload in _artifact_values(runtime)
    }


def _manifest_body(manifest: ReleaseAssuranceHandoffManifest) -> dict[str, Any]:
    """Return the manifest fields used to recompute its content address."""

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


def build_release_assurance_handoff(
    runtime: ReleaseAssuranceRuntimeReport,
) -> ReleaseAssuranceHandoffPacket:
    """Assemble a complete 19-artifact durable handoff."""

    values = _artifact_values(runtime)
    artifacts = tuple(
        _artifact(artifact_id, path, media_type, role, source, payload)
        for artifact_id, path, media_type, role, source, payload in values
    )
    if len(artifacts) != RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT:
        raise ValidationError("release-assurance handoff artifact denominator is not closed")
    if len(artifacts) > RELEASE_ASSURANCE_HANDOFF_MAX_ARTIFACTS:
        raise ValidationError("release-assurance handoff exceeds its maximum artifact budget")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    source_addresses = tuple(
        (name, address)
        for name, address in (
            ("snapshot", runtime.snapshot.content_address),
            ("runtime", runtime.content_address),
            ("summary", runtime.summary.content_address),
            ("observability", runtime.observability.content_address),
            ("graph", runtime.graph.content_address),
            ("plan", runtime.plan.content_address),
            ("views", runtime.views.content_address),
        )
    )
    accepted = runtime.accepted and all(item.required for item in artifacts)
    manifest_body = {
        "version": RELEASE_ASSURANCE_HANDOFF_VERSION,
        "schema_version": RELEASE_ASSURANCE_HANDOFF_SCHEMA_VERSION,
        "bundle_id": runtime.snapshot.bundle_id,
        "run_id": runtime.run_id,
        "artifact_count": len(artifacts),
        "required_artifact_count": sum(item.required for item in artifacts),
        "artifacts": metadata,
        "source_addresses": source_addresses,
        "accepted": accepted,
    }
    manifest = ReleaseAssuranceHandoffManifest(
        **manifest_body,
        content_address=content_hash(manifest_body, prefix="release-assurance-handoff-manifest"),
    )
    packet_body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "run_id": runtime.run_id,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": accepted,
    }
    return ReleaseAssuranceHandoffPacket(
        runtime.snapshot.bundle_id,
        runtime.run_id,
        artifacts,
        manifest,
        accepted,
        content_hash(packet_body, prefix="release-assurance-handoff"),
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write bytes through a sibling temporary file and atomic replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


def write_release_assurance_handoff(
    packet: ReleaseAssuranceHandoffPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Persist a packet without silently deleting an existing handoff."""

    root = Path(destination)
    if root.exists() and not root.is_dir():
        raise ValidationError("handoff destination is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    existing_files = tuple(path for path in root.rglob("*") if path.is_file())
    if existing_files and not allow_existing:
        raise ValidationError("handoff destination is not empty")
    for artifact in packet.artifacts:
        target = root / safe_relative_path(artifact.relative_path)
        _atomic_write(target, artifact.content)
    manifest_payload = (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    _atomic_write(root / "manifest.json", manifest_payload)
    return root


def _empty_verification(directory: Path, state: ReleaseAssuranceHandoffState) -> ReleaseAssuranceHandoffVerification:
    """Create a stable failed result before a manifest can be decoded."""

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
    return ReleaseAssuranceHandoffVerification(
        **body,
        content_address=content_hash(body, prefix="release-assurance-handoff-verification"),
    )


def _read_manifest(directory: str | Path) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
    """Read a manifest and return parse/drift diagnostics."""

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
    drift: list[str] = []
    expected_address = content_hash(
        {key: value.get(key) for key in (
            "version", "schema_version", "bundle_id", "run_id", "artifact_count",
            "required_artifact_count", "artifacts", "source_addresses", "accepted",
        )},
        prefix="release-assurance-handoff-manifest",
    )
    if value.get("content_address") != expected_address:
        drift.append("manifest.content_address")
    if value.get("version") != RELEASE_ASSURANCE_HANDOFF_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != RELEASE_ASSURANCE_HANDOFF_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    return root, value, tuple(drift)


def inspect_release_assurance_handoff(
    directory: str | Path,
) -> ReleaseAssuranceHandoffInspection:
    """Inspect only manifest metadata without reading artifact bytes."""

    root, manifest, drift = _read_manifest(directory)
    if not manifest:
        body = {
            "directory": str(root),
            "state": ReleaseAssuranceHandoffState.MISSING,
            "bundle_id": "",
            "run_id": "",
            "artifact_count": 0,
            "required_artifact_count": 0,
            "artifact_ids": (),
            "accepted": False,
        }
        return ReleaseAssuranceHandoffInspection(
            **body,
            content_address=content_hash(body, prefix="release-assurance-handoff-inspection"),
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
        "state": ReleaseAssuranceHandoffState.INSPECTED,
        "bundle_id": str(manifest.get("bundle_id", "")),
        "run_id": str(manifest.get("run_id", "")),
        "artifact_count": int(manifest.get("artifact_count", 0)),
        "required_artifact_count": int(manifest.get("required_artifact_count", 0)),
        "artifact_ids": artifact_ids,
        "accepted": accepted,
    }
    return ReleaseAssuranceHandoffInspection(
        **body,
        content_address=content_hash(body | {"manifest_drift": drift}, prefix="release-assurance-handoff-inspection"),
    )


def _text_boundary(payload: bytes) -> tuple[str, ...]:
    """Scan human-readable artifacts for prohibited attribution tokens."""

    try:
        text = payload.decode("utf-8").casefold()
    except UnicodeDecodeError:
        return ("$invalid-utf8",)
    return tuple(f"$text:{token}" for token in _TEXT_PRIVATE_TOKENS if token in text)


def _listed_artifacts(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return well-typed manifest artifact rows."""

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


def verify_release_assurance_handoff(
    directory: str | Path,
) -> ReleaseAssuranceHandoffVerification:
    """Verify manifest closure, exact bytes, paths, and public boundary."""

    root, manifest, manifest_drift = _read_manifest(directory)
    if not manifest:
        return _empty_verification(root, ReleaseAssuranceHandoffState.MISSING)
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
    if len(listed) > RELEASE_ASSURANCE_HANDOFF_MAX_ARTIFACTS:
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
        symlinked = _path_has_symlink(root, path)
        if symlinked:
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
        media_type = str(item.get("media_type", ""))
        if media_type == "application/json":
            try:
                boundary.extend(forbidden_keys(json.loads(payload.decode("utf-8"))))
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        elif media_type in {"text/csv", "text/markdown"}:
            boundary.extend(f"{path}:{item}" for item in _text_boundary(payload))
    if len(artifact_ids) != len(set(artifact_ids)):
        manifest_drift = (*manifest_drift, "manifest.artifact_ids")
    actual_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    unexpected.extend(path for path in actual_paths if path not in sorted((*expected_paths, "manifest.json")))
    required_count = sum(bool(item.get("required", False)) for item in listed)
    if required_count != int(manifest.get("required_artifact_count", -1)):
        manifest_drift = (*manifest_drift, "manifest.required_artifact_count")
    accepted = bool(manifest.get("accepted")) and len(listed) == RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT and not any((
        missing, unexpected, duplicate, unsafe, tampered, boundary, manifest_drift,
    ))
    body = {
        "directory": str(root),
        "state": ReleaseAssuranceHandoffState.READY if accepted else ReleaseAssuranceHandoffState.BLOCKED,
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
    return ReleaseAssuranceHandoffVerification(
        **body,
        content_address=content_hash(body, prefix="release-assurance-handoff-verification"),
    )


def _manifest_items(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return sorted, public manifest rows for queries."""

    return tuple(sorted(_listed_artifacts(manifest), key=lambda item: str(item.get("artifact_id", ""))))


def query_release_assurance_handoff(
    directory: str | Path,
    *,
    resource: str = "artifacts",
    artifact_id: str | None = None,
    role: str | None = None,
    media_type: str | None = None,
    required_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ReleaseAssuranceHandoffQueryResult:
    """Query the verified handoff manifest without rebuilding its runtime."""

    if resource not in RELEASE_ASSURANCE_HANDOFF_RESOURCE_NAMES:
        raise ValidationError(f"unsupported release-assurance handoff resource: {resource}")
    if offset < 0 or limit < 1 or limit > 500:
        raise ValidationError("release-assurance handoff pagination is outside its contract")
    root, manifest, _drift = _read_manifest(directory)
    verification = verify_release_assurance_handoff(root)
    if resource == "artifacts":
        rows: Iterable[dict[str, Any]] = _manifest_items(manifest)
        if artifact_id:
            rows = (item for item in rows if item.get("artifact_id") == artifact_id)
        if role:
            rows = (item for item in rows if item.get("role") == role)
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
    return ReleaseAssuranceHandoffQueryResult(
        str(root), resource, len(materialized), offset, limit, page,
        verification.accepted,
        content_hash(body, prefix="release-assurance-handoff-query"),
    )


def diff_release_assurance_handoffs(
    left_directory: str | Path,
    right_directory: str | Path,
) -> ReleaseAssuranceHandoffDiff:
    """Compare two handoff manifests by artifact address only."""

    left_root, left_manifest, _left_drift = _read_manifest(left_directory)
    right_root, right_manifest, _right_drift = _read_manifest(right_directory)
    left_verification = verify_release_assurance_handoff(left_root)
    right_verification = verify_release_assurance_handoff(right_root)
    left_rows = {str(item.get("artifact_id")): item for item in _listed_artifacts(left_manifest)}
    right_rows = {str(item.get("artifact_id")): item for item in _listed_artifacts(right_manifest)}
    shared = sorted(set(left_rows) & set(right_rows))
    added = tuple(sorted(set(right_rows) - set(left_rows)))
    removed = tuple(sorted(set(left_rows) - set(right_rows)))
    changed = tuple(item for item in shared if left_rows[item].get("content_address") != right_rows[item].get("content_address"))
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
    return ReleaseAssuranceHandoffDiff(
        **body,
        content_address=content_hash(body, prefix="release-assurance-handoff-diff"),
    )


def replay_release_assurance_handoff(directory: str | Path) -> dict[str, Any]:
    """Run verification twice and return a deterministic replay receipt."""

    first = verify_release_assurance_handoff(directory)
    second = verify_release_assurance_handoff(directory)
    deterministic = first.content_address == second.content_address
    body = {
        "directory": str(directory),
        "first_address": first.content_address,
        "second_address": second.content_address,
        "deterministic": deterministic,
        "accepted": first.accepted and second.accepted and deterministic,
    }
    return body | {"content_address": content_hash(body, prefix="release-assurance-handoff-replay")}


def release_assurance_handoff_status(directory: str | Path) -> dict[str, Any]:
    """Return compact status for a handoff without exposing artifact bytes."""

    verification = verify_release_assurance_handoff(directory)
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
    "build_release_assurance_handoff",
    "diff_release_assurance_handoffs",
    "inspect_release_assurance_handoff",
    "query_release_assurance_handoff",
    "release_assurance_handoff_artifact_payloads",
    "release_assurance_handoff_status",
    "replay_release_assurance_handoff",
    "verify_release_assurance_handoff",
    "write_release_assurance_handoff",
]

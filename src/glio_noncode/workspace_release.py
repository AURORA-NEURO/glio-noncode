"""Gated, portable, byte-verifiable release bundles for research workspaces.

Workspace projections are useful interactively, but research handoffs also
need a stable directory that can be copied, archived, and reopened without
access to the local run store.  This module packages the public workspace
history, current snapshot, transitions, tabular projections, and gate evidence
as UTF-8 artifacts.  The manifest addresses the exact artifact bytes and the
verifier rejects unsafe paths, duplicate identities, missing files, size or
line-count drift, tampering, unexpected files, and public-boundary violations.

The bundle is descriptive and research-use-only.  It does not redistribute raw
case input or private dossier payloads, and a successful handoff is not a
clinical or treatment authorization.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, hash_bytes
from .workspace_history import (
    WorkspaceHistory,
    build_persisted_workspace_history,
)

WORKSPACE_RELEASE_VERSION = "workspace-release-v1"
WORKSPACE_RELEASE_MANIFEST = "release.json"
WORKSPACE_RELEASE_ARTIFACT_PREFIX = "workspace-release-artifact"


@dataclass(frozen=True, slots=True)
class WorkspaceReleaseCheck:
    """One explicit workspace release-gate observation."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceReleaseArtifact:
    """One portable UTF-8 artifact addressed by its exact bytes."""

    artifact_id: str
    filename: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: str

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        body = {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload:
            body["payload"] = self.payload
        return body


@dataclass(frozen=True, slots=True)
class WorkspaceReleaseBundle:
    """Complete workspace handoff package and its independent gate evidence."""

    release_id: str
    run_id: str
    case_id: str
    history_address: str
    current_snapshot_index: int
    state: str
    accepted: bool
    checks: tuple[WorkspaceReleaseCheck, ...]
    artifacts: tuple[WorkspaceReleaseArtifact, ...]
    content_address: str

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return {
            "release_version": WORKSPACE_RELEASE_VERSION,
            "release_id": self.release_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "history_address": self.history_address,
            "current_snapshot_index": self.current_snapshot_index,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": self.artifact_count,
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [item.to_dict() for item in self.checks],
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "content_address": self.content_address,
        }

    def manifest_dict(self) -> dict[str, Any]:
        """Return a portable manifest without duplicating artifact payloads."""

        return self.to_dict(include_payloads=False)


@dataclass(frozen=True, slots=True)
class WorkspaceReleaseVerification:
    """Filesystem verification result for a workspace release directory."""

    path: str
    release_id: str
    accepted: bool
    manifest_version_valid: bool
    manifest_address_valid: bool
    public_boundary_valid: bool
    artifact_count: int
    verified_artifact_count: int
    failed_artifact_ids: tuple[str, ...]
    unexpected_filenames: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "release_id": self.release_id,
            "accepted": self.accepted,
            "manifest_version_valid": self.manifest_version_valid,
            "manifest_address_valid": self.manifest_address_valid,
            "public_boundary_valid": self.public_boundary_valid,
            "artifact_count": self.artifact_count,
            "verified_artifact_count": self.verified_artifact_count,
            "failed_artifact_ids": list(self.failed_artifact_ids),
            "unexpected_filenames": list(self.unexpected_filenames),
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> WorkspaceReleaseCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkspaceReleaseCheck(
        **body,
        content_address=content_hash(body, prefix="workspace-release-check"),
    )


def _csv_payload(headers: tuple[str, ...], rows: tuple[tuple[Any, ...], ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _json_text(value: Any) -> str:
    return canonical_json(value) + "\n"


def _artifact(
    artifact_id: str,
    filename: str,
    media_type: str,
    payload: str,
) -> WorkspaceReleaseArtifact:
    encoded = payload.encode("utf-8")
    return WorkspaceReleaseArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=media_type,
        byte_count=len(encoded),
        line_count=len(payload.splitlines()),
        content_address=hash_bytes(encoded, prefix=WORKSPACE_RELEASE_ARTIFACT_PREFIX),
        payload=payload,
    )


def _snapshot_rows(history: WorkspaceHistory) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            snapshot.index,
            snapshot.dossier_address,
            snapshot.is_current,
            snapshot.status,
            snapshot.review_state or "",
            snapshot.workspace_id,
            snapshot.workspace_state,
            snapshot.record_count,
            snapshot.accepted,
            " | ".join(snapshot.warnings),
        )
        for snapshot in history.snapshots
    )


def _record_rows(history: WorkspaceHistory) -> tuple[tuple[Any, ...], ...]:
    rows: list[tuple[Any, ...]] = []
    for snapshot in history.snapshots:
        if snapshot.workspace is None:
            continue
        for record in snapshot.workspace.get("records", ()):
            rows.append(
                (
                    snapshot.index,
                    str(record.get("record_id", "")),
                    str(record.get("record_type", "")),
                    str(record.get("label", "")),
                    str(record.get("context_key", "")),
                    str(record.get("state", "")),
                    str(record.get("coordinate_label", "")),
                    json.dumps(record.get("source_ids", []), ensure_ascii=False, sort_keys=True),
                    json.dumps(record.get("tags", []), ensure_ascii=False, sort_keys=True),
                )
            )
    return tuple(rows)


def _transition_rows(history: WorkspaceHistory) -> tuple[tuple[Any, ...], ...]:
    rows: list[tuple[Any, ...]] = []
    for transition in history.transitions:
        for change in transition.changes:
            rows.append(
                (
                    transition.source_snapshot_index,
                    transition.target_snapshot_index,
                    transition.source_status,
                    transition.target_status,
                    transition.metadata_changed,
                    change.change_type,
                    change.record_id,
                    change.record_type,
                    ";".join(change.changed_fields),
                    change.before_address or "",
                    change.after_address or "",
                )
            )
        if not transition.changes and transition.metadata_changed:
            rows.append(
                (
                    transition.source_snapshot_index,
                    transition.target_snapshot_index,
                    transition.source_status,
                    transition.target_status,
                    transition.metadata_changed,
                    "metadata",
                    "",
                    "",
                    "review_or_status_metadata_changed",
                    "",
                    "",
                )
            )
    return tuple(rows)


def _report(history: WorkspaceHistory, release_id: str, accepted: bool) -> str:
    lines = [
        "# Workspace release",
        "",
        f"- Release: `{release_id}`",
        f"- Run: `{history.run_id}`",
        f"- Case: `{history.case_id}`",
        f"- Snapshots: {history.snapshot_count}",
        f"- Transitions: {history.transition_count}",
        f"- Total changes: {history.total_change_count}",
        f"- Accepted: `{str(accepted).lower()}`",
        "",
        "This is a deterministic research-workspace handoff. It preserves",
        "exact-context navigation, review-state transitions, source-linked",
        "records, uncertainty, and blocked states. It is not a diagnosis,",
        "clinical recommendation, treatment instruction, or causal proof.",
        "",
    ]
    if history.warnings:
        lines.extend(("## Warnings", "", *[f"- {warning}" for warning in history.warnings], ""))
    lines.extend(("## Snapshot summary", "", "| Index | Status | Review | Records | Accepted |", "| ---: | --- | --- | ---: | --- |"))
    for snapshot in history.snapshots:
        lines.append(
            f"| {snapshot.index} | {snapshot.status} | {snapshot.review_state or ''} | "
            f"{snapshot.record_count} | {str(snapshot.accepted).lower()} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _payloads(
    history: WorkspaceHistory,
    release_id: str,
    accepted: bool,
    checks: tuple[WorkspaceReleaseCheck, ...],
) -> dict[str, tuple[str, str, str]]:
    current = (
        history.snapshots[history.current_snapshot_index].to_dict()
        if history.snapshots and 0 <= history.current_snapshot_index < len(history.snapshots)
        else None
    )
    summary = {
        "run_id": history.run_id,
        "case_id": history.case_id,
        "current_snapshot_index": history.current_snapshot_index,
        "snapshot_count": history.snapshot_count,
        "transition_count": history.transition_count,
        "total_change_count": history.total_change_count,
        "accepted": accepted,
        "history_address": history.content_address,
    }
    snapshot_headers = (
        "snapshot_index",
        "dossier_address",
        "is_current",
        "status",
        "review_state",
        "workspace_id",
        "workspace_state",
        "record_count",
        "accepted",
        "warnings",
    )
    record_headers = (
        "snapshot_index",
        "record_id",
        "record_type",
        "label",
        "context_key",
        "state",
        "coordinate_label",
        "source_ids",
        "tags",
    )
    transition_headers = (
        "source_snapshot_index",
        "target_snapshot_index",
        "source_status",
        "target_status",
        "metadata_changed",
        "change_type",
        "record_id",
        "record_type",
        "changed_fields",
        "before_address",
        "after_address",
    )
    gate = {
        "release_id": release_id,
        "accepted": accepted,
        "checks": [item.to_dict() for item in checks],
        "history_address": history.content_address,
    }
    return {
        "workspace-history": (
            "workspace-history.json",
            "application/json",
            _json_text(history.to_dict()),
        ),
        "workspace-current": (
            "workspace-current.json",
            "application/json",
            _json_text(current),
        ),
        "workspace-summary": (
            "workspace-summary.json",
            "application/json",
            _json_text(summary),
        ),
        "workspace-snapshots-csv": (
            "workspace-snapshots.csv",
            "text/csv",
            _csv_payload(snapshot_headers, _snapshot_rows(history)),
        ),
        "workspace-records-csv": (
            "workspace-records.csv",
            "text/csv",
            _csv_payload(record_headers, _record_rows(history)),
        ),
        "workspace-transitions-csv": (
            "workspace-transitions.csv",
            "text/csv",
            _csv_payload(transition_headers, _transition_rows(history)),
        ),
        "release-gate": (
            "release-gate.json",
            "application/json",
            _json_text(gate),
        ),
        "workspace-report": (
            "workspace-report.md",
            "text/markdown",
            _report(history, release_id, accepted),
        ),
    }


def build_workspace_release_bundle(history: WorkspaceHistory) -> WorkspaceReleaseBundle:
    """Build a gated bundle from a historical workspace closure."""

    release_id = f"workspace-release-{history.content_address.split(':', 1)[-1][:24]}"
    snapshot_valid = bool(history.snapshots) and 0 <= history.current_snapshot_index < len(history.snapshots)
    current_valid = snapshot_valid and history.snapshots[history.current_snapshot_index].accepted
    public_body = history.to_dict()
    checks = (
        _check(
            "history-accepted",
            history.accepted,
            history.accepted,
            True,
            "workspace release requires an accepted replay-gated history",
        ),
        _check(
            "current-snapshot",
            current_valid,
            history.current_snapshot_index if snapshot_valid else None,
            "accepted current snapshot",
            "the current workspace snapshot must exist and pass its boundary",
        ),
        _check(
            "public-boundary",
            not _has_forbidden_key(public_body) and not contains_private_key(public_body),
            not _has_forbidden_key(public_body) and not contains_private_key(public_body),
            True,
            "history closure contains no private or attribution projection key",
        ),
    )
    preliminary_accepted = all(item.passed for item in checks)
    raw_payloads = _payloads(history, release_id, preliminary_accepted, checks)
    artifacts = tuple(
        _artifact(artifact_id, filename, media_type, payload)
        for artifact_id, (filename, media_type, payload) in sorted(raw_payloads.items())
    )
    artifact_check = _check(
        "artifact-addresses",
        all(item.content_address.startswith(f"{WORKSPACE_RELEASE_ARTIFACT_PREFIX}:") for item in artifacts),
        len(artifacts),
        len(raw_payloads),
        "every release artifact is addressed by exact UTF-8 bytes",
    )
    checks = checks + (artifact_check,)
    accepted = all(item.passed for item in checks)
    if accepted != preliminary_accepted:
        raw_payloads = _payloads(history, release_id, accepted, checks)
        artifacts = tuple(
            _artifact(artifact_id, filename, media_type, payload)
            for artifact_id, (filename, media_type, payload) in sorted(raw_payloads.items())
        )
    body = {
        "release_version": WORKSPACE_RELEASE_VERSION,
        "release_id": release_id,
        "run_id": history.run_id,
        "case_id": history.case_id,
        "history_address": history.content_address,
        "current_snapshot_index": history.current_snapshot_index,
        "state": "ready" if accepted else "blocked",
        "accepted": accepted,
        "artifact_count": len(artifacts),
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
        "checks": [item.to_dict() for item in checks],
        "artifacts": [item.to_dict() for item in artifacts],
    }
    return WorkspaceReleaseBundle(
        release_id=release_id,
        run_id=history.run_id,
        case_id=history.case_id,
        history_address=history.content_address,
        current_snapshot_index=history.current_snapshot_index,
        state=body["state"],
        accepted=accepted,
        checks=checks,
        artifacts=artifacts,
        content_address=content_hash(body, prefix="workspace-release"),
    )


def build_persisted_workspace_release(
    runtime: CaseRuntime,
    run_id: str,
) -> WorkspaceReleaseBundle:
    """Build a portable workspace release from persisted run history."""

    return build_workspace_release_bundle(build_persisted_workspace_history(runtime, run_id))


def write_workspace_release_bundle(
    bundle: WorkspaceReleaseBundle,
    destination: str | Path,
) -> Path:
    """Write a release bundle into a new or empty directory."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("release destination must be empty")
    for artifact in bundle.artifacts:
        filename = Path(artifact.filename)
        if not artifact.filename or filename.name != artifact.filename:
            raise ValueError("release artifact path must be a direct filename")
        (root / artifact.filename).write_text(artifact.payload, encoding="utf-8", newline="")
    (root / WORKSPACE_RELEASE_MANIFEST).write_text(
        canonical_json(bundle.manifest_dict()),
        encoding="utf-8",
        newline="",
    )
    return root


def verify_workspace_release_bundle(
    destination: str | Path,
) -> WorkspaceReleaseVerification:
    """Reopen a workspace release and verify every file and manifest address."""

    root = Path(destination)
    if not root.is_dir():
        raise ValidationError("workspace release directory is missing")
    manifest_path = root / WORKSPACE_RELEASE_MANIFEST
    if not manifest_path.exists():
        raise ValidationError("workspace release manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("workspace release manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise ValidationError("workspace release manifest must be a JSON object")
    manifest_version_valid = manifest.get("release_version") == WORKSPACE_RELEASE_VERSION
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValidationError("workspace release manifest artifacts must be an array")
    try:
        declared_count = int(manifest.get("artifact_count", -1))
    except (TypeError, ValueError):
        declared_count = -1
    failed: list[str] = []
    warnings: list[str] = []
    verified = 0
    artifact_boundary_valid = True
    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()
    declared_filenames: set[str] = set()

    def safe_path(filename: str) -> Path | None:
        if not filename or Path(filename).name != filename:
            return None
        return root / filename

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            failed.append("invalid-artifact")
            continue
        artifact_id = str(artifact.get("artifact_id", ""))
        filename = str(artifact.get("filename", ""))
        if artifact_id in seen_ids or filename in seen_filenames:
            failed.append(artifact_id or "duplicate-artifact")
            warnings.append(f"duplicate workspace artifact identity for {artifact_id or filename}")
            continue
        seen_ids.add(artifact_id)
        seen_filenames.add(filename)
        declared_filenames.add(filename)
        path = safe_path(filename)
        if path is None:
            failed.append(artifact_id or "unsafe-artifact")
            warnings.append(f"unsafe workspace artifact path for {artifact_id}")
            continue
        if path.is_symlink():
            failed.append(artifact_id or "symlink-artifact")
            warnings.append(f"workspace artifact symlinks are not allowed for {artifact_id}")
            continue
        if not path.is_file():
            failed.append(artifact_id)
            warnings.append(f"workspace artifact is missing for {artifact_id}")
            continue
        payload = path.read_bytes()
        if hash_bytes(payload, prefix=WORKSPACE_RELEASE_ARTIFACT_PREFIX) != str(
            artifact.get("content_address", "")
        ):
            failed.append(artifact_id)
            warnings.append(f"workspace artifact byte address mismatch for {artifact_id}")
            continue
        try:
            expected_bytes = int(artifact.get("byte_count", -1))
            expected_lines = int(artifact.get("line_count", -1))
        except (TypeError, ValueError):
            failed.append(artifact_id)
            warnings.append(f"workspace artifact size metadata is invalid for {artifact_id}")
            continue
        if len(payload) != expected_bytes:
            failed.append(artifact_id)
            warnings.append(f"workspace artifact byte count mismatch for {artifact_id}")
            continue
        try:
            decoded = payload.decode("utf-8")
            observed_lines = len(decoded.splitlines())
        except UnicodeDecodeError:
            failed.append(artifact_id)
            warnings.append(f"workspace artifact is not UTF-8 for {artifact_id}")
            continue
        if str(artifact.get("media_type", "")) == "application/json":
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                failed.append(artifact_id)
                artifact_boundary_valid = False
                warnings.append(f"workspace JSON artifact is not valid JSON for {artifact_id}")
                continue
            if _has_forbidden_key(parsed) or contains_private_key(parsed):
                failed.append(artifact_id)
                artifact_boundary_valid = False
                warnings.append(f"workspace JSON artifact violates the public boundary for {artifact_id}")
                continue
        if observed_lines != expected_lines:
            failed.append(artifact_id)
            warnings.append(f"workspace artifact line count mismatch for {artifact_id}")
            continue
        verified += 1

    actual_filenames = {
        item.name for item in root.iterdir() if item.name != WORKSPACE_RELEASE_MANIFEST
    }
    unexpected = tuple(sorted(actual_filenames - declared_filenames))
    if unexpected:
        warnings.append("unexpected files are present in the workspace release")

    reconstructed = dict(manifest)
    manifest_address = reconstructed.pop("content_address", None)
    reconstructed_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            reconstructed_artifacts.append({"payload": ""})
            continue
        copy = dict(artifact)
        path = safe_path(str(copy.get("filename", "")))
        copy["payload"] = (
            path.read_text(encoding="utf-8", errors="replace")
            if path is not None and path.is_file()
            else ""
        )
        reconstructed_artifacts.append(copy)
    reconstructed["artifacts"] = reconstructed_artifacts
    manifest_address_valid = (
        content_hash(reconstructed, prefix="workspace-release") == manifest_address
    )
    if not manifest_address_valid:
        warnings.append("workspace release manifest content address mismatch")
    if not manifest_version_valid:
        warnings.append("workspace release manifest version is unsupported")
    public_boundary_valid = (
        not _has_forbidden_key(manifest)
        and not contains_private_key(manifest)
        and artifact_boundary_valid
    )
    if not public_boundary_valid:
        warnings.append("workspace release manifest violates the public boundary")
    artifact_count_valid = declared_count == len(artifacts)
    if not artifact_count_valid:
        warnings.append("workspace release artifact count mismatch")
    accepted = (
        bool(manifest.get("accepted"))
        and manifest_version_valid
        and artifact_count_valid
        and manifest_address_valid
        and public_boundary_valid
        and not failed
        and not unexpected
        and verified == len(artifacts)
    )
    body = {
        "path": str(root),
        "release_id": str(manifest.get("release_id", "")),
        "accepted": accepted,
        "manifest_version_valid": manifest_version_valid,
        "manifest_address_valid": manifest_address_valid,
        "public_boundary_valid": public_boundary_valid,
        "artifact_count": len(artifacts),
        "verified_artifact_count": verified,
        "failed_artifact_ids": tuple(failed),
        "unexpected_filenames": unexpected,
        "warnings": tuple(warnings),
    }
    return WorkspaceReleaseVerification(
        **body,
        content_address=content_hash(body, prefix="workspace-release-verification"),
    )


__all__ = [
    "WORKSPACE_RELEASE_ARTIFACT_PREFIX",
    "WORKSPACE_RELEASE_MANIFEST",
    "WORKSPACE_RELEASE_VERSION",
    "WorkspaceReleaseArtifact",
    "WorkspaceReleaseBundle",
    "WorkspaceReleaseCheck",
    "WorkspaceReleaseVerification",
    "build_persisted_workspace_release",
    "build_workspace_release_bundle",
    "verify_workspace_release_bundle",
    "write_workspace_release_bundle",
]

"""Deterministic handoff projections for the provenance-first review workspace.

The review workspace is intentionally useful in more than one setting.  JSON
is the machine contract, CSV is convenient for spreadsheet and notebook
inspection, and Markdown is the human review surface.  This module keeps those
views derived from the same typed report and packages all of them in a small,
portable directory whose manifest addresses exact UTF-8 bytes.

The package contains aggregate review information only.  It never adds raw
evidence payloads, producer metadata, direct subject fields, or hidden
attribution to a release.  A release that fails the report boundary remains
observable as a failed verification result, but it is not silently promoted
to an accepted handoff.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace import ReviewWorkspaceReport
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


REVIEW_WORKSPACE_EXPORT_VERSION = "review-workspace-export-v1"
REVIEW_WORKSPACE_RELEASE_VERSION = "review-workspace-release-v1"
REVIEW_WORKSPACE_RELEASE_MANIFEST = "manifest.json"
REVIEW_WORKSPACE_RELEASE_ARTIFACT_PREFIX = "review-workspace-release-artifact"
REVIEW_WORKSPACE_RELEASE_MANIFEST_PREFIX = "review-workspace-release-manifest"


_COLLECTION_FILENAMES = {
    "hypotheses": "hypotheses.csv",
    "edges": "edges.csv",
    "evidence": "evidence.csv",
    "alternatives": "alternatives.csv",
    "deltas": "deltas.csv",
    "provenance": "provenance.csv",
    "review_queue": "review-queue.csv",
}

_COLLECTION_HEADERS: dict[str, tuple[str, ...]] = {
    "hypotheses": (
        "hypothesis_id", "variant_id", "element_id", "gene_id", "state_id",
        "mechanism", "context_key", "status", "support", "uncertainty",
        "edge_ids", "evidence_ids", "alternative_ids", "provenance_ids",
        "missing_evidence", "negative_evidence", "content_address",
    ),
    "edges": (
        "edge_id", "hypothesis_id", "edge_type", "source_id", "target_id",
        "support", "uncertainty", "context_fit", "support_level", "claim_ids",
        "source_ids", "evidence_state_counts", "alternatives", "content_address",
    ),
    "evidence": (
        "evidence_id", "edge_id", "source_id", "channel", "state", "tier",
        "score", "confidence", "context_key", "summary", "depends_on",
        "supersedes", "content_address",
    ),
    "alternatives": (
        "alternative_id", "hypothesis_id", "label", "edge_ids", "evidence_ids",
        "source_ids", "state", "content_address",
    ),
    "deltas": (
        "delta_id", "item_type", "item_id", "dimension", "before", "after",
        "delta", "direction", "baseline_run_id", "current_run_id",
        "provenance_ids", "content_address",
    ),
    "provenance": (
        "provenance_id", "source_id", "edge_ids", "evidence_ids", "tiers",
        "states", "context_keys", "depends_on", "supersedes", "receipt_ids",
        "content_address",
    ),
    "review_queue": (
        "item_id", "item_type", "target_id", "priority", "reasons", "edge_ids",
        "evidence_ids", "state", "content_address",
    ),
}


def _value(value: Any) -> str | int | float | bool:
    """Render one CSV cell without implementation-dependent repr output."""

    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        return canonical_json(jsonable(value))
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _csv_text(headers: tuple[str, ...], rows: Iterable[Mapping[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=headers,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({header: _value(row.get(header)) for header in headers})
    return stream.getvalue()


def _rows(report: ReviewWorkspaceReport, collection: str) -> tuple[Mapping[str, Any], ...]:
    if collection not in _COLLECTION_HEADERS:
        raise ValidationError(f"unknown review workspace collection: {collection}")
    items = getattr(report, collection)
    return tuple(jsonable(item) for item in items)


def review_workspace_collection_csv(report: ReviewWorkspaceReport, collection: str) -> str:
    """Render one named review collection as canonical RFC-style CSV text."""

    headers = _COLLECTION_HEADERS.get(collection)
    if headers is None:
        raise ValidationError(f"unknown review workspace collection: {collection}")
    return _csv_text(headers, _rows(report, collection))


def review_workspace_hypotheses_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "hypotheses")


def review_workspace_edges_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "edges")


def review_workspace_evidence_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "evidence")


def review_workspace_alternatives_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "alternatives")


def review_workspace_deltas_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "deltas")


def review_workspace_provenance_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "provenance")


def review_workspace_queue_csv(report: ReviewWorkspaceReport) -> str:
    return review_workspace_collection_csv(report, "review_queue")


def _markdown_cell(value: Any) -> str:
    text = str(_value(value)).replace("|", "\\|").replace("\n", " ").strip()
    return text or "—"


def _markdown_table(
    headers: tuple[str, ...], rows: Iterable[Mapping[str, Any]], *, limit: int | None = None
) -> list[str]:
    selected = tuple(rows)[:limit] if limit is not None else tuple(rows)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in selected:
        lines.append("| " + " | ".join(_markdown_cell(row.get(header)) for header in headers) + " |")
    if not selected:
        lines.append("| " + " | ".join("—" for _ in headers) + " |")
    return lines


def render_review_workspace_markdown(report: ReviewWorkspaceReport) -> str:
    """Render a complete, deterministic human review document."""

    body = report.to_dict()
    lines = [
        "# Review workspace",
        "",
        f"- Workspace: `{report.workspace_id}`",
        f"- Run: `{report.run_id}`",
        f"- Case: `{report.case_id}`",
        f"- Version: `{report.version}`",
        f"- State: `{report.state.value}`",
        f"- Boundary accepted: `{str(report.accepted).lower()}`",
        f"- Content address: `{report.content_address}`",
        "",
        "This is a deterministic, aggregate research review projection. It preserves "
        "hypotheses, evidence dimensions, alternatives, provenance, queue reasons, "
        "and item-level changes. It is not a diagnosis, clinical recommendation, "
        "treatment instruction, or causal proof.",
        "",
        "## Coverage",
        "",
        "| Collection | Rows | Export |",
        "| --- | ---: | --- |",
    ]
    for collection, filename in _COLLECTION_FILENAMES.items():
        lines.append(f"| {collection} | {len(getattr(report, collection))} | `{filename}` |")
    lines.extend(("", "## Warnings", ""))
    if report.warnings:
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append("- None")
    lines.extend(("", "## Integrity", ""))
    integrity = body.get("run_integrity") or {}
    lines.extend(
        (
            f"- Current run replay accepted: `{str(integrity.get('accepted', False)).lower()}`",
            f"- Baseline run: `{report.baseline_run_id or 'none'}`",
            f"- Baseline replay accepted: `{str((body.get('baseline_integrity') or {}).get('accepted', False)).lower()}`",
            "",
            "## Hypotheses",
            "",
        )
    )
    lines.extend(
        _markdown_table(
            ("hypothesis_id", "context_key", "status", "support", "uncertainty", "edge_ids", "alternative_ids"),
            body["hypotheses"],
        )
    )
    lines.extend(("", "## Edges", ""))
    lines.extend(
        _markdown_table(
            ("edge_id", "hypothesis_id", "edge_type", "source_id", "target_id", "support", "uncertainty", "context_fit", "support_level"),
            body["edges"],
        )
    )
    lines.extend(("", "## Evidence", ""))
    lines.extend(
        _markdown_table(
            ("evidence_id", "edge_id", "source_id", "channel", "state", "tier", "score", "confidence", "context_key"),
            body["evidence"],
        )
    )
    lines.extend(("", "## Alternatives", ""))
    lines.extend(
        _markdown_table(
            ("alternative_id", "hypothesis_id", "label", "state", "edge_ids", "evidence_ids", "source_ids"),
            body["alternatives"],
        )
    )
    lines.extend(("", "## Provenance", ""))
    lines.extend(
        _markdown_table(
            ("provenance_id", "source_id", "edge_ids", "evidence_ids", "tiers", "states", "context_keys", "receipt_ids"),
            body["provenance"],
        )
    )
    lines.extend(("", "## Review queue", ""))
    lines.extend(
        _markdown_table(
            ("item_id", "item_type", "target_id", "priority", "state", "reasons"),
            body["review_queue"],
        )
    )
    lines.extend(("", "## Deltas", ""))
    lines.extend(
        _markdown_table(
            ("delta_id", "item_type", "item_id", "dimension", "before", "after", "delta", "direction"),
            body["deltas"],
        )
    )
    return "\n".join(lines) + "\n"


def review_workspace_export_payloads(report: ReviewWorkspaceReport) -> dict[str, bytes]:
    """Return all public review projections as exact UTF-8 artifact bytes."""

    public_body = report.to_dict()
    if contains_private_key(public_body):
        raise ValidationError("review workspace export failed its public boundary")
    payloads: dict[str, bytes] = {
        "review-workspace.json": (canonical_json(public_body) + "\n").encode("utf-8"),
        "review-workspace.md": render_review_workspace_markdown(report).encode("utf-8"),
    }
    for collection, filename in _COLLECTION_FILENAMES.items():
        payloads[filename] = review_workspace_collection_csv(report, collection).encode("utf-8")
    return {filename: payloads[filename] for filename in sorted(payloads)}


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceReleaseArtifact:
    """One exact-byte release artifact; payload is retained only in memory."""

    artifact_id: str
    filename: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: bytes

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload:
            result["content"] = self.payload.decode("utf-8")
        return result


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceReleaseBundle:
    """Portable review projections and the manifest that closes their set."""

    release_id: str
    run_id: str
    case_id: str
    workspace_address: str
    state: str
    accepted: bool
    artifacts: tuple[ReviewWorkspaceReleaseArtifact, ...]
    manifest: Mapping[str, Any]
    content_address: str

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "release_version": REVIEW_WORKSPACE_RELEASE_VERSION,
            "release_id": self.release_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "workspace_address": self.workspace_address,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": len(self.artifacts),
            "artifacts": [item.to_dict(include_payload=include_payloads) for item in self.artifacts],
            "manifest": jsonable(self.manifest),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceReleaseVerification:
    """Independent filesystem verification of one review release directory."""

    path: str
    release_id: str
    accepted: bool
    manifest_version_valid: bool
    manifest_address_valid: bool
    public_boundary_valid: bool
    artifact_count: int
    verified_artifact_count: int
    missing_files: tuple[str, ...]
    unexpected_files: tuple[str, ...]
    unsafe_files: tuple[str, ...]
    tampered_files: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _media_type(filename: str) -> str:
    if filename.endswith(".json"):
        return "application/json"
    if filename.endswith(".csv"):
        return "text/csv"
    return "text/markdown"


def _artifact(artifact_id: str, filename: str, payload: bytes) -> ReviewWorkspaceReleaseArtifact:
    return ReviewWorkspaceReleaseArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=_media_type(filename),
        byte_count=len(payload),
        line_count=len(payload.decode("utf-8").splitlines()),
        content_address=hash_bytes(payload, prefix=REVIEW_WORKSPACE_RELEASE_ARTIFACT_PREFIX),
        payload=payload,
    )


def _manifest_body(
    report: ReviewWorkspaceReport,
    release_id: str,
    artifacts: tuple[ReviewWorkspaceReleaseArtifact, ...],
    accepted: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "release_version": REVIEW_WORKSPACE_RELEASE_VERSION,
        "export_version": REVIEW_WORKSPACE_EXPORT_VERSION,
        "release_id": release_id,
        "run_id": report.run_id,
        "case_id": report.case_id,
        "workspace_address": report.content_address,
        "state": report.state.value,
        "accepted": accepted,
        "artifact_count": len(artifacts),
        "artifacts": [item.to_dict() for item in artifacts],
        "public_boundary_valid": report.accepted,
        "warnings": list(report.warnings),
    }
    body["manifest_address"] = content_hash(body, prefix=REVIEW_WORKSPACE_RELEASE_MANIFEST_PREFIX)
    return body


def build_review_workspace_release(report: ReviewWorkspaceReport) -> ReviewWorkspaceReleaseBundle:
    """Build a closed set of JSON, CSV, and Markdown review artifacts."""

    if not isinstance(report, ReviewWorkspaceReport):
        raise ValidationError("review release requires a typed review workspace report")
    payloads = review_workspace_export_payloads(report)
    artifacts = tuple(
        _artifact(filename.replace(".", "-"), filename, payload)
        for filename, payload in sorted(payloads.items())
    )
    accepted = report.accepted and bool(artifacts)
    manifest = _manifest_body(report, f"review-release-{report.content_address.split(':', 1)[-1][:24]}", artifacts, accepted)
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    body = {
        "release_id": manifest["release_id"],
        "run_id": report.run_id,
        "case_id": report.case_id,
        "workspace_address": report.content_address,
        "state": report.state.value,
        "accepted": accepted,
        "manifest": manifest,
        "manifest_bytes": hash_bytes(manifest_bytes, prefix=REVIEW_WORKSPACE_RELEASE_MANIFEST_PREFIX),
        "artifacts": [item.to_dict() for item in artifacts],
    }
    return ReviewWorkspaceReleaseBundle(
        release_id=str(manifest["release_id"]),
        run_id=report.run_id,
        case_id=report.case_id,
        workspace_address=report.content_address,
        state=report.state.value,
        accepted=accepted,
        artifacts=artifacts,
        manifest=manifest,
        content_address=content_hash(body, prefix="review-workspace-release"),
    )


def _safe_filename(raw: Any) -> str:
    filename = str(raw)
    path = Path(filename)
    if not filename or path.name != filename or filename in {".", "..", REVIEW_WORKSPACE_RELEASE_MANIFEST}:
        raise ValidationError(f"unsafe review release filename: {filename!r}")
    return filename


def write_review_workspace_release(
    bundle: ReviewWorkspaceReleaseBundle,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write a bundle without deleting unrelated files or following a symlink root."""

    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("review release destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValueError("review release destination is not empty; pass allow_existing=True to overwrite")
    for artifact in bundle.artifacts:
        filename = _safe_filename(artifact.filename)
        target = root / filename
        if target.exists() and target.is_symlink():
            raise ValidationError(f"review release artifact must not be a symlink: {filename}")
        target.write_bytes(artifact.payload)
    manifest_target = root / REVIEW_WORKSPACE_RELEASE_MANIFEST
    if manifest_target.exists() and manifest_target.is_symlink():
        raise ValidationError("review release manifest must not be a symlink")
    manifest_target.write_bytes((canonical_json(bundle.manifest) + "\n").encode("utf-8"))
    return root


def _verification(
    *,
    root: Path,
    release_id: str,
    accepted: bool,
    manifest_version_valid: bool,
    manifest_address_valid: bool,
    public_boundary_valid: bool,
    artifact_count: int,
    verified_artifact_count: int,
    missing_files: Iterable[str] = (),
    unexpected_files: Iterable[str] = (),
    unsafe_files: Iterable[str] = (),
    tampered_files: Iterable[str] = (),
    boundary_violations: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> ReviewWorkspaceReleaseVerification:
    body = {
        "path": str(root),
        "release_id": release_id,
        "accepted": accepted,
        "manifest_version_valid": manifest_version_valid,
        "manifest_address_valid": manifest_address_valid,
        "public_boundary_valid": public_boundary_valid,
        "artifact_count": artifact_count,
        "verified_artifact_count": verified_artifact_count,
        "missing_files": tuple(sorted(set(missing_files))),
        "unexpected_files": tuple(sorted(set(unexpected_files))),
        "unsafe_files": tuple(sorted(set(unsafe_files))),
        "tampered_files": tuple(sorted(set(tampered_files))),
        "boundary_violations": tuple(sorted(set(boundary_violations))),
        "warnings": tuple(dict.fromkeys(warnings)),
    }
    return ReviewWorkspaceReleaseVerification(
        **body,
        content_address=content_hash(body, prefix="review-workspace-release-verification"),
    )


def verify_review_workspace_release(destination: str | Path) -> ReviewWorkspaceReleaseVerification:
    """Verify manifest closure, exact bytes, paths, and public-boundary safety."""

    root = Path(destination)
    if not root.is_dir() or root.is_symlink():
        raise ValidationError("review release directory is missing or is a symlink")
    manifest_path = root / REVIEW_WORKSPACE_RELEASE_MANIFEST
    missing: list[str] = []
    unexpected: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    boundary: list[str] = []
    warnings: list[str] = []
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification(
            root=root, release_id="", accepted=False, manifest_version_valid=False,
            manifest_address_valid=False, public_boundary_valid=False, artifact_count=0,
            verified_artifact_count=0, missing_files=(REVIEW_WORKSPACE_RELEASE_MANIFEST,),
        )
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _verification(
            root=root, release_id="", accepted=False, manifest_version_valid=False,
            manifest_address_valid=False, public_boundary_valid=False, artifact_count=0,
            verified_artifact_count=0, tampered_files=(REVIEW_WORKSPACE_RELEASE_MANIFEST,),
        )
    if not isinstance(manifest, dict):
        return _verification(
            root=root, release_id="", accepted=False, manifest_version_valid=False,
            manifest_address_valid=False, public_boundary_valid=False, artifact_count=0,
            verified_artifact_count=0, tampered_files=(REVIEW_WORKSPACE_RELEASE_MANIFEST,),
        )
    release_id = str(manifest.get("release_id", ""))
    version_valid = manifest.get("release_version") == REVIEW_WORKSPACE_RELEASE_VERSION
    if not version_valid:
        tampered.append(REVIEW_WORKSPACE_RELEASE_MANIFEST)
    normalized_manifest = dict(manifest)
    listed_address = normalized_manifest.pop("manifest_address", None)
    address_valid = listed_address == content_hash(normalized_manifest, prefix=REVIEW_WORKSPACE_RELEASE_MANIFEST_PREFIX)
    if not address_valid:
        tampered.append(REVIEW_WORKSPACE_RELEASE_MANIFEST)
    if manifest_bytes != (canonical_json(manifest) + "\n").encode("utf-8"):
        tampered.append(REVIEW_WORKSPACE_RELEASE_MANIFEST)
    try:
        boundary.extend("manifest:" + item for item in _private_key_paths(manifest))
    except TypeError:
        tampered.append(REVIEW_WORKSPACE_RELEASE_MANIFEST)
    expected: list[str] = []
    artifact_ids: list[str] = []
    listed = manifest.get("artifacts", ())
    if not isinstance(listed, list):
        tampered.append("manifest.artifacts")
        listed = []
    verified_count = 0
    for raw_artifact in listed:
        if not isinstance(raw_artifact, dict):
            tampered.append("manifest.artifacts")
            continue
        try:
            filename = _safe_filename(raw_artifact.get("filename"))
        except ValidationError:
            unsafe.append(str(raw_artifact.get("filename", "")))
            continue
        if filename in expected:
            unsafe.append(filename)
        expected.append(filename)
        artifact_id = str(raw_artifact.get("artifact_id", ""))
        if not artifact_id or artifact_id in artifact_ids:
            unsafe.append(f"artifact_id:{artifact_id}")
        artifact_ids.append(artifact_id)
        target = root / filename
        if not target.is_file() or target.is_symlink():
            missing.append(filename)
            continue
        payload = b""
        try:
            payload = target.read_bytes()
            valid = (
                len(payload) == int(raw_artifact.get("byte_count", -1))
                and len(payload.decode("utf-8").splitlines()) == int(raw_artifact.get("line_count", -1))
                and hash_bytes(payload, prefix=REVIEW_WORKSPACE_RELEASE_ARTIFACT_PREFIX) == raw_artifact.get("content_address")
            )
        except (OSError, UnicodeError, ValueError, TypeError):
            valid = False
        if not valid:
            tampered.append(filename)
        else:
            verified_count += 1
        if raw_artifact.get("media_type") == "application/json":
            try:
                artifact_body = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{filename}:{item}" for item in _private_key_paths(artifact_body))
            except (UnboundLocalError, UnicodeError, json.JSONDecodeError):
                tampered.append(filename)
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    try:
        manifest_count_valid = int(manifest.get("artifact_count", -1)) == len(expected)
    except (TypeError, ValueError):
        manifest_count_valid = False
    if not manifest_count_valid:
        tampered.append("manifest.artifact_count")
    unexpected.extend(path for path in actual if path not in sorted((*expected, REVIEW_WORKSPACE_RELEASE_MANIFEST)))
    public_boundary_valid = not boundary and bool(manifest.get("public_boundary_valid", False))
    accepted = bool(version_valid and address_valid and public_boundary_valid and not any((missing, unexpected, unsafe, tampered)))
    if not accepted and manifest.get("accepted"):
        warnings.append("manifest declared acceptance but independent verification rejected the package")
    return _verification(
        root=root,
        release_id=release_id,
        accepted=accepted,
        manifest_version_valid=version_valid,
        manifest_address_valid=address_valid,
        public_boundary_valid=public_boundary_valid,
        artifact_count=len(expected),
        verified_artifact_count=verified_count,
        missing_files=missing,
        unexpected_files=unexpected,
        unsafe_files=unsafe,
        tampered_files=tampered,
        boundary_violations=boundary,
        warnings=warnings,
    )


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    """Return recursive forbidden-key paths for an independent audit."""

    forbidden = {
        "agent", "agent_id", "agent_name", "assistant", "assistant_id", "assistant_name",
        "author", "author_id", "author_name", "contact", "contact_name", "credential",
        "email", "generated_by", "individual", "individual_id", "language",
        "medical_record_number", "model", "model_id", "model_name", "model_version",
        "participant", "participant_id", "patient", "patient_id", "phone",
        "programming_language", "produced_by", "sample", "sample_id", "secret",
        "secret_key", "subject", "subject_id", "token", "credential_value",
    }
    if isinstance(value, Mapping):
        result: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in forbidden:
                result.append(child)
            result.extend(_private_key_paths(item, child))
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result = []
        for index, item in enumerate(value):
            result.extend(_private_key_paths(item, f"{path}[{index}]"))
        return tuple(result)
    return ()


__all__ = [
    "REVIEW_WORKSPACE_EXPORT_VERSION",
    "REVIEW_WORKSPACE_RELEASE_ARTIFACT_PREFIX",
    "REVIEW_WORKSPACE_RELEASE_MANIFEST",
    "REVIEW_WORKSPACE_RELEASE_MANIFEST_PREFIX",
    "REVIEW_WORKSPACE_RELEASE_VERSION",
    "ReviewWorkspaceReleaseArtifact",
    "ReviewWorkspaceReleaseBundle",
    "ReviewWorkspaceReleaseVerification",
    "build_review_workspace_release",
    "render_review_workspace_markdown",
    "review_workspace_alternatives_csv",
    "review_workspace_collection_csv",
    "review_workspace_deltas_csv",
    "review_workspace_edges_csv",
    "review_workspace_evidence_csv",
    "review_workspace_export_payloads",
    "review_workspace_hypotheses_csv",
    "review_workspace_provenance_csv",
    "review_workspace_queue_csv",
    "verify_review_workspace_release",
    "write_review_workspace_release",
]

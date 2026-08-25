"""Portable, gated handoff bundles for dossier comparisons.

Comparison responses are useful interactively, but review and downstream
analysis need an immutable directory that can be copied, inspected offline,
and verified without trusting the producing process.  This module materializes
that handoff while retaining failed checks and the source/target history
closures that establish what was compared.
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
from .run_comparison import (
    ComparisonChange,
    ComparisonDimension,
    DossierComparison,
    RunHistory,
    build_run_history,
    compare_persisted_runs,
)
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, hash_bytes

COMPARISON_RELEASE_VERSION = "comparison-release-v1"
COMPARISON_RELEASE_MANIFEST = "release.json"


@dataclass(frozen=True, slots=True)
class ComparisonReleaseCheck:
    """One explicit comparison handoff gate observation."""

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
class ComparisonReleaseArtifact:
    """One UTF-8 handoff file addressed by its exact bytes."""

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
class ComparisonReleaseBundle:
    """Complete comparison handoff package and its release evidence."""

    release_id: str
    source_run_id: str
    target_run_id: str
    source_snapshot_index: int | None
    target_snapshot_index: int | None
    comparison_address: str
    state: str
    accepted: bool
    checks: tuple[ComparisonReleaseCheck, ...]
    artifacts: tuple[ComparisonReleaseArtifact, ...]
    content_address: str

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return {
            "release_version": COMPARISON_RELEASE_VERSION,
            "release_id": self.release_id,
            "source_run_id": self.source_run_id,
            "target_run_id": self.target_run_id,
            "source_snapshot_index": self.source_snapshot_index,
            "target_snapshot_index": self.target_snapshot_index,
            "comparison_address": self.comparison_address,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": self.artifact_count,
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [item.to_dict() for item in self.checks],
            "artifacts": [item.to_dict(include_payload=include_payloads) for item in self.artifacts],
            "content_address": self.content_address,
        }

    def manifest_dict(self) -> dict[str, Any]:
        """Return the portable manifest without repeating file payloads."""

        return self.to_dict(include_payloads=False)


@dataclass(frozen=True, slots=True)
class ComparisonReleaseVerification:
    """Reopen-and-verify result for a comparison handoff directory."""

    path: str
    release_id: str
    accepted: bool
    manifest_address_valid: bool
    artifact_count: int
    verified_artifact_count: int
    failed_artifact_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "release_id": self.release_id,
            "accepted": self.accepted,
            "manifest_address_valid": self.manifest_address_valid,
            "artifact_count": self.artifact_count,
            "verified_artifact_count": self.verified_artifact_count,
            "failed_artifact_ids": list(self.failed_artifact_ids),
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> ComparisonReleaseCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ComparisonReleaseCheck(**body, content_address=content_hash(body, prefix="comparison-release-check"))


def _artifact(artifact_id: str, filename: str, media_type: str, payload: str) -> ComparisonReleaseArtifact:
    encoded = payload.encode("utf-8")
    return ComparisonReleaseArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=media_type,
        byte_count=len(encoded),
        line_count=len(payload.splitlines()),
        content_address=hash_bytes(encoded, prefix="comparison-release-artifact"),
        payload=payload,
    )


def _csv_payload(rows: tuple[tuple[Any, ...], ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "change_type",
            "key",
            "changed_fields",
            "before_address",
            "after_address",
            "before",
            "after",
        )
    )
    writer.writerows(rows)
    return output.getvalue()


def _change_row(change: ComparisonChange) -> tuple[str, ...]:
    return (
        change.change_type,
        change.key,
        ";".join(change.changed_fields),
        change.before_address or "",
        change.after_address or "",
        canonical_json(change.before) if change.before is not None else "",
        canonical_json(change.after) if change.after is not None else "",
    )


def _dimension_rows(dimension: ComparisonDimension) -> tuple[tuple[str, ...], ...]:
    return tuple(_change_row(change) for change in dimension.changes)


def render_comparison_markdown(comparison: DossierComparison) -> str:
    """Render a bounded, human-readable comparison report."""

    lines = [
        "# Dossier comparison",
        "",
        f"- Source run: `{comparison.source_run_id}` (snapshot `{comparison.source_snapshot_index}`)",
        f"- Target run: `{comparison.target_run_id}` (snapshot `{comparison.target_snapshot_index}`)",
        f"- Source status: `{comparison.source_status}`",
        f"- Target status: `{comparison.target_status}`",
        f"- Same case: `{str(comparison.same_case).lower()}`",
        f"- Accepted: `{str(comparison.accepted).lower()}`",
        f"- Content address: `{comparison.content_address}`",
        "",
        "## Release checks",
        "",
        "| Check | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    for check in comparison.checks:
        lines.append(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |")
    lines.extend(["", "## Summary", "", "| Measure | Count |", "| --- | ---: |"])
    for key, value in comparison.summary.items():
        if isinstance(value, bool):
            value = str(value).lower()
        lines.append(f"| `{key}` | `{value}` |")
    for dimension in (comparison.metadata,) + comparison.dimensions:
        lines.extend(
            [
                "",
                f"## {dimension.name.title()}",
                "",
                f"Source rows: `{dimension.source_count}`; target rows: `{dimension.target_count}`; "
                f"changes: `{dimension.change_count}`; truncated: `{str(dimension.truncated).lower()}`.",
                "",
                "| Type | Key | Fields | Before | After |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for change in dimension.changes:
            before = canonical_json(change.before) if change.before is not None else ""
            after = canonical_json(change.after) if change.after is not None else ""
            lines.append(
                "| {} | `{}` | `{}` | `{}` | `{}` |".format(
                    change.change_type,
                    change.key.replace("|", "\\|"),
                    ";".join(change.changed_fields),
                    before.replace("|", "\\|"),
                    after.replace("|", "\\|"),
                )
            )
    if comparison.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in comparison.warnings)
    return "\n".join(lines) + "\n"


def _payloads(
    comparison: DossierComparison,
    source_history: RunHistory | None,
    target_history: RunHistory | None,
) -> dict[str, tuple[str, str, str]]:
    dimensions = (comparison.metadata,) + comparison.dimensions

    def history_payload(history: RunHistory | None) -> str:
        return canonical_json(history.to_dict() if history else {"available": False})

    return {
        "comparison-json": ("comparison.json", "application/json", canonical_json(comparison.to_dict())),
        "comparison-summary": (
            "comparison-summary.json",
            "application/json",
            canonical_json(
                {
                    "source_run_id": comparison.source_run_id,
                    "target_run_id": comparison.target_run_id,
                    "source_snapshot_index": comparison.source_snapshot_index,
                    "target_snapshot_index": comparison.target_snapshot_index,
                    "summary": comparison.summary,
                    "accepted": comparison.accepted,
                    "content_address": comparison.content_address,
                }
            ),
        ),
        "comparison-markdown": ("comparison.md", "text/markdown", render_comparison_markdown(comparison)),
        "comparison-checks": (
            "comparison-checks.json",
            "application/json",
            canonical_json({"checks": [item.to_dict() for item in comparison.checks]}),
        ),
        "source-history": ("source-history.json", "application/json", history_payload(source_history)),
        "target-history": ("target-history.json", "application/json", history_payload(target_history)),
        "metadata-diff": (
            "metadata-diff.csv",
            "text/csv",
            _csv_payload(_dimension_rows(comparison.metadata)),
        ),
        "hypotheses-diff": (
            "hypotheses-diff.csv",
            "text/csv",
            _csv_payload(_dimension_rows(dimensions[1])),
        ),
        "evidence-diff": (
            "evidence-diff.csv",
            "text/csv",
            _csv_payload(_dimension_rows(dimensions[2])),
        ),
        "experiments-diff": (
            "experiments-diff.csv",
            "text/csv",
            _csv_payload(_dimension_rows(dimensions[3])),
        ),
    }


def build_comparison_release_bundle(
    comparison: DossierComparison,
    *,
    source_history: RunHistory | None = None,
    target_history: RunHistory | None = None,
) -> ComparisonReleaseBundle:
    """Build a gated comparison handoff while retaining failed checks."""

    payloads = _payloads(comparison, source_history, target_history)
    artifacts = tuple(
        _artifact(artifact_id, filename, media_type, payload)
        for artifact_id, (filename, media_type, payload) in sorted(payloads.items())
    )
    public_body = {
        "comparison": comparison.to_dict(),
        "source_history": source_history.to_dict() if source_history else None,
        "target_history": target_history.to_dict() if target_history else None,
        "artifacts": [item.to_dict() for item in artifacts],
    }
    history_available = source_history is not None and target_history is not None
    history_accepted = history_available and source_history.accepted and target_history.accepted
    checks = (
        _check(
            "comparison-accepted",
            comparison.accepted,
            comparison.accepted,
            True,
            "comparison passed replay, case, completeness, and public-boundary checks",
        ),
        _check(
            "history-available",
            history_available,
            history_available,
            True,
            "both source and target history closures are included",
        ),
        _check(
            "history-integrity",
            history_accepted,
            {
                "source": source_history.accepted if source_history else None,
                "target": target_history.accepted if target_history else None,
            },
            True,
            "source and target snapshot histories are verified",
        ),
        _check(
            "artifact-addresses",
            all(item.content_address.startswith("comparison-release-artifact:") for item in artifacts),
            len(artifacts),
            len(artifacts),
            "every handoff artifact is byte-addressed",
        ),
        _check(
            "public-boundary",
            not contains_private_key(public_body),
            not contains_private_key(public_body),
            True,
            "handoff metadata contains no private projection key",
        ),
    )
    accepted = all(item.passed for item in checks)
    release_id = (
        f"comparison-release-{comparison.content_address.split(':', 1)[-1][:24]}"
    )
    body = {
        "release_version": COMPARISON_RELEASE_VERSION,
        "release_id": release_id,
        "source_run_id": comparison.source_run_id,
        "target_run_id": comparison.target_run_id,
        "source_snapshot_index": comparison.source_snapshot_index,
        "target_snapshot_index": comparison.target_snapshot_index,
        "comparison_address": comparison.content_address,
        "state": "ready" if accepted else "blocked",
        "accepted": accepted,
        "artifact_count": len(artifacts),
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
        "checks": [item.to_dict() for item in checks],
        "artifacts": [item.to_dict() for item in artifacts],
    }
    return ComparisonReleaseBundle(
        release_id=release_id,
        source_run_id=comparison.source_run_id,
        target_run_id=comparison.target_run_id,
        source_snapshot_index=comparison.source_snapshot_index,
        target_snapshot_index=comparison.target_snapshot_index,
        comparison_address=comparison.content_address,
        state=body["state"],
        accepted=accepted,
        checks=checks,
        artifacts=artifacts,
        content_address=content_hash(body, prefix="comparison-release"),
    )


def build_persisted_comparison_release(
    runtime: CaseRuntime,
    source_run_id: str,
    target_run_id: str,
    *,
    source_snapshot: int | None = None,
    target_snapshot: int | None = None,
    change_limit: int = 5_000,
) -> ComparisonReleaseBundle:
    """Build a handoff package from replay-verified persisted histories."""

    source_history = build_run_history(runtime, source_run_id)
    target_history = source_history if source_run_id == target_run_id else build_run_history(runtime, target_run_id)
    comparison = compare_persisted_runs(
        runtime,
        source_run_id,
        target_run_id,
        source_snapshot=source_snapshot,
        target_snapshot=target_snapshot,
        change_limit=change_limit,
    )
    return build_comparison_release_bundle(
        comparison,
        source_history=source_history,
        target_history=target_history,
    )


def write_comparison_release_bundle(
    bundle: ComparisonReleaseBundle,
    destination: str | Path,
) -> Path:
    """Write a comparison handoff into a new or empty directory."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("comparison release destination must be empty")
    for artifact in bundle.artifacts:
        (root / artifact.filename).write_text(artifact.payload, encoding="utf-8", newline="")
    (root / COMPARISON_RELEASE_MANIFEST).write_text(
        canonical_json(bundle.manifest_dict()),
        encoding="utf-8",
        newline="",
    )
    return root


def verify_comparison_release_bundle(destination: str | Path) -> ComparisonReleaseVerification:
    """Verify manifest address and every comparison artifact on disk."""

    root = Path(destination)
    manifest_path = root / COMPARISON_RELEASE_MANIFEST
    if not manifest_path.is_file():
        raise ValidationError("comparison release manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValidationError("comparison release manifest must be a JSON object")
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValidationError("comparison release artifacts must be a JSON array")
    try:
        manifest_count = int(manifest.get("artifact_count", -1))
    except (TypeError, ValueError):
        manifest_count = -1
    count_valid = manifest_count == len(artifacts)
    failed: list[str] = []
    warnings: list[str] = []
    verified = 0
    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()

    def safe_path(filename: str) -> Path | None:
        if not filename or Path(filename).name != filename:
            return None
        return root / filename

    for raw_artifact in artifacts:
        if not isinstance(raw_artifact, dict):
            failed.append("invalid-artifact")
            continue
        artifact_id = str(raw_artifact.get("artifact_id", ""))
        filename = str(raw_artifact.get("filename", ""))
        if artifact_id in seen_ids or filename in seen_filenames:
            failed.append(artifact_id or "duplicate-artifact")
            warnings.append(f"duplicate artifact identity for {artifact_id or filename}")
            continue
        seen_ids.add(artifact_id)
        seen_filenames.add(filename)
        path = safe_path(filename)
        if path is None:
            failed.append(artifact_id)
            warnings.append(f"unsafe artifact path for {artifact_id}")
            continue
        if not path.is_file():
            failed.append(artifact_id)
            continue
        payload = path.read_bytes()
        if hash_bytes(payload, prefix="comparison-release-artifact") != str(raw_artifact.get("content_address", "")):
            failed.append(artifact_id)
            continue
        try:
            expected_bytes = int(raw_artifact.get("byte_count", -1))
            expected_lines = int(raw_artifact.get("line_count", -1))
        except (TypeError, ValueError):
            failed.append(artifact_id)
            warnings.append(f"invalid size metadata for {artifact_id}")
            continue
        if len(payload) != expected_bytes:
            failed.append(artifact_id)
            continue
        try:
            observed_lines = len(payload.decode("utf-8").splitlines())
        except UnicodeDecodeError:
            failed.append(artifact_id)
            warnings.append(f"artifact is not valid UTF-8 for {artifact_id}")
            continue
        if observed_lines != expected_lines:
            failed.append(artifact_id)
            continue
        verified += 1

    reconstructed = dict(manifest)
    reconstructed.pop("content_address", None)
    reconstructed_artifacts: list[dict[str, Any]] = []
    for raw_artifact in artifacts:
        if not isinstance(raw_artifact, dict):
            reconstructed_artifacts.append({"payload": ""})
            continue
        artifact_copy = dict(raw_artifact)
        path = safe_path(str(artifact_copy.get("filename", "")))
        artifact_copy["payload"] = (
            path.read_text(encoding="utf-8", errors="replace")
            if path is not None and path.is_file()
            else ""
        )
        reconstructed_artifacts.append(artifact_copy)
    reconstructed["artifacts"] = reconstructed_artifacts
    manifest_valid = content_hash(reconstructed, prefix="comparison-release") == manifest.get("content_address")
    if not count_valid:
        warnings.append("manifest artifact count mismatch")
    if not manifest_valid:
        warnings.append("manifest content address mismatch")
    accepted = (
        bool(manifest.get("accepted"))
        and count_valid
        and manifest_valid
        and not failed
        and verified == len(artifacts)
    )
    body = {
        "path": str(root),
        "release_id": str(manifest.get("release_id", "")),
        "accepted": accepted,
        "manifest_address_valid": manifest_valid,
        "artifact_count": len(artifacts),
        "verified_artifact_count": verified,
        "failed_artifact_ids": tuple(failed),
        "warnings": tuple(warnings),
    }
    return ComparisonReleaseVerification(
        **body,
        content_address=content_hash(body, prefix="comparison-release-verification"),
    )


__all__ = [
    "COMPARISON_RELEASE_MANIFEST",
    "COMPARISON_RELEASE_VERSION",
    "ComparisonReleaseArtifact",
    "ComparisonReleaseBundle",
    "ComparisonReleaseCheck",
    "ComparisonReleaseVerification",
    "build_comparison_release_bundle",
    "build_persisted_comparison_release",
    "render_comparison_markdown",
    "verify_comparison_release_bundle",
    "write_comparison_release_bundle",
]

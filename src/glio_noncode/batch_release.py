"""Gated, portable release bundles for batch evaluations.

Batch results are useful inside the local runtime, but a handoff needs a
directory that can be copied and verified without the producing process.  This
module materializes the batch result, canonical input, summary, item/failure
CSV projections, a Markdown report, and release-gate evidence.  A partial batch
is deliberately retained as an inspectable blocked bundle rather than being
silently presented as a successful release.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .batch_runtime import BatchResult, BatchRuntime
from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, hash_bytes

BATCH_RELEASE_VERSION = "batch-release-v1"
BATCH_RELEASE_MANIFEST = "release.json"


@dataclass(frozen=True, slots=True)
class BatchReleaseCheck:
    """One explicit batch release-gate observation."""

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
class BatchReleaseArtifact:
    """One UTF-8 release artifact addressed by its exact bytes."""

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
class BatchReleaseBundle:
    """Complete portable batch handoff and its independent gate evidence."""

    release_id: str
    batch_id: str
    input_address: str
    result_address: str
    state: str
    accepted: bool
    gate: dict[str, Any]
    checks: tuple[BatchReleaseCheck, ...]
    artifacts: tuple[BatchReleaseArtifact, ...]
    content_address: str

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return {
            "release_version": BATCH_RELEASE_VERSION,
            "release_id": self.release_id,
            "batch_id": self.batch_id,
            "input_address": self.input_address,
            "result_address": self.result_address,
            "state": self.state,
            "accepted": self.accepted,
            "artifact_count": self.artifact_count,
            "failed_check_ids": list(self.failed_check_ids),
            "gate": self.gate,
            "checks": [item.to_dict() for item in self.checks],
            "artifacts": [item.to_dict(include_payload=include_payloads) for item in self.artifacts],
            "content_address": self.content_address,
        }

    def manifest_dict(self) -> dict[str, Any]:
        """Return the portable manifest without duplicating artifact payloads."""

        return self.to_dict(include_payloads=False)


@dataclass(frozen=True, slots=True)
class BatchReleaseVerification:
    """Filesystem verification result for a written batch release."""

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


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> BatchReleaseCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return BatchReleaseCheck(**body, content_address=content_hash(body, prefix="batch-release-check"))


def _csv_payload(headers: tuple[str, ...], rows: tuple[tuple[Any, ...], ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _artifact(artifact_id: str, filename: str, media_type: str, payload: str) -> BatchReleaseArtifact:
    encoded = payload.encode("utf-8")
    return BatchReleaseArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=media_type,
        byte_count=len(encoded),
        line_count=len(payload.splitlines()),
        content_address=hash_bytes(encoded, prefix="batch-release-artifact"),
        payload=payload,
    )


def _item_rows(result: BatchResult) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            item.index,
            item.case_id,
            item.state,
            item.input_address or "",
            item.run_id or "",
            item.dossier_address or "",
            item.error_code or "",
            item.error_message or "",
            item.accepted,
        )
        for item in result.items
    )


def _public_input(value: Any) -> Any:
    """Remove private subject keys before raw input enters a portable release."""

    if isinstance(value, Mapping):
        private_keys = {
            "patient_id",
            "subject_id",
            "participant_id",
            "individual_id",
            "medical_record_number",
            "contact_name",
            "email",
            "phone",
        }
        return {
            str(key): _public_input(item)
            for key, item in value.items()
            if str(key).lower() not in private_keys
        }
    if isinstance(value, (list, tuple)):
        return [_public_input(item) for item in value]
    return value


def render_batch_markdown(
    result: BatchResult,
    checks: tuple[BatchReleaseCheck, ...],
    release_id: str,
) -> str:
    """Render a bounded human-readable batch handoff report."""

    state = "ready" if result.accepted else "blocked"
    lines = [
        "# Batch release",
        "",
        f"- Release: `{release_id}`",
        f"- Batch: `{result.batch_id}`",
        f"- State: `{state}`",
        f"- Accepted: `{str(result.accepted).lower()}`",
        f"- Requested items: `{result.requested_count}`",
        f"- Accepted items: `{result.accepted_count}`",
        f"- Failed items: `{result.failed_count}`",
        f"- Input address: `{result.input_address}`",
        f"- Result address: `{result.result_address}`",
        "",
        "## Release checks",
        "",
        "| Check | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        lines.append(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |")
    lines.extend(
        [
            "",
            "## Items",
            "",
            "| Index | Case | State | Run | Dossier | Error |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for item in result.items:
        lines.append(
            f"| {item.index} | `{item.case_id}` | `{item.state}` | "
            f"`{item.run_id or ''}` | `{item.dossier_address or ''}` | "
            f"`{item.error_code or ''}` |"
        )
    lines.extend(
        [
            "",
            "This release is a research-workbench handoff. A blocked or partial "
            "batch remains inspectable and is not an accepted aggregate result.",
            "",
        ]
    )
    return "\n".join(lines)


def _payloads(
    result: BatchResult,
    input_payload: Any,
    checks: tuple[BatchReleaseCheck, ...],
    release_id: str,
) -> dict[str, tuple[str, str, str]]:
    headers = (
        "index",
        "case_id",
        "state",
        "input_address",
        "run_id",
        "dossier_address",
        "error_code",
        "error_message",
        "accepted",
    )
    item_rows = _item_rows(result)
    failure_rows = tuple(row for row, item in zip(item_rows, result.items, strict=True) if not item.accepted)
    run_rows = tuple(
        (item.index, item.case_id, item.run_id or "", item.dossier_address or "")
        for item in result.items
        if item.accepted
    )
    summary = {
        "batch_id": result.batch_id,
        "label": result.label,
        "created_at": result.created_at,
        "requested_count": result.requested_count,
        "completed_count": result.completed_count,
        "accepted_count": result.accepted_count,
        "failed_count": result.failed_count,
        "partial": result.partial,
        "accepted": result.accepted,
        "options": result.options,
    }
    gate = {
        "release_id": release_id,
        "batch_id": result.batch_id,
        "accepted": result.accepted,
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
        "checks": [item.to_dict() for item in checks],
    }
    return {
        "batch-json": ("batch.json", "application/json", canonical_json(result.to_dict())),
        "batch-input": (
            "batch-input-public.json",
            "application/json",
            canonical_json(input_payload),
        ),
        "batch-summary": ("batch-summary.json", "application/json", canonical_json(summary)),
        "batch-items-csv": ("batch-items.csv", "text/csv", _csv_payload(headers, item_rows)),
        "batch-failures-csv": ("batch-failures.csv", "text/csv", _csv_payload(headers, failure_rows)),
        "batch-runs-csv": (
            "batch-runs.csv",
            "text/csv",
            _csv_payload(("index", "case_id", "run_id", "dossier_address"), run_rows),
        ),
        "batch-release-gate": ("batch-release-gate.json", "application/json", canonical_json(gate)),
        "batch-markdown": (
            "batch.md",
            "text/markdown",
            render_batch_markdown(result, checks, release_id),
        ),
    }


def build_batch_release_bundle(result: BatchResult, input_payload: Any) -> BatchReleaseBundle:
    """Build a gated release bundle from a batch result and its raw input."""

    input_address_valid = content_hash(input_payload) == result.input_address
    result_address_valid = content_hash(result._payload()) == result.result_address
    public_input = _public_input(input_payload)
    public_body = {
        "batch_id": result.batch_id,
        "input_address": result.input_address,
        "result_address": result.result_address,
        "result": result.to_dict(),
        "input": public_input,
    }
    release_id = f"batch-release-{result.batch_id.split('-', 1)[-1][:24]}"
    preliminary_checks = (
        _check("input-address", input_address_valid, input_address_valid, True, "the canonical batch input matches its stored address"),
        _check("result-address", result_address_valid, result_address_valid, True, "the canonical batch result matches its stored address"),
        _check("items-complete", result.completed_count == result.requested_count, result.completed_count, result.requested_count, "every requested item has a terminal outcome"),
        _check("item-counts", result.accepted_count + result.failed_count == result.completed_count, result.accepted_count + result.failed_count, result.completed_count, "accepted and failed counts reconcile with completed items"),
        _check("batch-accepted", result.accepted, result.accepted, True, "release requires every batch item to succeed"),
        _check("input-public-boundary", not contains_private_key(public_input), not contains_private_key(public_input), True, "the portable input projection omits private subject keys"),
        _check("public-boundary", not contains_private_key(public_body), not contains_private_key(public_body), True, "release metadata contains no private projection key"),
    )
    raw_payloads = _payloads(result, public_input, preliminary_checks, release_id)
    artifacts = tuple(
        _artifact(artifact_id, filename, media_type, payload)
        for artifact_id, (filename, media_type, payload) in sorted(raw_payloads.items())
    )
    artifact_check = _check(
        "artifact-addresses",
        all(artifact.content_address.startswith("batch-release-artifact:") for artifact in artifacts),
        len(artifacts),
        len(artifacts),
        "every release artifact is addressed by its exact UTF-8 bytes",
    )
    checks = preliminary_checks + (artifact_check,)
    accepted = all(item.passed for item in checks)
    gate = {
        "release_id": release_id,
        "batch_id": result.batch_id,
        "accepted": accepted,
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
    }
    body = {
        "release_version": BATCH_RELEASE_VERSION,
        "release_id": release_id,
        "batch_id": result.batch_id,
        "input_address": result.input_address,
        "result_address": result.result_address,
        "state": "ready" if accepted else "blocked",
        "accepted": accepted,
        "artifact_count": len(artifacts),
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
        "gate": gate,
        "checks": [item.to_dict() for item in checks],
        "artifacts": [item.to_dict() for item in artifacts],
    }
    return BatchReleaseBundle(
        release_id=release_id,
        batch_id=result.batch_id,
        input_address=result.input_address,
        result_address=result.result_address,
        state=body["state"],
        accepted=accepted,
        gate=gate,
        checks=checks,
        artifacts=artifacts,
        content_address=content_hash(body, prefix="batch-release"),
    )


def build_persisted_batch_release(runtime: CaseRuntime, batch_id: str) -> BatchReleaseBundle:
    """Build a release bundle only from a verified persisted batch."""

    batch_runtime = BatchRuntime(runtime=runtime)
    result = batch_runtime.get(batch_id)
    input_payload = runtime.store.store.get(result.input_address)
    if content_hash(input_payload) != result.input_address:
        raise ValidationError("cannot release a batch with an invalid input address")
    return build_batch_release_bundle(result, input_payload)


def write_batch_release_bundle(bundle: BatchReleaseBundle, destination: str | Path) -> Path:
    """Write a portable bundle into a new or empty directory."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("release destination must be empty")
    for artifact in bundle.artifacts:
        if not artifact.filename or Path(artifact.filename).name != artifact.filename:
            raise ValueError("release artifact path must be a direct filename")
        (root / artifact.filename).write_text(artifact.payload, encoding="utf-8", newline="")
    (root / BATCH_RELEASE_MANIFEST).write_text(
        canonical_json(bundle.manifest_dict()), encoding="utf-8", newline=""
    )
    return root


def verify_batch_release_bundle(destination: str | Path) -> BatchReleaseVerification:
    """Reopen a release directory and verify every artifact and manifest hash."""

    root = Path(destination)
    manifest_path = root / BATCH_RELEASE_MANIFEST
    if not manifest_path.exists():
        raise ValidationError("release manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValidationError("release manifest must be a JSON object")
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValidationError("release manifest artifacts must be a JSON array")
    failed: list[str] = []
    warnings: list[str] = []
    verified = 0
    try:
        declared_count = int(manifest.get("artifact_count", -1))
    except (TypeError, ValueError):
        declared_count = -1
    count_valid = declared_count == len(artifacts)
    if not count_valid:
        warnings.append("manifest artifact count mismatch")

    def safe_path(filename: str) -> Path | None:
        if not filename or Path(filename).name != filename:
            return None
        return root / filename

    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            failed.append("invalid-artifact")
            continue
        artifact_id = str(artifact.get("artifact_id", ""))
        filename = str(artifact.get("filename", ""))
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
        if hash_bytes(payload, prefix="batch-release-artifact") != str(artifact.get("content_address", "")):
            failed.append(artifact_id)
            continue
        try:
            expected_bytes = int(artifact.get("byte_count", -1))
            expected_lines = int(artifact.get("line_count", -1))
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
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            reconstructed_artifacts.append({"payload": ""})
            continue
        copy = dict(artifact)
        path = safe_path(str(copy.get("filename", "")))
        copy["payload"] = path.read_text(encoding="utf-8", errors="replace") if path and path.is_file() else ""
        reconstructed_artifacts.append(copy)
    reconstructed["artifacts"] = reconstructed_artifacts
    manifest_address_valid = content_hash(reconstructed, prefix="batch-release") == manifest.get("content_address")
    if not manifest_address_valid:
        warnings.append("manifest content address mismatch")
    accepted = (
        bool(manifest.get("accepted"))
        and count_valid
        and manifest_address_valid
        and not failed
        and verified == len(artifacts)
    )
    body = {
        "path": str(root),
        "release_id": str(manifest.get("release_id", "")),
        "accepted": accepted,
        "manifest_address_valid": manifest_address_valid,
        "artifact_count": len(artifacts),
        "verified_artifact_count": verified,
        "failed_artifact_ids": tuple(failed),
        "warnings": tuple(warnings),
    }
    return BatchReleaseVerification(
        **body,
        content_address=content_hash(body, prefix="batch-release-verification"),
    )


__all__ = [
    "BATCH_RELEASE_MANIFEST",
    "BATCH_RELEASE_VERSION",
    "BatchReleaseArtifact",
    "BatchReleaseBundle",
    "BatchReleaseCheck",
    "BatchReleaseVerification",
    "build_batch_release_bundle",
    "build_persisted_batch_release",
    "render_batch_markdown",
    "verify_batch_release_bundle",
    "write_batch_release_bundle",
]

"""Policy-gated portable release bundles for reviewed research dossiers."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dossier_query import build_dossier_query_closure, summarize_dossier
from .errors import ValidationError
from .models import Dossier
from .module_fabric_support import contains_private_key
from .reports import render_markdown
from .run_catalog import RunInspection, inspect_run
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash, hash_bytes
from .validation import ReleaseGate

DOSSIER_RELEASE_VERSION = "dossier-release-v1"
DOSSIER_RELEASE_MANIFEST = "release.json"


@dataclass(frozen=True, slots=True)
class ReleaseCheck:
    """One explicit release-gate observation."""

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
class ReleaseArtifact:
    """One portable text artifact with a byte-level content address."""

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
class DossierReleaseBundle:
    """Complete dossier release bundle and its independent gate evidence."""

    release_id: str
    run_id: str
    case_id: str
    dossier_address: str
    input_address: str
    event_address: str
    state: str
    accepted: bool
    gate: dict[str, Any]
    checks: tuple[ReleaseCheck, ...]
    artifacts: tuple[ReleaseArtifact, ...]
    content_address: str

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, *, include_payloads: bool = True) -> dict[str, Any]:
        return {
            "release_version": DOSSIER_RELEASE_VERSION,
            "release_id": self.release_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_address": self.dossier_address,
            "input_address": self.input_address,
            "event_address": self.event_address,
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
        """Return the portable manifest without embedding duplicate payloads."""

        return self.to_dict(include_payloads=False)


@dataclass(frozen=True, slots=True)
class ReleaseVerification:
    """Filesystem verification result for a written release bundle."""

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


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> ReleaseCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReleaseCheck(**body, content_address=content_hash(body, prefix="dossier-release-check"))


def _csv_payload(headers: tuple[str, ...], rows: tuple[tuple[Any, ...], ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def _artifact(artifact_id: str, filename: str, media_type: str, payload: str) -> ReleaseArtifact:
    encoded = payload.encode("utf-8")
    return ReleaseArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=media_type,
        byte_count=len(encoded),
        line_count=len(payload.splitlines()),
        content_address=hash_bytes(encoded, prefix="dossier-release-artifact"),
        payload=payload,
    )


def _payloads(dossier: Dossier, inspection: RunInspection, gate: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    query_closure = build_dossier_query_closure(dossier)
    evidence_rows = tuple(
        (
            item.evidence_id,
            item.edge_id,
            item.source_id,
            item.channel,
            item.state.value,
            item.tier.value,
            "" if item.score is None else item.score,
            item.confidence,
            item.summary,
        )
        for item in dossier.evidence
    )
    hypothesis_rows = tuple(
        (
            item.hypothesis_id,
            item.variant_id,
            item.element_id,
            item.gene_id,
            item.state_id,
            item.support,
            item.uncertainty,
            item.status.value,
        )
        for item in dossier.hypotheses
    )
    experiment_rows = tuple(
        (
            item.option_id,
            item.assay.value,
            item.priority,
            item.cost_class,
            ";".join(item.readouts),
            ";".join(item.controls),
        )
        for item in dossier.experiments
    )
    return {
        "dossier-json": ("dossier.json", "application/json", canonical_json(dossier.to_dict())),
        "dossier-markdown": ("dossier.md", "text/markdown", render_markdown(dossier)),
        "dossier-summary": ("dossier-summary.json", "application/json", canonical_json(summarize_dossier(dossier).to_dict())),
        "dossier-query-closure": ("dossier-query-closure.json", "application/json", canonical_json(query_closure)),
        "run-events": ("run-events.json", "application/json", canonical_json(inspection.event_record)),
        "release-gate": ("release-gate.json", "application/json", canonical_json(gate)),
        "review": ("review.json", "application/json", canonical_json({"review": dossier.review.to_dict() if dossier.review else None})),
        "evidence-csv": (
            "evidence.csv",
            "text/csv",
            _csv_payload(("evidence_id", "edge_id", "source_id", "channel", "state", "tier", "score", "confidence", "summary"), evidence_rows),
        ),
        "hypotheses-csv": (
            "hypotheses.csv",
            "text/csv",
            _csv_payload(("hypothesis_id", "variant_id", "element_id", "gene_id", "state_id", "support", "uncertainty", "status"), hypothesis_rows),
        ),
        "experiments-csv": (
            "experiments.csv",
            "text/csv",
            _csv_payload(("option_id", "assay", "priority", "cost_class", "readouts", "controls"), experiment_rows),
        ),
    }


def build_dossier_release_bundle(
    dossier: Dossier,
    inspection: RunInspection,
) -> DossierReleaseBundle:
    """Build a release bundle and retain every failed gate as evidence."""

    gate = ReleaseGate().check(dossier).to_dict()
    raw_payloads = _payloads(dossier, inspection, gate)
    artifacts = tuple(
        _artifact(artifact_id, filename, media_type, payload)
        for artifact_id, (filename, media_type, payload) in sorted(raw_payloads.items())
    )
    public_body = {
        "gate": gate,
        "artifacts": [item.to_dict() for item in artifacts],
        "run_id": dossier.run_id,
        "case_id": dossier.case_id,
    }
    checks = (
        _check("run-integrity", inspection.accepted, inspection.accepted, True, "the source run passed replay verification"),
        _check("review-accepted", dossier.is_releasable, dossier.review.state.value if dossier.review else None, "accepted", "release requires an accepted human review"),
        _check("release-gate", bool(gate["valid"]), gate["valid"], True, "structural and policy release checks pass"),
        _check("artifact-addresses", all(":" in item.content_address for item in artifacts), len(artifacts), len(artifacts), "every artifact is byte-addressed"),
        _check("public-boundary", not contains_private_key(public_body), not contains_private_key(public_body), True, "release metadata contains no private projection key"),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "release_version": DOSSIER_RELEASE_VERSION,
        "release_id": f"release-{dossier.content_address.split(':', 1)[-1][:24]}",
        "run_id": dossier.run_id,
        "case_id": dossier.case_id,
        "dossier_address": dossier.content_address,
        "input_address": dossier.input_address,
        "event_address": inspection.summary.event_address,
        "state": "ready" if accepted else "blocked",
        "accepted": accepted,
        "artifact_count": len(artifacts),
        "failed_check_ids": [item.check_id for item in checks if not item.passed],
        "gate": gate,
        "checks": [item.to_dict() for item in checks],
        "artifacts": [item.to_dict() for item in artifacts],
    }
    return DossierReleaseBundle(
        release_id=body["release_id"],
        run_id=dossier.run_id,
        case_id=dossier.case_id,
        dossier_address=dossier.content_address,
        input_address=dossier.input_address,
        event_address=inspection.summary.event_address,
        state=body["state"],
        accepted=accepted,
        gate=gate,
        checks=checks,
        artifacts=artifacts,
        content_address=content_hash(body, prefix="dossier-release"),
    )


def build_persisted_dossier_release(runtime: CaseRuntime, run_id: str) -> DossierReleaseBundle:
    """Build a release bundle only from a replay-verified persisted run."""

    inspection = inspect_run(runtime, run_id)
    if not inspection.accepted:
        raise ValidationError("cannot release a run that fails replay integrity")
    dossier = Dossier.from_dict(inspection.dossier_record)
    return build_dossier_release_bundle(dossier, inspection)


def write_dossier_release_bundle(bundle: DossierReleaseBundle, destination: str | Path) -> Path:
    """Write a portable bundle into a new or empty directory."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("release destination must be empty")
    for artifact in bundle.artifacts:
        (root / artifact.filename).write_text(artifact.payload, encoding="utf-8", newline="")
    (root / DOSSIER_RELEASE_MANIFEST).write_text(
        canonical_json(bundle.manifest_dict()), encoding="utf-8", newline=""
    )
    return root


def verify_dossier_release_bundle(destination: str | Path) -> ReleaseVerification:
    """Reopen a release directory and verify manifest and every artifact byte hash."""

    root = Path(destination)
    manifest_path = root / DOSSIER_RELEASE_MANIFEST
    if not manifest_path.exists():
        raise ValidationError("release manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValidationError("release manifest must be a JSON object")
    failed: list[str] = []
    warnings: list[str] = []
    verified = 0
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValidationError("release manifest artifacts must be a JSON array")
    try:
        manifest_artifact_count = int(manifest.get("artifact_count", -1))
    except (TypeError, ValueError):
        manifest_artifact_count = -1
    artifact_count_valid = manifest_artifact_count == len(artifacts)
    if not artifact_count_valid:
        warnings.append("manifest artifact count mismatch")

    def safe_path(filename: str) -> Path | None:
        if not filename or Path(filename).name != filename:
            return None
        return root / filename

    seen_artifact_ids: set[str] = set()
    seen_filenames: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            failed.append("invalid-artifact")
            continue
        artifact_id = str(artifact.get("artifact_id", ""))
        filename = str(artifact.get("filename", ""))
        if artifact_id in seen_artifact_ids or filename in seen_filenames:
            failed.append(artifact_id or "duplicate-artifact")
            warnings.append(f"duplicate artifact identity for {artifact_id or filename}")
            continue
        seen_artifact_ids.add(artifact_id)
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
        expected = str(artifact.get("content_address", ""))
        if hash_bytes(payload, prefix="dossier-release-artifact") != expected:
            failed.append(artifact_id)
            continue
        try:
            expected_byte_count = int(artifact.get("byte_count", -1))
            expected_line_count = int(artifact.get("line_count", -1))
        except (TypeError, ValueError):
            failed.append(artifact_id)
            warnings.append(f"invalid size metadata for {artifact_id}")
            continue
        if len(payload) != expected_byte_count:
            failed.append(artifact_id)
            continue
        try:
            observed_line_count = len(payload.decode("utf-8").splitlines())
        except UnicodeDecodeError:
            failed.append(artifact_id)
            warnings.append(f"artifact is not valid UTF-8 for {artifact_id}")
            continue
        if observed_line_count != expected_line_count:
            failed.append(artifact_id)
            continue
        verified += 1
    reconstructed = dict(manifest)
    reconstructed.pop("content_address", None)
    reconstructed_artifacts = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            reconstructed_artifacts.append({"payload": ""})
            continue
        artifact_copy = dict(artifact)
        path = safe_path(str(artifact_copy.get("filename", "")))
        artifact_copy["payload"] = (
            path.read_text(encoding="utf-8", errors="replace")
            if path is not None and path.is_file()
            else ""
        )
        reconstructed_artifacts.append(artifact_copy)
    reconstructed["artifacts"] = reconstructed_artifacts
    manifest_address_valid = content_hash(reconstructed, prefix="dossier-release") == manifest.get("content_address")
    if not manifest_address_valid:
        warnings.append("manifest content address mismatch")
    accepted = (
        bool(manifest.get("accepted"))
        and artifact_count_valid
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
    return ReleaseVerification(**body, content_address=content_hash(body, prefix="dossier-release-verification"))


__all__ = [
    "DOSSIER_RELEASE_MANIFEST",
    "DOSSIER_RELEASE_VERSION",
    "DossierReleaseBundle",
    "ReleaseArtifact",
    "ReleaseCheck",
    "ReleaseVerification",
    "build_dossier_release_bundle",
    "build_persisted_dossier_release",
    "verify_dossier_release_bundle",
    "write_dossier_release_bundle",
]

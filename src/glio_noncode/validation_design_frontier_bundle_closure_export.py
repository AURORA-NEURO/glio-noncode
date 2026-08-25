"""Exact-byte export packet for the D13 closure runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes, jsonable
from .validation_design_frontier_bundle_closure_contracts import (
    ValidationDesignClosureRuntimeReport,
)

VALIDATION_DESIGN_CLOSURE_EXPORT_VERSION = "validation-design-closure-export-v1"
VALIDATION_DESIGN_CLOSURE_EXPORT_MANIFEST = "closure-export.json"
VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_PREFIX = "validation-design-closure-export-artifact"
VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_COUNT = 11


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureExportArtifact:
    artifact_id: str
    relative_path: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: str | None = None

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload and self.payload is not None:
            body["payload"] = self.payload
        return jsonable(body)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureExportManifest:
    version: str
    bundle_id: str
    run_id: str
    artifacts: tuple[ValidationDesignClosureExportArtifact, ...]
    accepted: bool
    content_address: str

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "version": self.version,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "artifacts": [
                item.to_dict(include_payload=include_payloads) for item in self.artifacts
            ],
            "artifact_count": self.artifact_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureExportVerification:
    bundle_id: str
    artifact_count: int
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(str(item.get("check_id")) for item in self.checks if not item.get("passed"))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _safe_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _artifact(
    artifact_id: str, relative_path: str, media_type: str, value: Any
) -> ValidationDesignClosureExportArtifact:
    if media_type == "application/json":
        text = canonical_json(value) + "\n"
    else:
        text = str(value).rstrip("\n") + "\n"
    raw = text.encode("utf-8")
    body = {
        "artifact_id": artifact_id,
        "relative_path": relative_path,
        "media_type": media_type,
        "byte_count": len(raw),
        "line_count": len(text.splitlines()),
    }
    return ValidationDesignClosureExportArtifact(
        **body,
        content_address=hash_bytes(raw, prefix=VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_PREFIX),
        payload=text,
    )


def build_validation_design_closure_export(
    report: ValidationDesignClosureRuntimeReport,
    *,
    failure_report: Any | None = None,
) -> ValidationDesignClosureExportManifest:
    """Flatten a closure runtime into independently verifiable exact bytes."""

    artifacts = [
        _artifact("boundary", "boundary.json", "application/json", report.boundary.to_dict()),
        _artifact("indexes", "indexes.json", "application/json", report.indexes.to_dict()),
        _artifact(
            "index-audit", "index-audit.json", "application/json", report.index_audit.to_dict()
        ),
        _artifact(
            "reconciliation",
            "reconciliation.json",
            "application/json",
            report.reconciliation.to_dict(),
        ),
        _artifact("summary", "summary.json", "application/json", report.summary.to_dict()),
        _artifact(
            "summary-audit",
            "summary-audit.json",
            "application/json",
            report.summary_audit.to_dict(),
        ),
        _artifact(
            "certification",
            "certification.json",
            "application/json",
            report.certification.to_dict(),
        ),
        _artifact(
            "observability",
            "observability.json",
            "application/json",
            report.observability.to_dict(),
        ),
        _artifact("replay", "replay.json", "application/json", report.replay.to_dict()),
        _artifact("runtime", "runtime.json", "application/json", report.to_dict()),
    ]
    if failure_report is not None:
        artifacts.append(
            _artifact(
                "failure-injection",
                "failure-injection.json",
                "application/json",
                failure_report.to_dict(),
            )
        )
    accepted = report.accepted and len(artifacts) == VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_COUNT
    body = {
        "version": VALIDATION_DESIGN_CLOSURE_EXPORT_VERSION,
        "bundle_id": report.bundle.bundle_id,
        "run_id": report.run_id,
        "artifacts": tuple(item.to_dict(include_payload=False) for item in artifacts),
        "accepted": accepted,
    }
    return ValidationDesignClosureExportManifest(
        version=VALIDATION_DESIGN_CLOSURE_EXPORT_VERSION,
        bundle_id=report.bundle.bundle_id,
        run_id=report.run_id,
        artifacts=tuple(artifacts),
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-export"),
    )


def write_validation_design_closure_export(
    manifest: ValidationDesignClosureExportManifest, destination: str | Path
) -> Path:
    """Write exact export bytes and one root manifest."""

    if not manifest.accepted:
        raise ValidationError("cannot write a rejected D13 closure export")
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in manifest.artifacts:
        if artifact.payload is None or not _safe_path(artifact.relative_path):
            raise ValidationError(f"invalid D13 closure export artifact: {artifact.artifact_id}")
        target = root / Path(*PurePosixPath(artifact.relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.payload.encode("utf-8"))
    (root / VALIDATION_DESIGN_CLOSURE_EXPORT_MANIFEST).write_bytes(
        (canonical_json(manifest.to_dict()) + "\n").encode("utf-8")
    )
    return root


def verify_validation_design_closure_export(
    destination: str | Path,
) -> ValidationDesignClosureExportVerification:
    """Verify paths, bytes, addresses, and export manifest conservation."""

    root = Path(destination)
    manifest_path = root / VALIDATION_DESIGN_CLOSURE_EXPORT_MANIFEST
    checks: list[dict[str, Any]] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return ValidationDesignClosureExportVerification(
            bundle_id="",
            artifact_count=0,
            checks=({"check_id": "manifest-readable", "passed": False, "detail": str(exc)},),
            accepted=False,
            content_address=content_hash(
                {"checks": (str(exc),), "accepted": False},
                prefix="validation-design-closure-export-verification",
            ),
        )
    bundle_id = str(manifest.get("bundle_id", ""))
    artifacts = manifest.get("artifacts", [])
    checks.append(
        {
            "check_id": "manifest-version",
            "passed": manifest.get("version") == VALIDATION_DESIGN_CLOSURE_EXPORT_VERSION,
            "observed": manifest.get("version"),
            "required": VALIDATION_DESIGN_CLOSURE_EXPORT_VERSION,
        }
    )
    checks.append(
        {
            "check_id": "manifest-artifact-count",
            "passed": manifest.get("artifact_count")
            == len(artifacts)
            == VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_COUNT,
            "observed": manifest.get("artifact_count"),
            "required": VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_COUNT,
        }
    )
    paths = [str(item.get("relative_path", "")) for item in artifacts if isinstance(item, dict)]
    checks.append(
        {
            "check_id": "safe-unique-paths",
            "passed": len(paths) == len(set(paths)) and all(_safe_path(path) for path in paths),
            "observed": paths,
            "required": "safe unique relative paths",
        }
    )
    for raw in artifacts:
        if not isinstance(raw, dict):
            checks.append(
                {
                    "check_id": "artifact-object",
                    "passed": False,
                    "observed": type(raw).__name__,
                    "required": "object",
                }
            )
            continue
        artifact_id = str(raw.get("artifact_id", ""))
        path = str(raw.get("relative_path", ""))
        target = (
            root / Path(*PurePosixPath(path).parts) if _safe_path(path) else root / "__invalid__"
        )
        try:
            data = target.read_bytes()
            actual = hash_bytes(data, prefix=VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_PREFIX)
            passed = actual == raw.get("content_address") and len(data) == raw.get("byte_count")
            detail = "exact bytes and address match" if passed else "byte count or address mismatch"
        except OSError as exc:
            passed = False
            actual = ""
            detail = str(exc)
        checks.append(
            {
                "check_id": f"bytes:{artifact_id}",
                "passed": passed,
                "observed": actual,
                "required": raw.get("content_address"),
                "detail": detail,
            }
        )
    accepted = bool(manifest.get("accepted")) and all(item.get("passed") for item in checks)
    body = {
        "bundle_id": bundle_id,
        "artifact_count": len(artifacts),
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return ValidationDesignClosureExportVerification(
        bundle_id=bundle_id,
        artifact_count=len(artifacts),
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-export-verification"),
    )


__all__ = [
    "VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_COUNT",
    "VALIDATION_DESIGN_CLOSURE_EXPORT_ARTIFACT_PREFIX",
    "VALIDATION_DESIGN_CLOSURE_EXPORT_MANIFEST",
    "VALIDATION_DESIGN_CLOSURE_EXPORT_VERSION",
    "ValidationDesignClosureExportArtifact",
    "ValidationDesignClosureExportManifest",
    "ValidationDesignClosureExportVerification",
    "build_validation_design_closure_export",
    "verify_validation_design_closure_export",
    "write_validation_design_closure_export",
]

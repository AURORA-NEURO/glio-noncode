"""Exact-byte export packets for D15 closure review and archival."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .serialization import canonical_json, hash_bytes, jsonable
from .workbench_release_frontier_offline_closure_certification import (
    certify_workbench_release_closure,
)
from .workbench_release_frontier_offline_closure_failure_injection import (
    build_workbench_release_closure_failure_report,
)
from .workbench_release_frontier_offline_closure_graph import build_workbench_release_closure_graph
from .workbench_release_frontier_offline_closure_indexes import (
    audit_workbench_release_closure_indexes,
    build_workbench_release_closure_indexes,
)
from .workbench_release_frontier_offline_closure_observability import (
    build_workbench_release_closure_observability,
)
from .workbench_release_frontier_offline_closure_reconciliation import (
    reconcile_workbench_release_closure,
)
from .workbench_release_frontier_offline_closure_runtime import (
    run_workbench_release_closure_runtime,
)
from .workbench_release_frontier_offline_closure_schema import (
    build_workbench_release_closure_schema,
)
from .workbench_release_frontier_offline_closure_summary import (
    audit_workbench_release_closure_summary,
    build_workbench_release_closure_summary,
)
from .workbench_release_frontier_offline_closure_support import safe_relative_path
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_EXPORT_VERSION = "workbench-release-closure-export-v1"
WORKBENCH_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT = 14


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureExportArtifact:
    relative_path: str
    media_type: str
    byte_count: int
    content_address: str
    content: bytes

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body = {
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "content_address": self.content_address,
        }
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureExportManifest:
    version: str
    bundle_id: str
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureExportPacket:
    bundle_id: str
    artifacts: tuple[WorkbenchReleaseClosureExportArtifact, ...]
    manifest: WorkbenchReleaseClosureExportManifest
    accepted: bool
    content_address: str

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "artifacts": [item.to_dict(include_content=include_content) for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureExportVerification:
    bundle_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _value(value: Any) -> Any:
    return value.to_dict() if hasattr(value, "to_dict") else value


def _json_artifact(relative_path: str, value: Any) -> WorkbenchReleaseClosureExportArtifact:
    content = (canonical_json(jsonable(_value(value))) + "\n").encode("utf-8")
    return WorkbenchReleaseClosureExportArtifact(
        relative_path=relative_path,
        media_type="application/json",
        byte_count=len(content),
        content_address=hash_bytes(content, prefix="workbench-release-closure-export"),
        content=content,
    )


def build_workbench_release_closure_export(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureExportPacket:
    """Build fourteen immutable JSON artifacts plus a signed manifest."""

    boundary = {
        "bundle_id": bundle.bundle_id,
        "source_boundary": bundle.boundary,
        "accepted": bundle.accepted,
    }
    schema = build_workbench_release_closure_schema()
    indexes = build_workbench_release_closure_indexes(bundle)
    index_audit = audit_workbench_release_closure_indexes(bundle, indexes)
    reconciliation = reconcile_workbench_release_closure(bundle)
    summary = build_workbench_release_closure_summary(bundle)
    summary_audit = audit_workbench_release_closure_summary(summary)
    certification = certify_workbench_release_closure(bundle)
    observability = build_workbench_release_closure_observability(bundle)
    graph = build_workbench_release_closure_graph(bundle)
    failure = build_workbench_release_closure_failure_report(bundle)
    runtime = run_workbench_release_closure_runtime(
        bundle_id=bundle.bundle_id, run_id=f"{bundle.bundle_id}:export-runtime"
    )
    values = (
        ("boundary.json", boundary),
        ("schema.json", schema),
        ("indexes.json", indexes),
        ("index-audit.json", index_audit),
        ("reconciliation.json", reconciliation),
        ("summary.json", summary),
        ("summary-audit.json", summary_audit),
        ("certification.json", certification),
        ("observability.json", observability),
        ("graph.json", graph),
        ("failure-controls.json", failure),
        ("replay.json", runtime.replay),
        ("runtime.json", runtime),
        ("runtime-stages.json", {"stages": runtime.stages}),
    )
    artifacts = tuple(_json_artifact(path, value) for path, value in values)
    accepted = all(
        (
            bundle.accepted,
            indexes.accepted,
            index_audit.accepted,
            reconciliation.accepted,
            summary.accepted,
            summary_audit.accepted,
            certification.accepted,
            observability.accepted,
            graph.accepted,
            failure.accepted,
            runtime.accepted,
        )
    )
    manifest_body = {
        "version": WORKBENCH_RELEASE_CLOSURE_EXPORT_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(artifacts),
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "accepted": accepted and len(artifacts) == WORKBENCH_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT,
    }
    manifest = WorkbenchReleaseClosureExportManifest(
        **manifest_body,
        content_address=hash_bytes(
            canonical_json(manifest_body).encode("utf-8"),
            prefix="workbench-release-closure-export-manifest",
        ),
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "artifacts": artifacts,
        "manifest": manifest,
        "accepted": manifest.accepted,
    }
    content_body = {
        "bundle_id": bundle.bundle_id,
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "manifest": manifest.to_dict(),
        "accepted": manifest.accepted,
    }
    return WorkbenchReleaseClosureExportPacket(
        **body,
        content_address=hash_bytes(
            canonical_json(content_body).encode("utf-8"),
            prefix="workbench-release-closure-export-packet",
        ),
    )


def write_workbench_release_closure_export(
    packet: WorkbenchReleaseClosureExportPacket,
    destination: str | Path,
) -> Path:
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        if not safe_relative_path(artifact.relative_path):
            raise ValueError(f"unsafe D15 closure export path: {artifact.relative_path}")
        target = root / artifact.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.content)
    (root / "manifest.json").write_bytes(
        (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    )
    return root


def verify_workbench_release_closure_export(
    packet: WorkbenchReleaseClosureExportPacket,
    destination: str | Path,
) -> WorkbenchReleaseClosureExportVerification:
    root = Path(destination)
    expected = {item.relative_path: item for item in packet.artifacts}
    actual = (
        {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if root.exists()
        else {}
    )
    missing = set(expected) - set(actual)
    manifest_path = root / "manifest.json"
    expected_manifest = (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    if not manifest_path.is_file():
        missing.add("manifest.json")
    unexpected = set(actual) - set(expected)
    changed = {
        path
        for path in set(expected) & set(actual)
        if actual[path].read_bytes() != expected[path].content
    }
    if manifest_path.is_file() and manifest_path.read_bytes() != expected_manifest:
        changed.add("manifest.json")
    body = {
        "bundle_id": packet.bundle_id,
        "checked_artifact_count": len(actual),
        "missing_paths": tuple(sorted(missing)),
        "changed_paths": tuple(sorted(changed)),
        "unexpected_paths": tuple(sorted(unexpected)),
        "accepted": not missing and not changed and not unexpected and len(actual) == len(expected),
    }
    return WorkbenchReleaseClosureExportVerification(
        **body,
        content_address=hash_bytes(
            canonical_json(body).encode("utf-8"),
            prefix="workbench-release-closure-export-verification",
        ),
    )


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_EXPORT_ARTIFACT_COUNT",
    "WORKBENCH_RELEASE_CLOSURE_EXPORT_VERSION",
    "WorkbenchReleaseClosureExportArtifact",
    "WorkbenchReleaseClosureExportManifest",
    "WorkbenchReleaseClosureExportPacket",
    "WorkbenchReleaseClosureExportVerification",
    "build_workbench_release_closure_export",
    "verify_workbench_release_closure_export",
    "write_workbench_release_closure_export",
]

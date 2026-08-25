"""Exact-byte export packets for D14 closure review and archival."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_certification import (
    certify_evidence_lifecycle_closure,
)
from .evidence_lifecycle_frontier_offline_closure_failure_injection import (
    run_evidence_lifecycle_closure_failure_injection,
)
from .evidence_lifecycle_frontier_offline_closure_graph import (
    build_evidence_lifecycle_closure_graph,
)
from .evidence_lifecycle_frontier_offline_closure_indexes import (
    audit_evidence_lifecycle_closure_indexes,
    build_evidence_lifecycle_closure_indexes,
)
from .evidence_lifecycle_frontier_offline_closure_observability import (
    build_evidence_lifecycle_closure_observability,
)
from .evidence_lifecycle_frontier_offline_closure_reconciliation import (
    reconcile_evidence_lifecycle_closure,
)
from .evidence_lifecycle_frontier_offline_closure_runtime import (
    run_evidence_lifecycle_closure_runtime,
)
from .evidence_lifecycle_frontier_offline_closure_summary import (
    audit_evidence_lifecycle_closure_summary,
    build_evidence_lifecycle_closure_summary,
)
from .evidence_lifecycle_frontier_offline_closure_support import safe_relative_path
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import canonical_json, hash_bytes, jsonable

EVIDENCE_LIFECYCLE_CLOSURE_EXPORT_VERSION = "evidence-lifecycle-closure-export-v1"
EVIDENCE_LIFECYCLE_CLOSURE_EXPORT_ARTIFACT_COUNT = 12


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureExportArtifact:
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
class EvidenceLifecycleClosureExportManifest:
    version: str
    bundle_id: str
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureExportPacket:
    bundle_id: str
    artifacts: tuple[EvidenceLifecycleClosureExportArtifact, ...]
    manifest: EvidenceLifecycleClosureExportManifest
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
class EvidenceLifecycleClosureExportVerification:
    bundle_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _json_artifact(relative_path: str, value: Any) -> EvidenceLifecycleClosureExportArtifact:
    content = (canonical_json(value) + "\n").encode("utf-8")
    return EvidenceLifecycleClosureExportArtifact(
        relative_path=relative_path,
        media_type="application/json",
        byte_count=len(content),
        content_address=hash_bytes(content, prefix="evidence-lifecycle-closure-export"),
        content=content,
    )


def build_evidence_lifecycle_closure_export(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureExportPacket:
    indexes = build_evidence_lifecycle_closure_indexes(bundle)
    index_audit = audit_evidence_lifecycle_closure_indexes(bundle, indexes)
    reconciliation = reconcile_evidence_lifecycle_closure(bundle)
    summary = build_evidence_lifecycle_closure_summary(bundle)
    summary_audit = audit_evidence_lifecycle_closure_summary(summary)
    certification = certify_evidence_lifecycle_closure(bundle)
    observability = build_evidence_lifecycle_closure_observability(bundle)
    graph = build_evidence_lifecycle_closure_graph(bundle)
    failure = run_evidence_lifecycle_closure_failure_injection(bundle)
    runtime = run_evidence_lifecycle_closure_runtime(
        bundle_id=bundle.bundle_id, run_id=f"{bundle.bundle_id}:export-runtime"
    )
    replay = runtime.replay
    values = (
        (
            "boundary.json",
            {"bundle_id": bundle.bundle_id, "boundary": bundle.boundary, "accepted": bundle.ready},
        ),
        ("indexes.json", indexes),
        ("index-audit.json", index_audit),
        ("reconciliation.json", reconciliation),
        ("summary.json", summary),
        ("summary-audit.json", summary_audit),
        ("certification.json", certification),
        ("observability.json", observability),
        ("graph.json", graph),
        ("failure-controls.json", failure),
        ("replay.json", replay),
        ("runtime.json", runtime),
    )
    artifacts = tuple(_json_artifact(path, jsonable(value)) for path, value in values)
    manifest_body = {
        "version": EVIDENCE_LIFECYCLE_CLOSURE_EXPORT_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(artifacts),
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "accepted": all(
            (
                bundle.ready,
                indexes.accepted,
                index_audit.accepted,
                reconciliation.accepted,
                summary.accepted,
                summary_audit.accepted,
                certification.accepted,
                observability.accepted,
                graph.accepted,
                failure.accepted,
                replay.accepted,
                runtime.accepted,
            )
        ),
    }
    manifest = EvidenceLifecycleClosureExportManifest(
        **manifest_body,
        content_address=hash_bytes(
            canonical_json(manifest_body).encode("utf-8"),
            prefix="evidence-lifecycle-closure-export-manifest",
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
    return EvidenceLifecycleClosureExportPacket(
        **body,
        content_address=hash_bytes(
            canonical_json(content_body).encode("utf-8"),
            prefix="evidence-lifecycle-closure-export-packet",
        ),
    )


def write_evidence_lifecycle_closure_export(
    packet: EvidenceLifecycleClosureExportPacket, destination: str | Path
) -> Path:
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        if not safe_relative_path(artifact.relative_path):
            raise ValueError(f"unsafe D14 closure export path: {artifact.relative_path}")
        target = root / artifact.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.content)
    manifest = root / "manifest.json"
    manifest.write_bytes((canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8"))
    return root


def verify_evidence_lifecycle_closure_export(
    packet: EvidenceLifecycleClosureExportPacket, destination: str | Path
) -> EvidenceLifecycleClosureExportVerification:
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
    missing_values = set(expected) - set(actual)
    manifest_path = root / "manifest.json"
    expected_manifest = (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8")
    if not manifest_path.is_file():
        missing_values.add("manifest.json")
    missing = tuple(sorted(missing_values))
    unexpected = tuple(sorted(set(actual) - set(expected)))
    changed_values = {
        path
        for path in set(expected) & set(actual)
        if actual[path].read_bytes() != expected[path].content
    }
    if manifest_path.is_file() and manifest_path.read_bytes() != expected_manifest:
        changed_values.add("manifest.json")
    changed = tuple(sorted(changed_values))
    body = {
        "bundle_id": packet.bundle_id,
        "checked_artifact_count": len(actual),
        "missing_paths": missing,
        "changed_paths": changed,
        "unexpected_paths": unexpected,
        "accepted": not missing and not changed and not unexpected and len(actual) == len(expected),
    }
    return EvidenceLifecycleClosureExportVerification(
        **body,
        content_address=hash_bytes(
            canonical_json(body).encode("utf-8"),
            prefix="evidence-lifecycle-closure-export-verification",
        ),
    )


__all__ = [
    "EVIDENCE_LIFECYCLE_CLOSURE_EXPORT_ARTIFACT_COUNT",
    "EVIDENCE_LIFECYCLE_CLOSURE_EXPORT_VERSION",
    "EvidenceLifecycleClosureExportArtifact",
    "EvidenceLifecycleClosureExportManifest",
    "EvidenceLifecycleClosureExportPacket",
    "EvidenceLifecycleClosureExportVerification",
    "build_evidence_lifecycle_closure_export",
    "verify_evidence_lifecycle_closure_export",
    "write_evidence_lifecycle_closure_export",
]

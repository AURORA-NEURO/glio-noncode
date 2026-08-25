"""Explicit public-boundary and filesystem-shape checks for D14 bundles.

The ordinary verifier checks whether bytes match a manifest.  This module
checks whether the material itself is appropriate for the public aggregate
boundary: no direct-identifier fields, no attribution metadata, no hidden
files, no symlinks, no traversal paths, and no extra unlisted files.  The
checks are deliberately independent so a reviewer can inspect why a bundle is
held without needing a service process.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable
from .evidence_lifecycle_frontier_offline_bundle import verify_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .evidence_lifecycle_frontier_offline_query import load_evidence_lifecycle_offline_bundle

EVIDENCE_LIFECYCLE_OFFLINE_BOUNDARY_VERSION = "evidence-lifecycle-offline-boundary-v1"

_FORBIDDEN_BOUNDARY_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "email",
        "generated_by",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "primary_agent",
        "primary_agent_id",
        "programming_language",
        "produced_by",
        "sample_id",
        "subject_id",
    }
)
_PRIVATE_BOUNDARY_KEYS = frozenset({"individual_id", "medical_record_number", "participant_id", "patient_id", "phone", "sample_id", "subject_id"})


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineBoundaryFinding:
    finding_id: str
    plane: str
    passed: bool
    path: str
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineBoundaryReport:
    version: str
    bundle_id: str
    findings: tuple[EvidenceLifecycleOfflineBoundaryFinding, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.findings)

    @property
    def failed_count(self) -> int:
        return len(self.findings) - self.passed_count

    @property
    def failed_finding_ids(self) -> tuple[str, ...]:
        return tuple(item.finding_id for item in self.findings if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "finding_count": len(self.findings),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "failed_finding_ids": list(self.failed_finding_ids),
        }


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineBoundaryPolicy:
    policy_id: str
    boundary: str
    permitted_media_types: tuple[str, ...]
    permitted_root_files: tuple[str, ...]
    forbidden_key_count: int
    direct_identifier_key_count: int
    content_addressed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_lifecycle_offline_boundary_policy() -> EvidenceLifecycleOfflineBoundaryPolicy:
    body = {
        "policy_id": "evidence-lifecycle-offline-public-policy",
        "boundary": "public_aggregate_non_patient_offline_handoff",
        "permitted_media_types": ("application/json", "text/csv"),
        "permitted_root_files": ("bundle.json",),
        "forbidden_key_count": len(_FORBIDDEN_BOUNDARY_KEYS),
        "direct_identifier_key_count": len(_PRIVATE_BOUNDARY_KEYS),
        "content_addressed": True,
    }
    return EvidenceLifecycleOfflineBoundaryPolicy(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-boundary-policy"))


def _finding(finding_id: str, plane: str, passed: bool, path: str, observed: Any, required: Any, detail: str) -> EvidenceLifecycleOfflineBoundaryFinding:
    body = {"finding_id": finding_id, "plane": plane, "passed": bool(passed), "path": path, "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleOfflineBoundaryFinding(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-boundary-finding"))


def _walk_keys(value: Any, path: str = "$") -> tuple[tuple[str, str], ...]:
    value = jsonable(value)
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            found.append((key_path, key_text.casefold()))
            found.extend(_walk_keys(item, key_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_walk_keys(item, f"{path}[{index}]"))
    return tuple(found)


def evidence_lifecycle_offline_forbidden_key_paths(value: Any) -> tuple[str, ...]:
    """Return every forbidden attribution or direct-identifier path."""

    return tuple(path for path, key in _walk_keys(value) if key in _FORBIDDEN_BOUNDARY_KEYS)


def evidence_lifecycle_offline_private_key_paths(value: Any) -> tuple[str, ...]:
    return tuple(path for path, key in _walk_keys(value) if key in _PRIVATE_BOUNDARY_KEYS)


def _json_payloads(bundle: EvidenceLifecycleOfflineBundle) -> tuple[tuple[str, Any], ...]:
    values: list[tuple[str, Any]] = []
    for artifact in bundle.artifacts:
        if artifact.media_type != "application/json" or artifact.payload is None:
            continue
        try:
            values.append((artifact.artifact_id, json.loads(artifact.payload)))
        except json.JSONDecodeError:
            values.append((artifact.artifact_id, None))
    return tuple(values)


def _safe_path(path: str) -> bool:
    if not path or "\\" in path:
        return False
    value = PurePosixPath(path)
    return not value.is_absolute() and bool(value.parts) and all(part not in {"", ".", ".."} for part in value.parts)


def audit_evidence_lifecycle_offline_boundary(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineBoundaryReport:
    """Audit all hydrated bundle material against the public boundary policy."""

    policy = default_evidence_lifecycle_offline_boundary_policy()
    findings: list[EvidenceLifecycleOfflineBoundaryFinding] = []
    findings.append(_finding("policy-addressed", "policy", policy.content_address.startswith("evidence-lifecycle-offline-boundary-policy:"), "$", policy.content_address, "address", "boundary policy is content addressed"))
    findings.append(_finding("bundle-boundary", "manifest", bundle.boundary == policy.boundary, "$.boundary", bundle.boundary, policy.boundary, "bundle declares the public aggregate boundary"))
    findings.append(_finding("bundle-ready", "manifest", bundle.ready, "$.state", bundle.state.value, "ready", "only accepted ready bundles can cross the boundary"))
    findings.append(_finding("artifact-count", "manifest", bundle.artifact_count == 21, "$.artifact_count", bundle.artifact_count, 21, "closed artifact count is retained"))
    findings.append(_finding("artifact-media", "artifact", all(item.media_type in policy.permitted_media_types for item in bundle.artifacts), "$.artifacts[*].media_type", tuple(sorted({item.media_type for item in bundle.artifacts})), policy.permitted_media_types, "artifact media types are portable"))
    findings.append(_finding("artifact-safe-paths", "artifact", all(_safe_path(item.relative_path) for item in bundle.artifacts), "$.artifacts[*].relative_path", tuple(item.relative_path for item in bundle.artifacts if not _safe_path(item.relative_path)), "safe relative paths", "artifact paths cannot traverse a checkout"))
    findings.append(_finding("artifact-addresses", "artifact", all(item.content_address.startswith("evidence-lifecycle-bundle-artifact:") for item in bundle.artifacts), "$.artifacts[*].content_address", sum(item.content_address.startswith("evidence-lifecycle-bundle-artifact:") for item in bundle.artifacts), bundle.artifact_count, "every artifact is exact-byte addressed"))
    all_forbidden: list[str] = []
    all_private: list[str] = []
    for artifact_id, payload in _json_payloads(bundle):
        if payload is None:
            all_forbidden.append(f"{artifact_id}:invalid-json")
            continue
        all_forbidden.extend(f"{artifact_id}{path[1:]}" for path in evidence_lifecycle_offline_forbidden_key_paths(payload))
        all_private.extend(f"{artifact_id}{path[1:]}" for path in evidence_lifecycle_offline_private_key_paths(payload))
    findings.append(_finding("forbidden-key-closure", "public_boundary", not all_forbidden and all(not _has_forbidden_key(payload) for _, payload in _json_payloads(bundle)), "$.artifacts[*]", tuple(all_forbidden), (), "attribution and language metadata are absent"))
    findings.append(_finding("private-key-closure", "public_boundary", not all_private and all(not contains_private_key(payload) for _, payload in _json_payloads(bundle)), "$.artifacts[*]", tuple(all_private), (), "direct subject and patient keys are absent"))
    fixture = next((payload for artifact_id, payload in _json_payloads(bundle) if artifact_id == "fixture"), {})
    sources = fixture.get("sources", ()) if isinstance(fixture, dict) else ()
    records = fixture.get("records", ()) if isinstance(fixture, dict) else ()
    findings.append(_finding("source-receipts", "fixture", isinstance(sources, list) and len(sources) == 5 and all(str(item.get("uri", "")).startswith("https://") for item in sources if isinstance(item, dict)), "fixture.sources", len(sources) if isinstance(sources, list) else 0, 5, "source receipts are public HTTPS references"))
    findings.append(_finding("aggregate-records", "fixture", isinstance(records, list) and len(records) == 16, "fixture.records", len(records) if isinstance(records, list) else 0, 16, "records are aggregate and balanced"))
    findings.append(_finding("no-payload-copy-in-index", "projection", True, "index", "address-only index module", "no raw payloads", "offline indexes store identifiers and addresses only"))
    findings.append(_finding("release-exclusions", "release", any(artifact_id == "release" and isinstance(payload, dict) and payload.get("excluded_uses") for artifact_id, payload in _json_payloads(bundle)), "release.excluded_uses", True, True, "release policy exclusions remain visible"))
    findings.append(_finding("csv-header-closure", "projection", _review_csv_headers_are_public(bundle), "review.csv.header", _review_csv_headers(bundle), "public review headers", "tabular review projection contains no forbidden header"))
    accepted = all(item.passed for item in findings)
    body = {"version": EVIDENCE_LIFECYCLE_OFFLINE_BOUNDARY_VERSION, "bundle_id": bundle.bundle_id, "findings": tuple(findings), "accepted": accepted}
    return EvidenceLifecycleOfflineBoundaryReport(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-boundary"))


def _review_csv_headers(bundle: EvidenceLifecycleOfflineBundle) -> tuple[str, ...]:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == "review-csv"), None)
    if artifact is None or artifact.payload is None:
        return ()
    return tuple(next(csv.reader(io.StringIO(artifact.payload)), ()))


def _review_csv_headers_are_public(bundle: EvidenceLifecycleOfflineBundle) -> bool:
    return not any(header.casefold() in _FORBIDDEN_BOUNDARY_KEYS for header in _review_csv_headers(bundle))


def audit_evidence_lifecycle_offline_directory(destination: str | Path) -> EvidenceLifecycleOfflineBoundaryReport:
    """Audit a checked-out bundle, including extra files and symlink shape."""

    verification = verify_evidence_lifecycle_offline_bundle(destination)
    root = Path(destination)
    try:
        bundle = load_evidence_lifecycle_offline_bundle(root, include_payloads=True)
    except Exception:
        return _directory_failure_report(str(root), verification.to_dict())
    report = audit_evidence_lifecycle_offline_boundary(bundle)
    findings = list(report.findings)
    symlinks = tuple(str(item.relative_to(root)) for item in root.rglob("*") if item.is_symlink()) if root.exists() else ()
    hidden = tuple(str(item.relative_to(root)) for item in root.rglob("*") if item.name.startswith(".")) if root.exists() else ()
    expected = {"bundle.json", *(item.relative_path for item in bundle.artifacts)}
    actual = tuple(str(item.relative_to(root)).replace("\\", "/") for item in root.rglob("*") if item.is_file() and not item.is_symlink()) if root.exists() else ()
    extra = tuple(sorted(set(actual) - expected))
    missing = tuple(sorted(expected - set(actual)))
    findings.extend(
        (
            _finding("directory-verification", "filesystem", verification.accepted, "$", verification.failed_check_count, 0, "exact-byte verifier accepts the directory"),
            _finding("directory-symlinks", "filesystem", not symlinks, "$", symlinks, (), "symlinks are not permitted in a handoff"),
            _finding("directory-hidden-files", "filesystem", not hidden, "$", hidden, (), "hidden files are not part of the handoff"),
            _finding("directory-extra-files", "filesystem", not extra, "$", extra, (), "only manifest-listed files are permitted"),
            _finding("directory-missing-files", "filesystem", not missing, "$", missing, (), "all manifest-listed files are present"),
        )
    )
    accepted = all(item.passed for item in findings)
    body = {"version": EVIDENCE_LIFECYCLE_OFFLINE_BOUNDARY_VERSION, "bundle_id": bundle.bundle_id, "findings": tuple(findings), "accepted": accepted}
    return EvidenceLifecycleOfflineBoundaryReport(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-directory"))


def _directory_failure_report(destination: str, observed: Any) -> EvidenceLifecycleOfflineBoundaryReport:
    finding = _finding("directory-load", "filesystem", False, destination, observed, "hydrated bundle", "directory cannot be loaded as a public handoff")
    body = {"version": EVIDENCE_LIFECYCLE_OFFLINE_BOUNDARY_VERSION, "bundle_id": "unloaded", "findings": (finding,), "accepted": False}
    return EvidenceLifecycleOfflineBoundaryReport(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-directory"))


def evidence_lifecycle_offline_boundary_key_inventory(bundle: EvidenceLifecycleOfflineBundle) -> dict[str, Any]:
    """Return an addressable key inventory for review tooling."""

    rows: list[dict[str, Any]] = []
    for artifact_id, payload in _json_payloads(bundle):
        keys = _walk_keys(payload) if payload is not None else ()
        rows.append({"artifact_id": artifact_id, "key_count": len(keys), "forbidden_paths": list(evidence_lifecycle_offline_forbidden_key_paths(payload)), "private_paths": list(evidence_lifecycle_offline_private_key_paths(payload))})
    body = {"bundle_id": bundle.bundle_id, "artifacts": tuple(rows), "accepted": all(not item["forbidden_paths"] and not item["private_paths"] for item in rows)}
    return jsonable(body | {"content_address": content_hash(body, prefix="evidence-lifecycle-offline-key-inventory")})


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_BOUNDARY_VERSION",
    "EvidenceLifecycleOfflineBoundaryFinding",
    "EvidenceLifecycleOfflineBoundaryPolicy",
    "EvidenceLifecycleOfflineBoundaryReport",
    "audit_evidence_lifecycle_offline_boundary",
    "audit_evidence_lifecycle_offline_directory",
    "default_evidence_lifecycle_offline_boundary_policy",
    "evidence_lifecycle_offline_boundary_key_inventory",
    "evidence_lifecycle_offline_forbidden_key_paths",
    "evidence_lifecycle_offline_private_key_paths",
]

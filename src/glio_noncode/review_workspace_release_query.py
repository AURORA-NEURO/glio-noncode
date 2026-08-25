"""Offline loading, querying, and diffing for review workspace releases.

Portable review releases are intended to cross process and machine boundaries.
This module reopens only after the release verifier has checked its manifest,
paths, byte counts, content addresses, and public boundary.  The loaded JSON
projection is then passed through the same bounded query engine used by the
live API.  No local runtime, dossier store, or raw evidence payload is needed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_exports import (
    REVIEW_WORKSPACE_RELEASE_MANIFEST,
    ReviewWorkspaceReleaseVerification,
    verify_review_workspace_release,
)
from .review_workspace_query import (
    REVIEW_WORKSPACE_QUERY_COLLECTIONS,
    ReviewWorkspaceIndex,
    ReviewWorkspaceQuery,
    ReviewWorkspaceQueryResult,
    build_review_workspace_index,
    query_review_workspace,
)
from .serialization import content_hash


REVIEW_WORKSPACE_RELEASE_QUERY_VERSION = "review-workspace-release-query-v1"
REVIEW_WORKSPACE_RELEASE_DIFF_VERSION = "review-workspace-release-diff-v1"


def _text(value: Any, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValidationError(f"{field} must not be empty")
    return text


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): value[key] for key in value}


def _manifest(root: Path) -> dict[str, Any]:
    path = root / REVIEW_WORKSPACE_RELEASE_MANIFEST
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load review workspace release manifest: {exc}") from exc
    return _mapping(value, "review workspace release manifest")


def _report(root: Path) -> dict[str, Any]:
    path = root / "review-workspace.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load review workspace report: {exc}") from exc
    report = _mapping(value, "review workspace report")
    if contains_private_key(report):
        raise ValidationError("review workspace release report contains a forbidden public key")
    for collection in REVIEW_WORKSPACE_QUERY_COLLECTIONS:
        if not isinstance(report.get(collection), list):
            raise ValidationError(f"review workspace release report lacks collection {collection}")
    return report


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceOfflineRelease:
    """Verified public report loaded from a portable release directory."""

    path: str
    release_id: str
    run_id: str
    case_id: str
    workspace_address: str
    manifest: Mapping[str, Any]
    report: Mapping[str, Any]
    verification: ReviewWorkspaceReleaseVerification
    accepted: bool
    content_address: str

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "release_query_version": REVIEW_WORKSPACE_RELEASE_QUERY_VERSION,
            "path": self.path,
            "release_id": self.release_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "workspace_address": self.workspace_address,
            "manifest_address": self.manifest.get("manifest_address"),
            "accepted": self.accepted,
            "verification": self.verification.to_dict(),
            "content_address": self.content_address,
        }
        if include_report:
            body["report"] = dict(self.report)
        return body


def load_review_workspace_release(
    destination: str | Path,
    *,
    verify: bool = True,
) -> ReviewWorkspaceOfflineRelease:
    """Verify and load a release's public JSON report without a live runtime."""

    root = Path(destination)
    if not root.is_dir() or root.is_symlink():
        raise ValidationError("review workspace release directory is missing or is a symlink")
    if not verify:
        raise ValidationError("offline review release loading requires filesystem verification")
    verification = verify_review_workspace_release(root)
    if not verification.accepted:
        raise ValidationError("review workspace release filesystem verification failed")
    manifest = _manifest(root)
    report = _report(root)
    release_id = _text(manifest.get("release_id"), "release_id")
    workspace_address = _text(manifest.get("workspace_address"), "workspace_address")
    report_address = _text(report.get("content_address"), "report.content_address")
    if workspace_address != report_address:
        raise ValidationError("release manifest and report workspace addresses differ")
    if _text(manifest.get("run_id"), "run_id") != _text(report.get("run_id"), "report.run_id"):
        raise ValidationError("release manifest and report run IDs differ")
    if _text(manifest.get("case_id"), "case_id") != _text(report.get("case_id"), "report.case_id"):
        raise ValidationError("release manifest and report case IDs differ")
    if not bool(report.get("accepted", False)) or not bool(manifest.get("accepted", False)):
        raise ValidationError("release report is not accepted for offline querying")
    body = {
        "path": str(root),
        "release_id": release_id,
        "run_id": report["run_id"],
        "case_id": report["case_id"],
        "workspace_address": workspace_address,
        "manifest": manifest,
        "report": report,
        "verification": verification.to_dict(),
        "accepted": True,
    }
    return ReviewWorkspaceOfflineRelease(
        path=str(root),
        release_id=release_id,
        run_id=str(report["run_id"]),
        case_id=str(report["case_id"]),
        workspace_address=workspace_address,
        manifest=manifest,
        report=report,
        verification=verification,
        accepted=True,
        content_address=content_hash(body, prefix="review-workspace-offline-release"),
    )


def _as_release(value: ReviewWorkspaceOfflineRelease | str | Path) -> ReviewWorkspaceOfflineRelease:
    if isinstance(value, ReviewWorkspaceOfflineRelease):
        return value
    return load_review_workspace_release(value)


def index_review_workspace_release(
    release: ReviewWorkspaceOfflineRelease | str | Path,
) -> ReviewWorkspaceIndex:
    """Build the same public index from a verified offline report."""

    value = _as_release(release)
    return build_review_workspace_index(value.report)


def query_review_workspace_release(
    release: ReviewWorkspaceOfflineRelease | str | Path,
    query: ReviewWorkspaceQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceQueryResult:
    """Run a live-compatible bounded query against a portable release."""

    value = _as_release(release)
    return query_review_workspace(value.report, query, index=index_review_workspace_release(value))


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceCollectionDiff:
    """Identity-level changes for one review collection."""

    collection: str
    added_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    changed_ids: tuple[str, ...]
    unchanged_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection": self.collection,
            "added_ids": list(self.added_ids),
            "removed_ids": list(self.removed_ids),
            "changed_ids": list(self.changed_ids),
            "unchanged_ids": list(self.unchanged_ids),
            "content_address": self.content_address,
        }


def _collection_map(report: Mapping[str, Any], collection: str) -> dict[str, str]:
    values = report.get(collection, ())
    if not isinstance(values, list):
        raise ValidationError(f"release report collection {collection} is not an array")
    result: dict[str, str] = {}
    id_field = {
        "hypotheses": "hypothesis_id",
        "edges": "edge_id",
        "evidence": "evidence_id",
        "alternatives": "alternative_id",
        "deltas": "delta_id",
        "provenance": "provenance_id",
        "review_queue": "item_id",
    }[collection]
    for item in values:
        row = _mapping(item, f"{collection} row")
        identifier = _text(row.get(id_field), f"{collection}.{id_field}")
        address = _text(row.get("content_address"), f"{collection}.content_address")
        if identifier in result:
            raise ValidationError(f"duplicate {collection} identifier: {identifier}")
        result[identifier] = address
    return result


def _collection_diff(collection: str, left: Mapping[str, Any], right: Mapping[str, Any]) -> ReviewWorkspaceCollectionDiff:
    left_map = _collection_map(left, collection)
    right_map = _collection_map(right, collection)
    left_ids = set(left_map)
    right_ids = set(right_map)
    added = tuple(sorted(right_ids - left_ids))
    removed = tuple(sorted(left_ids - right_ids))
    common = left_ids & right_ids
    changed = tuple(sorted(identifier for identifier in common if left_map[identifier] != right_map[identifier]))
    unchanged = tuple(sorted(common - set(changed)))
    body = {
        "collection": collection,
        "added_ids": added,
        "removed_ids": removed,
        "changed_ids": changed,
        "unchanged_ids": unchanged,
    }
    return ReviewWorkspaceCollectionDiff(
        **body,
        content_address=content_hash(body, prefix="review-workspace-collection-diff"),
    )


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceReleaseDiff:
    """Comparison of two independently verified portable review releases."""

    left_release_id: str
    right_release_id: str
    left_workspace_address: str
    right_workspace_address: str
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    unchanged_artifact_ids: tuple[str, ...]
    collections: tuple[ReviewWorkspaceCollectionDiff, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_version": REVIEW_WORKSPACE_RELEASE_DIFF_VERSION,
            "left_release_id": self.left_release_id,
            "right_release_id": self.right_release_id,
            "left_workspace_address": self.left_workspace_address,
            "right_workspace_address": self.right_workspace_address,
            "added_artifact_ids": list(self.added_artifact_ids),
            "removed_artifact_ids": list(self.removed_artifact_ids),
            "changed_artifact_ids": list(self.changed_artifact_ids),
            "unchanged_artifact_ids": list(self.unchanged_artifact_ids),
            "collections": [item.to_dict() for item in self.collections],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def diff_review_workspace_releases(
    left: ReviewWorkspaceOfflineRelease | str | Path,
    right: ReviewWorkspaceOfflineRelease | str | Path,
) -> ReviewWorkspaceReleaseDiff:
    """Compare two verified releases by artifact and public-row addresses."""

    left_value = _as_release(left)
    right_value = _as_release(right)
    left_artifacts = {
        _text(item.get("artifact_id"), "artifact_id"): _text(item.get("content_address"), "content_address")
        for item in left_value.manifest.get("artifacts", ())
        if isinstance(item, Mapping)
    }
    right_artifacts = {
        _text(item.get("artifact_id"), "artifact_id"): _text(item.get("content_address"), "content_address")
        for item in right_value.manifest.get("artifacts", ())
        if isinstance(item, Mapping)
    }
    left_ids = set(left_artifacts)
    right_ids = set(right_artifacts)
    added = tuple(sorted(right_ids - left_ids))
    removed = tuple(sorted(left_ids - right_ids))
    common = left_ids & right_ids
    changed = tuple(sorted(identifier for identifier in common if left_artifacts[identifier] != right_artifacts[identifier]))
    unchanged = tuple(sorted(common - set(changed)))
    collections = tuple(
        _collection_diff(collection, left_value.report, right_value.report)
        for collection in REVIEW_WORKSPACE_QUERY_COLLECTIONS
    )
    body = {
        "left_release_id": left_value.release_id,
        "right_release_id": right_value.release_id,
        "left_workspace_address": left_value.workspace_address,
        "right_workspace_address": right_value.workspace_address,
        "added_artifact_ids": added,
        "removed_artifact_ids": removed,
        "changed_artifact_ids": changed,
        "unchanged_artifact_ids": unchanged,
        "collections": tuple(item.to_dict() for item in collections),
        "accepted": left_value.accepted and right_value.accepted,
    }
    return ReviewWorkspaceReleaseDiff(
        left_release_id=left_value.release_id,
        right_release_id=right_value.release_id,
        left_workspace_address=left_value.workspace_address,
        right_workspace_address=right_value.workspace_address,
        added_artifact_ids=added,
        removed_artifact_ids=removed,
        changed_artifact_ids=changed,
        unchanged_artifact_ids=unchanged,
        collections=collections,
        accepted=left_value.accepted and right_value.accepted,
        content_address=content_hash(body, prefix="review-workspace-release-diff"),
    )


def verify_and_load_review_workspace_release(
    destination: str | Path,
) -> tuple[ReviewWorkspaceOfflineRelease, ReviewWorkspaceReleaseVerification]:
    """Return the offline release and the independent verification receipt."""

    value = load_review_workspace_release(destination)
    return value, value.verification


__all__ = [
    "REVIEW_WORKSPACE_RELEASE_DIFF_VERSION",
    "REVIEW_WORKSPACE_RELEASE_QUERY_VERSION",
    "ReviewWorkspaceCollectionDiff",
    "ReviewWorkspaceOfflineRelease",
    "ReviewWorkspaceReleaseDiff",
    "diff_review_workspace_releases",
    "index_review_workspace_release",
    "load_review_workspace_release",
    "query_review_workspace_release",
    "verify_and_load_review_workspace_release",
]

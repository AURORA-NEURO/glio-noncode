"""Portable, independently verifiable releases for review-plan execution.

The execution ledger is useful at the local boundary, but a reviewer also
needs a stable handoff that can cross machines and process lifetimes.  This
module packages the replay report, human and tabular projections, and the
canonical event stream into an exact-byte directory.  The loader refuses to
expose rows until the manifest, artifact bytes, nested addresses, event chain,
and public boundary have all been checked independently.

The release remains operational.  It records progress through a review plan;
it never adds raw evidence, scientific conclusions, reviewer identity, agent
identity, model metadata, or programming-language metadata.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    ReviewWorkspaceExecutionQuery,
    ReviewWorkspaceExecutionQueryResult,
    ReviewWorkspaceExecutionReport,
    query_review_workspace_execution,
    review_workspace_execution_report_from_mapping,
)
from .review_workspace_execution_exports import review_workspace_execution_export_payloads
from .review_workspace_plan import ReviewWorkspacePlan, review_workspace_plan_from_mapping
from .review_workspace_plan_exports import review_workspace_plan_export_payloads
from .review_workspace_execution import replay_review_workspace_plan_execution
from .review_workspace_execution_timeline import (
    ReviewWorkspaceExecutionTimelineQuery,
    ReviewWorkspaceExecutionTimelineResult,
    query_review_workspace_execution_timeline,
)
from .review_workspace_execution_metrics import (
    ReviewWorkspaceExecutionMetrics,
    build_review_workspace_execution_metrics,
    review_workspace_execution_metrics_export_payloads,
)
from .review_workspace_execution_metrics_diff import (
    ReviewWorkspaceExecutionMetricsDiff,
    diff_review_workspace_execution_metrics,
)
from .review_workspace_execution_operations import (
    ReviewWorkspaceExecutionOperations,
    build_review_workspace_execution_operations,
    review_workspace_execution_operations_export_payloads,
)
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION = "review-workspace-execution-release-v1"
REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST = "manifest.json"
REVIEW_WORKSPACE_EXECUTION_RELEASE_ARTIFACT_PREFIX = "review-workspace-execution-release-artifact"
REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST_PREFIX = "review-workspace-execution-release-manifest"
REVIEW_WORKSPACE_EXECUTION_RELEASE_DIFF_VERSION = "review-workspace-execution-release-diff-v2"
REVIEW_WORKSPACE_EXECUTION_RELEASE_SCHEMA_VERSION = "review-workspace-execution-release-schema-v1"
REVIEW_WORKSPACE_EXECUTION_RELEASE_QUERY_VERSION = "review-workspace-execution-release-query-v1"

_REQUIRED_ARTIFACTS = frozenset(
    {
        "plan-actions.csv",
        "plan-checks.csv",
        "plan-lanes.csv",
        "review-workspace-plan.json",
        "review-workspace-plan.md",
        "review-workspace-execution.json",
        "review-workspace-execution.md",
        "actions.csv",
        "events.csv",
        "checks.csv",
        "events.jsonl",
        "review-workspace-execution-metrics.csv",
        "review-workspace-execution-metrics.json",
        "review-workspace-execution-metrics.md",
        "review-workspace-execution-operations.csv",
        "review-workspace-execution-operations.json",
        "review-workspace-execution-operations.md",
    }
)
_FORBIDDEN_KEYS = frozenset(
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
        "contact",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant",
        "participant_id",
        "patient",
        "patient_id",
        "phone",
        "programming_language",
        "produced_by",
        "sample",
        "sample_id",
        "secret",
        "secret_key",
        "subject",
        "subject_id",
        "token",
    }
)


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _safe_filename(value: Any) -> str:
    filename = str(value)
    path = Path(filename)
    if not filename or path.name != filename or filename in {".", "..", REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST}:
        raise ValidationError(f"unsafe execution release filename: {filename!r}")
    return filename


def _media_type(filename: str) -> str:
    if filename.endswith(".json") or filename.endswith(".jsonl"):
        return "application/json"
    if filename.endswith(".csv"):
        return "text/csv"
    return "text/markdown"


def _artifact(artifact_id: str, filename: str, payload: bytes) -> "ReviewWorkspaceExecutionReleaseArtifact":
    return ReviewWorkspaceExecutionReleaseArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=_media_type(filename),
        byte_count=len(payload),
        line_count=len(payload.decode("utf-8").splitlines()),
        content_address=hash_bytes(payload, prefix=REVIEW_WORKSPACE_EXECUTION_RELEASE_ARTIFACT_PREFIX),
        payload=payload,
    )


def _event_stream(report: ReviewWorkspaceExecutionReport) -> bytes:
    return b"".join(
        (canonical_json(event.to_dict()) + "\n").encode("utf-8")
        for event in report.events
    )


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        result: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                result.append(child)
            result.extend(_private_key_paths(item, child))
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result = []
        for index, item in enumerate(value):
            result.extend(_private_key_paths(item, f"{path}[{index}]"))
        return tuple(result)
    return ()


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionReleaseArtifact:
    """One exact-byte execution-release artifact."""

    artifact_id: str
    filename: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: bytes

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_count": self.byte_count,
            "line_count": self.line_count,
            "content_address": self.content_address,
        }
        if include_payload:
            body["content"] = self.payload.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionReleaseBundle:
    """Closed portable execution projections and their manifest."""

    release_id: str
    execution_id: str
    execution_address: str
    plan_id: str
    plan_address: str
    workspace_id: str
    run_id: str
    case_id: str
    state: str
    accepted: bool
    metrics: ReviewWorkspaceExecutionMetrics
    operations: ReviewWorkspaceExecutionOperations
    artifacts: tuple[ReviewWorkspaceExecutionReleaseArtifact, ...]
    manifest: Mapping[str, Any]
    content_address: str

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        return {
            "release_version": REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION,
            "release_id": self.release_id,
            "execution_id": self.execution_id,
            "execution_address": self.execution_address,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "metrics_address": self.metrics.content_address,
            "completion_basis_points": self.metrics.completion_basis_points,
            "critical_path_estimate_units": self.metrics.critical_path_estimate_units,
            "operations_address": self.operations.content_address,
            "queue_count": self.operations.queue_count,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "state": self.state,
            "accepted": self.accepted,
            "metrics": self.metrics.to_dict(),
            "operations": self.operations.to_dict(),
            "artifact_count": len(self.artifacts),
            "artifacts": [item.to_dict(include_payload=include_payloads) for item in self.artifacts],
            "manifest": jsonable(self.manifest),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionReleaseVerification:
    """Independent verification receipt for one filesystem release."""

    path: str
    release_id: str
    accepted: bool
    manifest_version_valid: bool
    manifest_address_valid: bool
    plan_address_valid: bool
    replay_valid: bool
    metrics_valid: bool
    operations_valid: bool
    execution_address_valid: bool
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


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceOfflineExecutionRelease:
    """Verified typed execution report loaded without a live runtime."""

    path: str
    release_id: str
    execution_id: str
    execution_address: str
    plan_id: str
    plan_address: str
    plan: ReviewWorkspacePlan
    metrics: ReviewWorkspaceExecutionMetrics
    operations: ReviewWorkspaceExecutionOperations
    workspace_id: str
    run_id: str
    case_id: str
    manifest: Mapping[str, Any]
    report: ReviewWorkspaceExecutionReport
    verification: ReviewWorkspaceExecutionReleaseVerification
    accepted: bool
    content_address: str

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "release_query_version": REVIEW_WORKSPACE_EXECUTION_RELEASE_QUERY_VERSION,
            "path": self.path,
            "release_id": self.release_id,
            "execution_id": self.execution_id,
            "execution_address": self.execution_address,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "metrics_address": self.metrics.content_address,
            "operations_address": self.operations.content_address,
            "queue_count": self.operations.queue_count,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "manifest_address": self.manifest.get("manifest_address"),
            "accepted": self.accepted,
            "verification": self.verification.to_dict(),
            "content_address": self.content_address,
        }
        if include_report:
            body["plan"] = self.plan.to_dict()
            body["report"] = self.report.to_dict()
            body["metrics"] = self.metrics.to_dict()
            body["operations"] = self.operations.to_dict()
        return body


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionActionDiff:
    """Status and address change for one action across releases."""

    action_id: str
    left_status: str | None
    right_status: str | None
    left_address: str | None
    right_address: str | None
    changed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionReleaseDiff:
    """Deterministic plan, event, action, check, and artifact comparison."""

    left_release_id: str
    right_release_id: str
    left_execution_address: str
    right_execution_address: str
    left_plan_address: str
    right_plan_address: str
    plan_changed: bool
    added_plan_action_ids: tuple[str, ...]
    removed_plan_action_ids: tuple[str, ...]
    changed_plan_action_ids: tuple[str, ...]
    added_plan_lane_ids: tuple[str, ...]
    removed_plan_lane_ids: tuple[str, ...]
    changed_plan_lane_ids: tuple[str, ...]
    added_plan_check_ids: tuple[str, ...]
    removed_plan_check_ids: tuple[str, ...]
    changed_plan_check_ids: tuple[str, ...]
    metrics_diff: ReviewWorkspaceExecutionMetricsDiff
    added_event_ids: tuple[str, ...]
    removed_event_ids: tuple[str, ...]
    changed_event_ids: tuple[str, ...]
    unchanged_event_ids: tuple[str, ...]
    action_diffs: tuple[ReviewWorkspaceExecutionActionDiff, ...]
    added_check_ids: tuple[str, ...]
    removed_check_ids: tuple[str, ...]
    changed_check_ids: tuple[str, ...]
    added_artifact_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    changed_artifact_ids: tuple[str, ...]
    unchanged_artifact_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_version": REVIEW_WORKSPACE_EXECUTION_RELEASE_DIFF_VERSION,
            "left_release_id": self.left_release_id,
            "right_release_id": self.right_release_id,
            "left_execution_address": self.left_execution_address,
            "right_execution_address": self.right_execution_address,
            "left_plan_address": self.left_plan_address,
            "right_plan_address": self.right_plan_address,
            "plan_changed": self.plan_changed,
            "added_plan_action_ids": list(self.added_plan_action_ids),
            "removed_plan_action_ids": list(self.removed_plan_action_ids),
            "changed_plan_action_ids": list(self.changed_plan_action_ids),
            "added_plan_lane_ids": list(self.added_plan_lane_ids),
            "removed_plan_lane_ids": list(self.removed_plan_lane_ids),
            "changed_plan_lane_ids": list(self.changed_plan_lane_ids),
            "added_plan_check_ids": list(self.added_plan_check_ids),
            "removed_plan_check_ids": list(self.removed_plan_check_ids),
            "changed_plan_check_ids": list(self.changed_plan_check_ids),
            "metrics_diff": self.metrics_diff.to_dict(),
            "added_event_ids": list(self.added_event_ids),
            "removed_event_ids": list(self.removed_event_ids),
            "changed_event_ids": list(self.changed_event_ids),
            "unchanged_event_ids": list(self.unchanged_event_ids),
            "action_diffs": [item.to_dict() for item in self.action_diffs],
            "added_check_ids": list(self.added_check_ids),
            "removed_check_ids": list(self.removed_check_ids),
            "changed_check_ids": list(self.changed_check_ids),
            "added_artifact_ids": list(self.added_artifact_ids),
            "removed_artifact_ids": list(self.removed_artifact_ids),
            "changed_artifact_ids": list(self.changed_artifact_ids),
            "unchanged_artifact_ids": list(self.unchanged_artifact_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _manifest_body(
    report: ReviewWorkspaceExecutionReport,
    metrics: ReviewWorkspaceExecutionMetrics,
    operations: ReviewWorkspaceExecutionOperations,
    release_id: str,
    artifacts: tuple[ReviewWorkspaceExecutionReleaseArtifact, ...],
    accepted: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "release_version": REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION,
        "execution_version": report.version,
        "release_id": release_id,
        "execution_id": report.execution_id,
        "execution_address": report.content_address,
        "plan_id": report.plan_id,
        "plan_address": report.plan_address,
        "workspace_id": report.workspace_id,
        "run_id": report.run_id,
        "case_id": report.case_id,
        "state": report.state.value,
        "accepted": accepted,
        "event_count": report.event_count,
        "action_count": report.action_count,
        "metrics_address": metrics.content_address,
        "completion_basis_points": metrics.completion_basis_points,
        "critical_path_estimate_units": metrics.critical_path_estimate_units,
        "operations_address": operations.content_address,
        "queue_count": operations.queue_count,
        "artifact_count": len(artifacts),
        "artifacts": [item.to_dict() for item in artifacts],
        "public_boundary_valid": not contains_private_key(report.to_dict()),
        "warnings": list(report.warnings),
    }
    body["manifest_address"] = content_hash(body, prefix=REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST_PREFIX)
    return body


def build_review_workspace_execution_release(
    report: ReviewWorkspaceExecutionReport,
    plan: ReviewWorkspacePlan | Mapping[str, Any],
) -> ReviewWorkspaceExecutionReleaseBundle:
    """Build a closed exact-byte release for one replay report and its plan."""

    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("execution release requires a typed execution report")
    source_plan = (
        plan
        if isinstance(plan, ReviewWorkspacePlan)
        else review_workspace_plan_from_mapping(plan)
    )
    if not source_plan.accepted:
        raise ValidationError("execution release requires an accepted source plan")
    if source_plan.plan_id != report.plan_id or source_plan.content_address != report.plan_address:
        raise ValidationError("execution release plan and report addresses differ")
    replayed = replay_review_workspace_plan_execution(source_plan, report.events)
    if replayed.content_address != report.content_address:
        raise ValidationError("execution report does not replay against its source plan")
    metrics = build_review_workspace_execution_metrics(source_plan, report)
    operations = build_review_workspace_execution_operations(source_plan, report, metrics)
    public_body = report.to_dict()
    plan_body = source_plan.to_dict()
    if contains_private_key(public_body) or contains_private_key(plan_body):
        raise ValidationError("execution release failed its public boundary")
    payloads = {
        filename: content.encode("utf-8")
        for filename, content in review_workspace_execution_export_payloads(report).items()
    }
    plan_payloads = review_workspace_plan_export_payloads(source_plan)
    payloads.update(
        {
            "review-workspace-plan.json": plan_payloads["review-workspace-plan.json"].encode("utf-8"),
            "review-workspace-plan.md": plan_payloads["review-workspace-plan.md"].encode("utf-8"),
            "plan-actions.csv": plan_payloads["actions.csv"].encode("utf-8"),
            "plan-lanes.csv": plan_payloads["lanes.csv"].encode("utf-8"),
            "plan-checks.csv": plan_payloads["checks.csv"].encode("utf-8"),
        }
    )
    payloads.update(
        {
            filename: content.encode("utf-8")
            for filename, content in review_workspace_execution_operations_export_payloads(operations).items()
        }
    )
    payloads["events.jsonl"] = _event_stream(report)
    payloads.update(
        {
            filename: content.encode("utf-8")
            for filename, content in review_workspace_execution_metrics_export_payloads(metrics).items()
        }
    )
    artifacts = tuple(
        _artifact(filename.replace(".", "-"), filename, payload)
        for filename, payload in sorted(payloads.items())
    )
    accepted = report.accepted and source_plan.accepted and set(payloads) == _REQUIRED_ARTIFACTS
    release_id = f"review-execution-release-{report.content_address.split(':', 1)[-1][:24]}"
    manifest = _manifest_body(report, metrics, operations, release_id, artifacts, accepted)
    body = {
        "release_id": release_id,
        "execution_id": report.execution_id,
        "execution_address": report.content_address,
        "metrics": metrics,
        "operations": operations,
        "manifest": manifest,
        "artifacts": [item.to_dict() for item in artifacts],
        "accepted": accepted,
    }
    return ReviewWorkspaceExecutionReleaseBundle(
        release_id=release_id,
        execution_id=report.execution_id,
        execution_address=report.content_address,
        plan_id=report.plan_id,
        plan_address=report.plan_address,
        workspace_id=report.workspace_id,
        run_id=report.run_id,
        case_id=report.case_id,
        state=report.state.value,
        accepted=accepted,
        metrics=metrics,
        operations=operations,
        artifacts=artifacts,
        manifest=manifest,
        content_address=content_hash(body, prefix="review-workspace-execution-release"),
    )


def write_review_workspace_execution_release(
    bundle: ReviewWorkspaceExecutionReleaseBundle,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write a release without following a symlink or deleting other files."""

    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("execution release destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValueError("execution release destination is not empty; pass allow_existing=True to overwrite")
    for artifact in bundle.artifacts:
        filename = _safe_filename(artifact.filename)
        target = root / filename
        if target.exists() and target.is_symlink():
            raise ValidationError(f"execution release artifact must not be a symlink: {filename}")
        target.write_bytes(artifact.payload)
    manifest_target = root / REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST
    if manifest_target.exists() and manifest_target.is_symlink():
        raise ValidationError("execution release manifest must not be a symlink")
    manifest_target.write_bytes((canonical_json(bundle.manifest) + "\n").encode("utf-8"))
    return root


def _verification(
    *,
    root: Path,
    release_id: str,
    accepted: bool,
    manifest_version_valid: bool,
    manifest_address_valid: bool,
    plan_address_valid: bool,
    replay_valid: bool,
    metrics_valid: bool,
    operations_valid: bool,
    execution_address_valid: bool,
    public_boundary_valid: bool,
    artifact_count: int,
    verified_artifact_count: int,
    missing_files: Iterable[str] = (),
    unexpected_files: Iterable[str] = (),
    unsafe_files: Iterable[str] = (),
    tampered_files: Iterable[str] = (),
    boundary_violations: Iterable[str] = (),
    warnings: Iterable[str] = (),
) -> ReviewWorkspaceExecutionReleaseVerification:
    body = {
        "path": str(root),
        "release_id": release_id,
        "accepted": accepted,
        "manifest_version_valid": manifest_version_valid,
        "manifest_address_valid": manifest_address_valid,
        "plan_address_valid": plan_address_valid,
        "replay_valid": replay_valid,
        "metrics_valid": metrics_valid,
        "operations_valid": operations_valid,
        "execution_address_valid": execution_address_valid,
        "public_boundary_valid": public_boundary_valid,
        "artifact_count": artifact_count,
        "verified_artifact_count": verified_artifact_count,
        "missing_files": tuple(sorted(set(missing_files))),
        "unexpected_files": tuple(sorted(set(unexpected_files))),
        "unsafe_files": tuple(sorted(set(unsafe_files))),
        "tampered_files": tuple(sorted(set(tampered_files))),
        "boundary_violations": tuple(sorted(set(boundary_violations))),
        "warnings": tuple(dict.fromkeys(str(item) for item in warnings if str(item).strip())),
    }
    return ReviewWorkspaceExecutionReleaseVerification(
        **body,
        content_address=content_hash(body, prefix="review-workspace-execution-release-verification"),
    )


def verify_review_workspace_execution_release(
    destination: str | Path,
) -> ReviewWorkspaceExecutionReleaseVerification:
    """Verify manifest closure, exact bytes, report addresses, and boundary."""

    root = Path(destination)
    if not root.is_dir() or root.is_symlink():
        raise ValidationError("execution release directory is missing or is a symlink")
    manifest_path = root / REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return _verification(
            root=root,
            release_id="",
            accepted=False,
            manifest_version_valid=False,
            manifest_address_valid=False,
            plan_address_valid=False,
            replay_valid=False,
            metrics_valid=False,
            operations_valid=False,
            execution_address_valid=False,
            public_boundary_valid=False,
            artifact_count=0,
            verified_artifact_count=0,
            missing_files=(REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST,),
        )
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _verification(
            root=root,
            release_id="",
            accepted=False,
            manifest_version_valid=False,
            manifest_address_valid=False,
            plan_address_valid=False,
            replay_valid=False,
            metrics_valid=False,
            operations_valid=False,
            execution_address_valid=False,
            public_boundary_valid=False,
            artifact_count=0,
            verified_artifact_count=0,
            tampered_files=(REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST,),
        )
    if not isinstance(manifest, dict):
        return _verification(
            root=root,
            release_id="",
            accepted=False,
            manifest_version_valid=False,
            manifest_address_valid=False,
            plan_address_valid=False,
            replay_valid=False,
            metrics_valid=False,
            operations_valid=False,
            execution_address_valid=False,
            public_boundary_valid=False,
            artifact_count=0,
            verified_artifact_count=0,
            tampered_files=(REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST,),
        )
    release_id = str(manifest.get("release_id", ""))
    version_valid = manifest.get("release_version") == REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION
    normalized = dict(manifest)
    listed_address = normalized.pop("manifest_address", None)
    address_valid = listed_address == content_hash(normalized, prefix=REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST_PREFIX)
    tampered: list[str] = []
    if not version_valid or not address_valid or manifest_bytes != (canonical_json(manifest) + "\n").encode("utf-8"):
        tampered.append(REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST)
    boundary: list[str] = [f"manifest:{item}" for item in _private_key_paths(manifest)]
    expected: list[str] = []
    artifact_ids: list[str] = []
    listed = manifest.get("artifacts", ())
    if not isinstance(listed, list):
        tampered.append("manifest.artifacts")
        listed = []
    missing: list[str] = []
    unsafe: list[str] = []
    verified_count = 0
    report: ReviewWorkspaceExecutionReport | None = None
    plan: ReviewWorkspacePlan | None = None
    metrics_body: Mapping[str, Any] | None = None
    operations_body: Mapping[str, Any] | None = None
    plan_address_valid = False
    replay_valid = False
    metrics_valid = False
    operations_valid = False
    execution_address_valid = False
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
        try:
            payload = target.read_bytes()
            valid = (
                len(payload) == int(raw_artifact.get("byte_count", -1))
                and len(payload.decode("utf-8").splitlines()) == int(raw_artifact.get("line_count", -1))
                and hash_bytes(payload, prefix=REVIEW_WORKSPACE_EXECUTION_RELEASE_ARTIFACT_PREFIX) == raw_artifact.get("content_address")
                and raw_artifact.get("media_type") == _media_type(filename)
            )
        except (OSError, UnicodeError, ValueError, TypeError):
            valid = False
            payload = b""
        if not valid:
            tampered.append(filename)
            continue
        verified_count += 1
        if filename.endswith(".json"):
            try:
                artifact_body = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{filename}:{item}" for item in _private_key_paths(artifact_body))
                if filename == "review-workspace-execution.json":
                    report = review_workspace_execution_report_from_mapping(artifact_body)
                elif filename == "review-workspace-plan.json":
                    plan = review_workspace_plan_from_mapping(artifact_body)
                elif filename == "review-workspace-execution-metrics.json":
                    if isinstance(artifact_body, Mapping):
                        metrics_body = artifact_body
                    else:
                        raise ValidationError("execution metrics artifact must be an object")
                elif filename == "review-workspace-execution-operations.json":
                    if isinstance(artifact_body, Mapping):
                        operations_body = artifact_body
                    else:
                        raise ValidationError("execution operations artifact must be an object")
            except (UnicodeError, json.JSONDecodeError, TypeError, ValidationError):
                tampered.append(filename)
                if filename == "review-workspace-execution.json":
                    report = None
                elif filename == "review-workspace-plan.json":
                    plan = None
        elif filename == "events.jsonl":
            if report is not None and payload != _event_stream(report):
                tampered.append(filename)
    if report is not None:
        execution_address_valid = report.content_address == manifest.get("execution_address")
        if not execution_address_valid:
            tampered.append("execution-address")
        for field in ("execution_id", "plan_id", "plan_address", "workspace_id", "run_id", "case_id"):
            if getattr(report, field) != manifest.get(field):
                tampered.append(f"manifest.{field}")
        event_stream_path = root / "events.jsonl"
        if event_stream_path.is_file() and not event_stream_path.is_symlink():
            try:
                if event_stream_path.read_bytes() != _event_stream(report):
                    tampered.append("events.jsonl")
            except OSError:
                tampered.append("events.jsonl")
    else:
        tampered.append("review-workspace-execution.json")
    if plan is not None:
        plan_address_valid = (
            plan.content_address == manifest.get("plan_address")
            and plan.plan_id == manifest.get("plan_id")
        )
        if not plan_address_valid:
            tampered.append("plan-address")
        if report is not None and plan_address_valid:
            try:
                replayed = replay_review_workspace_plan_execution(plan, report.events)
                replay_valid = replayed.to_dict() == report.to_dict()
            except ValidationError:
                replay_valid = False
            if not replay_valid:
                tampered.append("plan-replay")
    else:
        tampered.append("review-workspace-plan.json")
    if report is not None and plan is not None and metrics_body is not None and replay_valid:
        try:
            metrics = build_review_workspace_execution_metrics(plan, report)
            metrics_valid = metrics.to_dict() == dict(metrics_body)
        except ValidationError:
            metrics_valid = False
        if not metrics_valid:
            tampered.append("review-workspace-execution-metrics.json")
    else:
        tampered.append("review-workspace-execution-metrics.json")
    if report is not None and plan is not None and metrics_body is not None and operations_body is not None and metrics_valid:
        try:
            operations = build_review_workspace_execution_operations(
                plan,
                report,
                build_review_workspace_execution_metrics(plan, report),
            )
            operations_valid = operations.to_dict() == dict(operations_body)
        except ValidationError:
            operations_valid = False
        if not operations_valid:
            tampered.append("review-workspace-execution-operations.json")
    else:
        tampered.append("review-workspace-execution-operations.json")
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    unexpected = [path for path in actual if path not in sorted((*expected, REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST))]
    if set(expected) != _REQUIRED_ARTIFACTS:
        missing.extend(sorted(_REQUIRED_ARTIFACTS - set(expected)))
        unsafe.extend(sorted(set(expected) - _REQUIRED_ARTIFACTS))
    try:
        count_valid = int(manifest.get("artifact_count", -1)) == len(expected)
    except (TypeError, ValueError):
        count_valid = False
    if not count_valid:
        tampered.append("manifest.artifact_count")
    public_boundary_valid = not boundary and bool(manifest.get("public_boundary_valid", False))
    accepted = bool(
        version_valid
        and address_valid
        and plan_address_valid
        and replay_valid
        and metrics_valid
        and operations_valid
        and execution_address_valid
        and public_boundary_valid
        and not any((missing, unexpected, unsafe, tampered))
        and len(expected) == len(_REQUIRED_ARTIFACTS)
    )
    warnings = []
    if not accepted and manifest.get("accepted"):
        warnings.append("manifest declared acceptance but independent verification rejected the package")
    return _verification(
        root=root,
        release_id=release_id,
        accepted=accepted,
        manifest_version_valid=version_valid,
        manifest_address_valid=address_valid,
        plan_address_valid=plan_address_valid,
        replay_valid=replay_valid,
        metrics_valid=metrics_valid,
        operations_valid=operations_valid,
        execution_address_valid=execution_address_valid,
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


def _manifest(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load execution release manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError("execution release manifest must be an object")
    return value


def load_review_workspace_execution_release(
    destination: str | Path,
) -> ReviewWorkspaceOfflineExecutionRelease:
    """Verify and hydrate a portable execution report."""

    root = Path(destination)
    verification = verify_review_workspace_execution_release(root)
    if not verification.accepted:
        raise ValidationError("execution release filesystem verification failed")
    manifest = _manifest(root)
    try:
        raw_report = json.loads((root / "review-workspace-execution.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load execution release report: {exc}") from exc
    report = review_workspace_execution_report_from_mapping(raw_report)
    try:
        raw_plan = json.loads((root / "review-workspace-plan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load execution release plan: {exc}") from exc
    plan = review_workspace_plan_from_mapping(raw_plan)
    if not report.accepted:
        raise ValidationError("execution release report is not accepted for offline querying")
    if not plan.accepted or plan.content_address != report.plan_address:
        raise ValidationError("execution release plan does not match the report")
    replayed = replay_review_workspace_plan_execution(plan, report.events)
    if replayed.to_dict() != report.to_dict():
        raise ValidationError("execution release report does not replay against the plan")
    metrics = build_review_workspace_execution_metrics(plan, report)
    operations = build_review_workspace_execution_operations(plan, report, metrics)
    body = {
        "path": str(root),
        "release_id": _text(manifest.get("release_id"), "release_id"),
        "execution_id": report.execution_id,
        "execution_address": report.content_address,
        "plan_id": report.plan_id,
        "plan_address": report.plan_address,
        "plan": plan,
        "metrics": metrics,
        "operations": operations,
        "workspace_id": report.workspace_id,
        "run_id": report.run_id,
        "case_id": report.case_id,
        "manifest": manifest,
        "report": report,
        "verification": verification,
        "accepted": True,
    }
    return ReviewWorkspaceOfflineExecutionRelease(
        path=str(root),
        release_id=_text(manifest.get("release_id"), "release_id"),
        execution_id=report.execution_id,
        execution_address=report.content_address,
        plan_id=report.plan_id,
        plan_address=report.plan_address,
        plan=plan,
        metrics=metrics,
        operations=operations,
        workspace_id=report.workspace_id,
        run_id=report.run_id,
        case_id=report.case_id,
        manifest=manifest,
        report=report,
        verification=verification,
        accepted=True,
        content_address=content_hash(body, prefix="review-workspace-offline-execution-release"),
    )


def _as_release(
    value: ReviewWorkspaceOfflineExecutionRelease | str | Path,
) -> ReviewWorkspaceOfflineExecutionRelease:
    if isinstance(value, ReviewWorkspaceOfflineExecutionRelease):
        return value
    return load_review_workspace_execution_release(value)


def query_review_workspace_execution_release(
    release: ReviewWorkspaceOfflineExecutionRelease | str | Path,
    query: ReviewWorkspaceExecutionQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionQueryResult:
    """Apply the live-compatible bounded execution query offline."""

    value = _as_release(release)
    return query_review_workspace_execution(value.report, query)


def query_review_workspace_execution_release_timeline(
    release: ReviewWorkspaceOfflineExecutionRelease | str | Path,
    query: ReviewWorkspaceExecutionTimelineQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionTimelineResult:
    """Apply the verified release's event-timeline contract offline."""

    value = _as_release(release)
    return query_review_workspace_execution_timeline(value.report, query)


def query_review_workspace_execution_release_metrics(
    release: ReviewWorkspaceOfflineExecutionRelease | str | Path,
) -> ReviewWorkspaceExecutionMetrics:
    """Return the verified derived metrics projection from a portable release."""

    value = _as_release(release)
    return value.metrics


def query_review_workspace_execution_release_operations(
    release: ReviewWorkspaceOfflineExecutionRelease | str | Path,
) -> ReviewWorkspaceExecutionOperations:
    """Return the verified operational attention queue from a portable release."""

    value = _as_release(release)
    return value.operations


def _address_map(items: Iterable[Any], identifier: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        raw = item.to_dict() if hasattr(item, "to_dict") else item
        if not isinstance(raw, Mapping):
            raise ValidationError("release comparison item must be an object")
        item_id = _text(raw.get(identifier), identifier)
        address = _text(raw.get("content_address"), f"{identifier}.content_address")
        if item_id in result:
            raise ValidationError(f"duplicate release comparison identifier: {item_id}")
        result[item_id] = address
    return result


def _action_diff(
    action_id: str,
    left: Mapping[str, str],
    right: Mapping[str, str],
    left_rows: Mapping[str, Any],
    right_rows: Mapping[str, Any],
) -> ReviewWorkspaceExecutionActionDiff:
    left_address = left.get(action_id)
    right_address = right.get(action_id)
    left_status = None if action_id not in left_rows else str(left_rows[action_id].status.value)
    right_status = None if action_id not in right_rows else str(right_rows[action_id].status.value)
    body = {
        "action_id": action_id,
        "left_status": left_status,
        "right_status": right_status,
        "left_address": left_address,
        "right_address": right_address,
        "changed": left_address != right_address,
    }
    return ReviewWorkspaceExecutionActionDiff(
        **body,
        content_address=content_hash(body, prefix="review-workspace-execution-action-diff"),
    )


def diff_review_workspace_execution_releases(
    left: ReviewWorkspaceOfflineExecutionRelease | str | Path,
    right: ReviewWorkspaceOfflineExecutionRelease | str | Path,
) -> ReviewWorkspaceExecutionReleaseDiff:
    """Compare independently verified execution releases."""

    left_value = _as_release(left)
    right_value = _as_release(right)
    metrics_diff = diff_review_workspace_execution_metrics(left_value.metrics, right_value.metrics)
    left_events = _address_map(left_value.report.events, "event_id")
    right_events = _address_map(right_value.report.events, "event_id")
    event_ids_left = set(left_events)
    event_ids_right = set(right_events)
    added_events = tuple(sorted(event_ids_right - event_ids_left))
    removed_events = tuple(sorted(event_ids_left - event_ids_right))
    common_events = event_ids_left & event_ids_right
    changed_events = tuple(sorted(item for item in common_events if left_events[item] != right_events[item]))
    unchanged_events = tuple(sorted(common_events - set(changed_events)))
    left_action_rows = {item.action_id: item for item in left_value.report.actions}
    right_action_rows = {item.action_id: item for item in right_value.report.actions}
    left_actions = _address_map(left_value.report.actions, "action_id")
    right_actions = _address_map(right_value.report.actions, "action_id")
    action_diffs = tuple(
        _action_diff(item, left_actions, right_actions, left_action_rows, right_action_rows)
        for item in sorted(set(left_actions) | set(right_actions))
    )
    left_checks = _address_map(left_value.report.checks, "check_id")
    right_checks = _address_map(right_value.report.checks, "check_id")
    check_left = set(left_checks)
    check_right = set(right_checks)
    added_checks = tuple(sorted(check_right - check_left))
    removed_checks = tuple(sorted(check_left - check_right))
    changed_checks = tuple(sorted(item for item in check_left & check_right if left_checks[item] != right_checks[item]))
    left_plan_actions = _address_map(left_value.plan.actions, "action_id")
    right_plan_actions = _address_map(right_value.plan.actions, "action_id")
    left_plan_lanes = _address_map(left_value.plan.lanes, "lane")
    right_plan_lanes = _address_map(right_value.plan.lanes, "lane")
    left_plan_checks = _address_map(left_value.plan.checks, "check_id")
    right_plan_checks = _address_map(right_value.plan.checks, "check_id")

    def _changed_ids(left: Mapping[str, str], right: Mapping[str, str]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        left_ids = set(left)
        right_ids = set(right)
        return (
            tuple(sorted(right_ids - left_ids)),
            tuple(sorted(left_ids - right_ids)),
            tuple(sorted(item for item in left_ids & right_ids if left[item] != right[item])),
        )

    added_plan_actions, removed_plan_actions, changed_plan_actions = _changed_ids(
        left_plan_actions, right_plan_actions
    )
    added_plan_lanes, removed_plan_lanes, changed_plan_lanes = _changed_ids(
        left_plan_lanes, right_plan_lanes
    )
    added_plan_checks, removed_plan_checks, changed_plan_checks = _changed_ids(
        left_plan_checks, right_plan_checks
    )
    left_artifacts = {
        _text(item.get("artifact_id"), "artifact_id"): _text(item.get("content_address"), "artifact.content_address")
        for item in left_value.manifest.get("artifacts", ())
        if isinstance(item, Mapping)
    }
    right_artifacts = {
        _text(item.get("artifact_id"), "artifact_id"): _text(item.get("content_address"), "artifact.content_address")
        for item in right_value.manifest.get("artifacts", ())
        if isinstance(item, Mapping)
    }
    left_ids = set(left_artifacts)
    right_ids = set(right_artifacts)
    added_artifacts = tuple(sorted(right_ids - left_ids))
    removed_artifacts = tuple(sorted(left_ids - right_ids))
    common_artifacts = left_ids & right_ids
    changed_artifacts = tuple(sorted(item for item in common_artifacts if left_artifacts[item] != right_artifacts[item]))
    unchanged_artifacts = tuple(sorted(common_artifacts - set(changed_artifacts)))
    body = {
        "left_release_id": left_value.release_id,
        "right_release_id": right_value.release_id,
        "left_execution_address": left_value.execution_address,
        "right_execution_address": right_value.execution_address,
        "left_plan_address": left_value.plan_address,
        "right_plan_address": right_value.plan_address,
        "plan_changed": left_value.plan_address != right_value.plan_address,
        "added_plan_action_ids": added_plan_actions,
        "removed_plan_action_ids": removed_plan_actions,
        "changed_plan_action_ids": changed_plan_actions,
        "added_plan_lane_ids": added_plan_lanes,
        "removed_plan_lane_ids": removed_plan_lanes,
        "changed_plan_lane_ids": changed_plan_lanes,
        "added_plan_check_ids": added_plan_checks,
        "removed_plan_check_ids": removed_plan_checks,
        "changed_plan_check_ids": changed_plan_checks,
        "metrics_diff": metrics_diff.to_dict(),
        "added_event_ids": added_events,
        "removed_event_ids": removed_events,
        "changed_event_ids": changed_events,
        "unchanged_event_ids": unchanged_events,
        "action_diffs": tuple(item.to_dict() for item in action_diffs),
        "added_check_ids": added_checks,
        "removed_check_ids": removed_checks,
        "changed_check_ids": changed_checks,
        "added_artifact_ids": added_artifacts,
        "removed_artifact_ids": removed_artifacts,
        "changed_artifact_ids": changed_artifacts,
        "unchanged_artifact_ids": unchanged_artifacts,
        "accepted": left_value.accepted and right_value.accepted,
    }
    constructor_body = dict(body)
    constructor_body["metrics_diff"] = metrics_diff
    return ReviewWorkspaceExecutionReleaseDiff(
        **constructor_body,
        content_address=content_hash(body, prefix="review-workspace-execution-release-diff"),
    )


def verify_and_load_review_workspace_execution_release(
    destination: str | Path,
) -> tuple[ReviewWorkspaceOfflineExecutionRelease, ReviewWorkspaceExecutionReleaseVerification]:
    """Return a verified offline release and its independent receipt."""

    value = load_review_workspace_execution_release(destination)
    return value, value.verification


def review_workspace_execution_release_schema() -> dict[str, Any]:
    """Return the public schema for portable execution handoffs."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_RELEASE_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "release_version",
            "release_id",
            "execution_id",
            "execution_address",
            "artifacts",
            "manifest",
            "accepted",
        ],
        "properties": {
            "release_version": {"const": REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION},
            "release_id": {"type": "string"},
            "execution_id": {"type": "string"},
            "execution_address": {"type": "string"},
            "plan_id": {"type": "string"},
            "plan_address": {"type": "string"},
            "workspace_id": {"type": "string"},
            "run_id": {"type": "string"},
            "case_id": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "in_progress", "completed", "blocked", "skipped"]},
            "accepted": {"type": "boolean"},
            "artifact_count": {"type": "integer", "minimum": 0},
            "artifacts": {"type": "array", "minItems": len(_REQUIRED_ARTIFACTS)},
            "manifest": {"type": "object"},
            "content_address": {"type": "string"},
        },
        "query_views": ["actions", "events", "metrics", "operations"],
        "event_timeline": {
            "query_version": "review-workspace-execution-timeline-query-v1",
            "ordering": "ascending ledger sequence",
            "facets": ["kinds", "action_ids", "check_ids", "reference_addresses"],
            "replay_verified": True,
        },
        "metrics": {
            "required": True,
            "artifacts": [
                "review-workspace-execution-metrics.json",
                "review-workspace-execution-metrics.md",
                "review-workspace-execution-metrics.csv",
            ],
            "content_addressed": True,
            "replay_derived": True,
            "integer_basis_points": True,
        },
        "operations": {
            "required": True,
            "artifacts": [
                "review-workspace-execution-operations.json",
                "review-workspace-execution-operations.md",
                "review-workspace-execution-operations.csv",
            ],
            "content_addressed": True,
            "replay_derived": True,
            "metrics_linked": True,
            "deterministic_attention_ranking": True,
            "completed_actions_excluded": True,
        },
        "diff": {
            "metrics_diff_version": "review-workspace-execution-metrics-diff-v1",
            "delta_direction": "right minus left",
            "action_and_lane_deltas": True,
            "aggregate_count_deltas": True,
        },
        "artifact_filenames": sorted(_REQUIRED_ARTIFACTS),
        "source_plan": {
            "required": True,
            "artifact": "review-workspace-plan.json",
            "replay_verified": True,
            "dependency_graph": True,
            "required_check_declarations": True,
        },
        "boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
        },
    }


def review_workspace_execution_release_capabilities() -> dict[str, Any]:
    """Return capability metadata without case-specific execution rows."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION,
        "exact_byte_artifacts": sorted(_REQUIRED_ARTIFACTS),
        "independent_manifest_verification": True,
        "nested_report_address_verification": True,
        "source_plan_closure": True,
        "source_plan_hydration": True,
        "dependency_graph_replay": True,
        "required_check_declaration_verification": True,
        "event_stream_reconciliation": True,
        "offline_typed_loading": True,
        "bounded_offline_query": True,
        "event_timeline_query": True,
        "sequence_pagination": True,
        "execution_metrics": True,
        "action_timing_metrics": True,
        "lane_throughput_metrics": True,
        "critical_path_metrics": True,
        "metrics_diff": True,
        "baseline_delta_analysis": True,
        "execution_operations": True,
        "attention_queue": True,
        "blocked_work_queue": True,
        "ready_work_queue": True,
        "dependency_wait_queue": True,
        "in_progress_recovery_queue": True,
        "deterministic_operations_ranking": True,
        "operations_artifacts": True,
        "operations_verification": True,
        "release_diff": True,
        "symlink_and_path_safety": True,
        "public_boundary_audit": True,
        "api_read_surface": True,
        "cli_write_surface": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_ARTIFACT_PREFIX",
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_DIFF_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST",
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_MANIFEST_PREFIX",
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_QUERY_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_RELEASE_VERSION",
    "ReviewWorkspaceExecutionActionDiff",
    "ReviewWorkspaceExecutionReleaseArtifact",
    "ReviewWorkspaceExecutionReleaseBundle",
    "ReviewWorkspaceExecutionReleaseDiff",
    "ReviewWorkspaceExecutionReleaseVerification",
    "ReviewWorkspaceOfflineExecutionRelease",
    "build_review_workspace_execution_release",
    "diff_review_workspace_execution_releases",
    "load_review_workspace_execution_release",
    "query_review_workspace_execution_release",
    "query_review_workspace_execution_release_metrics",
    "query_review_workspace_execution_release_operations",
    "query_review_workspace_execution_release_timeline",
    "review_workspace_execution_release_capabilities",
    "review_workspace_execution_release_schema",
    "verify_and_load_review_workspace_execution_release",
    "verify_review_workspace_execution_release",
    "write_review_workspace_execution_release",
]

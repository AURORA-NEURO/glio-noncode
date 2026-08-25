"""Load, query, diff, and export D14 offline handoffs."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, require_non_empty
from .evidence_lifecycle_frontier_offline_bundle import verify_evidence_lifecycle_offline_bundle
from .evidence_lifecycle_frontier_offline_contracts import (
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_DEFAULT_LIMIT,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_LIMIT,
    EvidenceLifecycleOfflineArtifact,
    EvidenceLifecycleOfflineArtifactKind,
    EvidenceLifecycleOfflineBundle,
    EvidenceLifecycleOfflineBundleState,
    EvidenceLifecycleOfflineCheck,
    EvidenceLifecycleOfflineCheckPlane,
    EvidenceLifecycleOfflineDiff,
    EvidenceLifecycleOfflineQueryResult,
    EvidenceLifecycleOfflineVerification,
)


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and bool(path.parts) and all(part not in {"", ".", ".."} for part in path.parts)


def _load_mapping(value: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(value)
    try:
        manifest = json.loads((root / EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load evidence lifecycle offline manifest: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise ValidationError("evidence lifecycle offline manifest must be an object")
    return root, manifest


def _check_from_dict(value: Mapping[str, Any]) -> EvidenceLifecycleOfflineCheck:
    return EvidenceLifecycleOfflineCheck(
        check_id=str(value.get("check_id", "unknown")),
        plane=EvidenceLifecycleOfflineCheckPlane(str(value.get("plane", EvidenceLifecycleOfflineCheckPlane.MANIFEST.value))),
        passed=bool(value.get("passed", False)),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "manifest check")),
        content_address=str(value.get("content_address", "evidence-lifecycle-bundle-check:missing")),
    )


def load_evidence_lifecycle_offline_bundle(destination: str | Path, *, include_payloads: bool = False) -> EvidenceLifecycleOfflineBundle:
    """Load a manifest and optionally hydrate every exact artifact payload."""

    root, manifest = _load_mapping(destination)
    artifacts_value = manifest.get("artifacts", ())
    checks_value = manifest.get("checks", ())
    if not isinstance(artifacts_value, list) or not isinstance(checks_value, list):
        raise ValidationError("evidence lifecycle offline collections must be arrays")
    artifacts: list[EvidenceLifecycleOfflineArtifact] = []
    for raw in artifacts_value:
        if not isinstance(raw, Mapping):
            raise ValidationError("evidence lifecycle artifact entries must be objects")
        relative_path = str(raw.get("relative_path", ""))
        if not _safe_relative_path(relative_path):
            raise ValidationError(f"unsafe evidence lifecycle artifact path: {relative_path!r}")
        payload: str | None = None
        if include_payloads:
            try:
                payload = (root / Path(*relative_path.split("/"))).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValidationError(f"cannot hydrate evidence lifecycle artifact {relative_path}: {exc}") from exc
        artifacts.append(
            EvidenceLifecycleOfflineArtifact(
                artifact_id=str(raw.get("artifact_id", "")),
                relative_path=relative_path,
                media_type=str(raw.get("media_type", "")),
                kind=EvidenceLifecycleOfflineArtifactKind(str(raw.get("kind", EvidenceLifecycleOfflineArtifactKind.REVIEW.value))),
                byte_count=int(raw.get("byte_count", 0)),
                line_count=int(raw.get("line_count", 0)),
                content_address=str(raw.get("content_address", "")),
                payload=payload,
            )
        )
    checks = tuple(_check_from_dict(item) for item in checks_value if isinstance(item, Mapping))
    return EvidenceLifecycleOfflineBundle(
        bundle_id=str(manifest.get("bundle_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        fixture_id=str(manifest.get("fixture_id", "")),
        run_id=str(manifest.get("run_id", "")),
        state=EvidenceLifecycleOfflineBundleState(str(manifest.get("state", EvidenceLifecycleOfflineBundleState.BLOCKED.value))),
        accepted=bool(manifest.get("accepted", False)),
        artifacts=tuple(artifacts),
        checks=checks,
        runtime_address=str(manifest.get("runtime_address", "")),
        warning_count=int(manifest.get("warning_count", 0)),
        content_address=str(manifest.get("content_address", "")),
    )


def _as_bundle(value: EvidenceLifecycleOfflineBundle | str | Path, *, include_payloads: bool = False) -> EvidenceLifecycleOfflineBundle:
    if isinstance(value, EvidenceLifecycleOfflineBundle):
        return value
    return load_evidence_lifecycle_offline_bundle(value, include_payloads=include_payloads)


def _json_payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _matches(item: Mapping[str, Any], text: str | None) -> bool:
    return not text or text.casefold() in canonical_json(item).casefold()


def _record_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    fixture = _json_payload(bundle, "fixture")
    evaluation = _json_payload(bundle, "evaluation")
    if not isinstance(fixture, Mapping) or not isinstance(evaluation, Mapping):
        return ()
    records = fixture.get("records", ())
    executions = evaluation.get("executions", ())
    if not isinstance(records, list) or not isinstance(executions, list):
        return ()
    execution_by_id = {str(item.get("record_id")): item for item in executions if isinstance(item, Mapping) and item.get("record_id") is not None}
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_id = str(record.get("record_id", ""))
        execution = execution_by_id.get(record_id, {})
        rows.append(
            {
                "resource": "record",
                "record_id": record_id,
                "operation": record.get("operation"),
                "role": record.get("role"),
                "expected_state": record.get("expected_state"),
                "observed_state": execution.get("state"),
                "accepted": execution.get("accepted"),
                "issue_codes": execution.get("issue_codes", ()),
                "source_ids": record.get("source_ids", ()),
                "content_address": execution.get("content_address", record.get("content_address")),
            }
        )
    return tuple(sorted(rows, key=lambda item: (str(item.get("operation")), str(item.get("record_id")))))


def _check_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    evaluation = _json_payload(bundle, "evaluation")
    if not isinstance(evaluation, Mapping) or not isinstance(evaluation.get("checks"), list):
        return ()
    return tuple(
        {
            "resource": "check",
            "check_id": item.get("check_id"),
            "record_id": item.get("record_id"),
            "passed": item.get("passed"),
            "observed": item.get("observed"),
            "required": item.get("required"),
            "detail": item.get("detail"),
            "content_address": item.get("content_address"),
        }
        for item in evaluation["checks"]
        if isinstance(item, Mapping)
    )


def _source_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    fixture = _json_payload(bundle, "fixture")
    if not isinstance(fixture, Mapping) or not isinstance(fixture.get("sources"), list):
        return ()
    return tuple({"resource": "source", **item} for item in fixture["sources"] if isinstance(item, Mapping))


def _event_rows(bundle: EvidenceLifecycleOfflineBundle) -> tuple[dict[str, Any], ...]:
    observability = _json_payload(bundle, "observability")
    if not isinstance(observability, Mapping) or not isinstance(observability.get("events"), list):
        return ()
    return tuple({"resource": "event", **item} for item in observability["events"] if isinstance(item, Mapping))


def query_evidence_lifecycle_offline_bundle(
    bundle: EvidenceLifecycleOfflineBundle | str | Path,
    *,
    resource: str = "artifacts",
    operation: str | None = None,
    role: str | None = None,
    state: str | None = None,
    artifact_kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_DEFAULT_LIMIT,
    include_payloads: bool = False,
) -> EvidenceLifecycleOfflineQueryResult:
    """Query artifacts, records, evaluation checks, sources, or events."""

    if offset < 0:
        raise ValidationError("evidence lifecycle query offset cannot be negative")
    if limit < 1 or limit > EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_LIMIT:
        raise ValidationError(f"evidence lifecycle query limit must be between 1 and {EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_MAX_LIMIT}")
    normalized_resource = require_non_empty(resource, "resource").casefold()
    valid_resources = {"artifacts", "records", "checks", "sources", "events"}
    if normalized_resource not in valid_resources:
        raise ValidationError(f"unsupported evidence lifecycle query resource: {resource}")
    value = _as_bundle(bundle, include_payloads=include_payloads or normalized_resource in {"records", "checks", "sources", "events"})
    if normalized_resource == "artifacts":
        items: list[Mapping[str, Any]] = [item.to_dict(include_payload=include_payloads) for item in value.artifacts]
        if artifact_kind is not None:
            items = [item for item in items if item.get("kind") == artifact_kind]
    elif normalized_resource == "records":
        items = list(_record_rows(value))
        if operation is not None:
            items = [item for item in items if item.get("operation") == operation]
        if role is not None:
            items = [item for item in items if item.get("role") == role]
        if state is not None:
            items = [item for item in items if item.get("observed_state") == state or item.get("expected_state") == state]
    elif normalized_resource == "checks":
        items = list(_check_rows(value))
        if state is not None:
            wanted = state.casefold() in {"passed", "true", "accepted"}
            items = [item for item in items if bool(item.get("passed")) is wanted]
    elif normalized_resource == "sources":
        items = list(_source_rows(value))
    else:
        items = list(_event_rows(value))
        if state is not None:
            items = [item for item in items if item.get("state") == state]
    if text:
        items = [item for item in items if _matches(item, text)]
    total = len(items)
    page = tuple(dict(item) for item in items[offset : offset + limit])
    query = {"resource": normalized_resource, "operation": operation, "role": role, "state": state, "artifact_kind": artifact_kind, "text": text, "offset": offset, "limit": limit, "include_payloads": include_payloads}
    body = {"bundle_id": value.bundle_id, "query": query, "total": total, "offset": offset, "limit": limit, "items": page, "accepted": value.ready}
    return EvidenceLifecycleOfflineQueryResult(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-query"))


def export_evidence_lifecycle_offline_query_csv(result: EvidenceLifecycleOfflineQueryResult) -> str:
    """Export a stable CSV page with a union of deterministic item fields."""

    keys = sorted({str(key) for item in result.items for key in item})
    if not keys:
        keys = ["resource"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in result.items:
        writer.writerow({key: _csv_value(item.get(key)) for key in keys})
    return stream.getvalue()


def _csv_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return canonical_json(value)
    return "" if value is None else str(value)


def diff_evidence_lifecycle_offline_bundles(left: EvidenceLifecycleOfflineBundle | str | Path, right: EvidenceLifecycleOfflineBundle | str | Path) -> EvidenceLifecycleOfflineDiff:
    left_value = _as_bundle(left, include_payloads=False)
    right_value = _as_bundle(right, include_payloads=False)
    left_map = {item.artifact_id: item.content_address for item in left_value.artifacts}
    right_map = {item.artifact_id: item.content_address for item in right_value.artifacts}
    added = tuple(sorted(set(right_map) - set(left_map)))
    removed = tuple(sorted(set(left_map) - set(right_map)))
    changed = tuple(sorted(item for item in set(left_map) & set(right_map) if left_map[item] != right_map[item]))
    unchanged = tuple(sorted(item for item in set(left_map) & set(right_map) if left_map[item] == right_map[item]))
    body = {"left_bundle_id": left_value.bundle_id, "right_bundle_id": right_value.bundle_id, "added_artifact_ids": added, "removed_artifact_ids": removed, "changed_artifact_ids": changed, "unchanged_artifact_ids": unchanged, "left_accepted": left_value.accepted, "right_accepted": right_value.accepted, "accepted": left_value.accepted and right_value.accepted and not added and not removed and not changed}
    return EvidenceLifecycleOfflineDiff(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-diff"))


def verify_and_load_evidence_lifecycle_offline_bundle(destination: str | Path) -> tuple[EvidenceLifecycleOfflineVerification, EvidenceLifecycleOfflineBundle]:
    verification = verify_evidence_lifecycle_offline_bundle(destination)
    return verification, load_evidence_lifecycle_offline_bundle(destination, include_payloads=True)


__all__ = [
    "diff_evidence_lifecycle_offline_bundles",
    "export_evidence_lifecycle_offline_query_csv",
    "load_evidence_lifecycle_offline_bundle",
    "query_evidence_lifecycle_offline_bundle",
    "verify_and_load_evidence_lifecycle_offline_bundle",
]

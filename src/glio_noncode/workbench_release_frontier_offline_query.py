"""Load, query, diff, and export D15 offline handoffs."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash
from .workbench_release_frontier_offline_contracts import (
    WORKBENCH_RELEASE_OFFLINE_DEFAULT_LIMIT,
    WORKBENCH_RELEASE_OFFLINE_MANIFEST,
    WORKBENCH_RELEASE_OFFLINE_MAX_LIMIT,
    WorkbenchReleaseOfflineArtifact,
    WorkbenchReleaseOfflineArtifactKind,
    WorkbenchReleaseOfflineBundle,
    WorkbenchReleaseOfflineBundleState,
    WorkbenchReleaseOfflineCheck,
    WorkbenchReleaseOfflineCheckPlane,
    WorkbenchReleaseOfflineDiff,
    WorkbenchReleaseOfflineQueryResult,
    WorkbenchReleaseOfflineVerification,
)
from .workbench_release_frontier_offline_bundle import verify_workbench_release_offline_bundle


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _manifest_mapping(value: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(value)
    manifest_path = root / WORKBENCH_RELEASE_OFFLINE_MANIFEST
    if not manifest_path.is_file():
        raise ValidationError(f"workbench offline manifest is missing: {manifest_path}")
    try:
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"workbench offline manifest cannot be read: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("workbench offline manifest root must be an object")
    return root, parsed


def _artifact(
    root: Path, raw: Mapping[str, Any], *, include_payloads: bool
) -> WorkbenchReleaseOfflineArtifact:
    required = (
        "artifact_id",
        "relative_path",
        "media_type",
        "kind",
        "byte_count",
        "line_count",
        "content_address",
    )
    missing = tuple(key for key in required if key not in raw)
    if missing:
        raise ValidationError(f"workbench artifact metadata is missing fields: {missing}")
    relative_path = str(raw["relative_path"])
    if not _safe_relative_path(relative_path):
        raise ValidationError(f"workbench artifact path is unsafe: {relative_path!r}")
    payload: str | None = None
    if include_payloads:
        target = root / Path(*PurePosixPath(relative_path).parts)
        if not target.is_file():
            raise ValidationError(f"workbench artifact file is missing: {target}")
        try:
            payload = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValidationError(f"workbench artifact file cannot be read: {target}") from exc
    try:
        kind = WorkbenchReleaseOfflineArtifactKind(str(raw["kind"]))
    except ValueError as exc:
        raise ValidationError(f"unknown workbench artifact kind: {raw.get('kind')!r}") from exc
    return WorkbenchReleaseOfflineArtifact(
        artifact_id=str(raw["artifact_id"]),
        relative_path=relative_path,
        media_type=str(raw["media_type"]),
        kind=kind,
        byte_count=int(raw["byte_count"]),
        line_count=int(raw["line_count"]),
        content_address=str(raw["content_address"]),
        payload=payload,
    )


def _check(raw: Mapping[str, Any]) -> WorkbenchReleaseOfflineCheck:
    required = ("check_id", "plane", "passed", "observed", "required", "detail", "content_address")
    missing = tuple(key for key in required if key not in raw)
    if missing:
        raise ValidationError(f"workbench check metadata is missing fields: {missing}")
    try:
        plane = WorkbenchReleaseOfflineCheckPlane(str(raw["plane"]))
    except ValueError as exc:
        raise ValidationError(
            f"unknown workbench offline check plane: {raw.get('plane')!r}"
        ) from exc
    return WorkbenchReleaseOfflineCheck(
        check_id=str(raw["check_id"]),
        plane=plane,
        passed=bool(raw["passed"]),
        observed=raw["observed"],
        required=raw["required"],
        detail=str(raw["detail"]),
        content_address=str(raw["content_address"]),
    )


def load_workbench_release_offline_bundle(
    destination: str | Path, *, include_payloads: bool = True
) -> WorkbenchReleaseOfflineBundle:
    """Load a manifest and optionally its exact payload text without executing the producer."""

    root, manifest = _manifest_mapping(destination)
    try:
        artifacts_raw = manifest["artifacts"]
        checks_raw = manifest["checks"]
        if not isinstance(artifacts_raw, list) or not isinstance(checks_raw, list):
            raise TypeError("artifacts and checks must be arrays")
        artifacts = tuple(
            _artifact(root, item, include_payloads=include_payloads)
            for item in artifacts_raw
            if isinstance(item, Mapping)
        )
        checks = tuple(_check(item) for item in checks_raw if isinstance(item, Mapping))
        state = WorkbenchReleaseOfflineBundleState(str(manifest["state"]))
        return WorkbenchReleaseOfflineBundle(
            bundle_id=str(manifest["bundle_id"]),
            version=str(manifest["version"]),
            boundary=str(manifest["boundary"]),
            fixture_id=str(manifest["fixture_id"]),
            run_id=str(manifest["run_id"]),
            state=state,
            accepted=bool(manifest["accepted"]),
            artifacts=artifacts,
            checks=checks,
            runtime_address=str(manifest["runtime_address"]),
            stage_count=int(manifest["stage_count"]),
            warning_count=int(manifest["warning_count"]),
            content_address=str(manifest["content_address"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"workbench offline manifest has invalid shape: {exc}") from exc


def _payload(bundle: WorkbenchReleaseOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    if artifact.media_type != "application/json":
        return artifact.payload
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"workbench artifact {artifact_id!r} is not valid JSON") from exc


def _rows(
    bundle: WorkbenchReleaseOfflineBundle, artifact_id: str, key: str
) -> tuple[dict[str, Any], ...]:
    value = _payload(bundle, artifact_id)
    if not isinstance(value, Mapping) or not isinstance(value.get(key), list):
        return ()
    return tuple(item for item in value[key] if isinstance(item, Mapping))


def _resources(bundle: WorkbenchReleaseOfflineBundle, resource: str) -> tuple[dict[str, Any], ...]:
    normalized = resource.casefold().replace("-", "_")
    if normalized in {"artifacts", "artifact"}:
        return tuple(item.to_dict(include_payload=False) for item in bundle.artifacts)
    if normalized in {"checks", "check", "evaluation_checks"}:
        return _rows(bundle, "evaluation", "checks")
    if normalized in {"bundle_checks", "bundle_check", "manifest_checks"}:
        return tuple(item.to_dict() for item in bundle.checks)
    if normalized in {"records", "record"}:
        return _rows(bundle, "fixture", "records")
    if normalized in {"sources", "source"}:
        return _rows(bundle, "fixture", "sources")
    if normalized in {"executions", "execution", "evaluation"}:
        return _rows(bundle, "evaluation", "executions")
    if normalized in {"events", "event", "observability"}:
        values = _payload(bundle, "observability")
        if isinstance(values, Mapping) and isinstance(values.get("values"), Mapping):
            return (dict(values["values"]),)
        return _rows(bundle, "observability", "observations")
    if normalized in {"stages", "stage", "runtime"}:
        return _rows(bundle, "runtime", "stages")
    if normalized in {"operations", "operation", "operation_index"}:
        value = _payload(bundle, "operation-index")
        if isinstance(value, Mapping) and isinstance(value.get("operations"), Mapping):
            return tuple(
                {"operation": key, "record_ids": value[key]} for key in sorted(value["operations"])
            )
        return ()
    if normalized in {"denominators", "denominator", "counts"}:
        value = _payload(bundle, "denominator-index")
        return (dict(value),) if isinstance(value, Mapping) else ()
    if normalized in {"keys", "key", "public_keys"}:
        value = _payload(bundle, "public-key-index")
        return (dict(value),) if isinstance(value, Mapping) else ()
    if normalized in {"components", "planes", "plane"}:
        return tuple(
            {
                "artifact_id": item.artifact_id,
                "kind": item.kind.value,
                "relative_path": item.relative_path,
                "content_address": item.content_address,
            }
            for item in bundle.artifacts
            if item.kind
            not in {
                WorkbenchReleaseOfflineArtifactKind.RUNTIME,
                WorkbenchReleaseOfflineArtifactKind.REVIEW_CSV,
            }
        )
    raise ValidationError(f"unsupported workbench offline resource: {resource!r}")


def _filter_rows(
    rows: tuple[dict[str, Any], ...], filters: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    selected = rows
    for field in (
        "record_id",
        "source_id",
        "operation",
        "role",
        "state",
        "observed_state",
        "capability",
        "stage_id",
        "kind",
        "artifact_id",
        "check_id",
        "plane",
    ):
        expected = filters.get(field)
        if expected in (None, "", (), []):
            continue
        values = {
            str(item).strip()
            for item in (
                expected if isinstance(expected, (list, tuple, set)) else str(expected).split(",")
            )
            if str(item).strip()
        }

        def value_for(item: Mapping[str, Any]) -> str:
            if field == "state" and "state" not in item and "passed" in item:
                return "passed" if bool(item.get("passed")) else "failed"
            return str(item.get(field, ""))

        selected = tuple(item for item in selected if value_for(item) in values)
    raw_text = filters.get("text", "")
    text = "" if raw_text is None else str(raw_text).casefold().strip()
    if text:
        selected = tuple(item for item in selected if text in canonical_json(item).casefold())
    return selected


def query_workbench_release_offline_bundle(
    destination: str | Path | WorkbenchReleaseOfflineBundle,
    *,
    resource: str = "artifacts",
    offset: int = 0,
    limit: int = WORKBENCH_RELEASE_OFFLINE_DEFAULT_LIMIT,
    filters: Mapping[str, Any] | None = None,
) -> WorkbenchReleaseOfflineQueryResult:
    """Query a bounded public resource projection by stable fields."""

    if offset < 0:
        raise ValidationError("offset cannot be negative")
    if limit <= 0 or limit > WORKBENCH_RELEASE_OFFLINE_MAX_LIMIT:
        raise ValidationError(f"limit must be between 1 and {WORKBENCH_RELEASE_OFFLINE_MAX_LIMIT}")
    bundle = (
        destination
        if isinstance(destination, WorkbenchReleaseOfflineBundle)
        else load_workbench_release_offline_bundle(destination, include_payloads=True)
    )
    query = {"resource": resource, "offset": offset, "limit": limit, **dict(filters or {})}
    selected = _filter_rows(_resources(bundle, resource), query)
    items = selected[offset : offset + limit]
    body = {
        "bundle_id": bundle.bundle_id,
        "query": query,
        "total": len(selected),
        "offset": offset,
        "limit": limit,
        "items": items,
        "accepted": bundle.ready,
    }
    return WorkbenchReleaseOfflineQueryResult(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-query")
    )


def export_workbench_release_offline_query_csv(result: WorkbenchReleaseOfflineQueryResult) -> str:
    """Export a query without assuming a fixed schema across resources."""

    keys = sorted({key for item in result.items for key in item})
    stream = io.StringIO()
    if not keys:
        return ""
    writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in result.items:
        writer.writerow(
            {
                key: canonical_json(item.get(key))
                if isinstance(item.get(key), (dict, list, tuple))
                else item.get(key, "")
                for key in keys
            }
        )
    return stream.getvalue()


def diff_workbench_release_offline_bundles(
    left: str | Path, right: str | Path
) -> WorkbenchReleaseOfflineDiff:
    """Compare two handoffs by artifact identity and exact-byte address."""

    left_value = load_workbench_release_offline_bundle(left, include_payloads=False)
    right_value = load_workbench_release_offline_bundle(right, include_payloads=False)
    left_map = {item.artifact_id: item.content_address for item in left_value.artifacts}
    right_map = {item.artifact_id: item.content_address for item in right_value.artifacts}
    added = tuple(sorted(set(right_map) - set(left_map)))
    removed = tuple(sorted(set(left_map) - set(right_map)))
    changed = tuple(
        sorted(item for item in set(left_map) & set(right_map) if left_map[item] != right_map[item])
    )
    unchanged = tuple(
        sorted(item for item in set(left_map) & set(right_map) if left_map[item] == right_map[item])
    )
    body = {
        "left_bundle_id": left_value.bundle_id,
        "right_bundle_id": right_value.bundle_id,
        "added_artifact_ids": added,
        "removed_artifact_ids": removed,
        "changed_artifact_ids": changed,
        "unchanged_artifact_ids": unchanged,
        "left_accepted": left_value.accepted,
        "right_accepted": right_value.accepted,
        "accepted": left_value.accepted
        and right_value.accepted
        and not added
        and not removed
        and not changed,
    }
    return WorkbenchReleaseOfflineDiff(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-diff")
    )


def verify_and_load_workbench_release_offline_bundle(
    destination: str | Path,
) -> tuple[WorkbenchReleaseOfflineVerification, WorkbenchReleaseOfflineBundle]:
    verification = verify_workbench_release_offline_bundle(destination)
    return verification, load_workbench_release_offline_bundle(destination, include_payloads=True)


__all__ = [
    "diff_workbench_release_offline_bundles",
    "export_workbench_release_offline_query_csv",
    "load_workbench_release_offline_bundle",
    "query_workbench_release_offline_bundle",
    "verify_and_load_workbench_release_offline_bundle",
]

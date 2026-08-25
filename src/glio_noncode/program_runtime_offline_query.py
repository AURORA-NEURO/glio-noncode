"""Bounded, deterministic queries over an architecture-program handoff."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_DEFAULT_LIMIT,
    PROGRAM_RUNTIME_OFFLINE_MAX_LIMIT,
    ProgramRuntimeOfflineArtifact,
    ProgramRuntimeOfflineBundle,
    ProgramRuntimeOfflineDiff,
    ProgramRuntimeOfflineQueryResult,
)
from .serialization import content_hash, jsonable


PROGRAM_RUNTIME_OFFLINE_RESOURCES = (
    "artifacts",
    "domains",
    "operations",
    "checks",
    "stages",
    "quality",
    "release_checks",
    "specifications",
    "capabilities",
    "states",
)


def _artifact(
    bundle: ProgramRuntimeOfflineBundle, artifact_id: str
) -> ProgramRuntimeOfflineArtifact | None:
    return next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)


def _payload(bundle: ProgramRuntimeOfflineBundle, artifact_id: str) -> Any:
    artifact = _artifact(bundle, artifact_id)
    if artifact is None or artifact.payload is None:
        return None
    if artifact.media_type == "application/json":
        try:
            return json.loads(artifact.payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"artifact {artifact_id!r} is not valid JSON") from exc
    return artifact.payload


def _csv_rows(bundle: ProgramRuntimeOfflineBundle, artifact_id: str) -> list[dict[str, Any]]:
    value = _payload(bundle, artifact_id)
    if not isinstance(value, str):
        return []
    return [dict(row) for row in csv.DictReader(io.StringIO(value))]


def _rows(bundle: ProgramRuntimeOfflineBundle, resource: str) -> list[dict[str, Any]]:
    if resource == "artifacts":
        return [item.to_dict(include_payload=False) for item in bundle.artifacts]
    if resource == "domains" or resource == "operations":
        value = _payload(bundle, "operations")
        return list(value) if isinstance(value, list) else []
    if resource == "checks":
        return _csv_rows(bundle, "checks")
    if resource == "stages":
        value = _payload(bundle, "stages")
        return list(value) if isinstance(value, list) else []
    if resource == "quality":
        value = _payload(bundle, "quality")
        if isinstance(value, Mapping):
            checks = value.get("checks", ())
            return list(checks) if isinstance(checks, list) else []
        return []
    if resource == "release_checks":
        value = _payload(bundle, "release-checks")
        return list(value) if isinstance(value, list) else []
    if resource == "specifications":
        value = _payload(bundle, "specifications")
        return list(value) if isinstance(value, list) else []
    if resource == "capabilities":
        value = _payload(bundle, "capabilities")
        return list(value) if isinstance(value, list) else []
    if resource == "states":
        domains = _rows(bundle, "domains")
        states: dict[str, int] = {}
        for item in domains:
            state = str(item.get("runtime_state", "unknown"))
            states[state] = states.get(state, 0) + 1
        return [{"state": key, "count": value} for key, value in sorted(states.items())]
    raise ValidationError(f"unsupported program offline query resource: {resource}")


def _matches(
    item: Mapping[str, Any],
    *,
    domain_id: str | None,
    state: str | None,
    accepted_only: bool,
    text: str | None,
) -> bool:
    def as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).casefold() in {"true", "1", "yes", "accepted", "pass"}

    if domain_id and str(item.get("domain_id", "")) != domain_id:
        return False
    if state and str(item.get("state", item.get("runtime_state", ""))) != state:
        return False
    if accepted_only and not as_bool(item.get("accepted", item.get("passed", False))):
        return False
    if text:
        haystack = json.dumps(jsonable(item), sort_keys=True).casefold()
        if text.casefold() not in haystack:
            return False
    return True


def query_program_runtime_offline_bundle(
    bundle: ProgramRuntimeOfflineBundle,
    *,
    resource: str = "artifacts",
    domain_id: str | None = None,
    state: str | None = None,
    accepted_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = PROGRAM_RUNTIME_OFFLINE_DEFAULT_LIMIT,
) -> ProgramRuntimeOfflineQueryResult:
    """Return one bounded stable page from a verified in-memory bundle."""

    if resource not in PROGRAM_RUNTIME_OFFLINE_RESOURCES:
        raise ValidationError(f"unsupported program offline query resource: {resource}")
    if offset < 0:
        raise ValidationError("query offset cannot be negative")
    if limit < 1 or limit > PROGRAM_RUNTIME_OFFLINE_MAX_LIMIT:
        raise ValidationError("query limit is outside the offline contract")
    if domain_id is not None and not str(domain_id).strip():
        raise ValidationError("domain_id cannot be blank")
    if state is not None and not str(state).strip():
        raise ValidationError("state cannot be blank")
    rows = [
        dict(item)
        for item in _rows(bundle, resource)
        if _matches(
            item,
            domain_id=domain_id,
            state=state,
            accepted_only=accepted_only,
            text=text,
        )
    ]
    rows.sort(
        key=lambda item: (
            str(item.get("domain_id", "")),
            str(item.get("ordinal", "")),
            str(item.get("check_id", item.get("artifact_id", item.get("stage_id", "")))),
        )
    )
    page = tuple(rows[offset : offset + limit])
    filters = {
        "domain_id": domain_id,
        "state": state,
        "accepted_only": accepted_only,
        "text": text,
    }
    body = {
        "bundle_id": bundle.bundle_id,
        "resource": resource,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": bundle.ready,
    }
    return ProgramRuntimeOfflineQueryResult(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-query"),
    )


def export_program_runtime_offline_query_csv(result: ProgramRuntimeOfflineQueryResult) -> str:
    """Export a query page without embedding opaque payload bytes."""

    rows = [dict(item) for item in result.items]
    keys = sorted({key for row in rows for key in row})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=keys or ["resource"], extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, sort_keys=True)
                if isinstance(value, (dict, list, tuple))
                else value
                for key, value in row.items()
            }
        )
    return output.getvalue()


def diff_program_runtime_offline_bundles(
    left: ProgramRuntimeOfflineBundle,
    right: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineDiff:
    """Compare two bundles by addresses and conserved denominators."""

    left_map = {item.artifact_id: item for item in left.artifacts}
    right_map = {item.artifact_id: item for item in right.artifacts}
    added = tuple(sorted(set(right_map) - set(left_map)))
    removed = tuple(sorted(set(left_map) - set(right_map)))
    changed = tuple(
        sorted(
            key
            for key in set(left_map) & set(right_map)
            if left_map[key].content_address != right_map[key].content_address
        )
    )
    unchanged = tuple(
        sorted(
            key
            for key in set(left_map) & set(right_map)
            if left_map[key].content_address == right_map[key].content_address
        )
    )
    changed_counts: dict[str, tuple[int, int]] = {}
    for key in ("domain_count", "stage_count", "warning_count", "artifact_count"):
        left_value = int(getattr(left, key)) if key != "artifact_count" else left.artifact_count
        right_value = int(getattr(right, key)) if key != "artifact_count" else right.artifact_count
        if left_value != right_value:
            changed_counts[key] = (left_value, right_value)
    accepted = (
        left.ready
        and right.ready
        and not added
        and not removed
        and not changed
        and not changed_counts
    )
    body = {
        "left_bundle_id": left.bundle_id,
        "right_bundle_id": right.bundle_id,
        "added_artifact_ids": added,
        "removed_artifact_ids": removed,
        "changed_artifact_ids": changed,
        "unchanged_artifact_ids": unchanged,
        "changed_counts": changed_counts,
        "left_accepted": left.ready,
        "right_accepted": right.ready,
        "accepted": accepted,
    }
    return ProgramRuntimeOfflineDiff(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-diff"),
    )


__all__ = [
    "PROGRAM_RUNTIME_OFFLINE_RESOURCES",
    "diff_program_runtime_offline_bundles",
    "export_program_runtime_offline_query_csv",
    "query_program_runtime_offline_bundle",
    "_artifact",
    "_payload",
    "_rows",
]

"""Bounded read APIs for D16 offline handoffs.

Queries operate on manifest-listed payloads and return stable projections.  A
query never scans an arbitrary directory, never follows a path supplied by a
caller, and never returns more than the configured page ceiling.  This keeps
the offline handoff suitable for command-line review, a local dashboard, and
the HTTP read API without creating a second mutable data store.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .deployment_frontier_offline_bundle import (
    load_deployment_frontier_offline_bundle,
    verify_deployment_frontier_offline_bundle,
)
from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_DEFAULT_LIMIT,
    DEPLOYMENT_FRONTIER_OFFLINE_MAX_LIMIT,
    DeploymentFrontierOfflineArtifactKind,
    DeploymentFrontierOfflineBundle,
    DeploymentFrontierOfflineDiff,
    DeploymentFrontierOfflineQueryResult,
    DeploymentFrontierOfflineVerification,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash


def _bundle(value: str | Path | DeploymentFrontierOfflineBundle) -> DeploymentFrontierOfflineBundle:
    return (
        value
        if isinstance(value, DeploymentFrontierOfflineBundle)
        else load_deployment_frontier_offline_bundle(value, include_payloads=True)
    )


def _payload(bundle: DeploymentFrontierOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    if artifact.media_type != "application/json":
        return artifact.payload
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"deployment artifact {artifact_id!r} is not valid JSON") from exc


def _rows(
    bundle: DeploymentFrontierOfflineBundle, artifact_id: str, key: str
) -> tuple[dict[str, Any], ...]:
    value = _payload(bundle, artifact_id)
    if not isinstance(value, Mapping) or not isinstance(value.get(key), list):
        return ()
    return tuple(dict(item) for item in value[key] if isinstance(item, Mapping))


def _resources(
    bundle: DeploymentFrontierOfflineBundle, resource: str
) -> tuple[dict[str, Any], ...]:
    normalized = resource.casefold().replace("-", "_")
    if normalized in {"artifact", "artifacts"}:
        return tuple(item.to_dict(include_payload=False) for item in bundle.artifacts)
    if normalized in {"bundle_check", "bundle_checks", "manifest_check", "manifest_checks"}:
        return tuple(item.to_dict() for item in bundle.checks)
    if normalized in {"record", "records"}:
        return _rows(bundle, "fixture", "records")
    if normalized in {"source", "sources"}:
        return _rows(bundle, "fixture", "sources")
    if normalized in {"execution", "executions", "evaluation"}:
        return _rows(bundle, "evaluation", "executions")
    if normalized in {"check", "checks", "evaluation_checks"}:
        return _rows(bundle, "evaluation", "checks")
    if normalized in {"stage", "stages", "runtime"}:
        return _rows(bundle, "runtime", "stages")
    if normalized in {"operation", "operations"}:
        value = _payload(bundle, "operation-index")
        if isinstance(value, Mapping) and isinstance(value.get("operations"), Mapping):
            return tuple(
                {"operation": key, "record_ids": value[key]} for key in sorted(value["operations"])
            )
        return ()
    if normalized in {"denominator", "denominators", "counts"}:
        value = _payload(bundle, "denominator-index")
        return (dict(value),) if isinstance(value, Mapping) else ()
    if normalized in {"issue", "issues"}:
        value = _payload(bundle, "issue-index")
        if isinstance(value, Mapping):
            return tuple(
                {
                    "issue": key,
                    "count": count,
                    "record_ids": value.get("record_ids", {}).get(key, ()),
                }
                for key, count in value.get("issue_counts", {}).items()
            )
        return ()
    if normalized in {"state", "states"}:
        value = _payload(bundle, "state-index")
        if isinstance(value, Mapping):
            return tuple(
                {
                    "state": key,
                    "count": count,
                    "record_ids": value.get("record_ids", {}).get(key, ()),
                }
                for key, count in value.get("state_counts", {}).items()
            )
        return ()
    if normalized in {"fixture", "fixture_index"}:
        value = _payload(bundle, "fixture-index")
        return (dict(value),) if isinstance(value, Mapping) else ()
    if normalized in {"keys", "key", "public_keys"}:
        value = _payload(bundle, "public-key-index")
        return (dict(value),) if isinstance(value, Mapping) else ()
    if normalized in {"components", "component", "planes", "plane"}:
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
                DeploymentFrontierOfflineArtifactKind.RUNTIME,
                DeploymentFrontierOfflineArtifactKind.REVIEW_CSV,
                DeploymentFrontierOfflineArtifactKind.SOURCES_CSV,
                DeploymentFrontierOfflineArtifactKind.EXECUTIONS_CSV,
            }
        )
    if normalized in {"observability", "events", "event"}:
        value = _payload(bundle, "trace")
        if isinstance(value, Mapping):
            return (
                tuple(value.get("observations", ()))
                if isinstance(value.get("observations"), list)
                else (dict(value),)
            )
        return ()
    if normalized in {"capability", "capabilities", "capability_map"}:
        value = _payload(bundle, "capability-map")
        return (
            tuple(
                {"operation": key, "description": description}
                for key, description in value.get("descriptions", {}).items()
            )
            if isinstance(value, Mapping)
            else ()
        )
    raise ValidationError(f"unsupported deployment offline resource: {resource!r}")


def _filter_rows(
    rows: tuple[dict[str, Any], ...], filters: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    selected = rows
    fields = (
        "record_id",
        "source_id",
        "operation",
        "role",
        "state",
        "observed_state",
        "stage_id",
        "kind",
        "artifact_id",
        "check_id",
        "plane",
        "issue",
    )
    for field in fields:
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
    raw_text = filters.get("text")
    text = "" if raw_text is None else str(raw_text).casefold().strip()
    if text:
        selected = tuple(item for item in selected if text in canonical_json(item).casefold())
    return selected


def query_deployment_frontier_offline_bundle(
    value: str | Path | DeploymentFrontierOfflineBundle,
    *,
    resource: str = "artifacts",
    offset: int = 0,
    limit: int = DEPLOYMENT_FRONTIER_OFFLINE_DEFAULT_LIMIT,
    filters: Mapping[str, Any] | None = None,
) -> DeploymentFrontierOfflineQueryResult:
    """Return one bounded, addressable page of a public resource."""

    if offset < 0:
        raise ValidationError("offset cannot be negative")
    if limit <= 0 or limit > DEPLOYMENT_FRONTIER_OFFLINE_MAX_LIMIT:
        raise ValidationError(
            f"limit must be between 1 and {DEPLOYMENT_FRONTIER_OFFLINE_MAX_LIMIT}"
        )
    bundle = _bundle(value)
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
    return DeploymentFrontierOfflineQueryResult(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-query")
    )


def export_deployment_frontier_offline_query_csv(
    result: DeploymentFrontierOfflineQueryResult,
) -> str:
    """Export a query page with deterministic field ordering."""

    keys = sorted({key for item in result.items for key in item})
    if not keys:
        return ""
    stream = io.StringIO()
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


def diff_deployment_frontier_offline_bundles(
    left: str | Path, right: str | Path
) -> DeploymentFrontierOfflineDiff:
    """Compare two handoffs by artifact identity and exact-byte address."""

    left_value = load_deployment_frontier_offline_bundle(left, include_payloads=False)
    right_value = load_deployment_frontier_offline_bundle(right, include_payloads=False)
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
    return DeploymentFrontierOfflineDiff(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-diff")
    )


def verify_and_load_deployment_frontier_offline_bundle(
    destination: str | Path,
) -> tuple[DeploymentFrontierOfflineVerification, DeploymentFrontierOfflineBundle]:
    verification = verify_deployment_frontier_offline_bundle(destination)
    return verification, load_deployment_frontier_offline_bundle(destination, include_payloads=True)


__all__ = [
    "diff_deployment_frontier_offline_bundles",
    "export_deployment_frontier_offline_query_csv",
    "load_deployment_frontier_offline_bundle",
    "query_deployment_frontier_offline_bundle",
    "verify_and_load_deployment_frontier_offline_bundle",
]

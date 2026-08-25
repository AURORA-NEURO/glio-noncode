"""Independent D15 public-boundary and artifact-shape closure audit."""

from __future__ import annotations

import json
from typing import Any

from .serialization import content_hash, jsonable
from .workbench_release_frontier_offline_boundary import audit_workbench_release_offline_boundary
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WorkbenchReleaseClosureBoundaryReport,
)
from .workbench_release_frontier_offline_closure_support import (
    discover_keys,
    forbidden_keys,
    safe_relative_path,
)
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle


def _json_payload(artifact: Any) -> Any:
    if artifact.payload is None or artifact.media_type != "application/json":
        return {}
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return {}


def _artifact_check(bundle: WorkbenchReleaseOfflineBundle, artifact: Any) -> dict[str, Any]:
    value = _json_payload(artifact)
    keys = forbidden_keys(value)
    body = {
        "artifact_id": artifact.artifact_id,
        "relative_path": artifact.relative_path,
        "payload_present": artifact.payload is not None,
        "payload_valid": artifact.media_type != "application/json"
        or isinstance(value, (dict, list)),
        "safe_path": safe_relative_path(artifact.relative_path),
        "addressed": artifact.content_address.startswith("workbench-release-bundle-artifact:"),
        "forbidden_keys": keys,
        "accepted": artifact.payload is not None
        and safe_relative_path(artifact.relative_path)
        and artifact.content_address.startswith("workbench-release-bundle-artifact:")
        and not keys,
    }
    return jsonable(
        body
        | {"content_address": content_hash(body, prefix="workbench-release-closure-artifact-check")}
    )


def audit_workbench_release_closure_boundary(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureBoundaryReport:
    """Audit hydrated D15 artifacts without relying on producer objects."""

    if any(item.payload is None for item in bundle.artifacts):
        raise ValueError("D15 closure boundary requires hydrated artifact payloads")
    base = audit_workbench_release_offline_boundary(bundle)
    checks = tuple(_artifact_check(bundle, artifact) for artifact in bundle.artifacts)
    forbidden = tuple(sorted({key for item in checks for key in item["forbidden_keys"]}))
    discovered = sum(len(discover_keys(_json_payload(item))) for item in bundle.artifacts)
    accepted = (
        base.accepted
        and len(bundle.artifacts) == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT
        and len({item.relative_path for item in bundle.artifacts})
        == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT
        and not forbidden
        and all(item["accepted"] for item in checks)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "source_boundary": bundle.boundary,
        "forbidden_keys": forbidden,
        "discovered_key_count": discovered,
        "artifact_checks": checks,
        "accepted": accepted,
    }
    return WorkbenchReleaseClosureBoundaryReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-boundary"),
    )


def workbench_release_closure_key_inventory(
    bundle: WorkbenchReleaseOfflineBundle,
) -> dict[str, Any]:
    keys: set[str] = set()
    for artifact in bundle.artifacts:
        keys.update(discover_keys(_json_payload(artifact)))
    forbidden = tuple(
        sorted(
            {
                item.rsplit(".", 1)[-1]
                for item in keys
                if item.rsplit(".", 1)[-1].casefold()
                in forbidden_keys({item.rsplit(".", 1)[-1]: True for item in keys})
            }
        )
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "key_count": len(keys),
        "keys": tuple(sorted(keys)),
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
    }
    return jsonable(
        body
        | {"content_address": content_hash(body, prefix="workbench-release-closure-key-inventory")}
    )


__all__ = ["audit_workbench_release_closure_boundary", "workbench_release_closure_key_inventory"]

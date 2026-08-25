"""Public boundary audit for the independent D16 deployment closure."""

from __future__ import annotations

import json
from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DeploymentFrontierClosureBoundaryReport,
)
from .deployment_frontier_offline_closure_support import (
    discover_keys,
    forbidden_keys,
    safe_relative_path,
)
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash, jsonable


def _artifact_check(artifact: Any) -> dict[str, Any]:
    value: Any = None
    if artifact.payload and artifact.media_type == "application/json":
        try:
            value = json.loads(artifact.payload)
        except json.JSONDecodeError:
            value = None
    elif artifact.payload:
        value = artifact.payload
    keys = forbidden_keys(value)
    body = {
        "artifact_id": artifact.artifact_id,
        "relative_path": artifact.relative_path,
        "payload_present": artifact.payload is not None,
        "payload_valid": artifact.media_type != "application/json" or value is not None,
        "safe_path": safe_relative_path(artifact.relative_path),
        "addressed": artifact.content_address.startswith("deployment-frontier-offline-artifact:"),
        "forbidden_keys": keys,
        "accepted": (
            artifact.payload is not None
            and (artifact.media_type != "application/json" or value is not None)
            and safe_relative_path(artifact.relative_path)
            and artifact.content_address.startswith("deployment-frontier-offline-artifact:")
            and not keys
        ),
    }
    return jsonable(
        body
        | {
            "content_address": content_hash(
                body, prefix="deployment-frontier-closure-artifact-check"
            )
        }
    )


def audit_deployment_frontier_closure_boundary(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureBoundaryReport:
    checks = tuple(_artifact_check(artifact) for artifact in bundle.artifacts)
    forbidden: set[str] = set()
    for check in checks:
        forbidden.update(str(item) for item in check["forbidden_keys"])
    accepted = (
        bundle.ready
        and bundle.boundary == "public_aggregate_deployment_offline_handoff"
        and len(bundle.artifacts) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT
        and len({item.artifact_id for item in bundle.artifacts})
        == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT
        and len({item.relative_path for item in bundle.artifacts})
        == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT
        and not forbidden
        and all(item["accepted"] for item in checks)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "source_boundary": bundle.boundary,
        "forbidden_keys": tuple(sorted(forbidden)),
        "discovered_key_count": len(discover_keys(bundle)),
        "artifact_checks": checks,
        "accepted": accepted,
    }
    return DeploymentFrontierClosureBoundaryReport(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-boundary"),
    )


def deployment_frontier_closure_key_inventory(
    bundle: DeploymentFrontierOfflineBundle,
) -> dict[str, Any]:
    keys = discover_keys(bundle)
    terminals = {path.rsplit(".", 1)[-1] for path in keys}
    forbidden = tuple(sorted(forbidden_keys({key: True for key in terminals})))
    body = {
        "bundle_id": bundle.bundle_id,
        "key_count": len(keys),
        "keys": keys,
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
    }
    return jsonable(
        body
        | {
            "content_address": content_hash(
                body, prefix="deployment-frontier-closure-key-inventory"
            )
        }
    )


__all__ = [
    "audit_deployment_frontier_closure_boundary",
    "deployment_frontier_closure_key_inventory",
]

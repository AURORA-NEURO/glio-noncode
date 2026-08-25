"""Independent D14 closure boundary projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evidence_lifecycle_frontier_offline_boundary import (
    audit_evidence_lifecycle_offline_boundary,
    audit_evidence_lifecycle_offline_directory,
)
from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_BOUNDARY,
    EvidenceLifecycleClosureBoundaryReport,
)
from .evidence_lifecycle_frontier_offline_closure_support import (
    discover_keys,
    forbidden_keys,
    safe_relative_path,
)
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash, jsonable


def _artifact_check(bundle: EvidenceLifecycleOfflineBundle, artifact: Any) -> dict[str, Any]:
    parse_ok = artifact.media_type != "application/json"
    decoded: Any = None
    if artifact.media_type == "application/json" and artifact.payload is not None:
        try:
            decoded = json.loads(artifact.payload)
            parse_ok = True
        except json.JSONDecodeError:
            parse_ok = False
    prohibited = forbidden_keys(decoded) if decoded is not None else ()
    return {
        "artifact_id": artifact.artifact_id,
        "relative_path": artifact.relative_path,
        "payload_present": artifact.payload is not None,
        "parse_ok": parse_ok,
        "addressed": artifact.content_address.startswith("evidence-lifecycle-bundle-artifact:"),
        "safe_path": safe_relative_path(artifact.relative_path),
        "forbidden_keys": prohibited,
        "accepted": bool(
            artifact.payload is not None
            and parse_ok
            and not prohibited
            and safe_relative_path(artifact.relative_path)
            and artifact.content_address.startswith("evidence-lifecycle-bundle-artifact:")
        ),
    }


def audit_evidence_lifecycle_closure_boundary(
    bundle: EvidenceLifecycleOfflineBundle,
    *,
    directory: str | Path | None = None,
) -> EvidenceLifecycleClosureBoundaryReport:
    """Audit the existing D14 boundary plus closure-specific key/path checks."""

    if any(item.payload is None for item in bundle.artifacts):
        raise ValueError("D14 closure boundary requires hydrated artifact payloads")
    base = audit_evidence_lifecycle_offline_boundary(bundle)
    filesystem = (
        audit_evidence_lifecycle_offline_directory(directory).accepted
        if directory is not None
        else base.accepted
    )
    checks = tuple(_artifact_check(bundle, item) for item in bundle.artifacts)
    discovered_count = sum(
        len(discover_keys(_json_payload(item)))
        for item in bundle.artifacts
        if item.media_type == "application/json"
    )
    forbidden = tuple(sorted({key for item in checks for key in item["forbidden_keys"]}))
    paths = tuple(item.relative_path for item in bundle.artifacts)
    accepted = bool(
        bundle.ready
        and base.accepted
        and filesystem
        and len(bundle.artifacts) == 21
        and len(paths) == len(set(paths))
        and not forbidden
        and all(item["accepted"] for item in checks)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "source_boundary": bundle.boundary,
        "closure_boundary": EVIDENCE_LIFECYCLE_CLOSURE_BOUNDARY,
        "forbidden_keys": forbidden,
        "discovered_key_count": discovered_count,
        "artifact_checks": checks,
        "filesystem_accepted": filesystem,
        "accepted": accepted,
    }
    return EvidenceLifecycleClosureBoundaryReport(
        bundle_id=bundle.bundle_id,
        source_boundary=bundle.boundary,
        forbidden_keys=forbidden,
        discovered_key_count=discovered_count,
        artifact_checks=checks,
        filesystem_accepted=filesystem,
        accepted=accepted,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-boundary"),
    )


def _json_payload(artifact: Any) -> Any:
    if artifact.payload is None or artifact.media_type != "application/json":
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def evidence_lifecycle_closure_key_inventory(
    bundle: EvidenceLifecycleOfflineBundle,
) -> dict[str, Any]:
    """Return an aggregate key inventory for closure review tooling."""

    rows = []
    for artifact in bundle.artifacts:
        value = _json_payload(artifact)
        keys = discover_keys(value) if value is not None else ()
        rows.append(
            {
                "artifact_id": artifact.artifact_id,
                "key_count": len(keys),
                "forbidden_keys": list(forbidden_keys(value)),
                "content_address": artifact.content_address,
            }
        )
    body = {
        "bundle_id": bundle.bundle_id,
        "artifacts": tuple(rows),
        "accepted": all(not row["forbidden_keys"] for row in rows),
    }
    return jsonable(
        body
        | {"content_address": content_hash(body, prefix="evidence-lifecycle-closure-key-inventory")}
    )


__all__ = [
    "audit_evidence_lifecycle_closure_boundary",
    "evidence_lifecycle_closure_key_inventory",
]

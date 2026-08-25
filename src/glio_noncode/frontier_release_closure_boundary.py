"""Boundary audit for the cross-domain D13-D16 release snapshot."""

from __future__ import annotations

from typing import Any

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
    FRONTIER_RELEASE_CLOSURE_BOUNDARY,
    FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
    FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
    FrontierReleaseBoundaryReport,
    FrontierReleaseClosureCheck,
    frontier_release_closure_check,
)
from .frontier_release_closure_support import (
    discover_keys,
    forbidden_keys,
    safe_relative_path,
)
from .serialization import content_hash


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> FrontierReleaseClosureCheck:
    return frontier_release_closure_check(check_id, "public", passed, observed, expected, detail)


def audit_frontier_release_boundary(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseBoundaryReport:
    rows = snapshot.to_dict()
    artifacts = rows.get("artifacts", ())
    domains = rows.get("domains", ())
    dependencies = rows.get("dependencies", ())
    gates = rows.get("gates", ())
    forbidden = forbidden_keys(rows)
    artifact_paths = tuple(str(item.get("relative_path", "")) for item in artifacts)
    artifact_refs = tuple(str(item.get("artifact_ref", "")) for item in artifacts)
    domain_ids = tuple(str(item.get("domain_id", "")) for item in domains)
    dependency_pairs = tuple(
        (str(item.get("source_domain_id", "")), str(item.get("target_domain_id", "")))
        for item in dependencies
    )
    checks = (
        _check(
            "boundary-identity",
            snapshot.boundary == FRONTIER_RELEASE_CLOSURE_BOUNDARY,
            snapshot.boundary,
            FRONTIER_RELEASE_CLOSURE_BOUNDARY,
            "release snapshot boundary is explicit",
        ),
        _check(
            "domain-count",
            len(domains) == FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            len(domains),
            FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            "all four D13-D16 domains are present",
        ),
        _check(
            "domain-order",
            domain_ids == FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
            domain_ids,
            FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
            "domain order is the declared release order",
        ),
        _check(
            "domain-acceptance",
            all(bool(item.get("accepted")) for item in domains),
            sum(bool(item.get("accepted")) for item in domains),
            FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            "every domain closure is accepted",
        ),
        _check(
            "artifact-count",
            len(artifacts) == FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(artifacts),
            FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "all domain artifact manifests are conserved",
        ),
        _check(
            "artifact-refs-unique",
            len(artifact_refs) == len(set(artifact_refs)) and all(artifact_refs),
            len(set(artifact_refs)),
            len(artifact_refs),
            "artifact references are namespaced and unique",
        ),
        _check(
            "artifact-paths-safe",
            all(safe_relative_path(path) for path in artifact_paths),
            sum(safe_relative_path(path) for path in artifact_paths),
            len(artifact_paths),
            "all artifact paths are safe relative paths",
        ),
        _check(
            "artifact-addresses",
            all(str(item.get("source_content_address", "")) for item in artifacts),
            sum(bool(item.get("source_content_address")) for item in artifacts),
            len(artifacts),
            "all source artifacts retain an address",
        ),
        _check(
            "dependency-count",
            len(dependencies) == FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            len(dependencies),
            FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            "release dependency matrix is complete",
        ),
        _check(
            "dependency-order",
            all(source < target for source, target in dependency_pairs),
            dependency_pairs,
            "acyclic D13-to-D16 ordering",
            "dependencies only point forward",
        ),
        _check(
            "gate-count",
            len(gates) == FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
            len(gates),
            FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
            "six release gates exist for every domain",
        ),
        _check(
            "gate-acceptance",
            all(bool(item.get("passed")) for item in gates),
            sum(bool(item.get("passed")) for item in gates),
            len(gates),
            "all release gates pass",
        ),
        _check(
            "forbidden-key-boundary",
            not forbidden,
            forbidden,
            (),
            "public release projection contains no forbidden identity fields",
        ),
    )
    accepted = snapshot.accepted and all(item.passed for item in checks)
    body = {
        "bundle_id": snapshot.bundle_id,
        "source_boundary": snapshot.boundary,
        "forbidden_keys": forbidden,
        "discovered_key_count": len(discover_keys(rows)),
        "checks": checks,
        "accepted": accepted,
    }
    return FrontierReleaseBoundaryReport(
        **body,
        content_address=content_hash(body, prefix="frontier-release-boundary"),
    )


def frontier_release_key_inventory(snapshot: FrontierReleaseSnapshot) -> dict[str, Any]:
    keys = discover_keys(snapshot.to_dict())
    terminals = {path.rsplit(".", 1)[-1].split("[", 1)[0] for path in keys}
    forbidden = tuple(sorted(forbidden_keys({key: True for key in terminals})))
    body = {
        "bundle_id": snapshot.bundle_id,
        "key_count": len(keys),
        "keys": keys,
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
    }
    return body | {"content_address": content_hash(body, prefix="frontier-release-key-inventory")}


__all__ = ["audit_frontier_release_boundary", "frontier_release_key_inventory"]

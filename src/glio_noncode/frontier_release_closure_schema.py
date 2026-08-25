"""Machine-readable schema and shape audit for the release projection."""

from __future__ import annotations

from typing import Any

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
    FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
    FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
    frontier_release_closure_check,
)
from .frontier_release_closure_support import all_rows, discover_keys, forbidden_keys
from .serialization import content_hash

FRONTIER_RELEASE_SCHEMA_RESOURCE_COUNT = 5


def build_frontier_release_schema() -> dict[str, Any]:
    resources = {
        "domains": {
            "required": ("domain_id", "bundle_id", "content_address", "accepted"),
            "identity": "domain_id",
        },
        "artifacts": {
            "required": ("artifact_ref", "domain_id", "relative_path", "content_address"),
            "identity": "artifact_ref",
        },
        "dependencies": {
            "required": (
                "dependency_id",
                "source_domain_id",
                "target_domain_id",
                "content_address",
            ),
            "identity": "dependency_id",
        },
        "gates": {
            "required": ("gate_id", "domain_id", "gate_type", "passed", "content_address"),
            "identity": "gate_id",
        },
        "runtime": {
            "required": ("domain_id", "runtime_content_address", "accepted", "content_address"),
            "identity": "domain_id",
        },
    }
    body = {
        "version": "frontier-release-schema-v1",
        "boundary": "public_aggregate_frontier_release_closure_handoff",
        "resources": resources,
        "public_policy": {
            "aggregate_only": True,
            "forbidden_keys": "recursive terminal-key denylist",
            "safe_paths": True,
        },
    }
    return body | {"content_address": content_hash(body, prefix="frontier-release-schema")}


def audit_frontier_release_schema(
    snapshot: FrontierReleaseSnapshot,
    schema: dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    schema = schema or build_frontier_release_schema()
    rows = all_rows(snapshot)
    resources = schema.get("resources", {})
    checks = (
        frontier_release_closure_check(
            "schema-version",
            "public",
            schema.get("version") == "frontier-release-schema-v1",
            schema.get("version"),
            "frontier-release-schema-v1",
            "schema version is current",
        ),
        frontier_release_closure_check(
            "schema-address",
            "public",
            str(schema.get("content_address", "")).startswith("frontier-release-schema:"),
            schema.get("content_address"),
            "frontier-release-schema:*",
            "schema is addressed",
        ),
        frontier_release_closure_check(
            "schema-resource-count",
            "public",
            len(resources) == FRONTIER_RELEASE_SCHEMA_RESOURCE_COUNT,
            len(resources),
            FRONTIER_RELEASE_SCHEMA_RESOURCE_COUNT,
            "all release resources have schemas",
        ),
        frontier_release_closure_check(
            "schema-domain-count",
            "domain",
            len(rows["domains"]) == FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            len(rows["domains"]),
            FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            "domain rows match schema denominator",
        ),
        frontier_release_closure_check(
            "schema-artifact-count",
            "artifact",
            len(rows["artifacts"]) == FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(rows["artifacts"]),
            FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "artifact rows match schema denominator",
        ),
        frontier_release_closure_check(
            "schema-dependency-count",
            "dependency",
            len(rows["dependencies"]) == FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            len(rows["dependencies"]),
            FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            "dependency rows match schema denominator",
        ),
        frontier_release_closure_check(
            "schema-gate-count",
            "gate",
            len(rows["gates"]) == FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
            len(rows["gates"]),
            FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
            "gate rows match schema denominator",
        ),
        frontier_release_closure_check(
            "schema-runtime-count",
            "runtime",
            len(rows["runtime"]) == FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            len(rows["runtime"]),
            FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            "runtime rows match schema denominator",
        ),
        frontier_release_closure_check(
            "schema-required-fields",
            "public",
            all(
                all(field in row for field in spec["required"])
                for resource, spec in resources.items()
                for row in rows.get(resource, ())
            ),
            len(resources),
            len(resources),
            "all projected rows carry required fields",
        ),
        frontier_release_closure_check(
            "schema-forbidden-keys",
            "public",
            not forbidden_keys(snapshot.to_dict()),
            forbidden_keys(snapshot.to_dict()),
            (),
            "schema projection contains no forbidden keys",
        ),
        frontier_release_closure_check(
            "schema-key-inventory",
            "public",
            bool(discover_keys(snapshot.to_dict())),
            len(discover_keys(snapshot.to_dict())),
            ">0",
            "schema projection has discoverable keys",
        ),
    )
    return checks


__all__ = [
    "FRONTIER_RELEASE_SCHEMA_RESOURCE_COUNT",
    "audit_frontier_release_schema",
    "build_frontier_release_schema",
]

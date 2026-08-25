"""Machine-readable schemas and runtime shape checks for D15 closure rows."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX,
    WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_SCHEMA_VERSION,
    WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
    workbench_release_closure_check,
)
from .workbench_release_frontier_offline_closure_support import (
    all_rows,
    discover_keys,
    forbidden_keys,
)
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_SCHEMA_RESOURCE_COUNT = 16


def build_workbench_release_closure_schema() -> dict[str, Any]:
    """Return a versioned schema without embedding fixture values."""

    resources = {
        "artifacts": {
            "required": ("artifact_id", "relative_path", "media_type", "content_address"),
            "identity": "artifact_id",
        },
        "records": {
            "required": ("record_id", "capability", "operation", "role", "content_address"),
            "identity": "record_id",
        },
        "executions": {
            "required": (
                "record_id",
                "operation",
                "observed_state",
                "issue_codes",
                "content_address",
            ),
            "identity": "record_id",
        },
        "checks": {
            "required": ("check_id", "record_id", "passed", "content_address"),
            "identity": "check_id",
        },
        "sources": {"required": ("source_id", "uri", "content_address"), "identity": "source_id"},
        "validation": {
            "required": ("record_id", "passed", "content_address"),
            "identity": "record_id+ordinal",
        },
        "evidence": {
            "required": ("record_id", "input_address", "output_address", "content_address"),
            "identity": "record_id",
        },
        "edges": {
            "required": ("edge_id", "parent_id", "child_id", "relation", "content_address"),
            "identity": "edge_id",
        },
        "views": {
            "required": ("record_id", "operation", "content_address"),
            "identity": "record_id",
        },
        "queue": {
            "required": ("record_id", "priority", "issue_codes", "content_address"),
            "identity": "record_id",
        },
        "diagnostics": {
            "required": ("record_id", "severity", "issues", "content_address"),
            "identity": "record_id",
        },
        "stages": {"required": ("stage_id", "ordinal", "content_address"), "identity": "stage_id"},
        "stage_index": {
            "required": ("stage_id", "ordinal", "content_address"),
            "identity": "stage_id",
        },
        "operations": {
            "required": ("operation", "record_count", "content_address"),
            "identity": "operation",
        },
        "controls": {
            "required": ("operation", "control_count", "content_address"),
            "identity": "operation",
        },
        "failures": {"required": ("case", "state", "content_address"), "identity": "case"},
    }
    body = {
        "version": WORKBENCH_RELEASE_CLOSURE_SCHEMA_VERSION,
        "check_prefix": WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX,
        "boundary": "public_aggregate_workbench_release_closure_handoff",
        "resources": resources,
        "public_policy": {
            "aggregate_only": True,
            "forbidden_keys": "recursive terminal-key denylist",
        },
    }
    return body | {"content_address": content_hash(body, prefix="workbench-release-closure-schema")}


def audit_workbench_release_closure_schema(
    bundle: WorkbenchReleaseOfflineBundle,
    schema: dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    schema = schema or build_workbench_release_closure_schema()
    rows = all_rows(bundle)
    resources = schema.get("resources", {})
    checks = [
        workbench_release_closure_check(
            "schema-version",
            "public",
            schema.get("version") == WORKBENCH_RELEASE_CLOSURE_SCHEMA_VERSION,
            schema.get("version"),
            WORKBENCH_RELEASE_CLOSURE_SCHEMA_VERSION,
            "schema version is current",
        ),
        workbench_release_closure_check(
            "schema-address",
            "public",
            str(schema.get("content_address", "")).startswith("workbench-release-closure-schema:"),
            schema.get("content_address"),
            "workbench-release-closure-schema:*",
            "schema is addressed",
        ),
        workbench_release_closure_check(
            "schema-resource-count",
            "public",
            len(resources) == WORKBENCH_RELEASE_CLOSURE_SCHEMA_RESOURCE_COUNT,
            len(resources),
            WORKBENCH_RELEASE_CLOSURE_SCHEMA_RESOURCE_COUNT,
            "all closure row resources have schemas",
        ),
        workbench_release_closure_check(
            "schema-artifacts",
            "manifest",
            len(rows["artifacts"]) == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(rows["artifacts"]),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "artifact rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-records",
            "fixture",
            len(rows["records"]) == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            len(rows["records"]),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "record rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-sources",
            "fixture",
            len(rows["sources"]) == WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            len(rows["sources"]),
            WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            "source rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-evaluation",
            "evaluation",
            len(rows["checks"]) == WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            len(rows["checks"]),
            WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-validation",
            "validation",
            len(rows["validation"]) == WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            len(rows["validation"]),
            WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            "validation rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-evidence",
            "evidence",
            len(rows["evidence"]) == WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            len(rows["evidence"]),
            WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            "evidence rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-lineage",
            "lineage",
            len(rows["edges"]) == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-runtime",
            "runtime",
            len(rows["stages"]) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stages"]),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime rows match schema denominator",
        ),
        workbench_release_closure_check(
            "schema-required-resources",
            "public",
            set(resources) == set(rows),
            tuple(sorted(resources)),
            tuple(sorted(rows)),
            "schema and row projections have the same resource names",
        ),
        workbench_release_closure_check(
            "schema-required-fields",
            "public",
            all(resources.get(name, {}).get("required") for name in rows),
            tuple(sorted(name for name in rows if not resources.get(name, {}).get("required"))),
            (),
            "every resource declares required fields",
        ),
        workbench_release_closure_check(
            "schema-address-fields",
            "public",
            all("content_address" in resources.get(name, {}).get("required", ()) for name in rows),
            sum("content_address" in resources.get(name, {}).get("required", ()) for name in rows),
            len(rows),
            "every resource requires an address",
        ),
        workbench_release_closure_check(
            "schema-row-addresses",
            "public",
            all(row.get("content_address") for values in rows.values() for row in values),
            sum(bool(row.get("content_address")) for values in rows.values() for row in values),
            sum(len(values) for values in rows.values()),
            "all projected rows are addressed",
        ),
        workbench_release_closure_check(
            "schema-public-keys",
            "public",
            not forbidden_keys({key: True for key in discover_keys(bundle)}),
            forbidden_keys({key: True for key in discover_keys(bundle)}),
            (),
            "discovered keys stay within public policy",
        ),
        workbench_release_closure_check(
            "schema-public-aggregate",
            "public",
            bool(schema.get("public_policy", {}).get("aggregate_only")),
            schema.get("public_policy", {}).get("aggregate_only"),
            True,
            "schema declares aggregate-only output",
        ),
        workbench_release_closure_check(
            "schema-bundle-accepted",
            "release",
            bundle.accepted,
            bundle.accepted,
            True,
            "schema source bundle is accepted",
        ),
    ]
    return tuple(checks)


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_SCHEMA_RESOURCE_COUNT",
    "audit_workbench_release_closure_schema",
    "build_workbench_release_closure_schema",
]

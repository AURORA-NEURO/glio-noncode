"""Machine-readable D16 closure row schemas and shape auditing."""

from __future__ import annotations

from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_CHECK_PREFIX,
    DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_VERSION,
    DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
    deployment_frontier_closure_check,
)
from .deployment_frontier_offline_closure_support import all_rows, discover_keys, forbidden_keys
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash

DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_RESOURCE_COUNT = 19


def build_deployment_frontier_closure_schema() -> dict[str, Any]:
    resources = {
        "artifacts": {
            "required": ("artifact_id", "relative_path", "media_type", "content_address"),
            "identity": "artifact_id",
        },
        "records": {
            "required": ("record_id", "operation", "role", "expected_state", "content_address"),
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
            "required": ("cell_id", "record_id", "passed", "content_address"),
            "identity": "cell_id",
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
            "required": ("record_id", "operation", "state", "content_address"),
            "identity": "record_id",
        },
        "queue": {
            "required": ("queue_id", "record_id", "priority", "content_address"),
            "identity": "queue_id",
        },
        "diagnostics": {
            "required": ("finding_id", "record_id", "severity", "content_address"),
            "identity": "finding_id",
        },
        "stages": {"required": ("stage_id", "sequence", "content_address"), "identity": "stage_id"},
        "stage_index": {
            "required": ("stage_id", "sequence", "content_address"),
            "identity": "stage_id",
        },
        "operations": {
            "required": ("operation", "record_ids", "content_address"),
            "identity": "operation",
        },
        "controls": {"required": ("record_id", "role", "content_address"), "identity": "record_id"},
        "failures": {
            "required": ("probe_id", "operation", "content_address"),
            "identity": "probe_id",
        },
        "audit_events": {
            "required": ("event_id", "sequence", "content_address"),
            "identity": "event_id",
        },
        "transcript_events": {
            "required": ("sequence", "stage_id", "content_address"),
            "identity": "sequence+stage_id",
        },
        "trace_observations": {
            "required": ("sequence", "stage_id", "output_address", "content_address"),
            "identity": "sequence",
        },
    }
    body = {
        "version": DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_VERSION,
        "check_prefix": DEPLOYMENT_FRONTIER_CLOSURE_CHECK_PREFIX,
        "boundary": "public_aggregate_deployment_closure_handoff",
        "resources": resources,
        "public_policy": {
            "aggregate_only": True,
            "forbidden_keys": "recursive terminal-key denylist",
        },
    }
    return body | {
        "content_address": content_hash(body, prefix="deployment-frontier-closure-schema")
    }


def audit_deployment_frontier_closure_schema(
    bundle: DeploymentFrontierOfflineBundle,
    schema: dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    schema = schema or build_deployment_frontier_closure_schema()
    rows = all_rows(bundle)
    resources = schema.get("resources", {})
    checks = (
        deployment_frontier_closure_check(
            "schema-version",
            "public",
            schema.get("version") == DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_VERSION,
            schema.get("version"),
            DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_VERSION,
            "schema version is current",
        ),
        deployment_frontier_closure_check(
            "schema-address",
            "public",
            str(schema.get("content_address", "")).startswith(
                "deployment-frontier-closure-schema:"
            ),
            schema.get("content_address"),
            "deployment-frontier-closure-schema:*",
            "schema is addressed",
        ),
        deployment_frontier_closure_check(
            "schema-resource-count",
            "public",
            len(resources) == DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_RESOURCE_COUNT,
            len(resources),
            DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_RESOURCE_COUNT,
            "all closure resources have schemas",
        ),
        deployment_frontier_closure_check(
            "schema-artifacts",
            "manifest",
            len(rows["artifacts"]) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len(rows["artifacts"]),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "artifact rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-records",
            "fixture",
            len(rows["records"]) == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            len(rows["records"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "record rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-sources",
            "fixture",
            len(rows["sources"]) == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            len(rows["sources"]),
            DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            "source rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-evaluation",
            "evaluation",
            len(rows["checks"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            len(rows["checks"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-validation",
            "validation",
            len(rows["validation"]) == DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            len(rows["validation"]),
            DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            "validation rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-evidence",
            "evidence",
            len(rows["evidence"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            len(rows["evidence"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            "evidence rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-lineage",
            "lineage",
            len(rows["edges"]) == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-runtime",
            "runtime",
            len(rows["stages"]) == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stages"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime rows match schema denominator",
        ),
        deployment_frontier_closure_check(
            "schema-required-resources",
            "public",
            set(resources) == set(rows),
            tuple(sorted(resources)),
            tuple(sorted(rows)),
            "schema and projections have the same resource names",
        ),
        deployment_frontier_closure_check(
            "schema-required-fields",
            "public",
            all(resources.get(name, {}).get("required") for name in rows),
            tuple(sorted(name for name in rows if not resources.get(name, {}).get("required"))),
            (),
            "every resource declares required fields",
        ),
        deployment_frontier_closure_check(
            "schema-address-fields",
            "public",
            all("content_address" in resources.get(name, {}).get("required", ()) for name in rows),
            sum("content_address" in resources.get(name, {}).get("required", ()) for name in rows),
            len(rows),
            "every resource requires an address",
        ),
        deployment_frontier_closure_check(
            "schema-row-addresses",
            "public",
            all(row.get("content_address") for values in rows.values() for row in values),
            sum(bool(row.get("content_address")) for values in rows.values() for row in values),
            sum(len(values) for values in rows.values()),
            "all projected rows are addressed",
        ),
        deployment_frontier_closure_check(
            "schema-public-keys",
            "public",
            not forbidden_keys({key: True for key in discover_keys(bundle)}),
            forbidden_keys({key: True for key in discover_keys(bundle)}),
            (),
            "discovered keys stay public",
        ),
        deployment_frontier_closure_check(
            "schema-aggregate-policy",
            "public",
            bool(schema.get("public_policy", {}).get("aggregate_only")),
            schema.get("public_policy", {}).get("aggregate_only"),
            True,
            "schema declares aggregate-only output",
        ),
        deployment_frontier_closure_check(
            "schema-source-accepted",
            "release",
            bundle.accepted,
            bundle.accepted,
            True,
            "source bundle is accepted",
        ),
    )
    return checks


__all__ = [
    "DEPLOYMENT_FRONTIER_CLOSURE_SCHEMA_RESOURCE_COUNT",
    "audit_deployment_frontier_closure_schema",
    "build_deployment_frontier_closure_schema",
]

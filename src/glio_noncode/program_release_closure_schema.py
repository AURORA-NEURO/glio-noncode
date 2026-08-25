"""Closed schema description for public aggregate release consumers."""

from __future__ import annotations

from typing import Any

from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
    PROGRAM_RELEASE_CLOSURE_BOUNDARY,
    PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
    PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
    PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
    PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT,
    PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT,
    PROGRAM_RELEASE_CLOSURE_PLAN_STEP_COUNT,
    PROGRAM_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL,
    PROGRAM_RELEASE_CLOSURE_SCHEMA_VERSION,
    PROGRAM_RELEASE_CLOSURE_VERSION,
    ProgramReleaseSnapshot,
)
from .program_release_closure_support import forbidden_keys
from .serialization import content_hash, jsonable


def program_release_closure_schema() -> dict[str, Any]:
    return {
        "schema_version": PROGRAM_RELEASE_CLOSURE_SCHEMA_VERSION,
        "version": PROGRAM_RELEASE_CLOSURE_VERSION,
        "title": "D01-D16 public aggregate program release closure",
        "boundary": PROGRAM_RELEASE_CLOSURE_BOUNDARY,
        "encoding": "UTF-8",
        "addressing": {
            "algorithm": "sha256",
            "projection_rule": "canonical JSON with terminal newline",
            "payload_rule": "no opaque source payloads",
        },
        "resources": {
            "domains": PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
            "artifacts": PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "dependencies": PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            "gates": PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
            "certification_checks": PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
            "runtime_stages": PROGRAM_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL,
            "observability_events": PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT,
            "observability_metrics": PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT,
            "plan_steps": PROGRAM_RELEASE_CLOSURE_PLAN_STEP_COUNT,
        },
        "public_boundary": {
            "aggregate_only": True,
            "private_identity_values": False,
            "attribution_metadata": False,
            "model_metadata": False,
            "network_required": False,
        },
        "query": {
            "resources": ("domains", "artifacts", "dependencies", "gates", "runtime"),
            "default_limit": 50,
            "max_limit": 500,
        },
        "exports": {
            "artifact_count": 15,
            "manifest": "manifest.json",
            "media_type": "application/json",
        },
    }


def validate_program_release_closure_schema(
    snapshot: ProgramReleaseSnapshot, schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    selected = schema or program_release_closure_schema()
    resources = selected["resources"]
    checks = {
        "version": selected.get("version") == PROGRAM_RELEASE_CLOSURE_VERSION,
        "boundary": selected.get("boundary") == PROGRAM_RELEASE_CLOSURE_BOUNDARY,
        "domains": len(snapshot.domains) == resources["domains"],
        "artifacts": len(snapshot.artifacts) == resources["artifacts"],
        "dependencies": len(snapshot.dependencies) == resources["dependencies"],
        "gates": len(snapshot.gates) == resources["gates"],
        "public_keys": not forbidden_keys(jsonable(snapshot)),
        "accepted": snapshot.accepted,
    }
    body = {
        "schema_version": selected.get("schema_version"),
        "checks": checks,
        "accepted": all(checks.values()),
    }
    body["content_address"] = content_hash(body, prefix="program-release-schema-report")
    return body


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE")
    or name.startswith("program_release_closure_schema")
    or name.startswith("validate_program_release_closure_schema")
    or name.startswith("ProgramRelease")
]

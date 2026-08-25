"""Schema descriptions and in-memory validation for D13 closure projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_contracts import (
    VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION,
    ValidationDesignClosurePlane,
    validation_design_closure_check,
)


def validation_design_closure_schema() -> dict[str, Any]:
    """Return the public JSON Schema for a closure runtime report."""

    address = {"type": "string", "minLength": 1}
    check = {
        "type": "object",
        "required": [
            "check_id",
            "plane",
            "passed",
            "observed",
            "required",
            "detail",
            "content_address",
        ],
        "properties": {
            "check_id": {"type": "string", "minLength": 1},
            "plane": {"type": "string", "minLength": 1},
            "passed": {"type": "boolean"},
            "observed": {},
            "required": {},
            "detail": {"type": "string"},
            "content_address": address,
        },
        "additionalProperties": False,
    }
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"glio-noncode/{VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION}",
        "title": "GLIO-NONCODE validation-design closure handoff",
        "type": "object",
        "required": [
            "version",
            "run_id",
            "state",
            "stages",
            "bundle",
            "boundary",
            "indexes",
            "reconciliation",
            "summary",
            "certification",
            "observability",
            "replay",
            "accepted",
            "content_address",
        ],
        "properties": {
            "version": {"const": "validation-design-closure-runtime-v1"},
            "run_id": {"type": "string", "minLength": 1},
            "state": {"enum": ["ready", "blocked", "empty"]},
            "stages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "stage_id",
                        "ordinal",
                        "state",
                        "input_address",
                        "output_address",
                        "detail",
                        "content_address",
                    ],
                },
            },
            "bundle": {"type": "object"},
            "boundary": {
                "type": "object",
                "required": [
                    "bundle_id",
                    "forbidden_keys",
                    "discovered_keys",
                    "path_checks",
                    "artifact_checks",
                    "accepted",
                    "content_address",
                ],
            },
            "indexes": {
                "type": "object",
                "required": ["bundle_id", "resource_counts", "accepted", "content_address"],
            },
            "reconciliation": {
                "type": "object",
                "required": ["version", "bundle_id", "checks", "accepted", "content_address"],
                "properties": {"checks": {"type": "array", "items": check}},
            },
            "summary": {
                "type": "object",
                "required": [
                    "bundle_id",
                    "counters",
                    "operations",
                    "states",
                    "planes",
                    "accepted",
                    "content_address",
                ],
            },
            "certification": {
                "type": "object",
                "required": [
                    "version",
                    "bundle_id",
                    "artifact_count",
                    "check_count",
                    "passed_check_count",
                    "failed_check_count",
                    "coverage_percent",
                    "domains",
                    "checks",
                    "accepted",
                    "content_address",
                ],
            },
            "observability": {
                "type": "object",
                "required": ["bundle_id", "events", "metrics", "accepted", "content_address"],
            },
            "replay": {
                "type": "object",
                "required": [
                    "first_address",
                    "second_address",
                    "expected_address",
                    "deterministic",
                    "accepted",
                    "content_address",
                ],
            },
            "accepted": {"type": "boolean"},
            "content_address": address,
        },
        "additionalProperties": False,
    }
    schema["content_address"] = content_hash(schema, prefix="validation-design-closure-schema")
    return schema


def validate_validation_design_closure_projection(value: Any) -> dict[str, Any]:
    """Perform strict structural checks without requiring a JSON-schema package."""

    required = (
        "version",
        "run_id",
        "state",
        "stages",
        "bundle",
        "boundary",
        "indexes",
        "reconciliation",
        "summary",
        "certification",
        "observability",
        "replay",
        "accepted",
        "content_address",
    )
    checks = [
        validation_design_closure_check(
            "schema-object",
            ValidationDesignClosurePlane.MANIFEST,
            isinstance(value, Mapping),
            type(value).__name__,
            "mapping",
            "closure projection is an object",
        ),
    ]
    if not isinstance(value, Mapping):
        return {
            "schema_version": VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION,
            "checks": [item.to_dict() for item in checks],
            "accepted": False,
            "content_address": content_hash(
                {"checks": checks, "accepted": False},
                prefix="validation-design-closure-schema-validation",
            ),
        }
    missing = tuple(field for field in required if field not in value)
    checks.extend(
        (
            validation_design_closure_check(
                "schema-required-fields",
                ValidationDesignClosurePlane.MANIFEST,
                not missing,
                missing,
                (),
                "closure projection has all required fields",
            ),
            validation_design_closure_check(
                "schema-version",
                ValidationDesignClosurePlane.MANIFEST,
                value.get("version") == "validation-design-closure-runtime-v1",
                value.get("version"),
                "validation-design-closure-runtime-v1",
                "runtime version is closed",
            ),
            validation_design_closure_check(
                "schema-state",
                ValidationDesignClosurePlane.MANIFEST,
                value.get("state") in {"ready", "blocked", "empty"},
                value.get("state"),
                ["ready", "blocked", "empty"],
                "runtime state is recognized",
            ),
            validation_design_closure_check(
                "schema-stages-array",
                ValidationDesignClosurePlane.RUNTIME,
                isinstance(value.get("stages"), list),
                type(value.get("stages")).__name__,
                "list",
                "runtime stages are an array",
            ),
            validation_design_closure_check(
                "schema-accepted-boolean",
                ValidationDesignClosurePlane.MANIFEST,
                isinstance(value.get("accepted"), bool),
                type(value.get("accepted")).__name__,
                "bool",
                "accepted is boolean",
            ),
            validation_design_closure_check(
                "schema-address",
                ValidationDesignClosurePlane.MANIFEST,
                str(value.get("content_address", "")).startswith(
                    "validation-design-closure-runtime:"
                ),
                value.get("content_address"),
                "validation-design-closure-runtime:",
                "runtime projection is addressed",
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {
        "schema_version": VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION,
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return {
        "schema_version": VALIDATION_DESIGN_CLOSURE_SCHEMA_VERSION,
        "checks": [item.to_dict() for item in checks],
        "accepted": accepted,
        "content_address": content_hash(body, prefix="validation-design-closure-schema-validation"),
    }


__all__ = [
    "validate_validation_design_closure_projection",
    "validation_design_closure_schema",
]

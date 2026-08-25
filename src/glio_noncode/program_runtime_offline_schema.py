"""Schema and structural validation for program-runtime handoffs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX,
    PROGRAM_RUNTIME_OFFLINE_BOUNDARY,
    PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION,
    PROGRAM_RUNTIME_OFFLINE_CHECK_PREFIX,
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_HANDOFF_STAGE_COUNT,
    PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS,
    PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
    PROGRAM_RUNTIME_OFFLINE_SCHEMA_VERSION,
)
from .serialization import content_hash, jsonable


def program_runtime_offline_bundle_schema() -> dict[str, Any]:
    """Return the closed manifest schema used by validators and consumers."""

    return {
        "schema_version": PROGRAM_RUNTIME_OFFLINE_SCHEMA_VERSION,
        "title": "Architecture program public aggregate offline bundle",
        "boundary": PROGRAM_RUNTIME_OFFLINE_BOUNDARY,
        "encoding": "UTF-8",
        "addressing": {
            "artifact_prefix": PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX,
            "check_prefix": PROGRAM_RUNTIME_OFFLINE_CHECK_PREFIX,
            "root_prefix": "program-runtime-offline-bundle",
            "algorithm": "sha256",
            "payload_rule": "exact bytes written to relative_path",
        },
        "manifest": {
            "filename": "bundle.json",
            "required": [
                "bundle_id",
                "version",
                "boundary",
                "run_id",
                "state",
                "accepted",
                "artifacts",
                "checks",
                "runtime_address",
                "domain_count",
                "stage_count",
                "warning_count",
                "content_address",
            ],
        },
        "artifact": {
            "required": [
                "artifact_id",
                "relative_path",
                "media_type",
                "kind",
                "byte_count",
                "line_count",
                "content_address",
            ],
            "payload": "stored in relative_path; optional in manifest projections",
            "max_count": PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS,
        },
        "check": {
            "required": [
                "check_id",
                "plane",
                "passed",
                "observed",
                "required",
                "detail",
                "content_address",
            ]
        },
        "denominators": {
            "domains": PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "program_checks": PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "quality_checks": PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            "runtime_stages": PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "offline_runtime_stages": PROGRAM_RUNTIME_OFFLINE_HANDOFF_STAGE_COUNT,
            "portable_artifacts": PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
        },
        "resources": [
            "artifacts",
            "domains",
            "operations",
            "checks",
            "stages",
            "quality",
            "release_checks",
            "specifications",
            "capabilities",
            "states",
        ],
        "public_boundary": {
            "aggregate_only": True,
            "private_identity_values": False,
            "attribution_metadata": False,
            "model_metadata": False,
            "network_required": False,
        },
    }


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> dict[str, Any]:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return body | {
        "content_address": content_hash(body, prefix="program-runtime-offline-schema-check")
    }


def validate_program_runtime_offline_manifest(value: Any) -> dict[str, Any]:
    """Validate manifest shape without reading any producer modules."""

    schema = program_runtime_offline_bundle_schema()
    checks: list[dict[str, Any]] = []
    is_object = isinstance(value, Mapping)
    checks.append(
        _check("manifest-object", is_object, type(value).__name__, "dict", "manifest is an object")
    )
    if not is_object:
        body = {
            "schema_version": PROGRAM_RUNTIME_OFFLINE_SCHEMA_VERSION,
            "accepted": False,
            "checks": checks,
        }
        return body | {
            "content_address": content_hash(body, prefix="program-runtime-offline-schema-report")
        }
    required = tuple(schema["manifest"]["required"])
    missing = tuple(key for key in required if key not in value)
    checks.append(
        _check(
            "manifest-required-fields",
            not missing,
            missing,
            (),
            "all required manifest fields are present",
        )
    )
    checks.append(
        _check(
            "manifest-version",
            value.get("version") == PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION,
            value.get("version"),
            PROGRAM_RUNTIME_OFFLINE_BUNDLE_VERSION,
            "manifest version is supported",
        )
    )
    checks.append(
        _check(
            "manifest-boundary",
            value.get("boundary") == PROGRAM_RUNTIME_OFFLINE_BOUNDARY,
            value.get("boundary"),
            PROGRAM_RUNTIME_OFFLINE_BOUNDARY,
            "manifest boundary is the public aggregate boundary",
        )
    )
    artifacts = value.get("artifacts", ())
    checks.append(
        _check(
            "artifact-list",
            isinstance(artifacts, list),
            type(artifacts).__name__,
            "list",
            "artifact inventory is a list",
        )
    )
    if isinstance(artifacts, list):
        checks.append(
            _check(
                "artifact-ceiling",
                len(artifacts) <= PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS,
                len(artifacts),
                PROGRAM_RUNTIME_OFFLINE_MAX_ARTIFACTS,
                "artifact ceiling is respected",
            )
        )
        ids = [item.get("artifact_id") for item in artifacts if isinstance(item, Mapping)]
        paths = [item.get("relative_path") for item in artifacts if isinstance(item, Mapping)]
        checks.append(
            _check(
                "artifact-identities",
                len(ids) == len(set(ids)),
                len(set(ids)),
                len(ids),
                "artifact ids are unique",
            )
        )
        checks.append(
            _check(
                "artifact-paths",
                len(paths) == len(set(paths)),
                len(set(paths)),
                len(paths),
                "artifact paths are unique",
            )
        )
        checks.extend(
            _check(
                f"artifact-{index}-fields",
                isinstance(item, Mapping)
                and all(field in item for field in schema["artifact"]["required"]),
                tuple(
                    field
                    for field in schema["artifact"]["required"]
                    if not isinstance(item, Mapping) or field not in item
                ),
                (),
                "artifact has the closed required field set",
            )
            for index, item in enumerate(artifacts)
        )
    checks_value = value.get("checks", ())
    checks.append(
        _check(
            "check-list",
            isinstance(checks_value, list),
            type(checks_value).__name__,
            "list",
            "invariant checks are a list",
        )
    )
    if isinstance(checks_value, list):
        checks.append(
            _check(
                "check-identities",
                len({item.get("check_id") for item in checks_value if isinstance(item, Mapping)})
                == len(checks_value),
                len(checks_value),
                len(checks_value),
                "check ids are unique",
            )
        )
    checks.append(
        _check(
            "domain-count-field",
            value.get("domain_count") == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            value.get("domain_count"),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "domain denominator is closed",
        )
    )
    checks.append(
        _check(
            "stage-count-field",
            value.get("stage_count") == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            value.get("stage_count"),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "stage denominator is closed",
        )
    )
    accepted = all(item["passed"] for item in checks)
    body = {
        "schema_version": PROGRAM_RUNTIME_OFFLINE_SCHEMA_VERSION,
        "accepted": accepted,
        "check_count": len(checks),
        "passed_check_count": sum(item["passed"] for item in checks),
        "failed_check_count": sum(not item["passed"] for item in checks),
        "checks": checks,
    }
    return jsonable(
        body
        | {"content_address": content_hash(body, prefix="program-runtime-offline-schema-report")}
    )


__all__ = ["program_runtime_offline_bundle_schema", "validate_program_runtime_offline_manifest"]

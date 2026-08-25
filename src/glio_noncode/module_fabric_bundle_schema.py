"""Closed manifest schema and structural validation for fabric bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_bundle_contracts import (
    MODULE_FABRIC_BUNDLE_VERSION,
    FabricBundleArtifactKind,
    FabricBundleState,
)
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

MODULE_FABRIC_BUNDLE_SCHEMA_VERSION = "module-fabric-bundle-schema-v1"


@dataclass(frozen=True, slots=True)
class FabricBundleSchemaCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class FabricBundleSchemaValidation:
    schema_version: str
    checks: tuple[FabricBundleSchemaCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "content_address": self.content_address,
        }


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> FabricBundleSchemaCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return FabricBundleSchemaCheck(
        **body,
        content_address=content_hash(body, prefix="module-fabric-bundle-schema-check"),
    )


def module_fabric_bundle_schema() -> dict[str, Any]:
    """Return a closed JSON Schema projection for ``bundle.json``."""

    artifact_properties = {
        "artifact_id": {"type": "string", "minLength": 1},
        "relative_path": {"type": "string", "minLength": 1},
        "media_type": {"type": "string", "minLength": 1},
        "kind": {"enum": [item.value for item in FabricBundleArtifactKind]},
        "byte_count": {"type": "integer", "minimum": 0},
        "line_count": {"type": "integer", "minimum": 0},
        "content_address": {"type": "string", "minLength": 1},
    }
    check_properties = {
        "check_id": {"type": "string", "minLength": 1},
        "plane": {"type": "string", "minLength": 1},
        "passed": {"type": "boolean"},
        "observed": {},
        "required": {},
        "detail": {"type": "string"},
        "content_address": {"type": "string", "minLength": 1},
    }
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"glio-noncode/{MODULE_FABRIC_BUNDLE_SCHEMA_VERSION}",
        "title": "GLIO-NONCODE module-fabric public bundle manifest",
        "type": "object",
        "required": [
            "bundle_id",
            "version",
            "boundary",
            "fixture_id",
            "run_id",
            "state",
            "accepted",
            "artifacts",
            "checks",
            "runtime_address",
            "warning_count",
            "artifact_count",
            "passed_check_count",
            "failed_check_count",
            "content_address",
        ],
        "properties": {
            "bundle_id": {"type": "string", "minLength": 1},
            "version": {"const": MODULE_FABRIC_BUNDLE_VERSION},
            "boundary": {"type": "string", "minLength": 1},
            "fixture_id": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "state": {"enum": [item.value for item in FabricBundleState]},
            "accepted": {"type": "boolean"},
            "artifacts": {"type": "array", "items": {"type": "object", "properties": artifact_properties}},
            "checks": {"type": "array", "items": {"type": "object", "properties": check_properties}},
            "runtime_address": {"type": "string", "minLength": 1},
            "warning_count": {"type": "integer", "minimum": 0},
            "artifact_count": {"type": "integer", "minimum": 0},
            "passed_check_count": {"type": "integer", "minimum": 0},
            "failed_check_count": {"type": "integer", "minimum": 0},
            "content_address": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    schema["content_address"] = content_hash(schema, prefix="module-fabric-bundle-schema")
    return schema


def validate_module_fabric_bundle_manifest(manifest: Any) -> FabricBundleSchemaValidation:
    """Validate required fields, cardinalities, and public keys without I/O."""

    checks: list[FabricBundleSchemaCheck] = [
        _check("manifest-object", isinstance(manifest, dict), type(manifest).__name__, "dict", "manifest root is an object"),
    ]
    if not isinstance(manifest, dict):
        body = {"checks": [item.to_dict() for item in checks], "accepted": False}
        return FabricBundleSchemaValidation(MODULE_FABRIC_BUNDLE_SCHEMA_VERSION, tuple(checks), False, content_hash(body, prefix="module-fabric-bundle-schema-validation"))
    required = (
        "bundle_id",
        "version",
        "boundary",
        "fixture_id",
        "run_id",
        "state",
        "accepted",
        "artifacts",
        "checks",
        "runtime_address",
        "content_address",
    )
    missing = tuple(item for item in required if item not in manifest)
    checks.append(_check("required-fields", not missing, list(missing), [], "all required manifest fields are present"))
    checks.append(_check("bundle-version", manifest.get("version") == MODULE_FABRIC_BUNDLE_VERSION, manifest.get("version"), MODULE_FABRIC_BUNDLE_VERSION, "bundle version is closed"))
    checks.append(_check("bundle-state", manifest.get("state") in {item.value for item in FabricBundleState}, manifest.get("state"), [item.value for item in FabricBundleState], "bundle state is recognized"))
    artifacts = manifest.get("artifacts", [])
    bundle_checks = manifest.get("checks", [])
    checks.append(_check("artifacts-array", isinstance(artifacts, list), type(artifacts).__name__, "list", "artifacts are represented as an array"))
    checks.append(_check("checks-array", isinstance(bundle_checks, list), type(bundle_checks).__name__, "list", "checks are represented as an array"))
    if isinstance(artifacts, list):
        checks.append(_check("artifact-count", manifest.get("artifact_count") == len(artifacts), manifest.get("artifact_count"), len(artifacts), "artifact_count reconciles with artifacts"))
        ids = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
        checks.append(_check("artifact-identities", len(ids) == len(set(ids)), len(set(ids)), len(ids), "artifact identities are unique"))
    if isinstance(bundle_checks, list):
        passed = sum(bool(item.get("passed")) for item in bundle_checks if isinstance(item, dict))
        checks.append(_check("check-counts", manifest.get("passed_check_count") == passed and manifest.get("failed_check_count") == len(bundle_checks) - passed, {"passed": manifest.get("passed_check_count"), "failed": manifest.get("failed_check_count")}, {"passed": passed, "failed": len(bundle_checks) - passed}, "check counts conserve the manifest checks"))
    checks.append(_check("public-boundary", not _has_forbidden_key(manifest) and not contains_private_key(manifest), True, True, "manifest contains no private or attribution keys"))
    accepted = all(item.passed for item in checks)
    body = {"checks": [item.to_dict() for item in checks], "accepted": accepted}
    return FabricBundleSchemaValidation(MODULE_FABRIC_BUNDLE_SCHEMA_VERSION, tuple(checks), accepted, content_hash(body, prefix="module-fabric-bundle-schema-validation"))


__all__ = [
    "MODULE_FABRIC_BUNDLE_SCHEMA_VERSION",
    "FabricBundleSchemaCheck",
    "FabricBundleSchemaValidation",
    "module_fabric_bundle_schema",
    "validate_module_fabric_bundle_manifest",
]

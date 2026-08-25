"""Closed manifest schema and validation for the D14 offline boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable
from .evidence_lifecycle_frontier_offline_contracts import (
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION,
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_SCHEMA_VERSION,
    EvidenceLifecycleOfflineArtifactKind,
    EvidenceLifecycleOfflineBundleState,
)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineSchemaCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineSchemaValidation:
    schema_version: str
    checks: tuple[EvidenceLifecycleOfflineSchemaCheck, ...]
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


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleOfflineSchemaCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return EvidenceLifecycleOfflineSchemaCheck(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-offline-schema-check"),
    )


def evidence_lifecycle_offline_bundle_schema() -> dict[str, Any]:
    """Return a closed JSON Schema projection for ``bundle.json``."""

    artifact_properties = {
        "artifact_id": {"type": "string", "minLength": 1},
        "relative_path": {"type": "string", "minLength": 1},
        "media_type": {"type": "string", "minLength": 1},
        "kind": {"enum": [item.value for item in EvidenceLifecycleOfflineArtifactKind]},
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
        "detail": {"type": "string", "minLength": 1},
        "content_address": {"type": "string", "minLength": 1},
    }
    required = [
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
    ]
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"glio-noncode/{EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_SCHEMA_VERSION}",
        "title": "GLIO-NONCODE D14 evidence lifecycle public bundle manifest",
        "type": "object",
        "required": required,
        "properties": {
            "bundle_id": {"type": "string", "minLength": 1},
            "version": {"const": EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION},
            "boundary": {"type": "string", "minLength": 1},
            "fixture_id": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "state": {"enum": [item.value for item in EvidenceLifecycleOfflineBundleState]},
            "accepted": {"type": "boolean"},
            "artifacts": {
                "type": "array",
                "items": {"type": "object", "properties": artifact_properties, "required": list(artifact_properties), "additionalProperties": False},
            },
            "checks": {
                "type": "array",
                "items": {"type": "object", "properties": check_properties, "required": list(check_properties), "additionalProperties": False},
            },
            "runtime_address": {"type": "string", "minLength": 1},
            "warning_count": {"type": "integer", "minimum": 0},
            "artifact_count": {"type": "integer", "minimum": 0},
            "passed_check_count": {"type": "integer", "minimum": 0},
            "failed_check_count": {"type": "integer", "minimum": 0},
            "content_address": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    schema["content_address"] = content_hash(schema, prefix="evidence-lifecycle-offline-schema")
    return schema


def validate_evidence_lifecycle_offline_manifest(manifest: Any) -> EvidenceLifecycleOfflineSchemaValidation:
    """Validate manifest shape without reading artifact files."""

    checks: list[EvidenceLifecycleOfflineSchemaCheck] = [_check("manifest-object", isinstance(manifest, dict), type(manifest).__name__, "dict", "manifest root is an object")]
    if not isinstance(manifest, dict):
        body = {"checks": [item.to_dict() for item in checks], "accepted": False}
        return EvidenceLifecycleOfflineSchemaValidation(EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_SCHEMA_VERSION, tuple(checks), False, content_hash(body, prefix="evidence-lifecycle-offline-schema-validation"))
    required = ("bundle_id", "version", "boundary", "fixture_id", "run_id", "state", "accepted", "artifacts", "checks", "runtime_address", "warning_count", "artifact_count", "passed_check_count", "failed_check_count", "content_address")
    missing = tuple(item for item in required if item not in manifest)
    checks.append(_check("required-fields", not missing, list(missing), [], "all required manifest fields are present"))
    checks.append(_check("bundle-version", manifest.get("version") == EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION, manifest.get("version"), EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_VERSION, "bundle version is closed"))
    checks.append(_check("bundle-state", manifest.get("state") in {item.value for item in EvidenceLifecycleOfflineBundleState}, manifest.get("state"), [item.value for item in EvidenceLifecycleOfflineBundleState], "bundle state is recognized"))
    artifacts = manifest.get("artifacts", [])
    bundle_checks = manifest.get("checks", [])
    checks.append(_check("artifacts-array", isinstance(artifacts, list), type(artifacts).__name__, "list", "artifacts are represented as an array"))
    checks.append(_check("checks-array", isinstance(bundle_checks, list), type(bundle_checks).__name__, "list", "checks are represented as an array"))
    if isinstance(artifacts, list):
        checks.append(_check("artifact-count", manifest.get("artifact_count") == len(artifacts), manifest.get("artifact_count"), len(artifacts), "artifact_count reconciles with artifacts"))
        ids = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
        paths = [item.get("relative_path") for item in artifacts if isinstance(item, dict)]
        kinds = [item.get("kind") for item in artifacts if isinstance(item, dict)]
        checks.append(_check("artifact-identities", len(ids) == len(set(ids)), len(set(ids)), len(ids), "artifact identities are unique"))
        checks.append(_check("artifact-paths", len(paths) == len(set(paths)), len(set(paths)), len(paths), "artifact paths are unique"))
        checks.append(_check("artifact-kinds", all(kind in {item.value for item in EvidenceLifecycleOfflineArtifactKind} for kind in kinds), kinds, [item.value for item in EvidenceLifecycleOfflineArtifactKind], "artifact kinds are recognized"))
        checks.append(_check("artifact-entry-shape", all(isinstance(item, dict) and all(key in item for key in ("artifact_id", "relative_path", "media_type", "kind", "byte_count", "line_count", "content_address")) for item in artifacts), True, True, "artifact entries contain closed metadata"))
    if isinstance(bundle_checks, list):
        passed = sum(bool(item.get("passed")) for item in bundle_checks if isinstance(item, dict))
        checks.append(_check("check-counts", manifest.get("passed_check_count") == passed and manifest.get("failed_check_count") == len(bundle_checks) - passed, {"passed": manifest.get("passed_check_count"), "failed": manifest.get("failed_check_count")}, {"passed": passed, "failed": len(bundle_checks) - passed}, "check counts conserve manifest checks"))
        checks.append(_check("check-entry-shape", all(isinstance(item, dict) and all(key in item for key in ("check_id", "plane", "passed", "observed", "required", "detail", "content_address")) for item in bundle_checks), True, True, "check entries contain closed metadata"))
    checks.append(_check("public-boundary", not _has_forbidden_key(manifest) and not contains_private_key(manifest), True, True, "manifest contains no private or attribution keys"))
    accepted = all(item.passed for item in checks)
    body = {"checks": [item.to_dict() for item in checks], "accepted": accepted}
    return EvidenceLifecycleOfflineSchemaValidation(EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_SCHEMA_VERSION, tuple(checks), accepted, content_hash(body, prefix="evidence-lifecycle-offline-schema-validation"))


__all__ = [
    "EvidenceLifecycleOfflineSchemaCheck",
    "EvidenceLifecycleOfflineSchemaValidation",
    "evidence_lifecycle_offline_bundle_schema",
    "validate_evidence_lifecycle_offline_manifest",
]

"""Closed schema and structural validation for certification bundle manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability_certification_bundle_contracts import (
    CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY,
    CAPABILITY_CERTIFICATION_BUNDLE_VERSION,
    CertificationBundleArtifactKind,
    CertificationBundleCheckPlane,
    CertificationBundleState,
)
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

CAPABILITY_CERTIFICATION_BUNDLE_SCHEMA_VERSION = "capability-certification-bundle-schema-v1"


@dataclass(frozen=True, slots=True)
class CertificationBundleSchemaCheck:
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
class CertificationBundleSchemaValidation:
    schema_version: str
    checks: tuple[CertificationBundleSchemaCheck, ...]
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


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> CertificationBundleSchemaCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return CertificationBundleSchemaCheck(**body, content_address=content_hash(body, prefix="capability-certification-bundle-schema-check"))


def capability_certification_bundle_schema() -> dict[str, Any]:
    """Return the closed JSON Schema projection for ``bundle.json``."""

    artifact_properties = {
        "artifact_id": {"type": "string", "minLength": 1},
        "relative_path": {"type": "string", "minLength": 1},
        "media_type": {"type": "string", "minLength": 1},
        "kind": {"enum": [item.value for item in CertificationBundleArtifactKind]},
        "byte_count": {"type": "integer", "minimum": 0},
        "line_count": {"type": "integer", "minimum": 0},
        "content_address": {"type": "string", "minLength": 1},
    }
    check_properties = {
        "check_id": {"type": "string", "minLength": 1},
        "plane": {"enum": [item.value for item in CertificationBundleCheckPlane]},
        "passed": {"type": "boolean"},
        "observed": {},
        "required": {},
        "detail": {"type": "string"},
        "content_address": {"type": "string", "minLength": 1},
    }
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"glio-noncode/{CAPABILITY_CERTIFICATION_BUNDLE_SCHEMA_VERSION}",
        "title": "GLIO-NONCODE capability certification bundle manifest",
        "type": "object",
        "required": [
            "bundle_id",
            "version",
            "boundary",
            "report_id",
            "run_id",
            "catalog_address",
            "runtime_address",
            "state",
            "accepted",
            "artifacts",
            "checks",
            "certificate_count",
            "domain_count",
            "total_checks",
            "passed_check_count",
            "failed_check_count",
            "warning_count",
            "artifact_count",
            "content_address",
        ],
        "properties": {
            "bundle_id": {"type": "string", "minLength": 1},
            "version": {"const": CAPABILITY_CERTIFICATION_BUNDLE_VERSION},
            "boundary": {"const": CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY},
            "report_id": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "catalog_address": {"type": "string", "minLength": 1},
            "runtime_address": {"type": "string", "minLength": 1},
            "state": {"enum": [item.value for item in CertificationBundleState]},
            "accepted": {"type": "boolean"},
            "artifacts": {"type": "array", "items": {"type": "object", "required": list(artifact_properties), "properties": artifact_properties, "additionalProperties": False}},
            "checks": {"type": "array", "items": {"type": "object", "required": list(check_properties), "properties": check_properties, "additionalProperties": False}},
            "certificate_count": {"type": "integer", "minimum": 0},
            "domain_count": {"type": "integer", "minimum": 0},
            "total_checks": {"type": "integer", "minimum": 0},
            "passed_check_count": {"type": "integer", "minimum": 0},
            "failed_check_count": {"type": "integer", "minimum": 0},
            "warning_count": {"type": "integer", "minimum": 0},
            "artifact_count": {"type": "integer", "minimum": 0},
            "content_address": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    schema["content_address"] = content_hash(schema, prefix="capability-certification-bundle-schema")
    return schema


def validate_capability_certification_bundle_manifest(manifest: Any) -> CertificationBundleSchemaValidation:
    """Validate manifest shape, denominators, state, and public keys."""

    checks: list[CertificationBundleSchemaCheck] = [_check("manifest-object", isinstance(manifest, dict), type(manifest).__name__, "dict", "manifest is an object")]
    if not isinstance(manifest, dict):
        body = {"checks": [item.to_dict() for item in checks], "accepted": False}
        return CertificationBundleSchemaValidation(CAPABILITY_CERTIFICATION_BUNDLE_SCHEMA_VERSION, tuple(checks), False, content_hash(body, prefix="capability-certification-bundle-schema-validation"))
    required = (
        "bundle_id",
        "version",
        "boundary",
        "report_id",
        "run_id",
        "catalog_address",
        "runtime_address",
        "state",
        "accepted",
        "artifacts",
        "checks",
        "certificate_count",
        "domain_count",
        "total_checks",
        "passed_check_count",
        "failed_check_count",
        "warning_count",
        "artifact_count",
        "content_address",
    )
    missing = tuple(item for item in required if item not in manifest)
    checks.append(_check("required-fields", not missing, list(missing), [], "required manifest fields are present"))
    checks.append(_check("bundle-version", manifest.get("version") == CAPABILITY_CERTIFICATION_BUNDLE_VERSION, manifest.get("version"), CAPABILITY_CERTIFICATION_BUNDLE_VERSION, "bundle version is closed"))
    checks.append(_check("bundle-boundary", manifest.get("boundary") == CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY, manifest.get("boundary"), CAPABILITY_CERTIFICATION_BUNDLE_BOUNDARY, "bundle boundary is closed"))
    checks.append(_check("bundle-state", manifest.get("state") in {item.value for item in CertificationBundleState}, manifest.get("state"), [item.value for item in CertificationBundleState], "bundle state is recognized"))
    artifacts = manifest.get("artifacts", [])
    bundle_checks = manifest.get("checks", [])
    checks.append(_check("artifacts-array", isinstance(artifacts, list), type(artifacts).__name__, "list", "artifacts are an array"))
    checks.append(_check("checks-array", isinstance(bundle_checks, list), type(bundle_checks).__name__, "list", "checks are an array"))
    if isinstance(artifacts, list):
        ids = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
        checks.append(_check("artifact-count", manifest.get("artifact_count") == len(artifacts), manifest.get("artifact_count"), len(artifacts), "artifact_count reconciles"))
        checks.append(_check("artifact-identities", len(ids) == len(set(ids)), len(set(ids)), len(ids), "artifact identities are unique"))
    if isinstance(bundle_checks, list):
        bundle_passed = sum(bool(item.get("passed")) for item in bundle_checks if isinstance(item, dict))
        checks.append(_check("bundle-checks-accepted", bundle_passed == len(bundle_checks), bundle_passed, len(bundle_checks), "all manifest closure checks pass"))
        checks.append(_check("check-counts", manifest.get("passed_check_count", -1) + manifest.get("failed_check_count", -1) == manifest.get("total_checks", -2), {"passed": manifest.get("passed_check_count"), "failed": manifest.get("failed_check_count"), "total": manifest.get("total_checks")}, "passed + failed = total certification checks", "certification check counts reconcile"))
    checks.append(_check("catalog-denominator", manifest.get("certificate_count") == 256 and manifest.get("domain_count") == 16 and manifest.get("total_checks") == 2572, {"certificates": manifest.get("certificate_count"), "domains": manifest.get("domain_count"), "checks": manifest.get("total_checks")}, {"certificates": 256, "domains": 16, "checks": 2572}, "complete certification denominators are retained"))
    checks.append(_check("public-boundary", not _has_forbidden_key(manifest) and not contains_private_key(manifest), True, True, "manifest contains no private or attribution keys"))
    accepted = all(item.passed for item in checks)
    body = {"checks": [item.to_dict() for item in checks], "accepted": accepted}
    return CertificationBundleSchemaValidation(CAPABILITY_CERTIFICATION_BUNDLE_SCHEMA_VERSION, tuple(checks), accepted, content_hash(body, prefix="capability-certification-bundle-schema-validation"))


__all__ = [
    "CAPABILITY_CERTIFICATION_BUNDLE_SCHEMA_VERSION",
    "CertificationBundleSchemaCheck",
    "CertificationBundleSchemaValidation",
    "capability_certification_bundle_schema",
    "validate_capability_certification_bundle_manifest",
]

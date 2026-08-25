"""Closed manifest schema and shape validation for D16 handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
    DEPLOYMENT_FRONTIER_OFFLINE_SCHEMA_VERSION,
    DeploymentFrontierOfflineArtifactKind,
    DeploymentFrontierOfflineBundleState,
)
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineSchemaCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineSchemaValidation:
    schema_version: str
    checks: tuple[DeploymentFrontierOfflineSchemaCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "failed_check_ids": list(self.failed_check_ids),
            "passed_count": self.passed_count,
        }


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> DeploymentFrontierOfflineSchemaCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineSchemaCheck(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-schema-check"),
    )


def deployment_frontier_offline_bundle_schema() -> dict[str, Any]:
    """Return the JSON Schema projection for ``bundle.json``."""

    artifact_properties = {
        "artifact_id": {"type": "string", "minLength": 1},
        "relative_path": {"type": "string", "minLength": 1},
        "media_type": {"type": "string", "minLength": 1},
        "kind": {"enum": [item.value for item in DeploymentFrontierOfflineArtifactKind]},
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
        "stage_count",
        "warning_count",
        "artifact_count",
        "passed_check_count",
        "failed_check_count",
        "content_address",
    ]
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"glio-noncode/{DEPLOYMENT_FRONTIER_OFFLINE_SCHEMA_VERSION}",
        "title": "GLIO-NONCODE D16 deployment public offline bundle manifest",
        "type": "object",
        "required": required,
        "properties": {
            "bundle_id": {"type": "string", "minLength": 1},
            "version": {"const": DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION},
            "boundary": {"type": "string", "minLength": 1},
            "fixture_id": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "state": {"enum": [item.value for item in DeploymentFrontierOfflineBundleState]},
            "accepted": {"type": "boolean"},
            "artifacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": artifact_properties,
                    "required": list(artifact_properties),
                    "additionalProperties": False,
                },
            },
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": check_properties,
                    "required": list(check_properties),
                    "additionalProperties": False,
                },
            },
            "runtime_address": {"type": "string", "minLength": 1},
            "stage_count": {"type": "integer", "minimum": 0},
            "warning_count": {"type": "integer", "minimum": 0},
            "artifact_count": {"type": "integer", "minimum": 0},
            "passed_check_count": {"type": "integer", "minimum": 0},
            "failed_check_count": {"type": "integer", "minimum": 0},
            "content_address": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    schema["content_address"] = content_hash(schema, prefix="deployment-frontier-offline-schema")
    return schema


def _validate_artifact(index: int, value: Any) -> tuple[DeploymentFrontierOfflineSchemaCheck, ...]:
    if not isinstance(value, dict):
        return (
            _check(
                f"artifact-{index}-object",
                False,
                type(value).__name__,
                "object",
                "artifact entry is an object",
            ),
        )
    required = (
        "artifact_id",
        "relative_path",
        "media_type",
        "kind",
        "byte_count",
        "line_count",
        "content_address",
    )
    missing = tuple(item for item in required if item not in value)
    checks = [
        _check(f"artifact-{index}-fields", not missing, missing, (), "artifact fields are complete")
    ]
    checks.append(
        _check(
            f"artifact-{index}-kind",
            value.get("kind") in {item.value for item in DeploymentFrontierOfflineArtifactKind},
            value.get("kind"),
            [item.value for item in DeploymentFrontierOfflineArtifactKind],
            "artifact kind is recognized",
        )
    )
    checks.append(
        _check(
            f"artifact-{index}-counts",
            isinstance(value.get("byte_count"), int)
            and value.get("byte_count", -1) >= 0
            and isinstance(value.get("line_count"), int)
            and value.get("line_count", -1) >= 0,
            {"byte_count": value.get("byte_count"), "line_count": value.get("line_count")},
            ">=0 integers",
            "artifact byte and line counts are non-negative",
        )
    )
    return tuple(checks)


def _validate_check(index: int, value: Any) -> tuple[DeploymentFrontierOfflineSchemaCheck, ...]:
    if not isinstance(value, dict):
        return (
            _check(
                f"check-{index}-object",
                False,
                type(value).__name__,
                "object",
                "check entry is an object",
            ),
        )
    required = ("check_id", "plane", "passed", "observed", "required", "detail", "content_address")
    missing = tuple(item for item in required if item not in value)
    checks = [
        _check(f"check-{index}-fields", not missing, missing, (), "check fields are complete")
    ]
    checks.append(
        _check(
            f"check-{index}-boolean",
            isinstance(value.get("passed"), bool),
            type(value.get("passed")).__name__,
            "bool",
            "check state is boolean",
        )
    )
    checks.append(
        _check(
            f"check-{index}-text",
            bool(str(value.get("check_id", ""))) and bool(str(value.get("detail", ""))),
            True,
            True,
            "check identity and detail are present",
        )
    )
    return tuple(checks)


def validate_deployment_frontier_offline_manifest(
    manifest: Any,
) -> DeploymentFrontierOfflineSchemaValidation:
    """Validate the root shape and closed field inventory without file I/O."""

    checks: list[DeploymentFrontierOfflineSchemaCheck] = [
        _check(
            "manifest-object",
            isinstance(manifest, dict),
            type(manifest).__name__,
            "dict",
            "manifest root is an object",
        )
    ]
    if not isinstance(manifest, dict):
        return DeploymentFrontierOfflineSchemaValidation(
            DEPLOYMENT_FRONTIER_OFFLINE_SCHEMA_VERSION,
            tuple(checks),
            False,
            content_hash(checks, prefix="deployment-frontier-offline-schema-validation"),
        )
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
        "stage_count",
        "warning_count",
        "artifact_count",
        "passed_check_count",
        "failed_check_count",
        "content_address",
    )
    missing = tuple(item for item in required if item not in manifest)
    checks.extend(
        (
            _check(
                "required-fields",
                not missing,
                missing,
                (),
                "all required manifest fields are present",
            ),
            _check(
                "bundle-version",
                manifest.get("version") == DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
                manifest.get("version"),
                DEPLOYMENT_FRONTIER_OFFLINE_BUNDLE_VERSION,
                "bundle version is closed",
            ),
            _check(
                "bundle-state",
                manifest.get("state")
                in {item.value for item in DeploymentFrontierOfflineBundleState},
                manifest.get("state"),
                [item.value for item in DeploymentFrontierOfflineBundleState],
                "bundle state is recognized",
            ),
            _check(
                "accepted-boolean",
                isinstance(manifest.get("accepted"), bool),
                type(manifest.get("accepted")).__name__,
                "bool",
                "root acceptance is boolean",
            ),
            _check(
                "artifacts-array",
                isinstance(manifest.get("artifacts"), list),
                type(manifest.get("artifacts")).__name__,
                "list",
                "artifacts are represented as an array",
            ),
            _check(
                "checks-array",
                isinstance(manifest.get("checks"), list),
                type(manifest.get("checks")).__name__,
                "list",
                "checks are represented as an array",
            ),
            _check(
                "artifact-count",
                isinstance(manifest.get("artifacts"), list)
                and manifest.get("artifact_count") == len(manifest.get("artifacts", ())),
                manifest.get("artifact_count"),
                len(manifest.get("artifacts", ()))
                if isinstance(manifest.get("artifacts"), list)
                else None,
                "artifact count reconciles with array",
            ),
            _check(
                "artifact-denominator",
                manifest.get("artifact_count") == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
                manifest.get("artifact_count"),
                DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
                "D16 artifact denominator is closed",
            ),
            _check(
                "check-counts",
                isinstance(manifest.get("passed_check_count"), int)
                and isinstance(manifest.get("failed_check_count"), int)
                and manifest.get("passed_check_count", -1) + manifest.get("failed_check_count", -1)
                == len(manifest.get("checks", ())),
                {
                    "passed": manifest.get("passed_check_count"),
                    "failed": manifest.get("failed_check_count"),
                },
                "passed+failed equals checks",
                "check counters reconcile",
            ),
            _check(
                "public-manifest",
                not _has_forbidden_key(manifest) and not contains_private_key(manifest),
                True,
                True,
                "manifest contains no prohibited public-surface key",
            ),
        )
    )
    artifacts = manifest.get("artifacts", [])
    if isinstance(artifacts, list):
        for index, value in enumerate(artifacts):
            checks.extend(_validate_artifact(index, value))
        ids = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
        paths = [item.get("relative_path") for item in artifacts if isinstance(item, dict)]
        checks.extend(
            (
                _check(
                    "artifact-identities-unique",
                    len(ids) == len(set(ids)),
                    len(ids),
                    len(set(ids)),
                    "artifact identifiers are unique",
                ),
                _check(
                    "artifact-paths-unique",
                    len(paths) == len(set(paths)),
                    len(paths),
                    len(set(paths)),
                    "artifact paths are unique",
                ),
            )
        )
    raw_checks = manifest.get("checks", [])
    if isinstance(raw_checks, list):
        for index, value in enumerate(raw_checks):
            checks.extend(_validate_check(index, value))
    accepted = all(item.passed for item in checks)
    body = {
        "schema_version": DEPLOYMENT_FRONTIER_OFFLINE_SCHEMA_VERSION,
        "checks": checks,
        "accepted": accepted,
    }
    return DeploymentFrontierOfflineSchemaValidation(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-schema-validation"),
    )


__all__ = [
    "DeploymentFrontierOfflineSchemaCheck",
    "DeploymentFrontierOfflineSchemaValidation",
    "deployment_frontier_offline_bundle_schema",
    "validate_deployment_frontier_offline_manifest",
]

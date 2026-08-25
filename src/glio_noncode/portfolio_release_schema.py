"""Machine-readable schema and validation helpers for portfolio manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .portfolio_release_contracts import (
    PORTFOLIO_RELEASE_VERSION,
    PortfolioArtifactKind,
    PortfolioReleaseState,
)
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

PORTFOLIO_RELEASE_SCHEMA_VERSION = "portfolio-release-schema-v1"


@dataclass(frozen=True, slots=True)
class PortfolioSchemaCheck:
    """One structural or boundary validation result."""

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
class PortfolioSchemaValidation:
    """Aggregate validation result for one in-memory manifest."""

    schema_version: str
    checks: tuple[PortfolioSchemaCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return stable structural failure identifiers."""

        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "content_address": self.content_address,
        }


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> PortfolioSchemaCheck:
    """Create an addressed schema observation."""

    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return PortfolioSchemaCheck(
        **body,
        content_address=content_hash(body, prefix="portfolio-release-schema-check"),
    )


def portfolio_release_schema() -> dict[str, Any]:
    """Return the closed public JSON schema projection."""

    artifact_properties = {
        "artifact_id": {"type": "string", "minLength": 1},
        "relative_path": {"type": "string", "minLength": 1},
        "media_type": {"type": "string", "minLength": 1},
        "kind": {"enum": [item.value for item in PortfolioArtifactKind]},
        "member_run_id": {"type": ["string", "null"]},
        "byte_count": {"type": "integer", "minimum": 0},
        "line_count": {"type": "integer", "minimum": 0},
        "content_address": {"type": "string", "minLength": 1},
    }
    member_properties = {
        "run_id": {"type": "string", "minLength": 1},
        "case_id": {"type": "string"},
        "dossier_address": {"type": ["string", "null"]},
        "workspace_history_address": {"type": ["string", "null"]},
        "dossier_release_id": {"type": ["string", "null"]},
        "workspace_release_id": {"type": ["string", "null"]},
        "dossier_state": {"type": "string"},
        "workspace_state": {"type": "string"},
        "state": {"enum": [item.value for item in PortfolioReleaseState]},
        "accepted": {"type": "boolean"},
        "ready": {"type": "boolean"},
        "artifact_count": {"type": "integer", "minimum": 0},
        "artifact_ids": {"type": "array", "items": {"type": "string"}},
        "failed_check_ids": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "content_address": {"type": "string", "minLength": 1},
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"glio-noncode/{PORTFOLIO_RELEASE_SCHEMA_VERSION}",
        "title": "GLIO-NONCODE portfolio release manifest",
        "type": "object",
        "required": [
            "release_version",
            "release_id",
            "as_of",
            "selection",
            "state",
            "accepted",
            "member_count",
            "artifact_count",
            "members",
            "artifacts",
            "checks",
            "content_address",
        ],
        "properties": {
            "release_version": {"const": PORTFOLIO_RELEASE_VERSION},
            "release_id": {"type": "string", "minLength": 1},
            "as_of": {"type": "string"},
            "selection": {"type": "object"},
            "state": {"enum": [item.value for item in PortfolioReleaseState]},
            "accepted": {"type": "boolean"},
            "member_count": {"type": "integer", "minimum": 0},
            "ready_member_count": {"type": "integer", "minimum": 0},
            "blocked_member_count": {"type": "integer", "minimum": 0},
            "artifact_count": {"type": "integer", "minimum": 0},
            "warning_count": {"type": "integer", "minimum": 0},
            "failed_check_ids": {"type": "array", "items": {"type": "string"}},
            "members": {"type": "array", "items": {"type": "object", "properties": member_properties}},
            "artifacts": {"type": "array", "items": {"type": "object", "properties": artifact_properties}},
            "checks": {"type": "array", "items": {"type": "object"}},
            "content_address": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    schema["content_address"] = content_hash(schema, prefix="portfolio-release-schema")
    return schema


def validate_portfolio_release_manifest(
    manifest: Any,
) -> PortfolioSchemaValidation:
    """Validate structural cardinalities and public keys without file I/O."""

    is_object = isinstance(manifest, dict)
    checks: list[PortfolioSchemaCheck] = [
        _check("manifest-object", is_object, type(manifest).__name__, "dict", "manifest must be a JSON object"),
    ]
    if not is_object:
        body = {"checks": [item.to_dict() for item in checks], "accepted": False}
        return PortfolioSchemaValidation(PORTFOLIO_RELEASE_SCHEMA_VERSION, tuple(checks), False, content_hash(body, prefix="portfolio-release-schema-validation"))
    required = (
        "release_version",
        "release_id",
        "as_of",
        "selection",
        "state",
        "accepted",
        "members",
        "artifacts",
        "checks",
        "content_address",
    )
    missing = tuple(item for item in required if item not in manifest)
    checks.append(_check("required-fields", not missing, list(missing), [], "all required manifest fields are present"))
    checks.append(_check("release-version", manifest.get("release_version") == PORTFOLIO_RELEASE_VERSION, manifest.get("release_version"), PORTFOLIO_RELEASE_VERSION, "manifest version is closed"))
    checks.append(_check("release-state", manifest.get("state") in {item.value for item in PortfolioReleaseState}, manifest.get("state"), [item.value for item in PortfolioReleaseState], "manifest state is recognized"))
    members = manifest.get("members", [])
    artifacts = manifest.get("artifacts", [])
    checks.append(_check("members-array", isinstance(members, list), type(members).__name__, "list", "members are represented as an array"))
    checks.append(_check("artifacts-array", isinstance(artifacts, list), type(artifacts).__name__, "list", "artifacts are represented as an array"))
    if isinstance(members, list):
        checks.append(_check("member-count", manifest.get("member_count") == len(members), manifest.get("member_count"), len(members), "member_count reconciles with members"))
    if isinstance(artifacts, list):
        checks.append(_check("artifact-count", manifest.get("artifact_count") == len(artifacts), manifest.get("artifact_count"), len(artifacts), "artifact_count reconciles with artifacts"))
    checks.append(_check("public-boundary", not _has_forbidden_key(manifest) and not contains_private_key(manifest), True, True, "manifest contains no private or attribution keys"))
    accepted = all(item.passed for item in checks)
    body = {"checks": [item.to_dict() for item in checks], "accepted": accepted}
    return PortfolioSchemaValidation(PORTFOLIO_RELEASE_SCHEMA_VERSION, tuple(checks), accepted, content_hash(body, prefix="portfolio-release-schema-validation"))


__all__ = [
    "PORTFOLIO_RELEASE_SCHEMA_VERSION",
    "PortfolioSchemaCheck",
    "PortfolioSchemaValidation",
    "portfolio_release_schema",
    "validate_portfolio_release_manifest",
]

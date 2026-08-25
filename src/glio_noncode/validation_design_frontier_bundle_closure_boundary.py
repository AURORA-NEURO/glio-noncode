"""Independent public-boundary checks for the D13 closure handoff."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .validation_design_frontier_bundle_closure_contracts import (
    VALIDATION_DESIGN_CLOSURE_BOUNDARY,
    ValidationDesignClosureBoundaryReport,
)
from .validation_design_frontier_bundle_closure_support import (
    discover_keys,
    forbidden_keys,
    safe_relative_path,
)
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle

_FORBIDDEN_PUBLIC_NAMES = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "email",
        "generated_by",
        "language",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "primary_agent",
        "primary_agent_id",
        "primary_agent_name",
        "programming_language",
        "produced_by",
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "medical_record_no",
        "phone",
        "phone_number",
        "email_address",
    }
)


def _json_artifact_check(artifact: Any) -> dict[str, Any]:
    payload = artifact.payload
    parsed: Any = None
    parse_ok = artifact.media_type != "application/json"
    if artifact.media_type == "application/json" and payload is not None:
        try:
            parsed = json.loads(payload)
            parse_ok = True
        except json.JSONDecodeError:
            parse_ok = False
    keys = discover_keys(parsed) if parse_ok and parsed is not None else ()
    direct = forbidden_keys(parsed) if parse_ok and parsed is not None else ()
    normalized_keys = tuple(sorted(path.rsplit(".", 1)[-1].casefold() for path in keys))
    forbidden_names = tuple(
        sorted(set(direct) | {name for name in normalized_keys if name in _FORBIDDEN_PUBLIC_NAMES})
    )
    return {
        "artifact_id": artifact.artifact_id,
        "relative_path": artifact.relative_path,
        "media_type": artifact.media_type,
        "parse_ok": parse_ok,
        "payload_present": payload is not None,
        "discovered_key_count": len(keys),
        "forbidden_keys": forbidden_names,
        "accepted": parse_ok and payload is not None and not forbidden_names,
    }


def _path_checks(bundle: ValidationDesignBundle) -> dict[str, bool]:
    paths = tuple(item.relative_path for item in bundle.artifacts)
    return {
        "all_safe_relative": all(safe_relative_path(path) for path in paths),
        "all_unique": len(paths) == len(set(paths)),
        "manifest_not_shadowed": "bundle.json" not in paths,
        "json_suffixes_match": all(
            item.media_type != "application/json" or item.relative_path.endswith(".json")
            for item in bundle.artifacts
        ),
        "csv_suffixes_match": all(
            item.media_type != "text/csv" or item.relative_path.endswith(".csv")
            for item in bundle.artifacts
        ),
    }


def validate_validation_design_closure_boundary(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureBoundaryReport:
    """Validate exact paths and public aggregate payloads without producer imports."""

    if any(item.payload is None for item in bundle.artifacts):
        raise ValidationError("D13 closure boundary requires hydrated artifact payloads")
    artifact_checks = tuple(_json_artifact_check(item) for item in bundle.artifacts)
    paths = _path_checks(bundle)
    all_forbidden = tuple(
        sorted({key for check in artifact_checks for key in check["forbidden_keys"]})
    )
    discovered = tuple(
        sorted(
            {
                key
                for check in artifact_checks
                for key in discover_keys(_safe_json(bundle, check["artifact_id"]))
            }
        )
    )
    accepted = bool(
        bundle.accepted
        and not all_forbidden
        and all(paths.values())
        and all(check["accepted"] for check in artifact_checks)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "boundary": VALIDATION_DESIGN_CLOSURE_BOUNDARY,
        "forbidden_keys": all_forbidden,
        "discovered_keys": discovered,
        "path_checks": paths,
        "artifact_checks": artifact_checks,
        "accepted": accepted,
    }
    return ValidationDesignClosureBoundaryReport(
        bundle_id=bundle.bundle_id,
        forbidden_keys=all_forbidden,
        discovered_keys=discovered,
        path_checks=paths,
        artifact_checks=artifact_checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-boundary"),
    )


def _safe_json(bundle: ValidationDesignBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None or artifact.media_type != "application/json":
        return None
    try:
        value = json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None
    return value


def public_projection(value: Any) -> Any:
    """Return a recursively filtered aggregate projection for callers that need it."""

    if isinstance(value, Mapping):
        return {
            str(key): public_projection(item)
            for key, item in value.items()
            if str(key).casefold() not in _FORBIDDEN_PUBLIC_NAMES
        }
    if isinstance(value, (list, tuple)):
        return [public_projection(item) for item in value]
    return jsonable(value)


def closure_public_boundary_inventory(bundle: ValidationDesignBundle) -> dict[str, Any]:
    report = validate_validation_design_closure_boundary(bundle)
    return {
        "boundary": VALIDATION_DESIGN_CLOSURE_BOUNDARY,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(bundle.artifacts),
        "forbidden_key_count": len(report.forbidden_keys),
        "discovered_key_count": len(report.discovered_keys),
        "path_checks": report.path_checks,
        "accepted": report.accepted,
        "content_address": report.content_address,
    }


__all__ = [
    "closure_public_boundary_inventory",
    "public_projection",
    "validate_validation_design_closure_boundary",
]

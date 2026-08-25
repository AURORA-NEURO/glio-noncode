"""Offline loading, querying, and diffing for D13 bundles."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, require_non_empty
from .validation_design_frontier_bundle_contracts import (
    VALIDATION_DESIGN_BUNDLE_DEFAULT_LIMIT,
    VALIDATION_DESIGN_BUNDLE_MANIFEST,
    VALIDATION_DESIGN_BUNDLE_MAX_LIMIT,
    ValidationDesignBundle,
    ValidationDesignBundleArtifact,
    ValidationDesignBundleArtifactKind,
    ValidationDesignBundleCheck,
    ValidationDesignBundleCheckPlane,
    ValidationDesignBundleDiff,
    ValidationDesignBundleQueryResult,
    ValidationDesignBundleState,
    ValidationDesignBundleVerification,
)
from .validation_design_frontier_offline_bundle import verify_validation_design_offline_bundle


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and bool(path.parts) and all(part not in {"", ".", ".."} for part in path.parts)


def _load_mapping(value: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(value)
    try:
        manifest = json.loads((root / VALIDATION_DESIGN_BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load validation-design bundle manifest: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise ValidationError("validation-design bundle manifest must be an object")
    return root, manifest


def _check_from_dict(value: Mapping[str, Any]) -> ValidationDesignBundleCheck:
    return ValidationDesignBundleCheck(
        check_id=str(value.get("check_id", "unknown")),
        plane=ValidationDesignBundleCheckPlane(str(value.get("plane", ValidationDesignBundleCheckPlane.MANIFEST.value))),
        passed=bool(value.get("passed", False)),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "validation-design-bundle-check:missing")),
    )


def load_validation_design_offline_bundle(destination: str | Path, *, include_payloads: bool = False) -> ValidationDesignBundle:
    """Load a manifest and optionally hydrate each exact artifact payload."""

    root, manifest = _load_mapping(destination)
    artifacts_value = manifest.get("artifacts", ())
    checks_value = manifest.get("checks", ())
    if not isinstance(artifacts_value, list) or not isinstance(checks_value, list):
        raise ValidationError("validation-design bundle collections must be arrays")
    artifacts: list[ValidationDesignBundleArtifact] = []
    for raw in artifacts_value:
        if not isinstance(raw, Mapping):
            raise ValidationError("validation-design bundle artifact entries must be objects")
        relative_path = str(raw.get("relative_path", ""))
        if not _safe_relative_path(relative_path):
            raise ValidationError(f"unsafe validation-design artifact path: {relative_path!r}")
        payload: str | None = None
        if include_payloads:
            try:
                payload = (root / Path(*relative_path.split("/"))).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValidationError(f"cannot hydrate artifact {relative_path}: {exc}") from exc
        artifacts.append(
            ValidationDesignBundleArtifact(
                artifact_id=str(raw.get("artifact_id", "")),
                relative_path=relative_path,
                media_type=str(raw.get("media_type", "")),
                kind=ValidationDesignBundleArtifactKind(str(raw.get("kind", ValidationDesignBundleArtifactKind.REPORT.value))),
                byte_count=int(raw.get("byte_count", 0)),
                line_count=int(raw.get("line_count", 0)),
                content_address=str(raw.get("content_address", "")),
                payload=payload,
            )
        )
    checks = tuple(_check_from_dict(item) for item in checks_value if isinstance(item, Mapping))
    return ValidationDesignBundle(
        bundle_id=str(manifest.get("bundle_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        fixture_id=str(manifest.get("fixture_id", "")),
        run_id=str(manifest.get("run_id", "")),
        state=ValidationDesignBundleState(str(manifest.get("state", ValidationDesignBundleState.BLOCKED.value))),
        accepted=bool(manifest.get("accepted", False)),
        artifacts=tuple(artifacts),
        checks=checks,
        runtime_address=str(manifest.get("runtime_address", "")),
        warning_count=int(manifest.get("warning_count", 0)),
        content_address=str(manifest.get("content_address", "")),
    )


def _as_bundle(value: ValidationDesignBundle | str | Path, *, include_payloads: bool = False) -> ValidationDesignBundle:
    if isinstance(value, ValidationDesignBundle):
        return value
    return load_validation_design_offline_bundle(value, include_payloads=include_payloads)


def _json_payload(bundle: ValidationDesignBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _matches(item: Mapping[str, Any], text: str | None) -> bool:
    return not text or text.casefold() in canonical_json(item).casefold()


def _record_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    fixture = _json_payload(bundle, "fixture")
    evaluation = _json_payload(bundle, "evaluation")
    if not isinstance(fixture, Mapping) or not isinstance(evaluation, Mapping):
        return ()
    records = fixture.get("records", ())
    executions = evaluation.get("executions", ())
    if not isinstance(records, list) or not isinstance(executions, list):
        return ()
    execution_by_id = {str(item.get("record_id")): item for item in executions if isinstance(item, Mapping) and item.get("record_id") is not None}
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_id = str(record.get("record_id", ""))
        execution = execution_by_id.get(record_id, {})
        rows.append(
            {
                "resource": "record",
                "record_id": record_id,
                "capability": record.get("capability"),
                "operation": record.get("operation"),
                "role": record.get("role"),
                "expected_state": record.get("expected_state"),
                "observed_state": execution.get("observed_state"),
                "issue_codes": execution.get("issue_codes", ()),
                "content_address": execution.get("content_address", record.get("content_address")),
            }
        )
    return tuple(sorted(rows, key=lambda item: (str(item.get("operation")), str(item.get("record_id")))))


def _check_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    evaluation = _json_payload(bundle, "evaluation")
    if not isinstance(evaluation, Mapping) or not isinstance(evaluation.get("checks"), list):
        return ()
    return tuple(
        {
            "resource": "check",
            "check_id": item.get("check_id"),
            "record_id": item.get("record_id"),
            "plane": item.get("plane"),
            "passed": item.get("passed"),
            "detail": item.get("detail"),
            "content_address": item.get("content_address"),
        }
        for item in evaluation["checks"]
        if isinstance(item, Mapping)
    )


def _source_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    fixture = _json_payload(bundle, "fixture")
    if not isinstance(fixture, Mapping) or not isinstance(fixture.get("sources"), list):
        return ()
    return tuple({"resource": "source", **item} for item in fixture["sources"] if isinstance(item, Mapping))


def query_validation_design_offline_bundle(
    bundle: ValidationDesignBundle | str | Path,
    *,
    resource: str = "artifacts",
    operation: str | None = None,
    capability: str | None = None,
    role: str | None = None,
    state: str | None = None,
    artifact_kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = VALIDATION_DESIGN_BUNDLE_DEFAULT_LIMIT,
    include_payloads: bool = False,
) -> ValidationDesignBundleQueryResult:
    """Query artifacts, public scenario records, evaluation checks, or sources."""

    if offset < 0:
        raise ValidationError("validation-design bundle query offset cannot be negative")
    if limit < 1 or limit > VALIDATION_DESIGN_BUNDLE_MAX_LIMIT:
        raise ValidationError(f"validation-design bundle query limit must be between 1 and {VALIDATION_DESIGN_BUNDLE_MAX_LIMIT}")
    normalized_resource = require_non_empty(resource, "resource").casefold()
    value = _as_bundle(bundle, include_payloads=include_payloads or normalized_resource in {"records", "checks", "sources"})
    if normalized_resource == "artifacts":
        items: list[Mapping[str, Any]] = [item.to_dict(include_payload=include_payloads) for item in value.artifacts]
        if artifact_kind is not None:
            items = [item for item in items if item.get("kind") == artifact_kind]
    elif normalized_resource == "records":
        items = list(_record_rows(value))
        if operation is not None:
            items = [item for item in items if item.get("operation") == operation]
        if capability is not None:
            items = [item for item in items if item.get("capability") == capability]
        if role is not None:
            items = [item for item in items if item.get("role") == role]
        if state is not None:
            items = [item for item in items if item.get("observed_state") == state or item.get("expected_state") == state]
    elif normalized_resource == "checks":
        items = list(_check_rows(value))
        if state is not None:
            items = [item for item in items if item.get("passed") is (state.casefold() == "passed")]
    elif normalized_resource == "sources":
        items = list(_source_rows(value))
    else:
        raise ValidationError("validation-design bundle resource must be artifacts, records, checks, or sources")
    items = [item for item in items if _matches(item, text)]
    selected = tuple(items[offset : offset + limit])
    query = {
        "resource": normalized_resource,
        "operation": operation,
        "capability": capability,
        "role": role,
        "state": state,
        "artifact_kind": artifact_kind,
        "text": text,
    }
    body = {"bundle_id": value.bundle_id, "query": query, "total": len(items), "offset": offset, "limit": limit, "items": selected, "accepted": value.accepted}
    return ValidationDesignBundleQueryResult(**body, content_address=content_hash(body, prefix="validation-design-bundle-query"))


def export_validation_design_bundle_query_csv(result: ValidationDesignBundleQueryResult) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    keys = tuple(sorted({str(key) for item in result.items for key in item})) if result.items else ("resource", "content_address")
    writer.writerow(keys)
    for item in result.items:
        writer.writerow([";".join(str(part) for part in item.get(key, ())) if isinstance(item.get(key), (list, tuple)) else item.get(key, "") for key in keys])
    return output.getvalue()


def diff_validation_design_offline_bundles(left: ValidationDesignBundle | str | Path, right: ValidationDesignBundle | str | Path) -> ValidationDesignBundleDiff:
    """Compare exact artifact identities across two D13 handoffs."""

    left_value = _as_bundle(left)
    right_value = _as_bundle(right)
    left_map = {item.artifact_id: item for item in left_value.artifacts}
    right_map = {item.artifact_id: item for item in right_value.artifacts}
    left_ids = set(left_map)
    right_ids = set(right_map)
    added = tuple(sorted(right_ids - left_ids))
    removed = tuple(sorted(left_ids - right_ids))
    common = left_ids & right_ids
    changed = tuple(sorted(item for item in common if left_map[item].content_address != right_map[item].content_address))
    unchanged = tuple(sorted(common - set(changed)))
    if isinstance(left, ValidationDesignBundle):
        left_verified = left.ready
    else:
        left_verified = verify_validation_design_offline_bundle(left).accepted
    if isinstance(right, ValidationDesignBundle):
        right_verified = right.ready
    else:
        right_verified = verify_validation_design_offline_bundle(right).accepted
    body = {
        "left_bundle_id": left_value.bundle_id,
        "right_bundle_id": right_value.bundle_id,
        "added_artifact_ids": added,
        "removed_artifact_ids": removed,
        "changed_artifact_ids": changed,
        "unchanged_artifact_ids": unchanged,
        "left_accepted": left_value.accepted,
        "right_accepted": right_value.accepted,
        "accepted": left_verified and right_verified,
    }
    return ValidationDesignBundleDiff(**body, content_address=content_hash(body, prefix="validation-design-bundle-diff"))


def verify_and_load_validation_design_offline_bundle(destination: str | Path, *, include_payloads: bool = False) -> tuple[ValidationDesignBundle, ValidationDesignBundleVerification]:
    verification = verify_validation_design_offline_bundle(destination)
    return load_validation_design_offline_bundle(destination, include_payloads=include_payloads), verification


__all__ = [
    "diff_validation_design_offline_bundles",
    "export_validation_design_bundle_query_csv",
    "load_validation_design_offline_bundle",
    "query_validation_design_offline_bundle",
    "verify_and_load_validation_design_offline_bundle",
]

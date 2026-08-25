"""Offline query, loading, and structural diff operations for fabric bundles."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_fabric_bundle import (
    module_fabric_bundle_filesystem_integrity_ok,
    verify_module_fabric_bundle,
)
from .module_fabric_bundle_contracts import (
    MODULE_FABRIC_BUNDLE_DEFAULT_LIMIT,
    MODULE_FABRIC_BUNDLE_MANIFEST,
    MODULE_FABRIC_BUNDLE_MAX_LIMIT,
    FabricBundle,
    FabricBundleArtifact,
    FabricBundleArtifactKind,
    FabricBundleCheck,
    FabricBundleCheckPlane,
    FabricBundleDiff,
    FabricBundleQueryResult,
    FabricBundleState,
)
from .serialization import canonical_json, content_hash, require_non_empty


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and bool(path.parts) and all(part not in {"", ".", ".."} for part in path.parts)


def _load_mapping(value: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(value)
    manifest_path = root / MODULE_FABRIC_BUNDLE_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load module-fabric bundle manifest: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise ValidationError("module-fabric bundle manifest must be an object")
    return root, manifest


def _check_from_dict(value: Mapping[str, Any]) -> FabricBundleCheck:
    return FabricBundleCheck(
        check_id=str(value.get("check_id", "unknown")),
        plane=FabricBundleCheckPlane(str(value.get("plane", FabricBundleCheckPlane.MANIFEST.value))),
        passed=bool(value.get("passed", False)),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "module-fabric-bundle-check:missing")),
    )


def load_module_fabric_bundle(
    destination: str | Path,
    *,
    include_payloads: bool = False,
    verify: bool = True,
) -> FabricBundle:
    """Load a bundle and optionally hydrate exact artifact bytes.

    Filesystem-backed loads verify the complete tree before exposing the
    manifest.  The independent verifier uses ``verify=False`` only after it
    has already completed its own path and byte checks.
    """

    if verify:
        verification = verify_module_fabric_bundle(destination)
        if not module_fabric_bundle_filesystem_integrity_ok(verification):
            raise ValidationError("module-fabric bundle filesystem integrity verification failed")

    root, manifest = _load_mapping(destination)
    artifacts_value = manifest.get("artifacts", ())
    checks_value = manifest.get("checks", ())
    if not isinstance(artifacts_value, list) or not isinstance(checks_value, list):
        raise ValidationError("module-fabric bundle manifest collections must be arrays")
    artifacts: list[FabricBundleArtifact] = []
    for raw in artifacts_value:
        if not isinstance(raw, Mapping):
            raise ValidationError("module-fabric bundle artifact entries must be objects")
        relative_path = str(raw.get("relative_path", ""))
        if not _safe_relative_path(relative_path):
            raise ValidationError(f"unsafe module-fabric bundle artifact path: {relative_path!r}")
        payload: str | None = None
        if include_payloads:
            try:
                payload = (root / Path(*relative_path.split("/"))).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValidationError(f"cannot hydrate artifact {relative_path}: {exc}") from exc
        artifacts.append(
            FabricBundleArtifact(
                artifact_id=str(raw.get("artifact_id", "")),
                relative_path=relative_path,
                media_type=str(raw.get("media_type", "")),
                kind=FabricBundleArtifactKind(str(raw.get("kind", FabricBundleArtifactKind.REPORT.value))),
                byte_count=int(raw.get("byte_count", 0)),
                line_count=int(raw.get("line_count", 0)),
                content_address=str(raw.get("content_address", "")),
                payload=payload,
            )
        )
    checks = tuple(_check_from_dict(item) for item in checks_value if isinstance(item, Mapping))
    return FabricBundle(
        bundle_id=str(manifest.get("bundle_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        fixture_id=str(manifest.get("fixture_id", "")),
        run_id=str(manifest.get("run_id", "")),
        state=FabricBundleState(str(manifest.get("state", FabricBundleState.BLOCKED.value))),
        accepted=bool(manifest.get("accepted", False)),
        artifacts=tuple(artifacts),
        checks=checks,
        runtime_address=str(manifest.get("runtime_address", "")),
        warning_count=int(manifest.get("warning_count", 0)),
        content_address=str(manifest.get("content_address", "")),
    )


def _as_bundle(value: FabricBundle | str | Path, *, include_payloads: bool = False) -> FabricBundle:
    if isinstance(value, FabricBundle):
        return value
    return load_module_fabric_bundle(value, include_payloads=include_payloads)


def _artifact_row(artifact: FabricBundleArtifact, *, include_payload: bool) -> dict[str, Any]:
    return artifact.to_dict(include_payload=include_payload)


def _json_payload(bundle: FabricBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _record_rows(bundle: FabricBundle) -> tuple[dict[str, Any], ...]:
    fixture = _json_payload(bundle, "fixture")
    evaluation = _json_payload(bundle, "evaluation")
    if not isinstance(fixture, Mapping) or not isinstance(evaluation, Mapping):
        return ()
    records = fixture.get("records", ())
    executions = evaluation.get("executions", ())
    if not isinstance(records, list) or not isinstance(executions, list):
        return ()
    execution_by_id = {
        str(item.get("record_id")): item
        for item in executions
        if isinstance(item, Mapping) and item.get("record_id") is not None
    }
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_id = str(record.get("record_id", ""))
        execution = execution_by_id.get(record_id, {})
        impl = execution.get("implementation_receipts", ())
        tests = execution.get("test_receipts", ())
        rows.append(
            {
                "resource": "record",
                "record_id": record_id,
                "domain_id": record.get("domain_id"),
                "capability_id": record.get("capability_id"),
                "role": record.get("role"),
                "expected_state": record.get("expected_state"),
                "observed_state": execution.get("observed_state"),
                "issue_codes": execution.get("issue_codes", ()),
                "implementation_reference_count": len(impl) if isinstance(impl, list) else 0,
                "test_reference_count": len(tests) if isinstance(tests, list) else 0,
                "content_address": execution.get("content_address", record.get("content_address")),
            }
        )
    return tuple(sorted(rows, key=lambda item: (str(item.get("domain_id")), str(item.get("capability_id")), str(item.get("record_id")))))


def _matches(item: Mapping[str, Any], text: str | None) -> bool:
    if not text:
        return True
    needle = text.casefold()
    return needle in canonical_json(item).casefold()


def query_module_fabric_bundle(
    bundle: FabricBundle | str | Path,
    *,
    resource: str = "artifacts",
    domain_id: str | None = None,
    capability_id: str | None = None,
    role: str | None = None,
    state: str | None = None,
    artifact_kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_FABRIC_BUNDLE_DEFAULT_LIMIT,
    include_payloads: bool = False,
) -> FabricBundleQueryResult:
    """Query the artifact index or the public record projection."""

    if offset < 0:
        raise ValidationError("bundle query offset cannot be negative")
    if limit < 1 or limit > MODULE_FABRIC_BUNDLE_MAX_LIMIT:
        raise ValidationError(f"bundle query limit must be between 1 and {MODULE_FABRIC_BUNDLE_MAX_LIMIT}")
    value = _as_bundle(bundle, include_payloads=include_payloads or resource == "records")
    normalized_resource = require_non_empty(resource, "resource").casefold()
    if normalized_resource == "records":
        items: list[Mapping[str, Any]] = list(_record_rows(value))
        if domain_id is not None:
            items = [item for item in items if item.get("domain_id") == domain_id]
        if capability_id is not None:
            items = [item for item in items if item.get("capability_id") == capability_id]
        if role is not None:
            items = [item for item in items if item.get("role") == role]
        if state is not None:
            items = [item for item in items if item.get("observed_state") == state or item.get("expected_state") == state]
        items = [item for item in items if _matches(item, text)]
    elif normalized_resource == "artifacts":
        items = [_artifact_row(item, include_payload=include_payloads) for item in value.artifacts]
        if artifact_kind is not None:
            items = [item for item in items if item.get("kind") == artifact_kind]
        items = [item for item in items if _matches(item, text)]
    else:
        raise ValidationError("bundle query resource must be artifacts or records")
    selected = tuple(items[offset : offset + limit])
    query = {
        "resource": normalized_resource,
        "domain_id": domain_id,
        "capability_id": capability_id,
        "role": role,
        "state": state,
        "artifact_kind": artifact_kind,
        "text": text,
    }
    body = {
        "bundle_id": value.bundle_id,
        "query": query,
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "items": selected,
        "accepted": value.accepted,
    }
    return FabricBundleQueryResult(
        **body,
        content_address=content_hash(body, prefix="module-fabric-bundle-query"),
    )


def export_module_fabric_bundle_query_csv(result: FabricBundleQueryResult) -> str:
    """Export any bounded query result with stable columns."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    keys: tuple[str, ...]
    if result.items:
        keys = tuple(sorted({str(key) for item in result.items for key in item}))
    else:
        keys = ("resource", "content_address")
    writer.writerow(keys)
    for item in result.items:
        writer.writerow(
            [
                ";".join(str(part) for part in item.get(key, ())) if isinstance(item.get(key), (list, tuple)) else item.get(key, "")
                for key in keys
            ]
        )
    return output.getvalue()


def diff_module_fabric_bundles(
    left: FabricBundle | str | Path,
    right: FabricBundle | str | Path,
) -> FabricBundleDiff:
    """Compare artifact identity and exact addresses across two bundles."""

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
    if isinstance(left, FabricBundle):
        left_verified = left.ready
    else:
        left_verified = verify_module_fabric_bundle(left).accepted
    if isinstance(right, FabricBundle):
        right_verified = right.ready
    else:
        right_verified = verify_module_fabric_bundle(right).accepted
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
    return FabricBundleDiff(**body, content_address=content_hash(body, prefix="module-fabric-bundle-diff"))


def verify_and_load_module_fabric_bundle(
    destination: str | Path,
    *,
    include_payloads: bool = False,
) -> tuple[FabricBundle, Any]:
    """Load a bundle alongside its independent filesystem verification."""

    verification = verify_module_fabric_bundle(destination)
    if not module_fabric_bundle_filesystem_integrity_ok(verification):
        raise ValidationError("module-fabric bundle filesystem integrity verification failed")
    return (
        load_module_fabric_bundle(destination, include_payloads=include_payloads, verify=False),
        verification,
    )


__all__ = [
    "diff_module_fabric_bundles",
    "export_module_fabric_bundle_query_csv",
    "load_module_fabric_bundle",
    "query_module_fabric_bundle",
    "verify_and_load_module_fabric_bundle",
]

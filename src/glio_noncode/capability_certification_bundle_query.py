"""Offline loading, querying, and diffing for certification bundles."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .capability_certification_bundle_contracts import (
    CAPABILITY_CERTIFICATION_BUNDLE_DEFAULT_LIMIT,
    CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST,
    CAPABILITY_CERTIFICATION_BUNDLE_MAX_LIMIT,
    CapabilityCertificationBundle,
    CertificationBundleArtifact,
    CertificationBundleArtifactKind,
    CertificationBundleCheck,
    CertificationBundleCheckPlane,
    CertificationBundleDiff,
    CertificationBundleQueryResult,
    CertificationBundleState,
)
from .serialization import canonical_json, content_hash, require_non_empty


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and bool(path.parts) and all(part not in {"", ".", ".."} for part in path.parts)


def _load_mapping(value: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(value)
    try:
        manifest = json.loads((root / CAPABILITY_CERTIFICATION_BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load certification bundle manifest: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise ValueError("certification bundle manifest must be an object")
    return root, manifest


def _check_from_dict(value: Mapping[str, Any]) -> CertificationBundleCheck:
    return CertificationBundleCheck(
        check_id=str(value.get("check_id", "unknown")),
        plane=CertificationBundleCheckPlane(str(value.get("plane", CertificationBundleCheckPlane.MANIFEST.value))),
        passed=bool(value.get("passed", False)),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "capability-certification-bundle-check:missing")),
    )


def load_capability_certification_bundle(
    destination: str | Path,
    *,
    include_payloads: bool = False,
) -> CapabilityCertificationBundle:
    """Load manifest metadata and optionally hydrate all artifact bytes."""

    root, manifest = _load_mapping(destination)
    raw_artifacts = manifest.get("artifacts", ())
    raw_checks = manifest.get("checks", ())
    if not isinstance(raw_artifacts, list) or not isinstance(raw_checks, list):
        raise ValueError("certification bundle collections must be arrays")
    artifacts: list[CertificationBundleArtifact] = []
    for raw in raw_artifacts:
        if not isinstance(raw, Mapping):
            raise ValueError("certification artifact entries must be objects")
        relative_path = str(raw.get("relative_path", ""))
        if not _safe_relative_path(relative_path):
            raise ValueError(f"unsafe certification artifact path: {relative_path!r}")
        payload = None
        if include_payloads:
            try:
                payload = (root / Path(*PurePosixPath(relative_path).parts)).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(f"cannot hydrate certification artifact {relative_path}: {exc}") from exc
        artifacts.append(
            CertificationBundleArtifact(
                artifact_id=str(raw.get("artifact_id", "")),
                relative_path=relative_path,
                media_type=str(raw.get("media_type", "")),
                kind=CertificationBundleArtifactKind(str(raw.get("kind", CertificationBundleArtifactKind.REPORT.value))),
                byte_count=int(raw.get("byte_count", 0)),
                line_count=int(raw.get("line_count", 0)),
                content_address=str(raw.get("content_address", "")),
                payload=payload,
            )
        )
    checks = tuple(_check_from_dict(item) for item in raw_checks if isinstance(item, Mapping))
    return CapabilityCertificationBundle(
        bundle_id=str(manifest.get("bundle_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        report_id=str(manifest.get("report_id", "")),
        run_id=str(manifest.get("run_id", "")),
        catalog_address=str(manifest.get("catalog_address", "")),
        runtime_address=str(manifest.get("runtime_address", "")),
        state=CertificationBundleState(str(manifest.get("state", CertificationBundleState.BLOCKED.value))),
        accepted=bool(manifest.get("accepted", False)),
        artifacts=tuple(artifacts),
        checks=checks,
        certificate_count=int(manifest.get("certificate_count", 0)),
        domain_count=int(manifest.get("domain_count", 0)),
        total_checks=int(manifest.get("total_checks", 0)),
        passed_check_count=int(manifest.get("passed_check_count", 0)),
        failed_check_count=int(manifest.get("failed_check_count", 0)),
        warning_count=int(manifest.get("warning_count", 0)),
        content_address=str(manifest.get("content_address", "")),
    )


def _as_bundle(value: CapabilityCertificationBundle | str | Path, *, include_payloads: bool = False) -> CapabilityCertificationBundle:
    if isinstance(value, CapabilityCertificationBundle):
        return value
    return load_capability_certification_bundle(value, include_payloads=include_payloads)


def _json_payload(bundle: CapabilityCertificationBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _certificate_rows(bundle: CapabilityCertificationBundle) -> tuple[dict[str, Any], ...]:
    report = _json_payload(bundle, "report")
    if not isinstance(report, Mapping) or not isinstance(report.get("certificates"), list):
        return ()
    rows = []
    for item in report["certificates"]:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "resource": "certificate",
                "capability_id": item.get("capability_id"),
                "domain_id": item.get("domain_id"),
                "domain": item.get("domain"),
                "layer": item.get("layer"),
                "capability_order": item.get("capability_order"),
                "capability": item.get("capability"),
                "kind": item.get("kind"),
                "release_wave": item.get("release_wave"),
                "mvp_64": item.get("mvp_64"),
                "registry_state": item.get("registry_state"),
                "state": item.get("state"),
                "implementation_count": item.get("implementation_count", 0),
                "implementation_resolved": item.get("implementation_resolved", 0),
                "test_count": item.get("test_count", 0),
                "test_resolved": item.get("test_resolved", 0),
                "failed_checks": item.get("failed_checks", 0),
                "content_address": item.get("content_address"),
            }
        )
    return tuple(sorted(rows, key=lambda item: (str(item.get("domain_id")), int(item.get("capability_order", 0)), str(item.get("capability_id")))))


def _domain_rows(bundle: CapabilityCertificationBundle) -> tuple[dict[str, Any], ...]:
    report = _json_payload(bundle, "report")
    if not isinstance(report, Mapping) or not isinstance(report.get("domain_summaries"), list):
        return ()
    return tuple(
        {"resource": "domain", **item}
        for item in report["domain_summaries"]
        if isinstance(item, Mapping)
    )


def _matches(item: Mapping[str, Any], text: str | None) -> bool:
    return not text or text.casefold() in canonical_json(item).casefold()


def query_capability_certification_bundle(
    bundle: CapabilityCertificationBundle | str | Path,
    *,
    resource: str = "certificates",
    capability_id: str | None = None,
    domain_id: str | None = None,
    mvp_only: bool = False,
    state: str | None = None,
    artifact_kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = CAPABILITY_CERTIFICATION_BUNDLE_DEFAULT_LIMIT,
    include_payloads: bool = False,
) -> CertificationBundleQueryResult:
    """Query certificates, domains, checks, or artifact metadata."""

    if offset < 0:
        raise ValueError("certification bundle offset cannot be negative")
    if limit < 1 or limit > CAPABILITY_CERTIFICATION_BUNDLE_MAX_LIMIT:
        raise ValueError(f"certification bundle limit must be between 1 and {CAPABILITY_CERTIFICATION_BUNDLE_MAX_LIMIT}")
    normalized = require_non_empty(resource, "resource").casefold()
    value = _as_bundle(bundle, include_payloads=include_payloads or normalized in {"certificates", "domains", "checks"})
    if normalized == "certificates":
        items: list[Mapping[str, Any]] = list(_certificate_rows(value))
        if capability_id is not None:
            items = [item for item in items if item.get("capability_id") == capability_id]
        if domain_id is not None:
            items = [item for item in items if item.get("domain_id") == domain_id]
        if mvp_only:
            items = [item for item in items if item.get("mvp_64")]
        if state is not None:
            items = [item for item in items if item.get("state") == state]
        items = [item for item in items if _matches(item, text)]
    elif normalized == "domains":
        items = list(_domain_rows(value))
        if domain_id is not None:
            items = [item for item in items if item.get("domain_id") == domain_id]
        items = [item for item in items if _matches(item, text)]
    elif normalized == "checks":
        report = _json_payload(value, "report")
        items = []
        if isinstance(report, Mapping):
            for item in [*report.get("checks", ()), *[check for certificate in report.get("certificates", ()) if isinstance(certificate, Mapping) for check in certificate.get("checks", ())]]:
                if isinstance(item, Mapping) and _matches(item, text):
                    items.append({"resource": "check", **item})
        if capability_id is not None:
            items = [item for item in items if item.get("capability_id") == capability_id]
        if domain_id is not None:
            items = [item for item in items if str(item.get("capability_id", "")).startswith(f"GNC-{domain_id}-")]
        if state is not None:
            items = [item for item in items if bool(item.get("passed")) == (state == "accepted")]
    elif normalized == "artifacts":
        items = [item.to_dict(include_payload=include_payloads) for item in value.artifacts]
        if artifact_kind is not None:
            items = [item for item in items if item.get("kind") == artifact_kind]
        items = [item for item in items if _matches(item, text)]
    else:
        raise ValueError("certification bundle resource must be certificates, domains, checks, or artifacts")
    selected = tuple(items[offset : offset + limit])
    query = {
        "resource": normalized,
        "capability_id": capability_id,
        "domain_id": domain_id,
        "mvp_only": mvp_only,
        "state": state,
        "artifact_kind": artifact_kind,
        "text": text,
    }
    body = {"bundle_id": value.bundle_id, "query": query, "total": len(items), "offset": offset, "limit": limit, "items": selected, "accepted": value.accepted}
    return CertificationBundleQueryResult(**body, content_address=content_hash(body, prefix="capability-certification-bundle-query"))


def export_capability_certification_bundle_query_csv(result: CertificationBundleQueryResult) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    keys = tuple(sorted({str(key) for item in result.items for key in item})) if result.items else ("resource", "content_address")
    writer.writerow(keys)
    for item in result.items:
        writer.writerow([";".join(str(part) for part in item.get(key, ())) if isinstance(item.get(key), (list, tuple)) else item.get(key, "") for key in keys])
    return output.getvalue()


def diff_capability_certification_bundles(
    left: CapabilityCertificationBundle | str | Path,
    right: CapabilityCertificationBundle | str | Path,
) -> CertificationBundleDiff:
    """Compare verified capability and artifact addresses."""

    left_value = _as_bundle(left, include_payloads=True)
    right_value = _as_bundle(right, include_payloads=True)
    left_rows = {item["capability_id"]: item for item in _certificate_rows(left_value)}
    right_rows = {item["capability_id"]: item for item in _certificate_rows(right_value)}
    common = set(left_rows) & set(right_rows)
    changed_caps = tuple(sorted(item for item in common if left_rows[item].get("content_address") != right_rows[item].get("content_address")))
    unchanged_caps = tuple(sorted(common - set(changed_caps)))
    left_artifacts = {item.artifact_id: item for item in left_value.artifacts}
    right_artifacts = {item.artifact_id: item for item in right_value.artifacts}
    common_artifacts = set(left_artifacts) & set(right_artifacts)
    changed_artifacts = tuple(sorted(item for item in common_artifacts if left_artifacts[item].content_address != right_artifacts[item].content_address))
    body = {
        "left_bundle_id": left_value.bundle_id,
        "right_bundle_id": right_value.bundle_id,
        "added_capability_ids": tuple(sorted(set(right_rows) - set(left_rows))),
        "removed_capability_ids": tuple(sorted(set(left_rows) - set(right_rows))),
        "changed_capability_ids": changed_caps,
        "unchanged_capability_ids": unchanged_caps,
        "added_artifact_ids": tuple(sorted(set(right_artifacts) - set(left_artifacts))),
        "removed_artifact_ids": tuple(sorted(set(left_artifacts) - set(right_artifacts))),
        "changed_artifact_ids": changed_artifacts,
        "left_accepted": left_value.accepted,
        "right_accepted": right_value.accepted,
        "accepted": left_value.ready and right_value.ready,
    }
    return CertificationBundleDiff(**body, content_address=content_hash(body, prefix="capability-certification-bundle-diff"))


__all__ = [
    "diff_capability_certification_bundles",
    "export_capability_certification_bundle_query_csv",
    "load_capability_certification_bundle",
    "query_capability_certification_bundle",
]
